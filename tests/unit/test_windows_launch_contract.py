from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def read_repo_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_launcher_dry_run_does_not_start_qdrant_service_or_create_dirs() -> None:
    launcher = read_repo_text("LAUNCH_GOODQ.ps1")

    assert 'Write-StatusLine "Qdrant Service" "Not started (dry run)" "INFO"' in launcher
    assert 'Write-StatusLine (Split-Path $dir -Leaf) "Missing (dry run; not created)" "WARN"' in launcher
    assert 'SERVICE LAUNCH PREVIEW' in launcher
    assert "GOODQ4ALL READINESS SUMMARY" in launcher
    assert "Qdrant Store:" in launcher
    assert "Production-Ready" not in launcher


def test_qdrant_telemetry_is_disabled_for_config_service_and_foreground_start() -> None:
    qdrant_config = read_repo_text("vendor/qdrant/config.yaml")
    service_installer = read_repo_text("scripts/qdrant/INSTALL_QDRANT_SERVICE.bat")
    foreground_start = read_repo_text("scripts/qdrant/START_QDRANT.bat")

    assert "telemetry_disabled: true" in qdrant_config
    assert "QDRANT__TELEMETRY_DISABLED=true" in service_installer
    assert "QDRANT__TELEMETRY_DISABLED=true" in foreground_start
