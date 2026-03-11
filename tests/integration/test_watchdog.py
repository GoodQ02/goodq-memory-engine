#!/usr/bin/env python3
"""
Test script for watchdog functionality
Tests file detection and classification without actual processing
"""

import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.watchdog import WatchdogProcessor, FileState

def test_file_classification():
    """Test file type detection"""
    print("=" * 60)
    print("Testing File Classification")
    print("=" * 60)
    
    watchdog = WatchdogProcessor()
    
    test_files = [
        "video.mp4",
        "video.avi",
        "audio.mp3",
        "audio.wav",
        "image.jpg",
        "image.png",
        "document.pdf",
        "document.txt",
        "unknown.xyz"
    ]
    
    for filename in test_files:
        path = Path(filename)
        file_type = watchdog.get_file_type(path)
        print(f"  {filename:20} → {file_type or 'UNSUPPORTED'}")
    
    print()

def test_file_scanning():
    """Test directory scanning"""
    print("=" * 60)
    print("Testing Directory Scanning")
    print("=" * 60)
    
    watchdog = WatchdogProcessor()
    
    print(f"Watch directory: {watchdog.watch_dir}")
    print(f"Exists: {watchdog.watch_dir.exists()}")
    print()
    
    if watchdog.watch_dir.exists():
        files = watchdog.scan_directory()
        print(f"Found {len(files)} supported file(s):")
        for f in files:
            file_type = watchdog.get_file_type(f)
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"  [{file_type:8}] {f.name} ({size_mb:.2f} MB)")
    else:
        print("  [WARNING] Watch directory does not exist!")
    
    print()

def test_registry():
    """Test processed file registry"""
    print("=" * 60)
    print("Testing Processed File Registry")
    print("=" * 60)
    
    watchdog = WatchdogProcessor()
    
    print(f"State file: {watchdog.registry.state_file}")
    print(f"Exists: {watchdog.registry.state_file.exists()}")
    print(f"Processed files: {len(watchdog.registry.processed)}")
    
    if watchdog.registry.processed:
        print("\nRecent processed files:")
        for i, (hash_val, info) in enumerate(list(watchdog.registry.processed.items())[-5:]):
            print(f"  {i+1}. {info['original_name']:30} [{info['status']}] {info['timestamp']}")
    
    print()

def test_file_stability():
    """Test file stability detection"""
    print("=" * 60)
    print("Testing File Stability Detection")
    print("=" * 60)
    
    watchdog = WatchdogProcessor()
    files = watchdog.scan_directory()
    
    if files:
        test_file = files[0]
        print(f"Testing with: {test_file.name}")
        
        state = FileState(test_file)
        print(f"  Initial size: {state.size} bytes")
        print(f"  Initial mtime: {state.mtime}")
        
        for i in range(5):
            time.sleep(1)
            is_stable = state.is_stable()
            print(f"  Check {i+1}: {'STABLE' if is_stable else 'waiting...'}")
            if is_stable:
                break
    else:
        print("  [WARNING] No files to test")
    
    print()

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("GoodQ Watchdog Test Suite")
    print("=" * 60 + "\n")
    
    try:
        test_file_classification()
        test_file_scanning()
        test_registry()
        test_file_stability()
        
        print("=" * 60)
        print("All tests completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
