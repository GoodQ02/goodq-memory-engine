"""Execute the real stop wrapper with native WSL stand-ins and real TCP state.

The legacy broad Windows kill command is intercepted before execution. New
PowerShell file control runs under the real Windows PowerShell interpreter.
No command in this fixture can reach a live WSL distribution or service.
"""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows WSL caller")


@pytest.fixture(scope="module")
def wsl_boundary(tmp_path_factory):
    root = tmp_path_factory.mktemp("vllm-native-boundary")
    code = root / "Boundary.cs"
    code.write_text(r'''
using System;
using System.IO;
using System.Diagnostics;
using System.Threading;
public class Boundary {
    public static int Main(string[] args) {
        string root = Environment.GetEnvironmentVariable("GOODQ_VLLM_TEST_ROOT");
        string scenario = Environment.GetEnvironmentVariable("GOODQ_VLLM_TEST_CASE");
        string name = Path.GetFileNameWithoutExtension(Process.GetCurrentProcess().MainModule.FileName);
        string command = string.Join(" ", args);
        File.WriteAllLines(Path.Combine(root, DateTime.UtcNow.Ticks.ToString("D19") + "-" + Guid.NewGuid().ToString("N") + ".call"),
                           new string[] {name, command});
        // The old wrapper's process-name kill sweep is never executed live.
        if (name == "powershell") return 0;
        if (command.Contains("bash -lc")) {
            while (!File.Exists(Path.Combine(root, "release-anchor"))) Thread.Sleep(25);
            return 0;
        }
        if (Array.IndexOf(args, "--list") >= 0 || Array.IndexOf(args, "-l") >= 0) {
            if (scenario != "absent" || !command.Contains("--running")) Console.WriteLine("GoodQ-Test-Distro");
            Console.WriteLine("Unrelated-First-Distro");
            return 0;
        }
        if (command.Contains("systemctl stop")) {
            if (scenario == "stop_failed") return 7;
            File.WriteAllText(Path.Combine(root, "stopped"), "yes");
            return 0;
        }
        if (command.Contains("systemctl show")) {
            if (scenario == "query_failed") return 9;
            bool active = scenario == "still_active";
            Console.WriteLine("LoadState=loaded\nActiveState=" + (active ? "active" : "inactive") +
                "\nSubState=" + (active ? "running" : "dead") + "\nMainPID=" + (active ? "921" : "0") +
                "\nControlGroup=" + (active ? "/system.slice/vllm-llama1b.service" : "") +
                "\nResult=" + (scenario == "timeout_result" ? "timeout" : "success"));
            return 0;
        }
        if (command.Contains("ss ")) {
            if (scenario == "linux_listener") Console.WriteLine("LISTEN 0 128 0.0.0.0:38005 0.0.0.0:*");
            return 0;
        }
        // WSL's default shell reparses regex pipes and spaced arguments. The
        // live probe reproduced exit 127 for the unescaped alternation below.
        if (command.Contains("pgrep") || command.Contains("pkill")) {
            if (Array.IndexOf(args, "--exec") < 0) return 127;
            if (command.Contains("goodq-vllm-keepalive") &&
                Array.IndexOf(args, "^goodq-vllm-keepalive infinity$") < 0) return 98;
        }
        if (command.Contains("pgrep")) {
            if (scenario == "anchor_residual" && command.Contains("goodq-vllm-keepalive")) {
                Console.WriteLine("926"); return 0;
            }
            if (scenario == "manual_engine") { Console.WriteLine("923"); return 0; }
            return 1;
        }
        if (command.Contains("pkill")) {
            if (scenario != "windows_anchor") File.WriteAllText(Path.Combine(root, "release-anchor"), "yes");
            return scenario == "anchor_failed" ? 2 : 1;
        }
        return 98;
    }
}
''', encoding="utf-8")
    compile_script = root / "compile.ps1"
    compile_script.write_text(
        "param($Source,$Output)\n$ErrorActionPreference='Stop'\n"
        "Add-Type -Path $Source -OutputAssembly $Output -OutputType ConsoleApplication\n",
        encoding="utf-8-sig",
    )
    exe = root / "boundary.exe"
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    subprocess.run([str(shell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                    "-File", str(compile_script), "-Source", str(code), "-Output", str(exe)],
                   check=True, capture_output=True, timeout=30)
    return exe


@pytest.fixture
def stop_control(tmp_path, wsl_boundary):
    scripts = tmp_path / "deployment with spaces/scripts"
    bindings = scripts / "_lib"
    bindings.mkdir(parents=True)
    for name in ("interpreter_bindings.bat", "interpreter_bindings.ps1"):
        shutil.copyfile(REPO / "scripts/_lib" / name, bindings / name)
    for name in ("stop_vllm_servers.bat", "stop_vllm_servers.ps1"):
        source = REPO / "scripts" / name
        if name.endswith(".ps1") and os.environ.get("GOODQ_VLLM_STOP_TEST_SOURCE"):
            source = Path(os.environ["GOODQ_VLLM_STOP_TEST_SOURCE"])
        if source.exists():
            shutil.copyfile(source, scripts / name)
    shims = tmp_path / "shims"
    shims.mkdir()
    for name in ("wsl", "powershell"):
        shutil.copyfile(wsl_boundary, shims / (name + ".exe"))

    def run(scenario="healthy", port=None, anchor_distro=None):
        if port is None:
            with socket.socket() as port_owner:
                port_owner.bind(("127.0.0.1", 0))
                port = port_owner.getsockname()[1]
        events = tmp_path / "events"
        events.mkdir()
        env = {key: value for key, value in os.environ.items() if key.casefold() != "goodq_wsl_distro"}
        env.update(PATH=str(shims) + os.pathsep + os.environ["PATH"], GOODQ_NO_PAUSE="1",
                   GOODQ_VLLM_TEST_ROOT=str(events), GOODQ_VLLM_TEST_CASE=scenario)
        if scenario != "missing_binding":
            env["GOODQ_WSL_DISTRO"] = "GoodQ-Test-Distro"
        anchor = None
        try:
            if anchor_distro:
                anchor = subprocess.Popen([str(shims / "wsl.exe"), "-d", anchor_distro, "--", "bash", "-lc",
                                           "exec -a goodq-vllm-keepalive sleep infinity"], env=env,
                                          creationflags=subprocess.CREATE_NO_WINDOW)
            result = subprocess.run([os.environ["COMSPEC"], "/d", "/c",
                                     str(scripts / "stop_vllm_servers.bat"), "-Port", str(port)], cwd=tmp_path,
                                    env=env, capture_output=True, text=True, timeout=25,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            result.anchor_alive = anchor is not None and anchor.poll() is None
        finally:
            if anchor is not None:
                if anchor.poll() is None:
                    anchor.kill()
                anchor.wait(timeout=5)
        calls = [p.read_text().splitlines() for p in sorted(events.glob("*.call"))]
        assert "not recognized as an internal or external command" not in result.stderr, result.stderr
        return result, calls
    return run


@pytest.mark.parametrize("scenario", ["stop_failed", "query_failed", "still_active", "timeout_result",
                                     "linux_listener", "manual_engine", "anchor_failed"])
def test_vllm_stop_rejects_owner_failure_or_residual_runtime(stop_control, scenario):
    result, calls = stop_control(scenario)
    assert result.returncode != 0, "Stop control claimed release despite " + scenario
    reason = {
        "stop_failed": "systemd vLLM stop failed",
        "query_failed": "Cannot read the vLLM stop result",
        "still_active": "does not attest successful release",
        "timeout_result": "does not attest successful release",
        "linux_listener": "Linux endpoint is present",
        "manual_engine": "Model processes remain",
        "anchor_failed": "selected keepalive could not be released",
    }[scenario]
    assert reason in result.stdout + result.stderr, result.stdout + result.stderr
    if scenario != "anchor_failed":
        assert not any("pkill" in command for _, command in calls), "Keepalive released before server absence"
    assert not any("-KILL" in command or "Stop-Process" in command for _, command in calls)


def test_vllm_stop_requires_explicit_distro_before_any_wsl_action(stop_control):
    result, calls = stop_control("missing_binding")
    assert result.returncode != 0, "Stop control accepted a guessed WSL distro"
    assert "GOODQ_WSL_DISTRO must be configured" in result.stdout + result.stderr
    assert not any(name == "wsl" for name, _ in calls)


def test_vllm_stop_does_not_boot_an_already_stopped_distro(stop_control):
    result, calls = stop_control("absent")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not any("-d " in command for _, command in calls), "Stop control woke its stopped distro"


def test_vllm_stop_proves_absence_before_releasing_exact_keepalive(stop_control):
    result, calls = stop_control()
    assert result.returncode == 0, result.stdout + result.stderr
    commands = [command for name, command in calls if name == "wsl"]
    assert any("systemctl show" in command for command in commands), "No owner completion query"
    assert any("ss " in command for command in commands), "No Linux socket check"
    assert all("-d GoodQ-Test-Distro" in command for command in commands if "-d " in command)
    release, = [i for i, command in enumerate(commands) if "pkill" in command]
    assert "-TERM" in commands[release] and "^goodq-vllm-keepalive infinity$" in commands[release]
    assert any("pgrep" in command for command in commands[:release])
    assert not any("Stop-Process" in command for _, command in calls)


def test_vllm_stop_keeps_a_live_windows_endpoint_visible_even_if_http_would_fail(stop_control):
    with socket.socket() as owner:
        owner.bind(("127.0.0.1", 0))
        owner.listen()
        result, calls = stop_control(port=owner.getsockname()[1])
        assert result.returncode != 0, "Stop control accepted an alive but unresponsive endpoint"
        assert "still accepts connections" in result.stdout + result.stderr
        assert not any("pkill" in command for _, command in calls)


def test_vllm_stop_verifies_linux_anchor_absence_after_signal_attempt(stop_control):
    result, calls = stop_control("anchor_residual")
    assert result.returncode != 0, "Stop control accepted an unsignalled surviving Linux anchor"
    assert "keepalive remains" in result.stdout + result.stderr


def test_vllm_stop_waits_for_actual_windows_keepalive_exit(stop_control):
    result, _ = stop_control("windows_anchor", anchor_distro="GoodQ-Test-Distro")
    assert result.returncode != 0, "Stop control ignored its surviving Windows keepalive"
    assert result.anchor_alive, "Stop control force-killed its keepalive"
    assert "keepalive remains" in result.stdout + result.stderr


def test_vllm_stop_preserves_other_distro_keepalive(stop_control):
    result, _ = stop_control("windows_anchor", anchor_distro="GoodQ-Test-Distro-Sibling")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.anchor_alive, "Stop control terminated another distro's keepalive"


def test_vllm_stop_accepts_natural_windows_keepalive_exit(stop_control):
    result, _ = stop_control(anchor_distro="GoodQ-Test-Distro")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.anchor_alive
