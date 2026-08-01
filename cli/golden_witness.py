"""Read-only preflight authority for isolated Golden Witness runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Mapping
from uuid import uuid4

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


def prepare_witness_run(artifact_root: Path, input_path: Path) -> dict[str, Any]:
    """Build a contained execution receipt without creating or running anything."""
    root = Path(artifact_root).resolve()
    preflight = preflight_witness(root, input_path)
    run_id = f"r24-{uuid4().hex}"
    epoch_id = f"epoch_witness_{run_id}"
    mutable_paths = {
        "workspace": str(root / "workspace"),
        "output": str(root / "output"),
        "processing": str(root / "processing"),
        "config_snapshot": str(root / "config" / "witness-config.json"),
        "receipt": str(root / "prepared-receipt.json"),
    }
    return {
        "status": "prepared",
        "run_id": run_id,
        "epoch_id": epoch_id,
        "artifact_root": str(root),
        "input": preflight["input"],
        "preflight": preflight,
        "mutable_paths": mutable_paths,
        "runner": {"module": "cli.run_ingestion"},
        "promotion_enabled": False,
        "ingestion_isolation": True,
    }


def _isolated_runtime_snapshot(prepared_receipt: Mapping[str, Any], root: Path) -> dict[str, Any]:
    preflight = prepared_receipt.get("preflight")
    config = preflight.get("config") if isinstance(preflight, Mapping) else None
    paths = config.get("paths") if isinstance(config, Mapping) else None
    models_cache = paths.get("models_cache") if isinstance(paths, Mapping) else None
    if not isinstance(models_cache, str) or not models_cache:
        raise WitnessAuthorityError("prepared receipt has no external model cache")

    epoch_id = prepared_receipt.get("epoch_id")
    if not isinstance(epoch_id, str) or not epoch_id:
        raise WitnessAuthorityError("prepared receipt has no witness epoch identifier")
    data_root = root / "data"
    epoch_root = data_root / "epochs" / epoch_id
    faiss_root = epoch_root / "faiss"
    return {
        "ingestion_isolation": True,
        "witness": {
            "ingestion_isolation": True,
            "promotion_enabled": False,
            "artifact_root": str(root),
            "allow_sqlite_embeddings": True,
            "allow_turboquant_active_retrieval": True,
        },
        "paths": {
            "data_root": str(data_root),
            "db_dir": str(epoch_root),
            "db_path": str(epoch_root / "memory.db"),
            "knowledge_graph_db": str(epoch_root / "knowledge_graph.db"),
            "processing": str(epoch_root / "processing"),
            "log_dir": str(epoch_root / "logs"),
            "output_directory": str(epoch_root / "output"),
            "faiss_dir": str(faiss_root),
            "faiss_audio_path": str(faiss_root / "audio.index"),
            "faiss_index_path": str(faiss_root / "text.index"),
            "faiss_clip_path": str(faiss_root / "clip.index"),
            "faiss_dino_path": str(faiss_root / "dino.index"),
            "clip_id_map_db": str(faiss_root / "clip-id-map.sqlite"),
            "dino_id_map_db": str(faiss_root / "dino-id-map.sqlite"),
            "clap_id_map_db": str(faiss_root / "clap-id-map.sqlite"),
            "qdrant_storage": str(data_root / "qdrant"),
            "watchdog_state_file": str(epoch_root / "logs" / "watchdog_state.json"),
            "watchdog_lock_file": str(epoch_root / "logs" / "watchdog.lock"),
            "import_inbox": str(data_root / "import_inbox"),
            "ingest_requests": str(data_root / "ingest_requests"),
            "processed": str(data_root / "processed"),
            "failed": str(data_root / "failed"),
            "models_cache": models_cache,
        },
        "memory": {
            "routing": {
                "quantization_enabled": True,
                "quantization_shadow_mode": False,
            },
        },
        "qdrant": {
            "host": "http://127.0.0.1:6333",
            "collections": {
                "clip": f"goodq_clip_{epoch_id}",
                "dino": f"goodq_dino_{epoch_id}",
                "text": f"goodq_text_{epoch_id}",
                "audio": f"goodq_audio_{epoch_id}",
            },
        },
    }
def seal_prepared_receipt(prepared_receipt: Mapping[str, Any]) -> Path:
    """Persist one verified receipt below a fresh root without executing it."""
    if prepared_receipt.get("status") != "prepared":
        raise WitnessAuthorityError("only a prepared witness receipt can be sealed")
    artifact_root = prepared_receipt.get("artifact_root")
    if not isinstance(artifact_root, str) or not artifact_root:
        raise WitnessAuthorityError("prepared receipt has no artifact root")
    root = Path(artifact_root).resolve()
    if root.exists():
        raise WitnessAuthorityError("witness root must be fresh and absent before sealing")

    mutable_paths = prepared_receipt.get("mutable_paths")
    if not isinstance(mutable_paths, Mapping):
        raise WitnessAuthorityError("prepared receipt has no mutable path inventory")
    for role, value in mutable_paths.items():
        if not isinstance(value, str) or not value:
            raise WitnessAuthorityError(f"mutable path {role!r} is invalid")
        if not _is_within(Path(value).resolve(), root):
            raise WitnessAuthorityError(f"mutable path {role!r} escapes the witness root")

    receipt_path = root / "prepared-receipt.json"
    if mutable_paths.get("receipt") != str(receipt_path):
        raise WitnessAuthorityError("prepared receipt path does not match the witness root")

    runtime_config_path = root / "config" / "witness-config.json"
    runtime_config = _isolated_runtime_snapshot(prepared_receipt, root)
    sealed = json.loads(json.dumps(dict(prepared_receipt)))
    sealed["status"] = "sealed"
    sealed["runtime_config_path"] = str(runtime_config_path)
    root.mkdir(parents=True)
    runtime_config_path.parent.mkdir()
    runtime_config_path.write_text(
        json.dumps(runtime_config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    receipt_path.write_text(
        json.dumps(sealed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt_path
