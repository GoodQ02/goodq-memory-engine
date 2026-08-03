"""Regression contracts for the public Windows baseline installer."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _sync_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo_root = tmp_path / "repo"
    install_root = repo_root / "scripts" / "install"
    install_root.mkdir(parents=True)
    for name in ("sync_nsi_version.py", "goodq4all_installer.nsi", "versioninfo.json"):
        shutil.copy2(REPO_ROOT / "scripts" / "install" / name, install_root / name)
    shutil.copy2(REPO_ROOT / "goodq_version.py", repo_root / "goodq_version.py")
    nsi_path = install_root / "goodq4all_installer.nsi"
    nsi_path.write_text(
        nsi_path.read_text(encoding="utf-8").replace("2.5.8", "2.5.8-rc5"),
        encoding="utf-8",
    )
    return install_root / "sync_nsi_version.py", nsi_path, install_root / "versioninfo.json"


def test_sync_check_reports_stale_metadata_without_writing(tmp_path: Path) -> None:
    sync_script, nsi_path, versioninfo_path = _sync_fixture(tmp_path)
    before_nsi = nsi_path.read_bytes()
    before_versioninfo = versioninfo_path.read_bytes()

    result = subprocess.run(
        [sys.executable, str(sync_script), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "out of sync" in result.stdout.lower()
    assert nsi_path.read_bytes() == before_nsi
    assert versioninfo_path.read_bytes() == before_versioninfo


def test_installer_template_names_the_canonical_stable_version() -> None:
    source = (REPO_ROOT / "scripts" / "install" / "goodq4all_installer.nsi").read_text(
        encoding="utf-8"
    )

    assert "GoodQ4All_Setup_2.5.8.exe" in source
    assert "2.5.8-rc" not in source


def test_private_builder_declares_its_input_and_output_boundaries() -> None:
    source = (REPO_ROOT / "scripts" / "install" / "build_installer.bat").read_text(
        encoding="utf-8"
    )

    assert "GOODQ_INSTALLER_BUILD_ROOT" in source
    assert "Missing private build input" in source
    assert "GOODQ_INSTALLER_OUTPUT_ROOT" in source


def test_release_asset_verifier_defines_the_baseline_asset_set() -> None:
    verifier = REPO_ROOT / "scripts" / "install" / "verify_release_asset.ps1"

    assert verifier.exists()
    source = verifier.read_text(encoding="utf-8")
    assert "GoodQ4All_Setup_$ExpectedVersion.exe" in source
    assert "LAUNCH_GOODQ.exe" in source
    assert "goodq_audio_wsl" not in source


def test_release_asset_verifier_reports_an_empty_asset_directory(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REPO_ROOT / "scripts" / "install" / "verify_release_asset.ps1"),
            "-AssetRoot",
            str(tmp_path),
            "-ExpectedVersion",
            "2.5.8",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Release asset set must contain exactly" in result.stderr


def _write_asset_fixture(asset_root: Path, *, source_note: str | None = None) -> None:
    installer = asset_root / "GoodQ4All_Setup_2.5.8.exe"
    launcher = asset_root / "LAUNCH_GOODQ.exe"
    installer.write_bytes(b"installer")
    launcher.write_bytes(b"launcher")
    manifest = {
        "product_version": "2.5.8",
        "source_commit": "12f577e9",
        "source_tree_clean": True,
        "profile": "BASELINE",
        "excluded_optional_components": ["wsl_audio", "local_llm_serving", "gpu_enhanced"],
        "sha256": hashlib.sha256(installer.read_bytes()).hexdigest(),
        "launcher_sha256": hashlib.sha256(launcher.read_bytes()).hexdigest(),
    }
    if source_note is not None:
        manifest["source_note"] = source_note
    manifest_path = asset_root / "GoodQ4All_Setup_2.5.8.release_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    checksum_lines = [
        f"{manifest['sha256']} *{installer.name}",
        f"{manifest['launcher_sha256']} *{launcher.name}",
        f"{hashlib.sha256(manifest_path.read_bytes()).hexdigest()} *{manifest_path.name}",
    ]
    (asset_root / "GoodQ4All_Setup_2.5.8.sha256").write_text("\n".join(checksum_lines), encoding="ascii")


def _run_asset_verifier(asset_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REPO_ROOT / "scripts" / "install" / "verify_release_asset.ps1"),
            "-AssetRoot",
            str(asset_root),
            "-ExpectedVersion",
            "2.5.8",
            "-ExpectedCommit",
            "12f577e9",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_release_asset_verifier_rejects_a_nested_payload(tmp_path: Path) -> None:
    _write_asset_fixture(tmp_path)
    nested = tmp_path / "hidden_payload"
    nested.mkdir()
    (nested / "goodq_audio_wsl.tar").write_bytes(b"not allowed")

    result = _run_asset_verifier(tmp_path)

    assert result.returncode == 1
    assert "Release asset set must contain exactly" in result.stderr


@pytest.mark.parametrize("private_path", [r"C:\Users\jdben\private-build", r"c:/users/jdben/private-build"])
def test_release_asset_verifier_rejects_a_normal_windows_user_path(
    tmp_path: Path, private_path: str
) -> None:
    _write_asset_fixture(tmp_path, source_note=private_path)

    result = _run_asset_verifier(tmp_path)

    assert result.returncode == 1
    assert "Manifest contains private token" in result.stderr


def test_baseline_installer_omits_wsl_and_gpu_payload_paths() -> None:
    installer = (REPO_ROOT / "scripts" / "install" / "goodq4all_installer.nsi").read_text(
        encoding="utf-8"
    )
    builder = (REPO_ROOT / "scripts" / "install" / "build_installer.bat").read_text(
        encoding="utf-8"
    )

    assert '!if 0\n  ; --- STATE 8: WSL pre-baked distro import ---' in installer
    assert '!if 0\nSection /o "GPU-Accelerated WSL2 Audio"' in installer
    assert 'File /nonfatal "staged\\wsl\\goodq_audio_wsl.tar"' in installer
    assert 'mkdir "staged\\wsl"' not in builder
    assert "cublas64_12.dll" not in builder


def test_preflight_scans_every_source_root_packaged_by_nsis() -> None:
    preflight = (REPO_ROOT / "scripts" / "install" / "preflight_check.ps1").read_text(
        encoding="utf-8"
    )

    for source_root in ("api", "cli", "steps", "ui", "agents", "lib", "common", "retrieval", "pipelines"):
        assert f"..\\..\\{source_root}" in preflight
    assert "Get-ChildItem -Path $scanRoots" in preflight


def test_offline_release_launcher_requires_real_preflight_and_asset_receipt() -> None:
    launcher = (REPO_ROOT / "scripts" / "install" / "run_offline_release_build.bat").read_text(
        encoding="utf-8"
    )

    assert "preflight_check.ps1" in launcher
    assert "GOODQ_BYPASS_NETWORK_CHECK" not in launcher
    assert "build_installer.bat" in launcher
    assert "verify_release_asset.ps1" in launcher
    assert "offline_build.log" in launcher
    assert "offline_build_receipt.txt" in launcher
