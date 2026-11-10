"""One launch and text-transport policy for isolated Python workers.

This module prepares values only. Callers retain scheduling, process ownership,
resource admission, retries and persistence. No parent environment is modified.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import shutil
from typing import Any, Mapping


log = logging.getLogger(__name__)


class WorkerResultError(RuntimeError):
    """A rejected structured result remains available as failure evidence."""

    def __init__(self, message: str, *, step_name: str | None = None, outputs: dict | None = None):
        super().__init__(message)
        self.step_name = step_name
        self.outputs = outputs

SUBPROCESS_THREAD_CAP_STEPS = {"tagger", "sentiment", "emotion_classify"}
SUBPROCESS_THREAD_CAP_ENV = {
    "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
    "NUMEXPR_MAX_THREADS": "1", "TOKENIZERS_PARALLELISM": "false",
}
# CTranslate2 initializes OpenMP during DLL load. These defaults prevent its
# topology probe from deadlocking in non-interactive Windows worker sessions.
SUBPROCESS_AUDIO_OPENMP_GUARD_STEPS = {"audio_embed_clap", "audio_transcribe_local"}
SUBPROCESS_AUDIO_OPENMP_GUARD_ENV = {
    "KMP_DUPLICATE_LIB_OK": "TRUE", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
}


@dataclass(frozen=True)
class WorkerRequest:
    env_name: str
    step_name: str
    input_path: Path
    output_path: Path
    config_path: Path


@dataclass(frozen=True)
class WorkerLaunch:
    command: list[str]
    environment: dict[str, str]
    kind: str
    direct_python: str | None


def apply_env_overrides(
    environment: Mapping[str, str], overrides: Mapping[str, str | None] | None,
) -> dict[str, str]:
    result = dict(environment)
    for key, value in (overrides or {}).items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = value
    return result


def python_worker_environment(environment: Mapping[str, str]) -> dict[str, str]:
    """Bind both the child writer and any intermediate Conda Python process."""
    return {**environment, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def worker_payload(value: Any) -> Any:
    """Preserve the existing worker input conversion, including CLI defaults."""
    if hasattr(value, "default"):
        return worker_payload(value.default)
    if isinstance(value, dict):
        return {key: worker_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [worker_payload(item) for item in value]
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    return str(value)


def prepare_worker_launch(
    request: WorkerRequest,
    environment: Mapping[str, str],
    *,
    repo_root: Path,
    conda_exe: str,
    prefer_direct: bool,
    prefer_available_python: bool,
    overrides: Mapping[str, str | None] | None = None,
) -> WorkerLaunch:
    from configs.python_paths import get_env_python

    conda_available = (os.path.exists(conda_exe) if os.path.isabs(conda_exe)
                       else shutil.which(conda_exe) is not None)
    try:
        resolved = get_env_python(request.env_name)
    except Exception as exc:
        log.warning("Worker interpreter resolution failed env=%s error=%s", request.env_name, exc)
        resolved = None
    direct_python = str(resolved) if resolved and Path(resolved).exists() else None
    required = {
        "goodq_object_detect": "Selected object detection runtime envs/object_detect/.venv is unavailable",
        "goodq_caption_vlm": "Selected caption runtime envs/caption_vlm/.venv is unavailable",
    }
    if direct_python is None:
        if request.step_name == "image_ocr":
            raise RuntimeError("Selected OCR environment goodq_ocr is unavailable")
        if request.env_name in required:
            raise RuntimeError(required[request.env_name])

    direct = (prefer_direct or request.step_name == "image_ocr" or request.env_name in required
              or (prefer_available_python and direct_python is not None)
              or (not conda_available and direct_python is not None))
    arguments = [str(repo_root / "cli" / "step_runner.py"), "--step", request.step_name,
                 "--in", str(request.input_path), "--out", str(request.output_path),
                 "--cfg", str(request.config_path)]
    if direct:
        if not direct_python:
            raise RuntimeError(f"Direct interpreter fallback unavailable for env={request.env_name} step={request.step_name}")
        command = [direct_python, *arguments]
        kind = "direct_env_python"
    elif conda_available:
        command = [conda_exe, "run", "-n", request.env_name, "--no-capture-output", "python", *arguments]
        kind = "conda_run"
    else:
        raise RuntimeError("Conda unavailable for step execution "
                           f"(step={request.step_name}, env={request.env_name}, conda_exe={conda_exe}). "
                           "Bare interpreter fallback is disabled.")

    child_env = dict(environment)
    child_env["CONDA_PREFIX_1"] = child_env.get("CONDA_PREFIX", "")
    parent_dir = str(repo_root.parent)
    existing = child_env.get("PYTHONPATH", "")
    if parent_dir not in existing.split(os.pathsep):
        child_env["PYTHONPATH"] = os.pathsep.join(filter(None, (parent_dir, existing)))
    for selected, defaults in (
        (SUBPROCESS_THREAD_CAP_STEPS, SUBPROCESS_THREAD_CAP_ENV),
        (SUBPROCESS_AUDIO_OPENMP_GUARD_STEPS, SUBPROCESS_AUDIO_OPENMP_GUARD_ENV),
    ):
        if request.step_name in selected:
            for key, value in defaults.items():
                child_env.setdefault(key, value)
    if kind == "direct_env_python":
        executable = Path(direct_python)
        env_root = executable.parent.parent if executable.parent.name.lower() == "bin" else executable.parent
        env_bin = executable.parent if executable.parent.name.lower() == "bin" else env_root / "Scripts"
        child_env.update(CONDA_DEFAULT_ENV=request.env_name, CONDA_PREFIX=str(env_root))
        entries = [str(env_root)]
        if env_bin.exists():
            entries.append(str(env_bin))
        if child_env.get("PATH"):
            entries.append(child_env["PATH"])
        child_env["PATH"] = os.pathsep.join(entries)
    # CPU/native retry overrides apply before the mandatory transport contract.
    child_env = python_worker_environment(apply_env_overrides(child_env, overrides))
    return WorkerLaunch(command, child_env, kind, direct_python)


def decode_worker_stdout(value: bytes | str | None, *, step_name: str, env_name: str) -> str:
    """Decode after communicate(), so decoding errors stay on the caller thread."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value  # Already decoded transports/test doubles retain their contract.
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"Worker {step_name} ({env_name}) stdout is not valid UTF-8 at byte {exc.start}") from exc


