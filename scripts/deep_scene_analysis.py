import sqlite3
import json
import os

db_path = "data/memory.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get video hash
cursor.execute("SELECT DISTINCT video_hash FROM scenes LIMIT 1")
video_hash = cursor.fetchone()[0]
print(f"=== VIDEO HASH: {video_hash} ===\n")

# Get all scenes
cursor.execute("""
    SELECT id, start, end, meta 
    FROM scenes 
    WHERE video_hash = ? 
    ORDER BY start
""", (video_hash,))
scenes = cursor.fetchall()

print(f"=== FOUND {len(scenes)} SCENES ===\n")

for idx, scene in enumerate(scenes):
    scene_id, start, end, meta_json = scene
    meta = json.loads(meta_json) if meta_json else {}
    
    print(f"\n{'='*80}")
    print(f"SCENE {idx} (ID: {scene_id[:16]}...)")
    print(f"{'='*80}")
    print(f"Time: {start:.2f}s - {end:.2f}s (duration: {end-start:.2f}s)")
    print(f"Metadata: {json.dumps(meta, indent=2)[:200]}...")
    
    # Get links for this scene
    cursor.execute("""
        SELECT child_hash, relation, meta 
        FROM links 
        WHERE parent_hash = ?
        ORDER BY relation
    """, (scene_id,))
    links = cursor.fetchall()
    
    print(f"\nLinks from this scene: {len(links)}")
    for link in links:
        child_hash, relation, link_meta = link
        print(f"  → {relation}: {child_hash[:16]}...")
        if link_meta:
            link_meta_parsed = json.loads(link_meta)
            print(f"     {link_meta_parsed}")
    
    # Get embeddings for this scene
    cursor.execute("""
        SELECT modality, source_path, sentiment_label, sentiment_score 
        FROM embeddings 
        WHERE source_path LIKE ? 
        ORDER BY modality
    """, (f"%scene_{idx:04d}%",))
    embeddings = cursor.fetchall()
    
    print(f"\nEmbeddings for this scene: {len(embeddings)}")
    for emb in embeddings:
        modality, path, sent_label, sent_score = emb
        filename = os.path.basename(path)
        print(f"  [{modality}] {filename}")
        if sent_label:
            print(f"    Sentiment: {sent_label} ({sent_score:.2f})")
    
    # Get speaker segments overlapping this scene
    cursor.execute("""
        SELECT speaker, start, end, meta 
        FROM segments 
        WHERE video_hash = ? 
        AND ((start >= ? AND start < ?) OR (end > ? AND end <= ?) OR (start < ? AND end > ?))
        ORDER BY start
    """, (video_hash, start, end, start, end, start, end))
    segments = cursor.fetchall()
    
    print(f"\nSpeaker segments in this scene: {len(segments)}")
    for seg in segments:
        speaker, seg_start, seg_end, seg_meta = seg
        print(f"  {speaker}: {seg_start:.2f}s - {seg_end:.2f}s")

# Check for any orphaned embeddings or links
print(f"\n\n{'='*80}")
print("ORPHANED DATA CHECK")
print(f"{'='*80}")

cursor.execute("SELECT COUNT(*) FROM embeddings WHERE scene_id IS NULL")
orphaned_embeddings = cursor.fetchone()[0]
print(f"Embeddings without scene_id: {orphaned_embeddings}")

cursor.execute("""
    SELECT COUNT(*) FROM links 
    WHERE parent_hash NOT IN (SELECT id FROM scenes)
    AND parent_hash != ?
""", (video_hash,))
orphaned_links = cursor.fetchone()[0]
print(f"Links with non-existent parent (excluding video): {orphaned_links}")

# Check for missing data
print(f"\n{'='*80}")
print("MISSING DATA CHECK")
print(f"{'='*80}")

# Check which scenes have embeddings
for idx in range(10):
    cursor.execute("""
        SELECT COUNT(*) FROM embeddings 
        WHERE source_path LIKE ?
    """, (f"%scene_{idx:04d}%",))
    count = cursor.fetchone()[0]
    if count == 0:
        print(f"⚠ Scene {idx:04d}: NO EMBEDDINGS")
    else:
        # Break down by modality
        cursor.execute("""
            SELECT modality, COUNT(*) 
            FROM embeddings 
            WHERE source_path LIKE ? 
            GROUP BY modality
        """, (f"%scene_{idx:04d}%",))
        modalities = cursor.fetchall()
        modality_str = ", ".join([f"{m[0]}:{m[1]}" for m in modalities])
        print(f"✓ Scene {idx:04d}: {count} embeddings ({modality_str})")

conn.close()

print("\n\n=== CHECKING FOR TRANSCRIPTION FILES ===")
# Check for transcription output files
for scene_num in range(10):
    scene_str = f"scene_{scene_num:04d}"
    audio_path = f"logs/test_full_sample/sample/audio/{scene_str}.wav"
    
    # Look for associated transcription
    possible_paths = [
        f"logs/test_full_sample/sample/transcripts/{scene_str}.txt",
        f"logs/test_full_sample/sample/transcripts/{scene_str}.json",
        f"output/sample/transcripts/{scene_str}.txt",
        f"output/sample/transcripts/{scene_str}.json",
    ]
    
    found = False
    for path in possible_paths:
        if os.path.exists(path):
            print(f"✓ {scene_str}: Found at {path}")
            found = True
            break
    
    if not found:
        print(f"✗ {scene_str}: No transcription file found")

print("\n\n=== CHECKING FOR ANALYSIS OUTPUT FILES ===")
# Check for image analysis outputs
for scene_num in range(10):
    scene_str = f"scene_{scene_num:04d}"
    
    possible_paths = [
        f"logs/test_full_sample/sample/analysis/{scene_str}.json",
        f"output/sample/analysis/{scene_str}.json",
        f"output/sample/{scene_str}_analysis.json",
    ]
    
    found = False
    for path in possible_paths:
        if os.path.exists(path):
            print(f"✓ {scene_str}: Found at {path}")
            with open(path, 'r') as f:
                data = json.load(f)
                print(f"   Keys: {list(data.keys())}")
            found = True
            break
    
    if not found:
        print(f"✗ {scene_str}: No analysis file found")
