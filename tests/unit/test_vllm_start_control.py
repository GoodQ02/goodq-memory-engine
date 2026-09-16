"""Exercise the real PowerShell start control with inert OS/HTTP boundaries."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows WSL control")


@pytest.fixture
def start_control(tmp_path):
    scripts = tmp_path / "checkout with spaces" / "scripts"
    bindings = scripts / "_lib"
    bindings.mkdir(parents=True)
    shutil.copyfile(REPO / "scripts/start_vllm_servers.ps1", scripts / "start_vllm_servers.ps1")
    shutil.copyfile(REPO / "scripts/_lib/interpreter_bindings.ps1", bindings / "interpreter_bindings.ps1")
    (scripts / "stop_vllm_servers.ps1").write_text(
        "param($Port)\nWrite-AuditEvent 'cleanup' ([string]$Port)\n"
        "if ($Scenario -eq 'cleanup_failed') { throw 'fixture cleanup witness failure' }\n", encoding="utf-8"
    )
    harness = tmp_path / "boundary.ps1"
    harness.write_text(r'''
param($Control, $EventLog, $Scenario)
$ErrorActionPreference = 'Stop'
$global:OwnerActive = $Scenario -eq 'preexisting_timeout'
$global:OwnerReads = 0
function Write-AuditEvent($Name, $Value) {
    @{name=$Name;value=$Value} | ConvertTo-Json -Compress | Add-Content -LiteralPath $EventLog
}
function wsl.exe {
    $command = $args -join '|'
    Write-AuditEvent 'wsl' $command
    $global:LASTEXITCODE = 0
    if ($command -match 'systemctl\|show') {
        $global:OwnerReads++
        if ($Scenario -eq 'missing_unit') { 'LoadState=not-found'; return }
        $active = $global:OwnerActive -and -not ($Scenario -eq 'owner_exits' -and $global:OwnerReads -ge 3)
        'LoadState=loaded'
        'ActiveState=' + $(if ($active) {'active'} else {'inactive'})
        'MainPID=' + $(if ($active) {'555'} else {'0'})
    } elseif ($command -match 'systemctl\|start') {
        if ($Scenario -eq 'start_failed') { $global:LASTEXITCODE=7; return }
        $global:OwnerActive=$true
    } else { throw 'Unexpected WSL action in inert fixture.' }
}
function Get-CimInstance {
    param($Filter, $ErrorAction)
    if ($Scenario -eq 'same_anchor') {
        [pscustomobject]@{CommandLine='wsl.exe -d "GoodQ Test Distro" -- bash -lc "exec -a goodq-vllm-keepalive sleep infinity"'}
    } else {
        [pscustomobject]@{CommandLine='wsl.exe -d Other-Distro -- bash -lc "exec -a goodq-vllm-keepalive sleep infinity"'}
    }
}
function Start-Process {
    param($FilePath, $WindowStyle, [switch]$PassThru, $ArgumentList)
    Write-AuditEvent 'anchor' (@{file=$FilePath;style=$WindowStyle;arguments=@($ArgumentList)})
    $process = [pscustomobject]@{Id=888;Handle=1;HasExited=($Scenario -eq 'anchor_exited')}
    $process | Add-Member -MemberType ScriptMethod -Name Refresh -Value {} -PassThru
}
function Invoke-RestMethod {
    param($Uri, $TimeoutSec, $ErrorAction)
    Write-AuditEvent 'http' $Uri
    if ($Scenario -in @('timeout','preexisting_timeout','cleanup_failed')) { throw 'Not ready' }
    $provider = if ($Scenario -eq 'wrong_provider') {'ollama'} else {'vllm'}
    [pscustomobject]@{data=@([pscustomobject]@{id='test-speed';owned_by=$provider})}
}
try {
    & $Control -Port 38765 -WaitSeconds 1
    exit 0
} catch {
    Write-Output $_.Exception.Message
    exit 1
}
''', encoding="utf-8-sig")

    def run(scenario):
        env = {k: v for k, v in os.environ.items() if k.casefold() != "goodq_wsl_distro"}
        if scenario != "missing_binding":
            env["GOODQ_WSL_DISTRO"] = "GoodQ-Test-Distro" if scenario == "simple_distro" else "GoodQ Test Distro"
        events = tmp_path / "events.jsonl"
        shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        result = subprocess.run(
            [str(shell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(harness), "-Control", str(scripts / "start_vllm_servers.ps1"),
             "-EventLog", str(events), "-Scenario", scenario],
            env=env, capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        calls = [json.loads(line) for line in events.read_text(encoding="utf-8-sig").splitlines()] if events.exists() else []
        for call in calls:
            if call["name"] == "wsl":
                assert "-d|" + env["GOODQ_WSL_DISTRO"] + "|" in call["value"]
                assert "ollama" not in call["value"] and "|enable|" not in call["value"]
        return result, calls
    return run


@pytest.mark.parametrize("scenario,reason", [
    ("missing_binding", "GOODQ_WSL_DISTRO must be configured"),
    ("missing_unit", "no installed vLLM service"),
])
def test_rejects_missing_authority_before_start(start_control, scenario, reason):
    result, calls = start_control(scenario)
    assert result.returncode != 0 and reason in result.stdout
    assert not any(c["name"] in {"anchor", "cleanup", "http"} for c in calls)
    assert not any("systemctl|start" in str(c["value"]) for c in calls)


@pytest.mark.parametrize("scenario,new_anchor", [("same_anchor", False), ("other_anchor", True)])
def test_ready_owner_uses_only_matching_hidden_keepalive(start_control, scenario, new_anchor):
    result, calls = start_control(scenario)
    assert result.returncode == 0, result.stdout + result.stderr
    anchors = [c["value"] for c in calls if c["name"] == "anchor"]
    assert bool(anchors) == new_anchor
    if anchors:
        assert anchors[0]["style"] == "Hidden"
        assert '"GoodQ Test Distro"' in anchors[0]["arguments"]
    assert any(c["name"] == "http" and c["value"] == "http://127.0.0.1:38765/v1/models" for c in calls)
    assert not any(c["name"] == "cleanup" for c in calls)


@pytest.mark.parametrize("scenario,reason", [
    ("start_failed", "systemd vLLM start failed"),
    ("timeout", "did not become ready"),
    ("wrong_provider", "did not become ready"),
    ("owner_exits", "owner exited during readiness"),
    ("anchor_exited", "keepalive exited before vLLM became ready"),
])
def test_failed_new_start_uses_existing_verified_stop_boundary(start_control, scenario, reason):
    result, calls = start_control(scenario)
    assert result.returncode != 0 and reason in result.stdout, result.stdout + result.stderr
    assert [c["value"] for c in calls if c["name"] == "cleanup"] == ["38765"]
    if scenario == "start_failed":
        assert not any(c["name"] in {"anchor", "http"} for c in calls)
    if scenario == "anchor_exited":
        assert not any(c["name"] == "http" for c in calls)


def test_readiness_failure_does_not_stop_a_preexisting_owner(start_control):
    result, calls = start_control("preexisting_timeout")
    assert result.returncode != 0 and "did not become ready" in result.stdout
    assert not any(c["name"] == "cleanup" for c in calls)


def test_simple_distro_name_is_not_passed_with_literal_quotes(start_control):
    result, calls = start_control("simple_distro")
    assert result.returncode == 0, result.stdout + result.stderr
    anchor, = [c["value"] for c in calls if c["name"] == "anchor"]
    assert anchor["arguments"][1] == "GoodQ-Test-Distro"


def test_cleanup_failure_retains_the_original_startup_failure(start_control):
    result, calls = start_control("cleanup_failed")
    assert result.returncode != 0
    assert "did not become ready" in result.stdout
    assert "Cleanup is unverified: fixture cleanup witness failure" in result.stdout
