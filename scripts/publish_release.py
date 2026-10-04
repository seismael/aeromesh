"""Publish CI's exact validated artifacts as an immutable GitHub release.

The CI job supplies a push-to-main event and waits for every offline release
gate. Uploads happen while the release is a draft. Reruns verify existing bytes;
they never move tags, replace assets, or silently accept a conflicting release.
No package build or PyPI publication is performed here.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tarfile
import tempfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path


class PublicationError(RuntimeError):
    """A release prerequisite or immutable remote state did not match."""


def _run(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=180)


def _gh(args):
    return _run(["gh", *args])


def _checked(result):
    if result.returncode:
        raise PublicationError(result.stderr.strip() or "Release command failed")
    return result.stdout


def _api(path, *, missing_ok=False):
    result = _gh(["api", path])
    if missing_ok and result.returncode and "(HTTP 404)" in result.stderr:
        return None
    return json.loads(_checked(result))


def _context(root, environment):
    if (environment.get("GITHUB_EVENT_NAME"), environment.get("GITHUB_REF")) != (
        "push", "refs/heads/main"
    ):
        raise PublicationError("Releases require a push to main")
    repository = environment.get("GITHUB_REPOSITORY", "")
    sha = environment.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise PublicationError("Invalid repository")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise PublicationError("Invalid commit SHA")
    event = json.loads(Path(environment["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    if (
        event.get("ref") != "refs/heads/main" or event.get("after") != sha
        or event.get("deleted") or event.get("repository", {}).get("full_name") != repository
        or (event.get("head_commit") or {}).get("id") != sha
    ):
        raise PublicationError("Push event does not match the release commit and repository")
    message = event["head_commit"].get("message", "")
    subject = message.partition("\n")[0]
    match = re.fullmatch(r"release: v((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))", subject)
    if not match:
        raise PublicationError("Release commit subject must be exactly release: vX.Y.Z")
    head = _checked(_run(["git", "-C", str(root), "rev-parse", "HEAD"])).strip()
    local_subject = _checked(_run(["git", "-C", str(root), "show", "-s", "--format=%s", "HEAD"])).strip()
    if head != sha or local_subject != subject:
        raise PublicationError("Checkout is not the tested release commit")
    return repository, sha, match.group(1)


def _hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _metadata(path, name, version):
    stem = name.replace("-", "_") + "-" + version
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            target = stem + ".dist-info/METADATA"
            if [item for item in archive.namelist() if item.endswith(".dist-info/METADATA")] != [target]:
                raise PublicationError(f"Unexpected wheel metadata in {path.name}")
            metadata = archive.read(target)
    else:
        with tarfile.open(path, "r:gz") as archive:
            target = stem + "/PKG-INFO"
            entries = [item for item in archive.getmembers() if item.name == target]
            if len(entries) != 1 or not entries[0].isfile():
                raise PublicationError(f"Missing source metadata in {path.name}")
            with archive.extractfile(entries[0]) as stream:
                metadata = stream.read()
    fields = BytesParser().parsebytes(metadata)
    if fields.get_all("Name") != [name] or fields.get_all("Version") != [version]:
        raise PublicationError(f"Package metadata disagrees with release: {path.name}")


def _artifacts(root, dist, version):
    expected = {}
    for directory, name in (("aero", "aero"), ("sdk-python", "aeromesh-sdk")):
        project = tomllib.loads((root / "packages" / directory / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        if project.get("name") != name or project.get("version") != version:
            raise PublicationError(f"{name} must declare release version {version}")
        for suffix in ("-py3-none-any.whl", ".tar.gz"):
            filename = name.replace("-", "_") + "-" + version + suffix
            expected[filename] = (name, dist / filename)
    if {path.name for path in dist.iterdir()} != set(expected):
        raise PublicationError("Expected exactly both wheels and source distributions")
    for name, path in expected.values():
        if path.is_symlink() or not path.is_file():
            raise PublicationError(f"Artifact is not a regular file: {path.name}")
        _metadata(path, name, version)
    return {filename: path for filename, (_, path) in expected.items()}


def _notes(root, version):
    content = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"^## " + re.escape(version) + r"[ \t]*$\n(.*?)(?=^## |\Z)", content, re.MULTILINE | re.DOTALL)
    if not match or not match.group(1).strip():
        raise PublicationError(f"CHANGELOG.md has no release notes for {version}")
    return match.group(1).strip() + "\n"


def _tag_sha(repository, tag):
    ref = _api(f"repos/{repository}/git/ref/tags/{tag}", missing_ok=True)
    if ref is None:
        return None
    target = ref["object"]
    for _ in range(5):
        if not re.fullmatch(r"[0-9a-f]{40}", target.get("sha", "")):
            raise PublicationError("Invalid tag object")
        if target.get("type") == "commit":
            return target["sha"]
        if target.get("type") != "tag":
            break
        target = _api(f"repos/{repository}/git/tags/{target['sha']}")["object"]
    raise PublicationError("Release tag does not resolve to a commit")


def _release(repository, tag, notes):
    # The by-tag endpoint is for published releases. Authenticated listings also
    # include drafts; paginate so an older unfinished draft cannot be missed.
    pages = json.loads(_checked(_gh([
        "api", f"repos/{repository}/releases?per_page=100", "--paginate", "--slurp",
    ])))
    matches = [release for page in pages for release in page if release["tag_name"] == tag]
    if len(matches) > 1:
        raise PublicationError("Multiple releases use the requested tag")
    if not matches:
        return None
    release = matches[0]
    if (release.get("body") or "").strip() != notes.strip():
        raise PublicationError("Existing release notes differ from CHANGELOG.md")
    return release


def _verify_assets(repository, tag, release, artifacts, hashes, *, complete):
    names = [asset["name"] for asset in release["assets"]]
    if len(names) != len(set(names)) or not set(names).issubset(artifacts):
        raise PublicationError("Remote release contains unexpected or duplicate assets")
    if complete and set(names) != set(artifacts):
        raise PublicationError("Published release has an incomplete asset set")
    # Download to compare bytes even when GitHub does not supply asset digests.
    with tempfile.TemporaryDirectory(prefix="aeromesh-release-verify-") as directory:
        for name in names:
            _checked(_gh(["release", "download", tag, "--repo", repository,
                          "--pattern", name, "--dir", directory]))
            if _hash(Path(directory) / name) != hashes[name]:
                raise PublicationError(f"Remote asset differs from validated artifact: {name}")
    return set(names)


def publish(root, dist, environment):
    repository, sha, version = _context(root, environment)
    artifacts = _artifacts(root, dist, version)
    notes = _notes(root, version)
    constraints = root / "constraints" / "ci-python.txt"
    if not constraints.is_file() or constraints.is_symlink():
        raise PublicationError("Missing validated dependency constraints")
    artifacts[constraints.name] = constraints
    tag = "v" + version
    tag_sha = _tag_sha(repository, tag)
    if tag_sha is not None and tag_sha != sha:
        raise PublicationError("Existing release tag points to a different commit")
    with tempfile.TemporaryDirectory(prefix="aeromesh-release-") as directory:
        temporary = Path(directory)
        hashes = {name: _hash(path) for name, path in artifacts.items()}
        checksum = temporary / "SHA256SUMS"
        checksum.write_text("".join(f"{hashes[name]}  {name}\n" for name in sorted(hashes)), encoding="utf-8")
        artifacts[checksum.name] = checksum
        hashes[checksum.name] = _hash(checksum)
        notes_file = temporary / "notes.md"
        notes_file.write_text(notes, encoding="utf-8")
        release = _release(repository, tag, notes)
        if release is not None and not release["draft"]:
            if tag_sha != sha:
                raise PublicationError("Published release must have the exact commit tag")
            _verify_assets(repository, tag, release, artifacts, hashes, complete=True)
            print(f"{tag} already published; commit and all asset bytes verified")
            return
        if release is not None and release["target_commitish"] != sha:
            raise PublicationError("Existing draft does not target the tested commit")
        if release is None:
            _checked(_gh(["release", "create", tag, "--repo", repository,
                          "--draft", "--target", sha, "--title", f"AeroMesh {tag}",
                          "--notes-file", str(notes_file)]))
            release = _release(repository, tag, notes)
            if release is None or not release["draft"] or release["target_commitish"] != sha:
                raise PublicationError("Created draft does not match the tested commit")
        names = _verify_assets(repository, tag, release, artifacts, hashes, complete=False)
        missing = [str(artifacts[name]) for name in sorted(artifacts.keys() - names)]
        if missing:
            _checked(_gh(["release", "upload", tag, *missing, "--repo", repository]))
        # The draft stays private if any upload or verification fails.
        release = _release(repository, tag, notes)
        if release is None or not release["draft"] or release["target_commitish"] != sha:
            raise PublicationError("Draft changed before publication")
        _verify_assets(repository, tag, release, artifacts, hashes, complete=True)
        tag_sha = _tag_sha(repository, tag)
        if tag_sha is not None and tag_sha != sha:
            raise PublicationError("Release tag changed before publication")
        _checked(_gh(["release", "edit", tag, "--repo", repository, "--draft=false"]))
        if _tag_sha(repository, tag) != sha:
            raise PublicationError("Published tag did not resolve to tested commit")
        print(f"Published {tag} from {sha} with verified artifacts and SHA256SUMS")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    arguments = parser.parse_args()
    try:
        publish(Path(__file__).resolve().parents[1], arguments.dist.resolve(), os.environ)
    except (PublicationError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired,
            zipfile.BadZipFile, tarfile.TarError) as error:
        parser.exit(1, f"Release stopped: {error}\n")


if __name__ == "__main__":
    main()
