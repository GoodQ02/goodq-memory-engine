"""
Quick script to extract a test frame from video for vision testing
"""

import subprocess
import sys
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VIDEO_EXTENSIONS = ("*.mp4", "*.avi", "*.mov", "*.mkv")


def _candidate_video_locations():
    direct_file = os.environ.get("GOODQ_TEST_VIDEO")
    if direct_file:
        yield Path(direct_file)

    for env_name in ("GOODQ_TEST_VIDEO_DIR", "GOODQ_IMPORT_INBOX"):
        value = os.environ.get(env_name)
        if value:
            yield Path(value)

    data_root = os.environ.get("GOODQ_DATA_ROOT")
    if data_root:
        yield Path(data_root) / "GoodQ_Data" / "processing"

    yield REPO_ROOT / "import_inbox"
    yield REPO_ROOT / "samples" / "ingestion"


def extract_frame():
    """Extract a single frame from the first available video"""
    
    # Check for videos
    video_files = []
    checked_locations = []
    for location in _candidate_video_locations():
        checked_locations.append(location)
        if location.is_file():
            video_files.append(location)
        elif location.is_dir():
            for pattern in VIDEO_EXTENSIONS:
                video_files.extend(sorted(location.glob(pattern)))
    
    if not video_files:
        print("[FAIL] No video files found in:")
        for location in checked_locations:
            print(f"   {location}")
        print("\nProvide a video with GOODQ_TEST_VIDEO, GOODQ_TEST_VIDEO_DIR,")
        print("GOODQ_IMPORT_INBOX, GOODQ_DATA_ROOT, or samples/ingestion.")
        return False
    
    # Use first video
    video_path = video_files[0]
    print(f"[VIDEO] Using video: {video_path.name}")
    
    # Output path
    output_dir = Path(os.environ.get("GOODQ_TEST_FRAME_DIR", REPO_ROOT / "test_data"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "sample_frame.jpg"
    
    # Check if ffmpeg is available
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except:
        print("[FAIL] FFmpeg not found. Please install FFmpeg:")
        print("   winget install ffmpeg")
        return False
    
    # Extract frame at 10 seconds
    print(f"[TIMER]  Extracting frame at 10 seconds...")
    cmd = [
        "ffmpeg",
        "-ss", "10",  # Seek to 10 seconds
        "-i", str(video_path),
        "-vframes", "1",  # Extract 1 frame
        "-q:v", "2",  # High quality
        "-y",  # Overwrite
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if output_path.exists():
            print(f"[OK] Frame extracted successfully!")
            print(f"[SYMBOL] Saved to: {output_path}")
            print(f"[SYMBOL] File size: {output_path.stat().st_size / 1024:.1f} KB")
            return True
        else:
            print("[FAIL] Frame extraction failed")
            print("STDERR:", result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("[FAIL] Extraction timed out")
        return False
    except Exception as e:
        print(f"[FAIL] Error: {str(e)}")
        return False

def main():
    print("="*80)
    print("GoodQ4All - Test Frame Extraction")
    print("="*80)
    print("\nThis will extract a single frame for vision pipeline testing\n")
    
    if extract_frame():
        print("\n" + "="*80)
        print("Next Step:")
        print("="*80)
        print("Run focused vision tests or an approved witness for the current branch.")
        print("="*80)
    else:
        print("\n[WARN]  Manual extraction required:")
        print("1. Open a video in VLC or similar")
        print("2. Pause at any frame")
        print("3. Take a screenshot")
        print("4. Save as: test_data\\sample_frame.jpg")
    
    input("\nPress ENTER to exit...")

if __name__ == "__main__":
    main()
