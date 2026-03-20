"""
Simple ingestion test for GoodQ4All Phase 9.9
Tests the direct ingestion pipeline on a sample video
"""
import sys
import os

# Add repo root to path
sys.path.insert(0, r'L:\goodq4all')

print("[TEST] Starting ingestion test...")
print(f"[TEST] Python path: {sys.path[:3]}")

# Import required modules
try:
    from pipelines.direct_ingestion import run_direct_ingestion
    print("[TEST] [SYMBOL] direct_ingestion imported")
except ImportError as e:
    print(f"[TEST] [SYMBOL] Failed to import direct_ingestion: {e}")
    sys.exit(1)

try:
    from steps.common.config_loader import load_configs
    print("[TEST] [SYMBOL] config_loader imported")
except ImportError as e:
    print(f"[TEST] [SYMBOL] Failed to import config_loader: {e}")
    sys.exit(1)

# Load config
try:
    cfg = load_configs({})
    print("[TEST] [SYMBOL] Config loaded")
except Exception as e:
    print(f"[TEST] [SYMBOL] Failed to load config: {e}")
    sys.exit(1)

# Set test video
test_video = r"L:\goodq4all\import_inbox\01. 1987 - 1988.mp4"

if not os.path.exists(test_video):
    print(f"[TEST] [SYMBOL] Video not found: {test_video}")
    sys.exit(1)

print(f"[TEST] [SYMBOL] Test video found: {test_video}")
print(f"[TEST] Video size: {os.path.getsize(test_video) / (1024*1024):.2f} MB")

# Run ingestion
print("\n[TEST] Starting full ingestion pipeline...")
print("=" * 80)

try:
    result = run_direct_ingestion(test_video, cfg)
    print("=" * 80)
    print("[TEST] [SYMBOL] INGESTION COMPLETED SUCCESSFULLY")
    print(f"[TEST] Result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
except Exception as e:
    print("=" * 80)
    print(f"[TEST] [SYMBOL] INGESTION FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[TEST] Test complete!")
