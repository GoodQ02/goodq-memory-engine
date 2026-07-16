from __future__ import annotations

from pathlib import Path


def test_dev_pytest_wrapper_uses_canonical_env_and_repo_local_temp() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    wrapper = repo_root / "scripts" / "dev" / "run_pytest.ps1"
    content = wrapper.read_text(encoding="utf-8")

    assert "ValidateSet(\"goodq_core\")" in content
    assert "$CondaEnv = \"goodq_core\"" in content
    assert "Get-GoodQCondaEnv" not in content
    assert "tmp\\conda_run" in content
    assert "[string]$TempRoot" in content
    assert "if ($TempRoot)" in content
    assert "$env:TEMP = $localTemp" in content
    assert "$env:TMP = $localTemp" in content
    assert '"run", "--no-capture-output", "-n", $CondaEnv, "python", "-m", "pytest"' in content
