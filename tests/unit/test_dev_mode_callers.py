"""Execute cmd's real control flow with isolated external service boundaries.

The adjacent startup tests exercise the actual supervisor and Windows jobs.
Here no service/WSL/model command may reach the workstation: native shims
record requested operations and return the chosen owner's result.
"""
import base64
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows mode callers")


@pytest.fixture(scope="module")
def mode_boundary(tmp_path_factory):
    root = tmp_path_factory.mktemp("native-mode-boundary")
    code = root / "Boundary.cs"
    code.write_text(r'''
using System;
using System.IO;
using System.Text;
using System.Diagnostics;
public class Boundary {
    public static int Main(string[] args) {
        string name = Path.GetFileNameWithoutExtension(Process.GetCurrentProcess().MainModule.FileName).ToLowerInvariant();
        string joined = string.Join(" ", args);
        if (args.Length == 2 && args[0] == "-GoodQFixtureVllm") name = args[1] + "_vllm";
        string record = Path.Combine(Environment.GetEnvironmentVariable("GOODQ_MODE_TEST_EVENTS"),
            DateTime.UtcNow.Ticks.ToString("D19") + "-" + Guid.NewGuid().ToString("N") + ".txt");
        File.WriteAllText(record, name + "|" +
            Convert.ToBase64String(Encoding.UTF8.GetBytes(string.Join("\0", args))) + "\n");
        if (joined.Contains("Get-GoodQPythonExe")) Console.WriteLine(Environment.GetEnvironmentVariable("CONDA_PREFIX") + "\\python.exe");
        if (joined.Contains("Get-GoodQWslDistro")) {
            string distro = Environment.GetEnvironmentVariable("GOODQ_MODE_TEST_DISTRO");
            if (string.IsNullOrEmpty(distro)) return 31;
            Console.WriteLine(distro);
        }
        if (joined.Contains("start_goodq_dev.ps1")) {
            string key = joined.Contains("-StopCurrent") ? "STOP" : joined.Contains("-Supervise") ? "SUPERVISE" : "CHECK";
            string value = Environment.GetEnvironmentVariable("GOODQ_MODE_TEST_" + key);
            if (!string.IsNullOrEmpty(value)) return int.Parse(value);
        }
        if (name == "stop_vllm") return int.Parse(Environment.GetEnvironmentVariable("GOODQ_MODE_TEST_VLLM"));
        return 0;
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
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                    "-File", str(compile_script), "-Source", str(code), "-Output", str(exe)],
                   check=True, capture_output=True, timeout=30)
    return exe


@pytest.fixture
def run_mode(tmp_path, mode_boundary):
    root = tmp_path / "mode deployment with spaces"
    root.mkdir()
    scripts = root / "scripts"
    (scripts / "_lib").mkdir(parents=True)
    (scripts / "_lib/interpreter_bindings.bat").write_text(
        '@echo off\nset "GOODQ_CONDA_ENV=goodq_core"\nset "GOODQ_WSL_DISTRO=Ubuntu-22.04"\nexit /b 0\n'
    )
    for mode in ("on", "off"):
        # Visibility only: legacy child windows must remain hidden during tests.
        source = (REPO / f"dev_{mode}.bat").read_text().replace(" /min ", " /b ")
        (root / f"dev_{mode}.bat").write_text(source)
    for name in ("start", "stop"):
        (scripts / f"{name}_vllm_servers.bat").write_text(
            '@echo off\npowershell.exe -GoodQFixtureVllm ' + name + '\nexit /b %ERRORLEVEL%\n'
        )
    shims = root / "goodq_core"
    shims.mkdir()
    for command in ("powershell", "pwsh", "python", "wsl", "net", "ollama", "nvidia-smi"):
        shutil.copyfile(mode_boundary, shims / f"{command}.exe")

    def run(mode, *, check=0, supervise=0, stop=0, distro="Ubuntu-22.04", vllm_stop=0):
        events = root / "events"
        events.mkdir()
        env = os.environ.copy()
        env.update(PATH=str(shims) + os.pathsep + os.environ["PATH"], CONDA_PREFIX=str(shims),
                   GOODQ_NO_PAUSE="1", GOODQ_MODE_TEST_EVENTS=str(events),
                   GOODQ_MODE_TEST_CHECK=str(check), GOODQ_MODE_TEST_SUPERVISE=str(supervise),
                   GOODQ_MODE_TEST_STOP=str(stop), GOODQ_MODE_TEST_DISTRO=distro,
                   GOODQ_MODE_TEST_VLLM=str(vllm_stop),
                   DEV_ON_EXIT_CODE="73", DEV_OFF_EXIT_CODE="74")
        # Run from a different cwd; the real launcher must bind itself to its repo.
        result = subprocess.run([os.environ["COMSPEC"], "/d", "/c", str(root / f"dev_{mode}.bat")],
                                env=env, cwd=tmp_path, capture_output=True, text=True, timeout=25,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        calls = []
        for event in sorted(events.glob("*.txt")):
            line = event.read_text().strip()
            name, encoded = line.split("|", 1)
            calls.append((name, base64.b64decode(encoded).decode().split("\0") if encoded else []))
        return result, calls

    return run


def _owner(calls, action):
    return [i for i, (_, args) in enumerate(calls)
            if any("start_goodq_dev.ps1" in arg for arg in args) and action in args]


def test_dev_on_refuses_collision_before_compute_start(run_mode):
    result, calls = run_mode("on", check=17)
    assert result.returncode != 0, "Caller ignored startup owner's refusal"
    assert _owner(calls, "-CheckStart")
    assert not any(name in ("start_vllm", "wsl", "net") for name, _ in calls)
    assert not _owner(calls, "-Supervise")


def test_dev_off_failed_drain_preserves_compute_dependencies(run_mode):
    result, calls = run_mode("off", stop=19)
    assert result.returncode != 0
    assert _owner(calls, "-StopCurrent"), "Caller bypassed the runtime's drain control"
    assert not any(name in ("stop_vllm", "wsl", "ollama") for name, _ in calls)


def test_dev_off_waits_for_owner_before_teardown_and_never_force_kills_windows_roles(run_mode):
    result, calls = run_mode("off")
    assert result.returncode == 0, result.stdout + result.stderr
    stop, = _owner(calls, "-StopCurrent")
    teardown, = [i for i, (name, _) in enumerate(calls) if name == "stop_vllm"]
    assert stop < teardown
    assert not any("Stop-Process" in arg for _, args in calls for arg in args)
    assert [(name, args) for name, args in calls if name == "wsl"] == [
        ("wsl", ["--terminate", "Ubuntu-22.04"])
    ], "Dev Off crossed the selected distro boundary"


def test_dev_off_vllm_stop_failure_preserves_distro_and_model_dependencies(run_mode):
    result, calls = run_mode("off", vllm_stop=31)
    assert result.returncode != 0, "Dev Off ignored the vLLM owner failure"
    assert any(name == "stop_vllm" for name, _ in calls)
    assert not any(name in ("wsl", "ollama") for name, _ in calls)


def test_dev_off_uses_owner_release_instead_of_an_http_failure_as_absence(run_mode):
    result, calls = run_mode("off")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not any("38005/v1/models" in arg for _, args in calls for arg in args), (
        "Dev Off still substitutes a failed HTTP request for endpoint absence"
    )


def test_dev_on_preserves_supervisor_failure_and_does_not_spawn_competing_roles(run_mode):
    result, calls = run_mode("on", supervise=23)
    assert result.returncode != 0
    assert _owner(calls, "-Supervise"), "Caller bypassed the canonical supervisor"
    assert not any("Stop-Process" in arg or "-m api.server" in arg or "-m cli.watchdog" in arg
                   for _, args in calls for arg in args)
    assert "SYSTEM READY" not in result.stdout


def test_dev_on_normal_supervisor_exit_is_not_an_ambient_failure_or_new_readiness_claim(run_mode):
    result, calls = run_mode("on")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _owner(calls, "-Supervise")
    assert "Local agent mode activated" not in result.stdout


@pytest.mark.parametrize("mode", ["on", "off"])
def test_mode_refuses_an_unconfigured_wsl_target_before_runtime_actions(run_mode, mode):
    result, calls = run_mode(mode, distro="")
    assert result.returncode != 0, "Mode accepted a guessed WSL target"
    assert not any(name in ("start_vllm", "stop_vllm", "wsl", "net", "ollama") for name, _ in calls)
    assert not _owner(calls, "-Supervise") and not _owner(calls, "-StopCurrent")


@pytest.mark.parametrize("binding", ["environment", "file", "absent"])
def test_required_wsl_binding_never_selects_the_first_installed_distro(tmp_path, binding):
    directory = tmp_path / "scripts/_lib"
    directory.mkdir(parents=True)
    module = directory / "interpreter_bindings.ps1"
    shutil.copyfile(REPO / "scripts/_lib/interpreter_bindings.ps1", module)
    if binding == "file":
        (tmp_path / ".env.local").write_text("GOODQ_WSL_DISTRO=Selected-GoodQ\n")
    harness = tmp_path / "read.ps1"
    harness.write_text(
        "param($Module)\n$ErrorActionPreference='Stop'\n. $Module\n"
        "function wsl.exe { Write-Output 'Unrelated-First-Distro' }\n"
        "Get-GoodQWslDistro -RequireConfigured\n", encoding="utf-8-sig"
    )
    env = {k: v for k, v in os.environ.items() if k.casefold() != "goodq_wsl_distro"}
    if binding == "environment":
        env["GOODQ_WSL_DISTRO"] = "Selected-GoodQ"
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    result = subprocess.run([str(shell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                             "-File", str(harness), "-Module", str(module)], env=env,
                            capture_output=True, text=True, timeout=10)
    if binding == "absent":
        assert result.returncode != 0, "Required binding silently used automatic distro discovery"
        assert "Unrelated-First-Distro" not in result.stdout
    else:
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "Selected-GoodQ"
