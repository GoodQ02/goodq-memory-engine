#!/usr/bin/env python3
"""
Analyze what data is available vs what's being extracted to knowledge graph
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

# Get one detailed scene
scene = cursor.execute("SELECT * FROM scenes LIMIT 1").fetchone()
meta = json.loads(scene['meta']) if scene['meta'] else {}

print("="*60)
print("AVAILABLE FIELDS IN SCENE META")
print("="*60)

for key in sorted(meta.keys()):
    value = meta[key]
    if isinstance(value, (list, dict)):
        print(f"\n{key} ({type(value).__name__}):")
        if isinstance(value, list):
            if value:
                print(f"  Count: {len(value)}")
                print(f"  Sample: {value[0] if len(value) > 0 else 'empty'}")
        elif isinstance(value, dict):
            print(f"  Keys: {list(value.keys())}")
            # Print sample values
            for k, v in list(value.items())[:3]:
                v_str = str(v)[:100]
                print(f"    {k}: {v_str}")
    else:
        value_str = str(value)[:100]
        print(f"{key}: {value_str}")

print("\n" + "="*60)
print("WHAT'S CURRENTLY BEING EXTRACTED TO KNOWLEDGE GRAPH")
print("="*60)

print("""
FROM KEYFRAME (_process_keyframe_entities):
  ✓ detections/objects -> 'object' nodes
  ✓ tags -> 'concept' nodes  
  ✓ emotions -> 'emotion' nodes
  ✓ ocr_text -> 'concept' node with 'text_overlay'
  
  ✗ faces NOT EXTRACTED
  ✗ face_count NOT USED
  ✗ caption NOT EXTRACTED
  ✗ sentiment NOT EXTRACTED (from keyframe)
  ✗ entities NOT EXTRACTED
  ✗ detections details (bbox, confidence) NOT FULLY USED

FROM AUDIO (_process_audio_entities):
  ✓ transcript -> 'concept' node with 'speech'
  ✓ speakers -> 'person' nodes
  ✓ audio_emotion -> 'emotion' nodes
  ✓ tags -> 'concept' nodes
  
  ✗ sentiment NOT EXTRACTED (from audio)
  ✗ transcript_segments NOT EXTRACTED
  ✗ speaker_transcript NOT EXTRACTED
  ✗ diarization details NOT EXTRACTED
  ✗ music_events NOT EXTRACTED
  ✗ time_hints NOT EXTRACTED
  ✗ audio_features NOT EXTRACTED
""")

print("\n" + "="*60)
print("MISSING DATA FROM KNOWLEDGE GRAPH")
print("="*60)

# Analyze all scenes to see what data is available
all_scenes = cursor.execute("SELECT * FROM scenes").fetchall()
field_counts = {}

for scene in all_scenes:
    meta = json.loads(scene['meta']) if scene['meta'] else {}
    for key in meta.keys():
        field_counts[key] = field_counts.get(key, 0) + 1

print(f"\nField availability across {len(all_scenes)} scenes:")
for field, count in sorted(field_counts.items()):
    pct = (count / len(all_scenes)) * 100
    print(f"  {field}: {count}/{len(all_scenes)} ({pct:.0f}%)")

conn.close()

print("\n" + "="*60)
print("RECOMMENDATIONS")
print("="*60)
print("""
1. Extract FACES data:
   - Create 'person' nodes from face detections
   - Link with confidence and bbox info
   - Track across scenes for identity persistence

2. Extract SENTIMENT data:
   - Create 'sentiment' nodes or properties
   - Link to scenes with label (POSITIVE/NEGATIVE/NEUTRAL) and score

3. Extract EMOTIONS data more comprehensively:
   - Process emotions_json field if present
   - Create detailed emotion nodes with scores

4. Extract CAPTIONS:
   - Create 'description' concept nodes from captions
   - High value for semantic search

5. Extract ENTITIES:
   - Named entities (people, places, organizations)
   - Create specific node types

6. Extract MUSIC EVENTS:
   - Create 'music' or 'audio_event' nodes
   - Link with temporal info

7. Extract SPEAKER TRANSCRIPTS:
   - Create more detailed 'person' nodes
   - Link full transcripts, not just speaker IDs

8. Extract TIME HINTS:
   - Temporal context about when content occurred
   - Create temporal metadata nodes
""")
