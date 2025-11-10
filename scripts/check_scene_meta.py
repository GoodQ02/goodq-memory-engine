#!/usr/bin/env python3
"""Check scene metadata in memory.db"""

import sqlite3
import json

db_path = "L:\\goodq4all\\data\\memory.db"

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get all scenes
scenes = cursor.execute("SELECT * FROM scenes ORDER BY start").fetchall()

print(f"=== TOTAL SCENES: {len(scenes)} ===\n")

for scene in scenes[:5]:  # Show first 5
    print(f"Scene ID: {scene['id']}")
    print(f"  Video hash: {scene['video_hash']}")
    print(f"  Time: {scene['start']:.2f}s - {scene['end']:.2f}s ({scene['end']-scene['start']:.2f}s)")
    print(f"  Created: {scene['created_at']}")
    
    # Parse metadata
    if scene['meta']:
        try:
            meta = json.loads(scene['meta'])
            print(f"  Meta keys: {list(meta.keys())}")
            
            # Check for analysis fields
            if 'detections' in meta:
                print(f"    Detections: {len(meta['detections'])}")
            if 'objects' in meta:
                print(f"    Objects: {len(meta['objects'])}")
            if 'faces' in meta:
                print(f"    Faces: {len(meta['faces'])}")
            if 'text' in meta:
                print(f"    Text entries: {len(meta['text'])}")
            if 'emotions' in meta:
                print(f"    Emotions: {meta['emotions']}")
            if 'sentiment' in meta:
                print(f"    Sentiment: {meta['sentiment']}")
            if 'audio_features' in meta:
                print(f"    Audio features: {list(meta['audio_features'].keys())}")
            if 'transcript' in meta:
                trans = meta['transcript']
                if isinstance(trans, list) and trans:
                    print(f"    Transcript segments: {len(trans)}")
                    print(f"      First segment: {trans[0] if trans else 'None'}")
                elif isinstance(trans, str):
                    print(f"    Transcript: {trans[:100]}...")
                    
        except Exception as e:
            print(f"  Error parsing meta: {e}")
    else:
        print(f"  Meta: NULL")
    print()

# Check embeddings for scenes
print("\n=== EMBEDDINGS BY MODALITY ===")
embeddings = cursor.execute(
    "SELECT modality, COUNT(*) as count FROM embeddings GROUP BY modality"
).fetchall()
for row in embeddings:
    print(f"  {row['modality']}: {row['count']}")

# Check segments
print(f"\n=== SEGMENTS: {cursor.execute('SELECT COUNT(*) FROM segments').fetchone()[0]} ===")
segments = cursor.execute("SELECT * FROM segments LIMIT 3").fetchall()
for seg in segments:
    print(f"  Segment {seg['id']}: {seg['start']:.2f}s-{seg['end']:.2f}s, Speaker: {seg['speaker']}")
    if seg['meta']:
        try:
            meta = json.loads(seg['meta'])
            if 'text' in meta:
                print(f"    Text: {meta['text'][:100]}...")
        except:
            pass

# Check links
print(f"\n=== LINKS: {cursor.execute('SELECT COUNT(*) FROM links').fetchone()[0]} ===")
links = cursor.execute("SELECT relation, COUNT(*) as count FROM links GROUP BY relation").fetchall()
for row in links:
    print(f"  {row['relation']}: {row['count']}")

conn.close()
