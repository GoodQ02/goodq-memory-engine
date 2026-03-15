#!/usr/bin/env python
"""Portable bootstrap installer for the public GoodQ4All surface."""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


ENV_NAME = "goodq_core"
BASELINE_ENV_FILE = "environment.yml"
GPU_ENV_FILE = "environment.gpu.yml"
DEFAULT_DATA_ROOT = Path(r"C:\GoodQ_Data")
DEFAULT_WSL_DISTRO = "Ubuntu"
MIN_FREE_SPACE_GB = 25


@dataclass
class CapabilityProfile:
    profile: str
    gpu_available: bool
    wsl_available: bool
    nvidia_detail: str
    wsl_detail: str


@dataclass
class BootstrapContext:
    repo_root: Path
    conda_exe: Path
    launcher_bat: Path
    environment_yml: Path
    env_local_template: Path
    config_local_example: Path
    bootstrap_verify: Path
    qdrant_start_bat: Path
    data_root: Path
    enable_gpu: bool
    enable_wsl_audio: bool
    wsl_distro: str
    profile: CapabilityProfile


def _print(msg: str) -> None:
    print(msg, flush=True)


def _fail(msg: str, exit_code: int = 1) -> int:
    _print(f"[FAIL] {msg}")
    return exit_code


def _run(
    cmd: list[str],
    *,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
    capture: bool = True,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=capture,
        text=True,
        check=check,
    )


def _is_windows() -> bool:
    return platform.system().lower() == "windows"


def _repo_candidates() -> Iterable[Path]:
    env_root = os.environ.get("GOODQ_REPO_ROOT")
    if env_root:
        yield Path(env_root)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        yield exe_dir
        yield exe_dir.parent
    else:
        yield Path(__file__).resolve().parents[1]
    yield Path.cwd()


def resolve_repo_root() -> Path:
    for candidate in _repo_candidates():
        if (candidate / "configs" / "config.yaml").exists() and (candidate / "LAUNCH_GOODQ.bat").exists():
            return candidate
    raise FileNotFoundError("Unable to locate repository root (expected configs/config.yaml and LAUNCH_GOODQ.bat).")


def detect_python() -> tuple[bool, str]:
    version = sys.version_info
    detail = f"{version.major}.{version.minor}.{version.micro} ({sys.executable})"
    return (version.major, version.minor) >= (3, 10), detail


def detect_conda() -> Optional[Path]:
    candidates: list[Path] = []
    env_conda = os.environ.get("CONDA_EXE")
    if env_conda:
        candidates.append(Path(env_conda))

    which_conda = shutil.which("conda")
    if which_conda:
        candidates.append(Path(which_conda))

    user_profile = Path(os.environ.get("USERPROFILE", ""))
    if user_profile:
        candidates.extend(
            [
                user_profile / "miniconda3" / "Scripts" / "conda.exe",
                user_profile / "anaconda3" / "Scripts" / "conda.exe",
                user_profile / "Miniforge3" / "Scripts" / "conda.exe",
                user_profile / "mambaforge" / "Scripts" / "conda.exe",
            ]
        )

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return candidate
    return None


def detect_gpu() -> tuple[bool, str]:
    try:
        completed = _run(["nvidia-smi", "-L"])
    except FileNotFoundError:
        return False, "nvidia-smi not found"
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip() or "nvidia-smi failed"
        return False, detail
    detail = completed.stdout.strip().splitlines()[0] if completed.stdout.strip() else "NVIDIA GPU detected"
    return True, detail


def detect_wsl() -> tuple[bool, str, str]:
    try:
        completed = _run(["wsl", "-l", "-q"])
    except FileNotFoundError:
        return False, "wsl not found", DEFAULT_WSL_DISTRO
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip() or "wsl unavailable"
        return False, detail, DEFAULT_WSL_DISTRO
    raw_stdout = (completed.stdout or "").replace("\x00", "")
    distros = [line.strip() for line in raw_stdout.splitlines() if line.strip()]
    distro = distros[0] if distros else DEFAULT_WSL_DISTRO
    detail = f"installed distros: {', '.join(distros)}" if distros else "wsl present"
    return True, detail, distro


