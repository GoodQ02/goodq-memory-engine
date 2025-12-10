"""
Quick script to extract a test frame from video for vision testing
"""

import subprocess
import sys
from pathlib import Path

def extract_frame():
    """Extract a single frame from the first available video"""
    
    # Check for videos
    video_dirs = [
        Path("L:/_DATA/FAMILY_FEAST"),
        Path("L:/goodq4all/import_inbox"),
        Path("L:/_DATA/GoodQ_Data/processing")
    ]
    
    video_files = []
    for vdir in video_dirs:
        if vdir.exists():
            video_files.extend(list(vdir.glob("*.mp4")))
            video_files.extend(list(vdir.glob("*.avi")))
            video_files.extend(list(vdir.glob("*.mov")))
    
    if not video_files:
        print("[FAIL] No video files found in:")
        for vdir in video_dirs:
            print(f"   {vdir}")
        print("\nPlease place a video file in one of these directories")
        return False
    
    # Use first video
    video_path = video_files[0]
    print(f"[VIDEO] Using video: {video_path.name}")
    
    # Output path
    output_dir = Path("L:/goodq4all/test_data")
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
        print("Run the vision audit to test all components:")
        print("  > run_vision_audit.bat")
        print("="*80)
    else:
        print("\n[WARN]  Manual extraction required:")
        print("1. Open a video in VLC or similar")
        print("2. Pause at any frame")
        print("3. Take a screenshot")
        print("4. Save as: L:\\goodq4all\\test_data\\sample_frame.jpg")
    
    input("\nPress ENTER to exit...")

if __name__ == "__main__":
    main()
