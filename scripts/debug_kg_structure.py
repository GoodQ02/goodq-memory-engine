#!/usr/bin/env python3
"""
Debug why certain fields aren't being extracted
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import json
import sqlite3

db_path = Path("data/memory.db")
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get all scenes
scenes = cursor.execute("SELECT * FROM scenes ORDER BY start").fetchall()

print("="*60)
print("CHECKING ACTUAL DATA STRUCTURE")
print("="*60)

for idx, scene in enumerate(scenes[:3]):
    meta = json.loads(scene['meta']) if scene['meta'] else {}
    
    print(f"\nScene {idx}: {scene['start']:.2f}s - {scene['end']:.2f}s")
    
    # Check keyframe structure
    print("\n  KEYFRAME structure:")
    if 'keyframe' in meta:
        kf = meta['keyframe']
        print(f"    Type: {type(kf)}")
        if isinstance(kf, dict):
            print(f"    Keys: {list(kf.keys())}")
            if 'faces' in kf:
                print(f"    faces: {kf['faces']}")
            if 'caption' in kf:
                print(f"    caption: {kf['caption']}")
            if 'entities' in kf:
                print(f"    entities: {kf['entities']}")
            if 'tags' in kf:
                print(f"    tags: {kf['tags']}")
    else:
        print("    NO KEYFRAME IN META")
        # Check if there's top-level keyframe
        if 'caption' in meta:
            print(f"    Found caption at TOP LEVEL: {meta['caption']}")
        if 'faces' in meta:
            print(f"    Found faces at TOP LEVEL: count={len(meta['faces'])}")
        if 'tags' in meta:
            print(f"    Found tags at TOP LEVEL: {meta['tags']}")
    
    # Check audio structure
    print("\n  AUDIO structure:")
    if 'audio' in meta:
        audio = meta['audio']
        print(f"    Type: {type(audio)}")
        if isinstance(audio, dict):
            print(f"    Keys: {list(audio.keys())}")
            if 'sentiment' in audio:
                print(f"    sentiment: {audio['sentiment']}")
            if 'emotions' in audio:
                print(f"    emotions: {audio['emotions']}")
            if 'entities' in audio:
                print(f"    entities: {audio['entities']}")
            if 'speaker_transcript' in audio:
                print(f"    speaker_transcript count: {len(audio['speaker_transcript'])}")
    else:
        print("    NO AUDIO IN META")
        # Check top-level audio fields
        if 'sentiment' in meta:
            print(f"    Found sentiment at TOP LEVEL: {meta['sentiment']}")
        if 'speaker_transcript' in meta:
            print(f"    Found speaker_transcript at TOP LEVEL: count={len(meta['speaker_transcript'])}")

conn.close()

print("\n" + "="*60)
print("ISSUE IDENTIFIED")
print("="*60)
print("""
The problem is that the scene metadata has TWO levels:
1. Top-level fields (caption, faces, tags, sentiment, etc.)
2. Nested 'keyframe' and 'audio' dictionaries

The KG builder is looking for scene['keyframe']['faces'] but the data 
is stored as scene['faces'] at the top level!

Same for audio - it's looking for scene['audio']['sentiment'] but 
the data is at scene['sentiment'] top level.

SOLUTION: Update the KG builder to handle BOTH structures:
- Check nested keyframe/audio dicts first
- Fall back to top-level fields
""")