def decode_worker_diagnostics(value: bytes | str | None) -> str:
    """Native diagnostic bytes stay visible as escapes; they are never result JSON."""
    if value is None:
        return ""
    return value if isinstance(value, str) else value.decode("utf-8", errors="backslashreplace")


def parse_worker_result_json(
    raw: str,
    *,
    step_name: str,
    env_name: str,
    source: str,
) -> dict[str, Any]:
    payload = raw.strip()
    if not payload:
        raise RuntimeError(f"Step {step_name} returned empty output from {source} ({env_name})")
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        preview = payload.splitlines()[0][:200]
        raise RuntimeError(
            f"Step {step_name} returned invalid JSON from {source} ({env_name}): "
            f"{exc.msg} at line {exc.lineno} column {exc.colno}; preview={preview!r}"
        ) from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(
            f"Step {step_name} returned non-object JSON from {source} ({env_name})"
        )
    return parsed

def read_worker_result(
    output_path: Path, stdout: bytes | str | None, *, step_name: str, env_name: str,
) -> dict[str, Any]:
    """A successful worker's result file takes precedence over diagnostic stdout."""
    if output_path.exists():
        source = "output.json"
        try:
            raw = output_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError(
                f"Worker {step_name} ({env_name}) output.json is not valid UTF-8 at byte {exc.start}"
            ) from exc
    else:
        source = "stdout"
        raw = decode_worker_stdout(stdout, step_name=step_name, env_name=env_name)
    return parse_worker_result_json(raw, step_name=step_name, env_name=env_name, source=source)
