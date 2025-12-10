#!/usr/bin/env python3
"""Phase 3 Diagnostic - Identify exact issues with scene processing"""

import sqlite3
import json
import os
from pathlib import Path

db_path = "data/memory.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("="*80)
print("PHASE 3 DIAGNOSTIC REPORT")
print("="*80)

# Get video hash
cursor.execute("SELECT DISTINCT video_hash FROM scenes LIMIT 1")
result = cursor.fetchone()
if not result:
    print("ERROR: No scenes found in database!")
    exit(1)

video_hash = result[0]
print(f"\nVideo Hash: {video_hash}\n")

# Get all scenes
cursor.execute("""
    SELECT id, start, end, meta 
    FROM scenes 
    WHERE video_hash = ? 
    ORDER BY start
""", (video_hash,))
scenes = cursor.fetchall()

print(f"Total Scenes: {len(scenes)}\n")

# Issue 1: Check for duplicate/wrong paths in links
print("="*80)
print("ISSUE 1: Checking frame and audio paths in links")
print("="*80)

for idx, scene_data in enumerate(scenes[:5]):  # Check first 5 scenes
    scene_id, start, end, meta_json = scene_data
    meta = json.loads(meta_json) if meta_json else {}
    scene_index = meta.get('index', idx)
    
    print(f"\nScene {scene_index} (DB index {idx}): {start:.2f}s - {end:.2f}s")
    print(f"  Scene ID: {scene_id[:16]}...")
    
    # Get keyframe link
    cursor.execute("""
        SELECT child_hash, meta 
        FROM links 
        WHERE parent_hash = ? AND relation = 'keyframe_of'
    """, (scene_id,))
    frame_link = cursor.fetchone()
    if frame_link:
        child_hash, link_meta = frame_link
        link_meta_parsed = json.loads(link_meta) if link_meta else {}
        path = link_meta_parsed.get('path', 'NO PATH')
        print(f"  Frame Link: {path}")
        print(f"  Expected: scene_{scene_index:04d}.jpg")
        if f"scene_{scene_index:04d}" not in path:
            print(f"  [FAIL] MISMATCH!")
    else:
        print(f"  [FAIL] NO FRAME LINK FOUND")
    
    # Get audio link
    cursor.execute("""
        SELECT child_hash, meta 
        FROM links 
        WHERE parent_hash = ? AND relation = 'audio_of_scene'
    """, (scene_id,))
    audio_link = cursor.fetchone()
    if audio_link:
        child_hash, link_meta = audio_link
        link_meta_parsed = json.loads(link_meta) if link_meta else {}
        path = link_meta_parsed.get('path', 'NO PATH')
        print(f"  Audio Link: {path}")
        print(f"  Expected: scene_{scene_index:04d}.wav")
        if f"scene_{scene_index:04d}" not in path:
            print(f"  [FAIL] MISMATCH!")
    else:
        print(f"  [FAIL] NO AUDIO LINK FOUND")

# Issue 2: Check for duplicate embeddings
print("\n" + "="*80)
print("ISSUE 2: Checking for duplicate embeddings")
print("="*80)

cursor.execute("""
    SELECT source_path, modality, COUNT(*) as count
    FROM embeddings
    GROUP BY source_path, modality
    HAVING count > 1
    ORDER BY count DESC
    LIMIT 10
""")
duplicates = cursor.fetchall()

if duplicates:
    print(f"\nFound {len(duplicates)} source_path+modality combinations with duplicates:")
    for source_path, modality, count in duplicates:
        print(f"  {count}x [{modality}] {os.path.basename(source_path)}")
        
        # Show the actual hashes
        cursor.execute("""
            SELECT hash, scene_id 
            FROM embeddings 
            WHERE source_path = ? AND modality = ?
        """, (source_path, modality))
        entries = cursor.fetchall()
        for emb_hash, scene_id in entries:
            print(f"    Hash: {emb_hash[:16]}... Scene: {scene_id[:16] if scene_id else 'NULL'}...")
else:
    print("\n[SYMBOL] No duplicate embeddings found")

# Issue 3: Check for invalid speaker segments
print("\n" + "="*80)
print("ISSUE 3: Checking for invalid speaker segments")
print("="*80)

cursor.execute("""
    SELECT id, start, end, speaker, meta
    FROM segments
    WHERE video_hash = ?
    ORDER BY start
""", (video_hash,))
segments = cursor.fetchall()

invalid_segments = []
for seg_id, start, end, speaker, meta_json in segments:
    if end < start:
        invalid_segments.append((seg_id, start, end, speaker))
    elif end == start:
        invalid_segments.append((seg_id, start, end, speaker))

if invalid_segments:
    print(f"\nFound {len(invalid_segments)} invalid segments:")
    for seg_id, start, end, speaker in invalid_segments[:10]:  # Show first 10
        print(f"  Segment {seg_id[:16]}... Speaker: {speaker}")
        print(f"    Time: {start:.2f}s -> {end:.2f}s (duration: {end-start:.2f}s)")
        print(f"    [FAIL] INVALID: end <= start")
else:
    print("\n[SYMBOL] No invalid segments found")

# Issue 4: Check scene index consistency
print("\n" + "="*80)
print("ISSUE 4: Checking scene index consistency")
print("="*80)

index_issues = []
for db_idx, scene_data in enumerate(scenes):
    scene_id, start, end, meta_json = scene_data
    meta = json.loads(meta_json) if meta_json else {}
    meta_index = meta.get('index')
    
    if meta_index != db_idx:
        index_issues.append((db_idx, meta_index, start, end))

if index_issues:
    print(f"\nFound {len(index_issues)} scenes with index mismatches:")
    for db_idx, meta_index, start, end in index_issues[:10]:
        print(f"  DB position {db_idx}: meta.index={meta_index}, time={start:.2f}s-{end:.2f}s")
        print(f"    [FAIL] MISMATCH")
else:
    print("\n[SYMBOL] All scene indices are consistent")

# Summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Total Scenes: {len(scenes)}")
print(f"Total Segments: {len(segments)}")

cursor.execute("SELECT COUNT(*) FROM embeddings")
emb_count = cursor.fetchone()[0]
print(f"Total Embeddings: {emb_count}")

cursor.execute("SELECT COUNT(*) FROM links")
link_count = cursor.fetchone()[0]
print(f"Total Links: {link_count}")

print("\nIssues Found:")
print(f"  - Duplicate Embeddings: {len(duplicates) if duplicates else 0}")
print(f"  - Invalid Segments: {len(invalid_segments)}")
print(f"  - Index Mismatches: {len(index_issues)}")

conn.close()
