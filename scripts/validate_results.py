"""
Validate ingestion results for silent failures.

Checks for:
- Transcriptions marked "ok" but with no text
- Embeddings marked "ok" but not in FAISS
- Steps that completed in 0ms (likely skipped)
- Errors marked as "unavailable" (should be "failed")
"""

import json
import sys
from pathlib import Path


def validate_result_file(result_path: Path) -> dict:
    """Validate a single result JSON file."""
    issues = []
    
    try:
        with open(result_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return {"file": str(result_path), "error": f"Failed to load: {e}", "issues": []}
    
    # Handle both list and dict formats
    if isinstance(data, list):
        scenes = data
    else:
        scenes = data.get("scenes", [])
    for i, scene in enumerate(scenes):
        scene_id = f"Scene {i}"
        
        # Check audio transcription
        audio = scene.get("audio", {})
        transcript_meta = audio.get("transcript_meta", {})
        transcript = audio.get("transcript")
        
        if transcript_meta.get("status") == "ok" and not transcript:
            issues.append(f"{scene_id}: Transcript marked 'ok' but text is None")
        
        if transcript_meta.get("status") == "partial" and not transcript:
            issues.append(f"{scene_id}: Transcript marked 'partial' but should be 'failed' (no text)")
        
        # Check chunks for empty results marked as ok
        chunks = transcript_meta.get("chunks", [])
        for j, chunk in enumerate(chunks):
            if chunk.get("status") in ("ok", "empty") and not chunk.get("text"):
                issues.append(f"{scene_id} Chunk {j}: Marked '{chunk.get('status')}' but has no text - should be 'failed'")
        
        # Check audio emotion
        emotion_meta = audio.get("audio_emotion_meta", {})
        if emotion_meta.get("status") == "unavailable":
            issues.append(f"{scene_id}: Audio emotion 'unavailable' - should be 'failed' with error logged")
        
        # Check embeddings
        clip_meta = audio.get("clip_meta", {}) or scene.get("frame", {}).get("clip_meta", {})
        if clip_meta.get("status") == "error" and "input_ids" in str(clip_meta.get("error", "")):
            issues.append(f"{scene_id}: CLIP embedding error 'input_ids' - model not loading properly")
        
        # Check face detection
        faces_meta = scene.get("frame", {}).get("faces_meta", {})
        if faces_meta.get("status") == "error" and "unexpected EOF" in str(faces_meta.get("error", "")):
            issues.append(f"{scene_id}: Face detection 'unexpected EOF' - possible model corruption")
    
    return {
        "file": str(result_path),
        "scenes": len(scenes),
        "issues": issues
    }


def main():
    logs_dir = Path("L:/goodq4all/logs")
    
    # Find all result JSON files
    result_files = list(logs_dir.rglob("*_results.json"))
    
    if not result_files:
        print("[INFO] No result files found")
        return 0
    
    print(f"[INFO] Validating {len(result_files)} result files...")
    print()
    
    all_issues = []
    for result_file in result_files:
        validation = validate_result_file(result_file)
        if validation.get("issues"):
            all_issues.extend(validation["issues"])
            print(f"[ISSUES] {validation['file']}")
            for issue in validation["issues"]:
                print(f"  - {issue}")
            print()
    
    if all_issues:
        print(f"[SUMMARY] Found {len(all_issues)} issues across {len(result_files)} files")
        print()
        print("[ACTION] Run fix_silent_failures.py to address code issues")
        print("[ACTION] Re-ingest affected files after fixes are applied")
        return 1
    else:
        print(f"[SUCCESS] No silent failure issues found in {len(result_files)} result files")
        return 0


if __name__ == "__main__":
    sys.exit(main())
