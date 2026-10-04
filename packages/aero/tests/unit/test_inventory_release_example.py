"""Production example contracts, least-privilege grants and safe preparation."""

import hashlib
import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest

from aero.domain.errors import AeroMeshDomainError
from aero.services.policy import check_policy
from aero.services.releases import validate_release

EXAMPLE = Path(__file__).resolve().parents[4] / "examples/dependency-inventory"
IMAGE = "registry.example/inventory@sha256:" + "a" * 64


def load_example(name):
    spec = importlib.util.spec_from_file_location(f"inventory_example_{name}", EXAMPLE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def helper():
    return load_example("prepare_release")


def test_prepared_release_matches_real_parser_and_independent_policy(tmp_path, helper):
    paths = helper.prepare_release(IMAGE, tmp_path / "prepared")
    manifest, release, policy = [
        json.loads(paths[k].read_text()) for k in ("manifest", "release", "policy")
    ]
    validate_release(release)
    requested = check_policy(release, policy)
    assert requested["images"] == [IMAGE]
    assert requested["tools"] == {"inventory": ["inventory_requirements_text"]}
    assert requested["credentials"] == []
    text = "requests==2.32.0\nrich>=15\n"
    jsonschema.validate({"requirements_text": text}, manifest["capabilities"]["input_contract"])
    observed = load_example("server").inventory_text(text)
    jsonschema.validate(observed, manifest["capabilities"]["output_contract"])
    assert observed["dependency_count"] == 2
    assert observed["unpinned_count"] == 1
    assert observed["sha256"] == hashlib.sha256(text.encode()).hexdigest()
    policy["providers"]["inventory"]["tools"] = []
    with pytest.raises(AeroMeshDomainError, match="does not grant tools"):
        check_policy(release, policy)


@pytest.mark.parametrize("image", ["inventory:latest", "sha256:" + "a" * 64, IMAGE + "\n"])
def test_prepare_rejects_unpinned_image_before_creating_output(tmp_path, helper, image):
    target = tmp_path / "prepared"
    with pytest.raises(ValueError, match="repository@sha256"):
        helper.prepare_release(image, target)
    assert not target.exists()


def test_prepare_never_overwrites_existing_output(tmp_path, helper):
    target = tmp_path / "prepared"
    target.mkdir()
    existing = target / "inventory.release.json"
    existing.write_text("operator content")
    with pytest.raises(FileExistsError):
        helper.prepare_release(IMAGE, target)
    assert existing.read_text() == "operator content"
    assert list(target.iterdir()) == [existing]


def test_failed_validation_rolls_back_new_outputs(tmp_path, helper, monkeypatch):
    target = tmp_path / "prepared"

    def reject(*_args):
        raise ValueError("rejected fixture")

    monkeypatch.setattr(helper, "check_policy", reject)
    with pytest.raises(ValueError, match="rejected fixture"):
        helper.prepare_release(IMAGE, target)
    assert not target.exists()


def test_text_mode_matches_file_parser_and_preserves_byte_identity():
    server = load_example("server")
    root = EXAMPLE / "fixtures"
    raw = (root / "requirements.txt").read_bytes()
    file_result = server.inventory(root, "requirements.txt")
    text_result = server.inventory_text(raw.decode("utf-8"))
    assert text_result.pop("path") == "<provided>"
    file_result.pop("path")
    assert text_result == file_result


@pytest.mark.parametrize("text", ["-r secret.txt\n", "rich>=15\\\n", "\u00e9" * (512 * 1024 + 1)])
def test_text_mode_rejects_directives_and_oversized_utf8(text):
    with pytest.raises(ValueError):
        load_example("server").inventory_text(text)