def resolve_environment_spec(repo_root: Path, enable_gpu: bool, gpu_available: bool) -> Path:
    if enable_gpu and gpu_available:
        gpu_spec = repo_root / GPU_ENV_FILE
        if gpu_spec.exists():
            return gpu_spec
    return repo_root / BASELINE_ENV_FILE


def prompt_text(prompt: str, default: str, assume_yes: bool) -> str:
    if assume_yes or not sys.stdin.isatty():
        return default
    raw = input(f"{prompt} [{default}]: ").strip()
    return raw or default


def prompt_bool(prompt: str, default: bool, assume_yes: bool) -> bool:
    if assume_yes or not sys.stdin.isatty():
        return default
    suffix = "Y/n" if default else "y/N"
    raw = input(f"{prompt} [{suffix}]: ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes", "1", "true"}


def classify_profile(gpu_available: bool, wsl_available: bool, enable_gpu: bool) -> CapabilityProfile:
    profile = "GPU_ENHANCED" if gpu_available and enable_gpu else "BASELINE"
    gpu_ok, gpu_detail = detect_gpu()
    wsl_ok, wsl_detail, _ = detect_wsl()
    return CapabilityProfile(
        profile=profile,
        gpu_available=gpu_ok if gpu_available else False,
        wsl_available=wsl_ok if wsl_available else False,
        nvidia_detail=gpu_detail,
        wsl_detail=wsl_detail,
    )


def conda_env_exists(conda_exe: Path, env_name: str) -> bool:
    completed = _run([str(conda_exe), "env", "list", "--json"])
    if completed.returncode != 0:
        return False
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return False
    for env_path in payload.get("envs", []):
        if Path(env_path).name.lower() == env_name.lower():
            return True
    return False


def ensure_conda_env(conda_exe: Path, repo_root: Path, env_file: Path) -> None:
    if conda_env_exists(conda_exe, ENV_NAME):
        _print(f"[INFO] Updating existing Conda environment: {ENV_NAME}")
        completed = _run([str(conda_exe), "env", "update", "-n", ENV_NAME, "-f", str(env_file)], cwd=repo_root)
    else:
        _print(f"[INFO] Creating Conda environment from {env_file.name}")
        completed = _run([str(conda_exe), "env", "create", "-f", str(env_file)], cwd=repo_root)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip() or "conda environment command failed"
        raise RuntimeError(detail)


def env_python(conda_exe: Path, repo_root: Path, code: str) -> subprocess.CompletedProcess[str]:
    return _run(
        [str(conda_exe), "run", "-n", ENV_NAME, "python", "-c", code],
        cwd=repo_root,
    )


def check_disk_space(path: Path) -> tuple[bool, str]:
    probe = path
    if not probe.exists():
        probe = probe.parent if probe.parent.exists() else Path.cwd()
    usage = shutil.disk_usage(str(probe))
    free_gb = usage.free / (1024 ** 3)
    return free_gb >= MIN_FREE_SPACE_GB, f"{free_gb:.1f} GB free at {probe}"


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_env_local(path: Path, template_path: Path, ctx: BootstrapContext) -> None:
    if path.exists():
        _print(f"[INFO] Preserving existing {path.name}")
        return

    base = template_path.read_text(encoding="utf-8") if template_path.exists() else "# GoodQ local overrides\n"
    managed_block = textwrap.dedent(
        f"""

        # ----------------------------------------------------------------------
        # Bootstrap-managed defaults
        # ----------------------------------------------------------------------
        GOODQ_DATA_ROOT={ctx.data_root}
        GOODQ_CONDA_ENV={ENV_NAME}
        GOODQ_HOST_PROFILE={ctx.profile.profile}
        GOODQ_REQUIRE_GPU=0
        GOODQ_REQUIRE_WSL_AUDIO=0
        GOODQ_WSL_DISTRO={ctx.wsl_distro}
        GOODQ_WSL_WORKSPACE=auto
        """
    ).lstrip()
    path.write_text(base.rstrip() + "\n\n" + managed_block, encoding="utf-8")
    _print(f"[OK] Created {path.name}")


