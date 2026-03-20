"""
Quick test of direct ingestion without watchdog
"""
import sys
from pathlib import Path

# Ensure repo is in path
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from pipelines.direct_ingestion import run_direct_ingestion
from steps.common.config_loader import load_configs

# Use sample video
video_path = r"L:\goodq4all\import_inbox\sample.mp4"

print(f"Testing direct ingestion on: {video_path}")
print("="*80)

cfg = load_configs({})
result = run_direct_ingestion(video_path, cfg)

print("="*80)
print(f"Result: {result}")
print("\nIngestion complete!")
