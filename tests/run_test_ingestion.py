"""
Phase 9.6 Live Ingestion Test - Fixed Python Path
"""
import sys
import os

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now import goodq4all modules
from pipelines.direct_ingestion import run_direct_ingestion
from steps.common.config_loader import load_configs
import json
from pathlib import Path

def main():
    # Load config
    cfg = load_configs({})
    
    # Find test video
    import_inbox = Path(r"L:\goodq4all\import_inbox")
    videos = list(import_inbox.glob("*.mp4")) + list(import_inbox.glob("*.mov"))
    
    if not videos:
        print("ERROR: No videos found in import_inbox")
        return
    
    # Select smallest video
    test_video = min(videos, key=lambda p: p.stat().st_size)
    print(f"\n{'='*80}")
    print(f"PHASE 9.6 LIVE INGESTION TEST")
    print(f"{'='*80}")
    print(f"Test video: {test_video.name}")
    print(f"Size: {test_video.stat().st_size / (1024*1024):.2f} MB")
    print(f"{'='*80}\n")
    
    # Run ingestion
    try:
        result = run_direct_ingestion(str(test_video), cfg)
        print(f"\n{'='*80}")
        print("INGESTION COMPLETED SUCCESSFULLY")
        print(f"{'='*80}\n")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"\n{'='*80}")
        print("INGESTION FAILED")
        print(f"{'='*80}\n")
        import traceback
        traceback.print_exc()
        return

if __name__ == "__main__":
    main()
