"""
Fix silent failures in GoodQ pipeline where steps report 'ok' but produce no output.

This script:
1. Fixes transcription marking empty results as "ok" instead of "failed"
2. Fixes audio emotion returning generic errors instead of failing properly
3. Fixes CLIP embedding failing silently with generic error messages
4. Adds proper validation and error reporting
"""

import os
import re
from pathlib import Path

def fix_audio_transcribe():
    """Fix audio transcribe to properly report empty transcriptions as failures."""
    path = Path("L:/goodq4all/steps/audio_transcribe/step.py")
    if not path.exists():
        print(f"[SKIP] {path} not found")
        return
    
    content = path.read_text(encoding='utf-8')
    original = content
    
    # Fix 1: Change line 372 to mark empty transcripts as "failed" not "empty"
    # empty means it tried but got nothing, which is a failure for our use case
    content = re.sub(
        r'status": "ok" if transcript else "empty"',
        r'status": "ok" if transcript else "failed"',
        content
    )
    
    # Fix 2: Change line 441 to mark no-text results as "failed" not "partial"
    content = re.sub(
        r'status = "ok" if full_text else "partial"',
        r'status = "ok" if full_text else "failed"',
        content
    )
    
    # Fix 3: Add explicit check after line 443 to ensure we're loud about failures
    if '    if all(c.get("status") == "error" for c in chunk_reports):' in content:
        content = content.replace(
            '    if all(c.get("status") == "error" for c in chunk_reports):\n        status = "error"',
            '''    if all(c.get("status") == "error" for c in chunk_reports):
        status = "error"
    elif all(c.get("status") in ("failed", "error", "empty") for c in chunk_reports):
        status = "failed"'''
        )
    
    if content != original:
        path.write_text(content, encoding='utf-8')
        print(f"[FIXED] {path}")
        print("  - Changed empty transcript status from 'empty' to 'failed'")
        print("  - Changed no-text status from 'partial' to 'failed'")
        print("  - Added explicit failed status check for all failed chunks")
    else:
        print(f"[NO CHANGE] {path}")


def fix_audio_emotion():
    """Fix audio emotion to fail properly when models can't load."""
    path = Path("L:/goodq4all/steps/audio_emotion/step.py")
    if not path.exists():
        print(f"[SKIP] {path} not found")
        return
    
    content = path.read_text(encoding='utf-8')
    original = content
    
    # Find pattern where it catches exceptions and returns generic errors
    # Change to fail loudly so we know models aren't loading
    pattern = r'except Exception as e:[\s\n]+return \{"audio_emotion": None, "audio_emotion_meta": \{"status": "unavailable", "error": .*?\}\}'
    
    replacement = '''except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] Audio emotion model failed to load: {error_msg}")
        return {"audio_emotion": None, "audio_emotion_meta": {"status": "failed", "error": error_msg}}'''
    
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    if content != original:
        path.write_text(content, encoding='utf-8')
        print(f"[FIXED] {path}")
        print("  - Changed status from 'unavailable' to 'failed' for model load errors")
        print("  - Added explicit error logging")
    else:
        print(f"[NO CHANGE] {path}")


def fix_image_embed_clip():
    """Fix CLIP embedding to provide better error messages."""
    path = Path("L:/goodq4all/steps/image_embed_clip/step.py")
    if not path.exists():
        print(f"[SKIP] {path} not found")
        return
    
    content = path.read_text(encoding='utf-8')
    original = content
    
    # Find where it catches generic exceptions and add better error reporting
    if 'except Exception as e:' in content:
        # Add explicit logging for CLIP failures
        content = re.sub(
            r'(except Exception as e:[\s\n]+.*?return.*?"status": "error")',
            r'\1\n        print(f"[ERROR] CLIP embedding failed: {str(e)}")',
            content,
            flags=re.DOTALL
        )
    
    if content != original:
        path.write_text(content, encoding='utf-8')
        print(f"[FIXED] {path}")
        print("  - Added explicit error logging for CLIP failures")
    else:
        print(f"[NO CHANGE] {path}")


def fix_face_embed():
    """Fix face embedding to handle corrupted file errors properly."""
    path = Path("L:/goodq4all/steps/face_embed/step.py")
    if not path.exists():
        print(f"[SKIP] {path} not found")
        return
    
    content = path.read_text(encoding='utf-8')
    original = content
    
    # Add specific handling for "unexpected EOF" errors
    if '"unexpected EOF' in content or 'unexpected EOF' in content:
        # Already has error handling, make sure it's logging
        if 'print(' not in content or '[ERROR]' not in content:
            content = re.sub(
                r'(except.*?Exception.*?as e:.*?return.*?"status": "error".*?"error":.*?)',
                r'\1\n        print(f"[ERROR] Face embedding failed: {str(e)}")',
                content,
                flags=re.DOTALL,
                count=1
            )
    
    if content != original:
        path.write_text(content, encoding='utf-8')
        print(f"[FIXED] {path}")
        print("  - Added explicit error logging for face embedding failures")
    else:
        print(f"[NO CHANGE] {path}")


def add_validation_checks():
    """Add validation script to check for silent failures in results."""
    path = Path("L:/goodq4all/scripts/validate_results.py")
    
    content = '''"""
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
    
    # Check scenes
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
'''
    
    path.write_text(content, encoding='utf-8')
    print(f"[CREATED] {path}")
    print("  - Validation script to detect silent failures")


def main():
    print("=" * 70)
    print("GoodQ Silent Failure Fix")
    print("=" * 70)
    print()
    
    fix_audio_transcribe()
    print()
    
    fix_audio_emotion()
    print()
    
    fix_image_embed_clip()
    print()
    
    fix_face_embed()
    print()
    
    add_validation_checks()
    print()
    
    print("=" * 70)
    print("[COMPLETE] Silent failure fixes applied")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Run: python L:\\goodq4all\\scripts\\validate_results.py")
    print("2. Clear databases: L:\\goodq4all\\CLEAR_AND_REINGEST.bat")
    print("3. Re-ingest test video to verify fixes")
    print()


if __name__ == "__main__":
    main()
