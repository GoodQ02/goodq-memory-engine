#!/usr/bin/env python3
"""
WSL Audio Output Promotion Script
Copies validated audio results from WSL output directory to Windows canonical store.
"""
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys

# Paths
WSL_OUTPUT_DIR = Path("/mnt/l/goodq4all/logs/scene_ingest")  # WSL can access Windows via /mnt
REPO_ROOT = Path(__file__).resolve().parents[1]
_data_root_env = os.environ.get("GOODQ_DATA_ROOT")
if _data_root_env:
    WINDOWS_DATA_ROOT = Path(_data_root_env) / "GoodQ_Data" / "processing"
else:
    WINDOWS_DATA_ROOT = REPO_ROOT / "processing"

def find_wsl_audio_results():
    """Find all result.json files in WSL output"""
    # Access via \\wsl$\<distro>\<workspace>\output from Windows
    wsl_distro = os.environ.get("GOODQ_WSL_DISTRO", "Ubuntu")
    wsl_user = (
        os.environ.get("GOODQ_WSL_USER")
        or os.environ.get("USERNAME")
        or os.environ.get("USER")
        or os.environ.get("LOGNAME")
        or "user"
    )
    wsl_workspace = os.environ.get("GOODQ_WSL_WORKSPACE", f"/home/{wsl_user}/goodq_audio")
    workspace_unc = wsl_workspace.strip("/").replace("/", "\\")
    wsl_base = Path(f"\\\\wsl$\\{wsl_distro}\\{workspace_unc}\\output")
    if wsl_base.exists():
        return list(wsl_base.glob("**/result.json"))
    return []

def find_scene_audio_in_logs():
    """Find audio results written by the pipeline in logs/scene_ingest"""
    log_base = REPO_ROOT / "logs" / "scene_ingest"
    results = []
    
    for video_dir in log_base.glob("*"):
        if not video_dir.is_dir():
            continue
            
        audio_dir = video_dir / "audio"
        if audio_dir.exists():
            # Look for result.json or scene_*.json files
            results.extend(audio_dir.glob("*.json"))
    
    return results

def promote_audio_result(source_json: Path, video_id: str, scene_id: str):
    """Copy audio result to canonical processing directory"""
    
    # Target: <processing_root>/<video_id>/audio/scene_<scene_id>.json
    target_dir = WINDOWS_DATA_ROOT / video_id / "audio"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    target_file = target_dir / f"scene_{scene_id}.json"
    
    # Copy with metadata preservation
    shutil.copy2(source_json, target_file)
    
    print(f"✓ Promoted: {source_json.name} → {target_file}")
    return target_file

def extract_metadata_from_path(json_path: Path):
    """Extract video_id and scene_id from file path"""
    # Example: logs/scene_ingest/02. 1988 - 1989/audio/scene_0019.wav
    parts = json_path.parts
    
    video_name = None
    scene_id = None
    
    # Find video directory name
    for i, part in enumerate(parts):
        if part == "scene_ingest" and i + 1 < len(parts):
            video_name = parts[i + 1]
            break
    
    # Extract scene number from filename
    if "scene_" in json_path.stem:
        scene_id = json_path.stem.split("scene_")[1].split(".")[0]
    
    return video_name, scene_id

def main():
    print("=" * 60)
    print("  WSL AUDIO PROMOTION")
    print("=" * 60)
    
    # Find all audio results from logs
    log_results = find_scene_audio_in_logs()
    
    print(f"\n[Found {len(log_results)} audio results in logs]")
    
    promoted_count = 0
    
    for result_file in log_results:
        try:
            video_name, scene_id = extract_metadata_from_path(result_file)
            
            if not video_name or not scene_id:
                print(f"⚠ Skipping {result_file.name}: Could not extract metadata")
                continue
            
            # Use video name as video_id (sanitize if needed)
            video_id = video_name.replace(" ", "_").replace(".", "")
            
            promote_audio_result(result_file, video_id, scene_id)
            promoted_count += 1
            
        except Exception as e:
            print(f"✗ Error promoting {result_file.name}: {e}")
    
    print(f"\n✓ Promoted {promoted_count}/{len(log_results)} audio results")
    print(f"  Target: {WINDOWS_DATA_ROOT}")

if __name__ == "__main__":
    main()
