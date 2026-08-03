"""Regression contracts for the public Windows baseline installer."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


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
