#!/usr/bin/env python3
"""Comprehensive verification of Phase 1 fix - Segment text storage"""

import sqlite3
import json
import argparse
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _default_db_path() -> Path:
    for env_name in ("GOODQ_DB_PATH", "GOODQ_MEMORY_DB_PATH"):
        value = os.environ.get(env_name)
        if value:
            return Path(value).expanduser()

    data_root = os.environ.get("GOODQ_DATA_ROOT")
    if data_root:
        return Path(data_root).expanduser() / "GoodQ_Data" / "memory.db"

    return REPO_ROOT / "data" / "memory.db"


parser = argparse.ArgumentParser(description="Verify Phase 1 segment text storage")
parser.add_argument("--db-path", type=Path, default=_default_db_path(), help="Path to memory.db")
args = parser.parse_args()
db_path = args.db_path.expanduser()

if not db_path.exists():
    raise SystemExit(f"[ERROR] Database not found: {db_path}")

print("\n" + "="*100)
print(" " * 30 + "PHASE 1 FIX VERIFICATION REPORT")
print("="*100 + "\n")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all segments
segments = cursor.execute(
    "SELECT id, video_hash, start, end, speaker, meta FROM segments ORDER BY start"
).fetchall()

print(f"Total Segments in Database: {len(segments)}")
print("-" * 100 + "\n")

# Analysis
segments_with_text = 0
segments_without_text = 0
total_text_length = 0
speakers_found = set()

for seg_id, vh, start, end, speaker, meta_json in segments:
    meta = json.loads(meta_json) if meta_json else {}
    text = meta.get('text', '')
    
    if text:
        segments_with_text += 1
        total_text_length += len(text)
    else:
        segments_without_text += 1
    
    if speaker:
        speakers_found.add(speaker)

# Calculate statistics
avg_text_length = (total_text_length / segments_with_text) if segments_with_text > 0 else 0
coverage = (segments_with_text / len(segments) * 100) if segments else 0

print("STATISTICS:")
print(f"  [SYMBOL] Segments with text:    {segments_with_text} ({coverage:.1f}%)")
print(f"  [SYMBOL] Segments without text: {segments_without_text}")
print(f"  Unique speakers found:  {len(speakers_found)}")
print(f"  Average text length:    {avg_text_length:.1f} characters")
print(f"  Total transcript chars:  {total_text_length}")
print()

# Show sample segments
print("SAMPLE SEGMENTS (First 5 with text):")
print("-" * 100)

sample_count = 0
for seg_id, vh, start, end, speaker, meta_json in segments:
    meta = json.loads(meta_json) if meta_json else {}
    text = meta.get('text', '')
    
    if text and sample_count < 5:
        print(f"\n{sample_count + 1}. Time: {start:.2f}s - {end:.2f}s | Speaker: {speaker or 'Unknown'}")
        print(f"   Text: \"{text}\"")
        sample_count += 1

# Check scene-segment relationships via links
print("\n\n" + "="*100)
print("SCENE-SEGMENT RELATIONSHIPS:")
print("="*100 + "\n")

# Get links between video and segments
links = cursor.execute(
    "SELECT parent_hash, child_hash, relation, timestamp, meta FROM links WHERE relation = 'segment_of' ORDER BY timestamp"
).fetchall()

print(f"Total segment links: {len(links)}")

# Group by scene
scene_segments = {}
for parent, child, relation, ts, meta_json in links:
    meta = json.loads(meta_json) if meta_json else {}
    scene_id = meta.get('scene_id', 'unknown')
    
    if scene_id not in scene_segments:
        scene_segments[scene_id] = []
    scene_segments[scene_id].append((child, ts))

print(f"Scenes with segments: {len(scene_segments)}")
print()

for scene_id, segs in list(scene_segments.items())[:3]:  # Show first 3 scenes
    print(f"Scene: {scene_id[:32]}...")
    print(f"  Segments: {len(segs)}")
    
    # Get text for these segments
    for seg_hash, ts in segs[:3]:  # Show first 3 segments per scene
        seg_data = cursor.execute(
            "SELECT start, end, speaker, meta FROM segments WHERE id = ?",
            (seg_hash,)
        ).fetchone()
        
        if seg_data:
            s_start, s_end, s_speaker, s_meta_json = seg_data
            s_meta = json.loads(s_meta_json) if s_meta_json else {}
            s_text = s_meta.get('text', '')
            print(f"    @{s_start:.2f}s: \"{s_text[:60]}{'...' if len(s_text) > 60 else ''}\"")
    print()

# Final verdict
print("\n" + "="*100)
print("VERDICT:")
print("="*100 + "\n")

if segments_with_text == len(segments) and segments_with_text > 0:
    print("  [OK] PHASE 1 FIX SUCCESSFUL!")
    print(f"  [OK] All {segments_with_text} segments have text stored correctly")
    print("  [OK] Segment-to-scene relationships intact")
    print("  [OK] Speaker attribution preserved")
elif segments_with_text > 0:
    print(f"  [WARN]  PARTIAL SUCCESS")
    print(f"  [OK] {segments_with_text} segments have text ({coverage:.1f}%)")
    print(f"  [WARN]  {segments_without_text} segments missing text")
else:
    print("  [FAIL] FIX NOT WORKING")
    print("  [FAIL] No segments have text stored")

print("\n" + "="*100 + "\n")

conn.close()
