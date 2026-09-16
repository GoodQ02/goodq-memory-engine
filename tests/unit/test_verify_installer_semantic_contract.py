"""Mutation tests for the executable installer semantic compatibility gate."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER_RELATIVE = Path("scripts/install/verify_installer_semantic_contract.py")
CONTRACT_FIXTURE_FILES = (
    Path("goodq_version.py"),
    Path("configs/installer_profile_contract.yaml"),
    Path("scripts/install/installer_contract.py"),
    CHECKER_RELATIVE,
    Path("scripts/install/release_payload_packs.py"),
    Path("scripts/install/stage_profile_model_packs.py"),
    Path("scripts/install/verify_profile_model_payload.py"),
    Path("scripts/install/prebuild_readiness.py"),
    Path("scripts/install/LAUNCH_GOODQ.go"),
    Path("scripts/install/goodq4all_installer.nsi"),
    Path("scripts/install/generate_manifest.ps1"),
    Path("scripts/install/verify_release_asset.ps1"),
    Path("scripts/install/run_offline_release_build.bat"),
    Path("scripts/install/build_installer.bat"),
    Path("scripts/install/versioninfo.json"),
    Path(".github/workflows/ci.yml"),
)


def _contract_fixture(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    for relative in CONTRACT_FIXTURE_FILES:
        source = REPO_ROOT / relative
        destination = repo_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return repo_root


def _run_checker(repo_root: Path) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / CHECKER_RELATIVE),
            "--check",
            "--repo-root",
            str(repo_root),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed, json.loads(completed.stdout)


def _replace_once(repo_root: Path, relative: str, old: str, new: str) -> None:
    path = repo_root / relative
    source = path.read_text(encoding="utf-8")
    assert source.count(old) == 1, (relative, old, source.count(old))
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


def _failed_names(report: dict[str, object]) -> set[str]:
    return {
        str(check["name"])
        for check in report["checks"]
        if check["status"] == "mismatch"
    }


def test_current_repository_contract_is_compatible_and_read_only(tmp_path: Path) -> None:
    repo_root = _contract_fixture(tmp_path)
    before = {
        relative: (repo_root / relative).read_bytes()
        for relative in CONTRACT_FIXTURE_FILES
    }

    completed, report = _run_checker(repo_root)

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert report["schema"] == "goodq.installer-semantic-contract-check.v1"
    assert report["status"] == "compatible"
    assert report["compatible"] is True
    assert all(check["status"] == "compatible" for check in report["checks"])
    assert before == {
        relative: (repo_root / relative).read_bytes()
        for relative in CONTRACT_FIXTURE_FILES
    }


@pytest.mark.parametrize(
    ("relative", "old", "new", "failed_check"),
    [
        (
            "scripts/install/LAUNCH_GOODQ.go",
            "const releasePayloadSchemaVersion = 2",
            "const releasePayloadSchemaVersion = 1",
            "payload_schema",
        ),
        (
            "scripts/install/verify_profile_model_payload.py",
            'selected.get("schema_version") != SELECTED_CAPABILITIES_SCHEMA_VERSION',
            'selected.get("schema_version") != 1',
            "selected_capabilities_schema",
        ),
        (
            "scripts/install/stage_profile_model_packs.py",
            'manifest.get("schema_version") != MODEL_MEMBER_MANIFEST_SCHEMA_VERSION',
            'manifest.get("schema_version") != 1',
            "model_member_schema",
        ),
        (
            "scripts/install/goodq4all_installer.nsi",
            "GoodQ4All_Setup_3.0.1.exe",
            "GoodQ4All_Setup_9.9.9.exe",
            "product_version",
        ),
        (
            "scripts/install/run_offline_release_build.bat",
            'if /I not "%GOODQ_INSTALLER_PROFILE%"=="PUBLIC_GPU_ENHANCED" if /I not "%GOODQ_INSTALLER_PROFILE%"=="PERSONAL_AIR_GAP" (',
            'if /I not "%GOODQ_INSTALLER_PROFILE%"=="PUBLIC_GPU_ENHANCED" if /I not "%GOODQ_INSTALLER_PROFILE%"=="PERSONAL_DRIFT" (',
            "profiles",
        ),
        (
            "scripts/install/LAUNCH_GOODQ.go",
            'flag.String("apply-release-payload",',
            'flag.String("apply-payload",',
            "cli_contract",
        ),
        (
            "scripts/install/release_payload_packs.py",
            '"member_inventory_sha256": _json_inventory_sha256(member_records),',
            '"member_inventory_drift": _json_inventory_sha256(member_records),',
            "required_fields",
        ),
        (
            "scripts/install/release_payload_packs.py",
            '"status": PAYLOAD_INSTALL_RECEIPT_STATUS,',
            '"status": "applied_only",',
            "install_receipt",
        ),
        (
            "scripts/install/verify_release_asset.ps1",
            '$payloadContract.pack_format -ne "zip_stored_zip64"',
            '$payloadContract.pack_format -ne "zip_drift"',
            "payload_bindings",
        ),
        (
            "scripts/install/LAUNCH_GOODQ.go",
            "command.Stdin = bytes.NewReader(manifestBytes)",
            "command.Stdin = bytes.NewReader(nil)",
            "authenticated_handoff",
        ),
        (
            "scripts/install/release_payload_packs.py",
            "archive = stack.enter_context(zipfile.ZipFile(handle))",
            "archive = stack.enter_context(zipfile.ZipFile(pack_path))",
            "single_handle_processing",
        ),
        (
            "scripts/install/verify_profile_model_payload.py",
            "shell_command = (\n        \"set -euo pipefail; \"",
            "shell_command = translated.stdout.strip() + (\n        \"set -euo pipefail; \"",
            "wsl_argument_transport",
        ),
        (
            "scripts/install/run_offline_release_build.bat",
            "if errorlevel 1 (\n    echo [BLOCKED] Installer components are semantically incompatible. No output was created.",
            "if errorlevel 3 (\n    echo [BLOCKED] Installer components are semantically incompatible. No output was created.",
            "release_entrypoint_order",
        ),
        (
            "scripts/install/build_installer.bat",
            "if %ERRORLEVEL% neq 0 (\n    echo [ERROR] Installer components are semantically incompatible. No staging was created.",
            "if %ERRORLEVEL% equ 0 (\n    echo [ERROR] Installer components are semantically incompatible. No staging was created.",
            "builder_entrypoint_order",
        ),
    ],
)
def test_checker_rejects_semantic_mutations(
    tmp_path: Path,
    relative: str,
    old: str,
    new: str,
    failed_check: str,
) -> None:
    repo_root = _contract_fixture(tmp_path)
    _replace_once(repo_root, relative, old, new)

    completed, report = _run_checker(repo_root)

    assert completed.returncode == 2, completed.stderr or completed.stdout
    assert report["status"] == "mismatch"
    assert report["compatible"] is False
    assert failed_check in _failed_names(report)


@pytest.mark.parametrize(
    ("relative", "gate", "later", "failed_check"),
    [
        (
            "scripts/install/run_offline_release_build.bat",
            '"%GOODQ_DEV_PYTHON%" "%REPO_ROOT%\\scripts\\install\\verify_installer_semantic_contract.py" --check --repo-root "%REPO_ROOT%"',
            'mkdir "%GOODQ_RELEASE_OUTPUT_ROOT%"',
            "release_entrypoint_order",
        ),
        (
            "scripts/install/build_installer.bat",
            '"%GOODQ_DEV_PYTHON%" "%REPO_ROOT%\\scripts\\install\\verify_installer_semantic_contract.py" --check --repo-root "%REPO_ROOT%"',
            'mkdir "%STAGING_ROOT%"',
            "builder_entrypoint_order",
        ),
        (
            ".github/workflows/ci.yml",
            "conda run -n goodq_core python scripts/install/verify_installer_semantic_contract.py --check --repo-root .",
            "conda run -n goodq_core python -m pytest -q",
            "ci_order",
        ),
    ],
)
def test_checker_rejects_gate_ordering_after_mutating_work_begins(
    tmp_path: Path,
    relative: str,
    gate: str,
    later: str,
    failed_check: str,
) -> None:
    repo_root = _contract_fixture(tmp_path)
    path = repo_root / relative
    source = path.read_text(encoding="utf-8")
    assert source.count(gate) == 1
    assert source.count(later) == 1
    source = source.replace(gate, "", 1)
    source = source.replace(later, f"{later}\n{gate}", 1)
    path.write_text(source, encoding="utf-8")

    completed, report = _run_checker(repo_root)

    assert completed.returncode == 2, completed.stderr or completed.stdout
    assert failed_check in _failed_names(report)


def test_checker_reports_missing_configuration_as_execution_failure(tmp_path: Path) -> None:
    repo_root = _contract_fixture(tmp_path)
    (repo_root / "scripts/install/LAUNCH_GOODQ.go").unlink()

    completed, report = _run_checker(repo_root)

    assert completed.returncode == 1
    assert report["status"] == "error"
    assert report["compatible"] is False
    assert "LAUNCH_GOODQ.go" in report["error"]
