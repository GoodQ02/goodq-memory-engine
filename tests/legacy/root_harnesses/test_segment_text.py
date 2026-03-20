#!/usr/bin/env python3
"""Test script to verify segment text storage fix"""

import sqlite3
import json

db_path = "L:\\goodq4all\\data\\memory.db"

print("\n" + "="*80)
print("CHECKING SEGMENT TEXT STORAGE")
print("="*80 + "\n")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get a few segments
segments = cursor.execute(
    "SELECT id, video_hash, start, end, speaker, meta FROM segments LIMIT 5"
).fetchall()

print(f"Checking {len(segments)} sample segments:\n")

for idx, (seg_id, vh, start, end, speaker, meta_json) in enumerate(segments):
    meta = json.loads(meta_json) if meta_json else {}
    text = meta.get('text', '')
    
    print(f"Segment {idx + 1}:")
    print(f"  ID: {seg_id[:32]}...")
    print(f"  Time: {start:.2f}s - {end:.2f}s")
    print(f"  Speaker: {speaker or 'None'}")
    print(f"  Has text in meta: {'YES' if text else 'NO'}")
    if text:
        print(f"  Text: {text[:80]}{'...' if len(text) > 80 else ''}")
    else:
        print(f"  Meta keys: {list(meta.keys())}")
    print()

conn.close()

print("="*80)
print("To fix, we need to re-run ingestion on sample.mp4")
print("The fix has been applied to steps/common/memory.py line 345")
print("="*80 + "\n")
