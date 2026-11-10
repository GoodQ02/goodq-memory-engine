"""Exercise the installer-facing VLC staging and verification commands."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/install/vlc_runtime_payload.py"


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


@pytest.fixture
def package(tmp_path: Path) -> tuple[Path, Path]:
    files = {
        "vlc.exe": b"executable fixture",
        "libvlc.dll": b"API fixture",
        "libvlccore.dll": b"core fixture",
        "COPYING.txt": b"license fixture",
        "plugins/codec/libavcodec_plugin.dll": b"codec fixture",
    }
    archive = tmp_path / "vlc.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for name, value in files.items():
            output.writestr(f"vlc-3.0.24/{name}", value)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    members = [
        {"path": name, "size_bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
        for name, value in sorted(files.items())
    ]
    receipt = {"schema_version": 1, "version": "3.0.24", "archive_sha256": digest, "members": members}
    actual = json.loads((ROOT / "configs/offline_dependencies_manifest.json").read_text())
    record = dict(actual["dependencies"]["vlc"])
    record.update(sha256=digest, size_bytes=archive.stat().st_size, runtime_manifest_sha256=hashlib.sha256(_canonical(receipt)).hexdigest())
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"toolchains": {}, "dependencies": {"vlc": record}, "wheels": {"wheelhouse": []}}))
    return archive, manifest


def _command(mode: str, root: Path, package: tuple[Path, Path], profile: str = "PERSONAL_AIR_GAP") -> subprocess.CompletedProcess:
    archive, manifest = package
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), mode, "--root", str(root), "--archive", str(archive), "--manifest", str(manifest), "--profile", profile],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )


def test_installer_command_restores_all_members_then_rejects_tampering(tmp_path: Path, package) -> None:
    target = tmp_path / "restored"
    result = _command("stage", target, package)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["member_count"] == 5
    assert (target / "vlc.exe").read_bytes() == b"executable fixture"
    assert (target / "COPYING.txt").read_bytes() == b"license fixture"
    assert _command("verify", target, package).returncode == 0
    (target / "plugins/codec/libavcodec_plugin.dll").write_bytes(b"changed")
    rejected = _command("verify", target, package)
    assert rejected.returncode != 0
    assert "VLC runtime member mismatch" in rejected.stderr


@pytest.mark.parametrize("profile", ["PUBLIC_CPU_BASELINE", "PUBLIC_GPU_ENHANCED"])
def test_public_installer_cannot_admit_personal_vlc(tmp_path: Path, package, profile: str) -> None:
    target = tmp_path / "public"
    result = _command("stage", target, package, profile)
    assert result.returncode != 0
    assert "admitted only to PERSONAL_AIR_GAP" in result.stderr
    assert not target.exists()


def test_staging_refuses_changed_archive_and_existing_destination(tmp_path: Path, package) -> None:
    archive, _ = package
    target = tmp_path / "target"
    target.mkdir()
    (target / "keep.txt").write_text("preexisting")
    result = _command("stage", target, package)
    assert result.returncode != 0 and "destination must be new" in result.stderr
    assert (target / "keep.txt").read_text() == "preexisting"
    with archive.open("ab") as handle:
        handle.write(b"corruption")
    result = _command("stage", tmp_path / "new", package)
    assert result.returncode != 0 and "pinned size/SHA256" in result.stderr
    assert not (tmp_path / "new").exists()


def test_verification_refuses_forged_member_receipt(tmp_path: Path, package) -> None:
    target = tmp_path / "target"
    assert _command("stage", target, package).returncode == 0
    (target / "goodq-vlc-receipt.json").write_text('{}')
    result = _command("verify", target, package)
    assert result.returncode != 0 and "receipt does not match pinned inventory" in result.stderr


@pytest.mark.skipif(not shutil.which("powershell.exe"), reason="Windows installer command")
@pytest.mark.parametrize("profile,includes_vlc", [("PERSONAL_AIR_GAP", True), ("PUBLIC_CPU_BASELINE", False), ("PUBLIC_GPU_ENHANCED", False)])
def test_dependency_stager_applies_profile_before_admission(tmp_path: Path, package, profile: str, includes_vlc: bool) -> None:
    _, manifest = package
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(ROOT / "scripts/install/stage_dependencies.ps1"), "-Mode", "Audit", "-ManifestPath", str(manifest), "-CacheDir", str(tmp_path / "cache"), "-Profile", profile],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert ("Auditing Semantic Integrity: vlc_windows_x64_zip" in result.stdout) is includes_vlc


def test_personal_installer_stages_installs_and_verifies_vlc() -> None:
    builder = (ROOT / "scripts/install/build_installer.bat").read_text()
    installer = (ROOT / "scripts/install/goodq4all_installer.nsi").read_text()
    verifier = (ROOT / "scripts/install/verify_offline_suite.ps1").read_text()
    assert 'vlc_runtime_payload.py" stage --archive' in builder
    assert 'if /I "%GOODQ_INSTALLER_PROFILE%"=="PERSONAL_AIR_GAP"' in builder
    assert '!if "${GOODQ_INSTALLER_PROFILE}" == "PERSONAL_AIR_GAP"\n  SetOutPath "$INSTDIR\\vlc"' in installer
    assert 'File /r "staged\\vlc\\*.*"' in installer
    assert 'vlc_runtime_payload.py") verify --root' in verifier
    assert 'RMDir /r "$INSTDIR\\vlc"' in installer
