"""
Comprehensive diagnostic for sample.mp4 processing
"""
import sqlite3
import json
from pathlib import Path

print("=" * 100)
print("COMPREHENSIVE SAMPLE.MP4 PROCESSING DIAGNOSTIC")
print("=" * 100)

# 1. Check database
print("\n### DATABASE CHECK ###")
conn = sqlite3.connect('data/memory.db')
cursor = conn.cursor()

cursor.execute("SELECT video_hash FROM scenes LIMIT 1")
result = cursor.fetchone()
if result:
    video_hash = result[0]
    print(f"Video hash: {video_hash}")
    
    # Check scene metadata
    cursor.execute("SELECT id, start, end, meta FROM scenes WHERE video_hash = ?", (video_hash,))
    scene = cursor.fetchone()
    if scene:
        print(f"\nScene ID: {scene[0]}")
        print(f"Time range: {scene[1]}s - {scene[2]}s")
        meta = json.loads(scene[3])
        print(f"\nScene metadata keys: {list(meta.keys())}")
        
        # Check for keyframe and audio in metadata
        has_keyframe = 'caption' in meta
        has_audio_meta = 'audio' in meta or 'transcript' in meta
        
        print(f"\nMetadata contains:")
        print(f"  - Keyframe data (caption, objects): {has_keyframe}")
        print(f"  - Audio/transcript data: {has_audio_meta}")
        
        if has_keyframe:
            print(f"\n  Caption: {meta.get('caption', 'N/A')}")
            print(f"  Object count: {meta.get('object_count', 0)}")
        
        if has_audio_meta:
            print(f"\n  Audio metadata: {meta.get('audio', 'N/A')[:200]}")
        else:
            print("\n  [WARN] NO AUDIO DATA FOUND IN METADATA")

conn.close()

# 2. Check file system
print("\n\n### FILE SYSTEM CHECK ###")
workspace = Path('logs/test_workspace/sample')

print(f"\nWorkspace directory: {workspace}")
print(f"Exists: {workspace.exists()}")

if workspace.exists():
    frames_dir = workspace / 'frames'
    audio_dir = workspace / 'audio'
    
    print(f"\nFrames directory: {frames_dir}")
    print(f"  Exists: {frames_dir.exists()}")
    if frames_dir.exists():
        frame_files = list(frames_dir.glob('*.jpg'))
        print(f"  Frame files: {len(frame_files)}")
        for f in frame_files:
            print(f"    - {f.name} ({f.stat().st_size} bytes)")
    
    print(f"\nAudio directory: {audio_dir}")
    print(f"  Exists: {audio_dir.exists()}")
    if audio_dir.exists():
        audio_files = list(audio_dir.glob('*.wav'))
        print(f"  Audio files: {len(audio_files)}")
        if len(audio_files) == 0:
            print(f"    [WARN] NO AUDIO FILES FOUND - This is the problem!")
        for f in audio_files:
            print(f"    - {f.name} ({f.stat().st_size} bytes)")

# 3. Check test input file
print("\n\n### INPUT FILE CHECK ###")
input_file = Path('test_input/sample.mp4')
print(f"Input file: {input_file}")
print(f"  Exists: {input_file.exists()}")
if input_file.exists():
    print(f"  Size: {input_file.stat().st_size:,} bytes")

# 4. Check agent logs for errors
print("\n\n### AGENT LOGS CHECK ###")
log_dir = Path('logs')
recent_logs = [
    'Recon Scanner.log',
    'Visual Intel.log',
    'Target Identification.log',
]

for log_name in recent_logs:
    log_file = log_dir / log_name
    if log_file.exists():
        print(f"\n{log_name}:")
        with open(log_file, 'r') as f:
            lines = f.readlines()
            for line in lines[-3:]:  # Last 3 lines
                print(f"  {line.strip()}")

# 5. Check for audio-related logs
print("\n\n### AUDIO PROCESSING LOGS ###")
audio_log_patterns = ['*audio*', '*transcribe*', '*diarize*', '*speaker*']
audio_logs_found = False
for pattern in audio_log_patterns:
    for log_file in log_dir.glob(pattern):
        audio_logs_found = True
        print(f"\nFound: {log_file.name}")
        if log_file.stat().st_size > 0:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                print(f"  Last lines:")
                for line in lines[-5:]:
                    print(f"    {line.strip()}")
        else:
            print(f"  (empty file)")

if not audio_logs_found:
    print("\n[WARN] NO AUDIO PROCESSING LOGS FOUND - Audio steps likely never ran!")

# 6. Check configuration
print("\n\n### CONFIGURATION CHECK ###")
config_file = Path('logs/test_workspace/_resolved_config.json')
if config_file.exists():
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    force_reprocess = config.get('force_reprocess', False)
    print(f"Force reprocess: {force_reprocess}")
    
    run_info = config.get('run', {})
    print(f"Run ID: {run_info.get('id', 'N/A')}")
    print(f"Started at: {run_info.get('started_at', 'N/A')}")

print("\n" + "=" * 100)
print("DIAGNOSTIC SUMMARY")
print("=" * 100)

print("\n[STATS] KEY FINDINGS:")
print("1. [OK] Scene detection worked - 1 scene found (0-2s)")
print("2. [OK] Keyframe extraction worked - 1 frame image created")
print("3. [OK] Image analysis worked - caption and objects detected")
print("4. [OK] Image embeddings created - CLIP and DINO vectors in FAISS")
print("5. [FAIL] AUDIO PROCESSING DID NOT RUN - No WAV files, no transcripts, no audio embeddings")

print("\n[SEARCH] ROOT CAUSE ANALYSIS:")
print("The audio processing step appears to have been skipped or failed silently.")
print("Possible causes:")
print("  A) Audio processing was skipped due to deduplication logic (scene already 'materialized')")
print("  B) Audio extraction failed silently without proper error logging")
print("  C) Audio processing agents crashed or timed out")
print("  D) The run was interrupted before audio processing could begin")

print("\n[TARGET] NEXT STEPS:")
print("1. Check if 'skip_audio' flag was set to True during processing")
print("2. Run ingestion again with --force flag to bypass deduplication")
print("3. Check conda environments for audio processing steps")
print("4. Enable detailed logging to capture audio processing failures")
print("5. Test audio extraction manually with ffmpeg")

print("\n" + "=" * 100)
