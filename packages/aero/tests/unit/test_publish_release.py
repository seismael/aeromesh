"""Publication must use tested artifacts and leave incomplete releases private."""

import hashlib
import importlib.util
import io
import json
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "publish_release.py"
spec = importlib.util.spec_from_file_location("publish_release", SCRIPT)
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


def _artifact(path, name, version="1.0.0"):
    metadata = f"Metadata-Version: 2.3\nName: {name}\nVersion: {version}\n\n".encode()
    stem = name.replace("-", "_") + "-1.0.0"
    if path.suffix == ".whl":
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(f"{stem}.dist-info/METADATA", metadata)
    else:
        with tarfile.open(path, "w:gz") as archive:
            info = tarfile.TarInfo(f"{stem}/PKG-INFO")
            info.size = len(metadata)
            archive.addfile(info, io.BytesIO(metadata))


@pytest.fixture
def release(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    for directory, name in [("aero", "aero"), ("sdk-python", "aeromesh-sdk")]:
        project = root / "packages" / directory / "pyproject.toml"
        project.parent.mkdir(parents=True)
        project.write_text(f'[project]\nname = "{name}"\nversion = "1.0.0"\n')
    (root / "CHANGELOG.md").write_text("# Changelog\n\n## 1.0.0\n\nFirst production release.\n")
    (root / "constraints").mkdir()
    (root / "constraints" / "ci-python.txt").write_text("example==1.0.0\n")
    for args in [
        ["init", "-q", "-b", "main"],
        ["add", "."],
        ["-c", "user.name=Test", "-c", "user.email=test@example.org", "commit", "-qm", "release: v1.0.0"],
    ]:
        subprocess.run(["git", "-C", str(root), *args], check=True)
    sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    event = tmp_path / "event.json"
    event.write_text(json.dumps({
        "ref": "refs/heads/main", "after": sha,
        "head_commit": {"id": sha, "message": "release: v1.0.0"},
        "repository": {"full_name": "owner/aeromesh"},
    }))
    environment = {
        "GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": sha, "GITHUB_REPOSITORY": "owner/aeromesh",
        "GITHUB_EVENT_PATH": str(event),
    }
    dist = root / "dist"
    dist.mkdir()
    for name in ("aero", "aeromesh-sdk"):
        for suffix in (".tar.gz", "-py3-none-any.whl"):
            _artifact(dist / (name.replace("-", "_") + "-1.0.0" + suffix), name)
    return root, dist, environment


class GitHub:
    """Only the remote publication boundary is substituted."""

    def __init__(self, sha):
        self.sha = sha
        self.tag = None
        self.release = None
        self.assets = {}
        self.calls = []
        self.fail_upload = False

    def run(self, args):
        self.calls.append(args)
        if args[0] == "api":
            if "/git/ref/tags/" in args[1]:
                result = {"object": {"type": "commit", "sha": self.tag}} if self.tag else None
            elif args[1].endswith("/releases?per_page=100"):
                assert args[2:] == ["--paginate", "--slurp"]
                result = [[{**self.release, "assets": [{"name": name} for name in self.assets]}]] if self.release else [[]]
            else:
                pytest.fail(f"Unexpected API: {args}")
            if result is None:
                return subprocess.CompletedProcess(args, 1, "", "gh: Not Found (HTTP 404)")
            return subprocess.CompletedProcess(args, 0, json.dumps(result), "")
        command = args[1]
        if command == "create":
            assert "--draft" in args
            self.release = {
                "draft": True, "target_commitish": args[args.index("--target") + 1],
                "tag_name": args[2],
                "body": Path(args[args.index("--notes-file") + 1]).read_text(),
            }
        elif command == "upload":
            assert self.release["draft"]
            if self.fail_upload:
                return subprocess.CompletedProcess(args, 1, "", "upload interrupted")
            for argument in args[3:args.index("--repo")]:
                path = Path(argument)
                assert path.name not in self.assets, "Never overwrite assets"
                self.assets[path.name] = path.read_bytes()
        elif command == "download":
            name = args[args.index("--pattern") + 1]
            directory = Path(args[args.index("--dir") + 1])
            (directory / name).write_bytes(self.assets[name])
        elif command == "edit":
            assert self.release["draft"] and len(self.assets) == 6
            assert "--draft=false" in args
            self.release["draft"] = False
            self.tag = self.sha
        else:
            pytest.fail(f"Unexpected gh command: {args}")
        return subprocess.CompletedProcess(args, 0, "", "")


@pytest.fixture
def github(release, monkeypatch):
    github = GitHub(release[2]["GITHUB_SHA"])
    monkeypatch.setattr(publisher, "_gh", github.run)
    return github


def _publish(release):
    root, dist, environment = release
    publisher.publish(root, dist, environment)


def test_publishes_exact_tested_artifacts_only_after_upload(release, github):
    original = {path.name: path.read_bytes() for path in release[1].iterdir()}
    _publish(release)
    assert github.release["draft"] is False
    assert github.tag == release[2]["GITHUB_SHA"]
    assert {name: github.assets[name] for name in original} == original
    assert github.assets["ci-python.txt"] == (release[0] / "constraints/ci-python.txt").read_bytes()
    checksums = dict(line.split("  ")[::-1] for line in github.assets["SHA256SUMS"].decode().splitlines())
    assert checksums == {name: hashlib.sha256(value).hexdigest() for name, value in github.assets.items() if name != "SHA256SUMS"}
    assert {path.name for path in release[1].iterdir()} == set(original)


@pytest.mark.parametrize("field,value", [
    ("GITHUB_EVENT_NAME", "pull_request"), ("GITHUB_REF", "refs/heads/topic"),
    ("GITHUB_SHA", "f" * 40), ("GITHUB_REPOSITORY", "owner/repo;bad"),
])
def test_rejects_untrusted_publication_context(release, github, field, value):
    release[2][field] = value
    with pytest.raises(publisher.PublicationError):
        _publish(release)
    assert github.calls == []


def test_rejects_event_subject_and_checked_out_commit_disagreement(release, github):
    event = Path(release[2]["GITHUB_EVENT_PATH"])
    contents = json.loads(event.read_text())
    contents["head_commit"]["message"] = "release: v2.0.0"
    event.write_text(json.dumps(contents))
    with pytest.raises(publisher.PublicationError):
        _publish(release)
    assert github.calls == []


@pytest.mark.parametrize("defect", ["extra", "missing", "wrong_metadata", "wrong_source_metadata", "wrong_project_version"])
def test_rejects_unvalidated_distribution_set(release, github, defect):
    root, dist, _ = release
    wheel = dist / "aero-1.0.0-py3-none-any.whl"
    if defect == "extra":
        (dist / "unvalidated.whl").write_bytes(b"bad")
    elif defect == "missing":
        wheel.unlink()
    elif defect == "wrong_metadata":
        _artifact(wheel, "aero", "9.0.0")
    elif defect == "wrong_source_metadata":
        _artifact(dist / "aero-1.0.0.tar.gz", "aero", "9.0.0")
    else:
        (root / "packages/aero/pyproject.toml").write_text('[project]\nname="aero"\nversion="9.0.0"\n')
    with pytest.raises(publisher.PublicationError):
        _publish(release)
    assert github.calls == []


def test_upload_failure_keeps_release_draft_and_resumes(release, github):
    github.fail_upload = True
    with pytest.raises(publisher.PublicationError, match="upload interrupted"):
        _publish(release)
    assert github.release["draft"] is True
    assert github.tag is None
    github.fail_upload = False
    _publish(release)
    assert github.release["draft"] is False
    assert sum(args[:2] == ["release", "create"] for args in github.calls) == 1


def test_published_rerun_verifies_assets_without_mutation(release, github):
    _publish(release)
    github.calls.clear()
    _publish(release)
    assert all(args[0] == "api" or args[:2] == ["release", "download"] for args in github.calls)


@pytest.mark.parametrize("defect", ["tag", "corrupt_asset", "extra_asset", "missing_asset", "draft_target", "draft_notes"])
def test_existing_release_conflicts_fail_closed(release, github, defect):
    _publish(release)
    if defect == "tag":
        github.tag = "f" * 40
    elif defect == "corrupt_asset":
        github.assets["aero-1.0.0-py3-none-any.whl"] = b"corrupt"
    elif defect == "extra_asset":
        github.assets["extra"] = b"unexpected"
    elif defect == "missing_asset":
        del github.assets["ci-python.txt"]
    elif defect == "draft_target":
        github.release.update(draft=True, target_commitish="main")
    else:
        github.release.update(draft=True, body="Unreviewed notes")
    github.calls.clear()
    with pytest.raises(publisher.PublicationError):
        _publish(release)
    assert all(args[0] == "api" or args[:2] == ["release", "download"] for args in github.calls)


def test_same_commit_draft_with_some_matching_assets_is_resumed(release, github):
    github.release = {
        "draft": True, "target_commitish": github.sha, "tag_name": "v1.0.0",
        "body": "First production release.\n",
    }
    path = release[1] / "aero-1.0.0-py3-none-any.whl"
    github.assets[path.name] = path.read_bytes()
    _publish(release)
    assert not github.release["draft"]
    assert not any(args[:2] == ["release", "create"] for args in github.calls)


def test_remote_read_failure_never_creates_a_release(release, github, monkeypatch):
    def unavailable(args):
        github.calls.append(args)
        return subprocess.CompletedProcess(args, 1, "", "gh: API rate limit exceeded (HTTP 403)")

    monkeypatch.setattr(publisher, "_gh", unavailable)
    with pytest.raises(publisher.PublicationError, match="rate limit"):
        _publish(release)
    assert github.release is None
    assert all(args[0] == "api" for args in github.calls)


@pytest.mark.parametrize("subject", ["release: v1.0.0 extra", "release: v01.0.0", "release: v1.0.0-rc1"])
def test_release_requires_exact_stable_version_subject(release, github, subject):
    event = Path(release[2]["GITHUB_EVENT_PATH"])
    contents = json.loads(event.read_text())
    contents["head_commit"]["message"] = subject
    event.write_text(json.dumps(contents))
    with pytest.raises(publisher.PublicationError, match="exactly"):
        _publish(release)
    assert github.calls == []