def write_config_local(path: Path, ctx: BootstrapContext) -> None:
    if path.exists():
        _print(f"[INFO] Preserving existing {path.name}")
        return

    data_root = ctx.data_root.as_posix()
    content = textwrap.dedent(
        f"""
        # Generated by scripts/bootstrap_install.py
        # Local-only GoodQ overrides. Keep this file out of version control.

        host:
          data_root: "{data_root}"
          wsl_distro: "{ctx.wsl_distro}"
          wsl_user: ${{GOODQ_WSL_USER:-auto}}
          wsl_workspace: ${{GOODQ_WSL_WORKSPACE:-auto}}

        tts:
          elevenlabs_voice_id: ${{ELEVENLABS_VOICE_ID:-example_voice_id}}

        home_assistant:
          url: ${{GOODQ_HOME_ASSISTANT_URL:-http://localhost:8123}}
          token: ${{HA_TOKEN:-}}
        """
    ).lstrip()
    path.write_text(content, encoding="utf-8")
    _print(f"[OK] Created {path.name}")


def resolve_qdrant_url(conda_exe: Path, repo_root: Path) -> str:
    code = (
        "from steps.common.config_loader import load_configs; "
        "cfg = load_configs({}); "
        "print(((cfg.get('qdrant') or {}).get('host') or 'http://localhost:6333'))"
    )
    completed = env_python(conda_exe, repo_root, code)
    if completed.returncode != 0:
        return "http://localhost:6333"
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else "http://localhost:6333"


