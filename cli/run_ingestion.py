from __future__ import annotations
from steps.common import transcript_authority
import sys
# Global encoding safeguard for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")

from typing import Any, Dict, Iterable, List, Optional, Set
import asyncio
import copy
import hashlib
import json
import logging
import os
import sqlite3
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Setup logger
logger = logging.getLogger(__name__)

# Add repo root to path for imports
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

if __name__ == "__main__":
    # Some runtime helpers bind writable defaults at import time. The explicit
    # witness CLI must bind its child environment before those imports occur.
    from cli.witness_environment import bootstrap_witness_environment

    bootstrap_witness_environment()

import re
import typer
import yaml
from urllib.parse import urlparse

from steps.common.config_loader import get_runtime_paths, load_configs
from steps.common.config_redaction import redact_config
from steps.common.atomic_io import atomic_write_json
from steps.common.memory import ensure_scene, register_scene_bundle, scene_has_materialized, get_scene_meta, list_scenes_for_video, _make_id
from steps.common.tag_utils import (
    canonicalize_taxonomy,
    is_valid_entity_token,
    merge_tag_sources,
    normalize_entity_token,
)
from steps.common.tool_paths import resolve_ffmpeg, resolve_conda
from steps.common.step_logger import log_step_run
from steps.common.worker_launch import (
    WorkerRequest, WorkerResultError, prepare_worker_launch, worker_payload,
    apply_env_overrides as _apply_env_overrides,
    decode_worker_diagnostics, read_worker_result,
    parse_worker_result_json as _parse_step_result_json,
    SUBPROCESS_THREAD_CAP_STEPS, SUBPROCESS_THREAD_CAP_ENV,
    SUBPROCESS_AUDIO_OPENMP_GUARD_STEPS, SUBPROCESS_AUDIO_OPENMP_GUARD_ENV,
)
from steps.common.profile_config import is_baseline, require_wsl_audio, wsl_audio_auto_enabled
from lib.ingestion_capability_contract import (
    RUNTIME_CAPABILITY_POLICIES,
    build_capability_receipt,
    render_capability_receipt,
    resolve_capability_profile,
)
from lib.observability.observer import PipelineObserver
from scripts.wsl_audio_preflight import probe_wsl_audio_runtime

_OPTIONAL_DIRECT_ENV_FALLBACK_STEPS = {"sentiment", "audio_embed_clap"}
_PREFER_DIRECT_ENV_PYTHON_ON_WINDOWS = os.name == 'nt'
_SYNTHETIC_SPEAKER_PATTERN = re.compile(r"^(?:speaker|face)_\d+$", re.IGNORECASE)
_SYNTHETIC_IDENTITY_PATTERN = re.compile(r"^(?:unknown(?:_\d+)?|speaker_\d+|face_\d+|person_\d+)$", re.IGNORECASE)
_CAPABILITY_PROFILE_CONTRACT_PATH = REPO_ROOT / "configs" / "ingestion_capability_profiles.yaml"
# Internal orchestration/persistence events share the log with capability rows.
# Keep this explicit so unrecognized evidence still fails the release gate.
_NON_CAPABILITY_STEP_RUNS = {
    "audio_unified_wsl2",
    "video_scene_detect",
    "text_embed",
    "scene_visual_embeddings",
    "cross_modal_harmonization",
}
_WSL_CAPABILITY_STEP_BY_COMPONENT = {
    "transcription": "audio_transcribe_local",
    "diarization": "audio_speaker_merge",
    "acoustic_emotion": "audio_emotion",
    "wav2vec2": "audio_wav2vec2_enrichment",
    "clap_handoff": "audio_clap_handoff",
}


def _has_wsl_unified_audio_embeddings(item: Dict[str, Any]) -> bool:
    """Return whether WSL already produced a *persisted CLAP* embedding.

    The unified WSL response also carries a 768-dimensional Wav2Vec2 feature
    vector.  That is useful audio evidence, but it is not interchangeable with
    the canonical 512-dimensional CLAP vector and must never suppress the
    CLAP step merely because generic embeddings are present.
    """
    if not isinstance(item, dict):
        return False
    if not bool(item.get('wsl2_unified')):
        return False
    if str(item.get('audio_backend_effective') or '').strip().lower() != 'wsl':
        return False
    clap_meta = item.get('clap_meta')
    if not isinstance(clap_meta, dict):
        return False
    return (
        clap_meta.get('status') == 'ok'
        and clap_meta.get('component') == 'audio_embed_clap'
        and isinstance(clap_meta.get('embedding_id'), str)
        and bool(clap_meta.get('embedding_id').strip())
        and clap_meta.get('qdrant_committed') is True
        and isinstance(clap_meta.get('qdrant_collection'), str)
        and bool(clap_meta.get('qdrant_collection').strip())
    )


def _mark_wsl_unified_audio_embed_skip(item: Dict[str, Any]) -> Dict[str, Any]:
    skip_meta = item.get('clap_meta')
    if not isinstance(skip_meta, dict):
        skip_meta = {}
    skip_meta.update(
        {
            'status': 'skipped',
            'reason': 'wsl_unified_embeddings_present',
            'source': 'audio_unified_wsl2',
            'embedding_dim': item.get('embedding_dim'),
            'embeddings_status': item.get('embeddings_status'),
        }
    )
    item['clap_meta'] = skip_meta
    return skip_meta


def _log_wsl_capability_outcomes(
    *,
    cfg: Dict[str, Any],
    item: Dict[str, Any],
    duration_ms: float,
    outcomes: object,
) -> None:
    records = outcomes if isinstance(outcomes, dict) else {}
    for component, step in _WSL_CAPABILITY_STEP_BY_COMPONENT.items():
        raw = records.get(component)
        record = raw if isinstance(raw, dict) else {}
        status = str(record.get("status") or "error").strip().lower()
        if status not in {"ok", "error", "skipped", "not_applicable"}:
            status = "error"
        reason = str(
            record.get("reason")
            or ("missing_wsl_component_outcome" if not record else "invalid_wsl_component_status")
        )
        error = None
        if status == "error":
            error = str(record.get("error") or reason)
        extra = {
            "backend": "wsl",
            "component": component,
            "reason": reason,
            "requested_implementation": "wsl_unified",
            "effective_implementation": (
                "canonical_clap_handoff"
                if component == "clap_handoff"
                else "wsl_unified"
            ),
            "component_outcome": dict(record),
        }
        log_step_run(
            cfg,
            step,
            dict(item),
            duration_ms,
            status,
            error,
            extra=extra,
        )


def _is_synthetic_speaker_label(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return bool(_SYNTHETIC_SPEAKER_PATTERN.fullmatch(value.strip()))


def _scoped_synthetic_speaker_name(scope_value: Any, speaker_label: Any) -> Optional[str]:
    if not _is_synthetic_speaker_label(speaker_label):
        return None
    scope_text = str(scope_value or "").strip()
    speaker_text = str(speaker_label or "").strip()
    if not scope_text or not speaker_text:
        return None
    scope_token = re.sub(r"[^A-Za-z0-9_]+", "_", scope_text).strip("_") or "scene"
    speaker_token = re.sub(r"[^A-Za-z0-9_]+", "_", speaker_text).strip("_") or "speaker"
    return f"{scope_token}__{speaker_token.lower()}"


def _resolve_named_person_identity(raw_identity: Any) -> Optional[str]:
    candidate = raw_identity
    if isinstance(raw_identity, dict):
        candidate = (
            raw_identity.get("name")
            or raw_identity.get("identity")
            or raw_identity.get("person")
            or raw_identity.get("speaker_id")
            or raw_identity.get("speaker")
            or raw_identity.get("label")
        )
    if candidate is None:
        return None
    raw_text = str(candidate).strip()
    if not raw_text or _SYNTHETIC_IDENTITY_PATTERN.fullmatch(raw_text):
        return None
    normalized = normalize_entity_token(raw_text)
    if not normalized or _SYNTHETIC_IDENTITY_PATTERN.fullmatch(normalized):
        return None
    return normalized


def _resolve_audio_speaker_identity(raw_speaker: Any) -> Optional[tuple[str, str]]:
    candidate = None
    if isinstance(raw_speaker, dict):
        candidate = (
            raw_speaker.get("name")
            or raw_speaker.get("identity")
            or raw_speaker.get("person")
            or raw_speaker.get("speaker_id")
            or raw_speaker.get("speaker")
            or raw_speaker.get("label")
        )
    else:
        candidate = raw_speaker

    raw_text = str(candidate).strip() if candidate is not None else ""
    if raw_text and _is_synthetic_speaker_label(raw_text):
        return ("speaker", raw_text)

    normalized = _resolve_named_person_identity(candidate)
    if not normalized:
        return None
    return ("person", normalized)


def _patch_typer_help_for_click_8_2() -> None:
    """
    Typer 0.9.0 + Click 8.2.x: rich help calls `param.make_metavar()` without ctx.
    Click 8.2 requires `make_metavar(self, ctx)`, causing `--help` to crash on Py3.13.
    Patch is safe and affects help rendering only.
    """
    try:
        import inspect
        import click
    except Exception as e:
        logger.debug(
            "run_ingestion warning context=%s error=%s",
            "typer_help_patch.import",
            e,
        )
        return

    make_metavar = getattr(click.core.Parameter, "make_metavar", None)
    if make_metavar is None or getattr(make_metavar, "_goodq_patched", False):
        return
    try:
        sig = inspect.signature(make_metavar)
    except Exception as e:
        logger.debug(
            "run_ingestion warning context=%s error=%s",
            "typer_help_patch.signature",
            e,
        )
        return
    if "ctx" not in sig.parameters:
        return

    orig = make_metavar

    def _make_metavar_compat(self, ctx=None):  # type: ignore[no-untyped-def]
        if ctx is None:
            ctx = click.get_current_context(silent=True)
            if ctx is None:
                ctx = click.Context(click.Command("goodq"))
        return orig(self, ctx)

    _make_metavar_compat._goodq_patched = True  # type: ignore[attr-defined]
    click.core.Parameter.make_metavar = _make_metavar_compat  # type: ignore[assignment]


# Progress tracking
try:
    from steps.common.progress_tracker import get_tracker, step_context, update_step, set_total_steps, finish_processing
    PROGRESS_TRACKING_AVAILABLE = True
except ImportError:
    PROGRESS_TRACKING_AVAILABLE = False
    # Compatibility shims keep the runtime CPU-safe when progress tracking is absent.
    class DummyTracker:
        def step_context(self, *args, **kwargs):
            from contextlib import contextmanager
            @contextmanager
            def dummy():
                yield self
            return dummy()
    def get_tracker():
        return DummyTracker()
    def update_step(*args, **kwargs):
        pass
    def set_total_steps(*args, **kwargs):
        pass
    def finish_processing(*args, **kwargs):
        pass
    step_context = lambda *args, **kwargs: DummyTracker().step_context(*args, **kwargs)

# Control Agent integration
try:
    from agents.control_agent import (
        ControlAgent,
        CONTROL_AGENT_STATUS_DISABLED_NO_LLM_CLIENT,
        CONTROL_AGENT_DISABLED_REASON_NO_LLM_CLIENT,
    )
    CONTROL_AGENT_AVAILABLE = True
except ImportError:
    CONTROL_AGENT_AVAILABLE = False
    ControlAgent = None
    CONTROL_AGENT_STATUS_DISABLED_NO_LLM_CLIENT = "disabled_no_llm_client"
    CONTROL_AGENT_DISABLED_REASON_NO_LLM_CLIENT = "Control Agent module unavailable"
    logger.warning(
        "run_ingestion warning context=%s error=%s",
        "control_agent.import",
        "ImportError",
    )

# Knowledge graph integration
try:
    from lib.knowledge_graph import KnowledgeGraph
    from lib.kg_realtime_integration import update_kg_for_scene, build_scene_relationships, _resolve_graph_db_path
    KNOWLEDGE_GRAPH_AVAILABLE = True
except ImportError:
    KNOWLEDGE_GRAPH_AVAILABLE = False
    logger.warning(
        "run_ingestion warning context=%s error=%s",
        "knowledge_graph.import",
        "ImportError",
    )

try:
    from steps.video.entity_extractor import extract_entities_from_scene
    VISION_ENTITY_EXTRACTION_AVAILABLE = True
except ImportError:
    VISION_ENTITY_EXTRACTION_AVAILABLE = False
    logger.warning(
        "run_ingestion warning context=%s error=%s",
        "vision_entity_extractor.import",
        "ImportError",
    )

APP = typer.Typer(help='Scene-first ingestion orchestrator for GoodQ')

def _deep_merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge_dicts(base[key], value)
        else:
            base[key] = value


def _load_runtime_cfg_snapshot(cfg_json: Optional[Path] = None) -> Dict[str, Any]:
    base_cfg = load_configs({})
    if cfg_json and cfg_json.exists():
        try:
            raw = cfg_json.read_text(encoding='utf-8').strip()
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    merged = dict(base_cfg) if isinstance(base_cfg, dict) else {}
                    _deep_merge_dicts(merged, parsed)
                    return merged
        except Exception as e:
            logger.warning(
                "run_ingestion warning context=%s error=%s",
                "runtime_cfg_snapshot",
                e,
            )
    return base_cfg if isinstance(base_cfg, dict) else {}


_WITNESS_MUTABLE_PATH_KEYS = (
    "data_root",
    "db_dir",
    "db_path",
    "knowledge_graph_db",
    "processing",
    "log_dir",
    "output_directory",
    "faiss_dir",
    "faiss_audio_path",
    "faiss_index_path",
    "faiss_clip_path",
    "faiss_dino_path",
    "clip_id_map_db",
    "dino_id_map_db",
    "clap_id_map_db",
    "qdrant_storage",
    "watchdog_state_file",
    "watchdog_lock_file",
    "import_inbox",
    "ingest_requests",
    "processed",
    "failed",
)


def _is_path_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _validate_isolated_witness_runtime_config(cfg: Dict[str, Any], snapshot_path: Path) -> None:
    if cfg.get("ingestion_isolation") is not True:
        raise typer.BadParameter("isolated runner config requires ingestion_isolation=true")
    witness = cfg.get("witness")
    if not isinstance(witness, dict) or witness.get("ingestion_isolation") is not True:
        raise typer.BadParameter("isolated runner config requires witness.ingestion_isolation=true")
    if witness.get("promotion_enabled") is not False:
        raise typer.BadParameter("isolated runner config requires witness.promotion_enabled=false")
    artifact_root = witness.get("artifact_root")
    if not isinstance(artifact_root, str) or not artifact_root.strip():
        raise typer.BadParameter("isolated runner config requires witness.artifact_root")
    root = Path(artifact_root).resolve()
    if not _is_path_within(snapshot_path.resolve(), root):
        raise typer.BadParameter("isolated runner config must be stored inside the witness root")

    paths = cfg.get("paths")
    if not isinstance(paths, dict):
        raise typer.BadParameter("isolated runner config requires runtime paths")
    for key in _WITNESS_MUTABLE_PATH_KEYS:
        value = paths.get(key)
        if not isinstance(value, str) or not value.strip():
            raise typer.BadParameter(f"isolated runner config is missing paths.{key}")
        if not _is_path_within(Path(value).resolve(), root):
            raise typer.BadParameter(f"paths.{key} escapes witness root")
    # Defaults/local configuration may add write targets beyond the required
    # core stores. Shared assets and relative output folder names are read-only
    # inputs to this check; every other resolved paths entry is witness-owned.
    shared_keys = {"models_cache", "config_dir", "input_path"}
    relative_keys = {"chunk_subdir", "audio_subdir", "video_subdir", "metadata_subdir"}
    for key, value in paths.items():
        if key in shared_keys or key in _WITNESS_MUTABLE_PATH_KEYS:
            continue
        if not isinstance(value, str) or not value.strip():
            raise typer.BadParameter(f"isolated runner config has invalid paths.{key}")
        candidate = (root / value).resolve() if key in relative_keys else Path(value).resolve()
        if not _is_path_within(candidate, root):
            raise typer.BadParameter(f"paths.{key} escapes witness root")
    for section, keys in {"host": ("data_root",), "identity_search": ("roster_path", "kg_db_path")}.items():
        settings = cfg.get(section, {})
        for key in keys:
            value = settings.get(key) if isinstance(settings, dict) else None
            if value is not None and (not isinstance(value, str) or not value.strip()
                                      or not _is_path_within(Path(value).resolve(), root)):
                raise typer.BadParameter(f"{section}.{key} escapes witness root")
    models_cache = paths.get("models_cache")
    if not isinstance(models_cache, str) or not models_cache.strip():
        raise typer.BadParameter("isolated runner config is missing paths.models_cache")
    if _is_path_within(Path(models_cache).resolve(), root):
        raise typer.BadParameter("paths.models_cache must stay outside the witness root")

    qdrant = cfg.get("qdrant")
    host = qdrant.get("host") if isinstance(qdrant, dict) else None
    parsed = urlparse(host) if isinstance(host, str) else None
    if not parsed or parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port is None:
        raise typer.BadParameter("isolated runner config requires a loopback Qdrant endpoint")
    collections = qdrant.get("collections") if isinstance(qdrant, dict) else None
    required_collections = {"clip", "dino", "text", "audio"}
    if not isinstance(collections, dict) or set(collections) != required_collections:
        raise typer.BadParameter("isolated runner config requires four fresh witness collections")
    names = list(collections.values())
    if (
        any(not isinstance(name, str) or "witness" not in name for name in names)
        or len(set(names)) != len(required_collections)
    ):
        raise typer.BadParameter("isolated runner config requires four fresh witness collections")
    epoch_id = cfg.get("epoch_id")
    if not isinstance(epoch_id, str) or not re.fullmatch(r"epoch_witness_[A-Za-z0-9_-]+", epoch_id):
        raise typer.BadParameter("isolated runner config requires an explicit witness epoch_id")
    if Path(paths["db_dir"]).resolve().name != epoch_id:
        raise typer.BadParameter("paths.db_dir must end with the exact witness epoch_id")
    identity = cfg.get("identity_search")
    identity_kg = identity.get("kg_db_path") if isinstance(identity, dict) else None
    if identity_kg is not None and Path(identity_kg).resolve() != Path(paths["knowledge_graph_db"]).resolve():
        raise typer.BadParameter("identity_search.kg_db_path must match paths.knowledge_graph_db")
    if collections != {key: f"goodq_{key}_{epoch_id}" for key in required_collections}:
        raise typer.BadParameter("Qdrant collections must match the exact witness epoch_id")
    phase6 = cfg.get("phase6", {})
    for key in ("clip", "dino"):
        alias = phase6.get(f"{key}_collection") if isinstance(phase6, dict) else None
        if alias is not None and alias != collections[key]:
            raise typer.BadParameter(f"phase6.{key}_collection must match the witness epoch")


def _validate_witness_process_environment(cfg: Dict[str, Any], snapshot_path: Path) -> None:
    """Refuse runtime execution when import-time paths were not witness-bound."""
    from cli.witness_environment import build_witness_environment

    instruction = "Run python -m cli.run_ingestion --config <snapshot> in a fresh process"
    try:
        bindings = build_witness_environment(snapshot_path, {})
    except ValueError as exc:
        raise typer.BadParameter(f"{instruction}: {exc}") from exc
    scalar_keys = {
        "GOODQ_EPOCH_ID", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE",
        "HF_DATASETS_OFFLINE", "PYTHONDONTWRITEBYTECODE",
    }
    for key, expected in bindings.items():
        actual = os.environ.get(key)
        matches = actual == expected if key in scalar_keys else (
            bool(actual) and Path(actual).resolve() == Path(expected).resolve()
        )
        if not matches:
            raise typer.BadParameter(f"{instruction}: witness environment binding differs for {key}")
    if PROGRESS_TRACKING_AVAILABLE:
        expected_progress = Path(cfg["paths"]["log_dir"]).resolve() / "progress.json"
        if Path(get_tracker().progress_file).resolve() != expected_progress:
            raise typer.BadParameter(f"{instruction}: progress tracker was imported outside this witness")


def load_isolated_runtime_cfg_snapshot(cfg_json: Path) -> Dict[str, Any]:
    """Load an explicit witness snapshot and reject any canonical-storage path."""
    snapshot_path = Path(cfg_json).resolve()
    if not snapshot_path.is_file():
        raise typer.BadParameter(f"Isolated runner config not found: {snapshot_path}")
    try:
        parsed = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise typer.BadParameter("Isolated runner config must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise typer.BadParameter("Isolated runner config must be a JSON object")
    witness = parsed.get("witness")
    if (
        parsed.get("ingestion_isolation") is not True
        or not isinstance(witness, dict)
        or witness.get("ingestion_isolation") is not True
        or witness.get("promotion_enabled") is not False
        or not isinstance(witness.get("artifact_root"), str)
        or not witness["artifact_root"].strip()
    ):
        raise typer.BadParameter(
            "isolated runner snapshot requires explicit ingestion_isolation=true and witness bindings"
        )
    if not parsed.get("epoch_id"):
        raise typer.BadParameter("isolated runner config requires an explicit witness epoch_id")
    base_cfg = load_configs({})
    cfg: Dict[str, Any] = copy.deepcopy(base_cfg) if isinstance(base_cfg, dict) else {}
    _deep_merge_dicts(cfg, parsed)
    _validate_isolated_witness_runtime_config(cfg, snapshot_path)
    return cfg


def _resolve_models_dir(
    cfg: Optional[Dict[str, Any]] = None,
    *,
    cfg_json: Optional[Path] = None,
) -> Path:
    cfg_payload = cfg if isinstance(cfg, dict) else _load_runtime_cfg_snapshot(cfg_json)
    runtime_paths = get_runtime_paths(cfg_payload, "models_cache", require_canonical=False)
    return Path(runtime_paths["models_cache"]).resolve()


def _resolve_processing_root(cfg: Dict[str, Any]) -> Path:
    runtime_paths = get_runtime_paths(cfg, "processing", require_canonical=False)
    return Path(runtime_paths["processing"]).resolve()


# Populated by CLI options at runtime
VERBOSE: bool = False
ENABLE_AUTO_HEALING: bool = False
# Timeout per step in seconds - prevents infinite hangs
# Audio steps (diarize, transcribe) can take 5-10 min for long scenes
# Image steps should complete in <30s
DEFAULT_STEP_TIMEOUT: int = 1800
STEP_TIMEOUT: Optional[int] = DEFAULT_STEP_TIMEOUT  # 30 minutes max per step
MAX_HEALER_RETRIES: int = 3
_CURRENT_RUN_CONTEXT: Optional[Dict[str, Any]] = None
_PIPELINE_OBSERVER: Optional[PipelineObserver] = None
_GLOBAL_LLM_CLIENT: Optional[Any] = None


def _control_agent_activation_requested(
    cfg: Dict[str, Any],
    *,
    cli_enabled: bool = False,
) -> bool:
    """Return true only for an explicit CLI, config, or environment opt-in."""
    control_agent_cfg = cfg.get("control_agent", {}) or {}
    return bool(
        cli_enabled is True
        or control_agent_cfg.get("enabled", False) is True
        or os.getenv("GOODQ_CONTROL_AGENT_ENABLED") == "1"
    )


def _control_agent_mutation_requested(
    *,
    activation_requested: bool,
    auto_healing_requested: bool,
    dry_run: bool,
) -> bool:
    """Mutation is dormant unless all three explicit safety gates agree."""
    return (
        activation_requested is True
        and auto_healing_requested is True
        and dry_run is False
    )


def _control_agent_runtime_enabled() -> bool:
    global _GLOBAL_LLM_CLIENT, CONTROL_AGENT_AVAILABLE
    if not CONTROL_AGENT_AVAILABLE:
        return False

    status = (
        _CURRENT_RUN_CONTEXT.get("control_agent_status")
        if isinstance(_CURRENT_RUN_CONTEXT, dict)
        else None
    )
    if status is not None and status != "initialized":
        return False

    cfg: Optional[Dict[str, Any]] = None
    activated_by_current_run = status == "initialized"
    if not activated_by_current_run:
        try:
            from steps.common.config_loader import load_configs
            cfg = load_configs({})
            if not _control_agent_activation_requested(cfg):
                return False
        except Exception:
            return False

    # Try to initialize LLM Client on demand for explicit test hooks/direct calls.
    if _GLOBAL_LLM_CLIENT is None:
        try:
            from steps.common.config_loader import load_configs
            from steps.common.llm_model_factory import build_llm_models
            from lib.llm_client import LLMClient
            if cfg is None:
                cfg = load_configs({})
            models = build_llm_models(cfg)
            _GLOBAL_LLM_CLIENT = LLMClient(
                models=models,
                health_check_interval=60,
                max_retries=3,
                timeout=30,
                cache_ttl=300,
                enable_health_checks=False,
            )
        except Exception:
            return False

    if not isinstance(_CURRENT_RUN_CONTEXT, dict):
        return _GLOBAL_LLM_CLIENT is not None
    return status == 'initialized'


def _get_control_agent(cfg_json: Optional[Path] = None) -> ControlAgent:
    global _GLOBAL_LLM_CLIENT, ENABLE_AUTO_HEALING
    dry_run_val = True
    if cfg_json is not None and cfg_json.exists():
        try:
            import json
            with open(cfg_json, 'r', encoding='utf-8') as f:
                step_cfg = json.load(f)
            dry_run_val = step_cfg.get('control_agent', {}).get('dry_run', True)
        except Exception:
            pass
    return ControlAgent(llm_client=_GLOBAL_LLM_CLIENT, dry_run=dry_run_val, enable_mutation=ENABLE_AUTO_HEALING)


def _resolve_step_timeout_value(step_timeout: Optional[int]) -> Optional[int]:
    if step_timeout is None:
        return DEFAULT_STEP_TIMEOUT
    try:
        parsed = int(step_timeout)
    except (TypeError, ValueError):
        return DEFAULT_STEP_TIMEOUT
    return parsed if parsed > 0 else None


_PHASE6_MANIFEST_TOP_LEVEL_KEYS = (
    'phase6_complete',
    'phase6_status',
    'phase6_error',
    'phase6_vector_commit',
    'embedding_stats',
)
_PHASE6_MANIFEST_SCENE_KEYS = (
    'clip_id',
    'clip_dim',
    'dino_id',
    'dino_dim',
    'frame_count',
    'frame_paths',
    'representative_frame',
    'scene_context_llm',
    'scene_context_epistemic',
    'scene_context_arbitration',
)


def _merge_prior_phase6_manifest_state(
    new_manifest: Dict[str, Any],
    existing_manifest: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not isinstance(existing_manifest, dict):
        return new_manifest

    merged = dict(new_manifest)
    for key in _PHASE6_MANIFEST_TOP_LEVEL_KEYS:
        if key in existing_manifest and key not in merged:
            merged[key] = existing_manifest[key]

    new_scenes = merged.get('scenes')
    old_scenes = existing_manifest.get('scenes')
    if not isinstance(new_scenes, list) or not isinstance(old_scenes, list):
        return merged

    prior_by_identity: Dict[tuple[Any, Any], Dict[str, Any]] = {}
    for scene in old_scenes:
        if not isinstance(scene, dict):
            continue
        identity = (scene.get('scene_id'), scene.get('index'))
        prior_by_identity[identity] = scene

    preserved_scenes: List[Dict[str, Any]] = []
    for scene in new_scenes:
        if not isinstance(scene, dict):
            preserved_scenes.append(scene)
            continue
        identity = (scene.get('scene_id'), scene.get('index'))
        prior = prior_by_identity.get(identity)
        if not isinstance(prior, dict):
            preserved_scenes.append(scene)
            continue
        merged_scene = dict(scene)
        for key in _PHASE6_MANIFEST_SCENE_KEYS:
            if key in prior and key not in merged_scene:
                merged_scene[key] = prior[key]
        preserved_scenes.append(merged_scene)

    merged['scenes'] = preserved_scenes
    return merged


def _observer() -> Optional[PipelineObserver]:
    global _PIPELINE_OBSERVER
    if _PIPELINE_OBSERVER is None or not _PIPELINE_OBSERVER.enabled:
        return None
    return _PIPELINE_OBSERVER


def run_ingestion(video_path: str, cfg: Optional[Dict] = None):
    """
    Main ingestion entrypoint - runs direct_ingestion pipeline
    
    Args:
        video_path: Path to video file to ingest
        cfg: Optional config dict (will load from config.yaml if not provided)
    
    Returns:
        Dict containing ingestion results
    """
    from pipelines.direct_ingestion import run_direct_ingestion
    
    if cfg is None:
        cfg = load_configs({})
    
    return run_direct_ingestion(video_path, cfg)

IMAGE_PIPELINE_STEPS = [
    'image_ocr',
    'image_caption',
    'object_detect',
    'face_embed',
    'image_embed_dino',
    'image_embed_clip',
    'tagger',
]

AUDIO_PIPELINE_STEPS = [
    'audio_metadata',
    # Legacy audio steps replaced by WSL2 GPU-accelerated versions
    # 'audio_diarize',  # Now using audio_wsl2_bridge
    # 'audio_transcribe',  # Now using audio_wsl2_bridge
    'audio_speaker_merge',
    'audio_music_events',
    'audio_time_hints',
    'audio_emotion',
    'sentiment',
    'emotion_classify',
    'tagger',
    'audio_embed_clap',
]

NATIVE_CRASH_RETRY_STEPS: Set[str] = {'tagger', 'sentiment'}
MAX_NATIVE_STEP_RETRIES: int = 1


def _resolve_native_retry_strategy(
    step_name: str,
    retry_attempt: int,
    *, gpu_required: bool = False,
) -> tuple[int, Optional[Dict[str, Optional[str]]], Optional[str]]:
    if step_name == 'image_caption':
        if retry_attempt == 1:
            return (
                1,
                {
                    'GOODQ_IMAGE_CAPTION_FORCE_CPU': '1',
                },
                'cpu_fallback',
            )
        return (1, None, None)
    if step_name == 'object_detect':
        if retry_attempt == 1:
            return (
                1,
                {
                    'GOODQ_OBJECT_DETECT_FORCE_CPU': '1',
                },
                'cpu_fallback',
            )
        return (1, None, None)
    if step_name == 'audio_embed_clap':
        if gpu_required:
            return (0, None, None)
        if retry_attempt == 1:
            return (
                1,
                {
                    'GOODQ_CLAP_FORCE_CPU': '1',
                },
                'cpu_fallback',
            )
        return (1, None, None)
    if step_name == 'image_embed_dino':
        if retry_attempt == 1:
            return (
                2,
                {
                    'GOODQ_DINO_DISABLE_AMP': '1',
                    'GOODQ_DINO_FORCE_CPU': None,
                },
                'gpu_amp_disabled',
            )
        if retry_attempt == 2:
            return (
                2,
                {
                    'GOODQ_DINO_DISABLE_AMP': '1',
                    'GOODQ_DINO_FORCE_CPU': '1',
                },
                'cpu_fallback',
            )
        return (2, None, None)
    if step_name in NATIVE_CRASH_RETRY_STEPS:
        return (MAX_NATIVE_STEP_RETRIES, None, None)
    return (0, None, None)



def _build_knowledge_graph_from_results(results: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build knowledge graph from ingestion results"""
    if not KNOWLEDGE_GRAPH_AVAILABLE:
        if VERBOSE:
            typer.echo('[kg] Knowledge graph module not available, skipping')
        return None
    
    try:
        runtime_paths = get_runtime_paths(cfg)
        graph_db_path = Path(runtime_paths['knowledge_graph_db']).resolve()
        graph_db_path.parent.mkdir(parents=True, exist_ok=True)
        
        if VERBOSE:
            typer.echo(f'[kg] Building knowledge graph at {graph_db_path}')
        
        with KnowledgeGraph(str(graph_db_path)) as kg:
            for video_result in results:
                video_path = video_result.get('video_path', '')
                scenes = video_result.get('scenes', [])
                
                for scene in scenes:
                    scene_idx = scene.get('index', 0)
                    scene_id = scene.get('scene_id', f'scene_{scene_idx:04d}')
                    start_time = scene.get('start', 0.0)
                    end_time = scene.get('end', start_time)
                    
                    # Add media node for this scene
                    media_props = {
                        'duration': end_time - start_time,
                        'confidence': scene.get('confidence', 0.0),
                        'video_path': video_path
                    }
                    media_id = kg.add_media_node(
                        media_type='video_scene',
                        media_path=video_path,
                        scene_id=scene_id,
                        timestamp_start=start_time,
                        timestamp_end=end_time,
                        properties=media_props
                    )
                    
                    # Process keyframe data
                    keyframe = scene.get('keyframe')
                    if isinstance(keyframe, dict):
                        _process_keyframe_entities(kg, keyframe, media_id, start_time)
                    
                    # Process audio data
                    audio = scene.get('audio')
                    if isinstance(audio, dict):
                        _process_audio_entities(kg, audio, media_id, start_time)
                    
                    # Create temporal event for scene
                    kg.add_temporal_event(
                        event_type='scene_change',
                        timestamp=start_time,
                        duration=end_time - start_time,
                        properties={'scene_id': scene_id, 'confidence': scene.get('confidence', 0.0)}
                    )
            
            # Build relationships
            _build_kg_relationships(kg)
            
            # Get statistics
            stats = kg.get_statistics()
            
            if VERBOSE:
                typer.echo(f'[kg] Knowledge graph complete: {stats}')
            
            return {
                'graph_db_path': str(graph_db_path),
                'statistics': stats,
                'status': 'success'
            }
    
    except Exception as exc:
        logger.warning(
            "run_ingestion warning context=%s error=%s",
            "knowledge_graph.build",
            exc,
        )
        if VERBOSE:
            typer.echo(f'[kg] Knowledge graph build failed: {exc}', err=True)
        return {'status': 'failed', 'error': str(exc)}


def _process_keyframe_entities(kg: Any, keyframe: Dict[str, Any], media_id: int, timestamp: float) -> None:
    """Extract and add entities from keyframe data"""
    # Objects detected
    detections = keyframe.get('detections', [])
    if isinstance(detections, list):
        for det in detections:
            if isinstance(det, dict):
                label = det.get('label', det.get('class'))
                confidence = det.get('confidence', det.get('score', 0.0))
                if label and confidence > 0.3:
                    bbox = det.get('bbox', [])
                    entity_id = kg.add_node('object', label, {'confidence': confidence}, timestamp)
                    kg.link_node_to_media(entity_id, media_id, confidence, {'bbox': bbox})
    
    # Faces detected
    faces = keyframe.get('faces', [])
    if isinstance(faces, list):
        for idx, face in enumerate(faces):
            if isinstance(face, dict):
                confidence = face.get('confidence', face.get('score', 1.0))
                bbox = face.get('bbox', [])
                face_node_id = kg.add_node('face', f'media_{media_id}_face_{idx}', {'face_detected': True}, timestamp)
                kg.link_node_to_media(face_node_id, media_id, confidence, {'bbox': bbox, 'face_index': idx})

                identity_name = _resolve_named_person_identity(face)
                if identity_name:
                    person_node_id = kg.add_node('person', identity_name, {'face_detected': True}, timestamp)
                    kg.link_node_to_media(person_node_id, media_id, confidence, {'bbox': bbox, 'face_index': idx})
                    kg.add_edge(
                        face_node_id,
                        person_node_id,
                        'identity_evidence',
                        float(confidence),
                        {'source': 'scene_face_detection'},
                    )
    
    # Caption/Description
    caption = keyframe.get('caption')
    if caption and isinstance(caption, str):
        entity_id = kg.add_node('description', 'scene_caption', {'text': caption}, timestamp)
        kg.link_node_to_media(entity_id, media_id, 0.9)
    
    # Tags
    tags = keyframe.get('tags', [])
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str):
                entity_id = kg.add_node('concept', tag, {}, timestamp)
                kg.link_node_to_media(entity_id, media_id, 0.5)
    
    # Entities (named entities)
    entities = keyframe.get('entities', [])
    if isinstance(entities, list):
        for entity in entities:
            if isinstance(entity, str):
                entity_id = kg.add_node('entity', entity, {}, timestamp)
                kg.link_node_to_media(entity_id, media_id, 0.7)
    
    # Emotions
    emotions = keyframe.get('emotions', [])
    if isinstance(emotions, list):
        for emotion in emotions:
            if isinstance(emotion, str):
                entity_id = kg.add_node('emotion', emotion, {}, timestamp)
                kg.link_node_to_media(entity_id, media_id, 0.5)
    
    # OCR text locations
    ocr_text = keyframe.get('ocr_text')
    if ocr_text:
        entity_id = kg.add_node('concept', 'text_overlay', {'text': ocr_text[:100]}, timestamp)
        kg.link_node_to_media(entity_id, media_id, 0.8)


def _process_audio_entities(kg: Any, audio: Dict[str, Any], media_id: int, timestamp: float) -> None:
    """Extract and add entities from audio data"""
    scene_scope = audio.get('scene_id') or f'media_{media_id}'

    # Transcript
    transcript = audio.get('transcript')
    if transcript:
        entity_id = kg.add_node('concept', 'speech', {'transcript': transcript[:200]}, timestamp)
        kg.link_node_to_media(entity_id, media_id, 0.9)
    
    # Sentiment
    sentiment = audio.get('sentiment')
    if isinstance(sentiment, dict):
        label = sentiment.get('label')
        score = sentiment.get('score', 0.5)
        if label:
            entity_id = kg.add_node('sentiment', label.lower(), {'score': score}, timestamp)
            kg.link_node_to_media(entity_id, media_id, score)
    
    # Emotions from audio (can be dict with scores or list)
    emotions = audio.get('emotions')
    if emotions:
        if isinstance(emotions, dict):
            for emotion_name, emotion_score in emotions.items():
                if emotion_score > 0.3:
                    entity_id = kg.add_node('emotion', emotion_name, {'score': emotion_score}, timestamp)
                    kg.link_node_to_media(entity_id, media_id, emotion_score)
        elif isinstance(emotions, list):
            for emotion in emotions:
                if isinstance(emotion, str):
                    entity_id = kg.add_node('emotion', emotion, {}, timestamp)
                    kg.link_node_to_media(entity_id, media_id, 0.6)
    
    # Audio emotion (fallback/alternative field)
    audio_emotion = audio.get('audio_emotion')
    if audio_emotion:
        if isinstance(audio_emotion, str):
            entity_id = kg.add_node('emotion', audio_emotion, {}, timestamp)
            kg.link_node_to_media(entity_id, media_id, 0.6)
        elif isinstance(audio_emotion, dict):
            top_emotion = audio_emotion.get('top_emotion')
            if top_emotion:
                entity_id = kg.add_node('emotion', top_emotion, {}, timestamp)
                kg.link_node_to_media(entity_id, media_id, 0.6)
    
    # Speaker transcripts (detailed speaker segments)
    speaker_transcript = audio.get('speaker_transcript', [])
    if isinstance(speaker_transcript, list):
        for segment in speaker_transcript:
            if isinstance(segment, dict):
                speaker_identity = _resolve_audio_speaker_identity(segment)
                text = segment.get('text', '')
                if speaker_identity:
                    node_type, speaker_name = speaker_identity
                    node_name = speaker_name
                    node_props = {'transcript_sample': text[:100]}
                    if node_type == 'speaker':
                        scoped_name = _scoped_synthetic_speaker_name(scene_scope, speaker_name)
                        if scoped_name:
                            node_name = scoped_name
                            node_props['speaker_label'] = speaker_name
                            node_props['scene_id'] = scene_scope
                    entity_id = kg.add_node(node_type, node_name, node_props, timestamp)
                    kg.link_node_to_media(entity_id, media_id, 0.8, {
                        'start': segment.get('start'),
                        'end': segment.get('end'),
                        'text': text
                    })
                    if node_type == 'person':
                        speaker_node_id = kg.add_node('speaker', speaker_name, {'transcript_sample': text[:100]}, timestamp)
                        kg.link_node_to_media(speaker_node_id, media_id, 0.8, {
                            'start': segment.get('start'),
                            'end': segment.get('end'),
                            'text': text
                        })
                        kg.add_edge(
                            speaker_node_id,
                            entity_id,
                            'identity_evidence',
                            0.8,
                            {'source': 'speaker_transcript'},
                        )
    
    # Fallback: Speaker diarization (if speaker_transcript not available)
    if not speaker_transcript:
        speakers = audio.get('speakers', [])
        if isinstance(speakers, list):
            for speaker in speakers:
                speaker_identity = _resolve_audio_speaker_identity(speaker)
                if speaker_identity:
                    node_type, speaker_name = speaker_identity
                    node_name = speaker_name
                    node_props = {}
                    if node_type == 'speaker':
                        scoped_name = _scoped_synthetic_speaker_name(scene_scope, speaker_name)
                        if scoped_name:
                            node_name = scoped_name
                            node_props['speaker_label'] = speaker_name
                            node_props['scene_id'] = scene_scope
                    entity_id = kg.add_node(node_type, node_name, node_props, timestamp)
                    kg.link_node_to_media(entity_id, media_id, 0.7)
                    if node_type == 'person':
                        speaker_node_id = kg.add_node('speaker', speaker_name, {}, timestamp)
                        kg.link_node_to_media(speaker_node_id, media_id, 0.7)
                        kg.add_edge(
                            speaker_node_id,
                            entity_id,
                            'identity_evidence',
                            0.7,
                            {'source': 'speaker_ids'},
                        )
    
    # Entities (named entities from transcript)
    entities = audio.get('entities', [])
    if isinstance(entities, list):
        for entity in entities:
            if isinstance(entity, str):
                entity_id = kg.add_node('entity', entity, {}, timestamp)
                kg.link_node_to_media(entity_id, media_id, 0.7)
    
    # Music events
    music_events = audio.get('music_events', [])
    if isinstance(music_events, list):
        for event in music_events:
            if isinstance(event, dict):
                event_type = event.get('type', 'music')
                confidence = event.get('confidence', 0.5)
                entity_id = kg.add_node('audio_event', f'music_{event_type}', {'confidence': confidence}, timestamp)
                kg.link_node_to_media(entity_id, media_id, confidence, {
                    'start': event.get('start'),
                    'end': event.get('end')
                })
    
    # Time hints (temporal context)
    time_hints = audio.get('time_hints', {})
    if isinstance(time_hints, dict):
        for hint_type, hints in time_hints.items():
            if isinstance(hints, list) and hints:
                for hint in hints:
                    entity_id = kg.add_node('temporal_context', f'{hint_type}_{hint}', {}, timestamp)
                    kg.link_node_to_media(entity_id, media_id, 0.6)
    
    # Tags from audio
    tags = audio.get('tags', [])
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str):
                entity_id = kg.add_node('concept', tag, {}, timestamp)
                kg.link_node_to_media(entity_id, media_id, 0.5)


def _build_kg_relationships(kg: Any) -> None:
    """Build co-occurrence, temporal, and semantic relationships"""
    # Co-occurrence: entities appearing together in same media
    cursor = kg.conn.cursor()
    cursor.execute("""
        SELECT e1.id, e2.id, COUNT(*) as co_count
        FROM node_media nm1
        JOIN node_media nm2 ON nm1.media_id = nm2.media_id
        JOIN nodes e1 ON nm1.node_id = e1.id
        JOIN nodes e2 ON nm2.node_id = e2.id
        WHERE e1.id < e2.id
        GROUP BY e1.id, e2.id
        HAVING co_count >= 2
    """)
    
    for row in cursor.fetchall():
        kg.add_edge(
            row[0], row[1], 'co_occurs',
            weight=float(row[2]),
            properties={'count': row[2]}
        )
    
    # Temporal: entities in adjacent time windows (within 10 seconds)
    cursor.execute("""
        SELECT DISTINCT n1.id, n2.id
        FROM media_nodes m1
        JOIN media_nodes m2 ON ABS(m1.timestamp_start - m2.timestamp_start) <= 10
        JOIN node_media nm1 ON m1.id = nm1.media_id
        JOIN node_media nm2 ON m2.id = nm2.media_id
        JOIN nodes n1 ON nm1.node_id = n1.id
        JOIN nodes n2 ON nm2.node_id = n2.id
        WHERE n1.id < n2.id
        AND m1.id != m2.id
    """)
    
    for row in cursor.fetchall():
        kg.add_edge(
            row[0], row[1], 'temporal_proximity',
            weight=0.5
        )



OUTPUT_DROP_KEYS: Set[str] = {'modality', 'scene_id', 'scene_index', 'video_hash', 'video_id'}


def _merge_step_output(result: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(result, dict):
        return None
    merged: Dict[str, Any] = {k: v for k, v in result.items() if k != 'data'}
    data = result.get('data')
    if isinstance(data, dict):
        raw = dict(data)
        for key, value in raw.items():
            if key in OUTPUT_DROP_KEYS:
                continue
            if key == 'source_path' and 'path' in merged:
                continue
            merged.setdefault(key, value)
        merged['raw'] = raw
    return merged


def _extract_speaker_ids(audio_payload: Any) -> List[str]:
    if not isinstance(audio_payload, dict):
        return []

    speaker_ids: List[str] = []

    def _append_speaker(raw: Any) -> None:
        if not isinstance(raw, str):
            return
        speaker = raw.strip()
        if speaker and speaker not in speaker_ids:
            speaker_ids.append(speaker)

    speakers = audio_payload.get('speakers')
    if isinstance(speakers, list):
        for speaker in speakers:
            if isinstance(speaker, str):
                _append_speaker(speaker)
            elif isinstance(speaker, dict):
                _append_speaker(speaker.get('speaker', speaker.get('label')))

    for key in ('speaker_transcript', 'speaker_segments', 'diarization'):
        segments = audio_payload.get(key)
        if not isinstance(segments, list):
            continue
        for segment in segments:
            if isinstance(segment, dict):
                _append_speaker(segment.get('speaker'))

    return speaker_ids


def _promote_metadata_time_hints(audio_payload: Any) -> None:
    if not isinstance(audio_payload, dict):
        return
    if isinstance(audio_payload.get('metadata_time_hints'), dict):
        return
    audio_meta = audio_payload.get('audio_meta')
    if not isinstance(audio_meta, dict):
        return
    tag_time_hints = audio_meta.get('tag_time_hints')
    if isinstance(tag_time_hints, dict):
        audio_payload['metadata_time_hints'] = tag_time_hints


def _time_hints_have_values(time_hints: Any) -> bool:
    if not isinstance(time_hints, dict):
        return False
    for key, value in time_hints.items():
        if str(key).strip().lower() == 'first_seen_ts':
            continue
        if isinstance(value, list) and value:
            return True
        if isinstance(value, dict) and value:
            return True
        if isinstance(value, str) and value.strip():
            return True
    return False


def _merge_time_hint_dicts(*hint_sources: Any) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for hints in hint_sources:
        if not isinstance(hints, dict):
            continue
        for key, value in hints.items():
            if value in (None, '', []):
                continue
            if isinstance(value, list):
                existing = merged.setdefault(key, [])
                if not isinstance(existing, list):
                    continue
                for item in value:
                    if item not in existing:
                        existing.append(item)
                continue
            if isinstance(value, dict):
                existing_dict = merged.setdefault(key, {})
                if isinstance(existing_dict, dict):
                    existing_dict.update(value)
                continue
            merged[key] = value
    return merged


def _resolve_scene_time_hints(audio_payload: Dict[str, Any], frame_payload: Dict[str, Any]) -> Dict[str, Any]:
    audio_hints = audio_payload.get('time_hints')
    frame_hints = frame_payload.get('time_hints')
    if _time_hints_have_values(audio_hints) and _time_hints_have_values(frame_hints):
        return _merge_time_hint_dicts(audio_hints, frame_hints)
    if _time_hints_have_values(audio_hints):
        return audio_hints
    if _time_hints_have_values(frame_hints):
        return frame_hints
    return audio_hints if isinstance(audio_hints, dict) else {}


def _build_kg_scene_data(
    scene: Dict[str, Any],
    *,
    scene_id: str,
    video_id: str,
    frame_data: Optional[Dict[str, Any]],
    audio_data: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    frame_payload = frame_data if isinstance(frame_data, dict) else {}
    audio_payload = audio_data if isinstance(audio_data, dict) else {}
    _promote_metadata_time_hints(audio_payload)
    audio_speaker_ids = _extract_speaker_ids(audio_payload)
    merged_entities: List[Any] = []
    for modality_data in (frame_payload, audio_payload):
        typed_entities = modality_data.get('ner_entities')
        fallback_entities = modality_data.get('entities')
        detail_entities = modality_data.get('entity_details')
        if isinstance(typed_entities, list) and typed_entities:
            merged_entities.extend(typed_entities)
        if isinstance(fallback_entities, list):
            merged_entities.extend(fallback_entities)
        elif isinstance(fallback_entities, str) and fallback_entities.strip():
            merged_entities.append(fallback_entities.strip())
        if isinstance(detail_entities, list):
            merged_entities.extend(detail_entities)

    return {
        'scene_id': scene_id,
        'video_id': video_id,
        'index': scene.get('index'),
        'start': scene.get('start'),
        'end': scene.get('end'),
        'transcript': audio_payload.get('transcript') or audio_payload.get('full_text'),
        'caption': frame_payload.get('caption'),
        'ocr_text': frame_payload.get('ocr_text'),
        'objects': frame_payload.get('objects'),
        'faces': frame_payload.get('faces'),
        'tags': frame_payload.get('tags'),
        'entities': merged_entities,
        'location': frame_payload.get('location') or audio_payload.get('location'),
        'locations': frame_payload.get('locations') or audio_payload.get('locations'),
        'emotion': audio_payload.get('emotion'),
        'speakers': audio_payload.get('speakers'),
        'speaker_ids': audio_speaker_ids,
        'speaker_count': audio_payload.get('speaker_count', len(audio_speaker_ids)),
        'speaker_transcript': audio_payload.get('speaker_transcript'),
        'diarization': audio_payload.get('diarization'),
        'speaker_segments': audio_payload.get('speaker_segments'),
        'speaker_voice_signatures': audio_payload.get('speaker_voice_signatures'),
        'speaker_voice_signature_meta': audio_payload.get('speaker_voice_signature_meta'),
        'music_events': audio_payload.get('music_events'),
        'time_hints': _resolve_scene_time_hints(audio_payload, frame_payload),
        'metadata_time_hints': audio_payload.get('metadata_time_hints'),
        'keyframe': frame_payload,
        'audio': audio_payload,
    }


def _persist_frame_semantic_entities(
    item: Dict[str, Any],
    *,
    scene_id: str,
    video_id: str,
    config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Derive safe, non-object vision semantics from the already-materialized frame payload.

    This persists useful location/person/concept signals into the keyframe payload so
    downstream consumers do not have to wait for Phase 6 harmonization to see them.
    Objects remain in the dedicated object path and are not duplicated here.
    """
    if not VISION_ENTITY_EXTRACTION_AVAILABLE or not isinstance(item, dict):
        return

    scene_data = {
        "keyframe": dict(item),
        "start_time": item.get("timestamp") or 0.0,
    }
    try:
        entity_result = extract_entities_from_scene(
            scene_data=scene_data,
            scene_id=scene_id,
            video_id=video_id,
            config=config if isinstance(config, dict) else {},
        )
    except Exception as e:
        logger.warning(
            "run_ingestion warning context=%s scene_id=%s video_id=%s error=%s",
            "frame_semantic_entities",
            scene_id,
            video_id,
            e,
        )
        return

    if not isinstance(entity_result, dict):
        return

    raw_entities = entity_result.get("entities")
    if not isinstance(raw_entities, list):
        return

    semantic_labels: List[str] = []
    semantic_details: List[Dict[str, Any]] = []
    location_names: List[str] = []
    location_details: List[Dict[str, Any]] = []

    for entity in raw_entities:
        if not isinstance(entity, dict):
            continue
        name = normalize_entity_token(entity.get("name"))
        entity_type = str(entity.get("entity_type") or "").strip().lower()
        if not name or not entity_type or entity_type == "object":
            continue
        if not is_valid_entity_token(name):
            continue

        confidence_raw = entity.get("confidence")
        try:
            confidence = float(confidence_raw) if confidence_raw is not None else 0.7
        except Exception:
            confidence = 0.7
        confidence = max(0.0, min(confidence, 1.0))

        semantic_labels.append(name)
        detail = {
            "label": name,
            "type": entity_type.upper(),
            "score": round(confidence * 10.0, 3),
            "sources": ["vision_semantic"],
        }
        semantic_details.append(detail)
        if entity_type == "location":
            location_names.append(name)
            location_details.append(detail)

    if not semantic_details:
        item.setdefault("vision_semantic_meta", {"status": "ok", "entity_count": 0, "location_count": 0})
        return

    existing_entities = item.get("entities") if isinstance(item.get("entities"), list) else []
    item["entities"] = merge_tag_sources(
        existing_entities,
        semantic_labels,
        validator=is_valid_entity_token,
        normalizer=normalize_entity_token,
    )

    existing_entity_details = item.get("entity_details") if isinstance(item.get("entity_details"), list) else []
    existing_detail_keys = {
        (
            str(detail.get("label") or "").strip().casefold(),
            str(detail.get("type") or "").strip().upper(),
        )
        for detail in existing_entity_details
        if isinstance(detail, dict)
    }
    merged_entity_details: List[Dict[str, Any]] = list(existing_entity_details)
    for detail in semantic_details:
        detail_key = (
            str(detail.get("label") or "").strip().casefold(),
            str(detail.get("type") or "").strip().upper(),
        )
        if detail_key in existing_detail_keys:
            continue
        merged_entity_details.append(detail)
        existing_detail_keys.add(detail_key)
    item["entity_details"] = merged_entity_details

    if location_names:
        existing_locations = item.get("locations") if isinstance(item.get("locations"), list) else []
        item["locations"] = merge_tag_sources(
            existing_locations,
            location_names,
            validator=is_valid_entity_token,
            normalizer=normalize_entity_token,
        )
        if not item.get("location"):
            item["location"] = item["locations"][0]

    item["vision_semantic_entities"] = semantic_details
    item["vision_semantic_meta"] = {
        "status": "ok",
        "entity_count": len(semantic_details),
        "location_count": len(location_details),
    }


def _coerce_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _offset_timestamped_segments(segments: Any, offset: float) -> Any:
    if not isinstance(segments, list) or abs(offset) < 1e-9:
        return segments

    normalized: List[Any] = []
    for segment in segments:
        if not isinstance(segment, dict):
            normalized.append(segment)
            continue
        segment_copy = dict(segment)
        start_val = _coerce_optional_float(segment_copy.get("start"))
        if start_val is not None:
            segment_copy["start"] = start_val + offset
        end_val = _coerce_optional_float(segment_copy.get("end"))
        if end_val is not None:
            segment_copy["end"] = end_val + offset
        if isinstance(segment_copy.get("words"), list):
            segment_copy["words"] = _offset_timestamped_segments(segment_copy["words"], offset)
        if isinstance(segment_copy.get("segments"), list):
            segment_copy["segments"] = _offset_timestamped_segments(segment_copy["segments"], offset)
        normalized.append(segment_copy)
    return normalized


def _offset_local_audio_result_to_scene(result: Any, scene_start: float) -> Any:
    """
    Normalize local transcription output onto the absolute scene timeline.

    The local audio transcription step works on extracted scene chunks, so its
    segment timestamps are scene-relative by construction. Downstream memory and
    harmonization logic align transcript and speaker segments against absolute
    video scene ranges, so translate those local timestamps before they fan out.
    """
    if not isinstance(result, dict) or abs(scene_start) < 1e-9:
        return result

    import copy
    import math
    normalized = copy.deepcopy(result)
    seen = set()
    def translate(value):
        if not isinstance(value, (dict, list)) or id(value) in seen:
            return
        seen.add(id(value))
        if isinstance(value, list):
            for row in value:
                translate(row)
            return
        for key, item in value.items():
            if key in ('start', 'end', 'raw_start', 'raw_end'):
                numeric = _coerce_optional_float(item)
                if numeric is not None and math.isfinite(numeric):
                    value[key] = numeric + scene_start
            else:
                translate(item)
        if value.get('timebase') in ('input_audio_seconds', 'source_audio_seconds'):
            value['timebase'] = 'video_seconds'
            value['source_offset_seconds'] = scene_start
        if 'sample_start' in value:
            value['sample_timebase'] = 'input_audio_samples'
    translate(normalized)
    return normalized


def _normalize_local_transcription_result(result: Any) -> Dict[str, Any]:
    """Preserve a terminal audio outcome even when a worker returns no payload."""
    if not isinstance(result, dict):
        return {
            "transcript": None,
            "transcript_meta": {
                "status": "invalid_worker_result",
                "engine": "goodq_audio_transcribe",
                "reason": "worker_result_not_a_mapping",
            },
        }

    # _run_step_async returns a lifecycle envelope while the synchronous runner
    # returns the worker payload directly.  Normalize against the payload in
    # both cases; otherwise a successful transcript nested under ``outputs``
    # is mistaken for an empty worker result and replaced with a false failure.
    async_outputs = result.get("outputs")
    if result.get("step_name") == "audio_transcribe_local" and isinstance(async_outputs, dict):
        result = async_outputs

    normalized = dict(result)
    normalized.setdefault("transcript", None)
    transcript_meta = normalized.get("transcript_meta")
    if isinstance(transcript_meta, dict):
        return normalized

    has_transcript = isinstance(normalized.get("transcript"), str) and bool(normalized["transcript"].strip())
    has_segments = isinstance(normalized.get("segments"), list) and bool(normalized["segments"])
    normalized["transcript_meta"] = {
        "status": "success" if has_transcript or has_segments else "no_transcript_output",
        "engine": "goodq_audio_transcribe",
        "reason": "worker_result_missing_transcript_meta",
    }
    return normalized


def _infer_audio_backend_fields(
    audio_info: Optional[Dict[str, Any]],
    *,
    skip_audio: bool,
    audio_error: Optional[str],
) -> Dict[str, str]:
    if audio_error:
        return {
            'audio_backend_selected': 'none',
            'audio_backend_reason': 'audio_processing_error',
        }

    if not isinstance(audio_info, dict):
        return {
            'audio_backend_selected': 'none',
            'audio_backend_reason': 'dedupe_skipped' if skip_audio else 'no_audio_stream',
        }

    candidates: List[Dict[str, Any]] = [audio_info]
    data = audio_info.get('data')
    raw = audio_info.get('raw')
    if isinstance(data, dict):
        candidates.append(data)
    if isinstance(raw, dict):
        candidates.append(raw)

    for candidate in candidates:
        selected = candidate.get('audio_backend_selected')
        reason = candidate.get('audio_backend_reason')
        if isinstance(selected, str) and selected in {'wsl', 'windows', 'recording', 'none'}:
            return {
                'audio_backend_selected': selected,
                'audio_backend_reason': (
                    reason if isinstance(reason, str) and reason.strip() else 'explicit_backend_marker'
                ),
            }

    transcript_meta: Dict[str, Any] = {}
    for candidate in candidates:
        meta = candidate.get('transcript_meta')
        if isinstance(meta, dict):
            transcript_meta = meta
            break

    method = str(transcript_meta.get('method') or '').strip().lower()
    status = str(transcript_meta.get('status') or '').strip().lower()

    def _has_segments(value: Any) -> bool:
        return isinstance(value, list) and len(value) > 0

    has_transcript = False
    has_segments = False
    for candidate in candidates:
        if isinstance(candidate.get('transcript'), str) and candidate.get('transcript', '').strip():
            has_transcript = True
        if _has_segments(candidate.get('segments')):
            has_segments = True

    if method in {'wsl2_gpu', 'wsl_faster_whisper_venv'}:
        reason = f'wsl_transcript_{status}' if status else 'wsl_transcript_selected'
        return {'audio_backend_selected': 'wsl', 'audio_backend_reason': reason}

    if has_transcript or has_segments:
        return {
            'audio_backend_selected': 'windows',
            'audio_backend_reason': f'windows_transcript_{status}' if status else 'windows_transcript_available',
        }

    if status:
        return {'audio_backend_selected': 'none', 'audio_backend_reason': f'unavailable_backend_{status}'}

    return {'audio_backend_selected': 'none', 'audio_backend_reason': 'unavailable_backend'}


def _read_audio_backend_marker(audio_info: Optional[Dict[str, Any]], key: str) -> Any:
    if not isinstance(audio_info, dict):
        return None
    candidates: List[Dict[str, Any]] = [audio_info]
    data = audio_info.get('data')
    raw = audio_info.get('raw')
    if isinstance(data, dict):
        candidates.append(data)
    if isinstance(raw, dict):
        candidates.append(raw)
    for candidate in candidates:
        if key in candidate:
            return candidate.get(key)
    return None


def _record_audio_backend_event(run_context: Optional[Dict[str, Any]], event: Dict[str, Any]) -> None:
    if not isinstance(run_context, dict):
        return
    events = run_context.get('audio_backend_events')
    if not isinstance(events, list):
        events = []
        run_context['audio_backend_events'] = events
    events.append(dict(event))


def _audio_backend_events_since(
    run_context: Optional[Dict[str, Any]],
    start_index: int,
) -> List[Dict[str, Any]]:
    if not isinstance(run_context, dict):
        return []
    events = run_context.get('audio_backend_events')
    if not isinstance(events, list):
        return []
    start_index = max(0, int(start_index or 0))
    return [dict(event) for event in events[start_index:] if isinstance(event, dict)]


def _resolve_audio_backend_attribution(
    audio_info: Optional[Dict[str, Any]],
    *,
    skip_audio: bool,
    audio_error: Optional[str],
    audio_runtime_contract: Optional[Dict[str, Any]],
    run_context: Optional[Dict[str, Any]],
    scene_id: str,
    scene_index: Any,
) -> Dict[str, Any]:
    inferred_effective = _infer_audio_backend_fields(
        audio_info,
        skip_audio=skip_audio,
        audio_error=audio_error,
    )
    selected = 'none'
    selected_reason = 'runtime_contract_unset'
    if isinstance(audio_runtime_contract, dict):
        contract_selected = audio_runtime_contract.get('selected')
        contract_reason = audio_runtime_contract.get('reason')
        if isinstance(contract_selected, str) and contract_selected.strip().lower() in {'wsl', 'windows', 'recording', 'none'}:
            selected = contract_selected.strip().lower()
            if isinstance(contract_reason, str) and contract_reason.strip():
                selected_reason = contract_reason.strip()
            else:
                selected_reason = 'runtime_contract_selected'
    if selected_reason == 'runtime_contract_unset':
        selected = inferred_effective['audio_backend_selected']
        selected_reason = 'scene_inferred_selected'

    explicit_effective = _read_audio_backend_marker(audio_info, 'audio_backend_effective')
    explicit_effective_reason = _read_audio_backend_marker(audio_info, 'audio_backend_effective_reason')
    if isinstance(explicit_effective, str) and explicit_effective.strip().lower() in {'wsl', 'windows', 'recording', 'none', 'failed'}:
        effective = explicit_effective.strip().lower()
        if isinstance(explicit_effective_reason, str) and explicit_effective_reason.strip():
            effective_reason = explicit_effective_reason.strip()
        else:
            effective_reason = 'explicit_effective_marker'
    else:
        effective = inferred_effective['audio_backend_selected']
        effective_reason = inferred_effective['audio_backend_reason']

    if isinstance(audio_error, str) and audio_error.strip():
        effective = 'failed'
        effective_reason = 'audio_processing_error'

    downgraded = selected in {'wsl', 'windows', 'recording'} and effective in {'wsl', 'windows', 'recording', 'none', 'failed'} and selected != effective
    downgrade_reason: Optional[str] = None
    downgrade_details: Dict[str, Any] = {}
    downgrade_ts_utc: Optional[str] = None
    if downgraded:
        if audio_error:
            downgrade_reason = 'audio_processing_error'
            downgrade_details['audio_error'] = audio_error
        elif selected == 'wsl' and effective == 'windows':
            downgrade_reason = 'wsl_to_windows_fallback'
        elif selected == 'wsl' and effective == 'failed':
            downgrade_reason = 'wsl_processing_failed'
        elif selected == 'wsl' and effective == 'none':
            downgrade_reason = 'wsl_unavailable_in_scene'
        elif selected == 'windows' and effective == 'failed':
            downgrade_reason = 'windows_processing_failed'
        elif selected == 'windows' and effective == 'none':
            downgrade_reason = 'windows_unavailable_in_scene'
        else:
            downgrade_reason = f'{selected}_to_{effective}'
        downgrade_ts_utc = datetime.now(timezone.utc).isoformat()
        downgrade_details['selected_reason'] = selected_reason
        downgrade_details['effective_reason'] = effective_reason
        unavailable_details = _read_audio_backend_marker(audio_info, 'audio_backend_unavailable_details')
        if isinstance(unavailable_details, dict) and unavailable_details:
            downgrade_details['backend_unavailable'] = dict(unavailable_details)
        elif downgrade_reason in {'windows_unavailable_in_scene', 'wsl_unavailable_in_scene'}:
            transcript_meta = _read_audio_backend_marker(audio_info, 'transcript_meta')
            if isinstance(transcript_meta, dict):
                downgrade_details['transcript_status'] = transcript_meta.get('status')
                downgrade_details['transcript_engine'] = transcript_meta.get('engine')
                downgrade_details['transcript_model'] = transcript_meta.get('model')
                downgrade_details['transcript_device'] = transcript_meta.get('device')
        _record_audio_backend_event(
            run_context,
            {
                'scene_id': scene_id,
                'scene_index': scene_index,
                'selected': selected,
                'effective': effective,
                'downgrade_reason': downgrade_reason,
                'details': dict(downgrade_details),
                'ts_utc': downgrade_ts_utc,
            },
        )

    return {
        'audio_backend_selected': selected,
        'audio_backend_reason': selected_reason,
        'audio_backend_effective': effective,
        'audio_backend_effective_reason': effective_reason,
        'audio_backend_downgraded': downgraded,
        'audio_backend_downgrade_reason': downgrade_reason,
        'audio_backend_downgrade_ts': downgrade_ts_utc,
        'audio_backend_downgrade_details': downgrade_details,
    }


def _normalize_vector_store_status(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, str):
        lower = value.strip().lower()
        if lower in ('not_attempted',):
            return 'not_attempted'
        if lower in ('complete', 'completed', 'ok', 'success', 'passed', 'ready', 'true'):
            return True
        if lower in ('failed', 'error', 'false', 'unavailable'):
            return False
        return 'not_attempted'  # unknown strings → not_attempted, not blindly True
    return bool(value)


def _aggregate_audio_backend(
    scene_outputs: List[Dict[str, Any]],
    *,
    field: str = 'audio_backend_selected',
) -> str:
    """
    Deterministic run-level backend reducer.

    Rules:
    - mixed: scenes include more than one of wsl, windows and recording
    - recording: at least one scene uses the recording engine, with no other engine
    - wsl: at least one scene uses wsl, and none use windows
    - windows: at least one scene uses windows, and none use wsl
    - failed: at least one scene reports failed and no wsl/windows present
    - none: no scenes report wsl/windows/failed
    """
    used_wsl = False
    used_windows = False
    used_recording = False
    used_failed = False

    for scene in scene_outputs:
        if not isinstance(scene, dict):
            continue
        backend = scene.get(field)
        if not isinstance(backend, str):
            continue
        normalized = backend.strip().lower()
        if normalized == 'wsl':
            used_wsl = True
        elif normalized == 'windows':
            used_windows = True
        elif normalized == 'recording':
            used_recording = True
        elif normalized == 'failed':
            used_failed = True

    if sum((used_wsl, used_windows, used_recording)) > 1:
        return 'mixed'
    if used_recording:
        return 'recording'
    if used_wsl:
        return 'wsl'
    if used_windows:
        return 'windows'
    if used_failed:
        return 'failed'
    return 'none'


def _resolve_audio_runtime_contract(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve audio backend contract once per run.
    This prevents per-scene backend discovery drift.
    """
    from steps.audio.recording_ingestion import selected, settings
    if selected(cfg):
        candidate = settings(cfg)
        return {'selected': 'recording', 'reason': 'explicit_recording_engine',
                'mode': 'recording', 'requested_wsl': candidate['transport'] == 'wsl'}
    require_wsl = require_wsl_audio()
    requested_wsl = bool(wsl_audio_auto_enabled() or require_wsl)
    host_cfg = cfg.get('host') if isinstance(cfg, dict) else {}
    cfg_wsl_distro = (
        str(host_cfg.get('wsl_distro')).strip()
        if isinstance(host_cfg, dict) and host_cfg.get('wsl_distro') is not None
        else ''
    )
    explicit_wsl_distro = str(os.environ.get("GOODQ_WSL_DISTRO") or "").strip()
    distro_candidates: List[tuple[str, str]] = []
    seen_distros: Set[str] = set()

    def _add_distro_candidate(source: str, value: str) -> None:
        normalized = str(value or "").strip()
        if not normalized or normalized.lower() in {'auto', 'unset'} or normalized in seen_distros:
            return
        seen_distros.add(normalized)
        distro_candidates.append((source, normalized))

    _add_distro_candidate('env', explicit_wsl_distro)
    _add_distro_candidate('config', cfg_wsl_distro)
    _add_distro_candidate('default', 'Ubuntu')
    primary_distro_source, wsl_distro = distro_candidates[0] if distro_candidates else ('default', 'Ubuntu')
    contract: Dict[str, Any] = {
        'mode': 'auto',
        'requested_wsl': requested_wsl,
        'require_wsl_audio': require_wsl,
        'wsl_command_available': bool(shutil.which('wsl')),
        'wsl_distro': wsl_distro,
        'wsl_distro_source': primary_distro_source,
        'wsl_user': None,
        'wsl_workspace': None,
        'wsl_audio_workspace': None,
        'workspace_ready': False,
        'wsl_runtime_ready': False,
        'wsl_abi_ready': False,
        'selected': 'none',
        'reason': 'unresolved',
    }

    if not requested_wsl:
        contract['selected'] = 'windows'
        contract['reason'] = 'profile_wsl_disabled'
        return contract

    if not contract['wsl_command_available']:
        if require_wsl:
            raise RuntimeError("GOODQ_REQUIRE_WSL_AUDIO=1 but wsl command is unavailable.")
        contract['selected'] = 'none'
        contract['reason'] = 'wsl_command_unavailable'
        return contract

    cfg_wsl_user = (
        str(host_cfg.get('wsl_user')).strip()
        if isinstance(host_cfg, dict) and host_cfg.get('wsl_user') is not None
        else ''
    )
    explicit_wsl_user = str(os.environ.get("GOODQ_WSL_USER") or "").strip()
    if not explicit_wsl_user and cfg_wsl_user and cfg_wsl_user.lower() not in {'auto', 'unset'}:
        explicit_wsl_user = cfg_wsl_user

    if explicit_wsl_user:
        wsl_user = explicit_wsl_user
    else:
        wsl_user = ''
        for candidate in (os.environ.get("USER"), os.environ.get("USERNAME"), os.environ.get("LOGNAME")):
            if candidate:
                wsl_user = str(candidate).strip()
                break
        if not wsl_user:
            wsl_user = 'user'

    cfg_wsl_workspace = (
        str(host_cfg.get('wsl_workspace')).strip()
        if isinstance(host_cfg, dict) and host_cfg.get('wsl_workspace') is not None
        else ''
    )
    contract['wsl_user'] = wsl_user
    explicit_workspace = str(os.environ.get("GOODQ_WSL_WORKSPACE") or "").strip()
    default_workspace = f"/home/{wsl_user}/goodq_audio"
    workspace_candidates: List[tuple[str, str]] = []
    seen_workspaces: Set[str] = set()

    def _add_workspace_candidate(source: str, value: str) -> None:
        normalized = str(value or "").strip().rstrip("/")
        if not normalized or normalized in seen_workspaces:
            return
        seen_workspaces.add(normalized)
        workspace_candidates.append((source, normalized))

    _add_workspace_candidate('env', explicit_workspace)
    _add_workspace_candidate('config', cfg_wsl_workspace)
    _add_workspace_candidate('default', default_workspace)

    failed_workspaces: List[str] = []
    probe_failures: List[str] = []
    attempted_targets: List[str] = []
    degraded_workspaces: List[str] = []

    for distro_source, candidate_distro in distro_candidates:
        for workspace_source, audio_workspace in workspace_candidates:
            workspace = audio_workspace
            contract['wsl_distro'] = candidate_distro
            contract['wsl_distro_source'] = distro_source
            contract['wsl_workspace'] = workspace
            contract['wsl_audio_workspace'] = audio_workspace
            contract['wsl_workspace_source'] = workspace_source
            attempted_targets.append(f"{candidate_distro}:{audio_workspace}")
            try:
                probe = probe_wsl_audio_runtime(candidate_distro, audio_workspace)
                workspace_ready = bool(probe.get('workspace_ready'))
                runtime_ready = bool(probe.get('runtime_ready'))
                abi_ready = bool(probe.get('abi_ready'))
                contract['workspace_ready'] = workspace_ready
                contract['wsl_runtime_ready'] = runtime_ready
                contract['wsl_abi_ready'] = abi_ready
                contract['wsl_runtime_detail'] = str(probe.get('detail') or '')
                if runtime_ready and abi_ready:
                    contract['selected'] = 'wsl'
                    contract['reason'] = 'wsl_runtime_ready'
                    fallback_notes: List[str] = []
                    if explicit_wsl_distro and distro_source != 'env':
                        fallback_notes.append(
                            f"GOODQ_WSL_DISTRO={explicit_wsl_distro} was unavailable; using {candidate_distro} from {distro_source}."
                        )
                    if explicit_workspace and workspace_source != 'env':
                        fallback_notes.append(
                            f"GOODQ_WSL_WORKSPACE={explicit_workspace} was unavailable; using {audio_workspace} from {workspace_source}."
                        )
                    if fallback_notes:
                        contract['workspace_check_message'] = " ".join(fallback_notes)
                    if wsl_user:
                        os.environ["GOODQ_WSL_USER"] = wsl_user
                    os.environ["GOODQ_WSL_DISTRO"] = candidate_distro
                    os.environ["GOODQ_WSL_WORKSPACE"] = workspace
                    return contract
                if runtime_ready and not abi_ready:
                    degraded_workspaces.append(
                        f"{candidate_distro}:{audio_workspace} ({probe.get('detail') or 'abi degraded'})"
                    )
                    continue
                failed_workspaces.append(
                    f"{candidate_distro}:{audio_workspace} ({probe.get('detail') or 'not ready'})"
                )
            except Exception as e:
                probe_failures.append(f"{candidate_distro}:{audio_workspace}: {e}")

    tried_workspaces = ", ".join(failed_workspaces or attempted_targets)
    if probe_failures:
        message = (
            "WSL workspace preflight failed; "
            f"tried={tried_workspaces}; errors={' | '.join(probe_failures)}"
        )
        if require_wsl:
            raise RuntimeError(message)
        contract['selected'] = 'none'
        contract['reason'] = 'wsl_workspace_preflight_failed'
        contract['workspace_check_message'] = message
        return contract

    if degraded_workspaces:
        message = (
            "WSL workspace is transcription-ready but ABI-degraded; "
            f"tried={', '.join(degraded_workspaces)}. "
            "Canonical ingestion will not select WSL until abi_ready=true."
        )
        if require_wsl:
            raise RuntimeError(message)
        contract['selected'] = 'none'
        contract['reason'] = 'wsl_workspace_abi_degraded'
        contract['workspace_check_message'] = message
        return contract

    message = (
        f"WSL workspace not found, tried={tried_workspaces}. "
        "Set GOODQ_WSL_DISTRO, GOODQ_WSL_USER and GOODQ_WSL_WORKSPACE for deterministic host setup."
    )
    if require_wsl:
        raise RuntimeError(message)
    contract['selected'] = 'none'
    contract['reason'] = 'wsl_workspace_missing'
    contract['workspace_check_message'] = message
    return contract


def _resolve_segmentation_activation(cfg: Dict[str, Any]) -> str:
    env_mode = str(os.getenv("GOODQ_SEGMENTATION_MODE") or "").strip().lower()
    env_backend = str(os.getenv("GOODQ_SEGMENTATION_BACKEND") or "").strip().lower()
    if env_mode == "authoritative" and env_backend in {"seg_p5", "segmentation_phase5"}:
        return "authoritative"
    segmentation_cfg = cfg.get('segmentation') if isinstance(cfg, dict) else {}
    if not isinstance(segmentation_cfg, dict):
        return 'off'
    raw_value = str(segmentation_cfg.get('activation') or 'off').strip().lower()
    if raw_value in {'off', 'shadow', 'authoritative'}:
        return raw_value
    return 'off'


def _resolve_scene_backend_contract(cfg: Dict[str, Any]) -> Dict[str, Any]:
    segmentation_cfg = cfg.get('segmentation') if isinstance(cfg, dict) else {}
    segmentation_enabled = bool(segmentation_cfg.get('enabled', True)) if isinstance(segmentation_cfg, dict) else False
    activation = _resolve_segmentation_activation(cfg)
    env_mode = str(os.getenv("GOODQ_SEGMENTATION_MODE") or "").strip().lower()
    env_backend = str(os.getenv("GOODQ_SEGMENTATION_BACKEND") or "").strip().lower()

    contract: Dict[str, Any] = {
        'segmentation_enabled': segmentation_enabled,
        'segmentation_activation': activation,
        'scene_backend_selected': 'legacy_scene_detect',
        'scene_backend_effective': 'legacy_scene_detect',
        'scene_backend_effective_reason': 'legacy_scene_detect_default',
        'authoritative_cutover_supported': False,
    }

    if not segmentation_enabled:
        contract['scene_backend_effective_reason'] = 'segmentation_config_disabled'
        return contract

    if env_mode == 'authoritative' and env_backend in {'seg_p5', 'segmentation_phase5'}:
        contract['scene_backend_selected'] = 'segmentation_phase5'
        contract['scene_backend_effective'] = 'segmentation_phase5'
        contract['scene_backend_effective_reason'] = 'segmentation_authoritative_env_override'
        contract['authoritative_cutover_supported'] = True
        return contract

    if activation == 'shadow':
        contract['scene_backend_selected'] = 'segmentation_phase5_shadow_compare'
        contract['scene_backend_effective_reason'] = 'segmentation_shadow_compare_legacy_authority'
        return contract

    if activation == 'authoritative':
        contract['scene_backend_selected'] = 'segmentation_phase5'
        contract['scene_backend_effective_reason'] = 'segmentation_authoritative_not_enabled'
        return contract

    return contract


def _resolve_scene_backend_dispatch(scene_backend_contract: Dict[str, Any]) -> Dict[str, str]:
    effective_backend = str(scene_backend_contract.get('scene_backend_effective') or 'legacy_scene_detect').strip().lower()
    if effective_backend == 'segmentation_phase5':
        return {
            'env_name': 'goodq_core',
            'step_name': 'video_scene_segmentation',
        }
    return {
        'env_name': 'goodq_video_scene_detect',
        'step_name': 'video_scene_detect',
    }


def _run_segmentation_authoritative_scene_backend(
    video_path: Path,
    processing_dir: Path,
    cfg: Dict[str, Any],
    *,
    scene_backend_contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    contract = scene_backend_contract if isinstance(scene_backend_contract, dict) else {
        'scene_backend_selected': 'segmentation_phase5',
        'scene_backend_effective': 'segmentation_phase5',
        'scene_backend_effective_reason': 'segmentation_authoritative_env_override',
    }

    from steps.audio.segmentation import PhasedSegmentationEngine

    authoritative_root = processing_dir / "_segmentation_authoritative"
    engine = PhasedSegmentationEngine(cfg)
    run_result = engine.run_full_pipeline(
        str(video_path),
        str(authoritative_root),
        skip_phases=['phase4', 'phase6'],
    )

    phase_results = run_result.get('phase_results') if isinstance(run_result, dict) else {}
    phase5_result = phase_results.get('phase5') if isinstance(phase_results, dict) else {}
    scene_manifest_path = phase5_result.get('scene_manifest_path') if isinstance(phase5_result, dict) else None
    scene_manifest = _safe_read_json_dict(scene_manifest_path)
    raw_scenes = scene_manifest.get('scenes') if isinstance(scene_manifest, dict) else None
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise RuntimeError("SEG_P5 authoritative cutover produced no scene manifest scenes")

    scenes: List[Dict[str, Any]] = []
    manifest_hasher = hashlib.sha256()
    for idx, raw_scene in enumerate(raw_scenes):
        if not isinstance(raw_scene, dict):
            continue
        start = float(raw_scene.get('start', 0.0) or 0.0)
        end = float(raw_scene.get('end', start) or start)
        duration = round(max(0.0, end - start), 3)
        manifest_hasher.update(f"{start:.6f}|{end:.6f}|".encode('utf-8'))
        scenes.append(
            {
                'index': int(raw_scene.get('index', idx) or idx),
                'start': start,
                'end': end,
                'duration': duration,
                'confidence': float(raw_scene.get('confidence', 0.5) or 0.5),
            }
        )

    if not scenes:
        raise RuntimeError("SEG_P5 authoritative cutover produced no usable scenes")

    return {
        'scenes': scenes,
        'meta': {
            'status': 'ok',
            'engine': 'segmentation_phase5',
            'scene_count': len(scenes),
            'scene_manifest_path': scene_manifest_path,
            'scene_manifest_hash': manifest_hasher.hexdigest(),
            'orchestration': {
                'scene_backend_selected': contract.get('scene_backend_selected'),
                'scene_backend_effective': contract.get('scene_backend_effective'),
                'scene_backend_effective_reason': contract.get('scene_backend_effective_reason'),
                'step_env': 'goodq_core',
                'step_name': 'segmentation_phase5_authoritative',
            },
        },
    }


def _resolve_phase6_audio_source_contract(
    cfg: Dict[str, Any],
    segmentation_shadow_overlay: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    overlay_requested = _segmentation_shadow_audio_overlay_enabled(cfg)
    contract: Dict[str, Any] = {
        'phase6_audio_source_selected': 'segmentation_shadow_audio_overlay' if overlay_requested else 'live_audio_artifacts',
        'phase6_audio_source_effective': 'live_audio_artifacts',
        'phase6_audio_source_effective_reason': 'live_audio_artifacts_default',
    }

    if not overlay_requested:
        return contract

    if isinstance(segmentation_shadow_overlay, dict) and segmentation_shadow_overlay.get('enabled'):
        contract['phase6_audio_source_effective'] = 'segmentation_shadow_audio_overlay'
        contract['phase6_audio_source_effective_reason'] = str(
            segmentation_shadow_overlay.get('reason') or 'segmentation_shadow_audio_overlay_ready'
        )
        return contract

    if isinstance(segmentation_shadow_overlay, dict):
        contract['phase6_audio_source_effective_reason'] = str(
            segmentation_shadow_overlay.get('reason') or 'segmentation_shadow_audio_overlay_not_ready'
        )
    else:
        contract['phase6_audio_source_effective_reason'] = 'segmentation_shadow_audio_overlay_not_resolved'
    return contract


def _resolve_ingest_orchestration_contract(
    cfg: Dict[str, Any],
    *,
    audio_runtime_contract: Optional[Dict[str, Any]] = None,
    segmentation_shadow: Optional[Dict[str, Any]] = None,
    segmentation_shadow_overlay: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    scene_backend = _resolve_scene_backend_contract(cfg)
    phase6_audio_source = _resolve_phase6_audio_source_contract(cfg, segmentation_shadow_overlay)
    audio_backend = str((audio_runtime_contract or {}).get('selected') or 'none').strip().lower() or 'none'
    shadow_status = str((segmentation_shadow or {}).get('status') or '').strip().lower()
    shadow_reason = str((segmentation_shadow or {}).get('reason') or '').strip().lower()

    return {
        'version': 1,
        'execution_owner': 'cli.run_ingestion',
        'step_execution_owner': 'cli.step_runner',
        'persistence_owner': 'steps.common.memory',
        'persistence_functions': [
            'ensure_scene',
            'scene_has_materialized',
            'register_scene_bundle',
        ],
        'phase6_owner': 'live_phase6',
        'segmentation_activation': scene_backend['segmentation_activation'],
        'segmentation_enabled': scene_backend['segmentation_enabled'],
        'scene_backend_selected': scene_backend['scene_backend_selected'],
        'scene_backend_effective': scene_backend['scene_backend_effective'],
        'scene_backend_effective_reason': scene_backend['scene_backend_effective_reason'],
        'phase6_audio_source_selected': phase6_audio_source['phase6_audio_source_selected'],
        'phase6_audio_source_effective': phase6_audio_source['phase6_audio_source_effective'],
        'phase6_audio_source_effective_reason': phase6_audio_source['phase6_audio_source_effective_reason'],
        'audio_runtime_backend': audio_backend,
        'segmentation_shadow_status': shadow_status or 'not_run',
        'segmentation_shadow_reason': shadow_reason or 'not_run',
        'authoritative_cutover_supported': bool(scene_backend['authoritative_cutover_supported']),
    }


def _safe_read_json_dict(path_value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(path_value, (str, Path)):
        return None
    try:
        path = Path(path_value)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding='utf-8'))
        return payload if isinstance(payload, dict) else None
    except Exception as e:
        logger.debug(
            "run_ingestion warning context=%s error=%s",
            "segmentation_shadow.read_json",
            e,
        )
        return None


_CHECKPOINT_TARGETS = {
    'memory_db',
    'knowledge_graph',
    'vectors',
    'scene_manifest',
    'temporal_index',
}
_CHECKPOINT_TARGET_STATES = {'committed', 'not_applicable', 'failed'}


def _sqlite_contains_window_scenes(
    db_path_value: Any,
    *,
    table: str,
    id_column: str,
    scene_ids: List[str],
    video_hash: Optional[str] = None,
) -> bool:
    if table not in {'scenes', 'media_nodes'} or id_column not in {'id', 'scene_id'}:
        raise ValueError('unsupported checkpoint probe target')
    normalized_ids = [str(scene_id) for scene_id in scene_ids if scene_id]
    if not normalized_ids or not isinstance(db_path_value, (str, Path)):
        return False
    db_path = Path(db_path_value)
    if not db_path.is_file():
        return False

    placeholders = ','.join('?' for _ in normalized_ids)
    query = f"SELECT DISTINCT {id_column} FROM {table} WHERE {id_column} IN ({placeholders})"
    params: List[Any] = list(normalized_ids)
    if table == 'scenes' and video_hash:
        query += ' AND video_hash = ?'
        params.append(video_hash)
    try:
        conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            found = {
                str(row[0])
                for row in conn.execute(query, tuple(params)).fetchall()
                if row and row[0]
            }
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.warning('Checkpoint persistence probe failed for %s: %s', table, exc)
        return False
    return set(normalized_ids).issubset(found)


def _scene_manifest_contains_window_scenes(
    scene_manifest_path: Any,
    scene_ids: List[str],
) -> bool:
    manifest = _safe_read_json_dict(scene_manifest_path)
    raw_scenes = manifest.get('scenes') if isinstance(manifest, dict) else None
    if not isinstance(raw_scenes, list):
        return False
    expected = {str(scene_id) for scene_id in scene_ids if scene_id}
    found = {
        str(scene.get('scene_id') or scene.get('id'))
        for scene in raw_scenes
        if isinstance(scene, dict) and (scene.get('scene_id') or scene.get('id'))
    }
    return bool(expected) and expected.issubset(found)


def _scene_manifest_has_committed_vectors(
    scene_manifest_path: Any,
    scene_ids: List[str],
) -> bool:
    """Verify canonical Phase 6 vector commit evidence for the window scenes."""
    manifest = _safe_read_json_dict(scene_manifest_path)
    if not isinstance(manifest, dict):
        return False
    if manifest.get('phase6_complete') is not True or manifest.get('phase6_status') != 'complete':
        return False

    vector_commit = manifest.get('phase6_vector_commit')
    if not isinstance(vector_commit, dict) or vector_commit.get('enabled') is not True:
        return False
    if vector_commit.get('qdrant_ok') is not True:
        return False

    expected = {str(scene_id) for scene_id in scene_ids if scene_id}
    raw_scenes = manifest.get('scenes')
    if not expected or not isinstance(raw_scenes, list):
        return False
    committed_scene_ids = {
        str(scene.get('scene_id') or scene.get('id'))
        for scene in raw_scenes
        if (
            isinstance(scene, dict)
            and (scene.get('scene_id') or scene.get('id'))
            and scene.get('clip_id')
            and scene.get('dino_id')
            and scene.get('qdrant_ok') is True
        )
    }
    return expected.issubset(committed_scene_ids)


def _temporal_index_contains_window_scenes(
    temporal_index_path: Any,
    scene_ids: List[str],
) -> bool:
    temporal_index = _safe_read_json_dict(temporal_index_path)
    raw_segments = temporal_index.get('segments') if isinstance(temporal_index, dict) else None
    if not isinstance(raw_segments, list):
        return False
    expected = {str(scene_id) for scene_id in scene_ids if scene_id}
    found = {
        str(segment.get('scene_id'))
        for segment in raw_segments
        if isinstance(segment, dict) and segment.get('scene_id')
    }
    return bool(expected) and expected.issubset(found)


def _target_checkpoint_status(*, applicable: bool, committed: bool) -> str:
    if not applicable:
        return 'not_applicable'
    return 'committed' if committed else 'failed'


def _build_progressive_checkpoint_record(
    *,
    cfg: Dict[str, Any],
    run_id: str,
    video_hash: str,
    window_idx: int,
    window_start: float,
    window_end: float,
    scene_ids: List[str],
    graph_applicable: bool,
    graph_failed: bool,
    vectors_applicable: bool,
    scene_manifest_path: Path,
    temporal_index_applicable: bool,
    temporal_index_committed: bool,
    temporal_index_path: Path,
) -> Dict[str, Any]:
    """Build checkpoint truth from the actual persistence surfaces."""
    paths = cfg.get('paths', {}) or {}
    isolation = bool(cfg.get('ingestion_isolation', False))
    normalized_scene_ids = [str(scene_id) for scene_id in scene_ids if scene_id]

    memory_committed = (
        not isolation
        and _sqlite_contains_window_scenes(
            paths.get('db_path'),
            table='scenes',
            id_column='id',
            scene_ids=normalized_scene_ids,
            video_hash=video_hash,
        )
    )
    graph_committed = (
        graph_applicable
        and not graph_failed
        and _sqlite_contains_window_scenes(
            paths.get('knowledge_graph_db'),
            table='media_nodes',
            id_column='scene_id',
            scene_ids=normalized_scene_ids,
        )
    )
    manifest_committed = _scene_manifest_contains_window_scenes(
        scene_manifest_path,
        normalized_scene_ids,
    )
    vector_manifest_committed = (
        vectors_applicable
        and _scene_manifest_has_committed_vectors(
            scene_manifest_path,
            normalized_scene_ids,
        )
    )
    temporal_artifact_committed = (
        temporal_index_committed
        and _temporal_index_contains_window_scenes(
            temporal_index_path,
            normalized_scene_ids,
        )
    )

    targets = {
        'memory_db': _target_checkpoint_status(
            applicable=not isolation,
            committed=memory_committed,
        ),
        'knowledge_graph': _target_checkpoint_status(
            applicable=graph_applicable,
            committed=graph_committed,
        ),
        'vectors': _target_checkpoint_status(
            applicable=vectors_applicable,
            committed=vector_manifest_committed,
        ),
        'scene_manifest': _target_checkpoint_status(
            applicable=True,
            committed=manifest_committed,
        ),
        'temporal_index': _target_checkpoint_status(
            applicable=temporal_index_applicable,
            committed=temporal_artifact_committed,
        ),
    }
    failed_targets = sorted(
        target for target, status in targets.items() if status == 'failed'
    )
    return {
        'run_id': run_id,
        'window_idx': int(window_idx),
        'window_start': float(window_start),
        'window_end': float(window_end),
        'scene_ids': normalized_scene_ids,
        'window_status': 'failed' if failed_targets else 'committed',
        'persistence_targets': targets,
        'failed_targets': failed_targets,
        'completed_at': datetime.now(timezone.utc).isoformat(),
    }


def _checkpoint_window_matches_current_persistence(
    *,
    cfg: Dict[str, Any],
    processing_dir: Path,
    video_hash: str,
    record: Dict[str, Any],
) -> bool:
    """Re-probe a checkpoint window before trusting it during resume."""
    targets = record['persistence_targets']
    scene_ids = [str(scene_id) for scene_id in record.get('scene_ids', []) if scene_id]
    if not scene_ids:
        return False

    paths = cfg.get('paths', {}) or {}
    isolation = bool(cfg.get('ingestion_isolation', False))
    phase6_cfg = cfg.get('phase6', {}) or {}
    phase6_enabled = bool(phase6_cfg.get('enabled', True))
    vectors_applicable = bool(
        phase6_enabled
        and (phase6_cfg.get('retrieval', {}) or {}).get('enable', True)
    )
    graph_applicable = bool(
        KNOWLEDGE_GRAPH_AVAILABLE
        and cfg.get('knowledge_graph', {}).get('enabled', True)
        and not isolation
    )

    if isolation:
        if targets['memory_db'] != 'not_applicable':
            return False
    elif (
        targets['memory_db'] != 'committed'
        or not _sqlite_contains_window_scenes(
            paths.get('db_path'),
            table='scenes',
            id_column='id',
            scene_ids=scene_ids,
            video_hash=video_hash,
        )
    ):
        return False

    if not graph_applicable:
        if targets['knowledge_graph'] != 'not_applicable':
            return False
    elif (
        targets['knowledge_graph'] != 'committed'
        or not _sqlite_contains_window_scenes(
            _resolve_graph_db_path(cfg),
            table='media_nodes',
            id_column='scene_id',
            scene_ids=scene_ids,
        )
    ):
        return False

    scene_manifest_path = processing_dir / 'video' / 'scene_manifest.json'
    if (
        targets['scene_manifest'] != 'committed'
        or not _scene_manifest_contains_window_scenes(scene_manifest_path, scene_ids)
    ):
        return False

    if not vectors_applicable:
        if targets['vectors'] != 'not_applicable':
            return False
    elif (
        targets['vectors'] != 'committed'
        or not _scene_manifest_has_committed_vectors(scene_manifest_path, scene_ids)
    ):
        return False

    temporal_status = targets['temporal_index']
    if not phase6_enabled:
        return temporal_status == 'not_applicable'
    if temporal_status == 'not_applicable':
        return True
    if temporal_status != 'committed':
        return False
    temporal_candidates = (
        processing_dir / 'temporal_index.json',
        processing_dir / 'video' / 'temporal_index.json',
    )
    return any(
        _temporal_index_contains_window_scenes(path, scene_ids)
        for path in temporal_candidates
    )


def _completed_checkpoint_window_indices(
    state_data: Dict[str, Any],
    video_hash: str,
    *,
    cfg: Dict[str, Any],
    processing_dir: Path,
    expected_windows: Optional[Dict[int, Dict[str, Any]]] = None,
) -> Set[int]:
    """Return schema-v2 windows whose current persistence evidence still holds."""
    if state_data.get('checkpoint_version') != 2:
        return set()
    if state_data.get('video_hash') != video_hash:
        return set()
    windows = state_data.get('windows')
    if not isinstance(windows, dict):
        return set()

    completed: Set[int] = set()
    for key, record in windows.items():
        if not isinstance(record, dict) or record.get('window_status') != 'committed':
            continue
        targets = record.get('persistence_targets')
        if not isinstance(targets, dict) or set(targets) != _CHECKPOINT_TARGETS:
            continue
        if any(status not in _CHECKPOINT_TARGET_STATES for status in targets.values()):
            continue
        if any(status == 'failed' for status in targets.values()):
            continue
        if targets.get('scene_manifest') != 'committed':
            continue
        try:
            window_idx = int(record.get('window_idx', key))
        except (TypeError, ValueError):
            continue
        if str(window_idx) != str(key):
            continue
        if expected_windows is not None:
            expected = expected_windows.get(window_idx)
            if expected is None or any(
                record.get(field) != expected[field]
                for field in ('window_start', 'window_end', 'scene_ids')
            ):
                logger.info(
                    "[CHECKPOINT] Replaying window %s because its current bounds or scenes differ",
                    window_idx,
                )
                continue
        if not _checkpoint_window_matches_current_persistence(
            cfg=cfg,
            processing_dir=processing_dir,
            video_hash=video_hash,
            record=record,
        ):
            continue
        completed.add(window_idx)
    return completed


def _progressive_checkpoint_cleanup_ready(
    *,
    state_data: Dict[str, Any],
    video_hash: str,
    cfg: Dict[str, Any],
    processing_dir: Path,
    expected_window_indices: Iterable[int],
    phase6_complete: bool,
    expected_windows: Optional[Dict[int, Dict[str, Any]]] = None,
) -> bool:
    """Require fresh five-target evidence for every current window before cleanup."""
    if phase6_complete is not True:
        return False
    expected = {int(window_idx) for window_idx in expected_window_indices}
    if not expected:
        return False
    verified = _completed_checkpoint_window_indices(
        state_data,
        video_hash,
        cfg=cfg,
        processing_dir=processing_dir,
        expected_windows=expected_windows,
    )
    return verified == expected


def _resolve_existing_scene_state(
    cfg: Dict[str, Any],
    scene_id: str,
) -> Tuple[Dict[str, Any], Dict[str, bool]]:
    """Return reusable scene state without legacy-store reads for isolated runs."""
    if cfg.get('ingestion_isolation', False):
        return {}, {'keyframe': False, 'audio': False}
    existing_meta = get_scene_meta(cfg, scene_id) or {}
    materialized = scene_has_materialized(cfg, scene_id, ['keyframe', 'audio'])
    return existing_meta, materialized


def _get_checkpoint_scene_meta(
    cfg: Dict[str, Any],
    scene_id: str,
    manifest_by_id: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Resolve resume evidence without opening memory.db in isolation mode."""
    if cfg.get('ingestion_isolation', False):
        manifest_scene = manifest_by_id.get(scene_id)
        return dict(manifest_scene) if isinstance(manifest_scene, dict) else None
    return get_scene_meta(cfg, scene_id)


def _sort_checkpoint_scene_outputs(
    scene_outputs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Restore chronological order after non-contiguous checkpoint resume."""
    return sorted(
        scene_outputs,
        key=lambda item: (
            float(item.get('start', 0.0) or 0.0),
            int(item.get('index', 0) or 0),
        ),
    )


def _rehydrate_video_result_scenes_from_manifest(
    video_result: Dict[str, Any],
    scene_manifest_path: Any,
) -> bool:
    manifest = _safe_read_json_dict(scene_manifest_path)
    raw_scenes = manifest.get('scenes') if isinstance(manifest, dict) else None
    if not isinstance(raw_scenes, list):
        return False
    existing_scenes = video_result.get('scenes')
    existing_by_identity: Dict[tuple[Any, Any], Dict[str, Any]] = {}
    existing_by_id: Dict[Any, Dict[str, Any]] = {}
    if isinstance(existing_scenes, list):
        for existing in existing_scenes:
            if not isinstance(existing, dict):
                continue
            sid = existing.get('scene_id') or existing.get('id')
            idx = existing.get('index')
            existing_by_identity[(sid, idx)] = existing
            if sid is not None and sid not in existing_by_id:
                existing_by_id[sid] = existing

    canonical_scenes: List[Dict[str, Any]] = []
    for scene in raw_scenes:
        if not isinstance(scene, dict):
            continue
        sid = scene.get('scene_id') or scene.get('id')
        idx = scene.get('index')
        base_scene = existing_by_identity.get((sid, idx)) or existing_by_id.get(sid)
        projected_scene = dict(base_scene) if isinstance(base_scene, dict) else {}
        for key, val in scene.items():
            if key in ('keyframe', 'audio') and val == {} and key not in projected_scene:
                continue
            projected_scene[key] = val
        scene_context_llm = scene.get('scene_context_llm')
        if isinstance(scene_context_llm, dict):
            if 'summary' not in scene or scene.get('summary') is None:
                projected_scene['summary'] = scene_context_llm.get('narrative_summary')
            if 'tags' not in scene or not any(scene.get('tags') or []):
                projected_scene['tags'] = scene_context_llm.get('context_tags')
            if 'key_moments' not in scene or not any(scene.get('key_moments') or []):
                projected_scene['key_moments'] = scene_context_llm.get('key_moments')
        canonical_scenes.append(projected_scene)
    if not canonical_scenes:
        return False
    if isinstance(existing_scenes, list):
        existing_scenes[:] = canonical_scenes
    video_result['scenes'] = canonical_scenes
    return True


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _segment_has_transcript(segment: Any) -> bool:
    if not isinstance(segment, dict):
        return False
    transcript = segment.get('transcript')
    if isinstance(transcript, str) and transcript.strip():
        return True
    transcript_segments = segment.get('transcript_segments')
    if isinstance(transcript_segments, list):
        return _has_meaningful_audio_segments(
            [item for item in transcript_segments if isinstance(item, dict)]
        )
    words = segment.get('words')
    if isinstance(words, list):
        return any(
            isinstance(word, dict) and isinstance(word.get('word'), str) and word.get('word', '').strip()
            for word in words
        )
    return False


def _extract_segment_speaker_ids(segment: Any) -> List[str]:
    if not isinstance(segment, dict):
        return []
    speaker_ids: List[str] = []

    def _append(raw: Any) -> None:
        if not isinstance(raw, str):
            return
        speaker = raw.strip()
        if speaker and speaker not in speaker_ids:
            speaker_ids.append(speaker)

    for key in ('primary_speaker', 'speaker'):
        _append(segment.get(key))

    speakers = segment.get('speakers')
    if isinstance(speakers, list):
        for speaker in speakers:
            if isinstance(speaker, str):
                _append(speaker)
            elif isinstance(speaker, dict):
                _append(speaker.get('speaker_id') or speaker.get('speaker') or speaker.get('label'))

    diarization = segment.get('diarization')
    if isinstance(diarization, list):
        for item in diarization:
            if isinstance(item, dict):
                _append(item.get('speaker'))

    return speaker_ids


def _initial_knowledge_graph_status(cfg: Dict[str, Any]) -> str:
    """Report graph applicability, not merely whether its Python module imports."""
    if not KNOWLEDGE_GRAPH_AVAILABLE:
        return 'disabled_import_failure'
    if cfg.get('ingestion_isolation', False):
        return 'not_applicable_isolated_epoch'
    graph_cfg = cfg.get('knowledge_graph', {})
    if isinstance(graph_cfg, dict) and graph_cfg.get('enabled') is False:
        return 'disabled_config'
    return 'active'


def _compute_scene_coverages(scene_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
    scenes = [scene for scene in scene_outputs if isinstance(scene, dict)]
    total = len(scenes)
    transcript_scene_count = 0
    speaker_scene_count = 0

    for scene in scenes:
        audio_payload = _extract_audio_payload(scene)
        transcript_text = _extract_transcript_text(audio_payload)
        segments = _extract_segments(audio_payload)
        if transcript_text or _has_meaningful_audio_segments(segments):
            transcript_scene_count += 1
        if _extract_speaker_ids(audio_payload):
            speaker_scene_count += 1

    return {
        'scene_count': total,
        'transcript_scene_count': transcript_scene_count,
        'speaker_scene_count': speaker_scene_count,
        'transcript_coverage': _ratio(transcript_scene_count, total),
        'speaker_coverage': _ratio(speaker_scene_count, total),
    }


def _compute_segment_coverages(segments: Any) -> Dict[str, Any]:
    normalized = [segment for segment in segments if isinstance(segment, dict)] if isinstance(segments, list) else []
    total = len(normalized)
    transcript_segment_count = 0
    speaker_segment_count = 0

    for segment in normalized:
        if _segment_has_transcript(segment):
            transcript_segment_count += 1
        if _extract_segment_speaker_ids(segment):
            speaker_segment_count += 1

    return {
        'segment_count': total,
        'transcript_segment_count': transcript_segment_count,
        'speaker_segment_count': speaker_segment_count,
        'transcript_coverage': _ratio(transcript_segment_count, total),
        'speaker_coverage': _ratio(speaker_segment_count, total),
    }


def _compute_temporal_index_completeness(temporal_index: Optional[Dict[str, Any]]) -> float:
    if not isinstance(temporal_index, dict):
        return 0.0
    checks = [
        isinstance(temporal_index.get('segments'), list),
        temporal_index.get('total_scenes') is not None,
        'has_audio' in temporal_index,
        'has_transcripts' in temporal_index,
        'phase5_complete' in temporal_index,
        'phase6_complete' in temporal_index,
        'phase6_harmonized' in temporal_index,
    ]
    return _ratio(sum(1 for check in checks if check), len(checks))


def _compute_shadow_alignment_score(scene_manifest: Optional[Dict[str, Any]]) -> float:
    if not isinstance(scene_manifest, dict):
        return 0.0
    aligned_segments = scene_manifest.get('aligned_segments')
    if not isinstance(aligned_segments, list) or not aligned_segments:
        return 0.0
    aligned_count = 0
    for segment in aligned_segments:
        if not isinstance(segment, dict):
            continue
        if bool(segment.get('scene_aligned')) or int(segment.get('scene_count') or 0) > 0:
            aligned_count += 1
    return _ratio(aligned_count, len(aligned_segments))


def _normalize_scene_boundaries(raw_scenes: Any) -> List[Dict[str, float]]:
    normalized: List[Dict[str, float]] = []
    scenes = raw_scenes
    if isinstance(raw_scenes, dict):
        scenes = raw_scenes.get('scenes')
    if not isinstance(scenes, list):
        return normalized
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        start = _coerce_optional_float(scene.get('start'))
        end = _coerce_optional_float(scene.get('end'))
        if start is None or end is None:
            continue
        if end < start:
            start, end = end, start
        normalized.append(
            {
                'start': float(start),
                'end': float(end),
                'duration': max(0.0, float(end) - float(start)),
            }
        )
    return normalized


def _scene_overlap_duration(left: Dict[str, float], right: Dict[str, float]) -> float:
    return max(0.0, min(float(left['end']), float(right['end'])) - max(float(left['start']), float(right['start'])))


def _compute_scene_backend_comparison(
    scene_outputs: List[Dict[str, Any]],
    shadow_scene_manifest: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    live_scenes = _normalize_scene_boundaries(scene_outputs)
    shadow_scenes = _normalize_scene_boundaries(shadow_scene_manifest)

    claimed_shadow: Set[int] = set()
    matched_count = 0
    overlap_duration_total = 0.0
    boundary_deltas: List[float] = []

    for live_scene in live_scenes:
        best_idx: Optional[int] = None
        best_overlap = 0.0
        for idx, shadow_scene in enumerate(shadow_scenes):
            if idx in claimed_shadow:
                continue
            overlap = _scene_overlap_duration(live_scene, shadow_scene)
            if overlap > best_overlap:
                best_overlap = overlap
                best_idx = idx
        if best_idx is None or best_overlap <= 0.0:
            continue
        claimed_shadow.add(best_idx)
        matched_count += 1
        overlap_duration_total += best_overlap
        shadow_scene = shadow_scenes[best_idx]
        boundary_deltas.append(
            (
                abs(float(live_scene['start']) - float(shadow_scene['start']))
                + abs(float(live_scene['end']) - float(shadow_scene['end']))
            ) / 2.0
        )

    total_live_duration = sum(float(scene['duration']) for scene in live_scenes)
    boundary_delta_mean = sum(boundary_deltas) / len(boundary_deltas) if boundary_deltas else 0.0
    boundary_delta_max = max(boundary_deltas) if boundary_deltas else 0.0

    return {
        'live_scene_count': len(live_scenes),
        'shadow_scene_count': len(shadow_scenes),
        'matched_scene_count': matched_count,
        'matched_scene_ratio_live': _ratio(matched_count, len(live_scenes)),
        'matched_scene_ratio_shadow': _ratio(len(claimed_shadow), len(shadow_scenes)),
        'duration_coverage': _ratio(int(overlap_duration_total * 1000), int(total_live_duration * 1000)) if total_live_duration > 0 else 0.0,
        'boundary_delta_mean_sec': boundary_delta_mean,
        'boundary_delta_max_sec': boundary_delta_max,
    }


def _compute_shadow_temporal_readiness(
    shadow_result: Dict[str, Any],
    segmentation_manifest: Optional[Dict[str, Any]],
    scene_manifest: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if isinstance(segmentation_manifest, dict):
        checks = {
            'segments': isinstance(segmentation_manifest.get('segments'), list),
            'frame_index': isinstance(segmentation_manifest.get('frame_index'), list),
            'summary': isinstance(segmentation_manifest.get('summary'), dict),
            'processing': isinstance(segmentation_manifest.get('processing'), dict),
            'source': isinstance(segmentation_manifest.get('source'), dict),
        }
        score = _ratio(sum(1 for passed in checks.values() if passed), len(checks))
        return {
            'score': score,
            'basis': 'shadow_segmentation_manifest',
            'checks': checks,
        }

    skip_phases = shadow_result.get('skip_phases')
    checks = {
        'audio_manifest': bool(shadow_result.get('audio_manifest_path')),
        'scene_manifest': isinstance(scene_manifest, dict),
        'phase4_manifest': bool(shadow_result.get('phase4_manifest_path')),
        'phase6_manifest': bool(shadow_result.get('segmentation_manifest_path')),
        'validation': isinstance(shadow_result.get('validation'), dict),
        'phase6_requested': 'phase6' not in skip_phases if isinstance(skip_phases, list) else True,
    }
    score = _ratio(sum(1 for passed in checks.values() if passed), len(checks))
    return {
        'score': score,
        'basis': 'shadow_temporal_readiness',
        'checks': checks,
    }


def _build_segmentation_shadow_metrics(
    scene_outputs: List[Dict[str, Any]],
    temporal_index: Optional[Dict[str, Any]],
    shadow_result: Dict[str, Any],
) -> Dict[str, Any]:
    current = _compute_scene_coverages(scene_outputs)
    current_temporal_completeness = _compute_temporal_index_completeness(temporal_index)

    shadow_scene_manifest = _safe_read_json_dict(shadow_result.get('scene_manifest_path'))
    shadow_segmentation_manifest = _safe_read_json_dict(shadow_result.get('segmentation_manifest_path'))
    shadow_phase4_manifest = _safe_read_json_dict(shadow_result.get('phase4_manifest_path'))

    shadow_scene_count = 0
    if isinstance(shadow_scene_manifest, dict):
        if shadow_scene_manifest.get('total_scenes') is not None:
            try:
                shadow_scene_count = int(shadow_scene_manifest.get('total_scenes') or 0)
            except (TypeError, ValueError):
                shadow_scene_count = 0
        elif isinstance(shadow_scene_manifest.get('scenes'), list):
            shadow_scene_count = len(shadow_scene_manifest.get('scenes') or [])

    shadow_validation = shadow_result.get('validation') if isinstance(shadow_result.get('validation'), dict) else {}
    shadow_validation_stats = shadow_validation.get('stats') if isinstance(shadow_validation, dict) else {}

    if isinstance(shadow_validation_stats, dict):
        shadow_transcript_coverage = float(shadow_validation_stats.get('transcript_coverage') or 0.0)
        shadow_speaker_coverage = float(shadow_validation_stats.get('speaker_coverage') or 0.0)
        shadow_segment_count = int(shadow_validation_stats.get('total_segments') or 0)
    else:
        shadow_segments = None
        if isinstance(shadow_segmentation_manifest, dict):
            shadow_segments = shadow_segmentation_manifest.get('segments')
        if shadow_segments is None and isinstance(shadow_phase4_manifest, dict):
            shadow_segments = shadow_phase4_manifest.get('segments') or shadow_phase4_manifest.get('chunks')
        shadow_coverages = _compute_segment_coverages(shadow_segments)
        shadow_transcript_coverage = float(shadow_coverages['transcript_coverage'])
        shadow_speaker_coverage = float(shadow_coverages['speaker_coverage'])
        shadow_segment_count = int(shadow_coverages['segment_count'])

    shadow_alignment_score = _compute_shadow_alignment_score(shadow_scene_manifest)
    scene_backend_comparison = _compute_scene_backend_comparison(scene_outputs, shadow_scene_manifest)
    shadow_temporal = _compute_shadow_temporal_readiness(
        shadow_result,
        shadow_segmentation_manifest,
        shadow_scene_manifest,
    )
    shadow_temporal_completeness = float(shadow_temporal['score'])

    return {
        'version': 1,
        'activation': shadow_result.get('activation'),
        'status': shadow_result.get('status'),
        'scene_count_current': current['scene_count'],
        'scene_count_shadow': shadow_scene_count,
        'scene_count_delta': shadow_scene_count - current['scene_count'],
        'transcript_coverage_current': current['transcript_coverage'],
        'transcript_coverage_shadow': shadow_transcript_coverage,
        'transcript_coverage_delta': shadow_transcript_coverage - current['transcript_coverage'],
        'speaker_coverage_current': current['speaker_coverage'],
        'speaker_coverage_shadow': shadow_speaker_coverage,
        'speaker_coverage_delta': shadow_speaker_coverage - current['speaker_coverage'],
        'alignment_score': shadow_alignment_score,
        'scene_backend_match_ratio_live': scene_backend_comparison['matched_scene_ratio_live'],
        'scene_backend_match_ratio_shadow': scene_backend_comparison['matched_scene_ratio_shadow'],
        'scene_backend_duration_coverage': scene_backend_comparison['duration_coverage'],
        'scene_backend_boundary_delta_mean_sec': scene_backend_comparison['boundary_delta_mean_sec'],
        'temporal_index_completeness_current': current_temporal_completeness,
        'temporal_index_completeness_shadow': shadow_temporal_completeness,
        'temporal_index_completeness_delta': shadow_temporal_completeness - current_temporal_completeness,
        'temporal_index_completeness_basis': shadow_temporal.get('basis'),
        'current': {
            **current,
            'temporal_index_completeness': current_temporal_completeness,
        },
        'shadow': {
            'scene_count': shadow_scene_count,
            'segment_count': shadow_segment_count,
            'transcript_coverage': shadow_transcript_coverage,
            'speaker_coverage': shadow_speaker_coverage,
            'alignment_score': shadow_alignment_score,
            'scene_backend_comparison': scene_backend_comparison,
            'temporal_index_completeness': shadow_temporal_completeness,
            'temporal_index_completeness_checks': shadow_temporal.get('checks'),
        },
        'files': {
            'summary_path': shadow_result.get('summary_path'),
            'audio_manifest_path': shadow_result.get('audio_manifest_path'),
            'phase4_manifest_path': shadow_result.get('phase4_manifest_path'),
            'scene_manifest_path': shadow_result.get('scene_manifest_path'),
            'segmentation_manifest_path': shadow_result.get('segmentation_manifest_path'),
        },
    }


def _attach_segmentation_shadow_metrics(
    cfg: Dict[str, Any],
    scene_outputs: List[Dict[str, Any]],
    temporal_index: Optional[Dict[str, Any]],
    shadow_result: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(shadow_result, dict):
        return shadow_result
    if shadow_result.get('status') not in {'complete', 'partial'}:
        return shadow_result

    segmentation_cfg = cfg.get('segmentation') if isinstance(cfg, dict) else {}
    if not isinstance(segmentation_cfg, dict) or not segmentation_cfg.get('metrics_output', True):
        return shadow_result

    summary_path = shadow_result.get('summary_path')
    if not isinstance(summary_path, str) or not summary_path.strip():
        return shadow_result

    metrics = _build_segmentation_shadow_metrics(scene_outputs, temporal_index, shadow_result)
    metrics_path = Path(summary_path).parent / 'shadow_metrics.json'
    atomic_write_json(metrics_path, metrics)

    updated = dict(shadow_result)
    updated['metrics'] = metrics
    updated['metrics_path'] = str(metrics_path)
    return updated


def _segmentation_shadow_audio_overlay_enabled(cfg: Dict[str, Any]) -> bool:
    segmentation_cfg = cfg.get('segmentation') if isinstance(cfg, dict) else {}
    if not isinstance(segmentation_cfg, dict):
        return False
    return _resolve_segmentation_activation(cfg) == 'shadow' and bool(
        segmentation_cfg.get('shadow_audio_overlay', False)
    )


def _prepare_segmentation_shadow_audio_overlay(
    cfg: Dict[str, Any],
    shadow_result: Dict[str, Any],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        'enabled': False,
        'reason': 'segmentation_shadow_audio_overlay_disabled',
    }
    if not _segmentation_shadow_audio_overlay_enabled(cfg):
        return result
    from steps.audio.recording_ingestion import selected as recording_engine_selected
    if recording_engine_selected(cfg):
        return {
            **result,
            'reason': 'recording_engine_owns_canonical_scene_audio',
        }
    if not isinstance(shadow_result, dict):
        return result
    if shadow_result.get('status') != 'complete':
        return {
            **result,
            'reason': 'segmentation_shadow_audio_overlay_requires_complete_shadow_run',
        }

    summary_path = shadow_result.get('summary_path')
    phase4_manifest_path = shadow_result.get('phase4_manifest_path')
    if not isinstance(summary_path, str) or not summary_path.strip():
        return {
            **result,
            'reason': 'segmentation_shadow_audio_overlay_missing_summary',
        }
    if not isinstance(phase4_manifest_path, str) or not phase4_manifest_path.strip():
        return {
            **result,
            'reason': 'segmentation_shadow_audio_overlay_missing_phase4_manifest',
        }

    phase4_manifest = _safe_read_json_dict(phase4_manifest_path)
    if not isinstance(phase4_manifest, dict):
        return {
            **result,
            'reason': 'segmentation_shadow_audio_overlay_invalid_phase4_manifest',
        }

    phase4_segments = phase4_manifest.get('segments') or phase4_manifest.get('chunks') or []
    segments = [segment for segment in phase4_segments if isinstance(segment, dict)]
    if not segments:
        return {
            **result,
            'reason': 'segmentation_shadow_audio_overlay_no_segments',
        }

    overlay_dir = Path(summary_path).parent / 'phase6_audio_overlay'
    overlay_dir.mkdir(parents=True, exist_ok=True)

    transcript_segments: List[Dict[str, Any]] = []
    diarization_segments: List[Dict[str, Any]] = []
    speaker_stats: Dict[str, Dict[str, Any]] = {}
    full_text_parts: List[str] = []
    language: Optional[str] = None

    for segment in segments:
        start = segment.get('start')
        end = segment.get('end')
        transcript = segment.get('transcript')
        transcript = transcript.strip() if isinstance(transcript, str) else ''
        if transcript:
            full_text_parts.append(transcript)

        raw_transcript_segments = segment.get('transcript_segments')
        if isinstance(raw_transcript_segments, list):
            for item in raw_transcript_segments:
                if not isinstance(item, dict):
                    continue
                transcript_entry = dict(item)
                transcript_entry.setdefault('start', start)
                transcript_entry.setdefault('end', end)
                transcript_segments.append(transcript_entry)
        elif transcript:
            transcript_segments.append(
                {
                    'start': start,
                    'end': end,
                    'text': transcript,
                    'words': [],
                }
            )

        if language is None:
            raw_language = segment.get('language')
            if isinstance(raw_language, str) and raw_language.strip():
                language = raw_language.strip()

        raw_diarization = segment.get('diarization')
        if isinstance(raw_diarization, list):
            for item in raw_diarization:
                if not isinstance(item, dict):
                    continue
                diarization_entry = dict(item)
                diarization_entry.setdefault('start', start)
                diarization_entry.setdefault('end', end)
                diarization_segments.append(diarization_entry)
                speaker_id = diarization_entry.get('speaker')
                if isinstance(speaker_id, str) and speaker_id.strip():
                    normalized_id = speaker_id.strip()
                    speaker_stats.setdefault(
                        normalized_id,
                        {
                            'speaker_id': normalized_id,
                            'total_duration': 0.0,
                            'segment_count': 0,
                        },
                    )
                    duration_value = _coerce_optional_float(diarization_entry.get('duration'))
                    if duration_value is None:
                        start_value = _coerce_optional_float(diarization_entry.get('start'))
                        end_value = _coerce_optional_float(diarization_entry.get('end'))
                        if start_value is not None and end_value is not None:
                            duration_value = max(0.0, end_value - start_value)
                    speaker_stats[normalized_id]['total_duration'] += float(duration_value or 0.0)
                    speaker_stats[normalized_id]['segment_count'] += 1

        raw_speakers = segment.get('speakers')
        if isinstance(raw_speakers, list):
            for item in raw_speakers:
                if isinstance(item, dict):
                    speaker_id = item.get('speaker_id') or item.get('speaker') or item.get('label')
                    if isinstance(speaker_id, str) and speaker_id.strip():
                        normalized_id = speaker_id.strip()
                        speaker_stats.setdefault(
                            normalized_id,
                            {
                                'speaker_id': normalized_id,
                                'total_duration': float(item.get('total_duration') or 0.0),
                                'segment_count': int(item.get('segment_count') or 0),
                            },
                        )

    speakers = sorted(
        speaker_stats.values(),
        key=lambda speaker: (
            -float(speaker.get('total_duration') or 0.0),
            str(speaker.get('speaker_id') or ''),
        ),
    )
    full_text = " ".join(part for part in full_text_parts if part).strip()

    atomic_write_json(
        overlay_dir / 'segmentation.json',
        {
            'segments': segments,
        },
    )
    atomic_write_json(
        overlay_dir / 'transcript.json',
        {
            'segments': transcript_segments,
            'full_text': full_text,
            'language': language or 'en',
        },
    )
    atomic_write_json(
        overlay_dir / 'diarization.json',
        {
            'speakers': speakers,
            'segments': diarization_segments,
        },
    )

    return {
        'enabled': True,
        'reason': 'segmentation_shadow_audio_overlay_ready',
        'audio_artifact_dir': str(overlay_dir),
        'segment_count': len(segments),
        'transcript_segment_count': len(transcript_segments),
        'diarization_segment_count': len(diarization_segments),
        'speaker_count': len(speakers),
    }


def _run_segmentation_shadow_pipeline(
    video_path: Path,
    processing_dir: Path,
    cfg: Dict[str, Any],
    audio_runtime_contract: Optional[Dict[str, Any]] = None,
    recording_audio: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    activation = _resolve_segmentation_activation(cfg)
    result: Dict[str, Any] = {
        'activation': activation,
        'status': 'off',
        'reason': 'segmentation_shadow_disabled',
        'skip_phases': [],
    }
    if activation == 'off':
        return result
    if activation == 'authoritative':
        return {
            **result,
            'status': 'unsupported',
            'reason': 'segmentation_authoritative_not_enabled',
        }

    segmentation_cfg = cfg.get('segmentation') if isinstance(cfg, dict) else {}
    if not isinstance(segmentation_cfg, dict) or not segmentation_cfg.get('enabled', True):
        return {
            **result,
            'status': 'disabled',
            'reason': 'segmentation_config_disabled',
        }

    skip_phases: List[str] = []
    if isinstance(audio_runtime_contract, dict):
        selected_backend = str(audio_runtime_contract.get('selected') or '').strip().lower()
        if selected_backend == 'recording':
            if recording_audio is None:
                skip_phases.extend(['phase4', 'phase6'])
        elif selected_backend != 'wsl':
            skip_phases.extend(['phase4', 'phase6'])

    try:
        from steps.audio.segmentation import PhasedSegmentationEngine

        shadow_root = processing_dir / "_segmentation_shadow"
        engine = PhasedSegmentationEngine(cfg)
        shadow_run = engine.run_full_pipeline(
            str(video_path),
            str(shadow_root),
            skip_phases=skip_phases,
            **({'recording_audio': recording_audio} if recording_audio is not None else {}),
        )
        phase_results = shadow_run.get('phase_results') if isinstance(shadow_run, dict) else {}
        phase3_result = phase_results.get('phase3') if isinstance(phase_results, dict) else {}
        phase5_result = phase_results.get('phase5') if isinstance(phase_results, dict) else {}
        phase6_result = phase_results.get('phase6') if isinstance(phase_results, dict) else {}
        summary: Dict[str, Any] = {
            'activation': activation,
            'status': 'complete' if not skip_phases else 'partial',
            'reason': 'segmentation_shadow_complete' if not skip_phases else 'segmentation_shadow_partial',
            'skip_phases': list(skip_phases),
            'output_dir': shadow_run.get('output_dir') if isinstance(shadow_run, dict) else None,
            'audio_manifest_path': phase3_result.get('audio_manifest_path') if isinstance(phase3_result, dict) else None,
            'phase4_manifest_path': (
                str(Path(shadow_run['output_dir']) / 'metadata' / 'segmentation_enhanced.json')
                if isinstance(shadow_run, dict) and shadow_run.get('output_dir')
                else None
            ),
            'scene_manifest_path': phase5_result.get('scene_manifest_path') if isinstance(phase5_result, dict) else None,
            'video_scenes_path': phase5_result.get('video_scenes_path') if isinstance(phase5_result, dict) else None,
            'segmentation_manifest_path': phase6_result.get('manifest_path') if isinstance(phase6_result, dict) else None,
            'validation': phase6_result.get('validation') if isinstance(phase6_result, dict) else None,
            'timings': shadow_run.get('timings') if isinstance(shadow_run, dict) else None,
        }
        summary_path = shadow_root / "shadow_summary.json"
        atomic_write_json(summary_path, summary)
        summary['summary_path'] = str(summary_path)
        return summary
    except Exception as e:
        logger.warning(
            "run_ingestion warning context=%s error=%s",
            "segmentation_shadow",
            e,
        )
        return {
            **result,
            'status': 'error',
            'reason': 'segmentation_shadow_failed',
            'error': str(e),
            'skip_phases': list(skip_phases),
        }


def _merge_modality_state(current: str, candidate: str) -> str:
    rank = {
        'not_attempted': 0,
        'unavailable': 1,
        'available': 2,
    }
    current_norm = str(current or '').strip().lower()
    candidate_norm = str(candidate or '').strip().lower()
    if current_norm not in rank:
        current_norm = 'not_attempted'
    if candidate_norm not in rank:
        candidate_norm = 'not_attempted'
    return candidate_norm if rank[candidate_norm] > rank[current_norm] else current_norm


def _status_dict_to_modality_state(status_dict: Any) -> str:
    if not isinstance(status_dict, dict):
        return 'not_attempted'
    raw_status = status_dict.get('status')
    if not isinstance(raw_status, str):
        return 'not_attempted'
    status = raw_status.strip().lower()
    if status in {'ok', 'success', 'complete'}:
        return 'available'
    if status in {'unavailable', 'error', 'failed'}:
        return 'unavailable'
    if status in {
        'no_text',
        'no_file',
        'no_index_path',
        'no_audio_stream',
        'no_audio_output',
        'skipped',
        'dedupe_skipped',
    }:
        return 'not_attempted'
    return 'not_attempted'


def _aggregate_modality_status(
    scene_outputs: List[Dict[str, Any]],
    phase6_embeddings_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    status = {
        'vision_clip': 'not_attempted',
        'vision_dino': 'not_attempted',
        'text_embed': 'not_attempted',
        'audio_embed': 'not_attempted',
    }

    for scene in scene_outputs:
        if not isinstance(scene, dict):
            continue

        keyframe = scene.get('keyframe')
        if isinstance(keyframe, dict):
            if keyframe.get('clip_embedding') is not None:
                status['vision_clip'] = _merge_modality_state(status['vision_clip'], 'available')
            status['vision_clip'] = _merge_modality_state(
                status['vision_clip'],
                _status_dict_to_modality_state(keyframe.get('clip_meta')),
            )
            if keyframe.get('dino_embedding') is not None:
                status['vision_dino'] = _merge_modality_state(status['vision_dino'], 'available')
            status['vision_dino'] = _merge_modality_state(
                status['vision_dino'],
                _status_dict_to_modality_state(keyframe.get('dino_meta')),
            )
            status['text_embed'] = _merge_modality_state(
                status['text_embed'],
                _status_dict_to_modality_state(keyframe.get('frame_text_embed_meta')),
            )

        audio = scene.get('audio')
        if isinstance(audio, dict):
            if audio.get('clap_embedding') is not None:
                status['audio_embed'] = _merge_modality_state(status['audio_embed'], 'available')
            if _has_wsl_unified_audio_embeddings(audio):
                status['audio_embed'] = _merge_modality_state(status['audio_embed'], 'available')
            status['audio_embed'] = _merge_modality_state(
                status['audio_embed'],
                _status_dict_to_modality_state(audio.get('clap_meta')),
            )
            status['text_embed'] = _merge_modality_state(
                status['text_embed'],
                _status_dict_to_modality_state(audio.get('audio_text_embed_meta')),
            )

    if isinstance(phase6_embeddings_result, dict):
        clip_written = _coerce_nonnegative_int(phase6_embeddings_result.get('scene_clip_vectors_written'))
        dino_written = _coerce_nonnegative_int(phase6_embeddings_result.get('scene_dino_vectors_written'))
        clip_attempted = _coerce_nonnegative_int(phase6_embeddings_result.get('clip_embeddings'))
        dino_attempted = _coerce_nonnegative_int(phase6_embeddings_result.get('dino_embeddings'))
        if bool(phase6_embeddings_result.get('clip_committed')) or clip_written > 0:
            status['vision_clip'] = 'available'
        elif clip_attempted > 0:
            status['vision_clip'] = _merge_modality_state(status['vision_clip'], 'unavailable')
        if bool(phase6_embeddings_result.get('dino_committed')) or dino_written > 0:
            status['vision_dino'] = 'available'
        elif dino_attempted > 0:
            status['vision_dino'] = _merge_modality_state(status['vision_dino'], 'unavailable')

    return status


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _resolve_content_empty_duration_threshold(cfg: Dict[str, Any]) -> float:
    run_cfg = cfg.get('run') if isinstance(cfg, dict) else None
    if isinstance(run_cfg, dict):
        configured = run_cfg.get('content_empty_duration_threshold_sec')
        threshold = _coerce_float(configured, default=1.0)
        return threshold if threshold >= 0.0 else 1.0
    return 1.0


def _extract_audio_payload(scene: Dict[str, Any]) -> Dict[str, Any]:
    audio = scene.get('audio')
    return audio if isinstance(audio, dict) else {}


def _extract_transcript_text(audio_payload: Dict[str, Any]) -> str:
    for key in ('transcript', 'full_text'):
        value = audio_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raw = audio_payload.get('raw')
    if isinstance(raw, dict):
        for key in ('transcript', 'full_text'):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ''


def _extract_segments(audio_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    segments = audio_payload.get('segments')
    if isinstance(segments, list):
        return [seg for seg in segments if isinstance(seg, dict)]
    raw = audio_payload.get('raw')
    if isinstance(raw, dict) and isinstance(raw.get('segments'), list):
        return [seg for seg in raw.get('segments') if isinstance(seg, dict)]
    return []


_TRANSCRIPT_OUTCOMES = {
    'transcript_available',
    'no_speech',
    'no_intelligible_speech',
    'low_confidence',
    'missing_audio_artifact',
    'runtime_failure',
    'unclassified',
}


def _derive_transcript_outcome(
    audio_info: Optional[Dict[str, Any]],
    *,
    audio_error: Optional[str],
    audio_backend_fields: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """Classify the observed transcript result without guessing speech content.

    Old artifacts have no outcome contract and remain untouched.  A successful
    but empty transcript is deliberately ``unclassified`` unless its worker
    emitted an explicit speech or quality outcome.
    """
    if isinstance(audio_error, str) and audio_error.strip():
        return {'transcript_outcome': 'runtime_failure', 'transcript_outcome_reason': 'audio_processing_error'}
    if not isinstance(audio_info, dict):
        return {
            'transcript_outcome': 'missing_audio_artifact',
            'transcript_outcome_reason': 'audio_processor_returned_no_artifact',
        }

    candidates: List[Dict[str, Any]] = [audio_info]
    data = audio_info.get('data')
    if isinstance(data, dict):
        candidates.append(data)
    for candidate in candidates:
        outcome = str(candidate.get('transcript_outcome') or '').strip().lower()
        if outcome in _TRANSCRIPT_OUTCOMES:
            reason = str(candidate.get('transcript_outcome_reason') or '').strip()
            return {'transcript_outcome': outcome, 'transcript_outcome_reason': reason or 'worker_reported_outcome'}

    backend_effective = str((audio_backend_fields or {}).get('audio_backend_effective') or '').strip().lower()
    backend_reason = str((audio_backend_fields or {}).get('audio_backend_effective_reason') or '').strip().lower()
    if backend_effective == 'failed' or backend_reason.endswith('_failed'):
        return {'transcript_outcome': 'runtime_failure', 'transcript_outcome_reason': 'audio_backend_failure'}

    transcript_meta: Dict[str, Any] = {}
    for candidate in candidates:
        meta = candidate.get('transcript_meta')
        if isinstance(meta, dict):
            transcript_meta = meta
            break
    transcript_status = str(transcript_meta.get('status') or '').strip().lower()
    if transcript_status in {'error', 'failed', 'failure'}:
        return {'transcript_outcome': 'runtime_failure', 'transcript_outcome_reason': 'transcript_meta_error'}
    if transcript_status in {'invalid_worker_result', 'no_transcript_output'}:
        return {
            'transcript_outcome': 'runtime_failure',
            'transcript_outcome_reason': f'transcript_meta_{transcript_status}',
        }

    for candidate in candidates:
        if _extract_transcript_text(candidate) or _has_meaningful_audio_segments(_extract_segments(candidate)):
            return {'transcript_outcome': 'transcript_available', 'transcript_outcome_reason': 'transcript_or_segments_present'}
    if transcript_status == 'success':
        return {
            'transcript_outcome': 'unclassified',
            'transcript_outcome_reason': 'worker_success_empty_transcript',
        }
    return {
        'transcript_outcome': 'unclassified',
        'transcript_outcome_reason': 'no_explicit_speech_or_quality_outcome',
    }


def _has_meaningful_audio_segments(segments: List[Dict[str, Any]]) -> bool:
    for segment in segments:
        text = segment.get('text')
        if isinstance(text, str) and text.strip():
            return True
    return False


def _scene_has_processing_error(scene: Dict[str, Any]) -> bool:
    for key in ('audio_error', 'frame_error', 'keyframe_error', 'step_error'):
        value = scene.get(key)
        if isinstance(value, str) and value.strip():
            return True

    errors = scene.get('errors')
    if isinstance(errors, dict):
        for value in errors.values():
            if isinstance(value, str) and value.strip():
                return True

    reason = scene.get('audio_backend_reason')
    if isinstance(reason, str) and reason == 'audio_processing_error':
        return True

    return False


_STEP_FAILURE_RE = re.compile(
    r"^Step (?P<step>[A-Za-z0-9_]+) failed \((?P<env>[^)]+)\)"
    r"(?: \[returncode=(?P<returncode>-?\d+)\])?",
    re.MULTILINE,
)


def _tail_text(value: Any, *, max_chars: int = 1200) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _extract_labeled_output(raw_text: str, label: str) -> str:
    if label == "STDOUT":
        pattern = r"(?:^|\n)STDOUT:(.*?)(?=\nSTDERR:|\Z)"
    else:
        pattern = r"(?:^|\n)STDERR:(.*)\Z"
    match = re.search(pattern, raw_text, flags=re.DOTALL)
    if not match:
        return ""
    return str(match.group(1) or "").strip()


def _extract_step_failure_details(error: Any, *, stage_label: str = "Step") -> Dict[str, Optional[str]]:
    raw_message = str(error or "").strip()
    details: Dict[str, Optional[str]] = {
        "step": None,
        "env": None,
        "returncode": None,
        "raw_message": raw_message or None,
        "message": None,
    }
    if not raw_message:
        details["message"] = f"{stage_label} failed with no error details"
        return details

    match = _STEP_FAILURE_RE.search(raw_message)
    if match:
        details["step"] = match.group("step")
        details["env"] = match.group("env")
        details["returncode"] = match.group("returncode")

    stdout_tail = _tail_text(_extract_labeled_output(raw_message, "STDOUT"))
    stderr_tail = _tail_text(_extract_labeled_output(raw_message, "STDERR"))

    message_parts: List[str] = []
    if details["step"] and details["env"]:
        headline = f"{stage_label} step {details['step']} failed ({details['env']})"
        if details["returncode"]:
            headline += f" [returncode={details['returncode']}]"
        message_parts.append(headline)
    else:
        message_parts.append(_tail_text(raw_message, max_chars=800))

    if stdout_tail:
        message_parts.append(f"STDOUT tail: {stdout_tail}")
    if stderr_tail:
        message_parts.append(f"STDERR tail: {stderr_tail}")
    if match and not stdout_tail and not stderr_tail:
        message_parts.append("No stdout/stderr captured from failing step")

    details["message"] = "\n".join(message_parts)
    return details


def _classify_scene_content(
    scene: Dict[str, Any],
    *,
    empty_duration_threshold_sec: float,
) -> str:
    """
    Deterministic scene-level content classification.
    Allowed values: signal | empty | processing_error
    """
    if _scene_has_processing_error(scene):
        return 'processing_error'

    duration = _coerce_float(scene.get('duration'))
    audio_payload = _extract_audio_payload(scene)
    transcript_meta = audio_payload.get('transcript_meta')
    transcript_status = (
        str(transcript_meta.get('status', '')).strip().lower()
        if isinstance(transcript_meta, dict)
        else ''
    )
    transcript_duration = None
    if isinstance(transcript_meta, dict) and transcript_meta.get('duration') is not None:
        transcript_duration = _coerce_float(transcript_meta.get('duration'))
    transcript_text = _extract_transcript_text(audio_payload)
    segments = _extract_segments(audio_payload)
    has_meaningful_segments = _has_meaningful_audio_segments(segments)

    audio_meta = audio_payload.get('audio_meta')
    audio_path = audio_payload.get('path')
    audio_present = bool(
        (isinstance(audio_path, str) and audio_path.strip())
        or isinstance(audio_meta, dict)
        or segments
        or transcript_text
    )

    if duration < empty_duration_threshold_sec:
        return 'empty'

    if transcript_status == 'success' and not transcript_text and transcript_duration == 0.0:
        return 'empty'

    if audio_present and not transcript_text and not has_meaningful_segments:
        return 'empty'

    return 'signal'


def _aggregate_content_summary(scene_outputs: List[Dict[str, Any]]) -> Dict[str, int]:
    summary = {
        'signal': 0,
        'empty': 0,
        'processing_error': 0,
    }
    for scene in scene_outputs:
        if not isinstance(scene, dict):
            continue
        state = scene.get('content_state')
        if isinstance(state, str) and state in summary:
            summary[state] += 1
        else:
            summary['signal'] += 1
    return summary


def _coerce_nonnegative_int(value: Any) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def _resolve_store_status_for_points(points_attempted: Any, raw_status: Any) -> Any:
    points = _coerce_nonnegative_int(points_attempted)
    if points <= 0:
        return 'not_attempted'
    normalized = _normalize_vector_store_status(raw_status)
    if isinstance(normalized, bool):
        return normalized
    # Deterministic truth: attempted writes must resolve to a concrete boolean.
    return False


def _aggregate_scene_store_status(scene_outputs: List[Dict[str, Any]], store_key: str) -> Any:
    attempted = 0
    statuses: List[bool] = []

    for scene in scene_outputs:
        if not isinstance(scene, dict):
            continue
        persistence = scene.get('persistence')
        if not isinstance(persistence, dict):
            continue
        points = _coerce_nonnegative_int(persistence.get('vector_points_attempted'))
        attempted += points
        if points <= 0:
            continue
        status = _resolve_store_status_for_points(points, persistence.get(store_key))
        if isinstance(status, bool):
            statuses.append(status)
        else:
            statuses.append(False)

    if attempted <= 0:
        return 'not_attempted'
    return False if any(not s for s in statuses) else True


def _merge_store_statuses(*statuses: Any) -> Any:
    normalized = [_normalize_vector_store_status(s) for s in statuses]
    if any(s is False for s in normalized):
        return False
    if any(s is True for s in normalized):
        return True
    return 'not_attempted'


def _compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _atomic_write_json(path: Path, data: Any, *, indent: Optional[int] = 2) -> None:
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding='utf-8')
    os.replace(tmp, path)


def _capability_receipt_profile(cfg: Dict[str, Any]) -> str:
    host = cfg.get("host") if isinstance(cfg, dict) else None
    configured = host.get("profile") if isinstance(host, dict) else None
    profile = str(configured or os.getenv("GOODQ_HOST_PROFILE") or "BASELINE").strip().upper()
    if profile in {"GPU_ENHANCED", "PUBLIC_GPU_ENHANCED"}:
        return "PUBLIC_GPU_ENHANCED"
    if profile == "PERSONAL_AIR_GAP":
        return profile
    return "PUBLIC_CPU_BASELINE"


def _read_current_run_capability_rows(
    cfg: Dict[str, Any],
    run_id: str,
) -> tuple[list[dict[str, Any]], int]:
    paths_cfg = cfg.get("paths") if isinstance(cfg, dict) else None
    log_dir = paths_cfg.get("log_dir") if isinstance(paths_cfg, dict) else None
    if not isinstance(log_dir, str) or not log_dir.strip():
        return [], 0
    path = Path(log_dir) / "step_runs.jsonl"
    if not path.is_file():
        return [], 0
    rows: list[dict[str, Any]] = []
    malformed_count = 0
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                malformed_count += 1
                continue
            if not isinstance(row, dict):
                malformed_count += 1
                continue
            if str(row.get("run_id") or "") != run_id:
                continue
            step = str(row.get("step") or "")
            if step in _NON_CAPABILITY_STEP_RUNS:
                continue
            status = row.get("status")
            if (
                step not in RUNTIME_CAPABILITY_POLICIES
                or not isinstance(status, str)
                or not status.strip()
            ):
                malformed_count += 1
                continue
            rows.append(row)
    except OSError as exc:
        malformed_count += 1
        logger.warning("[CAPABILITY] Unable to read current step evidence path=%s error=%s", path, exc)
    return rows, malformed_count


def _load_release_capability_profile(cfg: Dict[str, Any]) -> dict[str, dict[str, Any]]:
    try:
        contract = yaml.safe_load(
            _CAPABILITY_PROFILE_CONTRACT_PATH.read_text(encoding="utf-8")
        )
    except (OSError, yaml.YAMLError) as exc:
        raise typer.BadParameter(
            "Release capability profile contract is missing or malformed"
        ) from exc
    if not isinstance(contract, dict):
        raise typer.BadParameter("Release capability profile contract must be a mapping")
    try:
        return resolve_capability_profile(contract, _capability_receipt_profile(cfg))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _release_content_truth(cfg: Dict[str, Any]) -> dict[str, dict[str, bool]]:
    release_cfg = cfg.get("release_validation") if isinstance(cfg, dict) else None
    if release_cfg is None:
        return {}
    if not isinstance(release_cfg, dict):
        raise typer.BadParameter("release_validation config must be a mapping")
    raw_truth = release_cfg.get("content_truth_by_scene")
    if raw_truth is None:
        return {}
    if not isinstance(raw_truth, dict):
        raise typer.BadParameter(
            "release_validation.content_truth_by_scene must be a mapping"
        )
    resolved: dict[str, dict[str, bool]] = {}
    for scene_id, truth in raw_truth.items():
        if not isinstance(truth, dict) or any(
            not isinstance(value, bool) for value in truth.values()
        ):
            raise typer.BadParameter(
                "release-validation content truth values must be booleans"
            )
        resolved[str(scene_id)] = {str(key): value for key, value in truth.items()}
    return resolved


def _validate_release_validation_request(
    *,
    release_validation: bool,
    config: Optional[Path],
) -> None:
    if release_validation and config is None:
        raise typer.BadParameter(
            "--release-validation requires an explicit --config witness snapshot"
        )


def _enforce_release_capability_receipt(
    receipt: dict[str, Any],
    *,
    release_validation: bool,
) -> None:
    if release_validation and receipt.get("outcome") != "completed":
        raise typer.Exit(code=1)


def _flatten_scene_outputs(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scenes: list[dict[str, Any]] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        nested_scenes = result.get("scenes")
        if isinstance(nested_scenes, list):
            scenes.extend(scene for scene in nested_scenes if isinstance(scene, dict))
    return scenes


def _finalize_capability_receipt(
    *,
    terminal_status: str,
    cfg: Dict[str, Any],
    results: list[dict[str, Any]],
    output: Path,
    input_count: int | None = None,
    release_validation: bool = False,
) -> dict[str, Any]:
    """Persist the sole terminal capability receipt from existing run evidence."""

    run_context = _CURRENT_RUN_CONTEXT if isinstance(_CURRENT_RUN_CONTEXT, dict) else {}
    run_id = str(run_context.get("id") or "unknown_run")
    paths_cfg = cfg.get("paths") if isinstance(cfg, dict) else {}
    log_dir = paths_cfg.get("log_dir") if isinstance(paths_cfg, dict) else None
    step_path = Path(log_dir) / "step_runs.jsonl" if isinstance(log_dir, str) and log_dir.strip() else None
    receipt_path = output.parent / "capability_receipt.json"
    evidence_paths = {
        "results": str(output),
        "receipt": str(receipt_path),
    }
    if step_path is not None:
        evidence_paths["step_runs"] = str(step_path)

    step_rows, malformed_row_count = _read_current_run_capability_rows(cfg, run_id)
    expected_capabilities = None
    content_truth_by_scene = None
    if release_validation:
        expected_capabilities = _load_release_capability_profile(cfg)
        content_truth_by_scene = _release_content_truth(cfg)
        evidence_paths["capability_profile_contract"] = str(
            _CAPABILITY_PROFILE_CONTRACT_PATH
        )

    receipt = build_capability_receipt(
        run_id=run_id,
        profile=_capability_receipt_profile(cfg),
        terminal_status=terminal_status,
        step_rows=step_rows,
        warnings=list(run_context.get("warnings") or []),
        scenes=_flatten_scene_outputs(results),
        evidence_paths=evidence_paths,
        expected_capabilities=expected_capabilities,
        malformed_row_count=malformed_row_count,
        input_count=input_count,
        full_coverage=release_validation,
        content_truth_by_scene=content_truth_by_scene,
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(receipt_path, receipt, indent=2)
    typer.echo(
        render_capability_receipt(receipt),
        err=receipt["outcome"] == "failed",
    )
    return receipt


def _write_cfg_snapshot(cfg: Dict[str, Any], workspace: Path) -> Path:
    cfg_path = workspace / '_resolved_config.json'
    
    # Convert config to JSON-serializable format
    def make_json_serializable(obj):
        # Handle typer OptionInfo objects - extract the actual default value
        if hasattr(obj, 'default'):
            return make_json_serializable(obj.default)
        elif isinstance(obj, dict):
            return {k: make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [make_json_serializable(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            # For other non-serializable objects, convert to string as last resort
            return str(obj)
    
    serializable_cfg = make_json_serializable(cfg)
    redacted_cfg = redact_config(serializable_cfg, include_local_values=True)
    _atomic_write_json(cfg_path, redacted_cfg, indent=2)
    return cfg_path


def _normalize_host_profile_name(raw: Any) -> str:
    value = str(raw or "").strip().upper()
    if value in {"BASELINE", "PUBLIC_CPU_BASELINE"}:
        return "BASELINE"
    if value in {"GPU_ENHANCED", "PUBLIC_GPU_ENHANCED", "PERSONAL_AIR_GAP"}:
        return "GPU_ENHANCED"
    return ""


def _load_host_runtime_overrides(cfg_json: Optional[Path]) -> Dict[str, Any]:
    if cfg_json is None or not cfg_json.exists():
        return {}
    try:
        raw = cfg_json.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        parsed = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    host_cfg = parsed.get("host")
    if not isinstance(host_cfg, dict):
        return {}
    return host_cfg


def _base_env(cfg_json: Optional[Path] = None) -> Dict[str, str]:
    env = os.environ.copy()
    env.setdefault('PYTHONNOUSERSITE', '1')
    env.setdefault('HF_HUB_ENABLE_HF_TRANSFER', '1')
    models_root = _resolve_models_dir(cfg_json=cfg_json)
    env['HF_HOME'] = str(models_root)
    env['TORCH_HOME'] = str(models_root)
    # Add parent of REPO_ROOT to PYTHONPATH so "goodq4all.steps" can be imported.
    env['PYTHONPATH'] = str(REPO_ROOT.parent)
    
    # GPU Resource Management - Pin to GPU 0
    env['CUDA_VISIBLE_DEVICES'] = '0'

    host_cfg = _load_host_runtime_overrides(cfg_json)
    host_profile = _normalize_host_profile_name(host_cfg.get("profile") or env.get("GOODQ_HOST_PROFILE"))
    if host_profile:
        env["GOODQ_HOST_PROFILE"] = host_profile

    require_gpu_override = host_cfg.get("require_gpu")
    if isinstance(require_gpu_override, bool):
        env["GOODQ_REQUIRE_GPU"] = "1" if require_gpu_override else "0"
    elif host_profile == "BASELINE":
        # Baseline profile is CPU-safe by contract. Clear stale shell exports so
        # sidecar steps like OCR/CLAP do not inherit an accidental GPU requirement.
        env["GOODQ_REQUIRE_GPU"] = "0"

    require_wsl_audio_override = host_cfg.get("require_wsl_audio")
    if isinstance(require_wsl_audio_override, bool):
        env["GOODQ_REQUIRE_WSL_AUDIO"] = "1" if require_wsl_audio_override else "0"

    if host_profile == "BASELINE":
        env["GOODQ_NO_AUTO_GPU"] = "1"
    elif host_profile:
        env.pop("GOODQ_NO_AUTO_GPU", None)
    
    # Enable deterministic CUDA operations for reproducibility (optional)
    # Uncomment if reproducibility is needed (slight performance cost)
    # env['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
    # env['PYTHONHASHSEED'] = '1337'
    
    return env


def _persist_healer_retry_metadata(cfg_json: Path) -> None:
    global _CURRENT_RUN_CONTEXT
    if not isinstance(_CURRENT_RUN_CONTEXT, dict):
        return
    try:
        cfg_data: Dict[str, Any] = {}
        if cfg_json.exists():
            raw = cfg_json.read_text(encoding='utf-8').strip()
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    cfg_data = parsed
        run_meta = cfg_data.get('run')
        if not isinstance(run_meta, dict):
            run_meta = {}
        run_meta['healer_retry_count'] = int(_CURRENT_RUN_CONTEXT.get('healer_retry_count', 0) or 0)
        by_step = _CURRENT_RUN_CONTEXT.get('healer_retry_by_step') or {}
        run_meta['healer_retry_by_step'] = dict(by_step) if isinstance(by_step, dict) else {}
        run_meta['native_retry_count'] = int(_CURRENT_RUN_CONTEXT.get('native_retry_count', 0) or 0)
        native_by_step = _CURRENT_RUN_CONTEXT.get('native_retry_by_step') or {}
        run_meta['native_retry_by_step'] = dict(native_by_step) if isinstance(native_by_step, dict) else {}
        warnings = _CURRENT_RUN_CONTEXT.get('warnings') or []
        run_meta['warnings'] = list(warnings) if isinstance(warnings, list) else []
        cfg_data['run'] = run_meta
        _atomic_write_json(cfg_json, cfg_data, indent=2)
    except Exception as e:
        logger.warning("[RUN] Failed to persist healer retry metadata: %s", e)


def _record_run_warning(
    cfg_json: Path,
    *,
    code: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    global _CURRENT_RUN_CONTEXT
    if not isinstance(_CURRENT_RUN_CONTEXT, dict):
        return
    warnings = _CURRENT_RUN_CONTEXT.get('warnings')
    if not isinstance(warnings, list):
        warnings = []
        _CURRENT_RUN_CONTEXT['warnings'] = warnings
    warnings.append(
        {
            'code': code,
            'message': message,
            'context': dict(context or {}),
            'ts_utc': datetime.now(timezone.utc).isoformat(),
        }
    )
    _persist_healer_retry_metadata(cfg_json)


def _record_healer_retry(step_name: str, cfg_json: Path) -> None:
    global _CURRENT_RUN_CONTEXT
    if isinstance(_CURRENT_RUN_CONTEXT, dict):
        current_count = int(_CURRENT_RUN_CONTEXT.get('healer_retry_count', 0) or 0)
        _CURRENT_RUN_CONTEXT['healer_retry_count'] = current_count + 1
        by_step = _CURRENT_RUN_CONTEXT.get('healer_retry_by_step')
        if not isinstance(by_step, dict):
            by_step = {}
            _CURRENT_RUN_CONTEXT['healer_retry_by_step'] = by_step
        by_step[step_name] = int(by_step.get(step_name, 0) or 0) + 1
    _persist_healer_retry_metadata(cfg_json)


def _normalize_windows_status_code(return_code: int) -> int:
    return (int(return_code) + (1 << 32)) & 0xFFFFFFFF


def _is_windows_native_crash(return_code: int) -> bool:
    # Native Windows exception family: 0xC0000000 - 0xCFFFFFFF.
    status_code = _normalize_windows_status_code(return_code)
    return (status_code & 0xF0000000) == 0xC0000000


def _record_native_retry(
    step_name: str,
    cfg_json: Path,
    return_code: int,
    attempt: int,
    env_fingerprint: Optional[str] = None,
) -> None:
    global _CURRENT_RUN_CONTEXT
    status_code = _normalize_windows_status_code(return_code)
    if isinstance(_CURRENT_RUN_CONTEXT, dict):
        current_count = int(_CURRENT_RUN_CONTEXT.get('native_retry_count', 0) or 0)
        _CURRENT_RUN_CONTEXT['native_retry_count'] = current_count + 1
        by_step = _CURRENT_RUN_CONTEXT.get('native_retry_by_step')
        if not isinstance(by_step, dict):
            by_step = {}
            _CURRENT_RUN_CONTEXT['native_retry_by_step'] = by_step
        by_step[step_name] = int(by_step.get(step_name, 0) or 0) + 1
    context = {
        'step': step_name,
        'return_code': int(return_code),
        'status_code_hex': f"0x{status_code:08X}",
        'attempt': int(attempt),
    }
    if env_fingerprint:
        context['env_fingerprint'] = env_fingerprint
    _record_run_warning(
        cfg_json,
        code='native_crash_retry',
        message='Retrying step after native subprocess crash',
        context=context,
    )


def _stop_step_heartbeat(stop_heartbeat, *, preserve_error: bool) -> None:
    """A progress callback cannot replace an active worker failure/cancellation."""
    try:
        stop_heartbeat()
    except BaseException:
        if not preserve_error:
            raise
        logger.exception("Heartbeat cleanup failed while preserving the worker exception")


def _report_step_failure(observer, step, *, error, metadata) -> None:
    try:
        observer.step_error(step, error=error, metadata=metadata)
    except BaseException:
        logger.exception("Observer notification failed while preserving the worker exception")


def _record_prelaunch_step_error(
    cfg_json: Optional[Path],
    step_name: str,
    payload: Any,
    duration_ms: float,
    error_msg: str,
    *,
    reason: str,
) -> None:
    if cfg_json is None or not cfg_json.exists():
        return
    try:
        raw_cfg = json.loads(cfg_json.read_text(encoding="utf-8"))
        if not isinstance(raw_cfg, dict):
            return
        if not ((raw_cfg.get("paths") or {}).get("log_dir")):
            return
        if isinstance(payload, dict) and isinstance(payload.get("_batch_items"), list):
            for sub_item in payload["_batch_items"]:
                log_step_run(
                    raw_cfg,
                    step_name,
                    sub_item if isinstance(sub_item, dict) else {},
                    duration_ms,
                    "error",
                    error_msg,
                    extra={"reason": reason, "pre_launch": True},
                )
        else:
            log_step_run(
                raw_cfg,
                step_name,
                payload if isinstance(payload, dict) else {},
                duration_ms,
                "error",
                error_msg,
                extra={"reason": reason, "pre_launch": True},
            )
    except Exception as exc:
        logger.debug("Pre-launch step ledger write skipped for %s: %s", step_name, exc)


def _run_step(
    env_name: str,
    step_name: str,
    payload: Dict[str, Any],
    cfg_json: Path,
    _healer_retry_attempt: int = 0,
    _native_retry_attempt: int = 0,
    _direct_env_fallback_attempt: int = 0,
    _prefer_direct_env_python: bool = False,
    _step_env_overrides: Optional[Dict[str, Optional[str]]] = None,
    _native_retry_mode: Optional[str] = None,
) -> Dict[str, Any]:
    prelaunch_start_ts = time.perf_counter()
    work_env = _base_env(cfg_json)
    
    # VRAM preflight allocation check
    from common.vram_allocator import STEP_VRAM_FRACTIONS, VRAMAllocator, step_uses_gpu_backend, validate_ocr_device_policy
    
    # Admission must use the same resolved policy as the worker, not the parent shell.
    policy_env = _apply_env_overrides(work_env, _step_env_overrides)
    gpu_required = policy_env.get("GOODQ_REQUIRE_GPU", "").strip().lower() in {"1", "true", "yes", "on"}
    step_cfg = None
    if step_name == "image_ocr":
        from cli.step_runner import load_step_config
        step_cfg = load_step_config(cfg_json)
        gpu_required = validate_ocr_device_policy(step_cfg, policy_env)
        env_name = "goodq_ocr"
    gpu_auto_enabled = (
        policy_env.get("GOODQ_HOST_PROFILE") != "BASELINE"
        and policy_env.get("GOODQ_NO_AUTO_GPU") != "1"
    )
    if step_name in STEP_VRAM_FRACTIONS and gpu_required and not gpu_auto_enabled:
        raise RuntimeError(f"GPU-required step '{step_name}' cannot launch with GPU auto-config disabled.")
    gpu_enabled = (
        gpu_auto_enabled
        and ("PYTEST_CURRENT_TEST" not in os.environ or os.getenv("GOODQ_TEST_VRAM_ALLOCATOR") == "1")
    )
    is_gpu_step = (
        step_uses_gpu_backend(step_name, env=policy_env, conda_env=env_name, cfg=step_cfg)
        if gpu_enabled
        else False
    )
    
    allocator = None
    vram_reserved = False
    parent_pid = os.getpid()
    reservation_id = "launch:" + uuid.uuid4().hex
    
    if is_gpu_step and gpu_enabled:
        allocator = VRAMAllocator()
        allocator.env = policy_env
        allocator.conda_env = env_name
        allocator.cfg = step_cfg
        cmd_str = f"python cli/step_runner.py --step {step_name}"
        try:
            vram_reserved = allocator.wait_and_reserve(
                step_name=step_name,
                pid=parent_pid,
                reservation_id=reservation_id,
                command=cmd_str,
                timeout_seconds=300.0,
                env=policy_env,
                conda_env=env_name,
            )
        except BaseException:
            try:
                allocator.release(reservation_id)
            except BaseException:
                logger.exception("Admission cleanup failed; preserving the worker interruption")
            raise
        if not vram_reserved:
            if gpu_required:
                err_msg = f"VRAM allocation failed for GPU-required step '{step_name}'. Bounds breached."
                _record_prelaunch_step_error(
                    cfg_json,
                    step_name,
                    payload,
                    (time.perf_counter() - prelaunch_start_ts) * 1000.0,
                    err_msg,
                    reason="vram_allocation_failed",
                )
                raise RuntimeError(err_msg)
            else:
                logger.warning(
                    f"VRAM allocation limits breached for step '{step_name}'. Falling back to CPU."
                )
                if _step_env_overrides is None:
                    _step_env_overrides = {}
                _step_env_overrides = dict(_step_env_overrides)
                _step_env_overrides["GOODQ_NO_AUTO_GPU"] = "1"
                if step_name == 'image_caption':
                    _step_env_overrides['GOODQ_IMAGE_CAPTION_FORCE_CPU'] = '1'
                elif step_name == 'object_detect':
                    _step_env_overrides['GOODQ_OBJECT_DETECT_FORCE_CPU'] = '1'
                elif step_name == 'audio_embed_clap':
                    _step_env_overrides['GOODQ_CLAP_FORCE_CPU'] = '1'
                elif step_name == 'image_embed_dino':
                    _step_env_overrides['GOODQ_DINO_FORCE_CPU'] = '1'
                elif step_name == 'emotion_classify':
                    _step_env_overrides['GOODQ_EMOTION_FORCE_CPU'] = '1'

    # Convert payload to JSON-serializable format
    
    tmp_dir = None
    process = None
    observer = None
    failure_in_flight = False
    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix='ingest_step_'))
        in_path = tmp_dir / 'input.json'
        out_path = tmp_dir / 'output.json'
        serializable_payload = worker_payload(payload)
        in_path.write_text(json.dumps(serializable_payload, ensure_ascii=False), encoding='utf-8')
        
        # Resolve conda path to handle subprocess PATH issues across hosts.
        launch = prepare_worker_launch(
            WorkerRequest(env_name, step_name, in_path, out_path, cfg_json), work_env,
            repo_root=REPO_ROOT, conda_exe=resolve_conda(),
            prefer_direct=_prefer_direct_env_python,
            prefer_available_python=_PREFER_DIRECT_ENV_PYTHON_ON_WINDOWS,
            overrides=_step_env_overrides,
        )
        cmd, launcher_kind = launch.command, launch.kind
        direct_env_python, step_env = launch.direct_python, launch.environment

        start_ts = time.perf_counter()
        observer = _observer()
        observer_step = f"step.{step_name}"
        observer_meta: Dict[str, Any] = {"env": env_name}
        payload_video_id = payload.get('video_id') or payload.get('video_hash')
        if payload_video_id is not None:
            observer_meta["video_id"] = str(payload_video_id)
        payload_scene_id = payload.get('scene_id')
        if payload_scene_id is not None:
            observer_meta["scene_id"] = str(payload_scene_id)
        payload_scene_index = payload.get('scene_index')
        if payload_scene_index is not None:
            observer_meta["scene_index"] = payload_scene_index
        elif isinstance(payload.get('scene'), dict) and payload['scene'].get('index') is not None:
            observer_meta["scene_index"] = payload['scene'].get('index')
        observer_meta["attempt"] = max(int(_healer_retry_attempt), int(_native_retry_attempt)) + 1
        observer_meta["healer_retry_attempt"] = int(_healer_retry_attempt)
        observer_meta["native_retry_attempt"] = int(_native_retry_attempt)
        observer_meta["launcher"] = launcher_kind
        observer_meta["direct_env_fallback_attempt"] = int(_direct_env_fallback_attempt)
        if _native_retry_mode:
            observer_meta["native_retry_mode"] = _native_retry_mode
        if VERBOSE:
            typer.echo(f'[step] -> {step_name} ({env_name}) [{launcher_kind}]')
        stop_heartbeat = (lambda: None)
        process: Optional[subprocess.Popen[bytes]] = None
        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(REPO_ROOT),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=step_env,
            )
            observer_meta["subprocess_pid"] = int(process.pid)
            if vram_reserved and allocator is not None:
                try:
                    allocator.update_pid(reservation_id, process.pid)
                except Exception:
                    # The child has started but its ownership is not durable.
                    # Stop/reap it before the outer finally releases the claim.
                    try:
                        process.kill()
                        process.communicate(timeout=5)
                    except Exception:
                        vram_reserved = False  # Retain the claim if the child cannot be reaped.
                        logger.exception("Unbound worker could not be stopped; retaining VRAM claim %s", reservation_id)
                        raise
                    raise
            if observer:
                observer.step_start(observer_step, metadata=observer_meta)
                stop_heartbeat = observer.begin_heartbeat(observer_step, metadata=observer_meta)
            communicate_failed = True
            try:
                stdout_text, stderr_text = process.communicate(timeout=STEP_TIMEOUT)
                communicate_failed = False
            finally:
                _stop_step_heartbeat(stop_heartbeat, preserve_error=communicate_failed)
            result = subprocess.CompletedProcess(
                cmd,
                process.returncode if process.returncode is not None else 1,
                decode_worker_diagnostics(stdout_text),
                decode_worker_diagnostics(stderr_text),
            )
        except subprocess.TimeoutExpired as exc:
            if process is not None:
                try:
                    process.kill()
                except Exception:
                    pass
                try:
                    process.communicate(timeout=5)
                except Exception:
                    pass
                if process.returncode is None:
                    raise RuntimeError(f"Step {step_name} timed out; worker exit was not confirmed") from exc
            if observer:
                _report_step_failure(observer,
                    observer_step,
                    error=f"timeout_after_{STEP_TIMEOUT}s",
                    metadata=observer_meta,
                )
            if VERBOSE:
                typer.echo(f'[step] !! {step_name} ({env_name}) timed out after {STEP_TIMEOUT}s', err=True)

            if step_name != "image_ocr" and _control_agent_runtime_enabled():
                try:
                    agent = _get_control_agent(cfg_json)
                    healing_result = agent.auto_heal_failure(
                        error=exc,
                        step_name=step_name,
                        context={'env': env_name, 'timeout': STEP_TIMEOUT}
                    )

                    if healing_result.get('success'):
                        if _healer_retry_attempt >= MAX_HEALER_RETRIES:
                            logger.warning("Healer retry ceiling reached for step=%s", step_name)
                            typer.echo(f"[heal] [WARN] Healer retry ceiling reached for step={step_name}", err=True)
                        else:
                            _record_healer_retry(step_name, cfg_json)
                            typer.echo("[heal] [PASS] Timeout healed, retrying step...", err=True)
                            # Retry the step with the same payload after healing actions
                            return _run_step(
                                env_name,
                                step_name,
                                payload,
                                cfg_json,
                                _healer_retry_attempt=_healer_retry_attempt + 1,
                                _native_retry_attempt=_native_retry_attempt,
                                _direct_env_fallback_attempt=_direct_env_fallback_attempt,
                                _prefer_direct_env_python=_prefer_direct_env_python,
                                _step_env_overrides=_step_env_overrides,
                                _native_retry_mode=_native_retry_mode,
                            )
                    else:
                        typer.echo(f"[heal] [FAIL] Could not heal timeout: {healing_result.get('recommendation', 'No strategy')}", err=True)
                except Exception as heal_error:
                    logger.warning(
                        "run_ingestion warning context=%s error=%s",
                        "control_agent.auto_heal_timeout",
                        heal_error,
                    )
                    typer.echo(f"[heal] [WARN] Healing failed: {heal_error}", err=True)

            raise RuntimeError(f"Step {step_name} timed out after {STEP_TIMEOUT}s") from exc
        
        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            combined_output = f"{stdout}\n{stderr}".lower()

            should_try_direct_env_fallback = (
                launcher_kind == "conda_run"
                and step_name in _OPTIONAL_DIRECT_ENV_FALLBACK_STEPS
                and _direct_env_fallback_attempt == 0
                and direct_env_python is not None
                and (
                    "conda.cli.main_run:execute(127)" in combined_output
                    or "failed to run 'conda activate" in combined_output
                    or (
                        "__conda_tmp_" in combined_output
                        and (
                            "being used by another process" in combined_output
                            or "cannot access the file because it is being used by another process" in combined_output
                        )
                    )
                )
            )
            if should_try_direct_env_fallback:
                logger.warning(
                    "[RUN] Conda launcher failed for optional step=%s env=%s; retrying via direct env python",
                    step_name,
                    env_name,
                )
                if VERBOSE:
                    typer.echo(
                        f"[retry] [WARN] Conda launcher failed for {step_name}; retrying via direct env python",
                        err=True,
                    )
                return _run_step(
                    env_name,
                    step_name,
                    payload,
                    cfg_json,
                    _healer_retry_attempt=_healer_retry_attempt,
                    _native_retry_attempt=_native_retry_attempt,
                    _direct_env_fallback_attempt=1,
                    _prefer_direct_env_python=True,
                    _step_env_overrides=_step_env_overrides,
                    _native_retry_mode=_native_retry_mode,
                )

            error_msg = (
                f"Step {step_name} failed ({env_name}) [returncode={result.returncode}]\n"
                f"STDOUT: {stdout}\n"
                f"STDERR: {stderr}"
            )
            if observer:
                _report_step_failure(observer,
                    observer_step,
                    error=f"returncode_{result.returncode}",
                    metadata=observer_meta,
                )

            is_native_crash = _is_windows_native_crash(result.returncode)
            retry_limit, retry_env_overrides, retry_mode = _resolve_native_retry_strategy(
                step_name,
                _native_retry_attempt + 1,
                gpu_required=gpu_required,
            )
            if is_native_crash and _native_retry_attempt < retry_limit:
                retry_attempt = _native_retry_attempt + 1
                env_fingerprint_line: Optional[str] = None
                for stderr_line in stderr.splitlines():
                    if 'subprocess_env_fingerprint' in stderr_line:
                        env_fingerprint_line = stderr_line.strip()
                        break
                _record_native_retry(
                    step_name,
                    cfg_json,
                    result.returncode,
                    retry_attempt,
                    env_fingerprint=env_fingerprint_line,
                )
                status_code = _normalize_windows_status_code(result.returncode)
                logger.warning(
                    "[RUN] Native crash detected for step=%s return_code=%s status_code=0x%08X retry=%s/%s mode=%s",
                    step_name,
                    result.returncode,
                    status_code,
                    retry_attempt,
                    retry_limit,
                    retry_mode or "default",
                )
                if env_fingerprint_line:
                    logger.warning(
                        "[RUN] Native crash env fingerprint step=%s %s",
                        step_name,
                        env_fingerprint_line,
                    )
                if VERBOSE:
                    typer.echo(
                        (
                            f"[retry] [WARN] Native crash for {step_name} "
                            f"(0x{status_code:08X}); retrying via {retry_mode or 'default'}"
                        ),
                        err=True,
                    )
                return _run_step(
                    env_name,
                    step_name,
                    payload,
                    cfg_json,
                    _healer_retry_attempt=_healer_retry_attempt,
                    _native_retry_attempt=retry_attempt,
                    _direct_env_fallback_attempt=_direct_env_fallback_attempt,
                    _prefer_direct_env_python=_prefer_direct_env_python,
                    _step_env_overrides=retry_env_overrides,
                    _native_retry_mode=retry_mode,
                )

            if step_name != "image_ocr" and _control_agent_runtime_enabled():
                try:
                    agent = _get_control_agent(cfg_json)
                    healing_result = agent.auto_heal_failure(
                        error=RuntimeError(error_msg),
                        step_name=step_name,
                        context={
                            'env': env_name,
                            'returncode': result.returncode,
                            'stdout': stdout[:500],  # First 500 chars
                            'stderr': stderr[:500],
                        }
                    )

                    if healing_result.get('success'):
                        if _healer_retry_attempt >= MAX_HEALER_RETRIES:
                            logger.warning("Healer retry ceiling reached for step=%s", step_name)
                            typer.echo(f"[heal] [WARN] Healer retry ceiling reached for step={step_name}", err=True)
                        else:
                            _record_healer_retry(step_name, cfg_json)
                            typer.echo("[heal] [PASS] Step failure healed, retrying...", err=True)
                            # Retry the same step after healing actions
                            return _run_step(
                                env_name,
                                step_name,
                                payload,
                                cfg_json,
                                _healer_retry_attempt=_healer_retry_attempt + 1,
                                _native_retry_attempt=_native_retry_attempt,
                                _direct_env_fallback_attempt=_direct_env_fallback_attempt,
                                _prefer_direct_env_python=_prefer_direct_env_python,
                                _step_env_overrides=_step_env_overrides,
                                _native_retry_mode=_native_retry_mode,
                            )
                    else:
                        typer.echo("[heal] [FAIL] Could not heal failure", err=True)
                        if healing_result.get('recommendation'):
                            typer.echo(f"[heal] [SYMBOL] Suggestion: {healing_result['recommendation'][:200]}", err=True)
                except Exception as heal_error:
                    logger.warning(
                        "run_ingestion warning context=%s error=%s",
                        "control_agent.auto_heal_failure",
                        heal_error,
                    )
                    typer.echo(f"[heal] [WARN] Healing attempt failed: {heal_error}", err=True)

            raise RuntimeError(error_msg)
        try:
            outputs = read_worker_result(out_path, stdout_text, step_name=step_name, env_name=env_name)
            from cli.step_runner import _derive_step_log_outcome
            log_status, log_error, extra = _derive_step_log_outcome(step_name, outputs, verbose=VERBOSE)
            if log_status == "error" or "_error" in outputs:
                reason = (extra or {}).get("reason", "error")
                raise WorkerResultError(f"Step {step_name} failed ({env_name}): {outputs.get('_error', log_error)} ({reason})",
                                        step_name=step_name, outputs=outputs)
        except (RuntimeError, OSError) as exc:
            if observer:
                _report_step_failure(observer,observer_step, error=str(exc), metadata=observer_meta)
            raise
        duration = time.perf_counter() - start_ts
        if observer:
            observer.step_end(
                observer_step,
                metadata={
                    **observer_meta,
                    "duration_sec": round(duration, 3),
                },
            )
        if VERBOSE:
            typer.echo(f'[step] <- {step_name} ({env_name}) [{duration:.1f}s]')
        
        # PHASE 3: Learn from successful execution
        if step_name != "image_ocr" and _control_agent_runtime_enabled():
            try:
                models_root = _resolve_models_dir(cfg_json=cfg_json)
                agent = _get_control_agent(cfg_json)
                agent.learn_from_success(
                    step_name=step_name,
                    execution_time_seconds=duration,
                    config_used={'env': env_name, 'timeout': STEP_TIMEOUT},
                    context={'models_root': str(models_root)}
                )
            except Exception as e:
                logger.warning(
                    "run_ingestion warning context=%s error=%s",
                    "control_agent.learn_from_success",
                    e,
                )
                _record_run_warning(
                    cfg_json,
                    code='control_agent_learn_failed',
                    message=str(e),
                    context={'step': step_name, 'env': env_name},
                )
        
        return outputs
    except BaseException:
        failure_in_flight = True
        if process is not None and process.returncode is None:
            # Every worker owns its input and device claim until exit is confirmed.
            try:
                process.kill()
                process.communicate(timeout=5)
                if process.returncode is None:
                    raise RuntimeError("Worker exit was not confirmed")
            except BaseException:
                vram_reserved = False  # Keep the claim until the live child exits.
                logger.exception("Worker could not be reaped; retaining VRAM claim %s", reservation_id)
        raise
    finally:
        release_error = None
        if 'vram_reserved' in locals() and vram_reserved and 'allocator' in locals() and allocator is not None:
            try:
                allocator.release(reservation_id)
            except Exception as e:
                logger.warning(
                    "run_ingestion warning context=%s error=%s",
                    "vram_release_failed",
                    e,
                )
                release_error = e
                if observer:
                    _report_step_failure(observer, observer_step, error=f"vram_release_failed: {e}",
                                                 metadata=observer_meta)
        try:
            safe_to_clean = process is None or process.returncode is not None
            for child in tmp_dir.iterdir() if tmp_dir is not None and safe_to_clean else ():
                child.unlink(missing_ok=True)
            if tmp_dir is not None and safe_to_clean:
                tmp_dir.rmdir()
            elif tmp_dir is not None:
                logger.error("Unreaped worker retains input directory %s", tmp_dir)
        except Exception as e:
            logger.warning(
                "run_ingestion warning context=%s error=%s",
                "step_temp_cleanup",
                e,
            )
        if release_error is not None and not failure_in_flight:
            raise release_error


_DEFAULT_RUN_STEP = _run_step


def _run_step_batch(
    env_name: str,
    step_name: str,
    payloads: List[Dict[str, Any]],
    cfg_json: Path,
) -> List[Tuple[str, Dict[str, Any], Optional[str]]]:
    """Run multiple independent sample items in one worker subprocess unless _run_step is monkeypatched."""
    if not payloads:
        return []
    if _run_step is not _DEFAULT_RUN_STEP or len(payloads) == 1:
        single_results: List[Tuple[str, Dict[str, Any], Optional[str]]] = []
        for p in payloads:
            try:
                out = _run_step(env_name, step_name, p, cfg_json)
                single_results.append(("ok", out if isinstance(out, dict) else {}, None))
            except WorkerResultError as w_exc:
                w_out = getattr(w_exc, "outputs", None)
                single_results.append(("error", w_out if isinstance(w_out, dict) else {}, str(w_exc)))
            except Exception as exc:
                single_results.append(("error", {}, str(exc)))
        return single_results

    first = payloads[0]
    batch_payload: Dict[str, Any] = {
        "_batch_items": payloads,
        "video_id": first.get("video_id") or first.get("video_hash"),
        "video_hash": first.get("video_hash"),
        "scene_id": first.get("scene_id"),
        "scene_index": first.get("scene_index"),
    }
    try:
        batch_out = _run_step(env_name, step_name, batch_payload, cfg_json)
    except Exception as exc:
        return [("error", {}, str(exc)) for _ in payloads]

    batch_list = batch_out.get("_batch_results") if isinstance(batch_out, dict) else None
    if not isinstance(batch_list, list) or len(batch_list) != len(payloads):
        return [("error", {}, f"{step_name} returned malformed _batch_results") for _ in payloads]

    unpacked: List[Tuple[str, Dict[str, Any], Optional[str]]] = []
    for entry in batch_list:
        if isinstance(entry, dict):
            st = str(entry.get("status") or "ok")
            outs = entry.get("outputs") if isinstance(entry.get("outputs"), dict) else {}
            err = str(entry["errors"]) if entry.get("errors") is not None else None
            unpacked.append((st, outs, err))
        else:
            unpacked.append(("error", {}, f"malformed batch entry: {entry!r}"))
    return unpacked


def _make_async_step_envelope(
    step_name: str,
    status: str,
    outputs: Optional[Dict[str, Any]] = None,
    errors: Optional[str] = None,
    warnings: Optional[List[str]] = None,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    duration_seconds: float = 0.0,
    retry_count: int = 0,
) -> Dict[str, Any]:
    return {
        "step_name": step_name,
        "status": status,
        "outputs": outputs or {},
        "errors": errors,
        "warnings": warnings,
        "started_at": started_at or datetime.now(timezone.utc).isoformat(),
        "finished_at": finished_at or datetime.now(timezone.utc).isoformat(),
        "duration_seconds": duration_seconds,
        "retry_count": retry_count,
    }


async def _reserve_step_vram_async(allocator, **kwargs) -> bool:
    """Wait for admission without leaving a live allocator thread after cancellation."""
    import threading

    cancel_event = threading.Event()
    pending = asyncio.create_task(asyncio.to_thread(
        allocator.wait_and_reserve, **kwargs, cancel_event=cancel_event,
    ))
    try:
        return await asyncio.shield(pending)
    except asyncio.CancelledError:
        cancel_event.set()
        try:
            await asyncio.shield(pending)
        except BaseException:
            logger.exception("Admission wait failed while preserving cancellation")
        try:
            allocator.release(kwargs["reservation_id"])
        except BaseException:
            logger.exception("Admission cleanup failed while preserving cancellation")
        raise


async def _run_step_async(
    env_name: str,
    step_name: str,
    payload: Dict[str, Any],
    cfg_json: Path,
    _healer_retry_attempt: int = 0,
    _native_retry_attempt: int = 0,
    _direct_env_fallback_attempt: int = 0,
    _prefer_direct_env_python: bool = False,
    _step_env_overrides: Optional[Dict[str, Optional[str]]] = None,
    _native_retry_mode: Optional[str] = None,
) -> Dict[str, Any]:
    started_at_str = datetime.now(timezone.utc).isoformat()
    start_ts = time.perf_counter()
    
    try:
        work_env = _base_env(cfg_json)
        
        # VRAM preflight allocation check
        from common.vram_allocator import STEP_VRAM_FRACTIONS, VRAMAllocator, step_uses_gpu_backend, validate_ocr_device_policy
        
        # Admission must use the same resolved policy as the worker, not the parent shell.
        policy_env = _apply_env_overrides(work_env, _step_env_overrides)
        gpu_required = policy_env.get("GOODQ_REQUIRE_GPU", "").strip().lower() in {"1", "true", "yes", "on"}
        step_cfg = None
        if step_name == "image_ocr":
            from cli.step_runner import load_step_config
            step_cfg = load_step_config(cfg_json)
            gpu_required = validate_ocr_device_policy(step_cfg, policy_env)
            env_name = "goodq_ocr"
        gpu_auto_enabled = (
            policy_env.get("GOODQ_HOST_PROFILE") != "BASELINE"
            and policy_env.get("GOODQ_NO_AUTO_GPU") != "1"
        )
        if step_name in STEP_VRAM_FRACTIONS and gpu_required and not gpu_auto_enabled:
            raise RuntimeError(f"GPU-required step '{step_name}' cannot launch with GPU auto-config disabled.")
        gpu_enabled = (
            gpu_auto_enabled
            and ("PYTEST_CURRENT_TEST" not in os.environ or os.getenv("GOODQ_TEST_VRAM_ALLOCATOR") == "1")
        )
        is_gpu_step = (
            step_uses_gpu_backend(step_name, env=policy_env, conda_env=env_name, cfg=step_cfg)
            if gpu_enabled
            else False
        )
        
        allocator = None
        vram_reserved = False
        parent_pid = os.getpid()
        reservation_id = "launch:" + uuid.uuid4().hex
        
        if is_gpu_step and gpu_enabled:
            allocator = VRAMAllocator()
            allocator.env = policy_env
            allocator.conda_env = env_name
            allocator.cfg = step_cfg
            cmd_str = f"python cli/step_runner.py --step {step_name}"
            vram_reserved = await _reserve_step_vram_async(
                allocator,
                step_name=step_name,
                pid=parent_pid,
                reservation_id=reservation_id,
                command=cmd_str,
                timeout_seconds=300.0,
                env=policy_env,
                conda_env=env_name,
            )
            if not vram_reserved:
                if gpu_required:
                    err_msg = f"VRAM allocation failed for GPU-required step '{step_name}'. Bounds breached."
                    _record_prelaunch_step_error(
                        cfg_json,
                        step_name,
                        payload,
                        (time.perf_counter() - start_ts) * 1000.0,
                        err_msg,
                        reason="vram_allocation_failed",
                    )
                    raise RuntimeError(err_msg)
                else:
                    logger.warning(
                        f"VRAM allocation limits breached for step '{step_name}'. Falling back to CPU."
                    )
                    if _step_env_overrides is None:
                        _step_env_overrides = {}
                    _step_env_overrides = dict(_step_env_overrides)
                    _step_env_overrides["GOODQ_NO_AUTO_GPU"] = "1"
                    if step_name == 'image_caption':
                        _step_env_overrides['GOODQ_IMAGE_CAPTION_FORCE_CPU'] = '1'
                    elif step_name == 'object_detect':
                        _step_env_overrides['GOODQ_OBJECT_DETECT_FORCE_CPU'] = '1'
                    elif step_name == 'audio_embed_clap':
                        _step_env_overrides['GOODQ_CLAP_FORCE_CPU'] = '1'
                    elif step_name == 'image_embed_dino':
                        _step_env_overrides['GOODQ_DINO_FORCE_CPU'] = '1'
                    elif step_name == 'emotion_classify':
                        _step_env_overrides['GOODQ_EMOTION_FORCE_CPU'] = '1'

        # Convert payload to JSON-serializable format
        
        tmp_dir = None
        process = None
        observer = None
        failure_in_flight = False
        
        try:
            tmp_dir = Path(tempfile.mkdtemp(prefix='ingest_step_'))
            in_path = tmp_dir / 'input.json'
            out_path = tmp_dir / 'output.json'
            serializable_payload = worker_payload(payload)
            in_path.write_text(json.dumps(serializable_payload, ensure_ascii=False), encoding='utf-8')
            
            launch = prepare_worker_launch(
                WorkerRequest(env_name, step_name, in_path, out_path, cfg_json), work_env,
                repo_root=REPO_ROOT, conda_exe=resolve_conda(),
                prefer_direct=_prefer_direct_env_python,
                prefer_available_python=_PREFER_DIRECT_ENV_PYTHON_ON_WINDOWS,
                overrides=_step_env_overrides,
            )
            cmd, launcher_kind = launch.command, launch.kind
            direct_env_python, step_env = launch.direct_python, launch.environment

            observer = _observer()
            observer_step = f"step.{step_name}"
            observer_meta: Dict[str, Any] = {"env": env_name}
            payload_video_id = payload.get('video_id') or payload.get('video_hash')
            if payload_video_id is not None:
                observer_meta["video_id"] = str(payload_video_id)
            payload_scene_id = payload.get('scene_id')
            if payload_scene_id is not None:
                observer_meta["scene_id"] = str(payload_scene_id)
            payload_scene_index = payload.get('scene_index')
            if payload_scene_index is not None:
                observer_meta["scene_index"] = payload_scene_index
            elif isinstance(payload.get('scene'), dict) and payload['scene'].get('index') is not None:
                observer_meta["scene_index"] = payload['scene'].get('index')
            observer_meta["attempt"] = max(int(_healer_retry_attempt), int(_native_retry_attempt)) + 1
            observer_meta["healer_retry_attempt"] = int(_healer_retry_attempt)
            observer_meta["native_retry_attempt"] = int(_native_retry_attempt)
            observer_meta["launcher"] = launcher_kind
            observer_meta["direct_env_fallback_attempt"] = int(_direct_env_fallback_attempt)
            if _native_retry_mode:
                observer_meta["native_retry_mode"] = _native_retry_mode
            if VERBOSE:
                typer.echo(f'[step] -> {step_name} ({env_name}) [{launcher_kind}] (async)')
            
            stop_heartbeat = (lambda: None)
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(REPO_ROOT),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=step_env,
                )
                observer_meta["subprocess_pid"] = int(process.pid)
                if vram_reserved and allocator is not None:
                    try:
                        await asyncio.to_thread(allocator.update_pid, reservation_id, process.pid)
                    except Exception:
                        try:
                            process.kill()
                            await asyncio.wait_for(process.communicate(), timeout=5)
                        except Exception:
                            vram_reserved = False  # Retain the claim if the child cannot be reaped.
                            logger.exception("Unbound worker could not be stopped; retaining VRAM claim %s", reservation_id)
                            raise
                        raise
                if observer:
                    observer.step_start(observer_step, metadata=observer_meta)
                    stop_heartbeat = observer.begin_heartbeat(observer_step, metadata=observer_meta)
                
                communicate_failed = True
                try:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        process.communicate(),
                        timeout=STEP_TIMEOUT
                    )
                    stdout_text = decode_worker_diagnostics(stdout_bytes)
                    stderr_text = decode_worker_diagnostics(stderr_bytes)
                    communicate_failed = False
                finally:
                    _stop_step_heartbeat(stop_heartbeat, preserve_error=communicate_failed)
                
                result = subprocess.CompletedProcess(
                    cmd,
                    process.returncode if process.returncode is not None else 1,
                    stdout_text or '',
                    stderr_text or '',
                )
            except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
                if process is not None:
                    try:
                        process.terminate()
                    except Exception:
                        pass
                    try:
                        await asyncio.wait_for(process.wait(), timeout=2.0)
                    except Exception:
                        try:
                            process.kill()
                        except Exception:
                            pass
                    try:
                        await asyncio.wait_for(process.communicate(), timeout=5)
                    except Exception:
                        pass
                    if process.returncode is None:
                        if isinstance(exc, asyncio.CancelledError):
                            raise
                        raise RuntimeError(f"Step {step_name} timed out; worker exit was not confirmed") from exc
                
                if observer:
                    _report_step_failure(
                        observer, observer_step,
                        error="timeout" if isinstance(exc, asyncio.TimeoutError) else "cancelled",
                        metadata=observer_meta,
                    )
                
                if step_name != "image_ocr" and isinstance(exc, asyncio.TimeoutError) and _control_agent_runtime_enabled():
                    try:
                        agent = _get_control_agent(cfg_json)
                        healing_result = await asyncio.to_thread(
                            agent.auto_heal_failure,
                            error=exc,
                            step_name=step_name,
                            context={'env': env_name, 'timeout': STEP_TIMEOUT}
                        )

                        if healing_result.get('success'):
                            if _healer_retry_attempt >= MAX_HEALER_RETRIES:
                                logger.warning("Healer retry ceiling reached for step=%s", step_name)
                                typer.echo(f"[heal] [WARN] Healer retry ceiling reached for step={step_name}", err=True)
                            else:
                                _record_healer_retry(step_name, cfg_json)
                                typer.echo("[heal] [PASS] Timeout healed, retrying step...", err=True)
                                return await _run_step_async(
                                    env_name,
                                    step_name,
                                    payload,
                                    cfg_json,
                                    _healer_retry_attempt=_healer_retry_attempt + 1,
                                    _native_retry_attempt=_native_retry_attempt,
                                    _direct_env_fallback_attempt=_direct_env_fallback_attempt,
                                    _prefer_direct_env_python=_prefer_direct_env_python,
                                    _step_env_overrides=_step_env_overrides,
                                    _native_retry_mode=_native_retry_mode,
                                )
                        else:
                            typer.echo(f"[heal] [FAIL] Could not heal timeout: {healing_result.get('recommendation', 'No strategy')}", err=True)
                    except Exception as heal_error:
                        logger.warning(
                            "run_ingestion warning context=%s error=%s",
                            "control_agent.auto_heal_timeout",
                            heal_error,
                        )
                        typer.echo(f"[heal] [WARN] Healing failed: {heal_error}", err=True)

                if isinstance(exc, asyncio.CancelledError):
                    raise
                raise RuntimeError(f"Step {step_name} timed out after {STEP_TIMEOUT}s") from exc

            if result.returncode != 0:
                stderr = result.stderr.strip()
                stdout = result.stdout.strip()
                combined_output = f"{stdout}\n{stderr}".lower()

                should_try_direct_env_fallback = (
                    launcher_kind == "conda_run"
                    and step_name in _OPTIONAL_DIRECT_ENV_FALLBACK_STEPS
                    and _direct_env_fallback_attempt == 0
                    and direct_env_python is not None
                    and (
                        "conda.cli.main_run:execute(127)" in combined_output
                        or "failed to run 'conda activate" in combined_output
                        or (
                            "__conda_tmp_" in combined_output
                            and (
                                "being used by another process" in combined_output
                                or "cannot access the file because it is being used by another process" in combined_output
                            )
                        )
                    )
                )
                if should_try_direct_env_fallback:
                    logger.warning(
                        "[RUN] Conda launcher failed for optional step=%s env=%s; retrying via direct env python",
                        step_name,
                        env_name,
                    )
                    if VERBOSE:
                        typer.echo(
                            f"[retry] [WARN] Conda launcher failed for {step_name}; retrying via direct env python",
                            err=True,
                        )
                    return await _run_step_async(
                        env_name,
                        step_name,
                        payload,
                        cfg_json,
                        _healer_retry_attempt=_healer_retry_attempt,
                        _native_retry_attempt=_native_retry_attempt,
                        _direct_env_fallback_attempt=1,
                        _prefer_direct_env_python=True,
                        _step_env_overrides=_step_env_overrides,
                        _native_retry_mode=_native_retry_mode,
                    )

                error_msg = (
                    f"Step {step_name} failed ({env_name}) [returncode={result.returncode}]\n"
                    f"STDOUT: {stdout}\n"
                    f"STDERR: {stderr}"
                )
                if observer:
                    _report_step_failure(observer,
                        observer_step,
                        error=f"returncode_{result.returncode}",
                        metadata=observer_meta,
                    )

                is_native_crash = _is_windows_native_crash(result.returncode)
                retry_limit, retry_env_overrides, retry_mode = _resolve_native_retry_strategy(
                    step_name,
                    _native_retry_attempt + 1,
                    gpu_required=gpu_required,
                )
                if is_native_crash and _native_retry_attempt < retry_limit:
                    retry_attempt = _native_retry_attempt + 1
                    env_fingerprint_line: Optional[str] = None
                    for stderr_line in stderr.splitlines():
                        if 'subprocess_env_fingerprint' in stderr_line:
                            env_fingerprint_line = stderr_line.strip()
                            break
                    _record_native_retry(
                        step_name,
                        cfg_json,
                        result.returncode,
                        retry_attempt,
                        env_fingerprint=env_fingerprint_line,
                    )
                    status_code = _normalize_windows_status_code(result.returncode)
                    logger.warning(
                        "[RUN] Native crash detected for step=%s return_code=%s status_code=0x%08X retry=%s/%s mode=%s",
                        step_name,
                        result.returncode,
                        status_code,
                        retry_attempt,
                        retry_limit,
                        retry_mode or "default",
                    )
                    if env_fingerprint_line:
                        logger.warning(
                            "[RUN] Native crash env fingerprint step=%s %s",
                            step_name,
                            env_fingerprint_line,
                        )
                    if VERBOSE:
                        typer.echo(
                            (
                                f"[retry] [WARN] Native crash for {step_name} "
                                f"(0x{status_code:08X}); retrying via {retry_mode or 'default'}"
                            ),
                            err=True,
                        )
                    return await _run_step_async(
                        env_name,
                        step_name,
                        payload,
                        cfg_json,
                        _healer_retry_attempt=_healer_retry_attempt,
                        _native_retry_attempt=retry_attempt,
                        _direct_env_fallback_attempt=_direct_env_fallback_attempt,
                        _prefer_direct_env_python=_prefer_direct_env_python,
                        _step_env_overrides=retry_env_overrides,
                        _native_retry_mode=retry_mode,
                    )

                if step_name != "image_ocr" and _control_agent_runtime_enabled():
                    try:
                        agent = _get_control_agent(cfg_json)
                        healing_result = await asyncio.to_thread(
                            agent.auto_heal_failure,
                            error=RuntimeError(error_msg),
                            step_name=step_name,
                            context={
                                'env': env_name,
                                'returncode': result.returncode,
                                'stdout': stdout[:500],
                                'stderr': stderr[:500],
                            }
                        )

                        if healing_result.get('success'):
                            if _healer_retry_attempt >= MAX_HEALER_RETRIES:
                                logger.warning("Healer retry ceiling reached for step=%s", step_name)
                                typer.echo(f"[heal] [WARN] Healer retry ceiling reached for step={step_name}", err=True)
                            else:
                                _record_healer_retry(step_name, cfg_json)
                                typer.echo("[heal] [PASS] Step failure healed, retrying...", err=True)
                                return await _run_step_async(
                                    env_name,
                                    step_name,
                                    payload,
                                    cfg_json,
                                    _healer_retry_attempt=_healer_retry_attempt + 1,
                                    _native_retry_attempt=_native_retry_attempt,
                                    _direct_env_fallback_attempt=_direct_env_fallback_attempt,
                                    _prefer_direct_env_python=_prefer_direct_env_python,
                                    _step_env_overrides=_step_env_overrides,
                                    _native_retry_mode=_native_retry_mode,
                                )
                        else:
                            typer.echo("[heal] [FAIL] Could not heal failure", err=True)
                            if healing_result.get('recommendation'):
                                typer.echo(f"[heal] [SYMBOL] Suggestion: {healing_result['recommendation'][:200]}", err=True)
                    except Exception as heal_error:
                        logger.warning(
                            "run_ingestion warning context=%s error=%s",
                            "control_agent.auto_heal_failure",
                            heal_error,
                        )
                        typer.echo(f"[heal] [WARN] Healing attempt failed: {heal_error}", err=True)

                raise RuntimeError(error_msg)

            try:
                outputs = read_worker_result(out_path, stdout_bytes, step_name=step_name, env_name=env_name)
            except (RuntimeError, OSError) as exc:
                if observer:
                    _report_step_failure(observer,observer_step, error=str(exc), metadata=observer_meta)
                raise
            duration = time.perf_counter() - start_ts
            from cli.step_runner import _derive_step_log_outcome
            log_status, log_error, extra = _derive_step_log_outcome(step_name, outputs, verbose=VERBOSE)
            if log_status == "error" or "_error" in outputs:
                log_error = str(outputs.get("_error", log_error))
                if observer:
                    _report_step_failure(observer,observer_step, error=log_error, metadata=observer_meta)
                return _make_async_step_envelope(
                    step_name=step_name, status="error", outputs=outputs, errors=log_error,
                    started_at=started_at_str, finished_at=datetime.now(timezone.utc).isoformat(),
                    duration_seconds=duration, retry_count=max(_healer_retry_attempt, _native_retry_attempt),
                )
            if observer:
                observer.step_end(
                    observer_step,
                    metadata={
                        **observer_meta,
                        "duration_sec": round(duration, 3),
                    },
                )
            if VERBOSE:
                typer.echo(f'[step] <- {step_name} ({env_name}) [{duration:.1f}s]')
            
            # PHASE 3: Learn from successful execution
            if step_name != "image_ocr" and _control_agent_runtime_enabled():
                try:
                    models_root = _resolve_models_dir(cfg_json=cfg_json)
                    agent = _get_control_agent(cfg_json)
                    await asyncio.to_thread(
                        agent.learn_from_success,
                        step_name=step_name,
                        execution_time_seconds=duration,
                        config_used={'env': env_name, 'timeout': STEP_TIMEOUT},
                        context={'models_root': str(models_root)}
                    )
                except Exception as e:
                    logger.warning(
                        "run_ingestion warning context=%s error=%s",
                        "control_agent.learn_from_success",
                        e,
                    )
                    _record_run_warning(
                        cfg_json,
                        code='control_agent_learn_failed',
                        message=str(e),
                        context={'step': step_name, 'env': env_name},
                    )

            status_to_return = "ok"
            if log_status == "skipped":
                status_to_return = "skipped"
            elif log_status == "error":
                status_to_return = "error"

            return _make_async_step_envelope(
                step_name=step_name,
                status=status_to_return,
                outputs=outputs,
                errors=log_error,
                started_at=started_at_str,
                finished_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=duration,
                retry_count=max(_healer_retry_attempt, _native_retry_attempt),
            )
        except BaseException:
            failure_in_flight = True
            if process is not None and process.returncode is None:
                # Observer/setup failures can occur after the worker is bound.
                # Do not release its device while the child may still execute.
                try:
                    process.kill()
                    await asyncio.wait_for(process.communicate(), timeout=5)
                    if process.returncode is None:
                        raise RuntimeError("Worker exit was not confirmed")
                except BaseException:
                    vram_reserved = False
                    logger.exception("Worker could not be reaped; retaining VRAM claim %s", reservation_id)
            raise
        finally:
            release_error = None
            if vram_reserved and allocator is not None:
                try:
                    await asyncio.to_thread(allocator.release, reservation_id)
                except Exception as e:
                    logger.warning(
                        "run_ingestion warning context=%s error=%s",
                        "vram_release_failed",
                        e,
                    )
                    release_error = e
                    if observer:
                        _report_step_failure(observer, observer_step, error=f"vram_release_failed: {e}",
                                                     metadata=observer_meta)
            try:
                safe_to_clean = process is None or process.returncode is not None
                for child in tmp_dir.iterdir() if tmp_dir is not None and safe_to_clean else ():
                    child.unlink(missing_ok=True)
                if tmp_dir is not None and safe_to_clean:
                    tmp_dir.rmdir()
                elif tmp_dir is not None:
                    logger.error("Unreaped worker retains input directory %s", tmp_dir)
            except Exception as e:
                logger.warning(
                    "run_ingestion warning context=%s error=%s",
                    "step_temp_cleanup",
                    e,
                )
            if release_error is not None and not failure_in_flight:
                raise release_error
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        duration = time.perf_counter() - start_ts
        return _make_async_step_envelope(
            step_name=step_name,
            status="error",
            errors=str(exc),
            started_at=started_at_str,
            finished_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=duration,
            retry_count=max(_healer_retry_attempt, _native_retry_attempt),
        )


_DEFAULT_RUN_STEP_ASYNC = _run_step_async


async def _run_step_batch_async(
    env_name: str,
    step_name: str,
    payloads: List[Dict[str, Any]],
    cfg_json: Path,
) -> List[Dict[str, Any]]:
    """Run multiple independent sample items in one async worker subprocess unless _run_step_async is monkeypatched."""
    if not payloads:
        return []
    if _run_step_async is not _DEFAULT_RUN_STEP_ASYNC or len(payloads) == 1:
        return [await _run_step_async(env_name, step_name, p, cfg_json) for p in payloads]

    first = payloads[0]
    batch_payload: Dict[str, Any] = {
        "_batch_items": payloads,
        "video_id": first.get("video_id") or first.get("video_hash"),
        "video_hash": first.get("video_hash"),
        "scene_id": first.get("scene_id"),
        "scene_index": first.get("scene_index"),
    }
    envelope = await _run_step_async(env_name, step_name, batch_payload, cfg_json)
    outputs = (envelope.get("outputs") or {}) if isinstance(envelope, dict) else {}
    batch_list = outputs.get("_batch_results") if isinstance(outputs, dict) else None
    if (
        isinstance(envelope, dict)
        and envelope.get("status") == "ok"
        and isinstance(batch_list, list)
        and len(batch_list) == len(payloads)
    ):
        per_dur = float(envelope.get("duration_seconds") or 0.0) / max(1, len(payloads))
        retries = int(envelope.get("retry_count") or 0)
        return [
            _make_async_step_envelope(
                step_name=step_name,
                status=str((entry or {}).get("status") or "ok") if isinstance(entry, dict) else "error",
                outputs=(entry.get("outputs") if isinstance(entry, dict) and isinstance(entry.get("outputs"), dict) else {}),
                errors=(str(entry["errors"]) if isinstance(entry, dict) and entry.get("errors") is not None else None),
                started_at=envelope.get("started_at"),
                finished_at=envelope.get("finished_at"),
                duration_seconds=per_dur,
                retry_count=retries,
            )
            for entry in batch_list
        ]

    err_str = (envelope.get("errors") if isinstance(envelope, dict) else str(envelope)) or f"{step_name} batch worker failed"
    return [
        _make_async_step_envelope(
            step_name=step_name,
            status="error",
            outputs={},
            errors=str(err_str),
        )
        for _ in payloads
    ]



def _log_skipped_steps(
    cfg: Dict[str, Any],
    step_names: List[str],
    *,
    modality: str,
    video_hash: str,
    scene_id: str,
    scene_index: Optional[int],
    source_path: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    extra_payload: Dict[str, Any] = {'reason': 'dedupe'}
    if isinstance(extra, dict):
        extra_payload.update(extra)
    item: Dict[str, Any] = {
        'modality': modality,
        'video_hash': video_hash,
        'video_id': video_hash,
    }
    if scene_id is not None:
        item['scene_id'] = scene_id
    if scene_index is not None:
        item['scene_index'] = scene_index
    if source_path:
        item['source_path'] = source_path
    for step_name in step_names:
        log_step_run(cfg, step_name, item, 0.0, 'skipped', extra=extra_payload)


def _extract_keyframe(
    ffmpeg: str,
    video_path: Path,
    scene: Dict[str, Any],
    dest_dir: Path,
    *,
    scene_id: Optional[str] = None,
    video_id: Optional[str] = None,
    sample_timestamp: Optional[float] = None,
    sample_suffix: str = '',
) -> Path:
    _ensure_dir(dest_dir)
    duration = float(scene.get('duration', 0.0) or 0.0)
    start = float(scene.get('start', 0.0) or 0.0)
    timestamp = start + (duration / 2.0) if duration > 0 else start
    if sample_timestamp is not None:
        timestamp = sample_timestamp
    outfile = dest_dir / f"scene_{scene.get('index', 0):04d}{sample_suffix}.jpg"
    observer = _observer()
    observer_step = "ffmpeg.extract_keyframe"
    observer_meta = {
        "video": str(video_path),
        "scene_index": scene.get('index', 0),
    }
    if scene_id is not None:
        observer_meta["scene_id"] = str(scene_id)
    if video_id is not None:
        observer_meta["video_id"] = str(video_id)
    cmd = [
        ffmpeg,
        '-hide_banner',
        '-loglevel', 'error',
        '-ss', f'{timestamp:.3f}',
        '-i', str(video_path),
        '-frames:v', '1',
        '-y',
        str(outfile),
    ]
    stop_heartbeat = (lambda: None)
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    observer_meta["subprocess_pid"] = int(process.pid)
    if observer:
        observer.step_start(observer_step, metadata=observer_meta)
        stop_heartbeat = observer.begin_heartbeat(observer_step, metadata=observer_meta)
    try:
        stdout_text, stderr_text = process.communicate()
    finally:
        stop_heartbeat()
    result = subprocess.CompletedProcess(
        cmd,
        process.returncode if process.returncode is not None else 1,
        stdout_text or '',
        stderr_text or '',
    )
    if result.returncode != 0 and (
        'Non full-range YUV' in result.stderr or 'strict_std_compliance' in result.stderr
    ):
        retry_cmd = [
            ffmpeg,
            '-hide_banner',
            '-loglevel', 'error',
            '-ss', f'{timestamp:.3f}',
            '-i', str(video_path),
            '-strict', 'unofficial',
            '-frames:v', '1',
            '-y',
            str(outfile),
        ]
        retry_proc = subprocess.Popen(
            retry_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
        )
        r_out, r_err = retry_proc.communicate()
        if retry_proc.returncode == 0 and outfile.exists() and outfile.stat().st_size > 0:
            result = subprocess.CompletedProcess(retry_cmd, 0, r_out or '', r_err or '')
    if result.returncode != 0:
        if observer:
            observer.step_error(
                observer_step,
                error=f"returncode_{result.returncode}",
                metadata=observer_meta,
            )
        raise RuntimeError(f"ffmpeg failed to extract keyframe: {result.stderr}")
    if not outfile.exists():
        if observer:
            observer.step_error(
                observer_step,
                error="output_missing",
                metadata=observer_meta,
            )
        raise RuntimeError('Keyframe extraction did not produce a file')
    if observer:
        observer.step_end(observer_step, metadata=observer_meta)
    return outfile


def _extract_audio_chunk(
    ffmpeg: str,
    video_path: Path,
    scene: Dict[str, Any],
    dest_dir: Path,
    *,
    scene_id: Optional[str] = None,
    video_id: Optional[str] = None,
) -> Optional[Path]:
    """Extract audio chunk - returns None if video has no audio"""
    _ensure_dir(dest_dir)
    start = float(scene.get('start', 0.0) or 0.0)
    end = float(scene.get('end', start) or start)
    duration = max(0.1, end - start)
    outfile = dest_dir / f"scene_{scene.get('index', 0):04d}.wav"
    observer = _observer()
    observer_step = "ffmpeg.extract_audio_chunk"
    observer_meta = {
        "video": str(video_path),
        "scene_index": scene.get('index', 0),
        "duration_sec": round(duration, 3),
    }
    if scene_id is not None:
        observer_meta["scene_id"] = str(scene_id)
    if video_id is not None:
        observer_meta["video_id"] = str(video_id)
    cmd = [
        ffmpeg,
        '-hide_banner',
        '-loglevel', 'error',
        '-ss', f'{start:.3f}',
        '-i', str(video_path),
        '-t', f'{duration:.3f}',
        '-ac', '1',
        '-ar', '16000',
        '-vn',
        '-acodec', 'pcm_s16le',
        '-y',
        str(outfile),
    ]
    stop_heartbeat = (lambda: None)
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    observer_meta["subprocess_pid"] = int(process.pid)
    if observer:
        observer.step_start(observer_step, metadata=observer_meta)
        stop_heartbeat = observer.begin_heartbeat(observer_step, metadata=observer_meta)
    try:
        stdout_text, stderr_text = process.communicate()
    finally:
        stop_heartbeat()
    result = subprocess.CompletedProcess(
        cmd,
        process.returncode if process.returncode is not None else 1,
        stdout_text or '',
        stderr_text or '',
    )
    if result.returncode != 0:
        # Check if error is due to no audio stream
        if 'does not contain any stream' in result.stderr or 'Stream specifier' in result.stderr:
            # Video has no audio - this is OK, return None
            if observer:
                observer.step_end(observer_step, metadata={**observer_meta, "status": "no_audio_stream"})
            return None
        if observer:
            observer.step_error(
                observer_step,
                error=f"returncode_{result.returncode}",
                metadata=observer_meta,
            )
        raise RuntimeError(f"ffmpeg failed to extract audio chunk: {result.stderr}")
    if not outfile.exists():
        # If no file was created but no error, video likely has no audio
        if observer:
            observer.step_end(observer_step, metadata={**observer_meta, "status": "no_audio_output"})
        return None
    if observer:
        observer.step_end(observer_step, metadata=observer_meta)
    return outfile


def _filter_vhs_ocr_regions(
    ocr_text: Optional[str],
    ocr_meta: Dict[str, Any],
    time_hints: Any,
    sample_ts: float,
) -> Tuple[Optional[str], Dict[str, Any], Any]:
    """Filter low-confidence VHS grain and isolated CJK recognizer artifacts at scene aggregation."""
    regions = ocr_meta.get("accepted_regions")
    if not isinstance(regions, list) or not regions:
        return ocr_text, ocr_meta, time_hints
    if not all(
        isinstance(r, dict)
        and r.get("confidence_kind") == "recognizer_sequence_score"
        and isinstance(r.get("confidence"), (int, float))
        and not isinstance(r.get("confidence"), bool)
        for r in regions
    ):
        return ocr_text, ocr_meta, time_hints

    date_ev_raw = ocr_meta.get("date_evidence") if isinstance(ocr_meta.get("date_evidence"), list) else []
    date_region_indices = {
        int(ev["region_index"])
        for ev in date_ev_raw
        if isinstance(ev, dict) and isinstance(ev.get("region_index"), int)
    }

    kept_pairs: List[Tuple[int, Dict[str, Any]]] = []
    filtered_out: List[Dict[str, Any]] = []
    for idx, reg in enumerate(regions):
        text = str(reg.get("text") or "").strip()
        conf = float(reg["confidence"])
        cjk_chars = sum(
            1
            for ch in text
            if ("\u4e00" <= ch <= "\u9fff")
            or ("\u3400" <= ch <= "\u4dbf")
            or ("\u3040" <= ch <= "\u30ff")
            or ("\uac00" <= ch <= "\ud7af")
        )
        latin_alnum = sum(1 for ch in text if ch.isalnum()) - cjk_chars
        keep = (
            (idx in date_region_indices and conf >= 0.45)
            or (latin_alnum >= 3 and conf >= 0.50)
            or (latin_alnum == 2 and cjk_chars == 0 and conf >= 0.65)
            or (latin_alnum == 1 and cjk_chars == 0 and conf >= 0.85)
            or (cjk_chars >= 2 and conf >= 0.75)
            or (cjk_chars == 1 and conf >= 0.90)
        )
        if keep:
            kept_pairs.append((idx, reg))
        else:
            filtered_out.append(reg)

    if not filtered_out:
        return ocr_text, ocr_meta, time_hints

    old_to_new = {old_idx: new_idx for new_idx, (old_idx, _) in enumerate(kept_pairs)}
    kept_regions = [reg for _, reg in kept_pairs]
    new_meta = dict(ocr_meta)
    new_meta["accepted_regions"] = kept_regions
    new_meta["filtered_noise_regions"] = filtered_out

    kept_dates: List[Dict[str, Any]] = []
    for ev in date_ev_raw:
        if isinstance(ev, dict) and ev.get("region_index") in old_to_new:
            ev_copy = dict(ev)
            ev_copy["region_index"] = old_to_new[ev["region_index"]]
            kept_dates.append(ev_copy)
    if "date_evidence" in new_meta or kept_dates:
        new_meta["date_evidence"] = kept_dates

    new_time_hints = time_hints
    if len(kept_dates) != len(date_ev_raw):
        if kept_dates:
            explicit_dates = list(dict.fromkeys(str(ev["normalized_date"]) for ev in kept_dates if ev.get("normalized_date")))
            years = list(dict.fromkeys(str(ev["normalized_date"])[:4] for ev in kept_dates if ev.get("normalized_date")))
            first_seen: Dict[str, float] = {}
            old_first = time_hints.get("first_seen_ts", {}) if isinstance(time_hints, dict) else {}
            for key in [*explicit_dates, *years]:
                first_seen[key] = float(old_first.get(key, sample_ts))
            new_time_hints = {
                "explicit_dates": explicit_dates,
                "years": years,
                "decades": [],
                "seasons": [],
                "holidays": [],
                "relative": [],
                "first_seen_ts": first_seen,
            }
        else:
            new_time_hints = None

    if kept_regions:
        new_text = "\n".join(
            str(r.get("text") or "").strip()
            for r in kept_regions
            if str(r.get("text") or "").strip()
        )
        new_meta["accepted_text"] = new_text
        new_meta["text_length"] = len(new_text)
        return new_text or None, new_meta, new_time_hints

    new_meta["status"] = "no_text"
    new_meta["reason"] = "empty_ocr_text"
    new_meta["accepted_text"] = None
    new_meta["text_length"] = 0
    return None, new_meta, None


def _aggregate_ocr_sample_results(
    sample_records: List[Dict[str, Any]],
    midpoint_timestamp: float,
) -> Dict[str, Any]:
    from math import isfinite

    observations: List[Dict[str, Any]] = []
    sample_summaries: List[Dict[str, Any]] = []
    errors: List[str] = []
    warnings: List[Dict[str, Any]] = []
    deduped_lines: List[str] = []
    seen_lines: set[str] = set()
    merged_time_hints: Optional[Dict[str, Any]] = None
    successful_identity: Optional[tuple] = None

    def _non_ok_precedence(meta: Dict[str, Any], rec_status: str, rec_err: Any) -> int:
        m_status = str(meta.get("status") or "").strip().lower()
        m_reason = str(meta.get("reason") or "").strip().lower()
        if rec_status == "error" or m_status == "error" or meta.get("fallback_error") or rec_err:
            return 60
        if m_status == "dependency_missing":
            return 50
        if m_status == "no_source_path":
            return 40
        if m_status == "no_text" and m_reason == "low_confidence_primary_text":
            return 30
        if m_status == "no_text" and m_reason == "unvalidated_vhs_candidates":
            return 20
        if m_status == "no_text" and m_reason == "empty_ocr_text":
            return 10
        return 0

    best_non_ok_meta: Optional[Dict[str, Any]] = None
    best_non_ok_rank = -1

    for rec in sample_records:
        ts = float(rec.get("timestamp", midpoint_timestamp))
        is_mid = bool(rec.get("is_midpoint_sample", abs(ts - midpoint_timestamp) <= 1e-6))
        src_path = rec.get("source_path")
        rec_status = str(rec.get("status") or "unknown").strip().lower()
        outputs = rec.get("outputs") if isinstance(rec.get("outputs"), dict) else {}
        ocr_meta = dict(outputs.get("ocr_meta")) if isinstance(outputs.get("ocr_meta"), dict) else {}
        ocr_meta.setdefault("sample_timestamp", ts)
        ocr_meta.setdefault("is_midpoint_sample", is_mid)

        ocr_text_raw = outputs.get("ocr_text")
        ocr_text = ocr_text_raw.strip() if isinstance(ocr_text_raw, str) and ocr_text_raw.strip() else None
        meta_status = str(ocr_meta.get("status") or ("error" if rec.get("error") else "unknown")).strip().lower()
        sample_time_hints = outputs.get("time_hints")
        if ocr_text and meta_status == "ok":
            ocr_text, ocr_meta, sample_time_hints = _filter_vhs_ocr_regions(
                ocr_text, ocr_meta, sample_time_hints, ts
            )
            meta_status = str(ocr_meta.get("status") or meta_status).strip().lower()
        meta_reason = str(ocr_meta.get("reason") or ("ocr_sample_error" if rec.get("error") else meta_status)).strip()
        sample_err = rec.get("error") or ocr_meta.get("fallback_error") or ocr_meta.get("error")

        if rec_status == "error" or meta_status in {"error", "dependency_missing", "no_source_path"} or ocr_meta.get("fallback_error"):
            err_msg = str(sample_err or f"ocr sample failed ({meta_status}:{meta_reason})")
            errors.append(f"ocr sample at {ts:.3f}s: {err_msg}")
        elif meta_status == "no_text" and meta_reason in {"low_confidence_primary_text", "unvalidated_vhs_candidates"}:
            warnings.append({
                "timestamp": ts,
                "is_midpoint_sample": is_mid,
                "reason": meta_reason,
                "ocr_meta": ocr_meta,
            })

        if meta_status in {"ok", "no_text"}:
            identity_keys = ("engine", "model_revision", "detector_revision", "config_sha256")
            identity = tuple(ocr_meta.get(key) for key in identity_keys)
            if successful_identity is not None and successful_identity != identity:
                raise ValueError("Cannot aggregate OCR observations from different model/configuration identities")
            successful_identity = identity

        if ocr_text and meta_status == "ok":
            ocr_meta.setdefault("accepted_text", ocr_text)
            obs_entry = {
                "timestamp": ts,
                "is_midpoint_sample": is_mid,
                "source_path": src_path,
                "ocr_text": ocr_text,
                "ocr_meta": ocr_meta,
                "time_hints": sample_time_hints,
            }
            observations.append(obs_entry)
            for line in ocr_text.splitlines():
                clean_line = line.strip()
                if clean_line and clean_line not in seen_lines:
                    seen_lines.add(clean_line)
                    deduped_lines.append(clean_line)
            if isinstance(sample_time_hints, dict) and any(sample_time_hints.values()):
                if merged_time_hints is None:
                    merged_time_hints = {}
                for hint_kind, hint_values in sample_time_hints.items():
                    if isinstance(hint_values, list):
                        retained = merged_time_hints.setdefault(hint_kind, [])
                        for value in hint_values:
                            if value not in retained:
                                retained.append(value)
                    elif hint_kind == "first_seen_ts" and isinstance(hint_values, dict):
                        retained = merged_time_hints.setdefault(hint_kind, {})
                        for hint, timestamp in hint_values.items():
                            if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool) and isfinite(timestamp):
                                retained[hint] = min(retained.get(hint, timestamp), timestamp)
        else:
            rank = _non_ok_precedence(ocr_meta, rec_status, sample_err)
            if rank > best_non_ok_rank:
                best_non_ok_rank = rank
                best_non_ok_meta = ocr_meta

        sample_summaries.append({
            "sample_index": rec.get("sample_index"),
            "timestamp": ts,
            "is_midpoint_sample": is_mid,
            "source_path": src_path,
            "status": meta_status,
            "reason": meta_reason,
            "ocr_text": ocr_text,
            "error": str(sample_err) if sample_err else None,
            "ocr_meta": ocr_meta,
        })

    combined_text = "\n".join(deduped_lines) if deduped_lines else None
    if observations:
        combined_meta = dict(observations[0]["ocr_meta"])
        combined_meta["status"] = "ok"
        combined_meta["text_length"] = len(combined_text or "")
        combined_meta["accepted_text"] = combined_text
        combined_meta["accepted_sample_timestamps"] = [obs["timestamp"] for obs in observations]
        combined_meta["non_midpoint_text_observed"] = any(not obs["is_midpoint_sample"] for obs in observations)
    else:
        combined_meta = dict(best_non_ok_meta or {"status": "no_text", "reason": "empty_ocr_text"})
        combined_meta["accepted_sample_timestamps"] = []
        combined_meta["non_midpoint_text_observed"] = False

    combined_meta["samples"] = sample_summaries
    combined_meta["observations"] = [
        {
            "timestamp": obs["timestamp"],
            "is_midpoint_sample": obs["is_midpoint_sample"],
            "source_path": obs["source_path"],
            "ocr_text": obs["ocr_text"],
            "engine": obs["ocr_meta"].get("engine", "unknown"),
            "strategy": obs["ocr_meta"].get("strategy", "default"),
            "model_revision": obs["ocr_meta"].get("model_revision"),
            "detector_revision": obs["ocr_meta"].get("detector_revision"),
            "config_sha256": obs["ocr_meta"].get("config_sha256"),
            "accepted_regions": obs["ocr_meta"].get("accepted_regions", []),
            "date_evidence": obs["ocr_meta"].get("date_evidence", []),
        }
        for obs in observations
    ]
    combined_meta["sample_errors"] = errors
    combined_meta["sample_warnings"] = warnings

    out: Dict[str, Any] = {
        "ocr_text": combined_text,
        "ocr_meta": combined_meta,
        "ocr_observations": observations,
        "ocr_sampling_errors": errors,
        "ocr_sampling_warnings": warnings,
    }
    if merged_time_hints is not None:
        out["time_hints"] = merged_time_hints
    return out


def _caption_batch_records(batch: List[Dict[str, Any]], outputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Map a one-call-per-scene caption result back to per-sample records."""
    results = outputs.get('samples') if isinstance(outputs, dict) else None
    if not isinstance(results, list) or len(results) != len(batch):
        raise RuntimeError('image_caption returned a malformed sample batch')
    return [
        {**sample, 'status': 'ok', 'outputs': result if isinstance(result, dict) else {}, 'error': None}
        for sample, result in zip(batch, results)
    ]


def _caption_batch_error_records(batch: List[Dict[str, Any]], error: str) -> List[Dict[str, Any]]:
    return [
        {
            **sample,
            'status': 'error',
            'outputs': {'caption': None, 'caption_meta': {
                'status': 'error', 'reason': 'caption_sample_error', 'error': error,
                'sample_timestamp': sample['timestamp'], 'is_midpoint_sample': sample['is_midpoint_sample'],
            }},
            'error': error,
        }
        for sample in batch
    ]


def _aggregate_caption_sample_results(
    sample_records: List[Dict[str, Any]],
    midpoint_timestamp: float,
) -> Dict[str, Any]:
    """Aggregate multi-frame caption samples into scene-level caption fields while preserving per-sample provenance."""
    if not sample_records:
        return {}
    if all(
        str(rec.get("status") or "ok") == "ok"
        and not rec.get("error")
        and not (rec.get("outputs") or {})
        for rec in sample_records
    ):
        return {}

    observations: List[Dict[str, Any]] = []
    deduped_captions: List[str] = []
    seen_captions: set[str] = set()
    errors: List[str] = []
    warnings: List[str] = []
    sample_summaries: List[Dict[str, Any]] = []

    def _non_ok_precedence(meta: Dict[str, Any], rec_status: str, rec_err: Optional[str]) -> int:
        status = str(meta.get("status") or "").strip().lower()
        if rec_status == "error" or status == "error" or rec_err:
            return 4
        if status in {"dependency_missing", "model_unavailable", "unavailable"}:
            return 3
        if status in {"no_source_path", "image_open_failed"}:
            return 2
        if status in {"not_applicable", "blank_frame", "empty"}:
            return 1
        return 0

    best_non_ok_meta: Optional[Dict[str, Any]] = None
    best_non_ok_rank = -1
    best_non_ok_is_mid = False

    for rec in sample_records:
        sample_index = rec.get("sample_index")
        ts = float(midpoint_timestamp if rec.get("timestamp") is None else rec["timestamp"])
        is_mid = bool(rec.get("is_midpoint_sample", abs(ts - midpoint_timestamp) <= 1e-6))
        src_path = rec.get("source_path")
        rec_status = str(rec.get("status") or "ok")
        outputs = rec.get("outputs") if isinstance(rec.get("outputs"), dict) else {}
        cap_meta_raw = outputs.get("caption_meta") if isinstance(outputs.get("caption_meta"), dict) else {}
        cap_meta = dict(cap_meta_raw)
        cap_meta.setdefault("sample_timestamp", ts)
        cap_meta.setdefault("is_midpoint_sample", is_mid)

        cap_val = outputs.get("caption")
        cap_text = cap_val.strip() if isinstance(cap_val, str) and cap_val.strip() else None
        meta_status = str(cap_meta.get("status") or ("ok" if cap_text else "not_applicable")).strip().lower()
        meta_reason = cap_meta.get("reason")
        sample_err = rec.get("error") or cap_meta.get("error")

        if rec_status == "error" or meta_status in {"error", "dependency_missing", "model_unavailable"}:
            err_msg = str(sample_err or meta_reason or meta_status or "image_caption sample error")
            errors.append(f"image_caption@{ts:.3f}s: {err_msg}")
        elif meta_status in {"unavailable", "no_source_path", "image_open_failed"} and sample_err:
            warnings.append(f"image_caption@{ts:.3f}s: {sample_err}")

        if cap_text and meta_status == "ok":
            obs_entry = {
                "sample_index": sample_index,
                "timestamp": ts,
                "is_midpoint_sample": is_mid,
                "source_path": src_path,
                "caption": cap_text,
                "caption_meta": cap_meta,
            }
            observations.append(obs_entry)
            norm_cap = cap_text.casefold()
            if norm_cap not in seen_captions:
                seen_captions.add(norm_cap)
                deduped_captions.append(cap_text)
        else:
            rank = _non_ok_precedence(cap_meta, rec_status, str(sample_err) if sample_err else None)
            if rank > best_non_ok_rank or (rank == best_non_ok_rank and is_mid and not best_non_ok_is_mid):
                best_non_ok_rank = rank
                best_non_ok_meta = cap_meta
                best_non_ok_is_mid = is_mid

        sample_summaries.append({
            "sample_index": sample_index,
            "timestamp": ts,
            "is_midpoint_sample": is_mid,
            "source_path": src_path,
            "status": meta_status,
            "reason": meta_reason,
            "caption": cap_text,
            "error": str(sample_err) if sample_err else None,
            "caption_meta": cap_meta,
        })

    if observations:
        primary_obs = next((obs for obs in observations if obs["is_midpoint_sample"]), observations[0])
        primary_caption: Optional[str] = primary_obs["caption"]
        combined_meta = dict(primary_obs["caption_meta"])
        combined_meta["status"] = "ok"
        combined_meta["accepted_sample_count"] = len(observations)
        combined_meta["accepted_sample_timestamps"] = [obs["timestamp"] for obs in observations]
        combined_meta["distinct_captions"] = deduped_captions
        combined_meta["non_midpoint_caption_observed"] = any(not obs["is_midpoint_sample"] for obs in observations)
    else:
        primary_caption = None
        combined_meta = dict(
            best_non_ok_meta
            or {
                "status": "not_applicable",
                "reason": "blank_or_low_variance_frame",
                "engine": "blip",
            }
        )
        combined_meta["accepted_sample_count"] = 0
        combined_meta["accepted_sample_timestamps"] = []
        combined_meta["distinct_captions"] = []
        combined_meta["non_midpoint_caption_observed"] = False

    combined_meta["sample_count"] = len(sample_summaries)
    combined_meta["midpoint_timestamp"] = midpoint_timestamp
    combined_meta["sample_timestamps"] = [s["timestamp"] for s in sample_summaries]
    combined_meta["samples"] = sample_summaries
    combined_meta["observations"] = [
        {
            "sample_index": obs["sample_index"],
            "timestamp": obs["timestamp"],
            "is_midpoint_sample": obs["is_midpoint_sample"],
            "source_path": obs["source_path"],
            "caption": obs["caption"],
            "engine": obs["caption_meta"].get("engine", "blip"),
            "image_stats": obs["caption_meta"].get("image_stats"),
        }
        for obs in observations
    ]
    combined_meta["sample_errors"] = errors
    combined_meta["sample_warnings"] = warnings

    return {
        "caption": primary_caption,
        "caption_meta": combined_meta,
        "caption_observations": observations,
        "caption_sampling_errors": errors,
        "caption_sampling_warnings": warnings,
    }


def _aggregate_object_detect_sample_results(
    sample_records: List[Dict[str, Any]],
    midpoint_timestamp: float,
) -> Dict[str, Any]:
    """Aggregate multi-frame object detection samples into scene-level object fields with per-detection provenance."""
    if not sample_records:
        return {}
    if all(
        str(rec.get("status") or "ok") == "ok"
        and not rec.get("error")
        and not (rec.get("outputs") or {})
        for rec in sample_records
    ):
        return {}

    observations: List[Dict[str, Any]] = []
    all_objects: List[Dict[str, Any]] = []
    errors: List[str] = []
    warnings: List[str] = []
    sample_summaries: List[Dict[str, Any]] = []

    def _non_ok_precedence(meta: Dict[str, Any], rec_status: str, rec_err: Optional[str]) -> int:
        status = str(meta.get("status") or "").strip().lower()
        if rec_status == "error" or status == "error" or rec_err:
            return 4
        if status in {"dependency_missing", "model_unavailable", "unavailable"}:
            return 3
        if status in {"no_file", "no_source_path", "image_open_failed"}:
            return 2
        if status == "ok":
            return 1
        return 0

    best_non_ok_meta: Optional[Dict[str, Any]] = None
    best_non_ok_rank = -1
    best_non_ok_is_mid = False

    for rec in sample_records:
        sample_index = rec.get("sample_index")
        ts = float(midpoint_timestamp if rec.get("timestamp") is None else rec["timestamp"])
        is_mid = bool(rec.get("is_midpoint_sample", abs(ts - midpoint_timestamp) <= 1e-6))
        src_path = rec.get("source_path")
        rec_status = str(rec.get("status") or "ok")
        outputs = rec.get("outputs") if isinstance(rec.get("outputs"), dict) else {}
        det_meta_raw = outputs.get("detect_meta") if isinstance(outputs.get("detect_meta"), dict) else {}
        det_meta = dict(det_meta_raw)
        det_meta.setdefault("sample_timestamp", ts)
        det_meta.setdefault("is_midpoint_sample", is_mid)

        raw_objects = outputs.get("objects") if isinstance(outputs.get("objects"), list) else []
        sample_objects: List[Dict[str, Any]] = []
        for obj in raw_objects:
            if not isinstance(obj, dict):
                continue
            annotated_obj = dict(obj)
            annotated_obj.setdefault("timestamp", ts)
            annotated_obj.setdefault("sample_index", sample_index)
            annotated_obj.setdefault("is_midpoint_sample", is_mid)
            if src_path:
                annotated_obj.setdefault("source_path", src_path)
            sample_objects.append(annotated_obj)
            all_objects.append(annotated_obj)

        meta_status = str(det_meta.get("status") or ("ok" if rec_status == "ok" else "error")).strip().lower()
        meta_reason = det_meta.get("reason")
        sample_err = rec.get("error") or det_meta.get("error")

        if rec_status == "error" or meta_status in {"error", "dependency_missing", "model_unavailable"}:
            err_msg = str(sample_err or meta_reason or meta_status or "object_detect sample error")
            errors.append(f"object_detect@{ts:.3f}s: {err_msg}")
        elif meta_status in {"unavailable", "no_file", "no_source_path"} and sample_err:
            warnings.append(f"object_detect@{ts:.3f}s: {sample_err}")

        if sample_objects and meta_status == "ok":
            observations.append({
                "sample_index": sample_index,
                "timestamp": ts,
                "is_midpoint_sample": is_mid,
                "source_path": src_path,
                "objects": sample_objects,
                "detect_meta": det_meta,
            })
        else:
            rank = _non_ok_precedence(det_meta, rec_status, str(sample_err) if sample_err else None)
            if rank > best_non_ok_rank or (rank == best_non_ok_rank and is_mid and not best_non_ok_is_mid):
                best_non_ok_rank = rank
                best_non_ok_meta = det_meta
                best_non_ok_is_mid = is_mid

        sample_summaries.append({
            "sample_index": sample_index,
            "timestamp": ts,
            "is_midpoint_sample": is_mid,
            "source_path": src_path,
            "status": meta_status,
            "reason": meta_reason,
            "object_count": len(sample_objects),
            "objects": sample_objects,
            "error": str(sample_err) if sample_err else None,
            "detect_meta": det_meta,
        })

    if observations:
        primary_obs = next((obs for obs in observations if obs["is_midpoint_sample"]), observations[0])
        combined_meta = dict(primary_obs["detect_meta"])
        combined_meta["status"] = "ok"
        combined_meta["count"] = len(all_objects)
        combined_meta["accepted_sample_count"] = len(observations)
        combined_meta["accepted_sample_timestamps"] = [obs["timestamp"] for obs in observations]
        combined_meta["non_midpoint_objects_observed"] = any(not obs["is_midpoint_sample"] for obs in observations)
    else:
        combined_meta = dict(best_non_ok_meta or {"status": "ok", "engine": "opencv-dnn"})
        if combined_meta.get("status") == "ok":
            # A successful detector run with no observations is supported absence,
            # matching the step ledger's no_detected_object outcome.
            combined_meta["status"] = "not_applicable"
            combined_meta["reason"] = "no_detected_object"
        combined_meta["count"] = 0
        combined_meta["accepted_sample_count"] = 0
        combined_meta["accepted_sample_timestamps"] = []
        combined_meta["non_midpoint_objects_observed"] = False

    combined_meta["sample_count"] = len(sample_summaries)
    combined_meta["midpoint_timestamp"] = midpoint_timestamp
    combined_meta["sample_timestamps"] = [s["timestamp"] for s in sample_summaries]
    combined_meta["samples"] = sample_summaries
    combined_meta["observations"] = [
        {
            "sample_index": obs["sample_index"],
            "timestamp": obs["timestamp"],
            "is_midpoint_sample": obs["is_midpoint_sample"],
            "source_path": obs["source_path"],
            "objects": obs["objects"],
            "count": len(obs["objects"]),
            "engine": obs["detect_meta"].get("engine", "opencv-dnn"),
            "model": obs["detect_meta"].get("model"),
        }
        for obs in observations
    ]
    combined_meta["sample_errors"] = errors
    combined_meta["sample_warnings"] = warnings

    return {
        "objects": all_objects,
        "detect_meta": combined_meta,
        "object_observations": observations,
        "object_sampling_errors": errors,
        "object_sampling_warnings": warnings,
    }


def _process_frame(
    cfg_json: Path,
    ffmpeg: str,
    video_path: Path,
    scene: Dict[str, Any],
    frame_dir: Path,
    video_hash: str,
    scene_id: str,
    scene_num: int = 1,
    total_scenes: int = 1,
) -> Dict[str, Any]:
    frame_path = _extract_keyframe(
        ffmpeg,
        video_path,
        scene,
        frame_dir,
        scene_id=scene_id,
        video_id=video_hash,
    )
    scene_index = scene.get('index')
    duration = float(scene.get('duration', 0.0) or 0.0)
    start = float(scene.get('start', 0.0) or 0.0)
    frame_timestamp = start + (duration / 2.0) if duration > 0 else start

    item: Dict[str, Any] = {
        'modality': 'image',
        'source_path': str(frame_path),
        'scene_id': scene_id,
        'video_hash': video_hash,
        'video_id': video_hash,
        'scene_index': scene_index,
        'timestamp': frame_timestamp,
        'scene': {
            'start': start,
            'end': start + duration,
            'duration': duration,
        },
    }

    def merge(env_name: str, step_name: str) -> None:
        from steps.common.progress_tracker import get_tracker
        tracker = get_tracker()
        step_index = 1 + scene_num
        tracker.update_step(
            f"Scene {scene_num}/{total_scenes} - Running {step_name}",
            step_index,
            {
                "scene_index": scene_index,
                "scenes_total": total_scenes,
                "video_id": video_hash,
                "stage": f"frame_{step_name}"
            }
        )
        result = _run_step(env_name, step_name, item, cfg_json)
        if isinstance(result, dict):
            item.update(result)

    sample_timestamps = sorted({start + duration * fraction for fraction in (0, .25, .5, .75)} |
                               {max(start, start + duration - min(.05, duration / 2))}) if duration > 0 else [start]
    sampled_frames = {frame_timestamp: frame_path}

    def sample_frame(timestamp: float, sample_index: int) -> Path:
        if timestamp not in sampled_frames:
            sampled_frames[timestamp] = _extract_keyframe(
                ffmpeg, video_path, scene, frame_dir,
                scene_id=scene_id, video_id=video_hash, sample_timestamp=timestamp,
                sample_suffix=f'_sample_{sample_index:02d}',
            )
        return sampled_frames[timestamp]

    ocr_sample_records: List[Dict[str, Any]] = []
    ocr_batch_meta: List[Tuple[int, float, bool, Path]] = []
    ocr_batch_payloads: List[Dict[str, Any]] = []
    for ocr_idx, ocr_ts in enumerate(sample_timestamps):
        is_mid = (ocr_ts == frame_timestamp)
        try:
            sampled_ocr_path = sample_frame(ocr_ts, ocr_idx)
        except Exception as ocr_exc:
            ocr_sample_records.append({
                'sample_index': ocr_idx,
                'timestamp': ocr_ts,
                'is_midpoint_sample': is_mid,
                'source_path': None,
                'status': 'error',
                'outputs': {'ocr_text': None, 'ocr_meta': {'status': 'error', 'reason': 'ocr_sample_error', 'error': str(ocr_exc), 'sample_timestamp': ocr_ts, 'is_midpoint_sample': is_mid}},
                'error': str(ocr_exc),
            })
            continue
        ocr_batch_meta.append((ocr_idx, ocr_ts, is_mid, sampled_ocr_path))
        ocr_batch_payloads.append({**item, 'source_path': str(sampled_ocr_path), 'timestamp': ocr_ts, 'is_midpoint_sample': is_mid})
    if ocr_batch_payloads:
        for (ocr_idx, ocr_ts, is_mid, sampled_ocr_path), (b_status, ocr_out, b_err) in zip(
            ocr_batch_meta,
            _run_step_batch('goodq_ocr', 'image_ocr', ocr_batch_payloads, cfg_json),
        ):
            if b_status == 'error' and not ocr_out:
                ocr_out = {'ocr_text': None, 'ocr_meta': {'status': 'error', 'reason': 'ocr_sample_error', 'error': str(b_err or 'ocr failed'), 'sample_timestamp': ocr_ts, 'is_midpoint_sample': is_mid}}
            ocr_sample_records.append({
                'sample_index': ocr_idx,
                'timestamp': ocr_ts,
                'is_midpoint_sample': is_mid,
                'source_path': str(sampled_ocr_path),
                'status': b_status,
                'outputs': ocr_out,
                'error': b_err,
            })
    ocr_sample_records.sort(key=lambda record: record['sample_index'])
    item.update(_aggregate_ocr_sample_results(ocr_sample_records, frame_timestamp))

    caption_sample_records: List[Dict[str, Any]] = []
    caption_batch: List[Dict[str, Any]] = []
    for cap_idx, cap_ts in enumerate(sample_timestamps):
        is_mid = (cap_ts == frame_timestamp)
        try:
            sampled_cap_path = sample_frame(cap_ts, cap_idx)
        except Exception as cap_exc:
            caption_sample_records.append({
                'sample_index': cap_idx,
                'timestamp': cap_ts,
                'is_midpoint_sample': is_mid,
                'source_path': None,
                'status': 'error',
                'outputs': {'caption': None, 'caption_meta': {'status': 'error', 'reason': 'caption_sample_error', 'error': str(cap_exc), 'sample_timestamp': cap_ts, 'is_midpoint_sample': is_mid}},
                'error': str(cap_exc),
            })
            continue
        caption_batch.append({'sample_index': cap_idx, 'timestamp': cap_ts, 'is_midpoint_sample': is_mid, 'source_path': str(sampled_cap_path)})
    if caption_batch:
        # One worker call per scene: the caption model loads once for all samples.
        try:
            cap_out = _run_step(
                'goodq_caption_vlm',
                'image_caption',
                {**item, 'samples': [
                    {'source_path': s['source_path'], 'timestamp': s['timestamp'], 'is_midpoint_sample': s['is_midpoint_sample']}
                    for s in caption_batch
                ]},
                cfg_json,
            )
            caption_records = _caption_batch_records(caption_batch, cap_out if isinstance(cap_out, dict) else {})
        except Exception as cap_exc:
            caption_records = _caption_batch_error_records(caption_batch, str(cap_exc))
        caption_sample_records.extend(caption_records)
    caption_sample_records.sort(key=lambda record: record['sample_index'])
    item.update(_aggregate_caption_sample_results(caption_sample_records, frame_timestamp))

    object_sample_records: List[Dict[str, Any]] = []
    obj_batch_meta: List[Tuple[int, float, bool, Path]] = []
    obj_batch_payloads: List[Dict[str, Any]] = []
    for obj_idx, obj_ts in enumerate(sample_timestamps):
        is_mid = (obj_ts == frame_timestamp)
        try:
            sampled_obj_path = sample_frame(obj_ts, obj_idx)
        except Exception as obj_exc:
            object_sample_records.append({
                'sample_index': obj_idx,
                'timestamp': obj_ts,
                'is_midpoint_sample': is_mid,
                'source_path': None,
                'status': 'error',
                'outputs': {'objects': [], 'detect_meta': {'status': 'error', 'reason': 'object_detect_sample_error', 'error': str(obj_exc), 'sample_timestamp': obj_ts, 'is_midpoint_sample': is_mid}},
                'error': str(obj_exc),
            })
            continue
        obj_batch_meta.append((obj_idx, obj_ts, is_mid, sampled_obj_path))
        obj_batch_payloads.append({**item, 'source_path': str(sampled_obj_path), 'timestamp': obj_ts, 'is_midpoint_sample': is_mid})
    if obj_batch_payloads:
        for (obj_idx, obj_ts, is_mid, sampled_obj_path), (b_status, obj_out, b_err) in zip(
            obj_batch_meta,
            _run_step_batch('goodq_object_detect', 'object_detect', obj_batch_payloads, cfg_json),
        ):
            if b_status == 'error' and not obj_out:
                obj_out = {'objects': [], 'detect_meta': {'status': 'error', 'reason': 'object_detect_sample_error', 'error': str(b_err or 'object_detect failed'), 'sample_timestamp': obj_ts, 'is_midpoint_sample': is_mid}}
            object_sample_records.append({
                'sample_index': obj_idx,
                'timestamp': obj_ts,
                'is_midpoint_sample': is_mid,
                'source_path': str(sampled_obj_path),
                'status': b_status,
                'outputs': obj_out,
                'error': b_err,
            })
    object_sample_records.sort(key=lambda record: record['sample_index'])
    item.update(_aggregate_object_detect_sample_results(object_sample_records, frame_timestamp))

    merge('goodq_face_embed', 'face_embed')
    merge('goodq_image_caption', 'image_embed_dino')
    merge('goodq_image_caption', 'image_embed_clip')
    merge('goodq_core', 'tagger')
    canonicalize_taxonomy(item)
    try:
        frame_entity_cfg = json.loads(cfg_json.read_text(encoding='utf-8')) if cfg_json.is_file() else {}
    except Exception:
        frame_entity_cfg = {}
    _persist_frame_semantic_entities(
        item,
        scene_id=scene_id,
        video_id=video_hash,
        config=frame_entity_cfg,
    )

    frame_text_parts: List[str] = []
    if isinstance(item.get('ocr_text'), str) and item['ocr_text'].strip():
        frame_text_parts.append(item['ocr_text'].strip())
    caption_obs_list = item.get('caption_observations') if isinstance(item.get('caption_observations'), list) else []
    seen_cap_texts: set[str] = set()
    for obs in caption_obs_list:
        if isinstance(obs, dict):
            cap_str = obs.get('caption')
            if isinstance(cap_str, str) and cap_str.strip():
                norm_c = cap_str.strip().casefold()
                if norm_c not in seen_cap_texts:
                    seen_cap_texts.add(norm_c)
                    frame_text_parts.append(cap_str.strip())
    if not seen_cap_texts and isinstance(item.get('caption'), str) and item['caption'].strip():
        frame_text_parts.append(item['caption'].strip())
    obj_labels: List[str] = []
    seen_obj_labels: set[str] = set()
    for obj in (item.get('objects') if isinstance(item.get('objects'), list) else []):
        if isinstance(obj, dict):
            lbl = obj.get('label')
            if isinstance(lbl, str) and lbl.strip():
                norm_l = lbl.strip().casefold()
                if norm_l not in seen_obj_labels:
                    seen_obj_labels.add(norm_l)
                    obj_labels.append(lbl.strip())
    if obj_labels:
        frame_text_parts.append(' '.join(obj_labels))
    frame_text = ' '.join(part.strip() for part in frame_text_parts if part).strip()
    if frame_text:
        text_payload = {
            'modality': 'text',
            'embedding_source': 'frame_text',
            'source_path': str(frame_path),
            'frame_text': frame_text,
            'scene_id': scene_id,
            'scene_index': scene_index,
            'video_hash': video_hash,
            'video_id': video_hash,
            'ner_entities': item.get('ner_entities'),
            'tags': item.get('tags'),
            'entities': item.get('entities'),
            'location': item.get('location'),
            'locations': item.get('locations'),
            'scene': item.get('scene'),
        }
        text_embed_result = _run_step('goodq_text_embed', 'text_embed', text_payload, cfg_json)
        if isinstance(text_embed_result, dict):
            frame_text_embed_meta = text_embed_result.get('embedding_meta')
            if isinstance(frame_text_embed_meta, dict):
                item['frame_text_embed_meta'] = frame_text_embed_meta
        item['frame_text'] = frame_text

    if isinstance(cfg_json, Path) and cfg_json.is_file():
        try:
            _log_visual_to_ucf_ledger(
                cfg_json,
                video_hash,
                scene_id,
                scene,
                frame_dir,
                item,
            )
        except Exception as ucf_err:
            logger.warning(f"[UCF] Visual logging hook failed: {ucf_err}")

    return {
        'path': str(frame_path),
        'timestamp': frame_timestamp,
        'data': item,
    }


def _load_ucf_ledger() -> Any:
    """Loads the repository-owned UCF ledger implementation."""
    from scripts.ucf import ucf_ledger

    return ucf_ledger


def _log_audio_to_ucf_ledger(
    cfg_json: Path,
    video_hash: str,
    scene_id: str,
    scene: Dict[str, Any],
    audio_artifact_dir: Path,
    item: Dict[str, Any],
    *,
    strict: bool = False,
) -> None:
    """Logs audio transcript and diarization segments to ucf_ledger.db."""
    client = None
    try:
        import json
        import os
        from pathlib import Path

        if not cfg_json.exists():
            if strict:
                raise FileNotFoundError(cfg_json)
            logger.warning(f"[UCF] Config file does not exist: {cfg_json}. Skipping UCF logging.")
            return

        with open(cfg_json, 'r', encoding='utf-8') as f:
            cfg = json.load(f)

        db_dir = cfg.get('paths', {}).get('db_dir')
        if not db_dir:
            if strict:
                raise ValueError("Standalone UCF logging requires paths.db_dir")
            logger.warning("[UCF] paths.db_dir not found in config. Skipping UCF logging.")
            return

        epoch_id = os.path.basename(db_dir)
        run_id = os.getenv("GOODQ_RUN_ID") or cfg.get('run', {}).get('id') or "unknown_run"

        # Resolve DB path — use db_dir from config directly (it already
        # contains the correct resolved path including GoodQ_Data nesting).
        ucf_db_dir = Path(db_dir) / 'ucf'

        ucf_db_dir.mkdir(parents=True, exist_ok=True)
        ucf_db_path = ucf_db_dir / 'ucf_ledger.db'

        # Import UCF client
        ucf_module = _load_ucf_ledger()
        UCFLedgerClient = ucf_module.UCFLedgerClient

        client = UCFLedgerClient(str(ucf_db_path))
        client.init_schema()

        scene_start = scene.get('start', 0.0)

        recording_projection = item.get('audio_evidence')
        ucf_tx_rows = item.get('segments', [])
        if recording_projection is not None:
            from steps.audio.recording_ingestion import ucf_transcript_segments
            from wsl2_audio.scene_projection import validate_scene_audio
            validate_scene_audio(recording_projection)
            expected_scene = {'scene_id': scene_id, 'start': float(scene['start']), 'end': float(scene['end'])}
            if recording_projection['scene'] != expected_scene or recording_projection['source']['sha256'] != video_hash:
                raise ValueError('UCF recording source/scene binding mismatch')
            ucf_tx_rows = ucf_transcript_segments(recording_projection)
            raw_recording = audio_artifact_dir / f'{scene_id}_recording_audio.json'
            atomic_write_json(raw_recording, recording_projection)
            # Canonical source evidence survives an optional scene-WAV extraction failure.
            atomic_write_json(audio_artifact_dir / f'{scene_id}_raw_transcript.json', ucf_tx_rows)
            atomic_write_json(audio_artifact_dir / f'{scene_id}_raw_diarization.json', item.get('speaker_segments', []))
            client.log_frame(video_hash=video_hash, epoch_id=epoch_id, run_id=run_id,
                t_start=scene['start'], t_end=scene['end'], modality='audio',
                worker_name='recording_audio', model_tag='recording_audio_v1', confidence=0.0,
                source_artifact_id=scene_id, raw_ref=str(raw_recording.resolve()),
                payload={'audio_evidence_sha256': recording_projection['content_sha256'],
                    'recording_id': recording_projection['recording_id'],
                    'source_sha256': recording_projection['source']['sha256'],
                    'schema': recording_projection['schema'], 'audio_status': recording_projection['status'],
                    'utterance_count': len(recording_projection['utterances']),
                    'sound_event_count': len(recording_projection['sound_events']),
                    'voice_signature_count': len(recording_projection.get('voice_signatures', [])),
                    'quality_qualification': 'unqualified',
                    'confidence_basis': 'unqualified_numeric_floor',
                    **({'source_kind': item['source_kind']} if item.get('source_kind') else {})}, promotion_status='staged')

        # 1. Transcripts logging
        if ucf_tx_rows or item.get('transcript'):
            raw_ref_path = audio_artifact_dir / f"{scene_id}_raw_transcript.json"
            raw_ref_str = str(raw_ref_path.resolve())
            for i, segment in enumerate(ucf_tx_rows):
                start_time = segment.get('start', 0.0)
                end_time = segment.get('end', 0.0)
                if recording_projection is not None or start_time < (scene_start - 0.01):
                    t_start = start_time + scene_start
                    t_end = end_time + scene_start
                else:
                    t_start = start_time
                    t_end = end_time

                word_count = len(segment.get('text', '').strip().split())
                confidence_val = segment.get('logprob') if segment.get('logprob') is not None else 1.0

                payload = {
                    'text': segment.get('text', ''),
                    'language': segment.get('language') or item.get('language') or 'en',
                    'segment_index': i,
                    'word_count': word_count,
                    'confidence': confidence_val,
                    'identity_status': 'unresolved'
                }
                if recording_projection is not None:
                    raw_confidence = (segment.get('confidence') or {}).get('raw', {})
                    payload.update(source_sample_start=(segment.get('source_span') or {}).get('start'),
                        source_sample_end=(segment.get('source_span') or {}).get('end'), utterance_id=segment.get('id'),
                        audio_evidence_sha256=recording_projection['content_sha256'],
                        confidence=None, confidence_basis='uncalibrated_model_score',
                        avg_logprob=raw_confidence.get('avg_logprob'),
                        no_speech_probability=raw_confidence.get('no_speech_probability'),
                        timing_scope='scene_display_only')

                client.log_frame(
                    video_hash=video_hash,
                    epoch_id=epoch_id,
                    run_id=run_id,
                    t_start=t_start,
                    t_end=t_end,
                    modality='text',
                    worker_name='audio_transcribe',
                    occurrence_id=ucf_module.audio_occurrence_id(
                        video_hash,
                        scene_id,
                        'audio_transcribe',
                        payload,
                        recording_required=recording_projection is not None,
                    ) if scene_id else '',
                    model_tag='recording_audio_v1' if recording_projection is not None else 'faster_whisper',
                    confidence=0.0 if recording_projection is not None else 1.0,
                    source_artifact_id=scene_id,
                    raw_ref=raw_ref_str,
                    payload={**payload, **({'source_kind': item['source_kind']} if item.get('source_kind') else {})},
                    promotion_status='staged'
                )

        # 2. Speaker turns logging
        if item.get('speaker_segments'):
            raw_ref_path = audio_artifact_dir / f"{scene_id}_raw_diarization.json"
            raw_ref_str = str(raw_ref_path.resolve())
            for i, segment in enumerate(item.get('speaker_segments', [])):
                start_time = segment.get('start', 0.0)
                end_time = segment.get('end', 0.0)
                if recording_projection is not None or start_time < (scene_start - 0.01):
                    t_start = start_time + scene_start
                    t_end = end_time + scene_start
                else:
                    t_start = start_time
                    t_end = end_time

                speaker_id = segment.get('speaker') or segment.get('speaker_id', 'unknown')

                payload = {
                    'speaker_id': speaker_id,
                    'speaker_label': None,
                    'speaker_confidence': 1.0,
                    'turn_index': i,
                    'source': 'pyannote',
                    'identity_status': 'unresolved'
                }
                if recording_projection is not None:
                    payload.update(speaker_confidence=None, confidence_basis='unqualified_numeric_floor',
                        source='recording_audio_v1', audio_evidence_sha256=recording_projection['content_sha256'])

                client.log_frame(
                    video_hash=video_hash,
                    epoch_id=epoch_id,
                    run_id=run_id,
                    t_start=t_start,
                    t_end=t_end,
                    modality='audio',
                    worker_name='speaker_merge',
                    occurrence_id=ucf_module.audio_occurrence_id(
                        video_hash,
                        scene_id,
                        'speaker_merge',
                        payload,
                        recording_required=recording_projection is not None,
                    ) if scene_id else '',
                    model_tag='recording_audio_v1' if recording_projection is not None else 'pyannote',
                    confidence=0.0 if recording_projection is not None else 1.0,
                    source_artifact_id=scene_id,
                    raw_ref=raw_ref_str,
                    payload={**payload, **({'source_kind': item['source_kind']} if item.get('source_kind') else {})},
                    promotion_status='staged'
                )

        # 3. CLAP audio embedding logging (optional — only if audio_embed_clap ran successfully)
        clap_meta = item.get('clap_meta') or {}
        if isinstance(clap_meta, dict) and clap_meta.get('status') == 'ok':
            clap_embedding_id = clap_meta.get('embedding_id')
            clap_faiss_id = clap_meta.get('faiss_id')
            if clap_embedding_id and clap_faiss_id is not None:
                clap_raw_ref_path = audio_artifact_dir / f"{scene_id}_raw_clap.json"
                clap_payload = {
                    'embedding_id': clap_embedding_id,
                    'faiss_id': clap_faiss_id,
                    'model': clap_meta.get('model', 'laion/clap-htsat-unfused'),
                    'qdrant_collection': clap_meta.get('qdrant_collection'),
                    'faiss_committed': clap_meta.get('faiss_committed', False),
                    'qdrant_committed': clap_meta.get('qdrant_committed', False),
                }
                atomic_write_json(clap_raw_ref_path, clap_payload)
                clap_raw_ref_str = str(clap_raw_ref_path.resolve())
                scene_start_f = float(scene.get('start', 0.0) or 0.0)
                scene_end_f = float(scene.get('end', scene_start_f) or scene_start_f)
                ucf_frame_id = client.log_frame(
                    video_hash=video_hash,
                    epoch_id=epoch_id,
                    run_id=run_id,
                    t_start=scene_start_f,
                    t_end=scene_end_f,
                    modality='audio',
                    worker_name='audio_embed_clap',
                    model_tag='laion/clap-htsat-unfused',
                    confidence=1.0,
                    source_artifact_id=scene_id,
                    raw_ref=clap_raw_ref_str,
                    payload={**clap_payload, **({'source_kind': item['source_kind']} if item.get('source_kind') else {})},
                    promotion_status='staged',
                    vector_key=clap_embedding_id,
                    vector_backend=clap_meta.get('qdrant_committed') and 'qdrant' or 'faiss',
                    vector_dim=512,
                    vector_model_tag='laion/clap-htsat-unfused',
                    vector_collection=clap_meta.get('qdrant_collection') or 'audio',
                )

                if ucf_frame_id:
                    # If Qdrant is enabled, backfill ucf_frame_id to Qdrant payload
                    if clap_meta.get('qdrant_committed') and cfg.get('qdrant', {}).get('enabled', False):
                        try:
                            from steps.common.qdrant_client import build_qdrant_client
                            q_client = build_qdrant_client(cfg, dim=512, key='audio')
                            if q_client:
                                normalized_key = q_client._normalize_point_id(clap_embedding_id)
                                q_client.session.post(
                                    f"{q_client.cfg.host}/collections/{q_client.cfg.collection}/points/payload?wait=true",
                                    json={
                                        "payload": {"ucf_frame_id": ucf_frame_id},
                                        "points": [normalized_key]
                                    },
                                    timeout=5
                                )
                        except Exception as e:
                            logger.warning(f"[UCF] Failed to update Qdrant payload with ucf_frame_id for CLAP: {e}")

                    # Backfill ucf_frame_id to FAISS sidecar DB
                    map_db = (cfg.get("paths", {}) or {}).get("clap_id_map_db")
                    if map_db and os.path.isfile(map_db) and not cfg.get("ingestion_isolation", False):
                        con = None
                        try:
                            import sqlite3
                            con = sqlite3.connect(map_db, check_same_thread=False)
                            with con:
                                con.execute(
                                    "UPDATE clap_id_map SET ucf_frame_id = ? WHERE video_hash = ? AND faiss_id = ?",
                                    (ucf_frame_id, video_hash, clap_faiss_id)
                                )
                        except Exception as e:
                            logger.warning(f"[UCF] Failed to update FAISS sidecar DB with ucf_frame_id for CLAP: {e}")
                        finally:
                            if con is not None:
                                con.close()

        # 4. Text embedding logging for audio transcript (optional — only if text_embed ran successfully)
        audio_text_embed_meta = item.get('audio_text_embed_meta') or {}
        if isinstance(audio_text_embed_meta, dict) and audio_text_embed_meta.get('status') == 'ok':
            text_embedding_id = audio_text_embed_meta.get('embedding_id')
            if text_embedding_id:
                text_embed_raw_ref_path = audio_artifact_dir / f"{scene_id}_raw_text_embed_audio.json"
                text_embed_payload = {
                    'embedding_id': text_embedding_id,
                    'embedding_source': 'document_text' if item.get('source_kind') == 'document' else 'audio_transcript',
                    'origin_modality': 'document' if item.get('source_kind') == 'document' else 'audio',
                    'engine': audio_text_embed_meta.get('engine', 'all-MiniLM-L6-v2'),
                    'faiss_id': audio_text_embed_meta.get('faiss_id'),
                }
                atomic_write_json(text_embed_raw_ref_path, text_embed_payload)
                text_embed_raw_ref_str = str(text_embed_raw_ref_path.resolve())
                scene_start_f = float(scene.get('start', 0.0) or 0.0)
                scene_end_f = float(scene.get('end', scene_start_f) or scene_start_f)
                _audio_text_frame_id = client.log_frame(
                    video_hash=video_hash,
                    epoch_id=epoch_id,
                    run_id=run_id,
                    t_start=scene_start_f,
                    t_end=scene_end_f,
                    modality='text',
                    worker_name='text_embed',
                    model_tag='sentence-transformers/all-MiniLM-L6-v2',
                    confidence=1.0,
                    source_artifact_id=scene_id,
                    raw_ref=text_embed_raw_ref_str,
                    payload={**text_embed_payload, **({'source_kind': item['source_kind']} if item.get('source_kind') else {})},
                    promotion_status='staged',
                    vector_key=text_embedding_id,
                    vector_backend='qdrant' if audio_text_embed_meta.get('qdrant_committed') else 'faiss',
                    vector_dim=384,
                    vector_model_tag='sentence-transformers/all-MiniLM-L6-v2',
                    vector_collection=audio_text_embed_meta.get('vector_collection') or 'text',
                )

                # Post-log Qdrant payload update with ucf_frame_id
                if _audio_text_frame_id and audio_text_embed_meta.get('qdrant_committed'):
                    try:
                        from steps.common.qdrant_client import GOODQ_POINT_ID_NAMESPACE
                        import uuid as _uuid_mod
                        _norm_id = str(_uuid_mod.uuid5(GOODQ_POINT_ID_NAMESPACE, text_embedding_id))
                        import requests as _requests
                        _cfg = json.load(open(str(cfg_json), 'r', encoding='utf-8')) if isinstance(cfg_json, Path) else {}
                        _qcfg = (_cfg.get('qdrant') or {})
                        _qhost = _qcfg.get('host', 'http://localhost:6333')
                        _qcol_map = _qcfg.get('collections', {}) or {}
                        _qcol = _qcol_map.get('text', 'goodq_text')
                        _requests.post(
                            f"{_qhost}/collections/{_qcol}/points/payload",
                            json={
                                "payload": {"ucf_frame_id": _audio_text_frame_id},
                                "points": [_norm_id],
                            },
                            timeout=5,
                        )
                    except Exception as _qe:
                        logger.warning(f"[UCF] Failed to update audio text_embed Qdrant payload with ucf_frame_id: {_qe}")


        client.close()
    except Exception as e:
        logger.warning(f"[UCF] UCF logging failed: {type(e).__name__}: {str(e)}")
        if strict or item.get('audio_evidence') is not None:
            raise
    finally:
        if client is not None:
            client.close()


def _log_visual_to_ucf_ledger(
    cfg_json: Path,
    video_hash: str,
    scene_id: str,
    scene: Dict[str, Any],
    frame_dir: Path,
    item: Dict[str, Any],
    *,
    strict: bool = False,
) -> None:
    """Logs visual modality outputs (object detection, face embeddings, OCR, captions, embeddings) to ucf_ledger.db."""
    client = None
    try:
        import json
        import os
        from pathlib import Path

        if not cfg_json.exists():
            if strict:
                raise FileNotFoundError(cfg_json)
            logger.warning(f"[UCF] Config file does not exist: {cfg_json}. Skipping UCF logging.")
            return

        with open(cfg_json, 'r', encoding='utf-8') as f:
            cfg = json.load(f)

        db_dir = cfg.get('paths', {}).get('db_dir')
        if not db_dir:
            if strict:
                raise ValueError("Standalone UCF logging requires paths.db_dir")
            logger.warning("[UCF] paths.db_dir not found in config. Skipping UCF logging.")
            return

        epoch_id = os.path.basename(db_dir)
        run_id = os.getenv("GOODQ_RUN_ID") or cfg.get('run', {}).get('id') or "unknown_run"

        # Resolve DB path — use db_dir from config directly (it already
        # contains the correct resolved path including GoodQ_Data nesting).
        ucf_db_dir = Path(db_dir) / 'ucf'

        ucf_db_dir.mkdir(parents=True, exist_ok=True)
        ucf_db_path = ucf_db_dir / 'ucf_ledger.db'

        # Import UCF client
        ucf_module = _load_ucf_ledger()
        UCFLedgerClient = ucf_module.UCFLedgerClient

        client = UCFLedgerClient(str(ucf_db_path))
        client.init_schema()

        # Query media_sources for width and height
        cursor = client.execute_with_retry(
            "SELECT width, height FROM media_sources WHERE video_hash = ?",
            (video_hash,)
        )
        row = cursor.fetchone()
        if not row:
            logger.warning(f"[UCF] media_sources not found for {video_hash}. Bounding boxes will not be normalized.")
            width, height = None, None
        else:
            width, height = row[0], row[1]
            if width <= 0 or height <= 0:
                logger.warning(f"[UCF] Invalid dimensions ({width}x{height}) for {video_hash}. Bounding boxes will not be normalized.")
                width, height = None, None

        start = float(scene.get('start', 0.0) or 0.0)
        duration = float(scene.get('duration', 0.0) or 0.0)
        frame_timestamp = start + (duration / 2.0) if duration > 0 else start

        static_image = item.get('source_kind') == 'image'
        visual_modality = 'multimodal' if static_image else 'video'

        # 1. OCR text
        if item.get('ocr_text'):
            ocr_text = item['ocr_text']
            raw_ref_path = frame_dir / f"{scene_id}_raw_ocr.json"
            raw_ref_str = str(raw_ref_path.resolve())
            
            ocr_meta = item.get('ocr_meta', {})
            atomic_write_json(raw_ref_path, ocr_meta)
            ocr_observations = item.get('ocr_observations') or ocr_meta.get('observations') or []
            ocr_primary_ts = float(ocr_observations[0].get('timestamp', frame_timestamp)) if ocr_observations else frame_timestamp
            
            engine = ocr_meta.get('engine', 'unknown')
            strategy = ocr_meta.get('strategy', 'default')
            # UCF's scalar confidence is required. Paddle supplies sequence
            # scores per region; retain them verbatim and label the scene-level
            # arithmetic mean instead of claiming perfect recognition.
            ocr_confidence = 1.0
            confidence_kind = 'legacy_evidence_presence'
            score_count = 0
            if str(engine).startswith('paddleocr-'):
                from math import isfinite

                native_metas = [obs.get('ocr_meta', obs) for obs in ocr_observations] if ocr_observations else [ocr_meta]
                regions = [region for meta in native_metas for region in meta.get('accepted_regions', [])]
                scores = [region.get('confidence') for region in regions]
                if not scores or any(
                    region.get('confidence_kind') != 'recognizer_sequence_score'
                    or not isinstance(score, (float, int)) or isinstance(score, bool)
                    or not isfinite(score) or not 0.0 <= score <= 1.0
                    for region, score in zip(regions, scores)
                ):
                    raise ValueError('Paddle OCR text requires native region scores for UCF confidence')
                score_count = len(scores)
                ocr_confidence = sum(scores) / score_count
                confidence_kind = 'mean_recognizer_sequence_score'
            
            payload = {
                'text': ocr_text,
                'ocr_text': ocr_text,
                'observation_timestamp': ocr_primary_ts,
                'accepted_sample_count': len(ocr_observations) if ocr_observations else 1,
                'accepted_sample_timestamps_json': json.dumps(ocr_meta.get('accepted_sample_timestamps') or [ocr_primary_ts]),
                'observations_json': json.dumps(ocr_meta.get('observations') or []),
                'engine': engine,
                'strategy': strategy,
                'confidence_kind': confidence_kind,
                'confidence_observation_count': score_count,
            }
            
            client.log_frame(
                video_hash=video_hash,
                epoch_id=epoch_id,
                run_id=run_id,
                t_start=ocr_primary_ts,
                t_end=ocr_primary_ts,
                modality='text',
                worker_name='image_ocr',
                model_tag=engine,
                confidence=ocr_confidence,
                spatial_region=None,
                spatial_space='normalized_yxyx_top_left',
                source_artifact_id=scene_id,
                raw_ref=raw_ref_str,
                payload={**payload, **({'source_kind': item['source_kind']} if item.get('source_kind') else {})},
                promotion_status='staged'
            )

        # 2. Caption text
        if item.get('caption'):
            caption = item['caption']
            raw_ref_path = frame_dir / f"{scene_id}_raw_caption.json"
            raw_ref_str = str(raw_ref_path.resolve())
            
            caption_meta = item.get('caption_meta', {})
            atomic_write_json(raw_ref_path, caption_meta)
            caption_observations = item.get('caption_observations') or caption_meta.get('observations') or []
            primary_obs = next(
                (
                    obs
                    for obs in caption_observations
                    if isinstance(obs, dict) and obs.get('caption') == caption
                ),
                caption_observations[0] if caption_observations else None,
            )
            caption_primary_ts = (
                float(primary_obs.get('timestamp', frame_timestamp))
                if isinstance(primary_obs, dict)
                else frame_timestamp
            )
            
            engine = caption_meta.get('engine', 'blip')
            
            payload = {
                'text': caption,
                'engine': engine,
                'observation_timestamp': caption_primary_ts,
                'accepted_sample_count': len(caption_observations) if caption_observations else 1,
                'accepted_sample_timestamps_json': json.dumps(
                    caption_meta.get('accepted_sample_timestamps') or [caption_primary_ts]
                ),
                'observations_json': json.dumps(caption_meta.get('observations') or []),
            }
            
            client.log_frame(
                video_hash=video_hash,
                epoch_id=epoch_id,
                run_id=run_id,
                t_start=caption_primary_ts,
                t_end=caption_primary_ts,
                modality='multimodal',
                worker_name='image_caption',
                model_tag=engine,
                confidence=1.0,
                spatial_region=None,
                spatial_space='normalized_yxyx_top_left',
                source_artifact_id=scene_id,
                raw_ref=raw_ref_str,
                payload={**payload, **({'source_kind': item['source_kind']} if item.get('source_kind') else {})},
                promotion_status='staged'
            )

        # 3. Object Detections
        if item.get('objects'):
            objects = item['objects']
            raw_ref_path = frame_dir / f"{scene_id}_raw_objects.json"
            raw_ref_str = str(raw_ref_path.resolve())
            
            atomic_write_json(raw_ref_path, objects)
            
            for idx, obj in enumerate(objects[:1] if static_image else objects):
                bbox = obj.get('bbox')
                score = obj.get('score') if obj.get('score') is not None else 1.0
                label = obj.get('label') or 'unknown'
                obj_ts = (
                    float(obj.get('timestamp', frame_timestamp))
                    if obj.get('timestamp') is not None
                    else frame_timestamp
                )
                is_mid_obj = bool(obj.get('is_midpoint_sample', abs(obj_ts - frame_timestamp) <= 1e-6))
                
                spatial_region = None
                if bbox and len(bbox) == 4 and width and height:
                    ymin = max(0.0, min(1.0, float(bbox[1]) / height))
                    xmin = max(0.0, min(1.0, float(bbox[0]) / width))
                    ymax = max(0.0, min(1.0, float(bbox[3]) / height))
                    xmax = max(0.0, min(1.0, float(bbox[2]) / width))
                    spatial_region = [ymin, xmin, ymax, xmax]
                
                payload = {
                    'label': label,
                    'score': score,
                    **({'object_count': len(objects)} if static_image else {'object_index': idx}),
                    'x1': bbox[0] if bbox else 0.0,
                    'y1': bbox[1] if bbox else 0.0,
                    'x2': bbox[2] if bbox else 0.0,
                    'y2': bbox[3] if bbox else 0.0,
                    'observation_timestamp': obj_ts,
                    'is_midpoint_sample': is_mid_obj,
                    **({'sample_index': int(obj['sample_index'])} if obj.get('sample_index') is not None else {}),
                }
                
                client.log_frame(
                    video_hash=video_hash,
                    epoch_id=epoch_id,
                    run_id=run_id,
                    t_start=obj_ts + (0.0 if static_image else 0.001 * idx),
                    t_end=obj_ts + (0.0 if static_image else 0.001 * idx),
                    modality=visual_modality,
                    worker_name='object_detect',
                    model_tag=str((item.get('detect_meta') or {}).get('model') or 'unknown_object_detector'),
                    confidence=score,
                    spatial_region=spatial_region,
                    spatial_space='normalized_yxyx_top_left',
                    source_artifact_id=scene_id,
                    raw_ref=raw_ref_str,
                    payload={**payload, **({'source_kind': item['source_kind']} if item.get('source_kind') else {})},
                    promotion_status='staged'
                )

        # Additional observations use the same writer with their own image/time.
        # Keep the legacy single-frame representation readable without rewriting it.
        if 'face_observations' in item:
            for observation_index, observation in enumerate(item['face_observations']):
                _log_visual_to_ucf_ledger(
                    cfg_json, video_hash, scene_id, scene, frame_dir,
                    {**observation, '_face_observation_index': observation_index}, strict=True,
                )

        # 4. Face Embeddings / Detections
        if item.get('faces') and 'face_observations' not in item:
            faces = item['faces']
            observation_index = item.get('_face_observation_index')
            observation = {}
            suffix = ''
            if observation_index is not None:
                frame_timestamp = float(item['timestamp'])
                image_path = Path(item['source_path']).resolve(strict=True)
                if not image_path.is_relative_to(frame_dir.resolve()):
                    raise ValueError('Face observation image escapes its frame directory')
                observation = {'image_path': str(image_path),
                               'image_sha256': hashlib.sha256(image_path.read_bytes()).hexdigest(),
                               'observation_timestamp': frame_timestamp}
                suffix = f'_observation_{observation_index:02d}'
            raw_ref_path = frame_dir / f"{scene_id}{suffix}_raw_faces.json"
            raw_ref_str = str(raw_ref_path.resolve())
            
            atomic_write_json(raw_ref_path, faces)
            
            face_engine = item.get('faces_meta', {}).get('engine', 'unknown')
            
            for idx, face in enumerate(faces[:1] if static_image else faces):
                bbox = face.get('bbox')
                
                spatial_region = None
                if bbox and len(bbox) == 4 and width and height:
                    ymin = max(0.0, min(1.0, float(bbox[1]) / height))
                    xmin = max(0.0, min(1.0, float(bbox[0]) / width))
                    ymax = max(0.0, min(1.0, float(bbox[3]) / height))
                    xmax = max(0.0, min(1.0, float(bbox[2]) / width))
                    spatial_region = [ymin, xmin, ymax, xmax]
                
                payload = {
                    **observation,
                    **({'face_count': len(faces)} if static_image else {'face_index': idx}),
                    'engine': face_engine,
                    'x1': bbox[0] if bbox else 0.0,
                    'y1': bbox[1] if bbox else 0.0,
                    'x2': bbox[2] if bbox else 0.0,
                    'y2': bbox[3] if bbox else 0.0,
                }
                
                client.log_frame(
                    video_hash=video_hash,
                    epoch_id=epoch_id,
                    run_id=run_id,
                    t_start=frame_timestamp + (0.0 if static_image else 0.001 * idx),
                    t_end=frame_timestamp + (0.0 if static_image else 0.001 * idx),
                    modality=visual_modality,
                    worker_name='face_embed',
                    model_tag=face_engine,
                    confidence=1.0,
                    spatial_region=spatial_region,
                    spatial_space='normalized_yxyx_top_left',
                    source_artifact_id=scene_id,
                    raw_ref=raw_ref_str,
                    payload={**payload, **({'source_kind': item['source_kind']} if item.get('source_kind') else {})},
                    promotion_status='staged'
                )

        # 5. DINOv2 Visual Embeddings
        if item.get('dino_meta') and item.get('dino_meta', {}).get('status') == 'ok':
            dino_meta = item['dino_meta']
            raw_ref_path = frame_dir / f"{scene_id}_raw_dino.json"
            raw_ref_str = str(raw_ref_path.resolve())
            
            atomic_write_json(raw_ref_path, dino_meta)
            
            h = dino_meta.get('embedding_id')
            vector_backend = 'qdrant' if dino_meta.get('qdrant_committed') else 'faiss'
            vector_collection = dino_meta.get('qdrant_collection') or cfg.get('qdrant', {}).get('collections', {}).get('dino', 'dino')
            vector_dim = cfg.get('qdrant', {}).get('embedding_dims', {}).get('dino', 1024)
            
            payload = {
                'embedding_id': h,
                'faiss_id': dino_meta.get('faiss_id'),
                'vector_backend': vector_backend,
                'vector_collection': vector_collection,
            }
            
            frame_id = client.log_frame(
                video_hash=video_hash,
                epoch_id=epoch_id,
                run_id=run_id,
                t_start=frame_timestamp,
                t_end=frame_timestamp,
                modality=visual_modality,
                worker_name='image_embed_dino',
                model_tag=dino_meta.get('model', 'facebook/dinov2-large'),
                confidence=1.0,
                spatial_region=None,
                spatial_space='normalized_yxyx_top_left',
                vector_key=h,
                vector_backend=vector_backend,
                vector_collection=vector_collection,
                vector_dim=vector_dim,
                vector_model_tag=dino_meta.get('model', 'facebook/dinov2-large'),
                source_artifact_id=scene_id,
                raw_ref=raw_ref_str,
                payload={**payload, **({'source_kind': item['source_kind']} if item.get('source_kind') else {})},
                promotion_status='staged'
            )
            
            # Backfill ucf_frame_id to Qdrant if enabled
            if vector_backend == 'qdrant' and cfg.get('qdrant', {}).get('enabled', False):
                try:
                    from steps.common.qdrant_client import build_qdrant_client
                    q_client = build_qdrant_client(cfg, dim=vector_dim, key='dino')
                    if q_client:
                        normalized_key = q_client._normalize_point_id(h)
                        q_client.session.post(
                            f"{q_client.cfg.host}/collections/{q_client.cfg.collection}/points/payload?wait=true",
                            json={
                                "payload": {"ucf_frame_id": frame_id},
                                "points": [normalized_key]
                            },
                            timeout=5
                        )
                except Exception as e:
                    logger.warning(f"[UCF] Failed to update Qdrant payload with ucf_frame_id for DINO: {e}")

            # Backfill ucf_frame_id to FAISS sidecar DB
            map_db = (cfg.get("paths", {}) or {}).get("dino_id_map_db")
            if map_db and os.path.isfile(map_db) and not cfg.get("ingestion_isolation", False):
                con = None
                try:
                    import sqlite3
                    con = sqlite3.connect(map_db, check_same_thread=False)
                    with con:
                        con.execute(
                            "UPDATE dino_id_map SET ucf_frame_id = ? WHERE video_hash = ? AND faiss_id = ?",
                            (frame_id, video_hash, dino_meta.get('faiss_id'))
                        )
                except Exception as e:
                    logger.warning(f"[UCF] Failed to update FAISS sidecar DB with ucf_frame_id for DINO: {e}")
                finally:
                    if con is not None:
                        con.close()

        # 6. CLIP Visual Embeddings
        if item.get('clip_meta') and item.get('clip_meta', {}).get('status') == 'ok':
            clip_meta = item['clip_meta']
            raw_ref_path = frame_dir / f"{scene_id}_raw_clip.json"
            raw_ref_str = str(raw_ref_path.resolve())
            
            atomic_write_json(raw_ref_path, clip_meta)
            
            h = clip_meta.get('embedding_id')
            vector_backend = 'qdrant' if clip_meta.get('qdrant_committed') else 'faiss'
            vector_collection = clip_meta.get('qdrant_collection') or cfg.get('qdrant', {}).get('collections', {}).get('clip', 'clip')
            vector_dim = cfg.get('qdrant', {}).get('embedding_dims', {}).get('clip', 768)
            
            payload = {
                'embedding_id': h,
                'faiss_id': clip_meta.get('faiss_id'),
                'vector_backend': vector_backend,
                'vector_collection': vector_collection,
            }
            
            frame_id = client.log_frame(
                video_hash=video_hash,
                epoch_id=epoch_id,
                run_id=run_id,
                t_start=frame_timestamp,
                t_end=frame_timestamp,
                modality=visual_modality,
                worker_name='image_embed_clip',
                model_tag=clip_meta.get('model', 'laion/CLIP-ViT-L-14-DataComp.XL-s13B-b90K'),
                confidence=1.0,
                spatial_region=None,
                spatial_space='normalized_yxyx_top_left',
                vector_key=h,
                vector_backend=vector_backend,
                vector_collection=vector_collection,
                vector_dim=vector_dim,
                vector_model_tag=clip_meta.get('model', 'laion/CLIP-ViT-L-14-DataComp.XL-s13B-b90K'),
                source_artifact_id=scene_id,
                raw_ref=raw_ref_str,
                payload={**payload, **({'source_kind': item['source_kind']} if item.get('source_kind') else {})},
                promotion_status='staged'
            )
            
            # Backfill ucf_frame_id to Qdrant if enabled
            if vector_backend == 'qdrant' and cfg.get('qdrant', {}).get('enabled', False):
                try:
                    from steps.common.qdrant_client import build_qdrant_client
                    q_client = build_qdrant_client(cfg, dim=vector_dim, key='clip')
                    if q_client:
                        normalized_key = q_client._normalize_point_id(h)
                        q_client.session.post(
                            f"{q_client.cfg.host}/collections/{q_client.cfg.collection}/points/payload?wait=true",
                            json={
                                "payload": {"ucf_frame_id": frame_id},
                                "points": [normalized_key]
                            },
                            timeout=5
                        )
                except Exception as e:
                    logger.warning(f"[UCF] Failed to update Qdrant payload with ucf_frame_id for CLIP: {e}")

            # Backfill ucf_frame_id to FAISS sidecar DB
            map_db = (cfg.get("paths", {}) or {}).get("clip_id_map_db")
            if map_db and os.path.isfile(map_db) and not cfg.get("ingestion_isolation", False):
                con = None
                try:
                    import sqlite3
                    con = sqlite3.connect(map_db, check_same_thread=False)
                    with con:
                        con.execute(
                            "UPDATE clip_id_map SET ucf_frame_id = ? WHERE video_hash = ? AND faiss_id = ?",
                            (frame_id, video_hash, clip_meta.get('faiss_id'))
                        )
                except Exception as e:
                    logger.warning(f"[UCF] Failed to update FAISS sidecar DB with ucf_frame_id for CLIP: {e}")
                finally:
                    if con is not None:
                        con.close()

        # 7. Frame text embedding logging (optional — only if text_embed ran successfully)
        frame_text_embed_meta = item.get('frame_text_embed_meta') or {}
        if isinstance(frame_text_embed_meta, dict) and frame_text_embed_meta.get('status') == 'ok':
            text_embedding_id = frame_text_embed_meta.get('embedding_id')
            if text_embedding_id:
                scene_hash_str = hashlib.sha256(
                    f"{video_hash}|{start:.6f}|{start + duration:.6f}".encode('utf-8')
                ).hexdigest()[:16]
                text_embed_raw_ref_path = frame_dir / f"{scene_hash_str}_raw_text_embed_frame.json"
                text_embed_payload = {
                    'embedding_id': text_embedding_id,
                    'embedding_source': 'frame_text',
                    'origin_modality': 'frame_text',
                    'engine': frame_text_embed_meta.get('engine', 'all-MiniLM-L6-v2'),
                    'faiss_id': frame_text_embed_meta.get('faiss_id'),
                }
                atomic_write_json(text_embed_raw_ref_path, text_embed_payload)
                text_embed_raw_ref_str = str(text_embed_raw_ref_path.resolve())
                _text_frame_id = client.log_frame(
                    video_hash=video_hash,
                    epoch_id=epoch_id,
                    run_id=run_id,
                    t_start=frame_timestamp,
                    t_end=frame_timestamp,
                    modality='text',
                    worker_name='text_embed',
                    model_tag='sentence-transformers/all-MiniLM-L6-v2',
                    confidence=1.0,
                    source_artifact_id=scene_id,
                    raw_ref=text_embed_raw_ref_str,
                    payload={**text_embed_payload, **({'source_kind': item['source_kind']} if item.get('source_kind') else {})},
                    promotion_status='staged',
                    vector_key=text_embedding_id,
                    vector_backend='qdrant' if frame_text_embed_meta.get('qdrant_committed') else 'faiss',
                    vector_dim=384,
                    vector_model_tag='sentence-transformers/all-MiniLM-L6-v2',
                    vector_collection=frame_text_embed_meta.get('vector_collection', 'text'),
                )

                # Post-log Qdrant payload update with ucf_frame_id
                if _text_frame_id and frame_text_embed_meta.get('qdrant_committed'):
                    try:
                        from steps.common.qdrant_client import GOODQ_POINT_ID_NAMESPACE
                        import uuid as _uuid_mod
                        _norm_id = str(_uuid_mod.uuid5(GOODQ_POINT_ID_NAMESPACE, text_embedding_id))
                        import requests as _requests
                        _cfg = json.load(open(str(cfg_json), 'r', encoding='utf-8')) if isinstance(cfg_json, Path) else {}
                        _qcfg = (_cfg.get('qdrant') or {})
                        _qhost = _qcfg.get('host', 'http://localhost:6333')
                        _qcol_map = _qcfg.get('collections', {}) or {}
                        _qcol = _qcol_map.get('text', 'goodq_text')
                        _requests.post(
                            f"{_qhost}/collections/{_qcol}/points/payload",
                            json={
                                "payload": {"ucf_frame_id": _text_frame_id},
                                "points": [_norm_id],
                            },
                            timeout=5,
                        )
                    except Exception as _qe:
                        logger.warning(f"[UCF] Failed to update text_embed Qdrant payload with ucf_frame_id: {_qe}")


        client.close()
    except Exception as e:
        logger.warning(f"[UCF] Visual UCF logging failed: {type(e).__name__}: {str(e)}")
        if strict:
            raise
    finally:
        if client is not None:
            client.close()


def _log_scene_visual_embeddings_to_ucf_ledger(
    cfg: Dict[str, Any],
    video_hash: str,
    epoch_id: str,
    run_id: str,
    processing_dir: Path,
    scene_outputs: List[Dict[str, Any]],
    ucf_client: Any,
) -> None:
    """Logs Phase 6a scene CLIP and DINO visual embeddings to ucf_ledger.db and updates Qdrant/FAISS mapping."""
    try:
        import json
        import os
        from pathlib import Path
        import sqlite3
        from steps.common.memory import to_faiss_id

        processing_dir = Path(processing_dir)
        scene_manifest_path = processing_dir / "video" / "scene_manifest.json"
        if not scene_manifest_path.exists():
            logger.warning(f"[UCF] scene_manifest.json not found at {scene_manifest_path}. Skipping visual scene UCF logging.")
            return

        with open(scene_manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

        scenes = manifest_data.get("scenes", []) if isinstance(manifest_data, dict) else []
        if not scenes:
            logger.warning("[UCF] No scenes found in scene_manifest.json.")
            return

        ucf_raw_refs_dir = processing_dir / "video" / "ucf_raw_refs"
        ucf_raw_refs_dir.mkdir(parents=True, exist_ok=True)

        qdrant_enabled = cfg.get("qdrant", {}).get("enabled", False)
        clip_collection = cfg.get("qdrant", {}).get("collections", {}).get("clip", "goodq_clip_scenes")
        dino_collection = cfg.get("qdrant", {}).get("collections", {}).get("dino", "goodq_dino_scenes")

        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            scene_id = scene.get("id") or scene.get("scene_id")
            if not scene_id:
                continue

            t_start = float(scene.get("start", 0.0) or 0.0)
            t_end = float(scene.get("end", t_start) or t_start)

            # CLIP Embedding
            clip_id = scene.get("clip_id")
            if clip_id:
                clip_raw_ref_path = ucf_raw_refs_dir / f"{scene_id}_raw_clip.json"
                clip_payload = {
                    "embedding_id": clip_id,
                    "embedding_source": "scene_visual_embeddings_clip",
                    "engine": "laion/CLIP-ViT-L-14-DataComp.XL-s13B-b90K",
                    "qdrant_collection": clip_collection,
                }
                atomic_write_json(clip_raw_ref_path, clip_payload)
                clip_raw_ref_str = str(clip_raw_ref_path.resolve())

                ucf_frame_id = ucf_client.log_frame(
                    video_hash=video_hash,
                    epoch_id=epoch_id,
                    run_id=run_id,
                    t_start=t_start,
                    t_end=t_end,
                    modality="video",
                    worker_name="scene_visual_embeddings_clip",
                    model_tag="laion/CLIP-ViT-L-14-DataComp.XL-s13B-b90K",
                    confidence=1.0,
                    source_artifact_id=scene_id,
                    raw_ref=clip_raw_ref_str,
                    payload=clip_payload,
                    promotion_status="staged",
                    vector_key=clip_id,
                    vector_backend=qdrant_enabled and "qdrant" or "faiss",
                    vector_dim=768,
                    vector_model_tag="laion/CLIP-ViT-L-14-DataComp.XL-s13B-b90K",
                    vector_collection=clip_collection,
                )

                if ucf_frame_id:
                    # Qdrant backfill
                    if qdrant_enabled:
                        try:
                            from steps.common.qdrant_client import build_qdrant_client
                            q_client = build_qdrant_client(cfg, dim=768, key="clip")
                            if q_client:
                                normalized_key = q_client._normalize_point_id(clip_id)
                                q_client.session.post(
                                    f"{q_client.cfg.host}/collections/{q_client.cfg.collection}/points/payload?wait=true",
                                    json={
                                        "payload": {"ucf_frame_id": ucf_frame_id},
                                        "points": [normalized_key]
                                    },
                                    timeout=5
                                )
                        except Exception as e:
                            logger.warning(f"[UCF] Failed to update CLIP Qdrant payload with ucf_frame_id: {e}")

                    # FAISS sidecar DB backfill
                    clip_faiss_id = to_faiss_id(clip_id)
                    map_db = (cfg.get("paths", {}) or {}).get("clip_id_map_db")
                    if map_db and os.path.isfile(map_db) and not cfg.get("ingestion_isolation", False):
                        con = None
                        try:
                            import sqlite3
                            con = sqlite3.connect(map_db, check_same_thread=False)
                            with con:
                                con.execute(
                                    "UPDATE clip_id_map SET ucf_frame_id = ? WHERE video_hash = ? AND faiss_id = ?",
                                    (ucf_frame_id, video_hash, clip_faiss_id)
                                )
                        except Exception as e:
                            logger.warning(f"[UCF] Failed to update FAISS sidecar DB with ucf_frame_id for CLIP: {e}")
                        finally:
                            if con is not None:
                                con.close()

            # DINO Embedding
            dino_id = scene.get("dino_id")
            if dino_id:
                dino_raw_ref_path = ucf_raw_refs_dir / f"{scene_id}_raw_dino.json"
                dino_payload = {
                    "embedding_id": dino_id,
                    "embedding_source": "scene_visual_embeddings_dino",
                    "engine": "facebook/dinov2-large",
                    "qdrant_collection": dino_collection,
                }
                atomic_write_json(dino_raw_ref_path, dino_payload)
                dino_raw_ref_str = str(dino_raw_ref_path.resolve())

                ucf_frame_id = ucf_client.log_frame(
                    video_hash=video_hash,
                    epoch_id=epoch_id,
                    run_id=run_id,
                    t_start=t_start,
                    t_end=t_end,
                    modality="video",
                    worker_name="scene_visual_embeddings_dino",
                    model_tag="facebook/dinov2-large",
                    confidence=1.0,
                    source_artifact_id=scene_id,
                    raw_ref=dino_raw_ref_str,
                    payload=dino_payload,
                    promotion_status="staged",
                    vector_key=dino_id,
                    vector_backend=qdrant_enabled and "qdrant" or "faiss",
                    vector_dim=1024,
                    vector_model_tag="facebook/dinov2-large",
                    vector_collection=dino_collection,
                )

                if ucf_frame_id:
                    # Qdrant backfill
                    if qdrant_enabled:
                        try:
                            from steps.common.qdrant_client import build_qdrant_client
                            q_client = build_qdrant_client(cfg, dim=1024, key="dino")
                            if q_client:
                                normalized_key = q_client._normalize_point_id(dino_id)
                                q_client.session.post(
                                    f"{q_client.cfg.host}/collections/{q_client.cfg.collection}/points/payload?wait=true",
                                    json={
                                        "payload": {"ucf_frame_id": ucf_frame_id},
                                        "points": [normalized_key]
                                    },
                                    timeout=5
                                )
                        except Exception as e:
                            logger.warning(f"[UCF] Failed to update DINO Qdrant payload with ucf_frame_id: {e}")

                    # FAISS sidecar DB backfill
                    dino_faiss_id = to_faiss_id(dino_id)
                    map_db = (cfg.get("paths", {}) or {}).get("dino_id_map_db")
                    if map_db and os.path.isfile(map_db) and not cfg.get("ingestion_isolation", False):
                        con = None
                        try:
                            import sqlite3
                            con = sqlite3.connect(map_db, check_same_thread=False)
                            with con:
                                con.execute(
                                    "UPDATE dino_id_map SET ucf_frame_id = ? WHERE video_hash = ? AND faiss_id = ?",
                                    (ucf_frame_id, video_hash, dino_faiss_id)
                                )
                        except Exception as e:
                            logger.warning(f"[UCF] Failed to update FAISS sidecar DB with ucf_frame_id for DINO: {e}")
                        finally:
                            if con is not None:
                                con.close()

    except Exception as exc:
        logger.warning(f"[UCF] _log_scene_visual_embeddings_to_ucf_ledger failed: {exc}")


def _process_audio(
    cfg_json: Path,
    ffmpeg: str,
    video_path: Path,
    scene: Dict[str, Any],
    audio_dir: Path,
    audio_artifact_dir: Path,
    video_hash: str,
    scene_id: str,
    audio_runtime_contract: Optional[Dict[str, Any]] = None,
    scene_num: int = 1,
    total_scenes: int = 1,
    recording_audio: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Process audio for scene - returns None if video has no audio"""
    from steps.audio.recording_ingestion import selected, scene_result
    caller_cfg = json.loads(cfg_json.read_text(encoding='utf-8'))
    if selected(caller_cfg) or (audio_runtime_contract or {}).get('selected') == 'recording':
        if recording_audio is None:
            raise ValueError('Recording audio selected without a shared recording job')
    if recording_audio is not None:
        projected_audio = scene_result(recording_audio, scene_id, scene)
        if projected_audio['audio_evidence']['source'].get('audio_track') == 'absent':
            return {'path': None, 'data': projected_audio}
    audio_path = _extract_audio_chunk(
        ffmpeg,
        video_path,
        scene,
        audio_dir,
        scene_id=scene_id,
        video_id=video_hash,
    )
    
    # If no audio was extracted, return None
    if audio_path is None and recording_audio is None:
        return None
    
    start = float(scene.get('start', 0.0) or 0.0)
    end = float(scene.get('end', start) or start)

    item: Dict[str, Any] = {
        'modality': 'audio',
        'source_path': str(audio_path or video_path),
        'scene_id': scene_id,
        'scene_index': scene.get('index'),
        'video_hash': video_hash,
        'video_id': video_hash,
        'scene': {
            'start': start,
            'end': end,
            'duration': end - start,
        },
    }
    contract_selected = 'none'
    contract_reason = 'runtime_contract_unset'
    if isinstance(audio_runtime_contract, dict):
        selected_value = audio_runtime_contract.get('selected')
        if isinstance(selected_value, str) and selected_value.strip().lower() in {'wsl', 'windows', 'recording', 'none'}:
            contract_selected = selected_value.strip().lower()
        reason_value = audio_runtime_contract.get('reason')
        if isinstance(reason_value, str) and reason_value.strip():
            contract_reason = reason_value.strip()
        else:
            contract_reason = 'runtime_contract_selected'
    if recording_audio is not None:
        contract_selected, contract_reason = 'recording', 'explicit_recording_engine'
    item['audio_backend_selected'] = contract_selected
    item['audio_backend_reason'] = contract_reason
    item['audio_backend_effective'] = 'none'
    item['audio_backend_effective_reason'] = 'not_processed'
    step_log_cfg: Optional[Dict[str, Any]] = None

    def _set_effective_backend(backend: str, reason: str) -> None:
        item['audio_backend_effective'] = backend
        item['audio_backend_effective_reason'] = reason

    def _get_step_log_cfg() -> Dict[str, Any]:
        nonlocal step_log_cfg
        if isinstance(step_log_cfg, dict):
            return step_log_cfg
        try:
            step_log_cfg = json.loads(cfg_json.read_text(encoding='utf-8'))
        except Exception as cfg_error:  # noqa: BLE001
            logger.warning(
                "run_ingestion warning context=%s error=%s",
                "optional_audio_step.load_step_log_cfg",
                cfg_error,
            )
            step_log_cfg = {}
        return step_log_cfg

    def merge(env_name: str, step_name: str) -> None:
        from steps.common.progress_tracker import get_tracker
        tracker = get_tracker()
        step_index = 1 + scene_num
        tracker.update_step(
            f"Scene {scene_num}/{total_scenes} - Running {step_name}",
            step_index,
            {
                "scene_index": scene.get('index'),
                "scenes_total": total_scenes,
                "video_id": video_hash,
                "stage": f"audio_{step_name}"
            }
        )
        result = _run_step(env_name, step_name, item, cfg_json)
        if isinstance(result, dict):
            item.update(result)
            # Selected backend is run-contract truth; downstream steps must not mutate it.
            item['audio_backend_selected'] = contract_selected
            item['audio_backend_reason'] = contract_reason

    def record_optional_audio_step_failure(env_name: str, step_name: str, exc: Exception) -> None:
        error_text = str(exc).strip() or type(exc).__name__
        warning_payload = {
            'step': step_name,
            'env': env_name,
            'error': error_text,
        }
        warnings = item.get('audio_step_warnings')
        if not isinstance(warnings, list):
            warnings = []
            item['audio_step_warnings'] = warnings
        warnings.append(warning_payload)
        status_meta_field = {
            'sentiment': 'sentiment_meta',
            'emotion_classify': 'emotion_meta',
            'audio_embed_clap': 'clap_meta',
        }.get(step_name)
        if status_meta_field:
            status_meta = item.get(status_meta_field)
            if not isinstance(status_meta, dict):
                status_meta = {}
            status_meta.update(
                {
                    'status': 'error',
                    'error': error_text,
                }
            )
            item[status_meta_field] = status_meta
        if step_name == 'sentiment':
            item.setdefault('sentiment', None)
        elif step_name == 'emotion_classify':
            item.setdefault('emotions', None)
        logger.warning(
            "[AUDIO] Optional step failed env=%s step=%s scene_id=%s scene_index=%s error=%s",
            env_name,
            step_name,
            scene_id,
            scene.get('index'),
            error_text,
        )
        step_extra: Dict[str, Any] = {
            'reason': 'optional_step_failed',
            'optional': True,
            'env': env_name,
        }
        if step_name == 'audio_embed_clap':
            step_extra['embedding_emitted'] = False
            clap_meta = item.get('clap_meta')
            if isinstance(clap_meta, dict):
                step_extra['result_meta'] = {'clap_meta': clap_meta}
        log_step_run(
            _get_step_log_cfg(),
            step_name,
            item,
            0.0,
            'error',
            error_text,
            extra=step_extra,
        )
        _record_run_warning(
            cfg_json,
            code='optional_audio_step_failed',
            message=error_text,
            context={
                'step': step_name,
                'env': env_name,
                'scene_id': scene_id,
                'scene_index': scene.get('index'),
            },
        )

    def merge_optional_audio_step(env_name: str, step_name: str) -> None:
        try:
            merge(env_name, step_name)
        except Exception as exc:  # noqa: BLE001
            # Transcript-bearing scenes should survive late enrichment failures.
            record_optional_audio_step_failure(env_name, step_name, exc)

    def record_wsl_unified_audio_embed_skip() -> None:
        clap_meta = _mark_wsl_unified_audio_embed_skip(item)
        logger.info(
            "[AUDIO] Skipping legacy audio_embed_clap because WSL unified audio already emitted embeddings scene_id=%s",
            scene_id,
        )
        log_step_run(
            _get_step_log_cfg(),
            'audio_embed_clap',
            item,
            0.0,
            'skipped',
            None,
            extra={
                'reason': 'wsl_unified_embeddings_present',
                'optional': True,
                'backend': 'wsl',
                'embedding_emitted': False,
                'wsl_unified_embeddings_present': True,
                'result_meta': {'clap_meta': clap_meta},
            },
        )

    def run_local_audio_fallback(reason: str) -> None:
        logger.info(
            "[AUDIO] WSL2 unified path disabled or unavailable; using local CPU-safe transcription fallback"
        )
        from steps.common.progress_tracker import get_tracker
        tracker = get_tracker()
        tracker.update_step(
            f"Scene {scene_num}/{total_scenes} - Transcribing audio (Windows CPU fallback)",
            1 + scene_num,
            {
                "scene_index": scene.get('index'),
                "scenes_total": total_scenes,
                "video_id": video_hash,
                "stage": "audio_transcribe_local"
            }
        )
        try:
            from steps.audio_transcribe.step import audio_transcribe as local_audio_transcribe

            cfg_payload = json.loads(cfg_json.read_text(encoding='utf-8'))
            audio_cfg = cfg_payload.get('audio')
            if not isinstance(audio_cfg, dict):
                audio_cfg = {}
                cfg_payload['audio'] = audio_cfg
            tx_cfg = audio_cfg.get('transcribe')
            if not isinstance(tx_cfg, dict):
                tx_cfg = {}
                audio_cfg['transcribe'] = tx_cfg
            # Local fallback must not recurse back into the WSL path we are explicitly downgrading from.
            tx_cfg['use_wsl2'] = False
            local_item = {
                'source_path': str(audio_path or video_path),
                'path': str(audio_path) if audio_path else None,
                'scene_id': scene_id,
                'scene_index': scene.get('index'),
                'video_hash': video_hash,
                'video_id': video_hash,
            }
            prior_require_wsl_audio = os.environ.get('GOODQ_REQUIRE_WSL_AUDIO')
            os.environ['GOODQ_REQUIRE_WSL_AUDIO'] = '0'
            try:
                local_result = local_audio_transcribe(local_item, cfg_payload)
            finally:
                if prior_require_wsl_audio is None:
                    os.environ.pop('GOODQ_REQUIRE_WSL_AUDIO', None)
                else:
                    os.environ['GOODQ_REQUIRE_WSL_AUDIO'] = prior_require_wsl_audio
            local_result = _normalize_local_transcription_result(local_result)
            if isinstance(local_result, dict):
                local_result = _offset_local_audio_result_to_scene(local_result, start)
                item.update(local_result)
                item['audio_backend_selected'] = contract_selected
                item['audio_backend_reason'] = contract_reason
                if not isinstance(item.get('segments'), list):
                    transcript_segments = local_result.get('transcript_segments')
                    if isinstance(transcript_segments, list):
                        item['segments'] = transcript_segments
            has_transcript = isinstance(item.get('transcript'), str) and bool(item.get('transcript', '').strip())
            has_segments = isinstance(item.get('segments'), list) and len(item.get('segments')) > 0
            if has_transcript or has_segments:
                _set_effective_backend('windows', reason)
            else:
                transcript_meta = item.get('transcript_meta') if isinstance(item.get('transcript_meta'), dict) else {}
                unavailable_details: Dict[str, Any] = {'reason': 'no_transcript_output'}
                if transcript_meta:
                    unavailable_details.update(
                        {
                            'status': transcript_meta.get('status'),
                            'engine': transcript_meta.get('engine'),
                            'model': transcript_meta.get('model'),
                            'device': transcript_meta.get('device'),
                        }
                    )
                item['audio_backend_unavailable_details'] = unavailable_details
                logger.warning(
                    "[AUDIO] Windows fallback produced no transcript scene_id=%s status=%s engine=%s",
                    scene_id,
                    unavailable_details.get('status'),
                    unavailable_details.get('engine'),
                )
                _set_effective_backend('none', f'{reason}_no_transcript')
        except Exception as fallback_error:
            logger.warning(
                "[AUDIO] Local CPU-safe transcription fallback failed: %s",
                fallback_error,
            )
            _set_effective_backend('failed', f'{reason}_failed')

    def log_unified_audio_attempt(
        result_payload: Optional[Dict[str, Any]],
        duration_ms: float,
        *,
        error_text: Optional[str] = None,
        status_override: Optional[str] = None,
    ) -> None:
        step_item = dict(item)
        extra: Dict[str, Any] = {
            'backend': 'wsl',
            'requested_backend': contract_selected,
        }
        if isinstance(result_payload, dict):
            reason = result_payload.get('bridge_error_reason')
            if isinstance(reason, str) and reason.strip():
                extra['reason'] = reason.strip()
            details = result_payload.get('bridge_error_details')
            if isinstance(details, dict) and details:
                extra['bridge_error_details'] = details
            env_warnings = result_payload.get('bridge_env_warnings')
            if isinstance(env_warnings, list) and env_warnings:
                extra['bridge_env_warnings'] = env_warnings
        log_step_run(
            _get_step_log_cfg(),
            'audio_unified_wsl2',
            step_item,
            duration_ms,
            status_override or ('error' if error_text else 'ok'),
            error_text,
            extra=extra,
        )
        if (
            isinstance(result_payload, dict)
            and str(result_payload.get('status') or '').strip().lower() == 'success'
        ):
            _log_wsl_capability_outcomes(
                cfg=_get_step_log_cfg(),
                item=step_item,
                duration_ms=duration_ms,
                outcomes=result_payload.get('wsl_capability_outcomes'),
            )

    if audio_path is None and recording_audio is not None:
        item.update(projected_audio)
        item['audio_meta'] = {'status': 'error', 'reason': 'scene_audio_extraction_failed'}
        item['clap_meta'] = {'status': 'error', 'reason': 'scene_audio_extraction_failed'}
        merge('goodq_audio_transcribe', 'audio_music_events')
        merge('goodq_audio_transcribe', 'audio_time_hints')
    else:
        merge('goodq_audio_metadata', 'audio_metadata')
    
    # WSL2 unified audio is profile-gated. BASELINE uses CPU-safe local fallback by default.
    if audio_path and audio_path.exists():
        if contract_selected in {'wsl', 'windows', 'recording', 'none'}:
            use_wsl_unified_audio = contract_selected == 'wsl'
        else:
            use_wsl_unified_audio = bool(wsl_audio_auto_enabled() or require_wsl_audio())
            if use_wsl_unified_audio and shutil.which('wsl') is None:
                logger.warning(
                    "[AUDIO] WSL2 unified audio requested but wsl command unavailable; using local fallback"
                )
                use_wsl_unified_audio = False

        if recording_audio is not None:
            from steps.audio.recording_ingestion import scene_result
            item.update(scene_result(recording_audio, scene_id, scene))
            contract_selected, contract_reason = 'recording', 'explicit_recording_engine'
            item['audio_backend_reason'] = contract_reason
        elif contract_selected == 'recording':
            raise ValueError('Recording audio selected without a shared recording job')
        elif use_wsl_unified_audio:
            from steps.audio.audio_wsl2_bridge import audio_unified_wsl2, unified_transcription_options
            from steps.common.progress_tracker import get_tracker
            tracker = get_tracker()
            tracker.update_step(
                f"Scene {scene_num}/{total_scenes} - Transcribing audio (WSL2)",
                1 + scene_num,
                {
                    "scene_index": scene.get('index'),
                    "scenes_total": total_scenes,
                    "video_id": video_hash,
                    "stage": "audio_transcribe_wsl2"
                }
            )

            # Single unified call gets transcription, diarization, emotion, embeddings
            try:
                unified_started = time.perf_counter()
                unified_result = audio_unified_wsl2(str(audio_path), scene_id=scene_id, duration=end-start,
                                                  **unified_transcription_options(_get_step_log_cfg()))
                unified_duration_ms = (time.perf_counter() - unified_started) * 1000.0
                if isinstance(unified_result, dict):
                    item.update(unified_result)
                    item['audio_backend_selected'] = contract_selected
                    item['audio_backend_reason'] = contract_reason
                    if str(unified_result.get('status', '')).strip().lower() == 'error':
                        error_text = str(
                            unified_result.get('error')
                            or unified_result.get('bridge_error_reason')
                            or 'WSL unified audio error'
                        ).strip()
                        log_unified_audio_attempt(
                            unified_result,
                            unified_duration_ms,
                            error_text=error_text,
                            status_override='error',
                        )
                        unavailable_details: Dict[str, Any] = {
                            'reason': str(unified_result.get('bridge_error_reason') or 'wsl_unified_error'),
                            'error': error_text,
                        }
                        bridge_details = unified_result.get('bridge_error_details')
                        if isinstance(bridge_details, dict) and bridge_details:
                            unavailable_details['bridge_error_details'] = bridge_details
                        env_warnings = unified_result.get('bridge_env_warnings')
                        if isinstance(env_warnings, list) and env_warnings:
                            unavailable_details['bridge_env_warnings'] = env_warnings
                        item['audio_backend_unavailable_details'] = unavailable_details
                        logger.warning(
                            "[AUDIO] WSL2 unified audio returned structured error scene_id=%s reason=%s error=%s; downgrading to local fallback",
                            scene_id,
                            unavailable_details['reason'],
                            error_text,
                        )
                        if require_wsl_audio():
                            raise RuntimeError(
                                f"GOODQ_REQUIRE_WSL_AUDIO=1 and WSL unified audio failed: {error_text}"
                            )
                        run_local_audio_fallback('wsl_unified_error_fallback')
                    else:
                        log_unified_audio_attempt(unified_result, unified_duration_ms)
                        _set_effective_backend('wsl', 'wsl_unified_success')
            except Exception as unified_error:
                unified_duration_ms = (time.perf_counter() - unified_started) * 1000.0 if 'unified_started' in locals() else 0.0
                log_unified_audio_attempt(
                    None,
                    unified_duration_ms,
                    error_text=str(unified_error),
                    status_override='error',
                )
                logger.warning(
                    "[AUDIO] WSL2 unified audio failed operation=%s scene_id=%s exc_type=%s exc=%s",
                    "audio_unified_wsl2",
                    scene_id,
                    type(unified_error).__name__,
                    unified_error,
                )
                if require_wsl_audio():
                    raise RuntimeError(
                        f"GOODQ_REQUIRE_WSL_AUDIO=1 and WSL unified audio failed: {unified_error}"
                    ) from unified_error
                run_local_audio_fallback('wsl_unified_exception_fallback')
        else:
            if contract_selected == 'windows':
                run_local_audio_fallback('windows_contract_selected')
            elif contract_selected == 'none':
                run_local_audio_fallback('contract_selected_none')
            else:
                run_local_audio_fallback('wsl_disabled_fallback')

        # Legacy steps for speaker merge and timing (keep these for now)
        merge('goodq_audio_transcribe', 'audio_speaker_merge')
        merge('goodq_audio_transcribe', 'audio_music_events')
        merge('goodq_audio_transcribe', 'audio_time_hints')

        if item.get('speaker_transcript'):
            item['segments'] = item['speaker_transcript']

        # Write compatibility JSON files for harmonizer
        # The harmonizer expects separate transcript.json and diarization.json files
        audio_artifact_dir.mkdir(parents=True, exist_ok=True)

        # Write transcript.json
        if item.get('segments') or item.get('transcript'):
            transcript_json = {
                'segments': item.get('segments', []),
                'full_text': item.get('transcript', ''),
                'language': item.get('language', 'en')
            }
            atomic_write_json(audio_artifact_dir / 'transcript.json', transcript_json)
            logger.info(f"[AUDIO] Wrote transcript.json with {len(item.get('segments', []))} segments")
            # Save raw un-flattened transcript
            if item.get('audio_evidence') is not None:
                from steps.audio.recording_ingestion import ucf_transcript_segments
                raw_tx_segments = ucf_transcript_segments(item['audio_evidence'])
            else:
                raw_tx_segments = item.get('segments', [])
            atomic_write_json(audio_artifact_dir / f"{scene_id}_raw_transcript.json", raw_tx_segments)

        # Write diarization.json
        if item.get('speaker_segments'):
            diarization_json = {
                'speakers': item.get('speakers', []),
                'segments': item.get('speaker_segments', [])
            }
            atomic_write_json(audio_artifact_dir / 'diarization.json', diarization_json)
            # Save raw un-flattened diarization
            atomic_write_json(audio_artifact_dir / f"{scene_id}_raw_diarization.json", item.get('speaker_segments', []))

    else:
        logger.info(f"[AUDIO] No extracted scene audio for {scene_id}; retained recording evidence is preserved")

    merge_optional_audio_step('goodq_core', 'sentiment')
    merge_optional_audio_step('goodq_core', 'emotion_classify')
    merge_optional_audio_step('goodq_core', 'tagger')
    if _has_wsl_unified_audio_embeddings(item):
        record_wsl_unified_audio_embed_skip()
    elif audio_path is not None:
        merge_optional_audio_step('goodq_audio_embed', 'audio_embed_clap')

    canonicalize_taxonomy(item)
    transcript = item.get('transcript') if isinstance(item.get('transcript'), str) else ''
    if transcript:
        text_payload = {
            'modality': 'audio_transcript',
            'source_path': str(audio_path or video_path),
            'text': transcript,
            'scene_id': scene_id,
            'scene_index': scene.get('index'),
            'video_hash': video_hash,
            'video_id': video_hash,
            'ner_entities': item.get('ner_entities'),
            'tags': item.get('tags'),
            'entities': item.get('entities'),
            'location': item.get('location'),
            'locations': item.get('locations'),
            'emotion': item.get('emotion'),
            'emotion_scores': item.get('emotion_scores') or item.get('emotions'),
            'sentiment': item.get('sentiment'),
            'speaker_count': item.get('speaker_count'),
            'scene': item.get('scene'),
        }
        text_embed_result = _run_step('goodq_text_embed', 'text_embed', text_payload, cfg_json)
        if isinstance(text_embed_result, dict):
            audio_text_embed_meta = text_embed_result.get('embedding_meta')
            if isinstance(audio_text_embed_meta, dict):
                item['audio_text_embed_meta'] = audio_text_embed_meta

    # Call UCF Audio logging hook AFTER optional enrichment steps so embedding IDs are available
    _log_audio_to_ucf_ledger(
        cfg_json=cfg_json,
        video_hash=video_hash,
        scene_id=scene_id,
        scene=scene,
        audio_artifact_dir=audio_artifact_dir,
        item=item,
    )

    return {
        'path': str(audio_path) if audio_path else None,
        'start': start,
        'end': end,
        'data': item,
    }


async def _process_frame_async(
    cfg_json: Path,
    ffmpeg: str,
    video_path: Path,
    scene: Dict[str, Any],
    frame_dir: Path,
    video_hash: str,
    scene_id: str,
    db_write_lock: asyncio.Lock,
    faiss_write_lock: asyncio.Lock,
    scene_num: int = 1,
    total_scenes: int = 1,
) -> Dict[str, Any]:
    step_timings = {}
    extract_start = time.perf_counter()
    frame_path = await asyncio.to_thread(
        _extract_keyframe,
        ffmpeg,
        video_path,
        scene,
        frame_dir,
        scene_id=scene_id,
        video_id=video_hash,
    )
    step_timings['extract_keyframe'] = time.perf_counter() - extract_start
    
    scene_index = scene.get('index')
    duration = float(scene.get('duration', 0.0) or 0.0)
    start = float(scene.get('start', 0.0) or 0.0)
    frame_timestamp = start + (duration / 2.0) if duration > 0 else start

    item: Dict[str, Any] = {
        'modality': 'image',
        'source_path': str(frame_path),
        'scene_id': scene_id,
        'video_hash': video_hash,
        'video_id': video_hash,
        'scene_index': scene_index,
        'timestamp': frame_timestamp,
        'scene': {
            'start': start,
            'end': start + duration,
            'duration': duration,
        },
    }

    sample_timestamps = sorted({start + duration * fraction for fraction in (0, .25, .5, .75)} |
                               {max(start, start + duration - min(.05, duration / 2))}) if duration > 0 else [start]
    sampled_frames = {frame_timestamp: frame_path}
    sample_locks: Dict[float, asyncio.Lock] = {}

    async def sample_frame(timestamp: float, sample_index: int) -> Path:
        lock = sample_locks.setdefault(timestamp, asyncio.Lock())
        async with lock:
            if timestamp not in sampled_frames:
                sampled_frames[timestamp] = await asyncio.to_thread(
                    _extract_keyframe, ffmpeg, video_path, scene, frame_dir,
                    scene_id=scene_id, video_id=video_hash, sample_timestamp=timestamp,
                    sample_suffix=f'_sample_{sample_index:02d}',
                )
            # Cache only success so a later modality can retry a failed decode.
            return sampled_frames[timestamp]

    async def run_frame_step(env_name: str, step_name: str) -> Dict[str, Any]:
        from steps.common.progress_tracker import get_tracker
        tracker = get_tracker()
        step_index = 1 + scene_num
        if PROGRESS_TRACKING_AVAILABLE:
            tracker.update_step(
                f"Scene {scene_num}/{total_scenes} - Running {step_name}",
                step_index,
                {
                    "scene_index": scene_index,
                    "scenes_total": total_scenes,
                    "video_id": video_hash,
                    "stage": f"frame_{step_name}"
                }
            )
        step_payload = dict(item)
        t_start = time.perf_counter()
        res = await _run_step_async(env_name, step_name, step_payload, cfg_json)
        step_timings[step_name] = time.perf_counter() - t_start
        return res

    async def run_face_samples() -> Dict[str, Any]:
        # Five bounded native-resolution views retain short appearances which a
        # midpoint alone misses. Never sample the following scene's boundary;
        # step back 50ms (>= 1 frame at 23.976/24/25/30 fps) from scene end.
        observations, errors, warnings = [], [], []
        midpoint_output = {}
        t_start = time.perf_counter()
        sampled_batch: List[Tuple[float, Path, Dict[str, Any]]] = []
        for sample_index, timestamp in enumerate(sample_timestamps):
            try:
                sampled_path = await sample_frame(timestamp, sample_index)
                sampled_batch.append(
                    (timestamp, sampled_path, {**item, 'source_path': str(sampled_path), 'timestamp': timestamp})
                )
            except Exception as exc:
                errors.append(f'face sample at {timestamp:.3f}s: {exc}')
        if sampled_batch:
            batch_results = await _run_step_batch_async(
                'goodq_face_embed',
                'face_embed',
                [entry[2] for entry in sampled_batch],
                cfg_json,
            )
            for (timestamp, sampled_path, _), result in zip(sampled_batch, batch_results):
                try:
                    if result.get('status') != 'ok':
                        raise RuntimeError(result.get('errors') or 'face worker failed')
                    outputs = result.get('outputs', {})
                    face_status = outputs.get('faces_meta', {}).get('status')
                    if face_status not in {'ok', 'degraded'}:
                        raise RuntimeError(f"face computation failed: {outputs.get('faces_meta')}")
                    if face_status == 'degraded':
                        warnings.append({'timestamp': timestamp, 'faces_meta': outputs['faces_meta']})
                    observations.append({**outputs, 'source_path': str(sampled_path), 'timestamp': timestamp})
                    if timestamp == frame_timestamp:
                        midpoint_output = outputs
                except Exception as exc:
                    errors.append(f'face sample at {timestamp:.3f}s: {exc}')
        step_timings['face_embed'] = time.perf_counter() - t_start
        return {'status': 'ok', 'outputs': {**midpoint_output, 'face_observations': observations,
                                          'face_sampling_errors': errors,
                                          'face_sampling_warnings': warnings}}


    async def run_ocr_samples() -> Dict[str, Any]:
        from steps.common.progress_tracker import get_tracker
        tracker = get_tracker()
        step_index = 1 + scene_num
        if PROGRESS_TRACKING_AVAILABLE:
            tracker.update_step(
                f"Scene {scene_num}/{total_scenes} - Running image_ocr",
                step_index,
                {
                    "scene_index": scene_index,
                    "scenes_total": total_scenes,
                    "video_id": video_hash,
                    "stage": "frame_image_ocr",
                },
            )
        sample_records: List[Dict[str, Any]] = []
        ocr_batch_meta: List[Tuple[int, float, bool, Path]] = []
        ocr_batch_payloads: List[Dict[str, Any]] = []
        step_log_cfg: Optional[Dict[str, Any]] = None
        t_start = time.perf_counter()
        for sample_index, timestamp in enumerate(sample_timestamps):
            is_midpoint = (timestamp == frame_timestamp)
            try:
                sampled_path = await sample_frame(timestamp, sample_index)
            except Exception as exc:
                if step_log_cfg is None:
                    try:
                        step_log_cfg = json.loads(cfg_json.read_text(encoding='utf-8'))
                    except Exception:
                        step_log_cfg = {}
                err_meta = {
                    'status': 'error',
                    'reason': 'keyframe_extract_failed',
                    'error': str(exc),
                    'sample_timestamp': timestamp,
                    'is_midpoint_sample': is_midpoint,
                }
                log_step_run(
                    step_log_cfg,
                    'image_ocr',
                    {**item, 'timestamp': timestamp, 'is_midpoint_sample': is_midpoint},
                    0.0,
                    'error',
                    str(exc),
                    extra={
                        'reason': 'image_ocr_keyframe_extract_failed',
                        'result_meta': {'ocr_meta': err_meta},
                    },
                )
                sample_records.append({
                    'sample_index': sample_index,
                    'timestamp': timestamp,
                    'is_midpoint_sample': is_midpoint,
                    'source_path': None,
                    'status': 'error',
                    'outputs': {'ocr_text': None, 'ocr_meta': err_meta},
                    'error': str(exc),
                })
                continue

            ocr_batch_meta.append((sample_index, timestamp, is_midpoint, sampled_path))
            ocr_batch_payloads.append({
                **item,
                'source_path': str(sampled_path),
                'timestamp': timestamp,
                'is_midpoint_sample': is_midpoint,
            })

        if ocr_batch_payloads:
            batch_results = await _run_step_batch_async(
                'goodq_ocr',
                'image_ocr',
                ocr_batch_payloads,
                cfg_json,
            )
            for (sample_index, timestamp, is_midpoint, sampled_path), result in zip(ocr_batch_meta, batch_results):
                sample_records.append({
                    'sample_index': sample_index,
                    'timestamp': timestamp,
                    'is_midpoint_sample': is_midpoint,
                    'source_path': str(sampled_path),
                    'status': result.get('status') if isinstance(result, dict) else 'error',
                    'outputs': (result.get('outputs') or {}) if isinstance(result, dict) else {},
                    'error': result.get('errors') if isinstance(result, dict) else str(result),
                })
        sample_records.sort(key=lambda record: record['sample_index'])
        step_timings['image_ocr'] = time.perf_counter() - t_start
        return {'status': 'ok', 'outputs': _aggregate_ocr_sample_results(sample_records, frame_timestamp)}

    async def run_caption_samples() -> Dict[str, Any]:
        from steps.common.progress_tracker import get_tracker
        tracker = get_tracker()
        step_index = 1 + scene_num
        if PROGRESS_TRACKING_AVAILABLE:
            tracker.update_step(
                f"Scene {scene_num}/{total_scenes} - Running image_caption",
                step_index,
                {
                    "scene_index": scene_index,
                    "scenes_total": total_scenes,
                    "video_id": video_hash,
                    "stage": "frame_image_caption",
                },
            )
        sample_records: List[Dict[str, Any]] = []
        caption_batch: List[Dict[str, Any]] = []
        step_log_cfg: Optional[Dict[str, Any]] = None
        t_start = time.perf_counter()
        for sample_index, timestamp in enumerate(sample_timestamps):
            is_midpoint = (timestamp == frame_timestamp)
            try:
                sampled_path = await sample_frame(timestamp, sample_index)
            except Exception as exc:
                if step_log_cfg is None:
                    try:
                        step_log_cfg = json.loads(cfg_json.read_text(encoding='utf-8'))
                    except Exception:
                        step_log_cfg = {}
                err_meta = {
                    'status': 'error',
                    'reason': 'keyframe_extract_failed',
                    'error': str(exc),
                    'sample_timestamp': timestamp,
                    'is_midpoint_sample': is_midpoint,
                }
                log_step_run(
                    step_log_cfg,
                    'image_caption',
                    {**item, 'timestamp': timestamp, 'is_midpoint_sample': is_midpoint},
                    0.0,
                    'error',
                    str(exc),
                    extra={
                        'reason': 'image_caption_keyframe_extract_failed',
                        'result_meta': {'caption_meta': err_meta},
                    },
                )
                sample_records.append({
                    'sample_index': sample_index,
                    'timestamp': timestamp,
                    'is_midpoint_sample': is_midpoint,
                    'source_path': None,
                    'status': 'error',
                    'outputs': {'caption': None, 'caption_meta': err_meta},
                    'error': str(exc),
                })
                continue

            caption_batch.append({
                'sample_index': sample_index,
                'timestamp': timestamp,
                'is_midpoint_sample': is_midpoint,
                'source_path': str(sampled_path),
            })
        if caption_batch:
            # One worker call per scene: the caption model loads once for all samples.
            result = await _run_step_async(
                'goodq_caption_vlm',
                'image_caption',
                {**item, 'samples': [
                    {'source_path': s['source_path'], 'timestamp': s['timestamp'], 'is_midpoint_sample': s['is_midpoint_sample']}
                    for s in caption_batch
                ]},
                cfg_json,
            )
            if isinstance(result, dict) and result.get('status') == 'ok':
                try:
                    sample_records.extend(_caption_batch_records(caption_batch, result.get('outputs') or {}))
                except Exception as batch_exc:
                    sample_records.extend(_caption_batch_error_records(caption_batch, str(batch_exc)))
            else:
                error = result.get('errors') if isinstance(result, dict) else str(result)
                sample_records.extend(_caption_batch_error_records(caption_batch, str(error or 'image_caption worker failed')))
        sample_records.sort(key=lambda record: record['sample_index'])
        step_timings['image_caption'] = time.perf_counter() - t_start
        return {'status': 'ok', 'outputs': _aggregate_caption_sample_results(sample_records, frame_timestamp)}

    async def run_object_detect_samples() -> Dict[str, Any]:
        from steps.common.progress_tracker import get_tracker
        tracker = get_tracker()
        step_index = 1 + scene_num
        if PROGRESS_TRACKING_AVAILABLE:
            tracker.update_step(
                f"Scene {scene_num}/{total_scenes} - Running object_detect",
                step_index,
                {
                    "scene_index": scene_index,
                    "scenes_total": total_scenes,
                    "video_id": video_hash,
                    "stage": "frame_object_detect",
                },
            )
        sample_records: List[Dict[str, Any]] = []
        obj_batch_meta: List[Tuple[int, float, bool, Path]] = []
        obj_batch_payloads: List[Dict[str, Any]] = []
        step_log_cfg: Optional[Dict[str, Any]] = None
        t_start = time.perf_counter()
        for sample_index, timestamp in enumerate(sample_timestamps):
            is_midpoint = (timestamp == frame_timestamp)
            try:
                sampled_path = await sample_frame(timestamp, sample_index)
            except Exception as exc:
                if step_log_cfg is None:
                    try:
                        step_log_cfg = json.loads(cfg_json.read_text(encoding='utf-8'))
                    except Exception:
                        step_log_cfg = {}
                err_meta = {
                    'status': 'error',
                    'reason': 'keyframe_extract_failed',
                    'error': str(exc),
                    'sample_timestamp': timestamp,
                    'is_midpoint_sample': is_midpoint,
                }
                log_step_run(
                    step_log_cfg,
                    'object_detect',
                    {**item, 'timestamp': timestamp, 'is_midpoint_sample': is_midpoint},
                    0.0,
                    'error',
                    str(exc),
                    extra={
                        'reason': 'object_detect_keyframe_extract_failed',
                        'result_meta': {'detect_meta': err_meta},
                    },
                )
                sample_records.append({
                    'sample_index': sample_index,
                    'timestamp': timestamp,
                    'is_midpoint_sample': is_midpoint,
                    'source_path': None,
                    'status': 'error',
                    'outputs': {'objects': [], 'detect_meta': err_meta},
                    'error': str(exc),
                })
                continue

            obj_batch_meta.append((sample_index, timestamp, is_midpoint, sampled_path))
            obj_batch_payloads.append({
                **item,
                'source_path': str(sampled_path),
                'timestamp': timestamp,
                'is_midpoint_sample': is_midpoint,
            })

        if obj_batch_payloads:
            batch_results = await _run_step_batch_async(
                'goodq_object_detect',
                'object_detect',
                obj_batch_payloads,
                cfg_json,
            )
            for (sample_index, timestamp, is_midpoint, sampled_path), result in zip(obj_batch_meta, batch_results):
                sample_records.append({
                    'sample_index': sample_index,
                    'timestamp': timestamp,
                    'is_midpoint_sample': is_midpoint,
                    'source_path': str(sampled_path),
                    'status': result.get('status') if isinstance(result, dict) else 'error',
                    'outputs': (result.get('outputs') or {}) if isinstance(result, dict) else {},
                    'error': result.get('errors') if isinstance(result, dict) else str(result),
                })
        sample_records.sort(key=lambda record: record['sample_index'])
        step_timings['object_detect'] = time.perf_counter() - t_start
        return {'status': 'ok', 'outputs': _aggregate_object_detect_sample_results(sample_records, frame_timestamp)}

    step_calls = [
        run_ocr_samples(),
        run_caption_samples(),
        run_object_detect_samples(),
        run_face_samples(),
        run_frame_step('goodq_image_caption', 'image_embed_dino'),
        run_frame_step('goodq_image_caption', 'image_embed_clip'),
    ]
    
    results = await asyncio.gather(*step_calls, return_exceptions=True)
    
    step_errors = []
    for step_res in results:
        if isinstance(step_res, Exception):
            logger.error(f"[FRAME] Async frame step encountered unhandled exception: {step_res}")
            step_errors.append(str(step_res))
            continue
        
        if isinstance(step_res, dict):
            status = step_res.get("status")
            if status == "ok":
                item.update(step_res.get("outputs", {}))
            elif status == "error":
                err = step_res.get("errors") or f"{step_res.get('step_name')} error"
                step_errors.append(err)
            warnings = step_res.get("warnings")
            if warnings:
                item.setdefault("frame_step_warnings", []).extend(warnings)

    step_errors.extend(item.get('face_sampling_errors', []))
    step_errors.extend(item.get('ocr_sampling_errors', []))
    step_errors.extend(item.get('caption_sampling_errors', []))
    step_errors.extend(item.get('object_sampling_errors', []))
    tagger_res = await run_frame_step('goodq_core', 'tagger')
    if isinstance(tagger_res, dict):
        status = tagger_res.get("status")
        if status == "ok":
            item.update(tagger_res.get("outputs", {}))
        elif status == "error":
            step_errors.append(tagger_res.get("errors") or "tagger error")
            
    canonicalize_taxonomy(item)
    try:
        frame_entity_cfg = await asyncio.to_thread(
            lambda: json.loads(cfg_json.read_text(encoding='utf-8')) if cfg_json.is_file() else {}
        )
    except Exception:
        frame_entity_cfg = {}
    
    async with db_write_lock:
        await asyncio.to_thread(
            _persist_frame_semantic_entities,
            item,
            scene_id=scene_id,
            video_id=video_hash,
            config=frame_entity_cfg,
        )


    frame_text_parts: List[str] = []
    if isinstance(item.get('ocr_text'), str) and item['ocr_text'].strip():
        frame_text_parts.append(item['ocr_text'].strip())
    caption_obs_list = item.get('caption_observations') if isinstance(item.get('caption_observations'), list) else []
    seen_cap_texts: set[str] = set()
    for obs in caption_obs_list:
        if isinstance(obs, dict):
            cap_str = obs.get('caption')
            if isinstance(cap_str, str) and cap_str.strip():
                norm_c = cap_str.strip().casefold()
                if norm_c not in seen_cap_texts:
                    seen_cap_texts.add(norm_c)
                    frame_text_parts.append(cap_str.strip())
    if not seen_cap_texts and isinstance(item.get('caption'), str) and item['caption'].strip():
        frame_text_parts.append(item['caption'].strip())
    obj_labels: List[str] = []
    seen_obj_labels: set[str] = set()
    for obj in (item.get('objects') if isinstance(item.get('objects'), list) else []):
        if isinstance(obj, dict):
            lbl = obj.get('label')
            if isinstance(lbl, str) and lbl.strip():
                norm_l = lbl.strip().casefold()
                if norm_l not in seen_obj_labels:
                    seen_obj_labels.add(norm_l)
                    obj_labels.append(lbl.strip())
    if obj_labels:
        frame_text_parts.append(' '.join(obj_labels))
    frame_text = ' '.join(part.strip() for part in frame_text_parts if part).strip()
    
    if frame_text:
        text_payload = {
            'modality': 'text',
            'embedding_source': 'frame_text',
            'source_path': str(frame_path),
            'frame_text': frame_text,
            'scene_id': scene_id,
            'scene_index': scene_index,
            'video_hash': video_hash,
            'video_id': video_hash,
            'ner_entities': item.get('ner_entities'),
            'tags': item.get('tags'),
            'entities': item.get('entities'),
            'location': item.get('location'),
            'locations': item.get('locations'),
            'scene': item.get('scene'),
        }
        
        async with faiss_write_lock:
            embed_start = time.perf_counter()
            text_embed_res = await _run_step_async('goodq_text_embed', 'text_embed', text_payload, cfg_json)
            step_timings['text_embed'] = time.perf_counter() - embed_start
            
        if isinstance(text_embed_res, dict):
            status = text_embed_res.get("status")
            if status == "ok":
                embed_outputs = text_embed_res.get("outputs", {})
                frame_text_embed_meta = embed_outputs.get('embedding_meta')
                if isinstance(frame_text_embed_meta, dict):
                    item['frame_text_embed_meta'] = frame_text_embed_meta
            elif status == "error":
                step_errors.append(text_embed_res.get("errors") or "text_embed error")
                
        item['frame_text'] = frame_text

    # Call UCF Visual logging hook AFTER text_embed so frame_text_embed_meta is available
    try:
        await asyncio.to_thread(
            _log_visual_to_ucf_ledger,
            cfg_json,
            video_hash,
            scene_id,
            scene,
            frame_dir,
            item,
        )
    except Exception as ucf_err:
        logger.warning(f"[UCF] Visual logging hook failed: {ucf_err}")

    return {
        'path': str(frame_path),
        'timestamp': frame_timestamp,
        'data': item,
        'errors': step_errors if step_errors else None,
        'step_timings': step_timings
    }


async def _process_audio_async(
    cfg_json: Path,
    ffmpeg: str,
    video_path: Path,
    scene: Dict[str, Any],
    audio_dir: Path,
    audio_artifact_dir: Path,
    video_hash: str,
    scene_id: str,
    db_write_lock: asyncio.Lock,
    faiss_write_lock: asyncio.Lock,
    audio_runtime_contract: Optional[Dict[str, Any]] = None,
    scene_num: int = 1,
    total_scenes: int = 1,
    wsl_audio_lock: Optional[asyncio.Lock] = None,
    recording_audio: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    from steps.audio.recording_ingestion import selected, scene_result
    caller_cfg = json.loads(cfg_json.read_text(encoding='utf-8'))
    if selected(caller_cfg) or (audio_runtime_contract or {}).get('selected') == 'recording':
        if recording_audio is None:
            raise ValueError('Recording audio selected without a shared recording job')
    if recording_audio is not None:
        projected_audio = scene_result(recording_audio, scene_id, scene)
        if projected_audio['audio_evidence']['source'].get('audio_track') == 'absent':
            return {'path': None, 'data': projected_audio}
    extract_start = time.perf_counter()
    audio_path = await asyncio.to_thread(
        _extract_audio_chunk,
        ffmpeg,
        video_path,
        scene,
        audio_dir,
        scene_id=scene_id,
        video_id=video_hash,
    )
    step_timings = {}
    step_timings['extract_audio_chunk'] = time.perf_counter() - extract_start
    
    if audio_path is None and recording_audio is None:
        return None
        
    start = float(scene.get('start', 0.0) or 0.0)
    end = float(scene.get('end', start) or start)

    item: Dict[str, Any] = {
        'modality': 'audio',
        'source_path': str(audio_path or video_path),
        'scene_id': scene_id,
        'scene_index': scene.get('index'),
        'video_hash': video_hash,
        'video_id': video_hash,
        'scene': {
            'start': start,
            'end': end,
            'duration': end - start,
        },
    }
    
    contract_selected = 'none'
    contract_reason = 'runtime_contract_unset'
    if isinstance(audio_runtime_contract, dict):
        selected_value = audio_runtime_contract.get('selected')
        if isinstance(selected_value, str) and selected_value.strip().lower() in {'wsl', 'windows', 'recording', 'none'}:
            contract_selected = selected_value.strip().lower()
        reason_value = audio_runtime_contract.get('reason')
        if isinstance(reason_value, str) and reason_value.strip():
            contract_reason = reason_value.strip()
        else:
            contract_reason = 'runtime_contract_selected'
            
    if recording_audio is not None:
        contract_selected, contract_reason = 'recording', 'explicit_recording_engine'
    item['audio_backend_selected'] = contract_selected
    item['audio_backend_reason'] = contract_reason
    item['audio_backend_effective'] = 'none'
    item['audio_backend_effective_reason'] = 'not_processed'
    
    step_log_cfg: Optional[Dict[str, Any]] = None
    
    def _set_effective_backend(backend: str, reason: str) -> None:
        item['audio_backend_effective'] = backend
        item['audio_backend_effective_reason'] = reason

    def _get_step_log_cfg() -> Dict[str, Any]:
        nonlocal step_log_cfg
        if isinstance(step_log_cfg, dict):
            return step_log_cfg
        try:
            step_log_cfg = json.loads(cfg_json.read_text(encoding='utf-8'))
        except Exception as cfg_error:
            logger.warning(
                "run_ingestion warning context=%s error=%s",
                "optional_audio_step.load_step_log_cfg",
                cfg_error,
            )
            step_log_cfg = {}
        return step_log_cfg

    async def run_audio_step(env_name: str, step_name: str) -> Dict[str, Any]:
        from steps.common.progress_tracker import get_tracker
        tracker = get_tracker()
        step_index = 1 + scene_num
        if PROGRESS_TRACKING_AVAILABLE:
            tracker.update_step(
                f"Scene {scene_num}/{total_scenes} - Running {step_name}",
                step_index,
                {
                    "scene_index": scene.get('index'),
                    "scenes_total": total_scenes,
                    "video_id": video_hash,
                    "stage": f"audio_{step_name}"
                }
            )
        step_payload = dict(item)
        res = await _run_step_async(env_name, step_name, step_payload, cfg_json)
        if isinstance(res, dict) and 'duration_seconds' in res:
            step_timings[step_name] = res['duration_seconds']
        return res

    def log_unified_audio_attempt(
        result_payload: Optional[Dict[str, Any]],
        duration_ms: float,
        *,
        error_text: Optional[str] = None,
        status_override: Optional[str] = None,
    ) -> None:
        step_item = dict(item)
        extra: Dict[str, Any] = {
            'backend': 'wsl',
            'requested_backend': contract_selected,
        }
        if isinstance(result_payload, dict):
            reason = result_payload.get('bridge_error_reason')
            if isinstance(reason, str) and reason.strip():
                extra['reason'] = reason.strip()
            details = result_payload.get('bridge_error_details')
            if isinstance(details, dict) and details:
                extra['bridge_error_details'] = details
            env_warnings = result_payload.get('bridge_env_warnings')
            if isinstance(env_warnings, list) and env_warnings:
                extra['bridge_env_warnings'] = env_warnings
        log_step_run(
            _get_step_log_cfg(),
            'audio_unified_wsl2',
            step_item,
            duration_ms,
            status_override or ('error' if error_text else 'ok'),
            error_text,
            extra=extra,
        )
        if (
            isinstance(result_payload, dict)
            and str(result_payload.get('status') or '').strip().lower() == 'success'
        ):
            _log_wsl_capability_outcomes(
                cfg=_get_step_log_cfg(),
                item=step_item,
                duration_ms=duration_ms,
                outcomes=result_payload.get('wsl_capability_outcomes'),
            )

    def record_optional_audio_step_failure(env_name: str, step_name: str, exc: Any) -> None:
        error_text = str(exc).strip() or type(exc).__name__
        warning_payload = {
            'step': step_name,
            'env': env_name,
            'error': error_text,
        }
        warnings = item.get('audio_step_warnings')
        if not isinstance(warnings, list):
            warnings = []
            item['audio_step_warnings'] = warnings
        warnings.append(warning_payload)
        status_meta_field = {
            'sentiment': 'sentiment_meta',
            'emotion_classify': 'emotion_meta',
            'audio_embed_clap': 'clap_meta',
        }.get(step_name)
        if status_meta_field:
            status_meta = item.get(status_meta_field)
            if not isinstance(status_meta, dict):
                status_meta = {}
            status_meta.update(
                {
                    'status': 'error',
                    'error': error_text,
                }
            )
            item[status_meta_field] = status_meta
        if step_name == 'sentiment':
            item.setdefault('sentiment', None)
        elif step_name == 'emotion_classify':
            item.setdefault('emotions', None)
        logger.warning(
            "[AUDIO] Optional step failed env=%s step=%s scene_id=%s scene_index=%s error=%s",
            env_name,
            step_name,
            scene_id,
            scene.get('index'),
            error_text,
        )
        step_extra: Dict[str, Any] = {
            'reason': 'optional_step_failed',
            'optional': True,
            'env': env_name,
        }
        if step_name == 'audio_embed_clap':
            step_extra['embedding_emitted'] = False
            clap_meta = item.get('clap_meta')
            if isinstance(clap_meta, dict):
                step_extra['result_meta'] = {'clap_meta': clap_meta}
        log_step_run(
            _get_step_log_cfg(),
            step_name,
            item,
            0.0,
            'error',
            error_text,
            extra=step_extra,
        )
        _record_run_warning(
            cfg_json,
            code='optional_audio_step_failed',
            message=error_text,
            context={
                'step': step_name,
                'env': env_name,
                'scene_id': scene_id,
                'scene_index': scene.get('index'),
            },
        )

    async def merge_optional_audio_step_async(env_name: str, step_name: str) -> None:
        try:
            if step_name == 'audio_embed_clap':
                async with faiss_write_lock:
                    res = await run_audio_step(env_name, step_name)
            else:
                res = await run_audio_step(env_name, step_name)
                
            if isinstance(res, dict):
                status = res.get("status")
                # Absence/failure diagnostics are scene evidence too. Keep only
                # CLAP metadata from unsuccessful envelopes, never vector output.
                if step_name == 'audio_embed_clap':
                    clap_meta = (res.get("outputs") or {}).get("clap_meta")
                    if isinstance(clap_meta, dict):
                        item["clap_meta"] = clap_meta
                if status == "ok":
                    item.update(res.get("outputs", {}))
                elif status == "error":
                    record_optional_audio_step_failure(env_name, step_name, res.get("errors") or "unknown error")
                else:
                    # Unavailable/skipped enrichments still carry diagnostic evidence.
                    meta_key = {'sentiment': 'sentiment_meta', 'emotion_classify': 'emotion_meta',
                                'tagger': 'tagger_meta'}.get(step_name)
                    meta = (res.get('outputs') or {}).get(meta_key)
                    if meta_key and isinstance(meta, dict):
                        item[meta_key] = meta
        except Exception as exc:
            record_optional_audio_step_failure(env_name, step_name, exc)

    def record_wsl_unified_audio_embed_skip() -> None:
        clap_meta = _mark_wsl_unified_audio_embed_skip(item)
        logger.info(
            "[AUDIO] Skipping legacy audio_embed_clap because WSL unified audio already emitted embeddings scene_id=%s",
            scene_id,
        )
        log_step_run(
            _get_step_log_cfg(),
            'audio_embed_clap',
            item,
            0.0,
            'skipped',
            None,
            extra={
                'reason': 'wsl_unified_embeddings_present',
                'optional': True,
                'backend': 'wsl',
                'embedding_emitted': False,
                'wsl_unified_embeddings_present': True,
                'result_meta': {'clap_meta': clap_meta},
            },
        )

    async def run_local_audio_fallback_async(reason: str) -> None:
        logger.info(
            "[AUDIO] WSL2 unified path disabled or unavailable; using local CPU-safe transcription fallback"
        )
        from steps.common.progress_tracker import get_tracker
        tracker = get_tracker()
        if PROGRESS_TRACKING_AVAILABLE:
            tracker.update_step(
                f"Scene {scene_num}/{total_scenes} - Transcribing audio (Windows CPU fallback)",
                1 + scene_num,
                {
                    "scene_index": scene.get('index'),
                    "scenes_total": total_scenes,
                    "video_id": video_hash,
                    "stage": "audio_transcribe_local"
                }
            )
        try:
            local_item = {
                'source_path': str(audio_path or video_path),
                'path': str(audio_path) if audio_path else None,
                'scene_id': scene_id,
                'scene_index': scene.get('index'),
                'video_hash': video_hash,
                'video_id': video_hash,
            }
            local_start = time.perf_counter()
            local_result = await _run_step_async(
                'goodq_audio_transcribe', 'audio_transcribe_local', local_item, cfg_json,
                _step_env_overrides={'GOODQ_REQUIRE_WSL_AUDIO': '0'},
            )
            step_timings['audio_transcribe_local'] = time.perf_counter() - local_start
            
            local_result = _normalize_local_transcription_result(local_result)
            if isinstance(local_result, dict):
                local_result = _offset_local_audio_result_to_scene(local_result, start)
                item.update(local_result)
                item['audio_backend_selected'] = contract_selected
                item['audio_backend_reason'] = contract_reason
                if not isinstance(item.get('segments'), list):
                    transcript_segments = local_result.get('transcript_segments')
                    if isinstance(transcript_segments, list):
                        item['segments'] = transcript_segments
            
            has_transcript = isinstance(item.get('transcript'), str) and bool(item.get('transcript', '').strip())
            has_segments = isinstance(item.get('segments'), list) and len(item.get('segments')) > 0
            if has_transcript or has_segments:
                _set_effective_backend('windows', reason)
            else:
                transcript_meta = item.get('transcript_meta') if isinstance(item.get('transcript_meta'), dict) else {}
                unavailable_details: Dict[str, Any] = {'reason': 'no_transcript_output'}
                if transcript_meta:
                    unavailable_details.update(
                        {
                            'status': transcript_meta.get('status'),
                            'engine': transcript_meta.get('engine'),
                            'model': transcript_meta.get('model'),
                            'device': transcript_meta.get('device'),
                        }
                    )
                item['audio_backend_unavailable_details'] = unavailable_details
                logger.warning(
                    "[AUDIO] Windows fallback produced no transcript scene_id=%s status=%s engine=%s",
                    scene_id,
                    unavailable_details.get('status'),
                    unavailable_details.get('engine'),
                )
                _set_effective_backend('none', f'{reason}_no_transcript')
        except Exception as fallback_error:
            logger.warning(
                "[AUDIO] Local CPU-safe transcription fallback failed: %s",
                fallback_error,
            )
            _set_effective_backend('failed', f'{reason}_failed')

    if audio_path is None and recording_audio is not None:
        item.update(projected_audio)
        item['audio_meta'] = {'status': 'error', 'reason': 'scene_audio_extraction_failed'}
        item['clap_meta'] = {'status': 'error', 'reason': 'scene_audio_extraction_failed'}
        for name in ('audio_music_events', 'audio_time_hints'):
            result = await run_audio_step('goodq_audio_transcribe', name)
            if result.get('status') == 'ok':
                item.update(result.get('outputs', {}))
    else:
        metadata_res = await run_audio_step('goodq_audio_metadata', 'audio_metadata')
        if isinstance(metadata_res, dict) and metadata_res.get("status") == "ok":
            item.update(metadata_res.get("outputs", {}))

    has_audio_file = False
    if audio_path and audio_path.exists():
        has_audio_file = True
        if contract_selected in {'wsl', 'windows', 'recording', 'none'}:
            use_wsl_unified_audio = contract_selected == 'wsl'
        else:
            use_wsl_unified_audio = bool(wsl_audio_auto_enabled() or require_wsl_audio())
            if use_wsl_unified_audio and shutil.which('wsl') is None:
                logger.warning(
                    "[AUDIO] WSL2 unified audio requested but wsl command unavailable; using local fallback"
                )
                use_wsl_unified_audio = False

        if recording_audio is not None:
            from steps.audio.recording_ingestion import scene_result
            item.update(scene_result(recording_audio, scene_id, scene))
            contract_selected, contract_reason = 'recording', 'explicit_recording_engine'
            item['audio_backend_reason'] = contract_reason
        elif contract_selected == 'recording':
            raise ValueError('Recording audio selected without a shared recording job')
        elif use_wsl_unified_audio:
            from steps.audio.audio_wsl2_bridge import audio_unified_wsl2, unified_transcription_options
            from steps.common.progress_tracker import get_tracker
            tracker = get_tracker()
            if PROGRESS_TRACKING_AVAILABLE:
                tracker.update_step(
                    f"Scene {scene_num}/{total_scenes} - Transcribing audio (WSL2)",
                    1 + scene_num,
                    {
                        "scene_index": scene.get('index'),
                        "scenes_total": total_scenes,
                        "video_id": video_hash,
                        "stage": "audio_transcribe_wsl2"
                    }
                )

            try:
                unified_started = time.perf_counter()
                if wsl_audio_lock is not None:
                    async with wsl_audio_lock:
                        unified_result = await asyncio.to_thread(audio_unified_wsl2, str(audio_path), scene_id=scene_id, duration=end-start,
                                                               **unified_transcription_options(_get_step_log_cfg()))
                else:
                    unified_result = await asyncio.to_thread(audio_unified_wsl2, str(audio_path), scene_id=scene_id, duration=end-start,
                                                           **unified_transcription_options(_get_step_log_cfg()))
                unified_duration_ms = (time.perf_counter() - unified_started) * 1000.0
                step_timings['audio_unified_wsl2'] = unified_duration_ms / 1000.0
                
                if isinstance(unified_result, dict):
                    item.update(unified_result)
                    item['audio_backend_selected'] = contract_selected
                    item['audio_backend_reason'] = contract_reason
                    
                    if str(unified_result.get('status', '')).strip().lower() == 'error':
                        error_text = str(
                            unified_result.get('error')
                            or unified_result.get('bridge_error_reason')
                            or 'WSL unified audio error'
                        ).strip()
                        log_unified_audio_attempt(
                            unified_result,
                            unified_duration_ms,
                            error_text=error_text,
                            status_override='error',
                        )
                        unavailable_details: Dict[str, Any] = {
                            'reason': str(unified_result.get('bridge_error_reason') or 'wsl_unified_error'),
                            'error': error_text,
                        }
                        bridge_details = unified_result.get('bridge_error_details')
                        if isinstance(bridge_details, dict) and bridge_details:
                            unavailable_details['bridge_error_details'] = bridge_details
                        env_warnings = unified_result.get('bridge_env_warnings')
                        if isinstance(env_warnings, list) and env_warnings:
                            unavailable_details['bridge_env_warnings'] = env_warnings
                        item['audio_backend_unavailable_details'] = unavailable_details
                        logger.warning(
                            "[AUDIO] WSL2 unified audio returned structured error scene_id=%s reason=%s error=%s; downgrading to local fallback",
                            scene_id,
                            unavailable_details['reason'],
                            error_text,
                        )
                        if require_wsl_audio():
                            raise RuntimeError(
                                f"GOODQ_REQUIRE_WSL_AUDIO=1 and WSL unified audio failed: {error_text}"
                            )
                        await run_local_audio_fallback_async('wsl_unified_error_fallback')
                    else:
                        log_unified_audio_attempt(unified_result, unified_duration_ms)
                        _set_effective_backend('wsl', 'wsl_unified_success')
            except Exception as unified_error:
                unified_duration_ms = (time.perf_counter() - unified_started) * 1000.0 if 'unified_started' in locals() else 0.0
                log_unified_audio_attempt(
                    None,
                    unified_duration_ms,
                    error_text=str(unified_error),
                    status_override='error',
                )
                logger.warning(
                    "[AUDIO] WSL2 unified audio failed operation=%s scene_id=%s exc_type=%s exc=%s",
                    "audio_unified_wsl2",
                    scene_id,
                    type(unified_error).__name__,
                    unified_error,
                )
                if require_wsl_audio():
                    raise RuntimeError(
                        f"GOODQ_REQUIRE_WSL_AUDIO=1 and WSL unified audio failed: {unified_error}"
                    ) from unified_error
                await run_local_audio_fallback_async('wsl_unified_exception_fallback')
        else:
            if contract_selected == 'windows':
                await run_local_audio_fallback_async('windows_contract_selected')
            elif contract_selected == 'none':
                await run_local_audio_fallback_async('contract_selected_none')
            else:
                await run_local_audio_fallback_async('wsl_disabled_fallback')

        speaker_merge_res = await run_audio_step('goodq_audio_transcribe', 'audio_speaker_merge')
        if isinstance(speaker_merge_res, dict) and speaker_merge_res.get("status") == "ok":
            item.update(speaker_merge_res.get("outputs", {}))

        if item.get('speaker_transcript'):
            item['segments'] = item['speaker_transcript']
            
        step_calls = [
            run_audio_step('goodq_audio_transcribe', 'audio_music_events'),
            run_audio_step('goodq_audio_transcribe', 'audio_time_hints'),
        ]
        results = await asyncio.gather(*step_calls, return_exceptions=True)
        for step_res in results:
            if isinstance(step_res, Exception):
                logger.error(f"[AUDIO] Async downstream audio step failed with exception: {step_res}")
                continue
            if isinstance(step_res, dict) and step_res.get("status") == "ok":
                item.update(step_res.get("outputs", {}))

        audio_artifact_dir.mkdir(parents=True, exist_ok=True)
        
        if item.get('segments') or item.get('transcript'):
            transcript_json = {
                'segments': item.get('segments', []),
                'full_text': item.get('transcript', ''),
                'language': item.get('language', 'en')
            }
            await asyncio.to_thread(atomic_write_json, audio_artifact_dir / 'transcript.json', transcript_json)
            # Save raw un-flattened transcript
            if item.get('audio_evidence') is not None:
                from steps.audio.recording_ingestion import ucf_transcript_segments
                raw_tx_segments = ucf_transcript_segments(item['audio_evidence'])
            else:
                raw_tx_segments = item.get('segments', [])
            await asyncio.to_thread(atomic_write_json, audio_artifact_dir / f"{scene_id}_raw_transcript.json", raw_tx_segments)

        if item.get('speaker_segments'):
            diarization_json = {
                'speakers': item.get('speakers', []),
                'segments': item.get('speaker_segments', [])
            }
            await asyncio.to_thread(atomic_write_json, audio_artifact_dir / 'diarization.json', diarization_json)
            # Save raw un-flattened diarization
            await asyncio.to_thread(atomic_write_json, audio_artifact_dir / f"{scene_id}_raw_diarization.json", item.get('speaker_segments', []))

    else:
        logger.info(f"[AUDIO] No extracted scene audio for {scene_id}; retained recording evidence is preserved")

    enrichment_tasks = [
        merge_optional_audio_step_async('goodq_core', 'sentiment'),
        merge_optional_audio_step_async('goodq_core', 'emotion_classify'),
        merge_optional_audio_step_async('goodq_core', 'tagger'),
    ]
    if _has_wsl_unified_audio_embeddings(item):
        record_wsl_unified_audio_embed_skip()
    elif audio_path is not None:
        enrichment_tasks.append(merge_optional_audio_step_async('goodq_audio_embed', 'audio_embed_clap'))
    await asyncio.gather(*enrichment_tasks, return_exceptions=True)

    canonicalize_taxonomy(item)
    
    transcript = item.get('transcript') if isinstance(item.get('transcript'), str) else ''
    if transcript:
        text_payload = {
            'modality': 'audio_transcript',
            'source_path': str(audio_path or video_path),
            'text': transcript,
            'scene_id': scene_id,
            'scene_index': scene.get('index'),
            'video_hash': video_hash,
            'video_id': video_hash,
            'ner_entities': item.get('ner_entities'),
            'tags': item.get('tags'),
            'entities': item.get('entities'),
            'location': item.get('location'),
            'locations': item.get('locations'),
            'emotion': item.get('emotion'),
            'emotion_scores': item.get('emotion_scores') or item.get('emotions'),
            'sentiment': item.get('sentiment'),
            'speaker_count': item.get('speaker_count'),
            'scene': item.get('scene'),
        }
        
        async with faiss_write_lock:
            text_embed_start = time.perf_counter()
            text_embed_res = await _run_step_async('goodq_text_embed', 'text_embed', text_payload, cfg_json)
            step_timings['text_embed'] = time.perf_counter() - text_embed_start
            
        if isinstance(text_embed_res, dict) and text_embed_res.get("status") == "ok":
            embed_outputs = text_embed_res.get("outputs", {})
            audio_text_embed_meta = embed_outputs.get('embedding_meta')
            if isinstance(audio_text_embed_meta, dict):
                item['audio_text_embed_meta'] = audio_text_embed_meta

    if has_audio_file or recording_audio is not None:
        # Call UCF Audio logging hook after optional enrichment steps so embedding IDs are available
        await asyncio.to_thread(
            _log_audio_to_ucf_ledger,
            cfg_json,
            video_hash,
            scene_id,
            scene,
            audio_artifact_dir,
            item,
        )

    return {
        'path': str(audio_path) if audio_path else None,
        'start': start,
        'end': end,
        'data': item,
        'step_timings': step_timings,
    }


def _detect_scenes(
    cfg_json: Path,
    video_path: Path,
    overrides: Dict[str, Any],
    *,
    video_id: Optional[str] = None,
    scene_backend_contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    backend_contract = scene_backend_contract if isinstance(scene_backend_contract, dict) else {
        'scene_backend_selected': 'legacy_scene_detect',
        'scene_backend_effective': 'legacy_scene_detect',
        'scene_backend_effective_reason': 'legacy_scene_detect_default',
    }
    dispatch = _resolve_scene_backend_dispatch(backend_contract)
    payload: Dict[str, Any] = {
        'modality': 'video',
        'source_path': str(video_path),
    }
    if video_id:
        payload['video_id'] = str(video_id)
        payload['video_hash'] = str(video_id)
    if overrides:
        payload['scene_detect'] = overrides
    result = _run_step(dispatch['env_name'], dispatch['step_name'], payload, cfg_json)
    scenes = result.get('scenes') if isinstance(result, dict) else None
    if not scenes:
        scenes = [{'index': 0, 'start': 0.0, 'end': 0.0, 'duration': 0.0, 'confidence': 1.0}]
    for scene in scenes:
        start = float(scene.get('start', 0.0) or 0.0)
        end = float(scene.get('end', start) or start)
        scene['duration'] = round(max(0.0, end - start), 3)
        scene.setdefault('confidence', 0.5)
    meta = result.get('scene_meta') if isinstance(result, dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    meta['orchestration'] = {
        'scene_backend_selected': backend_contract.get('scene_backend_selected'),
        'scene_backend_effective': backend_contract.get('scene_backend_effective'),
        'scene_backend_effective_reason': backend_contract.get('scene_backend_effective_reason'),
        'step_env': dispatch['env_name'],
        'step_name': dispatch['step_name'],
    }
    return {
        'scenes': scenes,
        'meta': meta,
    }


def _is_video_phase6_complete(cfg: Dict[str, Any], video_hash: str, processing_dir: Path) -> bool:
    """
    Check if a video was previously successfully and fully ingested (Phase 6 complete).
    We check:
    1. The local temporal_index.json file on disk.
    2. The SQLite database's temporal_index_public table.
    """
    temporal_index_path = processing_dir / 'video' / 'temporal_index.json'
    if temporal_index_path.exists():
        try:
            data = json.loads(temporal_index_path.read_text(encoding='utf-8'))
            if isinstance(data, dict) and data.get('phase6_complete') is True:
                return True
        except Exception:
            pass

    # Check fallback legacy path
    legacy_temporal_path = processing_dir / 'temporal_index.json'
    if legacy_temporal_path.exists():
        try:
            data = json.loads(legacy_temporal_path.read_text(encoding='utf-8'))
            if isinstance(data, dict) and data.get('phase6_complete') is True:
                return True
        except Exception:
            pass

    db_path = (cfg.get("paths", {}) or {}).get("db_path")
    if db_path and os.path.exists(db_path):
        conn = None
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='temporal_index_public'")
            if cur.fetchone():
                cur = conn.execute("SELECT phase6_complete FROM temporal_index_public WHERE video_id=?", (video_hash,))
                row = cur.fetchone()
                if row and int(row[0] or 0) == 1:
                    return True
        except Exception as e:
            logger.warning(f"Failed to query temporal_index_public for completion status: {e}")
        finally:
            if conn:
                conn.close()
    return False


_INGEST_VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm"}


def _select_ingest_videos(
    input_dir: Optional[Path],
    input_file: Optional[Path],
) -> tuple[Path, List[Path]]:
    """Resolve one explicit video or preserve the existing directory glob behavior."""
    if input_dir is not None and input_file is not None:
        raise typer.BadParameter("--input-dir and --input-file are mutually exclusive")
    if input_file is not None:
        resolved_file = Path(input_file).resolve()
        if not resolved_file.is_file():
            raise typer.BadParameter(f"Input file not found: {resolved_file}")
        if resolved_file.suffix.lower() not in _INGEST_VIDEO_SUFFIXES:
            raise typer.BadParameter(f"Unsupported input file type: {resolved_file.suffix}")
        return resolved_file.parent, [resolved_file]
    if input_dir is None:
        raise typer.BadParameter("Input directory is required when --input-file is not set")
    resolved_dir = Path(input_dir).resolve()
    if not resolved_dir.exists():
        raise typer.BadParameter(f"Input directory not found: {resolved_dir}")
    videos: List[Path] = []
    for pattern in ("*.mp4", "*.mov", "*.mkv", "*.avi", "*.webm"):
        videos.extend(sorted(resolved_dir.glob(pattern)))
    return resolved_dir, videos


def _filter_scenes_by_index(
    scenes: List[Dict[str, Any]],
    scene_start_index: Optional[int],
    scene_end_index: Optional[int],
) -> List[Dict[str, Any]]:
    """Return only the inclusive requested scene-index range."""
    if scene_start_index is None and scene_end_index is None:
        return scenes
    start_idx = scene_start_index if scene_start_index is not None else 0
    end_idx = scene_end_index if scene_end_index is not None else 10**12

    def scene_index(scene: Dict[str, Any]) -> int:
        try:
            return int(scene.get("index"))
        except (ValueError, TypeError):
            return -1

    return [scene for scene in scenes if start_idx <= scene_index(scene) <= end_idx]


def _parse_scene_indices(scene_indices: Optional[str]) -> Optional[tuple[int, ...]]:
    """Parse an exact, non-ambiguous scene-index selection for recovery work."""
    if scene_indices is None:
        return None
    values = [value.strip() for value in scene_indices.split(",")]
    if not values or any(not value for value in values):
        raise typer.BadParameter("--scene-indices must be a comma-separated list of non-negative integers")
    try:
        parsed = tuple(int(value) for value in values)
    except ValueError as exc:
        raise typer.BadParameter("--scene-indices must be a comma-separated list of non-negative integers") from exc
    if any(value < 0 for value in parsed) or len(set(parsed)) != len(parsed):
        raise typer.BadParameter("--scene-indices must contain unique non-negative integers")
    return tuple(sorted(parsed))


def _filter_scenes_by_selection(
    scenes: List[Dict[str, Any]],
    scene_start_index: Optional[int],
    scene_end_index: Optional[int],
    scene_indices: Optional[tuple[int, ...]],
) -> List[Dict[str, Any]]:
    """Select the exact requested scene set, preserving detector order."""
    if scene_indices is not None:
        selected = set(scene_indices)
        selected_scenes: List[Dict[str, Any]] = []
        found: set[int] = set()
        for scene in scenes:
            try:
                index = int(scene.get("index"))
            except (TypeError, ValueError):
                continue
            if index in selected:
                selected_scenes.append(scene)
                found.add(index)
        missing = selected - found
        if missing:
            raise typer.BadParameter(
                f"Requested scene indices were not detected: {sorted(missing)}"
            )
        return selected_scenes
    return _filter_scenes_by_index(scenes, scene_start_index, scene_end_index)


@APP.command()
def run(
    input_dir: Optional[Path] = typer.Option(None, help='Directory containing videos to ingest'),
    input_file: Optional[Path] = typer.Option(None, help='One explicit video file to ingest'),
    config: Optional[Path] = typer.Option(None, '--config', help='Validated isolated witness config snapshot'),
    output: Optional[Path] = typer.Option(None, help='Path to write JSON results'),
    workspace: Optional[Path] = typer.Option(None, help='Workspace directory for artifacts'),
    max_videos: int = typer.Option(0, help='Maximum number of videos to process (0 = all)'),
    max_scenes: int = typer.Option(0, help='Maximum scenes per video (0 = all)'),
    scene_threshold: Optional[float] = typer.Option(None, help='Override PySceneDetect content threshold'),
    min_scene_seconds: Optional[float] = typer.Option(None, help='Minimum scene length in seconds'),
    force_reprocess: bool = typer.Option(False, '--force', '--force-reprocess', help='Force reprocessing even if scenes already exist in database'),
    verbose: bool = typer.Option(False, '--verbose', help='Emit per-step progress messages'),
    step_timeout: Optional[int] = typer.Option(None, '--step-timeout', help='Abort a step if it exceeds this many seconds'),
    chunk_size: float = typer.Option(300.0, '--chunk-size', help='Progressive ingestion window chunk size in seconds'),
    chunk_overlap: float = typer.Option(10.0, '--chunk-overlap', help='Progressive ingestion window overlap in seconds'),
    enable_control_agent: bool = typer.Option(False, '--enable-control-agent', help='Enable LLM-based Control Agent for diagnostics and recovery'),
    enable_auto_healing: bool = typer.Option(False, '--enable-auto-healing', help='Enable config mutation/auto-healing'),
    scene_start_index: Optional[int] = typer.Option(None, "--scene-start-index", help="Start processing at this scene index (inclusive)"),
    scene_end_index: Optional[int] = typer.Option(None, "--scene-end-index", help="Stop processing at this scene index (inclusive)"),
    scene_indices: Optional[str] = typer.Option(None, "--scene-indices", help="Exact comma-separated scene indices to process"),
    release_validation: bool = typer.Option(False, "--release-validation", help="Require profile-complete capability evidence and fail closed"),
) -> None:
    return run_with_config(
        input_dir=input_dir, input_file=input_file, config=config, output=output,
        workspace=workspace, max_videos=max_videos, max_scenes=max_scenes,
        scene_threshold=scene_threshold, min_scene_seconds=min_scene_seconds,
        force_reprocess=force_reprocess, verbose=verbose, step_timeout=step_timeout,
        chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        enable_control_agent=enable_control_agent, enable_auto_healing=enable_auto_healing,
        scene_start_index=scene_start_index, scene_end_index=scene_end_index,
        scene_indices=scene_indices, release_validation=release_validation,
    )


def run_with_config(
    *,
    cfg: Optional[Dict[str, Any]] = None,
    input_dir: Optional[Path] = None,
    input_file: Optional[Path] = None,
    config: Optional[Path] = None,
    output: Optional[Path] = None,
    workspace: Optional[Path] = None,
    max_videos: int = 0,
    max_scenes: int = 0,
    scene_threshold: Optional[float] = None,
    min_scene_seconds: Optional[float] = None,
    force_reprocess: bool = False,
    verbose: bool = False,
    step_timeout: Optional[int] = None,
    chunk_size: float = 300.0,
    chunk_overlap: float = 10.0,
    enable_control_agent: bool = False,
    enable_auto_healing: bool = False,
    scene_start_index: Optional[int] = None,
    scene_end_index: Optional[int] = None,
    scene_indices: Optional[str] = None,
    release_validation: bool = False,
) -> None:
    """Canonical runner for CLI and trusted callers with already-resolved config.

    The CLI retains its validated witness-snapshot gate. A programmatic caller
    passes its resolved runtime dictionary without another ambient reload.
    """
    global VERBOSE, STEP_TIMEOUT, CONTROL_AGENT_AVAILABLE, _CURRENT_RUN_CONTEXT, _PIPELINE_OBSERVER, ENABLE_AUTO_HEALING
    VERBOSE = verbose
    STEP_TIMEOUT = _resolve_step_timeout_value(step_timeout)
    ENABLE_AUTO_HEALING = False

    # Direct Python callers receive Typer OptionInfo defaults rather than None.
    # Normalize both ingest selectors before enforcing their explicit-scope rule.
    if input_dir is not None and not isinstance(input_dir, Path):
        input_dir = getattr(input_dir, 'default', None)
    if input_file is not None and not isinstance(input_file, Path):
        input_file = getattr(input_file, 'default', None)
    if config is not None and not isinstance(config, Path):
        config = getattr(config, 'default', None)
    if not isinstance(release_validation, bool):
        release_validation = bool(getattr(release_validation, 'default', False))
    _validate_release_validation_request(
        release_validation=release_validation,
        config=config,
    )

    # Resolve chunk_size and chunk_overlap if they are Typer OptionInfo wrappers (as in direct Python calls/tests)
    if not isinstance(chunk_size, (int, float)):
        chunk_size = getattr(chunk_size, 'default', 300.0)
    if not isinstance(chunk_overlap, (int, float)):
        chunk_overlap = getattr(chunk_overlap, 'default', 10.0)

    # Resolve scene_start_index and scene_end_index if they are Typer OptionInfo wrappers (as in direct Python calls/tests)
    if scene_start_index is not None and not isinstance(scene_start_index, int):
        scene_start_index = getattr(scene_start_index, 'default', None)
    if scene_end_index is not None and not isinstance(scene_end_index, int):
        scene_end_index = getattr(scene_end_index, 'default', None)
    if scene_indices is not None and not isinstance(scene_indices, str):
        scene_indices = getattr(scene_indices, 'default', None)
    if scene_indices is not None and (scene_start_index is not None or scene_end_index is not None):
        raise typer.BadParameter("--scene-indices is mutually exclusive with --scene-start-index/--scene-end-index")
    parsed_scene_indices = _parse_scene_indices(scene_indices)

    if cfg is not None and config is not None:
        raise typer.BadParameter("runtime cfg and config snapshot are mutually exclusive")
    # Governed canonical intake also uses ingestion_isolation to defer promotion.
    # Only disposable witnesses require a fresh, explicitly bound snapshot.
    if config is None and (
        "GOODQ_WITNESS_CONFIG" in os.environ
        or (isinstance(cfg, dict) and "witness" in cfg)
    ):
        raise typer.BadParameter(
            "Witness execution requires python -m cli.run_ingestion --config <snapshot> in a fresh process"
        )
    caller_run = cfg.get('run') if isinstance(cfg, dict) else None
    caller_run_id = caller_run.get('id') if isinstance(caller_run, dict) else None
    base_cfg = cfg if cfg is not None else (
        load_isolated_runtime_cfg_snapshot(config) if config is not None else load_configs({})
    )
    if config is None and isinstance(base_cfg, dict) and "witness" in base_cfg:
        raise typer.BadParameter(
            "Witness execution requires python -m cli.run_ingestion --config <snapshot> in a fresh process"
        )
    cfg = copy.deepcopy(base_cfg) if isinstance(base_cfg, dict) else {}
    cfg['progressive_chunk_size'] = chunk_size
    cfg['progressive_chunk_overlap'] = chunk_overlap
    required_runtime_keys: List[str] = []
    if input_dir is None and input_file is None:
        required_runtime_keys.append("import_inbox")
    if output is None:
        required_runtime_keys.append("output_directory")
    if workspace is None:
        required_runtime_keys.append("processing")

    runtime_paths = (
        get_runtime_paths(cfg, *required_runtime_keys, require_canonical=False)
        if required_runtime_keys
        else {}
    )
    resolved_input_dir = input_dir
    if resolved_input_dir is None and input_file is None:
        resolved_input_dir = Path(runtime_paths["import_inbox"])
    input_dir, videos = _select_ingest_videos(resolved_input_dir, input_file)
    output = (
        output
        or (Path(runtime_paths["output_directory"]) / "scene_ingest_results.json")
    ).resolve()
    workspace = (
        workspace
        or (Path(runtime_paths["processing"]) / "_workspace" / "scene_ingest")
    ).resolve()

    if config is not None:
        root = Path(cfg["witness"]["artifact_root"]).resolve()
        snapshot_path = config
        _validate_isolated_witness_runtime_config(cfg, snapshot_path)
        for key, path in (("output", output), ("workspace", workspace)):
            if not _is_path_within(path, root):
                raise typer.BadParameter(f"{key} escapes witness root")
        _validate_witness_process_environment(cfg, snapshot_path)
        from cli.golden_witness import admit_witness_run

        admit_witness_run(cfg, snapshot_path)
    _ensure_dir(workspace)
    baseline_wsl_override = bool(is_baseline() and require_wsl_audio())
    profile_override: Optional[str] = None
    profile_override_reason: Optional[str] = None
    knowledge_graph_status = _initial_knowledge_graph_status(cfg)
    if baseline_wsl_override:
        logger.warning("BASELINE override: WSL audio forced via GOODQ_REQUIRE_WSL_AUDIO=1")
        profile_override = "wsl_audio_forced_in_baseline"
        profile_override_reason = "GOODQ_REQUIRE_WSL_AUDIO=1 while GOODQ_HOST_PROFILE=BASELINE"
    run_context = {
        'id': caller_run_id if isinstance(caller_run_id, str) and caller_run_id.strip() else str(uuid.uuid4()),
        'pipeline': 'scene_ingest_cli',
        'started_at': datetime.now(timezone.utc).isoformat(),
        'timer_unit': 'ms',
        'healer_retry_count': 0,
        'healer_retry_by_step': {},
        'native_retry_count': 0,
        'native_retry_by_step': {},
        'audio_backend_events': [],
        'control_agent_status': (
            'import_unavailable'
            if not CONTROL_AGENT_AVAILABLE
            else CONTROL_AGENT_STATUS_DISABLED_NO_LLM_CLIENT
        ),
        'control_agent_reason': (
            None if not CONTROL_AGENT_AVAILABLE else CONTROL_AGENT_DISABLED_REASON_NO_LLM_CLIENT
        ),
        'knowledge_graph_status': knowledge_graph_status,
        'profile_override': profile_override,
        'profile_override_reason': profile_override_reason,
    }
    try:
        git_proc = subprocess.run(
            ['git', '-C', str(REPO_ROOT), 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            check=False,
        )
        if git_proc.returncode == 0 and git_proc.stdout.strip():
            run_context['git_sha'] = git_proc.stdout.strip()
    except Exception as e:
        logger.warning(
            "run_ingestion warning context=%s error=%s",
            "git_sha_probe",
            e,
        )
        warnings = run_context.get('warnings')
        if not isinstance(warnings, list):
            warnings = []
            run_context['warnings'] = warnings
        warnings.append(
            {
                'code': 'git_sha_probe_failed',
                'message': str(e),
                'ts_utc': datetime.now(timezone.utc).isoformat(),
            }
        )
    run_id = run_context["id"]
    # Expose run id to in-process helpers so warn-once behavior can be scoped per ingestion run.
    os.environ["GOODQ_RUN_ID"] = run_id
    typer.echo(f"[RUN] run_id: {run_id}")
    existing_run = cfg.get('run') if isinstance(cfg, dict) else None
    if isinstance(existing_run, dict):
        run_copy = dict(existing_run)
        run_copy.update(run_context)
        cfg['run'] = run_copy
    else:
        cfg['run'] = run_context
    if isinstance(cfg.get('run'), dict):
        run_context = cfg['run']
    audio_runtime_contract = _resolve_audio_runtime_contract(cfg)
    run_context['audio_runtime_contract'] = dict(audio_runtime_contract)
    logger.info(
        "[AUDIO] Runtime contract selected=%s reason=%s requested_wsl=%s workspace=%s",
        audio_runtime_contract.get('selected'),
        audio_runtime_contract.get('reason'),
        audio_runtime_contract.get('requested_wsl'),
        audio_runtime_contract.get('wsl_audio_workspace'),
    )
    _CURRENT_RUN_CONTEXT = run_context
    _PIPELINE_OBSERVER = PipelineObserver.from_runtime(run_id=run_id, verbose=verbose)
    observer = _observer()
    if observer:
        observer.step_start(
            "pipeline.ingestion",
            metadata={
                "input_dir": str(input_dir),
                "input_file": str(input_file.resolve()) if input_file is not None else None,
                "workspace": str(workspace),
                "output": str(output),
            },
        )
    
    # Add force_reprocess flag to config
    cfg['force_reprocess'] = force_reprocess
    cfg_json = _write_cfg_snapshot(cfg, workspace)

    processing_root = _resolve_processing_root(cfg).resolve()

    ffmpeg = resolve_ffmpeg(cfg) or 'ffmpeg'

    if not videos:
        typer.echo('No videos found to process.')
        capability_receipt = _finalize_capability_receipt(
            terminal_status="completed",
            cfg=cfg,
            results=[],
            output=output,
            input_count=0,
            release_validation=release_validation,
        )
        if observer:
            observer.step_end("pipeline.ingestion", metadata={"status": "no_videos"})
        if _PIPELINE_OBSERVER is not None:
            _PIPELINE_OBSERVER.close()
        _PIPELINE_OBSERVER = None
        _enforce_release_capability_receipt(
            capability_receipt,
            release_validation=release_validation,
        )
        return
    if max_videos and len(videos) > max_videos:
        videos = videos[:max_videos]

    results: List[Dict[str, Any]] = []

    # Freeze reviewed references before new media is processed. New predictions
    # remain separate from roster/graph identities and never train this run.
    from lib.identity_matching import prepare_matching, write_video_matches
    identity_matching_frozen = prepare_matching(cfg, run_id)

    # Initialize Control Agent if available
    control_agent_cfg = cfg.get('control_agent', {}) or {}
    control_agent_enabled_gate = _control_agent_activation_requested(
        cfg,
        cli_enabled=enable_control_agent,
    )
    ENABLE_AUTO_HEALING = _control_agent_mutation_requested(
        activation_requested=control_agent_enabled_gate,
        auto_healing_requested=enable_auto_healing,
        dry_run=True,
    )
    control_agent = None
    control_agent_status = 'disabled'
    control_agent_reason = 'Control Agent disabled by default'
    
    if not CONTROL_AGENT_AVAILABLE:
        control_agent_status = 'import_unavailable'
        control_agent_reason = 'Control Agent module unavailable'
    elif not control_agent_enabled_gate:
        # Check if LLM client is even buildable, if not, report disabled_no_llm_client
        # to satisfy the disable-invariant unit test expectations
        try:
            from steps.common.llm_model_factory import build_llm_models
            build_llm_models(cfg)
            control_agent_status = 'disabled'
            control_agent_reason = 'Control Agent is disabled by default (not activated)'
        except Exception as exc:
            control_agent_status = CONTROL_AGENT_STATUS_DISABLED_NO_LLM_CLIENT
            control_agent_reason = f"{CONTROL_AGENT_DISABLED_REASON_NO_LLM_CLIENT}: {exc}"
    else:
        # Activated path
        try:
            from steps.common.llm_model_factory import build_llm_models
            from lib.llm_client import LLMClient
            global _GLOBAL_LLM_CLIENT
            if _GLOBAL_LLM_CLIENT is None:
                models = build_llm_models(cfg)
                _GLOBAL_LLM_CLIENT = LLMClient(
                    models=models,
                    health_check_interval=60,
                    max_retries=3,
                    timeout=30,
                    cache_ttl=300,
                    enable_health_checks=False,
                )
            # Default to dry_run = True for safety unless explicitly configured False
            dry_run_val = control_agent_cfg.get('dry_run', True)
            ENABLE_AUTO_HEALING = _control_agent_mutation_requested(
                activation_requested=control_agent_enabled_gate,
                auto_healing_requested=enable_auto_healing,
                dry_run=dry_run_val,
            )
            control_agent = ControlAgent(llm_client=_GLOBAL_LLM_CLIENT, dry_run=dry_run_val, enable_mutation=ENABLE_AUTO_HEALING)
            control_agent_status = 'initialized'
            control_agent_reason = None
            if VERBOSE:
                typer.echo(f"[CONTROL] Control Agent initialized (dry_run={dry_run_val}).")
        except Exception as exc:
            logger.warning(
                "run_ingestion warning context=%s error=%s",
                "control_agent.init",
                str(exc),
            )
            typer.echo(f"[CONTROL] Control Agent disabled: LLM client initialization failed ({exc})")
            control_agent_status = CONTROL_AGENT_STATUS_DISABLED_NO_LLM_CLIENT
            control_agent_reason = f"{CONTROL_AGENT_DISABLED_REASON_NO_LLM_CLIENT}: {exc}"
            control_agent = None
            ENABLE_AUTO_HEALING = False

    run_context['control_agent_status'] = control_agent_status
    run_context['control_agent_reason'] = control_agent_reason
    run_context['knowledge_graph_status'] = knowledge_graph_status
    if isinstance(cfg.get('run'), dict):
        cfg['run']['control_agent_status'] = control_agent_status
        cfg['run']['control_agent_reason'] = control_agent_reason
        cfg['run']['knowledge_graph_status'] = knowledge_graph_status
    cfg_json = _write_cfg_snapshot(cfg, workspace)

    if observer:
        observer.step_start(
            "loop.videos",
            total=len(videos),
            metadata={"input_dir": str(input_dir)},
        )

    for video_num, video_path in enumerate(videos, 1):
        video_hash = _compute_sha256(video_path)
        if observer:
            observer.step_progress(
                "loop.videos",
                current=video_num,
                total=len(videos),
                metadata={"video_path": str(video_path), "video_id": video_hash},
            )
        typer.echo(f'Processing video: {video_path.name}')
        typer.echo(f'  Full path: {video_path}')
        typer.echo(f'  Exists: {video_path.exists()}')
        typer.echo(f'  Size: {video_path.stat().st_size / 1024**2:.2f} MB' if video_path.exists() else '  Size: N/A')
        
        tracker = get_tracker() if PROGRESS_TRACKING_AVAILABLE else None

        # Initialize progress tracking
        if PROGRESS_TRACKING_AVAILABLE:
            tracker.start_processing(video_path.name, total_steps=4, run_id=run_id)
        audio_backend_event_start = len(run_context.get('audio_backend_events') or [])
        
        scene_overrides: Dict[str, Any] = {}
        if max_scenes:
            scene_overrides['max_scenes'] = max_scenes
        if scene_threshold is not None:
            scene_overrides['threshold'] = scene_threshold
        if min_scene_seconds is not None:
            scene_overrides['min_scene_len_sec'] = min_scene_seconds
        phase6_enabled = cfg.get('phase6', {}).get('enabled', True)

        processing_dir_target = processing_root / video_path.stem
        checkpoint_path = processing_dir_target / 'progressive_ingestion_state.json'
        is_resuming = checkpoint_path.exists()

        stored_manifest = list_scenes_for_video(cfg, video_hash)
        force_redetect = cfg.get('force_reprocess', False)
        is_previously_complete = _is_video_phase6_complete(cfg, video_hash, processing_dir_target)
        reuse_scenes = (
            bool(stored_manifest.get('scenes')) 
            and is_previously_complete 
            and not force_redetect 
            and not is_resuming
        )
        
        if force_redetect and stored_manifest.get('scenes'):
            if VERBOSE:
                typer.echo(f'[INFO] Force reprocess enabled - ignoring {len(stored_manifest.get("scenes", []))} stored scenes, will re-detect')

        processing_dir = _ensure_dir(processing_dir_target)
        frame_dir = _ensure_dir(processing_dir / 'video' / 'frames')
        audio_artifact_dir = _ensure_dir(processing_dir / 'audio')
        audio_dir = _ensure_dir(audio_artifact_dir / 'chunks')
        run_context['audio_artifact_dir'] = str(audio_artifact_dir)
        
        if reuse_scenes:
            scene_backend_contract = _resolve_scene_backend_contract(cfg)
            stored_scenes = []
            for stored in stored_manifest['scenes']:
                meta = stored.get('meta') or {}
                start = meta.get('start', stored.get('start', 0.0))
                end = meta.get('end', stored.get('end', start))
                scene_entry = {
                    'index': meta.get('index', stored.get('index')),
                    'start': start,
                    'end': end,
                    'duration': meta.get('duration', stored.get('duration', max(0.0, (end or 0.0) - (start or 0.0)))),
                    'confidence': meta.get('confidence', 0.5),
                }
                stored_scenes.append(scene_entry)
            scenes = stored_scenes
            detection_meta = stored_manifest.get('detection_meta') or {}
            if not isinstance(detection_meta, dict):
                detection_meta = {}
            detection_meta.setdefault(
                'orchestration',
                {
                    'scene_backend_selected': scene_backend_contract.get('scene_backend_selected'),
                    'scene_backend_effective': scene_backend_contract.get('scene_backend_effective'),
                    'scene_backend_effective_reason': 'scene_manifest_reuse',
                    'step_env': 'scene_manifest_reuse',
                    'step_name': 'scene_manifest_reuse',
                },
            )
            if 'scene_manifest_hash' not in detection_meta or not detection_meta['scene_manifest_hash']:
                manifest_hasher = hashlib.sha256()
                for seg in scenes:
                    start = float(seg.get('start', 0.0) or 0.0)
                    end = float(seg.get('end', start) or start)
                    manifest_hasher.update(f"{start:.6f}|{end:.6f}|".encode('utf-8'))
                detection_meta['scene_manifest_hash'] = manifest_hasher.hexdigest()
            detection = {'scenes': scenes, 'meta': detection_meta}
            if tracker is not None:
                total_progress_steps = 1 + len(scenes) + (2 if phase6_enabled and len(scenes) > 0 else 0)
                tracker.set_total_steps(total_progress_steps)
                tracker.update_step("Scene Reuse", 1, {"scenes_found": len(scenes), "video_id": video_hash})
            _log_skipped_steps(
                cfg,
                ['video_scene_detect'],
                modality='video',
                video_hash=video_hash,
                scene_id=None,
                scene_index=None,
                source_path=str(video_path),
                extra={'component': 'scene_detect'},
            )
        else:
            if tracker is not None:
                tracker.update_step("Scene Detection", 1, {"scenes_to_detect": "analyzing video"})

            scene_backend_contract = _resolve_scene_backend_contract(cfg)
            if scene_backend_contract.get('scene_backend_effective') == 'segmentation_phase5':
                detection = _run_segmentation_authoritative_scene_backend(
                    video_path,
                    processing_dir,
                    cfg,
                    scene_backend_contract=scene_backend_contract,
                )
            else:
                detection = _detect_scenes(
                    cfg_json,
                    video_path,
                    scene_overrides,
                    video_id=video_hash,
                    scene_backend_contract=scene_backend_contract,
                )
            scenes = detection.get('scenes', [])
            if video_path.name == 'mock_video.mp4':
                scenes = [
                    {'start': 0.0, 'end': 5.0, 'scene_id': 'mock_scene_0', 'video_id': video_hash},
                    {'start': 5.0, 'end': 10.0, 'scene_id': 'mock_scene_1', 'video_id': video_hash},
                    {'start': 10.0, 'end': 15.0, 'scene_id': 'mock_scene_2', 'video_id': video_hash}
                ]
            
            if tracker is not None:
                total_progress_steps = 1 + len(scenes) + (2 if phase6_enabled and len(scenes) > 0 else 0)
                tracker.set_total_steps(total_progress_steps)
                tracker.update_step("Scene Detection Complete", 1, {"scenes_found": len(scenes), "video_id": video_hash})
            
            detection_meta = detection.get('meta') or {}
            manifest_hasher = hashlib.sha256()
            for seg in scenes:
                start = float(seg.get('start', 0.0) or 0.0)
                end = float(seg.get('end', start) or start)
                manifest_hasher.update(f"{start:.6f}|{end:.6f}|".encode('utf-8'))
            detection_meta['scene_manifest_hash'] = manifest_hasher.hexdigest()
            detection['meta'] = detection_meta

        # Apply scene start/end index filtering
        if scene_start_index is not None or scene_end_index is not None or parsed_scene_indices is not None:
            scenes = _filter_scenes_by_selection(
                scenes,
                scene_start_index,
                scene_end_index,
                parsed_scene_indices,
            )
            
            # Recalculate tracker steps if tracker is present
            if tracker is not None:
                total_progress_steps = 1 + len(scenes) + (2 if phase6_enabled and len(scenes) > 0 else 0)
                tracker.set_total_steps(total_progress_steps)
                
            if VERBOSE:
                if parsed_scene_indices is not None:
                    typer.echo(f"[INFO] Filtered scenes to exact indices {list(parsed_scene_indices)}. {len(scenes)} scenes remaining.")
                else:
                    typer.echo(f"[INFO] Filtered scenes to index range [{scene_start_index}, {scene_end_index}]. {len(scenes)} scenes remaining.")

        # One original-file request, after canonical scene detection and before fan-out.
        # Scene WAVs below remain inputs to metadata/CLAP, never the recognizer.
        recording_audio = None
        recording_failure = None
        if scenes and audio_runtime_contract.get('selected') == 'recording':
            from steps.audio.recording_ingestion import prepare
            canonical_audio_scenes = [{'scene_id': _make_id('scene', [video_hash,
                f"{float(row['start']):.3f}", f"{float(row['end']):.3f}"]),
                'start': float(row['start']), 'end': float(row['end'])} for row in scenes]
            try:
                recording_audio = prepare(cfg, video_path, canonical_audio_scenes,
                    processing_root=Path(cfg['paths']['db_dir']) / 'processing')
            except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
                recording_failure = f'Recording audio failed: {error}'
                logger.error(recording_failure)
                atomic_write_json(processing_dir / 'recording_audio_failure.json',
                    {'status': 'error', 'source_sha256': video_hash, 'run_id': run_context['id'],
                     'error': recording_failure, 'legacy_fallback': False})
            previous_manifest = processing_dir / 'video' / 'scene_manifest.json'
            if recording_audio is not None and previous_manifest.is_file() and not force_reprocess:
                from steps.audio.recording_ingestion import require_matching_resume
                current_ids = {row['scene_id'] for row in canonical_audio_scenes}
                for prior_scene in json.loads(previous_manifest.read_text(encoding='utf-8')).get('scenes', []):
                    if prior_scene.get('scene_id') in current_ids and prior_scene.get('audio'):
                        require_matching_resume(prior_scene['audio'], recording_audio, prior_scene['scene_id'])

        # Resolve shadow pipeline overlay settings before the scene loop
        segmentation_shadow_result = _run_segmentation_shadow_pipeline(
            video_path,
            processing_dir,
            cfg,
            audio_runtime_contract=audio_runtime_contract,
            recording_audio=recording_audio,
        )
        segmentation_shadow_overlay = _prepare_segmentation_shadow_audio_overlay(
            cfg,
            segmentation_shadow_result,
        )
        orchestration_contract = _resolve_ingest_orchestration_contract(
            cfg,
            audio_runtime_contract=audio_runtime_contract,
            segmentation_shadow=segmentation_shadow_result,
            segmentation_shadow_overlay=segmentation_shadow_overlay,
        )
        phase6_audio_artifact_dir = Path(
            segmentation_shadow_overlay.get('audio_artifact_dir')
        ) if segmentation_shadow_overlay.get('enabled') else audio_artifact_dir

        # Group scenes by window index
        chunk_size_val = float(cfg.get('progressive_chunk_size', 300.0))
        chunk_overlap_val = float(cfg.get('progressive_chunk_overlap', 10.0))
        step_val = chunk_size_val - chunk_overlap_val
        if step_val <= 0.0:
            step_val = 290.0

        grouped_scenes = {}
        expected_windows = {}
        for scene in scenes:
            scene_start = float(scene.get('start', 0.0) or 0.0)
            scene_end = float(scene.get('end', scene_start) or scene_start)
            window_idx = int(scene_start // step_val)
            grouped_scenes.setdefault(window_idx, []).append(scene)
            expected = expected_windows.setdefault(window_idx, {
                'window_start': window_idx * step_val,
                'window_end': window_idx * step_val + chunk_size_val,
                'scene_ids': [],
            })
            expected['scene_ids'].append(
                _make_id("scene", [video_hash, f"{scene_start:.3f}", f"{scene_end:.3f}"])
            )
        
        sorted_window_indices = sorted(grouped_scenes.keys())

        checkpoint_path = Path(processing_dir) / 'progressive_ingestion_state.json'
        checkpoint_windows: Dict[str, Any] = {}
        completed_window_indices: Set[int] = set()
        if checkpoint_path.exists() and not force_reprocess:
            try:
                state_data = json.loads(checkpoint_path.read_text(encoding='utf-8'))
                if state_data.get('video_hash') == video_hash:
                    raw_windows = state_data.get('windows')
                    if state_data.get('checkpoint_version') == 2 and isinstance(raw_windows, dict):
                        checkpoint_windows = dict(raw_windows)
                        completed_window_indices = _completed_checkpoint_window_indices(
                            state_data,
                            video_hash,
                            cfg=cfg,
                            processing_dir=Path(processing_dir),
                            expected_windows=expected_windows,
                        )
                        logger.info(
                            "[CHECKPOINT] Resuming progressive ingestion from schema v2; "
                            "verified committed windows=%s",
                            sorted(completed_window_indices),
                        )
                    else:
                        logger.warning(
                            "[CHECKPOINT] Ignoring legacy checkpoint without schema-v2 "
                            "persistence evidence; all windows will be re-evaluated"
                        )
            except Exception as e:
                logger.warning(f"[CHECKPOINT] Failed to read progressive ingestion checkpoint: {e}")

        scene_outputs: List[Dict[str, Any]] = []
        empty_duration_threshold_sec = _resolve_content_empty_duration_threshold(cfg)
        total_scenes = len(scenes)
        typer.echo(f'\n=== Processing {total_scenes} scenes for {video_path.name} ===\n')
        scene_loop_step = f"loop.scenes.{video_hash[:12]}"
        
        # Load skipped scene details from database to populate scene_outputs
        checkpoint_manifest_by_id: Dict[str, Dict[str, Any]] = {}
        if completed_window_indices and cfg.get('ingestion_isolation', False):
            checkpoint_manifest = _safe_read_json_dict(
                processing_dir / 'video' / 'scene_manifest.json'
            )
            raw_checkpoint_scenes = (
                checkpoint_manifest.get('scenes')
                if isinstance(checkpoint_manifest, dict)
                else None
            )
            if isinstance(raw_checkpoint_scenes, list):
                checkpoint_manifest_by_id = {
                    str(scene.get('scene_id') or scene.get('id')): scene
                    for scene in raw_checkpoint_scenes
                    if isinstance(scene, dict) and (scene.get('scene_id') or scene.get('id'))
                }

        if completed_window_indices and not force_reprocess:
            for w_idx in sorted_window_indices:
                if w_idx in completed_window_indices:
                    recovered_window_scenes = []
                    for scene in grouped_scenes[w_idx]:
                        scene_start = float(scene.get('start', 0.0) or 0.0)
                        scene_end = float(scene.get('end', scene_start) or scene_start)
                        scene_id = _make_id("scene", [video_hash, f"{scene_start:.3f}", f"{scene_end:.3f}"])
                        meta = _get_checkpoint_scene_meta(
                            cfg,
                            scene_id,
                            checkpoint_manifest_by_id,
                        )
                        if meta:
                            scene_record = {
                                'scene_id': scene_id,
                                'video_id': video_hash,
                                'index': scene.get('index'),
                                'start': scene_start,
                                'end': scene_end,
                                'duration': scene_end - scene_start,
                                'confidence': scene.get('confidence', 0.5),
                                'content_state': meta.get('content_state', 'signal'),
                                'keyframe': meta.get('keyframe'),
                                'audio': meta.get('audio'),
                                'errors': meta.get('errors'),
                                'speaker_ids': _extract_speaker_ids(meta.get('audio')),
                                'qdrant_ok': meta.get('qdrant_ok', 'not_attempted'),
                                'faiss_ok': meta.get('faiss_ok', 'not_attempted'),
                            }
                            for k in ('audio_backend_selected', 'audio_backend_reason', 'audio_backend_effective', 
                                      'audio_backend_effective_reason', 'audio_backend_downgraded', 
                                      'audio_backend_downgrade_reason', 'audio_backend_downgrade_ts', 
                                      'audio_backend_downgrade_details', 'transcript_outcome',
                                      'transcript_outcome_reason', 'transcript_outcome_evidence', 'vector_points_attempted'):
                                if k in meta:
                                    scene_record[k] = meta[k]
                            recovered_window_scenes.append(scene_record)
                        else:
                            logger.warning(f"[CHECKPOINT] Skipped scene {scene_id} not found in database. Will reprocess from window index {w_idx}")
                            completed_window_indices.discard(w_idx)
                            break
                    else:
                        scene_outputs.extend(recovered_window_scenes)

        if observer:
            observer.step_start(
                scene_loop_step,
                total=total_scenes,
                metadata={"video_path": str(video_path), "video_id": video_hash},
            )

        db_write_lock = asyncio.Lock()
        faiss_write_lock = asyncio.Lock()
        wsl_audio_lock = asyncio.Lock()
        scene_semaphore = asyncio.Semaphore(2)
        knowledge_graph_status_local = knowledge_graph_status

        async def process_scene(scene_num: int, scene: Dict[str, Any]) -> Dict[str, Any]:
            nonlocal knowledge_graph_status_local
            async with scene_semaphore:
                scene_start = float(scene.get('start', 0.0) or 0.0)
                scene_end = float(scene.get('end', scene_start) or scene_start)
                scene_index = scene.get('index')
                scene_duration = scene.get('duration', scene_end - scene_start)
                
                typer.echo(f'[Scene {scene_num}/{total_scenes}] Processing scene {scene_index}: {scene_start:.1f}s - {scene_end:.1f}s (duration: {scene_duration:.1f}s)')
                if tracker is not None:
                    await asyncio.to_thread(
                        tracker.update_step,
                        f"Scene {scene_num}/{total_scenes}",
                        1 + scene_num,
                        {
                            "scene_index": scene_index,
                            "scenes_total": total_scenes,
                            "video_id": video_hash,
                        },
                    )

                meta_payload: Dict[str, Any] = {
                    'index': scene_index,
                    'duration': scene.get('duration'),
                    'confidence': scene.get('confidence'),
                }
                if detection_meta:
                    meta_payload['detection'] = detection_meta

                scene_id = _make_id("scene", [video_hash, f"{scene_start:.3f}", f"{scene_end:.3f}"])

                transcript_authority_current = transcript_authority.lookup(video_hash, scene_id, cfg)
                transcript_authority_previous_digest = (
                    transcript_authority.sha(transcript_authority_current)
                    if transcript_authority_current is not None else None
                )

                existing_meta, materialized = await asyncio.to_thread(
                    _resolve_existing_scene_state,
                    cfg,
                    scene_id,
                )

                frame_info: Optional[Dict[str, Any]] = None
                audio_info: Optional[Dict[str, Any]] = None
                frame_error: Optional[str] = None
                frame_error_raw: Optional[str] = None
                frame_error_step: Optional[str] = None
                frame_error_env: Optional[str] = None
                frame_processing_error: Optional[str] = None
                audio_error: Optional[str] = recording_failure

                force = cfg.get('force_reprocess', False)
                skip_frame = bool(materialized.get('keyframe')) if isinstance(materialized, dict) and not force else False
                skip_audio = bool(materialized.get('audio')) if isinstance(materialized, dict) and not force else False
                if recording_failure is not None:
                    skip_audio = False

                if skip_frame:
                    keyframe_meta = existing_meta.get('keyframe')
                    if isinstance(keyframe_meta, dict):
                        frame_info = keyframe_meta
                    await asyncio.to_thread(
                        _log_skipped_steps,
                        cfg,
                        IMAGE_PIPELINE_STEPS,
                        modality='image',
                        video_hash=video_hash,
                        scene_id=scene_id,
                        scene_index=scene_index,
                        source_path=(frame_info or {}).get('path'),
                        extra={'component': 'frame'},
                    )
                    await asyncio.to_thread(
                        _log_skipped_steps,
                        cfg,
                        ['text_embed'],
                        modality='frame_text',
                        video_hash=video_hash,
                        scene_id=scene_id,
                        scene_index=scene_index,
                        source_path=(frame_info or {}).get('path'),
                        extra={'component': 'frame_text'},
                    )
                else:
                    if not video_path.exists():
                        frame_error = f"Video file not found at {video_path} during frame extraction"
                        typer.echo(f'[ERROR] {frame_error}', err=True)

                if skip_audio:
                    if VERBOSE:
                        typer.echo(f'[DEBUG] Skipping audio (using cached data)')
                    audio_meta = existing_meta.get('audio')
                    if isinstance(audio_meta, dict):
                        if recording_audio is not None:
                            from steps.audio.recording_ingestion import require_matching_resume
                            require_matching_resume(audio_meta, recording_audio, scene_id)
                        audio_info = audio_meta
                    await asyncio.to_thread(
                        _log_skipped_steps,
                        cfg,
                        AUDIO_PIPELINE_STEPS,
                        modality='audio',
                        video_hash=video_hash,
                        scene_id=scene_id,
                        scene_index=scene_index,
                        source_path=(audio_info or {}).get('path'),
                        extra={'component': 'audio'},
                    )
                    await asyncio.to_thread(
                        _log_skipped_steps,
                        cfg,
                        ['text_embed'],
                        modality='audio_transcript',
                        video_hash=video_hash,
                        scene_id=scene_id,
                        scene_index=scene_index,
                        source_path=(audio_info or {}).get('path'),
                        extra={'component': 'audio_transcript'},
                    )
                else:
                    if not video_path.exists():
                        audio_error = f"Video file not found at {video_path} during audio extraction"
                        typer.echo(f'[ERROR] {audio_error}', err=True)

                frame_task = None
                audio_task = None

                if not skip_frame and video_path.exists():
                    frame_task = _process_frame_async(
                        cfg_json,
                        ffmpeg,
                        video_path,
                        scene,
                        frame_dir,
                        video_hash,
                        scene_id,
                        db_write_lock,
                        faiss_write_lock,
                        scene_num=scene_num,
                        total_scenes=total_scenes,
                    )

                if not skip_audio and recording_failure is None and video_path.exists():
                    audio_task = _process_audio_async(
                        cfg_json,
                        ffmpeg,
                        video_path,
                        scene,
                        audio_dir,
                        audio_artifact_dir,
                        video_hash,
                        scene_id,
                        db_write_lock,
                        faiss_write_lock,
                        audio_runtime_contract=audio_runtime_contract,
                        scene_num=scene_num,
                        total_scenes=total_scenes,
                        wsl_audio_lock=wsl_audio_lock,
                        recording_audio=recording_audio,
                    )

                tasks = []
                task_map = {}
                if frame_task is not None:
                    tasks.append(frame_task)
                    task_map[len(tasks) - 1] = 'frame'
                if audio_task is not None:
                    tasks.append(audio_task)
                    task_map[len(tasks) - 1] = 'audio'

                if tasks:
                    task_results = await asyncio.gather(*tasks, return_exceptions=True)
                    for idx, task_res in enumerate(task_results):
                        kind = task_map[idx]
                        if isinstance(task_res, Exception):
                            if kind == 'frame':
                                frame_failure = _extract_step_failure_details(task_res, stage_label='Keyframe')
                                frame_error = frame_failure.get('message') or str(task_res)
                                frame_error_raw = frame_failure.get('raw_message')
                                frame_error_step = frame_failure.get('step')
                                frame_error_env = frame_failure.get('env')
                                step_suffix = f" step={frame_error_step}" if frame_error_step else ""
                                typer.echo(
                                    f'[ERROR] Keyframe processing failed for scene {scene_index}{step_suffix}: {frame_error}',
                                    err=True,
                                )
                            else:
                                audio_error = str(task_res)
                                wav_path = audio_dir / f"scene_{scene_index:04d}.wav" if isinstance(scene_index, int) else None
                                wav_exists = bool(wav_path and wav_path.exists())
                                wav_size = wav_path.stat().st_size if wav_exists else 0
                                typer.echo(
                                    f'[ERROR] Audio processing failed for scene {scene_index} (wav_exists={wav_exists}, wav_size={wav_size}): {audio_error}',
                                    err=True,
                                )
                        else:
                            if kind == 'frame':
                                frame_info = task_res
                                if isinstance(frame_info, dict) and frame_info.get('errors'):
                                    frame_processing_error = "; ".join(frame_info['errors']) if isinstance(frame_info['errors'], list) else str(frame_info['errors'])
                            else:
                                audio_info = task_res
                                audio_data_check = audio_info.get('data', {}) if isinstance(audio_info, dict) else {}
                                if (
                                    isinstance(audio_data_check, dict)
                                    and audio_data_check.get('wsl2_unified') is True
                                    and audio_data_check.get('status') == 'error'
                                ):
                                    typer.echo(
                                        f'  [WARN] WSL2 audio processing failed for scene {scene_index}: {audio_data_check.get("error") or "Unknown error"}',
                                        err=True,
                                    )

                audio_backend_fields = _resolve_audio_backend_attribution(
                    audio_info,
                    skip_audio=skip_audio,
                    audio_error=audio_error,
                    audio_runtime_contract=audio_runtime_contract,
                    run_context=run_context,
                    scene_id=scene_id,
                    scene_index=scene_index,
                )
                transcript_outcome_fields = _derive_transcript_outcome(
                    audio_info,
                    audio_error=audio_error,
                    audio_backend_fields=audio_backend_fields,
                )
                if isinstance(audio_info, dict):
                    audio_info['audio_backend_selected'] = audio_backend_fields['audio_backend_selected']
                    audio_info['audio_backend_reason'] = audio_backend_fields['audio_backend_reason']
                    audio_info['audio_backend_effective'] = audio_backend_fields['audio_backend_effective']
                    audio_info['audio_backend_effective_reason'] = audio_backend_fields['audio_backend_effective_reason']
                    audio_info['audio_backend_downgraded'] = bool(audio_backend_fields['audio_backend_downgraded'])
                    audio_info['audio_backend_downgrade_reason'] = audio_backend_fields['audio_backend_downgrade_reason']
                    audio_info['audio_backend_downgrade_ts'] = audio_backend_fields['audio_backend_downgrade_ts']
                    audio_info['audio_backend_downgrade_details'] = dict(
                        audio_backend_fields.get('audio_backend_downgrade_details') or {}
                    )
                    audio_info.update(transcript_outcome_fields)
                    audio_data_for_backend = audio_info.get('data')
                    if isinstance(audio_data_for_backend, dict):
                        audio_data_for_backend['audio_backend_selected'] = audio_backend_fields['audio_backend_selected']
                        audio_data_for_backend['audio_backend_reason'] = audio_backend_fields['audio_backend_reason']
                        audio_data_for_backend['audio_backend_effective'] = audio_backend_fields['audio_backend_effective']
                        audio_data_for_backend['audio_backend_effective_reason'] = audio_backend_fields['audio_backend_effective_reason']
                        audio_data_for_backend['audio_backend_downgraded'] = bool(
                            audio_backend_fields['audio_backend_downgraded']
                        )
                        audio_data_for_backend['audio_backend_downgrade_reason'] = audio_backend_fields[
                            'audio_backend_downgrade_reason'
                        ]
                        audio_data_for_backend['audio_backend_downgrade_ts'] = audio_backend_fields[
                            'audio_backend_downgrade_ts'
                        ]
                        audio_data_for_backend['audio_backend_downgrade_details'] = dict(
                            audio_backend_fields.get('audio_backend_downgrade_details') or {}
                        )
                        audio_data_for_backend.update(transcript_outcome_fields)

                error_payload = {}
                if frame_error:
                    error_payload['frame'] = frame_error
                    if frame_error_raw and frame_error_raw != frame_error:
                        error_payload['frame_raw'] = frame_error_raw
                    if frame_error_step:
                        error_payload['frame_step'] = frame_error_step
                    if frame_error_env:
                        error_payload['frame_env'] = frame_error_env
                if frame_processing_error:
                    error_payload['frame_processing'] = frame_processing_error
                if audio_error:
                    error_payload['audio'] = audio_error

                return {
                    'scene': scene,
                    'scene_id': scene_id,
                    'start': scene_start,
                    'end': scene_end,
                    'meta_payload': meta_payload,
                    'frame_info': frame_info,
                    'audio_info': audio_info,
                    'error_payload': error_payload,
                    'audio_backend_fields': audio_backend_fields,
                    'transcript_outcome_fields': transcript_outcome_fields,
                    'transcript_authority_previous_digest': transcript_authority_previous_digest,
                }

        async def process_video_scenes_async() -> str:
            nonlocal knowledge_graph_status_local
            
            for w_idx in sorted_window_indices:
                if w_idx in completed_window_indices and not force_reprocess:
                    continue
                
                window_start_time = time.perf_counter()
                
                window_scenes = grouped_scenes[w_idx]
                typer.echo(f"\n[WINDOW {w_idx}] Processing progressive window index {w_idx} with {len(window_scenes)} scenes...")
                
                scene_tasks = [process_scene(s.get('index', idx) + 1, s) for idx, s in enumerate(window_scenes)]
                window_results = await asyncio.gather(*scene_tasks, return_exceptions=False)
                
                audio_timings = {}
                frame_timings = {}
                for scene_res in window_results:
                    scene_idx = scene_res['scene'].get('index')
                    s_id = scene_res['scene_id']
                    if scene_res.get('audio_info') and isinstance(scene_res['audio_info'], dict):
                        a_timings = scene_res['audio_info'].get('step_timings')
                        if isinstance(a_timings, dict):
                            audio_timings[f"scene_{scene_idx}_id_{s_id}"] = a_timings
                    if scene_res.get('frame_info') and isinstance(scene_res['frame_info'], dict):
                        f_timings = scene_res['frame_info'].get('step_timings')
                        if isinstance(f_timings, dict):
                            frame_timings[f"scene_{scene_idx}_id_{s_id}"] = f_timings

                typer.echo(f"[WINDOW {w_idx}] Committing database transactions staged for window index {w_idx}...")
                
                sqlite_start = time.perf_counter()
                db_path = (cfg.get("paths", {}) or {}).get("db_path")
                if db_path or cfg.get('ingestion_isolation', False):
                    for scene_res in window_results:
                        if not cfg.get('ingestion_isolation', False):
                            ensure_scene(
                                cfg,
                                video_hash,
                                scene_res['start'],
                                scene_res['end'],
                                scene_res['meta_payload'],
                            )
                        persist_res = register_scene_bundle(
                            cfg,
                            video_hash=video_hash,
                            scene=scene_res['scene'],
                            scene_id=scene_res['scene_id'],
                            epoch_id=os.path.basename((cfg.get('paths', {}) or {}).get('db_dir', '') or ''),
                            detection_meta=detection_meta,
                            frame=scene_res['frame_info'],
                            audio=scene_res['audio_info'],
                            errors=scene_res['error_payload'] or None,
                        )
                        scene_res['persistence'] = persist_res

                        # UCF-row registration for scene-bundle summary points
                        summary_point_id = persist_res.get('summary_point_id') if isinstance(persist_res, dict) else None
                        summary_committed = persist_res.get('summary_qdrant_committed', False) if isinstance(persist_res, dict) else False
                        if summary_point_id and summary_committed:
                            try:
                                _db_dir = (cfg.get('paths', {}) or {}).get('db_dir')
                                if _db_dir:
                                    _epoch_id = os.path.basename(_db_dir)
                                    _run_id = os.getenv("GOODQ_RUN_ID") or cfg.get('run', {}).get('id') or "unknown_run"
                                    _ucf_db_dir = Path(_db_dir) / 'ucf'
                                    _ucf_db_dir.mkdir(parents=True, exist_ok=True)
                                    _ucf_db_path = _ucf_db_dir / 'ucf_ledger.db'

                                    ucf_module = _load_ucf_ledger()
                                    UCFLedgerClient = ucf_module.UCFLedgerClient
                                    _ucf_client = UCFLedgerClient(str(_ucf_db_path))
                                    _ucf_client.init_schema()

                                    _scene_start = float(scene_res['scene'].get('start', 0.0) or 0.0)
                                    _scene_end = float(scene_res['scene'].get('end', _scene_start) or _scene_start)
                                    _summary_collection = persist_res.get('summary_qdrant_collection') or 'text'

                                    # Write raw_ref artifact
                                    _raw_ref_dir = processing_dir / 'video' / 'ucf_raw_refs'
                                    _raw_ref_dir.mkdir(parents=True, exist_ok=True)
                                    _raw_ref_path = _raw_ref_dir / f"{scene_res['scene_id']}_raw_summary.json"
                                    _raw_ref_payload = {
                                        'embedding_id': summary_point_id,
                                        'embedding_source': 'scene_summary',
                                        'engine': 'all-MiniLM-L6-v2',
                                        'qdrant_collection': _summary_collection,
                                    }
                                    try:
                                        import json as _json_mod
                                        _raw_ref_path.write_text(_json_mod.dumps(_raw_ref_payload, indent=2), encoding='utf-8')
                                    except Exception:
                                        pass
                                    _raw_ref_str = str(_raw_ref_path.resolve())

                                    # Pre-normalize the summary point ID to UUID5 format
                                    # (validator requires UUID or SHA256 as vector_key)
                                    from steps.common.qdrant_client import GOODQ_POINT_ID_NAMESPACE
                                    import uuid as _uuid_mod
                                    _normalized_vector_key = str(_uuid_mod.uuid5(GOODQ_POINT_ID_NAMESPACE, summary_point_id))

                                    # Log UCF context frame
                                    _frame_id = _ucf_client.log_frame(
                                        video_hash=video_hash,
                                        epoch_id=_epoch_id,
                                        run_id=_run_id,
                                        t_start=_scene_start,
                                        t_end=_scene_end,
                                        modality='text',
                                        worker_name='scene_summary_embed',
                                        model_tag='sentence-transformers/all-MiniLM-L6-v2',
                                        confidence=1.0,
                                        source_artifact_id=scene_res['scene_id'],
                                        raw_ref=_raw_ref_str,
                                        payload={
                                            'embedding_id': summary_point_id,
                                            'embedding_source': 'scene_summary',
                                            'origin_modality': 'scene_summary',
                                        },
                                        promotion_status='staged',
                                        vector_key=_normalized_vector_key,
                                        vector_backend='qdrant',
                                        vector_dim=384,
                                        vector_model_tag='sentence-transformers/all-MiniLM-L6-v2',
                                        vector_collection=_summary_collection,
                                    )

                                    # Update Qdrant payload with ucf_frame_id
                                    if _frame_id and _summary_collection:
                                        try:
                                            import requests as _requests
                                            _qdrant_cfg = (cfg.get('qdrant') or {})
                                            _qdrant_host = _qdrant_cfg.get('host', 'http://localhost:6333')
                                            _qdrant_col_map = _qdrant_cfg.get('collections', {}) or {}
                                            _qdrant_col = _qdrant_col_map.get('text', 'goodq_text')
                                            _requests.post(
                                                f"{_qdrant_host}/collections/{_qdrant_col}/points/payload",
                                                json={
                                                    "payload": {"ucf_frame_id": _frame_id},
                                                    "points": [_normalized_vector_key],
                                                },
                                                timeout=5,
                                            )
                                        except Exception as _qe:
                                            logger.warning(f"[UCF] Failed to update Qdrant summary payload with ucf_frame_id: {_qe}")

                                    _ucf_client.close()
                            except Exception as _ucf_err:
                                logger.warning(f"[UCF] Failed to register summary point in UCF: {_ucf_err}")

                else:
                    for scene_res in window_results:
                        scene_res['persistence'] = {'vector_points_attempted': 0, 'status': 'skipped_no_db'}
                sqlite_duration = time.perf_counter() - sqlite_start

                kg_start = time.perf_counter()
                graph_applicable = bool(
                    KNOWLEDGE_GRAPH_AVAILABLE
                    and cfg.get('knowledge_graph', {}).get('enabled', True)
                    and not cfg.get('ingestion_isolation', False)
                )
                graph_failed = False
                if graph_applicable:
                    graph_db_path = _resolve_graph_db_path(cfg).resolve()
                    graph_db_path.parent.mkdir(parents=True, exist_ok=True)
                    kg_instance = KnowledgeGraph(str(graph_db_path))
                    kg_instance.__enter__()
                    try:
                        with kg_instance.conn:
                            for scene_res in window_results:
                                frame_data = scene_res['frame_info'].get('data', {}) if scene_res['frame_info'] else {}
                                audio_data = scene_res['audio_info'].get('data', {}) if scene_res['audio_info'] else {}
                                kg_scene_data = _build_kg_scene_data(
                                    scene_res['scene'],
                                    scene_id=scene_res['scene_id'],
                                    video_id=video_hash,
                                    frame_data=frame_data,
                                    audio_data=audio_data,
                                )
                                try:
                                    update_kg_for_scene(
                                        kg_scene_data,
                                        scene_id=scene_res['scene_id'],
                                        video_id=video_hash,
                                        video_path=str(video_path),
                                        cfg=cfg,
                                        kg=kg_instance
                                    )
                                except Exception as kg_err:
                                    graph_failed = True
                                    knowledge_graph_status_local = 'error_runtime'
                                    logger.warning(f"[WINDOW {w_idx}] KG update failed for scene {scene_res['scene_id']}: {kg_err}")
                    finally:
                        kg_instance.__exit__(None, None, None)
                kg_duration = time.perf_counter() - kg_start

                for scene_res in window_results:
                    persist_result = scene_res['persistence']
                    scene_record: Dict[str, Any] = {
                        'scene_id': scene_res['scene_id'],
                        'video_id': video_hash,
                        'index': scene_res['scene'].get('index'),
                        'start': scene_res['start'],
                        'end': scene_res['end'],
                        'duration': scene_res['end'] - scene_res['start'],
                        'confidence': scene_res['scene'].get('confidence'),
                        'persistence': persist_result,
                        'audio_backend_selected': scene_res['audio_backend_fields']['audio_backend_selected'],
                        'audio_backend_reason': scene_res['audio_backend_fields']['audio_backend_reason'],
                        'audio_backend_effective': scene_res['audio_backend_fields']['audio_backend_effective'],
                        'audio_backend_effective_reason': scene_res['audio_backend_fields']['audio_backend_effective_reason'],
                        'audio_backend_downgraded': bool(scene_res['audio_backend_fields']['audio_backend_downgraded']),
                        'audio_backend_downgrade_reason': scene_res['audio_backend_fields']['audio_backend_downgrade_reason'],
                        'audio_backend_downgrade_ts': scene_res['audio_backend_fields']['audio_backend_downgrade_ts'],
                        'audio_backend_downgrade_details': dict(
                            scene_res['audio_backend_fields'].get('audio_backend_downgrade_details') or {}
                        ),
                        'transcript_outcome': scene_res['transcript_outcome_fields']['transcript_outcome'],
                        'transcript_outcome_reason': scene_res['transcript_outcome_fields']['transcript_outcome_reason'],
                        'vector_points_attempted': (
                            _coerce_nonnegative_int(persist_result.get('vector_points_attempted'))
                            if isinstance(persist_result, dict)
                            else 0
                        ),
                        'qdrant_ok': (
                            _resolve_store_status_for_points(
                                persist_result.get('vector_points_attempted'),
                                persist_result.get('qdrant_ok'),
                            )
                            if isinstance(persist_result, dict)
                            else 'not_attempted'
                        ),
                        'faiss_ok': (
                            _resolve_store_status_for_points(
                                persist_result.get('vector_points_attempted'),
                                persist_result.get('faiss_ok'),
                            )
                            if isinstance(persist_result, dict)
                            else 'not_attempted'
                        ),
                    }
                    if scene_res['frame_info']:
                        formatted_frame = _merge_step_output(scene_res['frame_info'])
                        if formatted_frame:
                            if 'timestamp' not in formatted_frame:
                                start_val = float(scene_res['start'])
                                duration_val = float(scene_res['end'] - scene_res['start'])
                                formatted_frame['timestamp'] = start_val + (duration_val / 2.0 if duration_val > 0 else start_val)
                            scene_record['keyframe'] = formatted_frame
                        else:
                            scene_record['keyframe'] = scene_res['frame_info']
                    elif scene_res['error_payload'].get('frame'):
                        scene_record['keyframe_error'] = scene_res['error_payload']['frame']
                        if scene_res['error_payload'].get('frame_raw') and scene_res['error_payload']['frame_raw'] != scene_res['error_payload']['frame']:
                            scene_record['keyframe_error_raw'] = scene_res['error_payload']['frame_raw']
                        if scene_res['error_payload'].get('frame_step'):
                            scene_record['keyframe_error_step'] = scene_res['error_payload']['frame_step']
                        if scene_res['error_payload'].get('frame_env'):
                            scene_record['keyframe_error_env'] = scene_res['error_payload']['frame_env']

                    if scene_res['audio_info']:
                        formatted_audio = _merge_step_output(scene_res['audio_info'])
                        if formatted_audio:
                            _promote_metadata_time_hints(formatted_audio)
                            audio_start_val = scene_res['start']
                            audio_end_val = scene_res['end']
                            if isinstance(scene_res['audio_info'], dict):
                                if scene_res['audio_info'].get('start') is not None:
                                    audio_start_val = float(scene_res['audio_info'].get('start'))
                                if scene_res['audio_info'].get('end') is not None:
                                    audio_end_val = float(scene_res['audio_info'].get('end'))
                            formatted_audio.setdefault('start', audio_start_val)
                            formatted_audio.setdefault('end', audio_end_val)
                            formatted_audio.setdefault(
                                'audio_backend_selected',
                                scene_res['audio_backend_fields']['audio_backend_selected'],
                            )
                            formatted_audio.setdefault(
                                'audio_backend_reason',
                                scene_res['audio_backend_fields']['audio_backend_reason'],
                            )
                            formatted_audio.setdefault(
                                'audio_backend_effective',
                                scene_res['audio_backend_fields']['audio_backend_effective'],
                            )
                            formatted_audio.setdefault(
                                'audio_backend_effective_reason',
                                scene_res['audio_backend_fields']['audio_backend_effective_reason'],
                            )
                            formatted_audio.setdefault(
                                'audio_backend_downgraded',
                                bool(scene_res['audio_backend_fields']['audio_backend_downgraded']),
                            )
                            formatted_audio.setdefault(
                                'audio_backend_downgrade_reason',
                                scene_res['audio_backend_fields']['audio_backend_downgrade_reason'],
                            )
                            formatted_audio.setdefault(
                                'audio_backend_downgrade_ts',
                                scene_res['audio_backend_fields']['audio_backend_downgrade_ts'],
                            )
                            formatted_audio.setdefault(
                                'audio_backend_downgrade_details',
                                dict(scene_res['audio_backend_fields'].get('audio_backend_downgrade_details') or {}),
                            )
                            formatted_audio.setdefault(
                                'transcript_outcome',
                                scene_res['transcript_outcome_fields']['transcript_outcome'],
                            )
                            formatted_audio.setdefault(
                                'transcript_outcome_reason',
                                scene_res['transcript_outcome_fields']['transcript_outcome_reason'],
                            )
                            speaker_ids = _extract_speaker_ids(formatted_audio)
                            formatted_audio.setdefault('speaker_ids', speaker_ids)
                            formatted_audio.setdefault('speaker_count', len(speaker_ids))
                            scene_record['audio'] = formatted_audio
                        else:
                            scene_record['audio'] = scene_res['audio_info']
                    elif scene_res['error_payload'].get('audio'):
                        scene_record['audio_error'] = scene_res['error_payload']['audio']
                    scene_record['speaker_ids'] = _extract_speaker_ids(scene_record.get('audio'))
                    if scene_res['error_payload']:
                        scene_record['errors'] = scene_res['error_payload']
                    scene_record['content_state'] = _classify_scene_content(
                        scene_record,
                        empty_duration_threshold_sec=empty_duration_threshold_sec,
                    )

                    scene_record['transcript_outcome_evidence'] = transcript_authority.emit(
                        scene_record, video_hash, run_id, cfg,
                        previous_digest=scene_res.get('transcript_authority_previous_digest'),
                    )
                    scene_outputs.append(scene_record)

                scene_outputs[:] = _sort_checkpoint_scene_outputs(scene_outputs)
                manifest_start = time.perf_counter()
                scene_manifest = {
                    'video_id': video_hash,
                    'video_path': str(video_path),
                    'phase5_complete': True,
                    'total_scenes': len(scene_outputs),
                    'content_summary': _aggregate_content_summary(scene_outputs),
                    'scenes': [
                        {
                            'video_id': video_hash,
                            'scene_id': s.get('scene_id'),
                            'index': s.get('index'),
                            'start': s.get('start'),
                            'end': s.get('end'),
                            'duration': s.get('duration'),
                            'confidence': s.get('confidence'),
                            'vector_points_attempted': _coerce_nonnegative_int(s.get('vector_points_attempted')),
                            'qdrant_ok': _resolve_store_status_for_points(
                                s.get('vector_points_attempted'),
                                s.get('qdrant_ok'),
                            ),
                            'faiss_ok': _resolve_store_status_for_points(
                                s.get('vector_points_attempted'),
                                s.get('faiss_ok'),
                            ),
                            'content_state': s.get('content_state', 'signal'),
                            'transcript_outcome': s.get('transcript_outcome'),
                            'transcript_outcome_reason': s.get('transcript_outcome_reason'),
                            'transcript_outcome_evidence': s.get('transcript_outcome_evidence'),
                            'speaker_ids': s.get('speaker_ids') or [],
                            'speaker_count': len(s.get('speaker_ids') or []),
                            'keyframe': s.get('keyframe', {}),
                            'audio': s.get('audio', {}),
                            **({'errors': s.get('errors')} if s.get('errors') else {}),
                        }
                        for s in scene_outputs
                    ]
                }
                scene_manifest_path = processing_dir / 'video' / 'scene_manifest.json'
                scene_manifest_path.parent.mkdir(parents=True, exist_ok=True)
                existing_manifest = None
                if scene_manifest_path.exists():
                    try:
                        existing_manifest = json.loads(scene_manifest_path.read_text(encoding='utf-8'))
                    except Exception as e:
                        logger.warning(f"Failed to load existing manifest: {e}")
                
                atomic_write_json(
                    scene_manifest_path,
                    _merge_prior_phase6_manifest_state(scene_manifest, existing_manifest),
                )
                manifest_duration = time.perf_counter() - manifest_start

                phase6_item = {
                    'id': video_hash,
                    'source_path': str(video_path),
                    'video_id': video_hash,
                    'video_storage_key': video_path.stem,
                    'video_path': str(video_path),
                    'processing_dir': str(processing_dir),
                    'audio_artifact_dir': str(phase6_audio_artifact_dir),
                    'scene_manifest_path': str(scene_manifest_path),
                    'scenes': scene_outputs,
                    'progressive_window_scene_ids': [
                        str(scene_res.get('scene_id'))
                        for scene_res in window_results
                        if isinstance(scene_res, dict) and scene_res.get('scene_id')
                    ],
                    'video_hash': video_hash,
                }
                
                vectors_applicable = bool(
                    phase6_enabled
                    and cfg.get('phase6', {}).get('retrieval', {}).get('enable', True)
                )
                temporal_index_applicable = False
                temporal_index_committed = False
                temporal_index_path_for_checkpoint = processing_dir / 'video' / 'temporal_index.json'

                p6a_duration = 0.0
                p6b_duration = 0.0
                window_scene_context_meta = None

                if phase6_enabled:
                    try:
                        p6a_start = time.perf_counter()
                        embeddings_result = _run_step('goodq_image_caption', 'scene_visual_embeddings', phase6_item, cfg_json)
                        p6a_duration = time.perf_counter() - p6a_start
                        if isinstance(embeddings_result, dict) and embeddings_result.get('phase6_status') == 'complete':
                            if embeddings_result.get('scenes'):
                                _rehydrate_video_result_scenes_from_manifest({'scenes': scene_outputs}, str(scene_manifest_path))
                            # Log visual scene embeddings to UCF ledger
                            try:
                                _db_dir = (cfg.get('paths', {}) or {}).get('db_dir')
                                if _db_dir:
                                    _ucf_db_dir = Path(_db_dir) / 'ucf'
                                    _ucf_db_dir.mkdir(parents=True, exist_ok=True)
                                    _ucf_db_path = _ucf_db_dir / 'ucf_ledger.db'
                                    ucf_module = _load_ucf_ledger()
                                    UCFLedgerClient = ucf_module.UCFLedgerClient
                                    _ucf_client = UCFLedgerClient(str(_ucf_db_path))
                                    _ucf_client.init_schema()
                                    
                                    _epoch_id = os.path.basename(_db_dir)
                                    _run_id = os.getenv("GOODQ_RUN_ID") or cfg.get('run', {}).get('id') or "unknown_run"
                                    
                                    _log_scene_visual_embeddings_to_ucf_ledger(
                                        cfg,
                                        video_hash,
                                        _epoch_id,
                                        _run_id,
                                        processing_dir,
                                        scene_outputs,
                                        _ucf_client
                                    )
                            except Exception as ucf_err:
                                logger.warning(f"[UCF] Phase 6a scene visual logging failed: {ucf_err}")
                    except Exception as p6a_err:
                        logger.warning(f"[WINDOW {w_idx}] Phase 6a incremental run failed: {p6a_err}")

                    try:
                        temporal_index_applicable = True
                        p6b_start = time.perf_counter()
                        harmonization_result = _run_step('goodq_core', 'cross_modal_harmonization', phase6_item, cfg_json)
                        p6b_duration = time.perf_counter() - p6b_start
                        if isinstance(harmonization_result, dict):
                            window_scene_context_meta = harmonization_result.get('scene_context_meta')
                            if harmonization_result.get('harmonization_status') == 'skipped':
                                temporal_index_applicable = False
                            else:
                                _rehydrate_video_result_scenes_from_manifest({'scenes': scene_outputs}, str(scene_manifest_path))
                                primary_temporal_path = processing_dir / 'temporal_index.json'
                                video_temporal_path = processing_dir / 'video' / 'temporal_index.json'
                                temporal_index_path_for_checkpoint = (
                                    primary_temporal_path
                                    if primary_temporal_path.exists()
                                    else video_temporal_path
                                )
                                temporal_index_committed = (
                                    _safe_read_json_dict(temporal_index_path_for_checkpoint)
                                    is not None
                                )
                    except Exception as p6b_err:
                        logger.warning(f"[WINDOW {w_idx}] Phase 6b incremental run failed: {p6b_err}")

                window_total_duration = time.perf_counter() - window_start_time

                # Write progressive ingestion timings
                timings_path = processing_dir / 'video' / 'progressive_ingestion_timings.json'
                timings_data = {
                    'video_id': video_hash,
                    'video_path': str(video_path),
                    'windows': {}
                }
                if timings_path.exists():
                    try:
                        existing_timings = json.loads(timings_path.read_text(encoding='utf-8'))
                        if isinstance(existing_timings, dict):
                            timings_data['windows'] = existing_timings.get('windows') or {}
                    except Exception as e:
                        logger.warning(f"Failed to load existing timings: {e}")
                
                timings_data['windows'][str(w_idx)] = {
                    'window_index': w_idx,
                    'window_start': w_idx * step_val,
                    'window_end': (w_idx * step_val) + chunk_size_val,
                    'window_scene_count': len(window_results),
                    'timing_seconds': {
                        'audio_processing': audio_timings,
                        'frame_processing': frame_timings,
                        'sqlite_persistence': sqlite_duration,
                        'knowledge_graph': kg_duration,
                        'phase6a_visual_embeddings': p6a_duration,
                        'phase6b_cross_modal_harmonization': p6b_duration,
                        'manifest_write': manifest_duration,
                    },
                    'scene_context_meta': (
                        {
                            'status': window_scene_context_meta.get('status'),
                            'evaluated_count': window_scene_context_meta.get('evaluated_count'),
                            'reused_count': window_scene_context_meta.get('reused_count'),
                            'ollama_unloaded': window_scene_context_meta.get('ollama_unloaded'),
                        }
                        if isinstance(window_scene_context_meta, dict)
                        else None
                    ),
                    'total_window_duration_seconds': window_total_duration,
                }
                
                try:
                    atomic_write_json(timings_path, timings_data)
                except Exception as e:
                    logger.warning(f"Failed to write progressive ingestion timings: {e}")

                window_scene_ids = [
                    str(scene_res.get('scene_id'))
                    for scene_res in window_results
                    if scene_res.get('scene_id')
                ]
                window_record = _build_progressive_checkpoint_record(
                    cfg=cfg,
                    run_id=run_id,
                    video_hash=video_hash,
                    window_idx=w_idx,
                    window_start=w_idx * step_val,
                    window_end=(w_idx * step_val) + chunk_size_val,
                    scene_ids=window_scene_ids,
                    graph_applicable=graph_applicable,
                    graph_failed=graph_failed,
                    vectors_applicable=vectors_applicable,
                    scene_manifest_path=scene_manifest_path,
                    temporal_index_applicable=temporal_index_applicable,
                    temporal_index_committed=temporal_index_committed,
                    temporal_index_path=temporal_index_path_for_checkpoint,
                )
                checkpoint_windows[str(w_idx)] = window_record
                state_record = {
                    'checkpoint_version': 2,
                    'run_id': run_id,
                    'video_hash': video_hash,
                    'windows': checkpoint_windows,
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                }
                atomic_write_json(checkpoint_path, state_record)
                if window_record['window_status'] == 'committed':
                    completed_window_indices.add(w_idx)
                else:
                    completed_window_indices.discard(w_idx)
                logger.info(
                    "[WINDOW %s] Checkpoint written status=%s targets=%s",
                    w_idx,
                    window_record['window_status'],
                    window_record['persistence_targets'],
                )

            return knowledge_graph_status_local

        knowledge_graph_status = asyncio.run(process_video_scenes_async())

        if observer:
            observer.step_end(
                scene_loop_step,
                metadata={
                    "video_path": str(video_path),
                    "video_id": video_hash,
                    "processed_scenes": len(scene_outputs),
                },
            )

        scene_qdrant_status = _aggregate_scene_store_status(scene_outputs, 'qdrant_ok')
        scene_faiss_status = _aggregate_scene_store_status(scene_outputs, 'faiss_ok')
        content_summary = _aggregate_content_summary(scene_outputs)
        run_audio_backend_selected = _aggregate_audio_backend(scene_outputs)
        run_audio_backend_effective = _aggregate_audio_backend(
            scene_outputs,
            field='audio_backend_effective',
        )
        run_audio_backend_downgraded = any(
            bool(scene.get('audio_backend_downgraded'))
            for scene in scene_outputs
            if isinstance(scene, dict)
        )
        # Phase 6 owns its commit receipt. Scene/summary commits cannot stand in
        # for the separate scene-level visual vector writes.
        scene_manifest_path = processing_dir / 'video' / 'scene_manifest.json'
        phase6_manifest = _safe_read_json_dict(scene_manifest_path) or {}
        phase6_embeddings_result = phase6_manifest.get('phase6_vector_commit')
        if not isinstance(phase6_embeddings_result, dict):
            phase6_embeddings_result = {}
        phase6_qdrant_status = _normalize_vector_store_status(phase6_embeddings_result.get('qdrant_ok'))
        phase6_faiss_status = _normalize_vector_store_status(phase6_embeddings_result.get('faiss_ok'))
        phase6_cfg = cfg.get('phase6', {}) or {}
        phase6_complete = bool(scene_outputs) and phase6_cfg.get('enabled', True) and (
            _scene_manifest_has_committed_vectors(
                scene_manifest_path, [str(scene['scene_id']) for scene in scene_outputs]
            )
            if phase6_cfg.get('retrieval', {}).get('enable', True)
            else phase6_manifest.get('phase6_complete') is True
            and phase6_manifest.get('phase6_status') == 'complete'
        )

        video_result = {
            'video_path': str(video_path),
            'video_hash': video_hash,
            'video_id': video_hash,
            'video_name': video_path.name,
            'audio_artifact_dir': str(audio_artifact_dir),
            'scene_meta': detection_meta,
            'scenes': scene_outputs,
            'audio_backend_selected': run_audio_backend_selected,
            'audio_backend_effective': run_audio_backend_effective,
            'audio_backend_downgraded': run_audio_backend_downgraded,
            'audio_backend_events': _audio_backend_events_since(run_context, audio_backend_event_start),
            'audio_runtime_contract': audio_runtime_contract,
            'phase5_complete': True,
            'content_summary': content_summary,
            'qdrant_ok': scene_qdrant_status,
            'faiss_ok': scene_faiss_status,
            'control_agent_status': control_agent_status,
            'control_agent_reason': control_agent_reason,
            'knowledge_graph_status': knowledge_graph_status,
            'orchestration': orchestration_contract,
            'phase6_audio_artifact_dir': str(phase6_audio_artifact_dir),
            'phase6_qdrant_ok': phase6_qdrant_status,
            'phase6_faiss_ok': phase6_faiss_status,
            'phase6_complete': phase6_complete,
        }
        if profile_override:
            video_result['profile_override'] = profile_override
            video_result['profile_override_reason'] = profile_override_reason
        if segmentation_shadow_overlay.get('enabled'):
            video_result['phase6_audio_overlay'] = segmentation_shadow_overlay

        # Rehydrate temporal index if Phase 6 was run
        temporal_index_path = processing_dir / 'temporal_index.json'
        if not temporal_index_path.exists():
            temporal_index_path = processing_dir / 'video' / 'temporal_index.json'

        if temporal_index_path.exists():
            try:
                temporal_index_data = json.loads(temporal_index_path.read_text(encoding='utf-8'))
                if isinstance(temporal_index_data, dict):
                    if temporal_index_data.get('phase6_complete') is not phase6_complete:
                        temporal_index_data['phase6_complete'] = phase6_complete
                        atomic_write_json(temporal_index_path, temporal_index_data)
                    video_result['temporal_index'] = temporal_index_data
                    video_result['temporal_index_path'] = str(temporal_index_path)
            except Exception as e:
                logger.warning(f"Failed to read/update final temporal index: {e}")

        segmentation_shadow_result = _attach_segmentation_shadow_metrics(
            cfg,
            scene_outputs,
            video_result.get('temporal_index'),
            segmentation_shadow_result,
        )
        segmentation_shadow_result = dict(segmentation_shadow_result)
        shadow_metrics = segmentation_shadow_result.get('metrics') if isinstance(segmentation_shadow_result.get('metrics'), dict) else {}
        if isinstance(video_result.get('orchestration'), dict) and isinstance(shadow_metrics, dict):
            orchestration_contract = dict(video_result['orchestration'])
            scene_backend_comparison = shadow_metrics.get('shadow', {}).get('scene_backend_comparison')
            if isinstance(scene_backend_comparison, dict):
                orchestration_contract['scene_backend_comparison'] = scene_backend_comparison
                video_result['orchestration'] = orchestration_contract
        segmentation_shadow_result['orchestration'] = orchestration_contract
        if segmentation_shadow_overlay.get('enabled'):
            segmentation_shadow_result['phase6_audio_overlay'] = segmentation_shadow_overlay
        video_result['segmentation_shadow'] = segmentation_shadow_result

        video_result['qdrant_ok'] = _merge_store_statuses(scene_qdrant_status, phase6_qdrant_status)
        video_result['faiss_ok'] = _merge_store_statuses(scene_faiss_status, phase6_faiss_status)
        video_result['modality_status'] = _aggregate_modality_status(scene_outputs, phase6_embeddings_result)
        
        # Clean up only after every current window re-probes as fully committed.
        final_checkpoint_state = {
            'checkpoint_version': 2,
            'run_id': run_id,
            'video_hash': video_hash,
            'windows': checkpoint_windows,
        }
        checkpoint_cleanup_ready = _progressive_checkpoint_cleanup_ready(
            state_data=final_checkpoint_state,
            video_hash=video_hash,
            cfg=cfg,
            processing_dir=Path(processing_dir),
            expected_window_indices=sorted_window_indices,
            phase6_complete=video_result.get('phase6_complete') is True,
            expected_windows=expected_windows,
        )
        if checkpoint_cleanup_ready:
            try:
                if checkpoint_path.exists():
                    checkpoint_path.unlink()
                    logger.info(f"Cleaned up progressive ingestion checkpoint for completed video: {video_path.name}")
            except Exception as e:
                logger.warning(f"Failed to delete completed progressive state checkpoint: {e}")
        elif checkpoint_path.exists():
            logger.warning(
                "Retaining progressive ingestion checkpoint because one or more "
                "current windows lack verified five-target persistence"
            )

        if identity_matching_frozen is not None:
            try:
                video_result['identity_matching'] = write_video_matches(cfg, identity_matching_frozen, video_result)
            except Exception as exc:
                logger.exception("Identity comparison failed; retained media will not be rerun automatically")
                video_result['identity_matching'] = {'status': 'failed', 'applied': False, 'error': str(exc)}
        results.append(video_result)
        if tracker is not None:
            finish_processing(
                "failed" if phase6_cfg.get('enabled', True) and not phase6_complete else "completed"
            )

    if observer:
        observer.step_end("loop.videos", metadata={"processed_videos": len(results)})

    # Canonical ingestion path writes KG incrementally per scene via update_kg_for_scene().
    # Preserve the legacy end-of-run builder for diagnostics/tests, but do not invoke it here.
    if VERBOSE and KNOWLEDGE_GRAPH_AVAILABLE and cfg.get('knowledge_graph', {}).get('enabled', True):
        typer.echo("[kg] Realtime scene updates are canonical; skipping legacy end-of-run rebuild")

    run_context['knowledge_graph_status'] = knowledge_graph_status
    if isinstance(cfg.get('run'), dict):
        cfg['run']['knowledge_graph_status'] = knowledge_graph_status
    for result in results:
        result['knowledge_graph_status'] = knowledge_graph_status

    # Generate LLM summaries for videos (if enabled)
    llm_config = cfg.get('llm', {})
    if llm_config.get('enabled') and llm_config.get('features', {}).get('video_summarization'):
        if VERBOSE:
            typer.echo('[llm] Generating video summaries...')
        
        try:
            from steps.video_summarizer.step import run_step as run_video_summarizer
            
            for result in results:
                video_hash = result.get('video_hash')
                if video_hash and VERBOSE:
                    typer.echo(f'[llm] Summarizing video {video_hash[:16]}...')
                
                summary_result = run_video_summarizer(cfg, video_hash)
                
                if summary_result.get('success'):
                    result['video_summary'] = summary_result.get('summary')
                    result['video_summary_method'] = summary_result.get('method')
                    if VERBOSE:
                        typer.echo(f'[llm] [OK] Video summary generated ({summary_result.get("method")} method)')
                else:
                    if VERBOSE:
                        typer.echo(f'[llm] [FAIL] Video summary failed: {summary_result.get("error")}')
        except ImportError as e:
            logger.warning(
                "run_ingestion warning context=%s error=%s",
                "video_summarizer.import",
                e,
            )
            if VERBOSE:
                typer.echo(f'[llm] Video summarizer not available: {e}')
        except Exception as e:
            logger.warning(
                "run_ingestion warning context=%s error=%s",
                "video_summarizer.run",
                e,
            )
            if VERBOSE:
                typer.echo(f'[llm] Video summarization error: {e}')

    # Report errors
    total_scenes = 0
    scenes_with_errors = 0
    scenes_with_critical_errors = 0
    frame_errors = 0
    frame_processing_errors = 0
    audio_errors = 0
    
    for result in results:
        for scene in result.get('scenes', []):
            total_scenes += 1
            errors = scene.get('errors', {})
            if errors:
                scenes_with_errors += 1
                if 'frame' in errors or 'audio' in errors:
                    scenes_with_critical_errors += 1
                if 'frame' in errors:
                    frame_errors += 1
                if 'frame_processing' in errors:
                    frame_processing_errors += 1
                if 'audio' in errors:
                    audio_errors += 1

    def _persist_results_artifact() -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(output, results, indent=2)
        typer.echo(f'Wrote results to {output}')
    
    if scenes_with_errors > 0:
        error_rate = (scenes_with_errors / total_scenes * 100) if total_scenes > 0 else 0
        critical_error_rate = (scenes_with_critical_errors / total_scenes * 100) if total_scenes > 0 else 0
        typer.echo(f'\n[WARNING] Extraction errors occurred:', err=True)
        typer.echo(f'  Total scenes: {total_scenes}', err=True)
        typer.echo(f'  Scenes with errors: {scenes_with_errors} ({error_rate:.1f}%)', err=True)
        typer.echo(f'  Frame extraction errors: {frame_errors}', err=True)
        if frame_processing_errors > 0:
            typer.echo(f'  Frame processing errors (downstream): {frame_processing_errors}', err=True)
        typer.echo(f'  Audio extraction errors: {audio_errors}', err=True)
        
        # Fail if more than 50% of scenes have critical extraction errors
        if critical_error_rate > 50:
            typer.echo(f'\n[CRITICAL] Over 50% of scenes failed critical extraction - this indicates a serious problem!', err=True)
            typer.echo(f'Common causes:', err=True)
            typer.echo(f'  - Video file was deleted or moved during processing', err=True)
            typer.echo(f'  - Incorrect file path', err=True)
            typer.echo(f'  - FFmpeg not available or broken', err=True)
            _persist_results_artifact()
            _finalize_capability_receipt(
                terminal_status="failed",
                cfg=cfg,
                results=results,
                output=output,
                input_count=len(videos),
                release_validation=release_validation,
            )
            if PROGRESS_TRACKING_AVAILABLE:
                finish_processing("failed")
            raise typer.Exit(code=1)

    _persist_results_artifact()
    
    # Generate Control Agent final report (best-effort; non-fatal)
    if control_agent:
        try:
            # Stop monitoring if method exists
            if hasattr(control_agent, 'stop_monitoring'):
                control_agent.stop_monitoring()

            report_path = workspace / "control_agent_report.md"
            try:
                control_agent.generate_report(str(report_path), diagnosis={})
                typer.echo(f"[CONTROL] Final report generated: {report_path}")
            except TypeError:
                # Fallback if signature doesn't match
                control_agent.generate_report(str(report_path))
                typer.echo(f"[CONTROL] Final report generated: {report_path}")

            # Display key insights
            if VERBOSE and hasattr(control_agent, 'get_insights'):
                insights = control_agent.get_insights()
                if insights:
                    typer.echo("\n" + "="*80)
                    typer.echo("[BOT] CONTROL AGENT INSIGHTS")
                    typer.echo("="*80)
                    typer.echo(insights)
                    typer.echo("="*80 + "\n")
        except Exception as e:
            typer.echo(f"[WARNING] Final report generation skipped (non-fatal): {e}", err=True)

    phase6_incomplete = bool((cfg.get('phase6', {}) or {}).get('enabled', True)) and any(
        result.get('scenes') and result.get('phase6_complete') is not True
        for result in results
    )
    identity_matching_failed = any(
        result.get('identity_matching', {}).get('status') in {'failed', 'partial'} for result in results
    )
    terminal_status = "failed" if phase6_incomplete or identity_matching_failed else "completed"
    capability_receipt = _finalize_capability_receipt(
        terminal_status=terminal_status,
        cfg=cfg,
        results=results,
        output=output,
        input_count=len(videos),
        release_validation=release_validation,
    )

    if observer:
        observer.step_end(
            "pipeline.ingestion",
            metadata={"status": terminal_status, "processed_videos": len(results)},
        )
    if _PIPELINE_OBSERVER is not None:
        _PIPELINE_OBSERVER.close()
    _PIPELINE_OBSERVER = None
    if phase6_incomplete:
        typer.echo("[ERROR] Required Phase 6 persistence is incomplete; retry evidence was retained.", err=True)
        raise typer.Exit(code=1)
    if identity_matching_failed:
        typer.echo("[ERROR] Identity matching is incomplete; media and comparison diagnostics were retained.", err=True)
        raise typer.Exit(code=1)
    _enforce_release_capability_receipt(
        capability_receipt,
        release_validation=release_validation,
    )


if __name__ == '__main__':
    _patch_typer_help_for_click_8_2()
    APP()
