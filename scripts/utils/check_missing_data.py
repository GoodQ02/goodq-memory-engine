#!/usr/bin/env python3
"""Check what face, speaker, and emotion data exists"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import json
import sqlite3

db_path = Path("data/memory.db")
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

scenes = conn.execute("SELECT * FROM scenes").fetchall()

face_count = 0
speaker_count = 0
emotion_count = 0
speaker_transcript_count = 0

for scene in scenes:
    meta = json.loads(scene['meta']) if scene['meta'] else {}
    
    # Check for faces in both locations
    if 'faces' in meta and meta['faces']:
        face_count += len(meta['faces'])
        print(f"Scene has {len(meta['faces'])} faces (top-level)")
    
    if 'keyframe' in meta and isinstance(meta['keyframe'], dict):
        kf = meta['keyframe']
        if 'faces' in kf and kf['faces']:
            face_count += len(kf['faces'])
            print(f"Scene has {len(kf['faces'])} faces (in keyframe)")
    
    # Check for speakers
    if 'speakers' in meta and meta['speakers']:
        speaker_count += len(meta['speakers'])
        print(f"Scene has speakers (top-level): {meta['speakers']}")
    
    if 'audio' in meta and isinstance(meta['audio'], dict):
        audio = meta['audio']
        if 'speakers' in audio and audio['speakers']:
            speaker_count += len(audio['speakers'])
            print(f"Scene has speakers (in audio): {audio['speakers']}")
        if 'speaker_transcript' in audio and audio['speaker_transcript']:
            speaker_transcript_count += len(audio['speaker_transcript'])
            print(f"Scene has {len(audio['speaker_transcript'])} speaker segments (in audio)")
        if 'emotions' in audio and audio['emotions']:
            emotion_count += 1
            print(f"Scene has emotions (in audio): {audio['emotions']}")
    
    # Check for speaker_transcript at top level
    if 'speaker_transcript' in meta and meta['speaker_transcript']:
        speaker_transcript_count += len(meta['speaker_transcript'])
        print(f"Scene has {len(meta['speaker_transcript'])} speaker segments (top-level)")
    
    # Check for emotions
    if 'emotions' in meta and meta['emotions']:
        emotion_count += 1
        print(f"Scene has emotions (top-level): {meta['emotions']}")

conn.close()

print(f"\nTotal faces: {face_count}")
print(f"Total speakers: {speaker_count}")
print(f"Total speaker transcript segments: {speaker_transcript_count}")
print(f"Total scenes with emotions: {emotion_count}")
