#!/usr/bin/env python3
"""Quick test of sample.mp4 processing"""
import sys
from pathlib import Path

# Add repo to path
sys.path.insert(0, str(Path(__file__).parent))

from cli.run_ingestion import run
import typer

if __name__ == "__main__":
    # Use sample.mp4 if it exists in import_inbox
    sample = Path("L:/goodq4all/import_inbox/sample.mp4")
    if not sample.exists():
        print(f"ERROR: {sample} not found!")
        sys.exit(1)
    
    print(f"Testing with {sample.name} ({sample.stat().st_size / 1024:.1f} KB)")
    print("=" * 80)
    
    # Run ingestion with verbose output
    app = typer.Typer()
    app.command()(run)
    app(
        [
            "--input-dir", "L:/goodq4all/import_inbox",
            "--workspace", "L:/goodq4all/logs/test_sample",
            "--output", "L:/goodq4all/logs/test_sample_results.json",
            "--force",
            "--verbose",
            "--step-timeout", "300",  # 5 minute timeout per step
        ],
        standalone_mode=False,
    )
