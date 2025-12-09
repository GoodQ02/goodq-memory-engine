"""
Direct Python ingestion pipeline for GoodQ4All.
NO ZenML. Pure Python sequential execution.

This is the production ingestion system.
"""
from __future__ import annotations
from typing import Any, Dict
from pathlib import Path
import sys

# Ensure goodq4all can be imported
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT.parent))

from steps.common.config_loader import load_configs


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
    print(f"[INGEST] Using pure Python pipeline (NO ZenML)")
    
    # The actual ingestion uses the scene-based runner which is already ZenML-free
    # Import and use the working scene ingestion system
    from goodq4all.cli.run_ingestion import run as scene_ingest_run
    import typer
    
    # Call the existing scene ingestion (which works without ZenML)
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
                workspace=Path(f"logs/direct_ingest_workspace"),
                max_videos=1,  # Process only this video
                verbose=True,
            )
        finally:
            # Cleanup temp directory
            if temp_inbox.exists():
                shutil.rmtree(temp_inbox)
        
        print(f"[INGEST] ✅ Ingestion complete for {video_path.name}")
        
        # Generate video_id (same logic as scene ingestion)
        video_id = video_path.stem
        processing_root = Path(cfg.get("paths", {}).get("processing_root", "L:/_DATA/GoodQ_Data/processing"))
        processing_dir = processing_root / video_id
        
        # Build temporal index path
        temporal_index_path = processing_dir / "metadata" / "temporal_index.json"
        
        # Return complete result with video_id and temporal_index for downstream validation
        result = {
            "status": "success", 
            "video_path": str(video_path),
            "video_id": video_id,
            "video_name": video_path.name,
            "processing_dir": str(processing_dir),
            "temporal_index_path": str(temporal_index_path) if temporal_index_path.exists() else None
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
        print(f"[INGEST] ❌ Ingestion failed: {e}")
        raise


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python direct_ingestion.py <video_path>")
        sys.exit(1)
    
    video_path = sys.argv[1]
    result = run_direct_ingestion(video_path)
    print(f"Result: {result}")
