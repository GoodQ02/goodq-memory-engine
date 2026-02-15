"""
Test audio diarization chunking optimization
"""
import os
import sys
import time
import json

# Add project to path
sys.path.insert(0, r"L:\goodq4all")

from steps.audio_diarize.step import audio_diarize
import yaml


def load_config():
    config_path = r"L:\goodq4all\config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def test_diarization_chunking():
    print("=" * 80)
    print("AUDIO DIARIZATION CHUNKING TEST")
    print("=" * 80)
    
    cfg = load_config()
    print("\n[OK] Config loaded")
    
    token = os.getenv("PYANNOTE_TOKEN") or os.getenv("HF_TOKEN")
    if not token:
        print("\n[ERROR] No PyAnnote/HuggingFace token found")
        return False
    
    print("[OK] PyAnnote token found")
    
    test_files = [
        r"L:\goodq4all\import_inbox\01. 1987 - 1988.mp4",
        r"L:\_DATA\FAMILY_FEAST\01. 1987 - 1988.mp4",
        r"L:\goodq4all\samples\ingestion\sample.mp4",
    ]
    
    test_path = None
    for path in test_files:
        if os.path.isfile(path):
            test_path = path
            break
    
    if not test_path:
        print("\n[ERROR] No test video found")
        return False
    
    print(f"[OK] Test file: {os.path.basename(test_path)}")
    print(f"   Size: {os.path.getsize(test_path) / (1024**3):.2f}GB")
    
    item = {"source_path": test_path}
    
    print("\n" + "=" * 80)
    print("TEST: Chunked Diarization (10min chunks)")
    print("=" * 80)
    
    start_time = time.time()
    result = audio_diarize(item, cfg)
    elapsed = time.time() - start_time
    
    print(f"\nTime: {elapsed:.1f}s ({elapsed/60:.1f}min)")
    print(f"Status: {result.get('diarize_meta', {}).get('status')}")
    
    if result.get("diarization"):
        segments = result["diarization"]
        meta = result.get("diarize_meta", {})
        print(f"[OK] Segments: {len(segments)}")
        print(f"[OK] Speakers: {meta.get('speaker_count', 'unknown')}")
        print(f"[OK] Chunked: {meta.get('chunked', False)}")
        print(f"[OK] Chunks: {meta.get('chunk_count', 1)}")
        
        print("\nFirst 5 segments:")
        for seg in segments[:5]:
            print(f"  {seg['start']:.1f}s - {seg['end']:.1f}s: {seg['speaker']}")
        
        print("\n[OK] TEST COMPLETE")
        return True
    else:
        print(f"[ERROR] No diarization result")
        print(f"   Error: {result.get('diarize_meta', {}).get('error', 'unknown')}")
        return False


if __name__ == "__main__":
    try:
        success = test_diarization_chunking()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
