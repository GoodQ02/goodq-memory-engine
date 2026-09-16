from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Callable

import pytest

from scripts.install.generate_release_fixture_pack import (
    FixturePackError,
    generate_fixture_pack,
    verify_fixture_pack,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_fixture(root: Path) -> tuple[Path, dict[str, dict[str, str]]]:
    repo_root = root / "repo"
    source_values = {
        "apollo_baseline": ("samples/onboarding_fixture.mp4", b"apollo-source"),
        "ui_walkthrough": ("samples/assets/ui_onboarding_walkthrough.mp4", b"lounge-source"),
        "demo_poster": ("samples/assets/goodq4all-demo-poster.jpg", b"poster-source"),
        "installer_mockup": ("samples/assets/one_click_installer_mockup.png", b"mockup-source"),
    }
    source_specs: dict[str, dict[str, str]] = {}
    for source_id, (relative, value) in source_values.items():
        path = repo_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
        source_specs[source_id] = {"path": relative, "sha256": _sha256(path)}
    return repo_root, source_specs


def _fake_ffmpeg(
    *,
    fail: bool = False,
    mutate_once: Path | None = None,
) -> Callable[[list[str], Path], subprocess.CompletedProcess[str]]:
    mutated = False

    def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        nonlocal mutated
        if command[-1] == "-version":
            return subprocess.CompletedProcess(command, 0, "ffmpeg version fixture-1.0\n", "")
        if mutate_once is not None and not mutated:
            mutate_once.write_bytes(mutate_once.read_bytes() + b"-drift")
            mutated = True
        if fail:
            return subprocess.CompletedProcess(command, 1, "", "synthetic ffmpeg failure")
        output = Path(command[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(f"encoded:{output.name}".encode("utf-8"))
        return subprocess.CompletedProcess(command, 0, "", "")

    return run


def _generate(
    tmp_path: Path,
    *,
    output_name: str = "fixture-pack",
    runner: Callable[[list[str], Path], subprocess.CompletedProcess[str]] | None = None,
) -> tuple[Path, Path, dict[str, dict[str, str]]]:
    repo_root, source_specs = _source_fixture(tmp_path)
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.write_bytes(b"sealed-ffmpeg")
    output_root = tmp_path / output_name
    manifest_path = generate_fixture_pack(
        repo_root=repo_root,
        output_root=output_root,
        ffmpeg_path=ffmpeg,
        source_specs=source_specs,
        run_command=runner or _fake_ffmpeg(),
    )
    return output_root, manifest_path, source_specs


def test_generator_rejects_a_missing_source(tmp_path: Path) -> None:
    repo_root, source_specs = _source_fixture(tmp_path)
    (repo_root / source_specs["demo_poster"]["path"]).unlink()
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.write_bytes(b"ffmpeg")

    with pytest.raises(FixturePackError, match="source is missing"):
        generate_fixture_pack(
            repo_root=repo_root,
            output_root=tmp_path / "output",
            ffmpeg_path=ffmpeg,
            source_specs=source_specs,
            run_command=_fake_ffmpeg(),
        )


def test_generator_rejects_a_nonempty_output_root(tmp_path: Path) -> None:
    repo_root, source_specs = _source_fixture(tmp_path)
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.write_bytes(b"ffmpeg")
    output_root = tmp_path / "output"
    output_root.mkdir()
    (output_root / "prior.txt").write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(FixturePackError, match="output root must be empty"):
        generate_fixture_pack(
            repo_root=repo_root,
            output_root=output_root,
            ffmpeg_path=ffmpeg,
            source_specs=source_specs,
            run_command=_fake_ffmpeg(),
        )


def test_generator_surfaces_ffmpeg_failure_without_a_terminal_manifest(tmp_path: Path) -> None:
    repo_root, source_specs = _source_fixture(tmp_path)
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.write_bytes(b"ffmpeg")
    output_root = tmp_path / "output"

    with pytest.raises(FixturePackError, match="FFmpeg failed"):
        generate_fixture_pack(
            repo_root=repo_root,
            output_root=output_root,
            ffmpeg_path=ffmpeg,
            source_specs=source_specs,
            run_command=_fake_ffmpeg(fail=True),
        )

    assert not (output_root / "fixture-pack-manifest.json").exists()


def test_generator_rechecks_sources_and_rejects_midrun_drift(tmp_path: Path) -> None:
    repo_root, source_specs = _source_fixture(tmp_path)
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.write_bytes(b"ffmpeg")
    drift_source = repo_root / source_specs["apollo_baseline"]["path"]

    with pytest.raises(FixturePackError, match="source drift"):
        generate_fixture_pack(
            repo_root=repo_root,
            output_root=tmp_path / "output",
            ffmpeg_path=ffmpeg,
            source_specs=source_specs,
            run_command=_fake_ffmpeg(mutate_once=drift_source),
        )


def test_verifier_rejects_nondeterministic_member_order(tmp_path: Path) -> None:
    output_root, manifest_path, _sources = _generate(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["members"].reverse()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    with pytest.raises(FixturePackError, match="unique and sorted"):
        verify_fixture_pack(output_root)


def test_verifier_rejects_output_hash_drift(tmp_path: Path) -> None:
    output_root, manifest_path, _sources = _generate(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    victim = output_root / manifest["members"][0]["path"]
    victim.write_bytes(victim.read_bytes() + b"-drift")

    with pytest.raises(FixturePackError, match="member (size|SHA256) drift"):
        verify_fixture_pack(output_root)


def test_valid_fixture_pack_round_trip_is_member_complete_and_secret_safe(tmp_path: Path) -> None:
    output_root, manifest_path, _sources = _generate(tmp_path)

    receipt = verify_fixture_pack(output_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert receipt["status"] == "verified"
    assert manifest["schema"] == "goodq.fixture-pack.v1"
    assert [item["path"] for item in manifest["members"]] == sorted(
        item["path"] for item in manifest["members"]
    )
    assert len(manifest["members"]) == 6
    assert len(manifest["sources"]) == 4
    assert manifest["member_count"] == 6
    assert manifest["members_sha256"] == receipt["members_sha256"]
    assert not any(str(tmp_path) in token for item in manifest["members"] for token in item["ffmpeg_args"])
    expected = {item["id"]: item["expected"] for item in manifest["members"]}
    assert expected["poster_face_ocr_object"]["face"] == "positive"
    assert expected["poster_face_ocr_object"]["ocr"] == "positive"
    assert expected["poster_face_ocr_object"]["object"] == "positive"
    assert expected["installer_ocr_no_face"]["face"] == "negative"
    assert expected["installer_ocr_no_face"]["ocr"] == "positive"
    assert all(value == "negative" for key, value in expected["empty_negative"].items() if key != "silence")
    assert expected["empty_negative"]["silence"] == "positive"


def test_fake_round_trip_is_deterministic_across_fresh_output_roots(tmp_path: Path) -> None:
    first_root, first_manifest_path, _sources = _generate(tmp_path / "first")
    second_root, second_manifest_path, _sources = _generate(tmp_path / "second")
    first = json.loads(first_manifest_path.read_text(encoding="utf-8"))
    second = json.loads(second_manifest_path.read_text(encoding="utf-8"))

    assert first["members_sha256"] == second["members_sha256"]
    assert [(item["path"], item["sha256"]) for item in first["members"]] == [
        (item["path"], item["sha256"]) for item in second["members"]
    ]
    assert verify_fixture_pack(first_root)["status"] == "verified"
    assert verify_fixture_pack(second_root)["status"] == "verified"
