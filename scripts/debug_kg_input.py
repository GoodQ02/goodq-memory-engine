#!/usr/bin/env python3
"""Test with debug output to see what's being passed to KG functions"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import json
import sqlite3

db_path = Path("data/memory.db")
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

scenes = conn.execute("SELECT * FROM scenes ORDER BY start LIMIT 3").fetchall()

for idx, scene in enumerate(scenes):
    meta = json.loads(scene['meta']) if scene['meta'] else {}
    
    print(f"\n{'='*60}")
    print(f"Scene {idx}: {scene['start']:.2f}s - {scene['end']:.2f}s")
    print('='*60)
    
    # Build keyframe dict
    keyframe_data = meta.get('keyframe', {}).copy() if isinstance(meta.get('keyframe'), dict) else {}
    if 'faces' in meta and meta['faces']:
        keyframe_data['faces'] = meta['faces']
    if 'objects' in keyframe_data:
        keyframe_data['detections'] = keyframe_data.pop('objects')
    
    print("\nKeyframe data keys:", list(keyframe_data.keys()))
    if 'faces' in keyframe_data:
        print(f"  faces count: {len(keyframe_data['faces'])}")
        print(f"  faces[0] keys: {list(keyframe_data['faces'][0].keys()) if keyframe_data['faces'] else 'empty'}")
    if 'detections' in keyframe_data:
        print(f"  detections count: {len(keyframe_data['detections'])}")
    
    # Build audio dict
    audio_data = meta.get('audio', {}).copy() if isinstance(meta.get('audio'), dict) else {}
    if 'speaker_transcript' in meta and meta['speaker_transcript']:
        audio_data['speaker_transcript'] = meta['speaker_transcript']
    if 'speakers' not in audio_data and 'speakers' in meta:
        audio_data['speakers'] = meta['speakers']
    
    print("\nAudio data keys:", list(audio_data.keys()))
    if 'speaker_transcript' in audio_data:
        print(f"  speaker_transcript count: {len(audio_data['speaker_transcript'])}")
        if audio_data['speaker_transcript']:
            st = audio_data['speaker_transcript'][0]
            print(f"  first segment keys: {list(st.keys())}")
            print(f"  first segment: {st}")
    if 'speakers' in audio_data:
        print(f"  speakers: {audio_data['speakers']}")
    if 'sentiment' in audio_data:
        print(f"  sentiment: {audio_data['sentiment']}")
    if 'emotions' in audio_data:
        print(f"  emotions: {audio_data['emotions']}")

conn.close()
