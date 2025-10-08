#!/usr/bin/env python3
"""
Simple watchdog test - copy sample.mp4 and watch it get detected
"""

import sys
import time
import shutil
from pathlib import Path
from datetime import datetime

WATCH_DIR = Path("L:/zenml_project/import_inbox")
TEST_SOURCE = WATCH_DIR / "sample.mp4"
TEST_TARGET = WATCH_DIR / f"test_copy_{datetime.now().strftime('%H%M%S')}.mp4"

def main():
    print("=" * 60)
    print("Simple Watchdog Detection Test")
    print("=" * 60)
    
    if not TEST_SOURCE.exists():
        print(f"[ERROR] Source file not found: {TEST_SOURCE}")
        return 1
    
    print(f"\nSource: {TEST_SOURCE.name}")
    print(f"Target: {TEST_TARGET.name}")
    print(f"Watch dir: {WATCH_DIR}")
    
    # Show current files
    files_before = list(WATCH_DIR.glob("*.mp4"))
    print(f"\nFiles before: {len(files_before)}")
    
    # Copy file
    print(f"\nCopying {TEST_SOURCE.name} to {TEST_TARGET.name}...")
    shutil.copy2(TEST_SOURCE, TEST_TARGET)
    print("✓ File copied")
    
    # Show new files
    files_after = list(WATCH_DIR.glob("*.mp4"))
    print(f"\nFiles after: {len(files_after)}")
    
    print("\n" + "=" * 60)
    print("Test file created successfully!")
    print("Now start the watchdog to process it:")
    print("  START_WATCHDOG.bat")
    print("=" * 60)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
