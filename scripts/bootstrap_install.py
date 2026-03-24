#!/usr/bin/env python
"""Portable bootstrap installer for the public GoodQ4All surface."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import textwrap
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional


ENV_NAME = "goodq_core"
BASELINE_ENV_FILE = "environment.yml"
GPU_ENV_FILE = "environment.gpu.yml"
DEFAULT_DATA_ROOT = Path(r"C:\GoodQ_Data")
DEFAULT_WSL_DISTRO = "Ubuntu-22.04"
MIN_FREE_SPACE_GB = 25
QDRANT_SERVICE_NAME = "GoodQ_Qdrant"
CONDA_TOS_CHANNELS = (
    "https://repo.anaconda.com/pkgs/main",
    "https://repo.anaconda.com/pkgs/r",
    "https://repo.anaconda.com/pkgs/msys2",
)
WINGET_FFMPEG_ID = "Gyan.FFmpeg.Essentials"
WINGET_NSSM_ID = "NSSM.NSSM"
CHOCO_FFMPEG_PACKAGE = "ffmpeg"
CHOCO_NSSM_PACKAGE = "nssm"
STEP_ENV_PYTHON = "3.10"
TORCH_CUDA_INDEX_URL = "https://download.pytorch.org/whl/cu121"


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
    qdrant_service_installer: Path
    qdrant_start_bat: Path
    data_root: Path
    enable_gpu: bool
    enable_wsl_audio: bool
    wsl_distro: str
    profile: CapabilityProfile
    install_step_envs: bool
    prefetch_models: bool
    wsl_user: Optional[str] = None
    wsl_workspace: Optional[str] = None


@dataclass(frozen=True)
class WslAudioContext:
    distro: str
    user: str
    home: str
    workspace: str
    windows_workspace: Path


@dataclass(frozen=True)
class StepEnvSpec:
    name: str
    req_rel_path: str
    lock_rel_path: str
    description: str
    smoke_imports: tuple[str, ...]
    conda_packages: tuple[str, ...] = ()
    conda_channels: tuple[str, ...] = ()
    allowed_pip_check_warnings: tuple[str, ...] = ()


SUPPORTED_STEP_ENVS: tuple[StepEnvSpec, ...] = (
    StepEnvSpec(
        "goodq_video_scene_detect",
        "envs/video_scene_detect/requirements.txt",
        "envs/locks/video_scene_detect.lock.txt",
        "scene detection",
        ("scenedetect", "cv2", "numpy"),
    ),
    StepEnvSpec(
        "goodq_image_caption",
        "envs/image_caption/requirements.txt",
        "envs/locks/image_caption.lock.txt",
        "ocr, captioning, exif, clip, dino",
        ("torch", "transformers", "faiss", "accelerate", "timezonefinder"),
    ),
    StepEnvSpec(
        "goodq_object_detect",
        "envs/object_detect/requirements.txt",
        "envs/locks/object_detect.lock.txt",
        "object detection",
        ("torch", "torchvision", "ultralytics", "cv2", "numpy"),
    ),
    StepEnvSpec(
        "goodq_face_embed",
        "envs/face_embed/requirements.txt",
        "envs/locks/face_embed.lock.txt",
        "face detection and embeddings",
        ("PIL", "torch", "torchvision", "face_recognition", "face_recognition_models", "facenet_pytorch", "cv2", "dlib"),
        conda_packages=("dlib=20.0.0",),
        conda_channels=("conda-forge",),
        allowed_pip_check_warnings=(
            "facenet-pytorch 2.6.0 has requirement torch<2.3.0,>=2.2.0",
            "facenet-pytorch 2.6.0 has requirement torchvision<0.18.0,>=0.17.0",
        ),
    ),
    StepEnvSpec(
        "goodq_text_embed",
        "envs/text_embed/requirements.txt",
        "envs/locks/text_embed.lock.txt",
        "text embeddings",
        ("torch", "sentence_transformers", "faiss", "numpy", "datasets"),
    ),
    StepEnvSpec(
        "goodq_audio_metadata",
        "envs/audio_metadata/requirements.txt",
        "envs/locks/audio_metadata.lock.txt",
        "audio metadata and time hints",
        ("mutagen", "librosa", "soundfile", "numpy"),
    ),
    StepEnvSpec(
        "goodq_audio_transcribe",
        "envs/audio_transcribe/requirements.txt",
        "envs/locks/audio_transcribe.lock.txt",
        "audio transcription helpers",
        ("torch", "faster_whisper", "soundfile"),
    ),
    StepEnvSpec(
        "goodq_audio_emotion",
        "envs/audio_emotion/requirements.txt",
        "envs/locks/audio_emotion.lock.txt",
        "audio emotion analysis",
        ("torch", "transformers", "librosa", "soundfile"),
    ),
    StepEnvSpec(
        "goodq_audio_embed",
        "envs/audio_embed/requirements.txt",
        "envs/locks/audio_embed.lock.txt",
        "audio embeddings",
        ("torch", "torchaudio", "transformers", "librosa", "faiss"),
    ),
)

WSL_AUDIO_ASSET_RELATIVE_PATHS: tuple[str, ...] = (
    "wsl2_audio/setup_wsl2_audio.sh",
    "wsl2_audio/setup_cuda_env.sh",
    "wsl2_audio/process_audio.py",
    "wsl2_audio/audio_service.py",
    "wsl2_audio/fw_transcribe.py",
    "scripts/wsl/install_audio_service.sh",
)


def _print(msg: str) -> None:
    print(msg, flush=True)


def _fail(msg: str, exit_code: int = 1) -> int:
    _print(f"[FAIL] {msg}")
    return exit_code


def _completed_output(completed: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part for part in ((completed.stdout or "").strip(), (completed.stderr or "").strip()) if part).strip()


def _format_elapsed(seconds: float) -> str:
    total = max(int(seconds), 0)
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def _model_progress_stale_timeout_sec() -> int:
    raw = os.environ.get("GOODQ_MODEL_STALL_TIMEOUT_SEC", "300").strip()
    try:
        return max(int(raw), 30)
    except ValueError:
        return 300


def _artifact_hint(paths: Iterable[Path]) -> str:
    for candidate in paths:
        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate
        if resolved.exists():
            return str(resolved)
    for candidate in paths:
        return str(candidate)
    return ""


def _read_json_file(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None
    except Exception:
        return None


def _bootstrap_models_heartbeat_status(progress_path: Path, report_path: Path) -> str:
    payload = _read_json_file(progress_path)
    if not isinstance(payload, dict):
        fallback = _read_json_file(report_path)
        if isinstance(fallback, dict):
            completed_count = fallback.get("completed_count")
            status = str(fallback.get("status") or "unknown")
            if completed_count is not None:
                return f"report_status={status} completed={completed_count}"
            return f"report_status={status}"
        return ""

    current_model = str(payload.get("current_model") or "pending")
    current_index = payload.get("current_index")
    total_assets = payload.get("total_assets")
    attempt = payload.get("current_attempt")
    completed_count = payload.get("completed_count")
    last_event = str(payload.get("last_event") or "unknown")
    status = str(payload.get("status") or "unknown")
    last_progress_at = payload.get("last_progress_at")
    age_text = "unknown"
    stale_marker = ""
    if isinstance(last_progress_at, (int, float)):
        age_sec = max(int(time.time() - float(last_progress_at)), 0)
        age_text = _format_elapsed(age_sec)
        if age_sec >= _model_progress_stale_timeout_sec():
            stale_marker = " stale=yes"

    parts = [f"progress_status={status}"]
    if current_index and total_assets:
        parts.append(f"asset={current_index}/{total_assets}")
    if completed_count is not None:
        parts.append(f"completed={completed_count}")
    parts.append(f"current_model={current_model}")
    if attempt not in (None, ""):
        parts.append(f"attempt={attempt}")
    parts.append(f"last_event={last_event}")
    parts.append(f"last_progress_age={age_text}{stale_marker}")
    return " ".join(parts)


def _run_with_heartbeat(
    cmd: list[str],
    *,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
    heartbeat_label: str,
    heartbeat_interval: int,
    heartbeat_artifacts: Iterable[Path],
    heartbeat_status_fn: Optional[Callable[[], str]] = None,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    output_lines: list[str] = []
    state = {
        "last_output_at": time.time(),
        "last_output_line": "",
    }

    def _reader() -> None:
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            output_lines.append(raw_line)
            line = raw_line.rstrip("\r\n")
            if line:
                state["last_output_at"] = time.time()
                state["last_output_line"] = line
                _print(line)

    reader = threading.Thread(target=_reader, name="bootstrap-install-reader", daemon=True)
    reader.start()

    started = time.time()
    last_heartbeat = started
    artifact_hint = _artifact_hint(heartbeat_artifacts)
    while proc.poll() is None:
        time.sleep(1)
        now = time.time()
        if now - state["last_output_at"] < heartbeat_interval:
            continue
        if now - last_heartbeat < heartbeat_interval:
            continue
        message = f"[HEARTBEAT] {heartbeat_label}: elapsed={_format_elapsed(now - started)}"
        if artifact_hint:
            message += f" artifact_hint={artifact_hint}"
        if heartbeat_status_fn:
            status_hint = heartbeat_status_fn().strip()
            if status_hint:
                message += f" {status_hint}"
        if state["last_output_line"]:
            message += f" last_output={state['last_output_line'][:140]}"
        else:
            message += " status=waiting_for_subprocess_output"
        _print(message)
        last_heartbeat = now

    reader.join(timeout=5)
    stdout = "".join(output_lines)
    return subprocess.CompletedProcess(cmd, proc.returncode or 0, stdout=stdout, stderr="")


def _run(
    cmd: list[str],
    *,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
    capture: bool = True,
    check: bool = False,
    heartbeat_label: str | None = None,
    heartbeat_interval: int = 20,
    heartbeat_artifacts: Iterable[Path] = (),
    heartbeat_status_fn: Optional[Callable[[], str]] = None,
) -> subprocess.CompletedProcess[str]:
    if heartbeat_label:
        completed = _run_with_heartbeat(
            cmd,
            cwd=cwd,
            env=env,
            heartbeat_label=heartbeat_label,
            heartbeat_interval=max(int(heartbeat_interval), 1),
            heartbeat_artifacts=heartbeat_artifacts,
            heartbeat_status_fn=heartbeat_status_fn,
        )
        if check and completed.returncode != 0:
            raise subprocess.CalledProcessError(completed.returncode, cmd, output=completed.stdout, stderr=completed.stderr)
        return completed

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


def _command_exists(name: str) -> bool:
    return shutil.which(name) is not None


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
    distro = DEFAULT_WSL_DISTRO
    if distros:
        ubuntu_like = [candidate for candidate in distros if candidate.lower().startswith("ubuntu")]
        if ubuntu_like:
            exact = next((candidate for candidate in ubuntu_like if candidate.lower() == "ubuntu"), None)
            distro = exact or ubuntu_like[0]
        else:
            distro = distros[0]
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
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw:
            return default
        lowered = raw.lower()
        if lowered in {"y", "yes"}:
            _print(f"[INFO] Using default path: {default}")
            return default
        if lowered in {"n", "no"}:
            _print(f"[WARN] Enter a path or press Enter to accept the default: {default}")
            continue
        return raw


def prompt_bool(prompt: str, default: bool, assume_yes: bool) -> bool:
    if assume_yes or not sys.stdin.isatty():
        return default
    suffix = "Y/n" if default else "y/N"
    raw = input(f"{prompt} [{suffix}]: ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes", "1", "true"}


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


def _run_powershell(command: str, *, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(["powershell", "-NoProfile", "-Command", command], capture=capture)


def _quote_ps(value: str) -> str:
    return value.replace("'", "''")


def _strip_wrapping_quotes(value: str) -> str:
    trimmed = (value or "").strip()
    if len(trimmed) >= 2 and trimmed[0] == trimmed[-1] and trimmed[0] in {"'", '"'}:
        return trimmed[1:-1]
    return trimmed


def _bash_quote(value: str) -> str:
    return "'" + str(value).replace("'", "'\"'\"'") + "'"


def _windows_to_wsl_path(path: str | Path) -> Optional[str]:
    normalized = str(path).replace("\\", "/")
    if len(normalized) >= 3 and normalized[1] == ":" and normalized[2] == "/":
        return f"/mnt/{normalized[0].lower()}/{normalized[3:]}"
    if normalized.startswith("/"):
        return normalized
    return None


def _wsl_unc_path(distro: str, wsl_path: str) -> Path:
    segments = [segment for segment in str(wsl_path).replace("\\", "/").split("/") if segment]
    unc = Path(rf"\\wsl$\{distro}")
    for segment in segments:
        unc = unc / segment
    return unc


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = _strip_wrapping_quotes(value)
    return values


def _is_placeholder_secret(value: str) -> bool:
    lowered = (value or "").strip().lower()
    return not lowered or lowered.startswith("your_") or lowered.endswith("_here")


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


def _has_core_torch_stack_conflict(conda_exe: Path) -> tuple[bool, str]:
    completed = _run([str(conda_exe), "list", "-n", ENV_NAME, "--json"])
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip() or "conda list failed"
        return False, detail
    try:
        payload = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError:
        return False, "conda list returned invalid JSON"

    has_conda_pytorch = any(str(rec.get("name")).lower() == "pytorch" for rec in payload if isinstance(rec, dict))
    has_pip_torch = any(
        str(rec.get("name")).lower() == "torch" and str(rec.get("channel", "")).lower() == "pypi"
        for rec in payload
        if isinstance(rec, dict)
    )
    if has_conda_pytorch and has_pip_torch:
        return True, "detected both Conda pytorch and pip torch in goodq_core"
    return False, "no duplicate torch stack detected"


def _conda_tos_commands(conda_exe: Path) -> list[list[str]]:
    return [
        [str(conda_exe), "tos", "accept", "--override-channels", "--channel", channel]
        for channel in CONDA_TOS_CHANNELS
    ]


def _conda_tos_instruction_block() -> str:
    commands = "\n".join(
        f"  conda tos accept --override-channels --channel {channel}" for channel in CONDA_TOS_CHANNELS
    )
    return f"Conda channel Terms of Service must be accepted before environment creation can continue:\n{commands}"


def _is_conda_tos_block(detail: str) -> bool:
    lowered = detail.lower()
    return (
        "terms of service" in lowered
        or "conda tos" in lowered
        or ("repo.anaconda.com" in lowered and "accept" in lowered and "channel" in lowered)
    )


def _is_transient_conda_network_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(
        token in lowered
        for token in (
            "condahttperror",
            "http 000 connection failed",
            "connection reset",
            "read timeout",
            "temporarily unavailable",
            "failed after connection broken",
        )
    )


def _accept_conda_tos(conda_exe: Path, *, assume_yes: bool) -> None:
    _print("")
    _print("[WARN] Conda channel Terms of Service are not yet accepted for this machine.")
    if not prompt_bool("Accept the required Conda channel Terms of Service now", True, assume_yes):
        raise RuntimeError(_conda_tos_instruction_block())

    for cmd in _conda_tos_commands(conda_exe):
        completed = _run(cmd)
        if completed.returncode != 0:
            detail = _completed_output(completed) or "conda tos accept failed"
            raise RuntimeError(f"{detail}\n\n{_conda_tos_instruction_block()}")
    _print("[OK] Accepted required Conda channel Terms of Service")


def _run_conda_with_tos_retry(
    conda_exe: Path,
    cmd: list[str],
    *,
    repo_root: Path,
    assume_yes: bool,
    capture: bool = True,
    heartbeat_label: str | None = None,
    heartbeat_artifacts: Iterable[Path] = (),
) -> subprocess.CompletedProcess[str]:
    completed: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, 4):
        completed = _run(
            cmd,
            cwd=repo_root,
            capture=capture,
            heartbeat_label=heartbeat_label,
            heartbeat_artifacts=heartbeat_artifacts,
        )
        if completed.returncode == 0:
            return completed

        detail = (completed.stderr or completed.stdout).strip() or "conda environment command failed"
        if _is_conda_tos_block(detail):
            _accept_conda_tos(conda_exe, assume_yes=assume_yes)
            completed = _run(
                cmd,
                cwd=repo_root,
                capture=capture,
                heartbeat_label=heartbeat_label,
                heartbeat_artifacts=heartbeat_artifacts,
            )
            if completed.returncode == 0:
                return completed
            detail = (completed.stderr or completed.stdout).strip() or "conda environment command failed"

        if attempt < 3 and _is_transient_conda_network_error(detail):
            _print(f"[WARN] Transient Conda network failure (attempt {attempt}/3). Retrying...")
            time.sleep(attempt * 2)
            continue
        raise RuntimeError(detail)

    assert completed is not None
    return completed


def ensure_conda_env(conda_exe: Path, repo_root: Path, env_file: Path, *, assume_yes: bool) -> None:
    if conda_env_exists(conda_exe, ENV_NAME):
        _print(f"[INFO] Updating existing Conda environment: {ENV_NAME}")
        _run_conda_with_tos_retry(
            conda_exe,
            [str(conda_exe), "env", "update", "-n", ENV_NAME, "-f", str(env_file)],
            repo_root=repo_root,
            assume_yes=assume_yes,
            heartbeat_label=f"Conda env update ({ENV_NAME})",
            heartbeat_artifacts=(env_file,),
        )
        has_conflict, detail = _has_core_torch_stack_conflict(conda_exe)
        if has_conflict:
            _print(f"[WARN] {detail}; recreating {ENV_NAME} from {env_file.name}")
            _run_conda_with_tos_retry(
                conda_exe,
                [str(conda_exe), "env", "remove", "-n", ENV_NAME, "-y"],
                repo_root=repo_root,
                assume_yes=assume_yes,
                heartbeat_label=f"Conda env remove ({ENV_NAME})",
                heartbeat_artifacts=(env_file,),
            )
            _run_conda_with_tos_retry(
                conda_exe,
                [str(conda_exe), "env", "create", "-f", str(env_file)],
                repo_root=repo_root,
                assume_yes=assume_yes,
                heartbeat_label=f"Conda env create ({ENV_NAME})",
                heartbeat_artifacts=(env_file,),
            )
    else:
        _print(f"[INFO] Creating Conda environment from {env_file.name}")
        _run_conda_with_tos_retry(
            conda_exe,
            [str(conda_exe), "env", "create", "-f", str(env_file)],
            repo_root=repo_root,
            assume_yes=assume_yes,
            heartbeat_label=f"Conda env create ({ENV_NAME})",
            heartbeat_artifacts=(env_file,),
        )


def _isolated_process_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    env["PIP_NO_CACHE_DIR"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return env


def _read_lock_lines(lock_path: Path) -> list[str]:
    return [
        line.strip()
        for line in lock_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _lock_uses_cuda_wheels(lock_path: Path) -> bool:
    return any("+cu121" in line for line in _read_lock_lines(lock_path))


def _create_step_env(conda_exe: Path, repo_root: Path, spec: StepEnvSpec, *, assume_yes: bool) -> None:
    _run_conda_with_tos_retry(
        conda_exe,
        [str(conda_exe), "create", "-y", "-n", spec.name, f"python={STEP_ENV_PYTHON}", "pip"],
        repo_root=repo_root,
        assume_yes=assume_yes,
        heartbeat_label=f"Step env create ({spec.name})",
        heartbeat_artifacts=(repo_root / spec.lock_rel_path,),
    )


def _remove_step_env(conda_exe: Path, repo_root: Path, spec: StepEnvSpec, *, assume_yes: bool) -> None:
    _run_conda_with_tos_retry(
        conda_exe,
        [str(conda_exe), "env", "remove", "-n", spec.name, "-y"],
        repo_root=repo_root,
        assume_yes=assume_yes,
        heartbeat_label=f"Step env remove ({spec.name})",
        heartbeat_artifacts=(repo_root / spec.lock_rel_path,),
    )


def _ensure_step_env_conda_packages(conda_exe: Path, repo_root: Path, spec: StepEnvSpec, *, assume_yes: bool) -> None:
    if not spec.conda_packages:
        return
    cmd = [str(conda_exe), "install", "-y", "-n", spec.name]
    for channel in spec.conda_channels:
        cmd.extend(["-c", channel])
    cmd.extend(spec.conda_packages)
    _run_conda_with_tos_retry(
        conda_exe,
        cmd,
        repo_root=repo_root,
        assume_yes=assume_yes,
        heartbeat_label=f"Step env conda sync ({spec.name})",
        heartbeat_artifacts=(repo_root / spec.lock_rel_path,),
    )


def _install_step_env_from_lock(conda_exe: Path, repo_root: Path, spec: StepEnvSpec) -> None:
    lock_path = repo_root / spec.lock_rel_path
    pip_env = _isolated_process_env()
    upgrade = _run(
        [
            str(conda_exe),
            "run",
            "-n",
            spec.name,
            "python",
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
            "--no-cache-dir",
            "--no-user",
            "--isolated",
        ],
        cwd=repo_root,
        env=pip_env,
        heartbeat_label=f"Step env pip upgrade ({spec.name})",
        heartbeat_artifacts=(lock_path,),
    )
    if upgrade.returncode != 0:
        detail = (upgrade.stderr or upgrade.stdout).strip() or f"pip upgrade failed for {spec.name}"
        raise RuntimeError(detail)

    install_cmd = [
        str(conda_exe),
        "run",
        "-n",
        spec.name,
        "python",
        "-m",
        "pip",
        "install",
        "-r",
        str(lock_path),
        "--no-cache-dir",
        "--no-user",
        "--isolated",
        "--no-deps",
    ]
    if _lock_uses_cuda_wheels(lock_path):
        install_cmd.extend(["--extra-index-url", TORCH_CUDA_INDEX_URL])

    install = _run(
        install_cmd,
        cwd=repo_root,
        env=pip_env,
        heartbeat_label=f"Step env lock install ({spec.name})",
        heartbeat_artifacts=(lock_path,),
    )
    if install.returncode != 0:
        detail = (install.stderr or install.stdout).strip() or f"lock install failed for {spec.name}"
        raise RuntimeError(detail)


def _validate_step_env(conda_exe: Path, repo_root: Path, spec: StepEnvSpec) -> list[str]:
    issues: list[str] = []
    runtime_env = _isolated_process_env()

    pip_check = _run(
        [str(conda_exe), "run", "-n", spec.name, "python", "-m", "pip", "check"],
        cwd=repo_root,
        env=runtime_env,
    )
    if pip_check.returncode != 0:
        detail = (pip_check.stdout or pip_check.stderr).strip() or "pip check failed"
        lines = [line.strip() for line in detail.splitlines() if line.strip()]
        unexpected = [
            line for line in lines
            if not any(allowed in line for allowed in spec.allowed_pip_check_warnings)
        ]
        if unexpected:
            issues.append(f"pip check failed for {spec.name}: {' | '.join(unexpected)}")
        else:
            _print(
                f"[INFO] {spec.name}: accepted non-blocking dependency notice "
                f"(runtime fallback remains supported): {' | '.join(lines)}"
            )

    smoke_code = "import " + ", ".join(spec.smoke_imports) + "; print('ok')"
    smoke = _run(
        [str(conda_exe), "run", "-n", spec.name, "python", "-c", smoke_code],
        cwd=repo_root,
        env=runtime_env,
    )
    if smoke.returncode != 0:
        detail = (smoke.stderr or smoke.stdout).strip() or f"smoke import failed for {spec.name}"
        issues.append(f"smoke imports failed for {spec.name}: {detail}")

    return issues


def ensure_step_env(conda_exe: Path, repo_root: Path, spec: StepEnvSpec, *, assume_yes: bool) -> None:
    req_path = repo_root / spec.req_rel_path
    lock_path = repo_root / spec.lock_rel_path
    if not req_path.exists():
        raise RuntimeError(f"Missing requirements file for {spec.name}: {req_path}")
    if not lock_path.exists():
        raise RuntimeError(f"Missing lock file for {spec.name}: {lock_path}")

    existed = conda_env_exists(conda_exe, spec.name)
    if existed:
        _print(f"[INFO] Refreshing supported step env: {spec.name} ({spec.description}) from {lock_path.relative_to(repo_root)}")
    else:
        _print(f"[INFO] Creating supported step env: {spec.name} ({spec.description}) from {lock_path.relative_to(repo_root)}")
        _create_step_env(conda_exe, repo_root, spec, assume_yes=assume_yes)

    def _sync_and_validate() -> list[str]:
        _ensure_step_env_conda_packages(conda_exe, repo_root, spec, assume_yes=assume_yes)
        _install_step_env_from_lock(conda_exe, repo_root, spec)
        return _validate_step_env(conda_exe, repo_root, spec)

    issues = _sync_and_validate()
    if issues and existed:
        _print(f"[WARN] {spec.name} diverged from the locked recipe; recreating the env for a clean sync")
        _remove_step_env(conda_exe, repo_root, spec, assume_yes=assume_yes)
        _create_step_env(conda_exe, repo_root, spec, assume_yes=assume_yes)
        issues = _sync_and_validate()
    if issues:
        raise RuntimeError(" ; ".join(issues))


def ensure_supported_step_envs(ctx: BootstrapContext, *, assume_yes: bool) -> None:
    if not ctx.install_step_envs:
        _print("[WARN] Step environment pack skipped. Full pipeline capability is not guaranteed.")
        return

    _print("[INFO] Provisioning supported step environment pack for full pipeline capability")
    for spec in SUPPORTED_STEP_ENVS:
        ensure_step_env(ctx.conda_exe, ctx.repo_root, spec, assume_yes=assume_yes)


def _run_bootstrap_models(conda_exe: Path, repo_root: Path, report_path: Path, progress_path: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            str(conda_exe),
            "run",
            "-n",
            ENV_NAME,
            "python",
            str(repo_root / "scripts" / "bootstrap_models.py"),
            "--report-path",
            str(report_path),
            "--progress-path",
            str(progress_path),
        ],
        cwd=repo_root,
        env=_isolated_process_env(),
        heartbeat_label="Model prefetch",
        heartbeat_artifacts=(progress_path, report_path),
        heartbeat_status_fn=lambda: _bootstrap_models_heartbeat_status(progress_path, report_path),
    )


def ensure_model_cache(ctx: BootstrapContext) -> None:
    if not ctx.prefetch_models:
        _print("[WARN] Model cache prefetch skipped. First-run embedding steps may be degraded until required models are staged.")
        return

    _print("[INFO] Prefetching required model cache for offline-ready ingest")
    _print("[INFO] Live model download progress will be shown below. Transient network failures are retried automatically.")
    report_path = ctx.repo_root / "logs" / "bootstrap_models_report.json"
    progress_path = ctx.repo_root / "logs" / "bootstrap_models_progress.json"
    report_path.unlink(missing_ok=True)
    progress_path.unlink(missing_ok=True)
    completed = _run_bootstrap_models(ctx.conda_exe, ctx.repo_root, report_path, progress_path)
    if completed.returncode != 0:
        raise RuntimeError("bootstrap_models.py failed; see console output above")

    required_failures: list[str] = []
    gated_failures: list[str] = []
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"bootstrap_models.py completed but did not write a report: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"bootstrap_models.py wrote invalid JSON report: {exc}") from exc

    env_payload = payload.get("env", {}) if isinstance(payload, dict) else {}
    hf_auth_present = bool(env_payload.get("hf_auth_present"))
    pyannote_auth_present = bool(env_payload.get("pyannote_auth_present"))
    hf_auth_source = str(env_payload.get("hf_auth_source") or "none")
    pyannote_auth_source = str(env_payload.get("pyannote_auth_source") or "none")
    if hf_auth_present:
        _print(f"[INFO] Hugging Face auth detected via {hf_auth_source}")
    else:
        _print("[WARN] Hugging Face auth not detected from .env.local or the current environment")
    if pyannote_auth_present:
        _print(f"[INFO] PyAnnote auth detected via {pyannote_auth_source}")
    else:
        _print("[WARN] PyAnnote auth not detected; gated diarization downloads may be skipped")

    for entry in payload.get("results", []):
        if not isinstance(entry, dict) or str(entry.get("status")).lower() != "error":
            continue
        model_name = str(entry.get("model") or entry.get("asset") or "unknown")
        if model_name.startswith("pyannote/"):
            gated_failures.append(model_name)
        else:
            required_failures.append(model_name)

    if required_failures:
        raise RuntimeError(
            "required model prefetch failed for: " + ", ".join(required_failures)
        )
    if gated_failures:
        _print(
            "[WARN] Gated model downloads were skipped or failed: "
            + ", ".join(gated_failures)
            + ". Set HF_TOKEN/PYANNOTE_TOKEN in .env.local and rerun bootstrap_models.py for full gated coverage."
        )
    ok_count = sum(1 for entry in payload.get("results", []) if isinstance(entry, dict) and str(entry.get("status")).lower() == "ok")
    error_count = len(required_failures) + len(gated_failures)
    _print(f"[INFO] Model prefetch summary: ok={ok_count} error={error_count}")
    _print("[OK] Required model cache prefetched")


def env_python(conda_exe: Path, repo_root: Path, code: str) -> subprocess.CompletedProcess[str]:
    return _run(
        [str(conda_exe), "run", "-n", ENV_NAME, "python", "-c", code],
        cwd=repo_root,
        env=_isolated_process_env(),
    )


def resolve_models_cache_root(conda_exe: Path, repo_root: Path) -> Optional[Path]:
    completed = env_python(
        conda_exe,
        repo_root,
        (
            "from steps.common.config_loader import get_runtime_paths, load_configs; "
            "cfg = load_configs({}); "
            "paths = get_runtime_paths(cfg, 'models_cache'); "
            "print(paths.get('models_cache', ''))"
        ),
    )
    if completed.returncode != 0:
        return None
    lines = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
    if not lines:
        return None
    return Path(lines[-1])


def check_disk_space(path: Path) -> tuple[bool, str]:
    probe = path
    if not probe.exists():
        probe = probe.parent if probe.parent.exists() else Path.cwd()
    usage = shutil.disk_usage(str(probe))
    free_gb = usage.free / (1024 ** 3)
    return free_gb >= MIN_FREE_SPACE_GB, f"{free_gb:.1f} GB free at {probe}"


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _effective_data_root(path: Path) -> Path:
    normalized = Path(path)
    return normalized if normalized.name.lower() == "goodq_data" else normalized / "GoodQ_Data"


def _base_data_root(path: Path) -> Path:
    effective = _effective_data_root(path)
    return effective.parent if effective.parent != effective else effective


def _resolve_wsl_audio_context(ctx: BootstrapContext) -> WslAudioContext:
    distro = (ctx.wsl_distro or DEFAULT_WSL_DISTRO).strip() or DEFAULT_WSL_DISTRO
    explicit_user = (ctx.wsl_user or os.environ.get("GOODQ_WSL_USER") or "").strip()
    explicit_workspace = _strip_wrapping_quotes(
        ctx.wsl_workspace or os.environ.get("GOODQ_WSL_WORKSPACE") or ""
    ).strip()
    if explicit_workspace.lower() == "auto":
        explicit_workspace = ""

    if not ctx.profile.wsl_available:
        raise RuntimeError("WSL audio bootstrap requested, but WSL is not available on this host.")

    probe = _run(
        [
            "wsl",
            "-d",
            distro,
            "--",
            "bash",
            "-lc",
            "printf '%s\\n%s\\n' \"$(whoami)\" \"$HOME\"",
        ]
    )
    if probe.returncode != 0:
        detail = (probe.stderr or probe.stdout).strip() or f"unable to query distro {distro}"
        raise RuntimeError(
            f"WSL distro '{distro}' is not ready yet. Launch it once to finish first-time setup, then rerun bootstrap. Detail: {detail}"
        )

    lines = [line.strip() for line in (probe.stdout or "").splitlines() if line.strip()]
    detected_user = lines[0] if lines else ""
    detected_home = lines[1] if len(lines) > 1 else ""
    user = explicit_user or detected_user or "user"
    home = detected_home or f"/home/{user}"
    workspace = explicit_workspace or f"{home.rstrip('/')}/goodq_audio"
    return WslAudioContext(
        distro=distro,
        user=user,
        home=home.rstrip("/") or f"/home/{user}",
        workspace=workspace.rstrip("/") or f"/home/{user}/goodq_audio",
        windows_workspace=_wsl_unc_path(distro, workspace),
    )


def _wsl_audio_env_values(ctx: BootstrapContext, wsl_ctx: WslAudioContext) -> dict[str, str]:
    env_file_values = _load_env_file(ctx.repo_root / ".env.local")

    def pick(*keys: str) -> Optional[str]:
        for key in keys:
            candidate = _strip_wrapping_quotes(os.environ.get(key) or env_file_values.get(key) or "")
            if candidate and not _is_placeholder_secret(candidate):
                return candidate
        return None

    values = {
        "GOODQ_WSL_DISTRO": wsl_ctx.distro,
        "GOODQ_WSL_USER": wsl_ctx.user,
        "GOODQ_WSL_WORKSPACE": wsl_ctx.workspace,
        "GOODQ_REQUIRE_WSL_AUDIO": "1",
        "GOODQ_REQUIRE_GPU": "1" if ctx.enable_gpu else "0",
    }

    hf_token = pick("HF_TOKEN", "HF_HUB_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACE_HUB_TOKEN")
    pyannote_token = pick("PYANNOTE_TOKEN") or hf_token
    if hf_token:
        values.update(
            {
                "HF_TOKEN": hf_token,
                "HF_HUB_TOKEN": hf_token,
                "HUGGINGFACE_TOKEN": hf_token,
                "HUGGINGFACE_HUB_TOKEN": hf_token,
            }
        )
    if pyannote_token:
        values["PYANNOTE_TOKEN"] = pyannote_token

    models_root = resolve_models_cache_root(ctx.conda_exe, ctx.repo_root)
    wsl_models_root = _windows_to_wsl_path(models_root) if models_root else None
    if wsl_models_root:
        values["HF_HOME"] = wsl_models_root
        values["TORCH_HOME"] = wsl_models_root
        values["HUGGINGFACE_HUB_CACHE"] = f"{wsl_models_root.rstrip('/')}/hub"

    return values


def _render_env_assignment(value: str) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _write_wsl_audio_env_file(wsl_ctx: WslAudioContext, values: dict[str, str]) -> Path:
    env_path = wsl_ctx.windows_workspace / ".goodq_env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Generated by scripts/bootstrap_install.py"]
    for key in sorted(values):
        lines.append(f"{key}={_render_env_assignment(values[key])}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return env_path


def _run_wsl_bash(
    wsl_ctx: WslAudioContext,
    script: str,
    *,
    heartbeat_label: str | None = None,
    heartbeat_artifacts: Iterable[Path] = (),
) -> subprocess.CompletedProcess[str]:
    return _run(
        ["wsl", "-d", wsl_ctx.distro, "--", "bash", "-lc", script],
        heartbeat_label=heartbeat_label,
        heartbeat_artifacts=heartbeat_artifacts,
    )


def _normalize_wsl_shell_asset(path: Path) -> bool:
    if path.suffix.lower() != ".sh" or not path.exists():
        return False
    raw = path.read_bytes()
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if normalized == raw:
        return False
    path.write_bytes(normalized)
    return True


def _sync_wsl_audio_assets(ctx: BootstrapContext, wsl_ctx: WslAudioContext) -> None:
    wsl_ctx.windows_workspace.mkdir(parents=True, exist_ok=True)
    for rel_path in WSL_AUDIO_ASSET_RELATIVE_PATHS:
        src = ctx.repo_root / rel_path
        if not src.exists():
            raise FileNotFoundError(f"Missing WSL audio asset: {src}")
        dst = wsl_ctx.windows_workspace / Path(rel_path).name
        shutil.copy2(src, dst)
        if _normalize_wsl_shell_asset(dst):
            _print(f"[INFO] Normalized CRLF line endings for staged WSL shell asset: {dst.name}")
    chmod_targets = " ".join(
        _bash_quote(f"{wsl_ctx.workspace}/{Path(rel_path).name}") for rel_path in WSL_AUDIO_ASSET_RELATIVE_PATHS
    )
    _run_wsl_bash(wsl_ctx, f"chmod +x {chmod_targets}")


def _probe_wsl_audio_workspace_ready(wsl_ctx: WslAudioContext) -> tuple[bool, str]:
    script = (
        f"test -f {_bash_quote(f'{wsl_ctx.workspace}/setup_cuda_env.sh')} && "
        f"test -f {_bash_quote(f'{wsl_ctx.workspace}/process_audio.py')} && "
        f"(test -x {_bash_quote(f'{wsl_ctx.workspace}/venv/bin/python')} || "
        f"test -x {_bash_quote(f'{wsl_ctx.workspace}/env/bin/python')}) && "
        f"source {_bash_quote(f'{wsl_ctx.workspace}/setup_cuda_env.sh')} >/dev/null 2>&1 && "
        "python3 -c \"import faster_whisper, torch; print('ready')\""
    )
    completed = _run_wsl_bash(wsl_ctx, script)
    if completed.returncode == 0:
        return True, "workspace and Python runtime are ready"
    return False, _completed_output(completed) or "WSL audio workspace probe failed"


def _wsl_has_systemd(wsl_ctx: WslAudioContext) -> bool:
    completed = _run_wsl_bash(wsl_ctx, "test -d /run/systemd/system")
    return completed.returncode == 0


def _wsl_passwordless_sudo_ready(wsl_ctx: WslAudioContext) -> tuple[bool, str]:
    completed = _run_wsl_bash(wsl_ctx, "sudo -n true")
    if completed.returncode == 0:
        return True, "passwordless sudo available"
    return False, _completed_output(completed) or "sudo password required"


def ensure_wsl_audio_ready(ctx: BootstrapContext, *, assume_yes: bool) -> bool:
    if not ctx.enable_wsl_audio:
        return True
    if not ctx.profile.wsl_available:
        elevated = _is_admin()
        _print("")
        _print("WSL Audio Bootstrap Handoff")
        _print("===========================")
        _print(f"[WARN] WSL audio acceleration was requested, but WSL is not installed yet.")
        _print(f"[INFO] Elevation state: {'elevated' if elevated else 'non-elevated'}")
        _print(f"[INFO] Run this next in an elevated PowerShell:")
        _print(f"  wsl --install -d {ctx.wsl_distro}")
        _print("[INFO] Reboot if Windows asks, launch the distro once to finish first-time setup, then rerun bootstrap.")
        return False

    wsl_ctx = _resolve_wsl_audio_context(ctx)
    ctx.wsl_user = wsl_ctx.user
    ctx.wsl_workspace = wsl_ctx.workspace
    _print(f"[INFO] WSL audio target: distro={wsl_ctx.distro} user={wsl_ctx.user} workspace={wsl_ctx.workspace}")

    _run_wsl_bash(
        wsl_ctx,
        f"mkdir -p {_bash_quote(wsl_ctx.workspace)}",
        heartbeat_label="WSL audio workspace prepare",
        heartbeat_artifacts=(wsl_ctx.windows_workspace,),
    )
    _sync_wsl_audio_assets(ctx, wsl_ctx)
    env_file = _write_wsl_audio_env_file(wsl_ctx, _wsl_audio_env_values(ctx, wsl_ctx))

    ready, detail = _probe_wsl_audio_workspace_ready(wsl_ctx)
    if not ready:
        _print("[INFO] Provisioning WSL audio runtime. Your Linux password may be requested by sudo.")
        setup_script = (
            f"cd {_bash_quote(wsl_ctx.workspace)} && "
            "set -a && [ -f ./.goodq_env ] && source ./.goodq_env; set +a && "
            f"GOODQ_WSL_WORKSPACE={_bash_quote(wsl_ctx.workspace)} "
            f"./setup_wsl2_audio.sh"
        )
        completed = _run_wsl_bash(
            wsl_ctx,
            setup_script,
            heartbeat_label="WSL audio bootstrap",
            heartbeat_artifacts=(wsl_ctx.windows_workspace / "venv", env_file),
        )
        if completed.returncode != 0:
            raise RuntimeError(_completed_output(completed) or "WSL audio setup failed")
        ready, detail = _probe_wsl_audio_workspace_ready(wsl_ctx)
        if not ready:
            raise RuntimeError(f"WSL audio workspace is still not ready after setup: {detail}")
    else:
        _print(f"[OK] WSL audio workspace already ready: {detail}")

    if _wsl_has_systemd(wsl_ctx):
        sudo_ready, sudo_detail = _wsl_passwordless_sudo_ready(wsl_ctx)
        if not sudo_ready:
            _print("[WARN] WSL audio workspace is ready, but persistent service install requires a Linux sudo password.")
            _print("[INFO] WSL audio service status: PENDING_SUDO")
            if sudo_detail:
                _print(f"[INFO] WSL sudo preflight detail: {sudo_detail}")
            _print("[INFO] Complete this once inside WSL to enable the persistent audio service:")
            _print(f"  wsl -d {wsl_ctx.distro}")
            _print(f"  cd {wsl_ctx.workspace}")
            _print("  bash ./install_audio_service.sh")
            _print(
                "[INFO] Direct WSL audio execution remains available meanwhile; bootstrap will continue without the persistent service."
            )
            return True
        service_script = (
            f"cd {_bash_quote(wsl_ctx.workspace)} && "
            "set -a && [ -f ./.goodq_env ] && source ./.goodq_env; set +a && "
            f"GOODQ_WSL_USER={_bash_quote(wsl_ctx.user)} "
            f"GOODQ_WSL_WORKSPACE={_bash_quote(wsl_ctx.workspace)} "
            "./install_audio_service.sh"
        )
        completed = _run_wsl_bash(
            wsl_ctx,
            service_script,
            heartbeat_label="WSL audio service install",
            heartbeat_artifacts=(wsl_ctx.windows_workspace / "logs",),
        )
        if completed.returncode == 0:
            _print("[OK] WSL audio service is installed and running.")
            _print("[INFO] WSL audio service status: RUNNING")
        else:
            _print("[WARN] WSL audio workspace is ready, but service install did not complete cleanly.")
            detail = _completed_output(completed)
            if detail:
                _print(f"[INFO] WSL service detail: {detail}")
            _print(
                "[INFO] Direct WSL audio execution remains available; rerun install_audio_service.sh inside WSL when convenient."
            )
    else:
        _print("[WARN] WSL systemd is unavailable; skipping persistent audio service install.")
        _print("[INFO] WSL audio service status: SKIPPED_NO_SYSTEMD")
        _print(
            f"[INFO] Direct WSL audio execution is ready. Manual service command: "
            f"wsl -d {wsl_ctx.distro} -- bash -lc \"cd {wsl_ctx.workspace} && source setup_cuda_env.sh && python3 audio_service.py\""
        )

    return True


def write_env_local(path: Path, template_path: Path, ctx: BootstrapContext) -> None:
    managed_marker = "# Bootstrap-managed defaults"
    created = not path.exists()
    if created:
        base = template_path.read_text(encoding="utf-8") if template_path.exists() else "# GoodQ local overrides\n"
    else:
        existing = path.read_text(encoding="utf-8")
        if managed_marker not in existing:
            _print(f"[INFO] Preserving existing {path.name}")
            return
        base = existing.split(managed_marker, 1)[0].rstrip()

    base_data_root = _base_data_root(ctx.data_root)
    wsl_audio_ready = bool(ctx.enable_wsl_audio and ctx.wsl_user and ctx.wsl_workspace)
    wsl_workspace = ctx.wsl_workspace or "auto"
    wsl_user = ctx.wsl_user or "auto"
    managed_block = textwrap.dedent(
        f"""

        # ----------------------------------------------------------------------
        # Bootstrap-managed defaults
        # ----------------------------------------------------------------------
        GOODQ_DATA_ROOT={base_data_root}
        GOODQ_CONDA_ENV={ENV_NAME}
        GOODQ_HOST_PROFILE={ctx.profile.profile}
        GOODQ_REQUIRE_GPU=0
        GOODQ_REQUIRE_WSL_AUDIO={1 if wsl_audio_ready else 0}
        GOODQ_WSL_DISTRO={ctx.wsl_distro}
        GOODQ_WSL_USER={wsl_user}
        GOODQ_WSL_WORKSPACE={wsl_workspace}
        """
    ).lstrip()
    path.write_text(base.rstrip() + "\n\n" + managed_block, encoding="utf-8")
    _print(f"[OK] {'Created' if created else 'Updated'} {path.name}")


def write_config_local(path: Path, ctx: BootstrapContext) -> None:
    generated_marker = "# Generated by scripts/bootstrap_install.py"
    created = not path.exists()
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if generated_marker not in existing:
            _print(f"[INFO] Preserving existing {path.name}")
            return

    data_root = _base_data_root(ctx.data_root).as_posix()
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
    _print(f"[OK] {'Created' if created else 'Updated'} {path.name}")


def resolve_ffmpeg() -> tuple[bool, str]:
    override = os.environ.get("GOODQ_FFMPEG_EXE", "").strip().strip('"').strip("'")
    if override:
        override_path = Path(override)
        if override_path.is_dir():
            for name in ("ffmpeg.exe", "ffmpeg"):
                candidate = override_path / name
                if candidate.exists():
                    override_path = candidate
                    break
        if override_path.exists():
            return True, f"GOODQ_FFMPEG_EXE={override_path}"
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return True, ffmpeg_path
    return False, "ffmpeg not found on PATH and GOODQ_FFMPEG_EXE is unset"


def _ffmpeg_instruction_block() -> str:
    lines = [
        "FFmpeg is optional but recommended for media extraction.",
        "Installer guidance:",
    ]
    if _command_exists("winget"):
        lines.append(f"  winget install --id {WINGET_FFMPEG_ID} -e --accept-package-agreements --accept-source-agreements")
    if _command_exists("choco"):
        lines.append(f"  choco install {CHOCO_FFMPEG_PACKAGE} -y")
    lines.append("  Or install FFmpeg manually and add it to PATH, or set GOODQ_FFMPEG_EXE in .env.local")
    return "\n".join(lines)


def ensure_ffmpeg_ready(*, assume_yes: bool) -> bool:
    ffmpeg_ok, ffmpeg_detail = resolve_ffmpeg()
    if ffmpeg_ok:
        _print(f"[OK] ffmpeg: {ffmpeg_detail}")
        return True

    _print(f"[WARN] ffmpeg: {ffmpeg_detail}")
    install_cmd: Optional[list[str]] = None
    install_label = ""
    if _command_exists("winget"):
        install_cmd = [
            "winget",
            "install",
            "--id",
            WINGET_FFMPEG_ID,
            "-e",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
        install_label = "winget"
    elif _command_exists("choco"):
        install_cmd = ["choco", "install", CHOCO_FFMPEG_PACKAGE, "-y"]
        install_label = "Chocolatey"

    if install_cmd and prompt_bool(f"Attempt FFmpeg installation via {install_label} now", True, assume_yes):
        completed = _run(install_cmd, capture=False)
        if completed.returncode == 0:
            ffmpeg_ok, ffmpeg_detail = resolve_ffmpeg()
            if ffmpeg_ok:
                _print(f"[OK] ffmpeg installed: {ffmpeg_detail}")
                return True
        _print("[WARN] FFmpeg installation attempt did not complete successfully.")

    _print(_ffmpeg_instruction_block())
    return False


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


def resolve_qdrant_runtime_paths(conda_exe: Path, repo_root: Path) -> tuple[str, str]:
    code = (
        "import json; "
        "from steps.common.config_loader import get_runtime_paths, load_configs; "
        "cfg = load_configs({}); "
        "paths = get_runtime_paths(cfg, 'qdrant_storage', 'log_dir'); "
        "print(json.dumps({'qdrant_storage': paths['qdrant_storage'], 'log_dir': paths['log_dir']}))"
    )
    completed = env_python(conda_exe, repo_root, code)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip() or "unable to resolve Qdrant runtime paths"
        raise RuntimeError(detail)
    lines = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("unable to resolve Qdrant runtime paths")
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"unable to parse Qdrant runtime paths: {exc}") from exc
    qdrant_storage = str(payload.get("qdrant_storage") or "").strip()
    log_dir = str(payload.get("log_dir") or "").strip()
    if not qdrant_storage or not log_dir:
        raise RuntimeError("Qdrant runtime paths were incomplete")
    return qdrant_storage, log_dir


def check_qdrant(url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/collections", timeout=5) as response:
            return response.status == 200, f"reachable at {url}"
    except urllib.error.URLError as exc:
        return False, f"not reachable at {url} ({exc.reason})"
    except Exception as exc:  # noqa: BLE001
        return False, f"not reachable at {url} ({exc})"


def inspect_windows_service(name: str) -> dict[str, str]:
    command = (
        f"$svc = Get-Service -Name '{_quote_ps(name)}' -ErrorAction SilentlyContinue; "
        "if ($null -eq $svc) { 'exists=false' } "
        "else { "
        "'exists=true'; "
        "'status=' + $svc.Status.ToString(); "
        "try { "
        f"  $cim = Get-CimInstance Win32_Service -Filter \"Name='{name}'\"; "
        "  if ($cim) { 'start_mode=' + $cim.StartMode } "
        "} catch { } "
        "}"
    )
    completed = _run_powershell(command)
    info: dict[str, str] = {}
    for line in (completed.stdout or "").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        info[key.strip()] = value.strip()
    return info


def _qdrant_repair_instruction(ctx: BootstrapContext) -> str:
    lines = [
        "Preferred Qdrant repair/install path:",
        f"  {ctx.qdrant_service_installer}",
    ]
    if ctx.qdrant_start_bat.exists():
        lines.append(f"Foreground testing fallback only: {ctx.qdrant_start_bat}")
    return "\n".join(lines)


def _qdrant_admin_command(ctx: BootstrapContext) -> str:
    installer = str(ctx.qdrant_service_installer)
    return (
        "powershell -NoProfile -Command "
        f"\"Start-Process -FilePath 'cmd.exe' -Verb RunAs -ArgumentList '/c','\\\"{installer}\\\" --non-interactive'\""
    )


def _qdrant_lifecycle_state(qdrant_ok: bool, service_info: dict[str, str]) -> str:
    if qdrant_ok:
        return "QDRANT_RUNNING"
    if service_info.get("exists") == "true":
        return "QDRANT_INSTALLED"
    return "QDRANT_PENDING_ADMIN"


def _print_qdrant_handoff(ctx: BootstrapContext, *, state: str, elevated: bool, qdrant_url: str) -> None:
    _print("[INFO] Qdrant lifecycle state: " + state)
    _print(f"[INFO] Current shell elevation: {'admin' if elevated else 'standard user'}")
    _print(f"[INFO] Qdrant health endpoint: {qdrant_url.rstrip('/')}")
    if not elevated and state != "QDRANT_RUNNING":
        _print("[WARN] Administrator privileges are required to install or repair the canonical Windows Qdrant service.")
        _print("[INFO] Run this command from an elevated shell if the automatic handoff does not complete:")
        _print(f"  {_qdrant_admin_command(ctx)}")


def _qdrant_installer_env(ctx: BootstrapContext) -> dict[str, str]:
    env = os.environ.copy()
    env["GOODQ_CONDA_ENV"] = ENV_NAME
    env["CONDA_EXE"] = str(ctx.conda_exe)
    try:
        qdrant_storage, log_dir = resolve_qdrant_runtime_paths(ctx.conda_exe, ctx.repo_root)
        env["QDRANT_STORAGE_PATH"] = qdrant_storage
        env["GOODQ_LOG_DIR"] = log_dir
    except Exception as exc:  # noqa: BLE001
        _print(f"[WARN] Unable to pre-resolve Qdrant runtime paths for installer handoff: {exc}")
    return env


def _run_qdrant_service_installer(installer: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return _run(
        ["cmd.exe", "/c", str(installer), "--non-interactive"],
        env=env,
        heartbeat_label="Qdrant service install",
        heartbeat_artifacts=(installer,),
    )


def _run_qdrant_service_installer_elevated(installer: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    installer_path = _quote_ps(str(installer))
    qdrant_storage = _quote_ps(env.get("QDRANT_STORAGE_PATH", ""))
    log_dir = _quote_ps(env.get("GOODQ_LOG_DIR", ""))
    conda_exe = _quote_ps(env.get("CONDA_EXE", ""))
    conda_env = _quote_ps(env.get("GOODQ_CONDA_ENV", ENV_NAME))
    cmd_script = (
        f"set \"CONDA_EXE={conda_exe}\" && "
        f"set \"GOODQ_CONDA_ENV={conda_env}\" && "
        f"set \"QDRANT_STORAGE_PATH={qdrant_storage}\" && "
        f"set \"GOODQ_LOG_DIR={log_dir}\" && "
        f"call \"{installer_path}\" --non-interactive"
    )
    ps_script = (
        f"$p = Start-Process -FilePath 'cmd.exe' "
        f"-ArgumentList '/c','{cmd_script}' "
        f"-WorkingDirectory '{_quote_ps(str(installer.parent))}' "
        "-Verb RunAs -Wait -PassThru; "
        "exit $p.ExitCode"
    )
    return _run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        env=env,
        heartbeat_label="Qdrant admin handoff",
        heartbeat_artifacts=(installer,),
    )


def _wait_for_qdrant(url: str, timeout_sec: int = 20) -> tuple[bool, str]:
    deadline = time.time() + max(timeout_sec, 1)
    last_detail = "not checked"
    while time.time() < deadline:
        ok, detail = check_qdrant(url)
        if ok:
            return True, detail
        last_detail = detail
        time.sleep(1)
    return False, last_detail


def ensure_qdrant_ready(ctx: BootstrapContext, *, assume_yes: bool) -> bool:
    qdrant_url = resolve_qdrant_url(ctx.conda_exe, ctx.repo_root)
    qdrant_ok, qdrant_detail = check_qdrant(qdrant_url)
    service_info = inspect_windows_service(QDRANT_SERVICE_NAME)
    elevated = _is_admin()
    lifecycle_state = _qdrant_lifecycle_state(qdrant_ok, service_info)
    if qdrant_ok:
        _print(f"[OK] qdrant: {qdrant_detail}")
        _print_qdrant_handoff(ctx, state=lifecycle_state, elevated=elevated, qdrant_url=qdrant_url)
        return True

    qdrant_exe = ctx.repo_root / "vendor" / "qdrant" / "qdrant.exe"
    qdrant_cfg = ctx.repo_root / "vendor" / "qdrant" / "config.yaml"

    _print(f"[WARN] qdrant: {qdrant_detail}")
    _print_qdrant_handoff(ctx, state=lifecycle_state, elevated=elevated, qdrant_url=qdrant_url)
    if service_info.get("exists") == "true":
        status = service_info.get("status", "unknown")
        start_mode = service_info.get("start_mode", "unknown")
        _print(f"[INFO] Qdrant service status: {status} (start mode: {start_mode})")
    else:
        _print("[INFO] Qdrant service status: not installed")
    _print(f"[INFO] Repo Qdrant binary: {'present' if qdrant_exe.exists() else 'missing'} at {qdrant_exe}")
    _print(f"[INFO] Repo Qdrant config: {'present' if qdrant_cfg.exists() else 'missing'} at {qdrant_cfg}")

    if not (ctx.qdrant_service_installer.exists() and qdrant_exe.exists() and qdrant_cfg.exists()):
        _print(_qdrant_repair_instruction(ctx))
        return False

    if not prompt_bool("Attempt to install or repair the Windows Qdrant service now", True, assume_yes):
        _print(_qdrant_repair_instruction(ctx))
        return False

    installer_env = _qdrant_installer_env(ctx)
    if elevated:
        completed = _run_qdrant_service_installer(ctx.qdrant_service_installer, installer_env)
    else:
        _print("[INFO] Elevation handoff starting now for the Windows Qdrant service installer.")
        completed = _run_qdrant_service_installer_elevated(ctx.qdrant_service_installer, installer_env)

    if completed.returncode != 0:
        detail = _completed_output(completed) or "Qdrant service installer exited non-zero"
        if not elevated:
            detail = f"{detail}. Accept the UAC prompt or run the installer manually as Administrator."
        _print(f"[WARN] Qdrant service installer did not complete successfully: {detail}")
        _print(_qdrant_repair_instruction(ctx))
        return False

    qdrant_ok, qdrant_detail = _wait_for_qdrant(qdrant_url)
    if qdrant_ok:
        _print(f"[OK] qdrant: {qdrant_detail}")
        _print_qdrant_handoff(ctx, state="QDRANT_RUNNING", elevated=elevated, qdrant_url=qdrant_url)
        return True

    service_info = inspect_windows_service(QDRANT_SERVICE_NAME)
    lifecycle_state = _qdrant_lifecycle_state(qdrant_ok, service_info)
    _print(f"[WARN] qdrant still unavailable after installer run: {qdrant_detail}")
    _print_qdrant_handoff(ctx, state=lifecycle_state, elevated=elevated, qdrant_url=qdrant_url)
    _print(_qdrant_repair_instruction(ctx))
    return False


def run_bootstrap_verify(conda_exe: Path, repo_root: Path) -> tuple[bool, str]:
    completed = _run(
        [str(conda_exe), "run", "-n", ENV_NAME, "python", str(repo_root / "scripts" / "bootstrap_verify.py"), "--json"],
        cwd=repo_root,
        env=_isolated_process_env(),
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip() or "bootstrap_verify failed"
        return False, detail
    payload_text = (completed.stdout or "").strip()
    if payload_text:
        try:
            report = json.loads(payload_text)
            overall = str(report.get("overall") or "pass").lower()
            if overall == "warn":
                return True, "bootstrap_verify overall=warn"
            if overall == "fail":
                return False, "bootstrap_verify overall=fail"
        except json.JSONDecodeError:
            pass
    return True, "bootstrap_verify overall=pass"


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

    assume_defaults = args.yes or args.inspect_only or args.verify_only
    default_data_root = str(args.data_root or DEFAULT_DATA_ROOT)
    chosen_data_root = _effective_data_root(Path(prompt_text("GoodQ data directory", default_data_root, assume_defaults)))
    enable_gpu = args.enable_gpu if args.enable_gpu is not None else prompt_bool(
        "Enable GPU acceleration", False, assume_defaults
    )
    enable_wsl_audio = args.enable_wsl_audio if args.enable_wsl_audio is not None else prompt_bool(
        "Enable WSL audio acceleration", wsl_available, assume_defaults
    )
    install_step_envs = prompt_bool(
        "Install the supported step environment pack for full pipeline capability",
        True,
        assume_defaults,
    )
    prefetch_models = args.prefetch_models if args.prefetch_models is not None else prompt_bool(
        "Prefetch required model cache for offline-ready ingest",
        True,
        assume_defaults,
    )

    if enable_gpu and not gpu_available:
        _print("[WARN] GPU acceleration requested, but no NVIDIA GPU was detected. Falling back to BASELINE.")
        enable_gpu = False
    if enable_wsl_audio and not wsl_available:
        _print("[WARN] WSL audio acceleration requested, but WSL2 is not installed yet. Bootstrap will stage the required handoff.")

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
        qdrant_service_installer=repo_root / "scripts" / "qdrant" / "INSTALL_QDRANT_SERVICE.bat",
        qdrant_start_bat=repo_root / "scripts" / "qdrant" / "START_QDRANT.bat",
        data_root=chosen_data_root,
        enable_gpu=enable_gpu,
        enable_wsl_audio=enable_wsl_audio,
        wsl_distro=args.wsl_distro or detected_distro or DEFAULT_WSL_DISTRO,
        profile=profile,
        install_step_envs=install_step_envs,
        prefetch_models=prefetch_models,
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
    _print(f"install_step_envs: {ctx.install_step_envs}")
    _print(f"prefetch_models  : {ctx.prefetch_models}")
    _print(f"environment_spec : {ctx.environment_yml.name}")
    _print(f"data_root        : {ctx.data_root}")
    _print("step_env_pack    : " + ", ".join(spec.name for spec in SUPPORTED_STEP_ENVS))
    if not disk_ok:
        _print(f"[WARN] Recommended free space is at least {MIN_FREE_SPACE_GB} GB.")


def prepare_local_files(ctx: BootstrapContext) -> None:
    ensure_directory(ctx.data_root)
    write_env_local(ctx.repo_root / ".env.local", ctx.env_local_template, ctx)
    write_config_local(ctx.repo_root / "configs" / "config.local.yaml", ctx)


def verify_runtime(ctx: BootstrapContext, *, qdrant_ready: Optional[bool] = None) -> int:
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

    ffmpeg_ok, ffmpeg_detail = resolve_ffmpeg()
    if ffmpeg_ok:
        _print(f"[OK] ffmpeg: {ffmpeg_detail}")
    else:
        _print(f"[WARN] ffmpeg: {ffmpeg_detail}")
        _print(_ffmpeg_instruction_block())

    qdrant_url = resolve_qdrant_url(ctx.conda_exe, ctx.repo_root)
    qdrant_ok, qdrant_detail = check_qdrant(qdrant_url)
    if qdrant_ready is not None and qdrant_ready:
        qdrant_ok = True
        qdrant_detail = f"reachable at {qdrant_url}"
    level = "OK" if qdrant_ok else "WARN"
    _print(f"[{level}] qdrant: {qdrant_detail}")
    if not qdrant_ok:
        service_info = inspect_windows_service(QDRANT_SERVICE_NAME)
        if service_info.get("exists") == "true":
            _print(
                f"[INFO] Qdrant service status: {service_info.get('status', 'unknown')} "
                f"(start mode: {service_info.get('start_mode', 'unknown')})"
            )
        else:
            _print("[INFO] Qdrant service status: not installed")
        if ctx.qdrant_service_installer.exists():
            _print(
                "[INFO] Preferred Qdrant path: install or repair the Windows service via: "
                f"{ctx.qdrant_service_installer}"
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
    parser.add_argument("--prefetch-models", dest="prefetch_models", action="store_true", help="download required model cache during bootstrap")
    parser.add_argument("--skip-model-prefetch", dest="prefetch_models", action="store_false", help="skip model cache downloads during bootstrap")
    parser.add_argument("--yes", action="store_true", help="accept defaults without prompting")
    parser.add_argument("--inspect-only", action="store_true", help="inspect capabilities and exit without changes")
    parser.add_argument("--verify-only", action="store_true", help="run lightweight verification only")
    parser.add_argument("--no-launch", action="store_true", help="skip launching LAUNCH_GOODQ.bat")
    parser.set_defaults(enable_gpu=None, enable_wsl_audio=None, prefetch_models=None)
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

    wsl_ready = True
    if not args.verify_only:
        try:
            ensure_conda_env(ctx.conda_exe, ctx.repo_root, ctx.environment_yml, assume_yes=args.yes)
            ensure_supported_step_envs(ctx, assume_yes=args.yes)
            prepare_local_files(ctx)
            ensure_model_cache(ctx)
            wsl_ready = ensure_wsl_audio_ready(ctx, assume_yes=args.yes)
            prepare_local_files(ctx)
        except Exception as exc:  # noqa: BLE001
            return _fail(f"Bootstrap preparation failed: {exc}")

    qdrant_ready = True
    if not args.verify_only:
        ensure_ffmpeg_ready(assume_yes=args.yes)
        qdrant_ready = ensure_qdrant_ready(ctx, assume_yes=args.yes)

    verify_exit = verify_runtime(ctx, qdrant_ready=qdrant_ready)
    if verify_exit != 0:
        return verify_exit

    if not args.verify_only and ctx.enable_wsl_audio and not wsl_ready:
        return _fail(
            "Bootstrap core setup completed, but the WSL audio extension is still pending. "
            "Complete the staged WSL install step shown above, launch the distro once, and rerun bootstrap."
        )

    if not args.verify_only and not qdrant_ready:
        return _fail(
            "Bootstrap core setup completed, but Qdrant service provisioning is still incomplete. "
            "Accept the elevation prompt or run INSTALL_QDRANT_SERVICE.bat as Administrator, "
            "then rerun the bootstrap or launch step."
        )

    if args.no_launch or args.verify_only:
        _print("[OK] Bootstrap complete. Launch skipped by flag.")
        return 0

    return launch_goodq(ctx)


if __name__ == "__main__":
    raise SystemExit(main())
