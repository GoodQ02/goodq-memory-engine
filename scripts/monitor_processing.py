#!/usr/bin/env python3
"""
Real-time processing monitor for GoodQ ingestion
"""

import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def get_color(text, color_code):
    """Add color to terminal output"""
    colors = {
        'green': '\033[92m',
        'yellow': '\033[93m',
        'red': '\033[91m',
        'blue': '\033[94m',
        'cyan': '\033[96m',
        'reset': '\033[0m',
        'bold': '\033[1m'
    }
    return f"{colors.get(color_code, '')}{text}{colors['reset']}"

def format_size(bytes):
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} TB"

def format_time(seconds):
    """Format seconds to human readable"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"

def monitor_processing():
    """Monitor processing in real-time"""
    base_dir = Path(__file__).parent
    processing_dir = base_dir / "data" / "processing"
    output_dir = base_dir / "output"
    logs_dir = base_dir / "logs"
    
    print("=" * 100)
    print(get_color("GoodQ Processing Monitor", 'bold'))
    print("=" * 100)
    print()
    
    last_stats = {}
    iteration = 0
    
    try:
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            
            print("=" * 100)
            print(get_color(f"GoodQ Processing Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 'bold'))
            print("=" * 100)
            print()
            
            # Check processing directories
            if processing_dir.exists():
                proc_dirs = [d for d in processing_dir.iterdir() if d.is_dir()]
                
                if proc_dirs:
                    print(get_color("📹 ACTIVE PROCESSING:", 'cyan'))
                    print()
                    
                    for proc_dir in proc_dirs:
                        # Get video file
                        video_files = list(proc_dir.glob("*.mp4")) + list(proc_dir.glob("*.avi"))
                        if video_files:
                            video_file = video_files[0]
                            size = video_file.stat().st_size
                            
                            print(f"  {get_color('Video:', 'yellow')} {video_file.name}")
                            print(f"  {get_color('Size:', 'yellow')} {format_size(size)}")
                            print(f"  {get_color('Processing Dir:', 'yellow')} {proc_dir.name}")
                            
                            # Count scenes
                            scenes_dir = proc_dir / "scenes"
                            if scenes_dir.exists():
                                scene_count = len([d for d in scenes_dir.iterdir() if d.is_dir()])
                                print(f"  {get_color('Scenes Detected:', 'green')} {scene_count}")
                                
                                # Count processed frames
                                total_frames = 0
                                for scene_dir in scenes_dir.iterdir():
                                    if scene_dir.is_dir():
                                        frames_dir = scene_dir / "frames"
                                        if frames_dir.exists():
                                            total_frames += len(list(frames_dir.glob("*.jpg")))
                                
                                if total_frames > 0:
                                    print(f"  {get_color('Frames Extracted:', 'green')} {total_frames}")
                            
                            # Check for embeddings
                            embeddings_dir = proc_dir / "embeddings"
                            if embeddings_dir.exists():
                                emb_files = list(embeddings_dir.glob("*.npy"))
                                if emb_files:
                                    print(f"  {get_color('Embeddings:', 'green')} {len(emb_files)} files")
                            
                            # Check for transcript
                            transcript_file = proc_dir / "transcript.json"
                            if transcript_file.exists():
                                try:
                                    with open(transcript_file) as f:
                                        transcript = json.load(f)
                                        if isinstance(transcript, list):
                                            print(f"  {get_color('Transcript:', 'green')} {len(transcript)} segments")
                                        elif isinstance(transcript, dict) and 'text' in transcript:
                                            print(f"  {get_color('Transcript:', 'green')} {len(transcript['text'])} characters")
                                except:
                                    pass
                            
                            print()
                else:
                    print(get_color("✅ No active processing", 'green'))
                    print()
            
            # Check output directory
            if output_dir.exists():
                output_videos = [d for d in output_dir.iterdir() if d.is_dir()]
                
                if output_videos:
                    print(get_color(f"✅ COMPLETED VIDEOS: {len(output_videos)}", 'green'))
                    print()
                    
                    for video_dir in sorted(output_videos, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
                        metadata_file = video_dir / "metadata.json"
                        if metadata_file.exists():
                            try:
                                with open(metadata_file) as f:
                                    metadata = json.load(f)
                                    filename = metadata.get('original_filename', video_dir.name)
                                    processed_date = metadata.get('processed_date', 'unknown')
                                    print(f"  • {filename} (processed: {processed_date[:10]})")
                            except:
                                print(f"  • {video_dir.name}")
                        else:
                            print(f"  • {video_dir.name}")
                    
                    if len(output_videos) > 5:
                        print(f"  ... and {len(output_videos) - 5} more")
                    print()
            
            # Check logs for recent activity
            print(get_color("📊 RECENT LOG ACTIVITY:", 'cyan'))
            print()
            
            log_files = {
                'Visual Biometrics': logs_dir / 'Visual Biometrics.log',
                'Audio Frequency': logs_dir / 'Audio Frequency.log',
                'Watchdog': logs_dir / 'watchdog.log'
            }
            
            for name, log_file in log_files.items():
                if log_file.exists():
                    try:
                        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                            recent = [l for l in lines[-10:] if 'SUCCESS' in l or 'complete' in l.lower()]
                            if recent:
                                last_line = recent[-1].strip()
                                if len(last_line) > 80:
                                    last_line = last_line[:77] + "..."
                                print(f"  {get_color(name + ':', 'yellow')} {last_line}")
                    except:
                        pass
            
            print()
            print("=" * 100)
            print(get_color("Press Ctrl+C to stop monitoring", 'yellow'))
            print("=" * 100)
            
            time.sleep(5)
            iteration += 1
            
    except KeyboardInterrupt:
        print()
        print(get_color("\n✅ Monitoring stopped", 'green'))
        print()

if __name__ == "__main__":
    monitor_processing()
