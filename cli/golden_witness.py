"""Read-only preflight authority for isolated Golden Witness runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

from steps.common.model_provisioner import resolve_models_root
from steps.common.tool_resolver import ToolResolver


class WitnessAuthorityError(RuntimeError):
    """Raised when a proposed witness cannot prove its isolation boundary."""


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _ffprobe_path() -> Path:
    ffmpeg = ToolResolver.resolve_tool("ffmpeg")
    if not ffmpeg["found"] or not ffmpeg["path"]:
        raise WitnessAuthorityError("ffmpeg is unavailable for witness preflight")

    ffmpeg_path = Path(str(ffmpeg["path"]))
    sibling = ffmpeg_path.with_name("ffprobe.exe" if ffmpeg_path.suffix.lower() == ".exe" else "ffprobe")
    resolved = sibling if sibling.is_file() else shutil.which("ffprobe")
    if not resolved:
        raise WitnessAuthorityError("ffprobe is unavailable for witness preflight")
    return Path(resolved)


def _probe_stream_metadata(input_path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            str(_ffprobe_path()),
            "-v",
            "error",
            "-show_entries",
            "format=format_name,duration:stream=codec_type,codec_name,width,height",
            "-of",
            "json",
            str(input_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "unknown ffprobe failure"
        raise WitnessAuthorityError(f"ffprobe could not inspect witness input: {detail}")
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise WitnessAuthorityError("ffprobe returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise WitnessAuthorityError("ffprobe returned an invalid metadata document")
    return parsed


def _device_policy() -> dict[str, Any]:
    try:
        import torch

        cuda_available = bool(torch.cuda.is_available())
        return {
            "cuda_available": cuda_available,
            "selected_device": "cuda" if cuda_available else "cpu",
        }
    except Exception as exc:
        return {"cuda_available": False, "selected_device": "cpu", "probe_error": type(exc).__name__}


def build_witness_config(artifact_root: Path, input_path: Path) -> dict[str, Any]:
    """Project a witness-only configuration without creating mutable paths."""
    root = Path(artifact_root).resolve()
    models_root = resolve_models_root().resolve()
    if _is_within(models_root, root):
        raise WitnessAuthorityError("model cache resolved inside witness root")
    return {
        "ingestion_isolation": True,
        "promotion_enabled": False,
        "paths": {
            "artifact_root": str(root),
            "input_path": str(Path(input_path).resolve()),
            "models_cache": str(models_root),
        },
    }


def preflight_witness(artifact_root: Path, input_path: Path) -> dict[str, Any]:
    """Return read-only witness facts; this function never creates a run root."""
    source = Path(input_path).resolve()
    if not source.is_file():
        raise WitnessAuthorityError("witness input is not a regular file")
    config = build_witness_config(artifact_root, source)
    tools = {
        "ffmpeg": ToolResolver.resolve_tool("ffmpeg"),
        "tesseract": ToolResolver.resolve_tool("tesseract"),
    }
    return {
        "status": "ready",
        "input": {
            "path": str(source),
            "sha256": _sha256_file(source),
            "stream_metadata": _probe_stream_metadata(source),
        },
        "config": config,
        "tools": tools,
        "device_policy": _device_policy(),
    }
