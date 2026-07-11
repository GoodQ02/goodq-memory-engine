import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "tests" / "runtime_evidence_manifest.json"
RUNNER_PATH = REPO_ROOT / "scripts" / "dev" / "run_runtime_evidence.ps1"
VALIDATOR_RUNNER_PATH = REPO_ROOT / "scripts" / "dev" / "run_r18_validator_suite.ps1"


def test_runtime_manifest_nodes_are_explicit_and_present():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    nodes = manifest["golden"]["required_test_nodes"]

    assert manifest["schema_version"] == 1
    assert len(nodes) == 4
    for node in nodes:
        relative_path = node.split("::", 1)[0]
        assert (REPO_ROOT / relative_path).is_file(), node


def test_runtime_evidence_runner_lists_without_calling_services():
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(RUNNER_PATH),
            "-Profile",
            "golden",
            "-ListOnly",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "profile=golden" in result.stdout
    assert "epoch=epoch_2026_07_05_home_memory_clean_01" in result.stdout
    assert "test_runtime_profile_services.py" in result.stdout


def test_runtime_evidence_runner_collects_from_an_unrelated_directory(tmp_path):
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(RUNNER_PATH),
            "-Profile",
            "golden",
            "-CollectOnly",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "5 tests collected" in result.stdout


def test_runtime_evidence_runner_uses_unique_os_temp_for_pytest_outputs():
    source = RUNNER_PATH.read_text(encoding="utf-8")
    assert "[IO.Path]::GetTempPath()" in source
    assert "--basetemp=$baseTemp" in source
    assert "cache_dir=$cacheRoot" in source
    assert '"-TempRoot", $tempRoot' in source
    assert 'PYTHONDONTWRITEBYTECODE = "1"' in source
    assert "Push-Location -LiteralPath $repoRoot" in source


def test_validator_runner_guards_both_checkouts_and_uses_os_temp():
    source = VALIDATOR_RUNNER_PATH.read_text(encoding="utf-8")
    assert "--git-common-dir" in source
    assert "ucf_validation_report.json" in source
    assert "ucf_validation_report.md" in source
    assert "Get-FileHash" in source
    assert "[IO.Path]::GetTempPath()" in source
    assert "--basetemp=$baseTemp" in source
    assert '"-TempRoot", $tempRoot' in source
    assert 'PYTHONDONTWRITEBYTECODE = "1"' in source
    assert "Push-Location -LiteralPath $repoRoot" in source


def test_validator_runner_list_only_is_service_free():
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(VALIDATOR_RUNNER_PATH),
            "-ListOnly",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "test_ucf_validator.py" in result.stdout
    assert "ucf_validation_report.json" in result.stdout
