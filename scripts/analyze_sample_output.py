#!/usr/bin/env python3
"""Analyze sample.mp4 processing output from memory.db."""

import sqlite3
import json
import argparse
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _default_db_path() -> Path:
    for env_name in ("GOODQ_DB_PATH", "GOODQ_MEMORY_DB_PATH"):
        value = os.environ.get(env_name)
        if value:
            return Path(value).expanduser()

    data_root = os.environ.get("GOODQ_DATA_ROOT")
    if data_root:
        return Path(data_root).expanduser() / "GoodQ_Data" / "memory.db"

    return REPO_ROOT / "data" / "memory.db"


parser = argparse.ArgumentParser(description="Analyze GoodQ scene output from memory.db")
parser.add_argument("--db-path", type=Path, default=_default_db_path(), help="Path to memory.db")
args = parser.parse_args()
db_path = args.db_path.expanduser()

if not db_path.exists():
    raise SystemExit(f"[ERROR] Database not found: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("\n" + "="*80)
print("=== SAMPLE.MP4 PROCESSING ANALYSIS ===")
print("="*80 + "\n")

# Find all videos (by looking at unique video_hash values)
video_hashes = cursor.execute(
    "SELECT DISTINCT video_hash FROM scenes ORDER BY created_at DESC"
).fetchall()

print(f"Total unique videos in database: {len(video_hashes)}\n")

for (video_hash,) in video_hashes:
    print(f"\n{'='*80}")
    print(f"VIDEO: {video_hash[:16]}...")
    print(f"{'='*80}\n")
    
    # Get scenes for this video
    scenes = cursor.execute(
        f"SELECT id, video_hash, start, end, meta, created_at FROM scenes WHERE video_hash = ? ORDER BY start",
        (video_hash,)
    ).fetchall()
    
    print(f"SCENES: {len(scenes)}")
    print("-" * 80)
    for idx, (scene_id, vh, start, end, meta_json, created) in enumerate(scenes):
        duration = end - start
        meta = json.loads(meta_json) if meta_json else {}
        print(f"\nScene {idx}: {scene_id}")
        print(f"  Time: {start:.2f}s - {end:.2f}s (duration: {duration:.2f}s)")
        print(f"  Created: {created}")
        
        if meta:
            print(f"  Metadata:")
            for key, value in meta.items():
                if isinstance(value, dict):
                    print(f"    {key}:")
                    for k, v in value.items():
                        print(f"      {k}: {v}")
                elif isinstance(value, list) and len(value) > 5:
                    print(f"    {key}: [{len(value)} items] {value[:3]}...")
                else:
                    print(f"    {key}: {value}")
    
    # Get segments for this video
    print(f"\n\nTRANSCRIPT SEGMENTS: ")
    print("-" * 80)
    segments = cursor.execute(
        f"SELECT id, video_hash, start, end, speaker, meta, created_at FROM segments WHERE video_hash = ? ORDER BY start",
        (video_hash,)
    ).fetchall()
    
    print(f"Total segments: {len(segments)}\n")
    for idx, (seg_id, vh, start, end, speaker, meta_json, created) in enumerate(segments):
        duration = end - start
        meta = json.loads(meta_json) if meta_json else {}
        text = meta.get('text', '')
        
        print(f"\nSegment {idx}: {seg_id}")
        print(f"  Time: {start:.2f}s - {end:.2f}s (duration: {duration:.2f}s)")
        print(f"  Speaker: {speaker or 'Unknown'}")
        print(f"  Text: {text[:100]}{'...' if len(text) > 100 else ''}")
        
        # Show other metadata
        meta_copy = dict(meta)
        meta_copy.pop('text', None)  # Already shown
        if meta_copy:
            print(f"  Other metadata: {list(meta_copy.keys())}")
    
    # Get embeddings for this video
    print(f"\n\nEMBEDDINGS:")
    print("-" * 80)
    embeddings = cursor.execute(
        """SELECT hash, faiss_id, source_path, modality, scene_id, sentiment_label, 
                  sentiment_score, emotions_json
           FROM embeddings 
           WHERE hash = ? OR source_path LIKE ?
           ORDER BY created_at""",
        (video_hash, f"%{video_hash[:10]}%")
    ).fetchall()
    
    print(f"Total embeddings: {len(embeddings)}\n")
    for idx, (hash_val, faiss_id, src, mod, scene, sent_label, sent_score, emo_json) in enumerate(embeddings):
        print(f"\nEmbedding {idx}:")
        print(f"  Hash: {hash_val[:16]}...")
        print(f"  FAISS ID: {faiss_id}")
        print(f"  Modality: {mod}")
        print(f"  Scene ID: {scene}")
        print(f"  Sentiment: {sent_label} ({sent_score:.3f})" if sent_label else "  Sentiment: None")
        
        if emo_json:
            emotions = json.loads(emo_json)
            if emotions:
                print(f"  Emotions: {emotions[:3] if len(emotions) > 3 else emotions}")
    
    # Get links for this video
    print(f"\n\nLINKS (RELATIONSHIPS):")
    print("-" * 80)
    links = cursor.execute(
        """SELECT parent_hash, child_hash, relation, timestamp, meta
           FROM links 
           WHERE parent_hash = ? OR child_hash = ?
           ORDER BY timestamp""",
        (video_hash, video_hash)
    ).fetchall()
    
    print(f"Total links: {len(links)}\n")
    for idx, (parent, child, relation, ts, meta_json) in enumerate(links[:10]):  # Show first 10
        meta = json.loads(meta_json) if meta_json else {}
        print(f"\nLink {idx}:")
        print(f"  {parent[:16]}... --[{relation}]--> {child[:16]}...")
        print(f"  Timestamp: {ts:.2f}s")
        if meta:
            print(f"  Meta: {meta}")
    
    if len(links) > 10:
        print(f"\n  ... and {len(links) - 10} more links")

print(f"\n\n{'='*80}")
print("=== END OF ANALYSIS ===")
print("="*80 + "\n")

conn.close()
