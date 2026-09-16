"""
Direct Python ingestion pipeline for GoodQ4All.
Pure Python sequential execution.

This is the production ingestion system.
"""
from __future__ import annotations
from typing import Any, Dict
from pathlib import Path
import sys
import os
import logging
import copy
import json
import uuid
import typer

# Ensure goodq4all and local modules can be imported
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT.parent))

from steps.common.config_loader import get_runtime_paths, load_configs

logger = logging.getLogger(__name__)
_PROCESSING_FALLBACK_WARNED = False


def _resolve_processing_root(cfg: Dict[str, Any]) -> Path:
    global _PROCESSING_FALLBACK_WARNED
    paths_cfg = (cfg.get("paths") or {}) if isinstance(cfg, dict) else {}
    processing = paths_cfg.get("processing")
    if processing:
        return Path(processing)

    data_root = paths_cfg.get("data_root")
    if data_root:
        if not _PROCESSING_FALLBACK_WARNED:
            logger.warning(
                "direct_ingestion path fallback used path_key=%s derived_from=%s",
                "paths.processing",
                "paths.data_root",
            )
            _PROCESSING_FALLBACK_WARNED = True
        return Path(data_root) / "processing"

    host_cfg = (cfg.get("host") or {}) if isinstance(cfg, dict) else {}
    base_root = host_cfg.get("data_root") or os.environ.get("GOODQ_DATA_ROOT")
    if base_root:
        if not _PROCESSING_FALLBACK_WARNED:
            logger.warning(
                "direct_ingestion path fallback used path_key=%s derived_from=%s",
                "paths.processing",
                "host.data_root_or_env",
            )
            _PROCESSING_FALLBACK_WARNED = True
        return Path(base_root) / "GoodQ_Data" / "processing"

    if not _PROCESSING_FALLBACK_WARNED:
        logger.warning(
            "direct_ingestion path fallback used path_key=%s derived_from=%s",
            "paths.processing",
            "cwd",
        )
        _PROCESSING_FALLBACK_WARNED = True
    return Path.cwd() / "processing"


def run_direct_ingestion(video_path: str | Path, cfg: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Run the full GoodQ4All ingestion pipeline in pure Python.
    
    Args:
        video_path: Path to video file to ingest
        cfg: Optional configuration dict. If None, loads from configs/
    
    Returns:
        Dict containing final enriched metadata for the video
    """
    if cfg is None:
        cfg = load_configs({})
    cfg = copy.deepcopy(cfg)
    
    video_path = Path(video_path).resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    
    print(f"[INGEST] Starting direct ingestion for: {video_path.name}")
    print("[INGEST] Using direct Python pipeline")
    
    # The actual ingestion uses the canonical scene-based runner
    # Import and use the working scene ingestion system
    try:
        from cli.run_ingestion import run_with_config as scene_ingest_run, _compute_sha256
    except ModuleNotFoundError as e:
        if e.name in {'cli', 'cli.run_ingestion'}:
            from goodq4all.cli.run_ingestion import run_with_config as scene_ingest_run, _compute_sha256
        else:
            raise
    
    # Get processing directory from config
    processing_root = _resolve_processing_root(cfg)
    processing_root.mkdir(parents=True, exist_ok=True)
    
    # Call the existing scene ingestion runtime
    try:
        logs_dir = Path(get_runtime_paths(cfg, "log_dir", require_canonical=False)["log_dir"]).resolve()
        logs_dir.mkdir(parents=True, exist_ok=True)
        output_json = logs_dir / f"direct_ingest_{uuid.uuid4().hex}.json"
        expected_hash = _compute_sha256(video_path)
        chunk_size = cfg.get("progressive_chunk_size", 300.0)
        chunk_overlap = cfg.get("progressive_chunk_overlap", 10.0)
        scene_ingest_run(
            cfg=cfg,
            input_file=video_path,
            output=output_json,
            workspace=processing_root,
            max_videos=1,
            verbose=True,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        # Only this invocation's result can establish successful handoff.
        try:
            ingestion_results = json.loads(output_json.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RuntimeError("direct_ingestion_result_missing_or_invalid") from exc
        if isinstance(ingestion_results, list) and len(ingestion_results) == 1:
            ingestion_results = ingestion_results[0]
        if not isinstance(ingestion_results, dict) or not ingestion_results:
            raise RuntimeError("direct_ingestion_result_requires_one_video")
        if (
            ingestion_results.get("video_hash") != expected_hash
            or ingestion_results.get("video_id") != expected_hash
        ):
            raise RuntimeError("direct_ingestion_result_content_mismatch")

        index_value = ingestion_results.get("temporal_index_path")
        temporal_index_path = Path(index_value).resolve() if index_value else None
        processing_dir = temporal_index_path.parent if temporal_index_path else processing_root / video_path.stem
        result = {
            "status": "success",
            "video_path": str(video_path),
            "video_id": expected_hash,
            "video_name": video_path.name,
            "video_hash": expected_hash,
            "processing_dir": str(processing_dir.absolute()),
            "temporal_index_path": str(temporal_index_path) if temporal_index_path else None,
            "result_path": str(output_json),
        }

        if temporal_index_path is not None:
            try:
                result["temporal_index"] = json.loads(temporal_index_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise RuntimeError("direct_ingestion_result_temporal_index_unreadable") from exc

        print(f"[INGEST] [PASS] Ingestion complete for {video_path.name}")
        return result
        
    except typer.Exit as e:
        message = f"direct_ingestion_runner_failed exit_code={e.exit_code}"
        print(f"[INGEST] [FAIL] Ingestion failed: {message}")
        raise RuntimeError(message) from e
    except Exception as e:
        print(f"[INGEST] [FAIL] Ingestion failed: {e}")
        raise


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python direct_ingestion.py <video_path>")
        sys.exit(1)
    
    video_path = sys.argv[1]
    result = run_direct_ingestion(video_path)
    print(f"Result: {result}")
