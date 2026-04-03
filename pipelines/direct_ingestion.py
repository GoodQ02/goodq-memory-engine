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

# Ensure goodq4all can be imported
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT.parent))

from steps.common.config_loader import load_configs

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
    
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    
    print(f"[INGEST] Starting direct ingestion for: {video_path.name}")
    print("[INGEST] Using direct Python pipeline")
    
    # The actual ingestion uses the canonical scene-based runner
    # Import and use the working scene ingestion system
    from goodq4all.cli.run_ingestion import run as scene_ingest_run
    import typer
    
    # Get processing directory from config
    processing_root = _resolve_processing_root(cfg)
    processing_root.mkdir(parents=True, exist_ok=True)
    
    # Call the existing scene ingestion runtime
    try:
        # Create a temporary directory with just this video to ensure only it gets processed
        import shutil
        temp_inbox = Path(f"logs/temp_inbox_{video_path.stem}")
        temp_inbox.mkdir(parents=True, exist_ok=True)
        
        # Symlink the video file
        temp_video = temp_inbox / video_path.name
        if temp_video.exists():
            temp_video.unlink()
        temp_video.symlink_to(video_path.absolute())
        
        try:
            scene_ingest_run(
                input_dir=temp_inbox,
                output=Path(f"logs/direct_ingest_{video_path.stem}.json"),
                workspace=processing_root,  # Use configured processing directory
                max_videos=1,  # Process only this video
                verbose=True,
            )
        finally:
            # Cleanup temp directory
            if temp_inbox.exists():
                shutil.rmtree(temp_inbox)
        
        print(f"[INGEST] [PASS] Ingestion complete for {video_path.name}")
        
        # Read the actual result JSON to get the correct video_id and paths
        output_json = Path(f"logs/direct_ingest_{video_path.stem}.json")
        actual_video_id = None
        actual_processing_dir = None
        video_hash = None
        
        if output_json.exists():
            import json
            with open(output_json, 'r') as f:
                ingestion_results = json.load(f)
                # Handle both list and dict formats
                if isinstance(ingestion_results, list) and len(ingestion_results) > 0:
                    ingestion_results = ingestion_results[0]
                
                # Extract video_id and hash from the JSON structure
                actual_video_id = ingestion_results.get('video_id')
                
                # Get the actual hash-based directory from scene data
                if 'scenes' in ingestion_results and len(ingestion_results['scenes']) > 0:
                    first_scene = ingestion_results['scenes'][0]
                    if 'raw' in first_scene and 'video_hash' in first_scene['raw']:
                        video_hash = first_scene['raw']['video_hash']
                        # The REAL processing directory uses the hash
                        actual_processing_dir = processing_root / video_hash
        
        # Fallback to stem-based ID if we couldn't read from JSON
        video_id = actual_video_id if actual_video_id else video_path.stem
        processing_dir = actual_processing_dir if actual_processing_dir else (processing_root / video_id)
        
        # Build temporal index path from actual processing location
        temporal_index_path = processing_dir / "temporal_index.json"
        if not temporal_index_path.exists():
            # Also check in metadata subdirectory
            temporal_index_path = processing_dir / "metadata" / "temporal_index.json"
        
        # Return complete result with video_id and temporal_index for downstream validation
        result = {
            "status": "success", 
            "video_path": str(video_path),
            "video_id": video_id,
            "video_name": video_path.name,
            "video_hash": video_hash,
            "processing_dir": str(processing_dir.absolute()),
            "temporal_index_path": str(temporal_index_path.absolute()) if temporal_index_path.exists() else None
        }
        
        # Optionally embed temporal index content if it exists
        if temporal_index_path.exists():
            try:
                import json
                with open(temporal_index_path, 'r') as f:
                    result["temporal_index"] = json.load(f)
            except Exception as e:
                print(f"[INGEST] Warning: Could not load temporal_index.json: {e}")
        
        return result
        
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
