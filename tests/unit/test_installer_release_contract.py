"""Regression contracts for the public Windows baseline installer."""

from __future__ import annotations

import hashlib
import json
import re
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


def test_preflight_proves_public_egress_instead_of_trusting_dns_cache() -> None:
    preflight = (REPO_ROOT / "scripts" / "install" / "preflight_check.ps1").read_text(
        encoding="utf-8"
    )

    assert "System.Net.Sockets.TcpClient" in preflight
    assert "1.1.1.1" in preflight
    assert "GetHostAddresses" not in preflight


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


def test_network_containment_wrapper_leaves_adapters_enabled_and_removes_its_rule() -> None:
    wrapper = (REPO_ROOT / "scripts" / "install" / "run_offline_release_with_network_toggle.ps1").read_text(
        encoding="utf-8"
    )
    launcher = (REPO_ROOT / "scripts" / "install" / "run_offline_release_build.bat").read_text(
        encoding="utf-8"
    )

    assert "New-NetFirewallRule" in wrapper
    assert "Remove-NetFirewallRule" in wrapper
    assert "PolicyStore ActiveStore" in wrapper
    assert "finally" in wrapper
    assert "network-toggle-receipt.json" in wrapper
    assert '$env:GOODQ_AUTO_NETWORK_TOGGLE = "1"' in wrapper
    assert 'GOODQ_AUTO_NETWORK_TOGGLE%' in launcher
    assert "Disable-NetAdapter" not in wrapper
    assert "Enable-NetAdapter" not in wrapper
    assert "CondaExe" in wrapper
    assert 'CONDA_EXE = $CondaExe' in wrapper
    assert '$env:GOODQ_RELEASE_OUTPUT_ROOT = $OutputRoot' in wrapper
    assert "& $BuildScript" in wrapper
    assert "cmd.exe /d /c" not in wrapper
    assert "interpreter_bindings.bat" in launcher
    assert 'set "GOODQ_DEV_PYTHON=%GOODQ_CONDA_ROOT%\\envs\\%GOODQ_CONDA_ENV%\\python.exe"' in launcher
    bindings = (REPO_ROOT / "scripts" / "_lib" / "interpreter_bindings.bat").read_text(encoding="utf-8")
    assert 'if /I "%%~xI"==".bat"' in bindings
    assert "Scripts\\conda.exe" in bindings


def test_offline_release_launcher_separates_release_assets_from_diagnostic_receipts() -> None:
    launcher = (REPO_ROOT / "scripts" / "install" / "run_offline_release_build.bat").read_text(
        encoding="utf-8"
    )

    assert 'set "ASSET_ROOT=%GOODQ_RELEASE_OUTPUT_ROOT%\\assets"' in launcher
    assert 'set "GOODQ_INSTALLER_OUTPUT_ROOT=%ASSET_ROOT%"' in launcher
    assert '-AssetRoot "%ASSET_ROOT%"' in launcher


def test_mini_agent_dependency_is_resolved_from_the_verified_offline_cache() -> None:
    lockfile = (REPO_ROOT / "requirements-baseline-lock.txt").read_text(encoding="utf-8")
    stager = (REPO_ROOT / "scripts" / "install" / "stage_dependencies.ps1").read_text(
        encoding="utf-8"
    )

    assert "goodq-mini-agent==0.1.1" in lockfile
    assert "goodq-mini-agent @ https://" not in lockfile
    assert "Declared wheel artifact" in stager
    assert "--ignore-installed" in stager


def test_offline_dependency_closure_uses_the_cp310_installer_target() -> None:
    launcher = (REPO_ROOT / "scripts" / "install" / "run_offline_release_build.bat").read_text(
        encoding="utf-8"
    )
    stager = (REPO_ROOT / "scripts" / "install" / "stage_dependencies.ps1").read_text(
        encoding="utf-8"
    )

    assert "GOODQ_DEV_PYTHON" in launcher
    assert "Offline closure verification requires CPython 3.10" in stager
    assert 'Join-Path $ScriptDir "staged\\runtime\\python.exe"' in stager
    assert "& $targetPython -m pip download" in stager


