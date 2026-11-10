"""Read-only planning and one-use store admission for isolated Golden Witness runs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Mapping
from urllib.parse import urlparse
from uuid import uuid4

from steps.common.model_provisioner import resolve_models_root
from steps.common.tool_resolver import ToolResolver


class WitnessAuthorityError(RuntimeError):
    """Raised when a proposed witness cannot prove its isolation boundary."""


_WITNESS_STORE_FILES = (
    "db_path", "knowledge_graph_db", "faiss_audio_path", "faiss_index_path",
    "faiss_clip_path", "faiss_dino_path", "clip_id_map_db", "dino_id_map_db",
    "clap_id_map_db",
)


def _witness_store_paths(cfg: Mapping[str, Any], root: Path) -> dict[str, Path]:
    paths = cfg.get("paths") or {}
    targets = {}
    for key in _WITNESS_STORE_FILES:
        value = paths.get(key)
        if not isinstance(value, str) or not value.strip():
            raise WitnessAuthorityError(f"witness store path is missing: {key}")
        targets[key] = Path(value)
    targets["ucf_ledger"] = Path(paths["db_dir"]) / "ucf" / "ucf_ledger.db"
    for key, original in targets.items():
        path = original.resolve()
        if not _is_within(path, root):
            raise WitnessAuthorityError(f"witness store path escapes root: {key}")
        for suffix in ("", "-wal", "-shm", "-journal"):
            if os.path.lexists(str(original) + suffix) or os.path.lexists(str(path) + suffix):
                raise WitnessAuthorityError(f"witness store is not fresh: {key}{suffix}")
    # Logs, config and import-created directories are permitted. Prior scene or
    # result artifacts are not evidence for a newly admitted ingestion.
    for key in ("processing", "output_directory", "faiss_dir"):
        directory = Path(paths[key]).resolve()
        if not _is_within(directory, root):
            raise WitnessAuthorityError(f"witness artifact path escapes root: {key}")
        if directory.exists() and any(item.is_file() or item.is_symlink() for item in directory.rglob("*")):
            raise WitnessAuthorityError(f"witness artifacts are not fresh: {key}")
    return {key: path.resolve() for key, path in targets.items()}


def _witness_shared_exceptions(cfg: Mapping[str, Any], root: Path) -> dict[str, Any]:
    models = Path(cfg["paths"]["models_cache"]).resolve()
    if not models.is_dir() or _is_within(models, root) or _is_within(root, models):
        raise WitnessAuthorityError("shared model cache must exist and not overlap witness root")
    allocator = sys.modules.get("common.vram_allocator")
    repo_processing = Path(__file__).resolve().parents[1] / "processing"
    fallback = Path(os.environ.get("ProgramData", "C:\\ProgramData")) / "GoodQ4All" / "processing"
    vram = {
        "purpose": "shared singleton GPU reservation and lock coordination",
        "resolution": "loaded" if allocator is not None else "unverified_until_allocator_load",
        "registry_path": str(allocator.REGISTRY_PATH) if allocator is not None else None,
        "lock_path": str(allocator.LOCK_PATH) if allocator is not None else None,
        "configured_candidates": [str(repo_processing), str(fallback)],
    }
    return {"models_cache": {"path": str(models), "purpose": "reuse existing shared model assets"},
            "vram_coordination": vram}


def _initialize_witness_collection(cfg: dict[str, Any], key: str, dim: int) -> None:
    from steps.common.qdrant_client import build_qdrant_client

    client = build_qdrant_client(cfg, dim, key)
    if client is None:
        raise WitnessAuthorityError("witness Qdrant initialization is disabled")
    original_get, original_put = client.session.get, client.session.put

    def require_absent(url, **kwargs):
        response = original_get(url, **kwargs, allow_redirects=False)
        if response.status_code != 404:
            raise WitnessAuthorityError("witness collection changed after absence check")
        return response

    def create_without_redirect(url, **kwargs):
        return original_put(url, **kwargs, allow_redirects=False)

    # The existing initializer otherwise accepts existing collections and creates
    # after any non-200 GET. A witness must never adopt that behavior silently.
    client.session.get = require_absent
    client.session.put = create_without_redirect
    try:
        if not client.ensure_collection():
            raise WitnessAuthorityError(f"witness collection initialization failed: {key}")
    finally:
        client.session.close()


def admit_witness_run(cfg: dict[str, Any], snapshot_path: Path) -> dict[str, Any]:
    """Claim a fresh run once, then initialize and verify only its four stores.

    Configuration/CLI containment must already have passed in the runner. A
    partial initialization leaves its admission marker and collections intact;
    retries require a new sealed witness, never silent reuse or cleanup.
    """
    from steps.common.atomic_io import atomic_write_json
    from steps.common.qdrant_client import build_qdrant_session

    witness = cfg.get("witness") or {}
    if (cfg.get("ingestion_isolation") is not True or
            witness.get("ingestion_isolation") is not True or witness.get("promotion_enabled") is not False):
        raise WitnessAuthorityError("witness admission requires non-promoting isolation")
    root = Path(witness["artifact_root"]).resolve()
    snapshot = Path(snapshot_path).resolve()
    if not root.is_dir() or not _is_within(snapshot, root):
        raise WitnessAuthorityError("witness snapshot must belong to the sealed root")
    if not snapshot.is_file():
        raise WitnessAuthorityError("witness snapshot must be an existing file")
    snapshot_sha256 = _sha256_file(snapshot)
    marker = root / "witness-admission.json"
    if os.path.lexists(marker):
        raise WitnessAuthorityError("witness already admitted; use a fresh run")
    stores = _witness_store_paths(cfg, root)
    shared = _witness_shared_exceptions(cfg, root)
    qcfg = cfg.get("qdrant") or {}
    host = qcfg.get("host", "")
    try:
        parsed = urlparse(host)
        port = parsed.port
    except ValueError as exc:
        raise WitnessAuthorityError("witness admission requires an explicit valid loopback Qdrant port") from exc
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}
            or port is None or not 1 <= port <= 65535 or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise WitnessAuthorityError("witness admission requires plain loopback Qdrant with an explicit valid port")
    collections = qcfg.get("collections") or {}
    expected = {key: f"goodq_{key}_{cfg['epoch_id']}" for key in ("clip", "dino", "text", "audio")}
    dims = qcfg.get("embedding_dims") or {}
    if collections != expected or qcfg.get("enabled") is not True:
        raise WitnessAuthorityError("witness admission requires four exact enabled epoch collections")
    if any(type(dims.get(key)) is not int or dims[key] <= 0 for key in expected):
        raise WitnessAuthorityError("witness admission requires explicit positive collection dimensions")
    host = host.rstrip("/")
    initializer_cfg = {**cfg, "qdrant": {**qcfg, "host": host}}
    with build_qdrant_session(host) as session:
        for key, name in expected.items():
            try:
                response = session.get(f"{host}/collections/{name}", timeout=3, allow_redirects=False)
            except Exception as exc:
                raise WitnessAuthorityError(f"witness collection absence unverified: {key}") from exc
            if response.status_code != 404:
                raise WitnessAuthorityError(f"witness collection is existing or unverified: {key}")
        # Recheck paths after network I/O, then reserve this run exclusively.
        _witness_store_paths(cfg, root)
        receipt = {
            "status": "initializing", "epoch_id": cfg["epoch_id"],
            "snapshot_path": str(snapshot),
            "snapshot_sha256": snapshot_sha256,
            "resolved_config_sha256": hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest(),
            "stores_absent": {key: str(path) for key, path in stores.items()},
            "collections_absent": expected, "collections_verified": {},
            "shared_exceptions": shared,
        }
        try:
            with marker.open("x", encoding="utf-8") as handle:
                json.dump(receipt, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError as exc:
            raise WitnessAuthorityError("witness already admitted; use a fresh run") from exc
        try:
            for key, name in expected.items():
                _initialize_witness_collection(initializer_cfg, key, dims[key])
                response = session.get(f"{host}/collections/{name}", timeout=3, allow_redirects=False)
                if response.status_code != 200:
                    raise WitnessAuthorityError(f"witness collection verification failed: {key}")
                result = response.json().get("result", {})
                vectors = result.get("config", {}).get("params", {}).get("vectors", {})
                if (type(result.get("points_count")) is not int or result["points_count"] != 0
                        or type(vectors.get("size")) is not int or vectors["size"] != dims[key]
                        or vectors.get("distance") != "Cosine"):
                    raise WitnessAuthorityError(f"witness collection is not empty with required schema: {key}")
                receipt["collections_verified"][key] = {"name": name, "points_count": 0,
                                                          "size": dims[key], "distance": "Cosine"}
            _witness_store_paths(cfg, root)
            receipt["status"] = "admitted"
        except Exception as exc:
            receipt["status"] = "failed"
            receipt["failure_type"] = type(exc).__name__
            atomic_write_json(marker, receipt)
            raise WitnessAuthorityError("witness collection initialization/verification failed; preserve partial run") from exc
        atomic_write_json(marker, receipt)
    return receipt


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


def _resolve_witness_profile(install_root: Path | None = None) -> str:
    """Resolve the installed profile so isolated evidence matches its runtime."""
    root = (install_root or Path(__file__).resolve().parents[1]).resolve()
    profile_path = root / "configs" / "installer_profile.txt"
    if profile_path.is_file():
        value = profile_path.read_text(encoding="utf-8").strip().upper()
        if value in {"PUBLIC_CPU_BASELINE", "PUBLIC_GPU_ENHANCED", "PERSONAL_AIR_GAP"}:
            return value
        raise WitnessAuthorityError(f"installed profile is invalid: {value or 'empty'}")
    value = os.getenv("GOODQ_HOST_PROFILE", "").strip().upper()
    if value in {"GPU_ENHANCED", "PUBLIC_GPU_ENHANCED"}:
        return "PUBLIC_GPU_ENHANCED"
    if value == "PERSONAL_AIR_GAP":
        return value
    return "PUBLIC_CPU_BASELINE"


def build_witness_config(artifact_root: Path, input_path: Path) -> dict[str, Any]:
    """Project a witness-only configuration without creating mutable paths."""
    root = Path(artifact_root).resolve()
    models_root = resolve_models_root().resolve()
    profile = _resolve_witness_profile()
    if _is_within(models_root, root):
        raise WitnessAuthorityError("model cache resolved inside witness root")
    return {
        "ingestion_isolation": True,
        "promotion_enabled": False,
        "host": {
            "profile": profile,
            "require_gpu": profile != "PUBLIC_CPU_BASELINE",
        },
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
        "epoch_id": epoch_id,
        "host": {**dict(config.get("host") or {}), "data_root": str(data_root)},
        "witness": {
            "ingestion_isolation": True,
            "promotion_enabled": False,
            "artifact_root": str(root),
            "allow_sqlite_embeddings": True,
            "allow_turboquant_active_retrieval": False,
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
            "reports_dir": str(root / "reports"),
            "csv_path": str(epoch_root / "logs" / "system_metrics.csv"),
            "nas_path": str(data_root / "archive"),
        },
        "identity_search": {
            "roster_path": str(root / "identity" / "family_roster.yaml"),
            "kg_db_path": str(epoch_root / "knowledge_graph.db"),
        },
        "memory": {
            "routing": {
                "quantization_enabled": False,
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
        "phase6": {
            "clip_collection": f"goodq_clip_{epoch_id}",
            "dino_collection": f"goodq_dino_{epoch_id}",
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
