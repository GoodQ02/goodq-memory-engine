from pathlib import Path
import subprocess
import sys

import pytest

from scripts.assets.hf_snapshot_intake import (
    VaultError,
    cache_key,
    compare_members,
    find_snapshot,
    snapshot_members,
)


def test_cache_key_matches_hugging_face_layout() -> None:
    assert cache_key("owner/model") == "models--owner--model"
    assert cache_key("legacy-model-id") == "models--legacy-model-id"
    with pytest.raises(VaultError, match="invalid"):
        cache_key("owner//model")


def test_find_snapshot_prefers_the_populated_root_or_hub_snapshot(tmp_path: Path) -> None:
    revision = "a" * 40
    shadow = tmp_path / "models--owner--model" / "snapshots" / revision
    shadow.mkdir(parents=True)
    target = tmp_path / "hub" / "models--owner--model" / "snapshots" / revision
    target.mkdir(parents=True)
    (target / "weights.bin").write_bytes(b"weights")

    assert find_snapshot(tmp_path, "owner/model", revision) == target


def test_snapshot_members_and_compare_are_deterministic(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "README.md").write_text("terms", encoding="utf-8")
    (tmp_path / "nested" / "weights.bin").write_bytes(b"weights")

    assert snapshot_members(tmp_path) == {"README.md", "nested/weights.bin"}
    assert compare_members(["README.md", "config.json"], ["README.md", "extra.bin"]) == (
        ["config.json"],
        ["extra.bin"],
    )


def test_script_entrypoint_loads_from_the_repository_root() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/assets/hf_snapshot_intake.py", "--help"],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Verify and seal one pinned Hugging Face snapshot" in result.stdout