def test_offline_launcher_requires_an_operator_selected_output_root() -> None:
    launcher = (REPO_ROOT / "scripts" / "install" / "run_offline_release_build.bat").read_text(
        encoding="utf-8"
    )

    assert "One_Domingo" not in launcher
    assert "GOODQ_RELEASE_OUTPUT_ROOT" in launcher
    assert "Missing release output" in launcher


def test_release_signing_uses_a_staged_manifest_not_the_tracked_checkout() -> None:
    builder = (REPO_ROOT / "scripts" / "install" / "build_installer.bat").read_text(
        encoding="utf-8"
    )
    signer = (REPO_ROOT / "scripts" / "install" / "sign_manifest.go").read_text(encoding="utf-8")
    installer = (REPO_ROOT / "scripts" / "install" / "goodq4all_installer.nsi").read_text(
        encoding="utf-8"
    )

    assert "--manifest-path staged\\configs\\model_download_manifest.json" in builder
    assert "--signature-path staged\\configs\\model_download_manifest.json.sig" in builder
    assert 'File "staged\\configs\\model_download_manifest.json"' in installer
    assert 'File "staged\\configs\\model_download_manifest.json.sig"' in installer
    assert 'flag.String("manifest-path"' in signer
    assert 'flag.String("signature-path"' in signer


def test_builder_stages_nssm_from_the_manifest_verified_cache_location() -> None:
    builder = (REPO_ROOT / "scripts" / "install" / "build_installer.bat").read_text(
        encoding="utf-8"
    )

    assert 'copy /y "staged_cache\\host_tools\\nssm.zip" "staged\\nssm.zip" >nul' in builder
    assert "NSSM archive is missing from the verified cache" in builder
    assert "NSSM executable was not produced by the verified archive" in builder


def test_baseline_installer_stages_and_installs_the_pinned_ffmpeg_runtime() -> None:
    builder = (REPO_ROOT / "scripts" / "install" / "build_installer.bat").read_text(
        encoding="utf-8"
    )
    installer = (REPO_ROOT / "scripts" / "install" / "goodq4all_installer.nsi").read_text(
        encoding="utf-8"
    )
    verifier = (REPO_ROOT / "scripts" / "install" / "verify_offline_suite.ps1").read_text(
        encoding="utf-8"
    )

    assert 'staged_cache\\external\\ffmpeg-n8.1.2-34-g9b6c8969e0-win64-lgpl-shared-8.1.zip' in builder
    assert 'staged\\ffmpeg\\ffmpeg.exe -version >nul' in builder
    assert 'staged\\ffmpeg\\ffprobe.exe -version >nul' in builder
    assert 'staged\\ffmpeg\\SOURCE_URL.txt' in builder
    assert 'File /r "staged\\ffmpeg\\*.*"' in installer
    assert '"ffmpeg\\ffmpeg.exe"' in verifier
    assert '"ffmpeg\\ffprobe.exe"' in verifier


def test_uninstaller_removes_all_packaged_tool_directories() -> None:
    installer = (REPO_ROOT / "scripts" / "install" / "goodq4all_installer.nsi").read_text(
        encoding="utf-8"
    )

    packaged_roots = set(re.findall(r'SetOutPath "\\$INSTDIR\\\\([^"\\\\]+)"', installer))
    removed_roots = set(re.findall(r'RMDir /r "\\$INSTDIR\\\\([^"\\\\]+)"', installer))

    assert packaged_roots <= removed_roots


def test_dependency_stager_resolves_its_manifest_and_cache_from_its_own_location() -> None:
    stager = (REPO_ROOT / "scripts" / "install" / "stage_dependencies.ps1").read_text(
        encoding="utf-8"
    )

    assert "Join-Path $ScriptDir $ManifestPath" in stager
    assert "Join-Path $ScriptDir $CacheDir" in stager


def test_ffmpeg_release_source_is_pinned_and_declares_redistribution_metadata() -> None:
    manifest = json.loads(
        (REPO_ROOT / "configs" / "offline_dependencies_manifest.json").read_text(encoding="utf-8")
    )
    ffmpeg = manifest["dependencies"]["ffmpeg"]

    assert "/releases/download/autobuild-2026-08-03-14-02/" in ffmpeg["source_url"]
    assert "latest" not in ffmpeg["source_url"]
    assert ffmpeg["license"] == "LGPL-2.1-or-later"
    assert ffmpeg["redistribution_status"] == "allowed"
