"""
Debug ingestion test - First Memory Run
"""
import sys
import os

print("="*80)
print("GOODQ4ALL - FIRST MEMORY RUN - DEBUG TEST")
print("="*80)

print("\n[1/5] Checking Python environment...")
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print(f"Current directory: {os.getcwd()}")

print("\n[2/5] Attempting imports...")
try:
    from goodq4all.pipelines.direct_ingestion import run_direct_ingestion
    print("[[SYMBOL]] Imported run_direct_ingestion")
except Exception as e:
    print(f"[[SYMBOL]] Failed to import run_direct_ingestion: {e}")
    sys.exit(1)

try:
    from goodq4all.steps.common.config_loader import load_configs
    print("[[SYMBOL]] Imported load_configs")
except Exception as e:
    print(f"[[SYMBOL]] Failed to import load_configs: {e}")
    sys.exit(1)

print("\n[3/5] Checking video file...")
video_path = r"L:\goodq4all\import_inbox\01. 1987 - 1988.mp4"
print(f"Target: {video_path}")

if os.path.exists(video_path):
    size_mb = os.path.getsize(video_path) / (1024*1024)
    print(f"[[SYMBOL]] Video file exists ({size_mb:.2f} MB)")
else:
    print("[[SYMBOL]] Video file NOT FOUND")
    sys.exit(1)

print("\n[4/5] Loading configuration...")
try:
    cfg = load_configs({})
    print(f"[[SYMBOL]] Configuration loaded")
    print(f"    Config type: {type(cfg)}")
    if hasattr(cfg, 'keys'):
        print(f"    Config keys (sample): {list(cfg.keys())[:5]}")
except Exception as e:
    print(f"[[SYMBOL]] Failed to load config: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[5/5] Running ingestion pipeline...")
print("-"*80)
try:
    result = run_direct_ingestion(video_path, cfg)
    print("-"*80)
    print("\n" + "="*80)
    print("[SYMBOL] INGESTION COMPLETED SUCCESSFULLY! [SYMBOL]")
    print("="*80)
    print(f"\nResult type: {type(result)}")
    if isinstance(result, dict):
        print(f"Result keys: {list(result.keys())}")
        if 'video_id' in result:
            print(f"Video ID: {result['video_id']}")
        if 'processing_dir' in result:
            print(f"Processing dir: {result['processing_dir']}")
except Exception as e:
    print("-"*80)
    print("\n" + "="*80)
    print("[SYMBOL] INGESTION FAILED [SYMBOL]")
    print("="*80)
    print(f"\nError: {e}")
    print("\nFull traceback:")
    import traceback
    traceback.print_exc()
    sys.exit(1)