def check_qdrant(url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/collections", timeout=5) as response:
            return response.status == 200, f"reachable at {url}"
    except urllib.error.URLError as exc:
        return False, f"not reachable at {url} ({exc.reason})"
    except Exception as exc:  # noqa: BLE001
        return False, f"not reachable at {url} ({exc})"


def run_bootstrap_verify(conda_exe: Path, repo_root: Path) -> tuple[bool, str]:
    completed = _run(
        [str(conda_exe), "run", "-n", ENV_NAME, "python", str(repo_root / "scripts" / "bootstrap_verify.py"), "--json"],
        cwd=repo_root,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip() or "bootstrap_verify failed"
        return False, detail
    return True, "bootstrap_verify passed"


def verify_env_python(conda_exe: Path, repo_root: Path) -> tuple[bool, str]:
    completed = env_python(conda_exe, repo_root, "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if completed.returncode != 0:
        return False, (completed.stderr or completed.stdout).strip() or "python probe failed"
    version = (completed.stdout or "").strip().splitlines()[-1]
    try:
        major, minor = version.split(".")[:2]
        ok = (int(major), int(minor)) >= (3, 10)
    except Exception:  # noqa: BLE001
        ok = False
    return ok, f"env python={version}"


def verify_config_loader(conda_exe: Path, repo_root: Path) -> tuple[bool, str]:
    completed = env_python(
        conda_exe,
        repo_root,
        "from steps.common.config_loader import load_configs; cfg=load_configs({}); print('ok' if isinstance(cfg, dict) else 'bad')",
    )
    if completed.returncode != 0:
        return False, (completed.stderr or completed.stdout).strip() or "config loader failed"
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return (lines[-1] == "ok"), "config loader works" if lines and lines[-1] == "ok" else "config loader returned unexpected output"


def verify_launcher(path: Path) -> tuple[bool, str]:
    return path.exists(), f"launcher={'present' if path.exists() else 'missing'} at {path}"


def collect_context(args: argparse.Namespace) -> BootstrapContext:
    repo_root = resolve_repo_root()
    conda_exe = detect_conda()
    if not conda_exe:
        raise RuntimeError("Conda was not found. Install Miniconda/Anaconda first, then rerun the bootstrap installer.")

    python_ok, python_detail = detect_python()
    if not python_ok:
        raise RuntimeError(f"Python 3.10+ is required. Current interpreter: {python_detail}")

    gpu_available, gpu_detail = detect_gpu()
    wsl_available, wsl_detail, detected_distro = detect_wsl()

    default_data_root = str(args.data_root or DEFAULT_DATA_ROOT)
    chosen_data_root = Path(prompt_text("Base data root directory", default_data_root, args.yes))
    enable_gpu = args.enable_gpu if args.enable_gpu is not None else prompt_bool(
        "Enable GPU acceleration", False, args.yes
    )
    enable_wsl_audio = args.enable_wsl_audio if args.enable_wsl_audio is not None else prompt_bool(
        "Enable WSL audio acceleration", wsl_available, args.yes
    )

    if enable_gpu and not gpu_available:
        _print("[WARN] GPU acceleration requested, but no NVIDIA GPU was detected. Falling back to BASELINE.")
        enable_gpu = False
    if enable_wsl_audio and not wsl_available:
        _print("[WARN] WSL audio acceleration requested, but WSL2 was not detected. Keeping WSL disabled.")
        enable_wsl_audio = False

    profile = CapabilityProfile(
        profile="GPU_ENHANCED" if enable_gpu and gpu_available else "BASELINE",
        gpu_available=gpu_available,
        wsl_available=wsl_available,
        nvidia_detail=gpu_detail,
        wsl_detail=wsl_detail,
    )

    return BootstrapContext(
        repo_root=repo_root,
        conda_exe=conda_exe,
        launcher_bat=repo_root / "LAUNCH_GOODQ.bat",
        environment_yml=resolve_environment_spec(repo_root, enable_gpu, gpu_available),
        env_local_template=repo_root / ".env.local.template",
        config_local_example=repo_root / "configs" / "config.local.example.yaml",
        bootstrap_verify=repo_root / "scripts" / "bootstrap_verify.py",
        qdrant_start_bat=repo_root / "scripts" / "qdrant" / "START_QDRANT.bat",
        data_root=chosen_data_root,
        enable_gpu=enable_gpu,
        enable_wsl_audio=enable_wsl_audio,
        wsl_distro=args.wsl_distro or detected_distro or DEFAULT_WSL_DISTRO,
        profile=profile,
    )


def print_inspection(ctx: BootstrapContext) -> None:
    disk_ok, disk_detail = check_disk_space(ctx.data_root)
    _print("")
    _print("GoodQ Bootstrap Inspection")
    _print("=========================")
    _print(f"repo_root        : {ctx.repo_root}")
    _print(f"windows_host     : {_is_windows()}")
    _print(f"python           : {sys.version.split()[0]} ({sys.executable})")
    _print(f"conda            : {ctx.conda_exe}")
    _print(f"disk             : {disk_detail}")
    _print(f"gpu_available    : {ctx.profile.gpu_available} ({ctx.profile.nvidia_detail})")
    _print(f"wsl_available    : {ctx.profile.wsl_available} ({ctx.profile.wsl_detail})")
    _print(f"profile          : {ctx.profile.profile}")
    _print(f"enable_gpu       : {ctx.enable_gpu}")
    _print(f"enable_wsl_audio : {ctx.enable_wsl_audio}")
    _print(f"environment_spec : {ctx.environment_yml.name}")
    _print(f"data_root        : {ctx.data_root}")
    if not disk_ok:
        _print(f"[WARN] Recommended free space is at least {MIN_FREE_SPACE_GB} GB.")


def prepare_local_files(ctx: BootstrapContext) -> None:
    ensure_directory(ctx.data_root)
    write_env_local(ctx.repo_root / ".env.local", ctx.env_local_template, ctx)
    write_config_local(ctx.repo_root / "configs" / "config.local.yaml", ctx)


def verify_runtime(ctx: BootstrapContext) -> int:
    _print("")
    _print("Bootstrap Verification")
    _print("======================")

    env_ok, env_detail = verify_env_python(ctx.conda_exe, ctx.repo_root)
    _print(f"[{'OK' if env_ok else 'FAIL'}] env python: {env_detail}")

    cfg_ok, cfg_detail = verify_config_loader(ctx.conda_exe, ctx.repo_root)
    _print(f"[{'OK' if cfg_ok else 'FAIL'}] config loader: {cfg_detail}")

    verify_ok, verify_detail = run_bootstrap_verify(ctx.conda_exe, ctx.repo_root)
    _print(f"[{'OK' if verify_ok else 'WARN'}] bootstrap_verify: {verify_detail}")

    launcher_ok, launcher_detail = verify_launcher(ctx.launcher_bat)
    _print(f"[{'OK' if launcher_ok else 'FAIL'}] launcher: {launcher_detail}")

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        _print(f"[OK] ffmpeg: {ffmpeg_path}")
    else:
        _print("[WARN] ffmpeg not on PATH. Install it or set GOODQ_FFMPEG_EXE in .env.local.")

    qdrant_url = resolve_qdrant_url(ctx.conda_exe, ctx.repo_root)
    qdrant_ok, qdrant_detail = check_qdrant(qdrant_url)
    level = "OK" if qdrant_ok else "WARN"
    _print(f"[{level}] qdrant: {qdrant_detail}")
    if not qdrant_ok:
        qdrant_service_installer = ctx.repo_root / "scripts" / "qdrant" / "INSTALL_QDRANT_SERVICE.bat"
        if qdrant_service_installer.exists():
            _print(
                "[INFO] Preferred Qdrant path: install or repair the Windows service via: "
                f"{qdrant_service_installer}"
            )
        if ctx.qdrant_start_bat.exists():
            _print(f"[INFO] Foreground testing fallback only: {ctx.qdrant_start_bat}")

    if not (env_ok and cfg_ok and launcher_ok):
        return 1
    return 0


def launch_goodq(ctx: BootstrapContext) -> int:
    _print("")
    _print("Launching GoodQ")
    _print("================")
    completed = _run(["cmd.exe", "/c", str(ctx.launcher_bat)], cwd=ctx.repo_root, capture=False)
    return completed.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Portable bootstrap installer for GoodQ4All")
    parser.add_argument("--data-root", help=r"override data root (default: C:\GoodQ_Data)")
    parser.add_argument("--wsl-distro", help="override WSL distro name")
    parser.add_argument("--enable-gpu", dest="enable_gpu", action="store_true", help="enable GPU_ENHANCED profile if supported")
    parser.add_argument("--disable-gpu", dest="enable_gpu", action="store_false", help="force BASELINE profile")
    parser.add_argument("--enable-wsl-audio", dest="enable_wsl_audio", action="store_true", help="enable WSL audio extension if available")
    parser.add_argument("--disable-wsl-audio", dest="enable_wsl_audio", action="store_false", help="disable WSL audio extension")
    parser.add_argument("--yes", action="store_true", help="accept defaults without prompting")
    parser.add_argument("--inspect-only", action="store_true", help="inspect capabilities and exit without changes")
    parser.add_argument("--verify-only", action="store_true", help="run lightweight verification only")
    parser.add_argument("--no-launch", action="store_true", help="skip launching LAUNCH_GOODQ.bat")
    parser.set_defaults(enable_gpu=None, enable_wsl_audio=None)
    return parser.parse_args()


def main() -> int:
    if not _is_windows():
        return _fail("GoodQ bootstrap_install.py currently supports Windows hosts only.")

    args = parse_args()
    try:
        ctx = collect_context(args)
    except Exception as exc:  # noqa: BLE001
        return _fail(str(exc))

    print_inspection(ctx)
    if args.inspect_only:
        return 0

    if not ctx.environment_yml.exists():
        return _fail(f"Missing environment spec: {ctx.environment_yml}")
    if not ctx.launcher_bat.exists():
        return _fail(f"Missing launcher: {ctx.launcher_bat}")

    if not args.verify_only:
        try:
            ensure_conda_env(ctx.conda_exe, ctx.repo_root, ctx.environment_yml)
            prepare_local_files(ctx)
        except Exception as exc:  # noqa: BLE001
            return _fail(f"Bootstrap preparation failed: {exc}")

    verify_exit = verify_runtime(ctx)
    if verify_exit != 0:
        return verify_exit

    if args.no_launch or args.verify_only:
        _print("[OK] Bootstrap complete. Launch skipped by flag.")
        return 0

    return launch_goodq(ctx)


if __name__ == "__main__":
    raise SystemExit(main())
