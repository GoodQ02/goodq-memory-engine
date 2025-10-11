"""Analyze ingestion output comprehensively."""
import sqlite3
import json
from pathlib import Path
from collections import Counter

print("=" * 70)
print("GOODQ INGESTION ANALYSIS")
print("=" * 70)

# Connect to memory DB
db_path = 'L:/_DATA/GoodQ_Data/data/memory_db/memory.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Basic stats
scenes_count = cur.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]
embeddings_count = cur.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
links_count = cur.execute("SELECT COUNT(*) FROM links").fetchone()[0]

print(f"\n📊 DATABASE STATS")
print(f"   Scenes: {scenes_count}")
print(f"   Embeddings: {embeddings_count}")
print(f"   Links: {links_count}")

# Analyze scenes
print(f"\n🎬 SCENE ANALYSIS")
cur.execute("SELECT id, video_hash, start, end, meta FROM scenes ORDER BY start")
all_captions = []
all_objects = []
all_tags = []
speaker_counts = Counter()
transcripts = []

for row in cur.fetchall():
    scene_id, video_hash, start, end, meta_json = row
    meta = json.loads(meta_json)
    
    # Extract keyframe data
    if 'keyframe' in meta:
        kf = meta['keyframe']
        if 'caption' in kf and kf['caption']:
            all_captions.append(kf['caption'])
        if 'objects' in kf:
            for obj in kf['objects']:
                all_objects.append(obj['label'])
        if 'tags' in kf:
            all_tags.extend(kf['tags'])
    
    # Extract audio data
    if 'audio' in meta:
        audio = meta['audio']
        if 'transcript' in audio and audio['transcript']:
            transcripts.append(audio['transcript'])
        if 'transcript_meta' in audio and 'chunks' in audio['transcript_meta']:
            for chunk in audio['transcript_meta']['chunks']:
                if 'speaker' in chunk:
                    speaker_counts[chunk['speaker']] += 1

print(f"   Total scenes processed: {scenes_count}")
print(f"   Time span: {start:.1f}s - {end:.1f}s")

# Captions
print(f"\n💬 CAPTIONS EXTRACTED ({len(all_captions)} total)")
for i, caption in enumerate(all_captions[:10], 1):
    print(f"   {i}. {caption}")
if len(all_captions) > 10:
    print(f"   ... and {len(all_captions) - 10} more")

# Objects
print(f"\n🔍 OBJECTS DETECTED")
object_counts = Counter(all_objects)
for obj, count in object_counts.most_common(10):
    print(f"   {obj}: {count}x")

# Tags
print(f"\n🏷️  TAGS APPLIED")
tag_counts = Counter(all_tags)
for tag, count in tag_counts.most_common(10):
    print(f"   {tag}: {count}x")

# Speakers
if speaker_counts:
    print(f"\n🎤 SPEAKERS DETECTED")
    for speaker, count in speaker_counts.most_common():
        print(f"   {speaker}: {count} chunks")

# Embeddings analysis
print(f"\n🧠 EMBEDDINGS")
try:
    cur.execute("SELECT type, COUNT(*) FROM embeddings GROUP BY type")
    for row in cur.fetchall():
        emb_type, count = row
        print(f"   {emb_type}: {count}")
except:
    print(f"   Total embeddings: {embeddings_count}")

# Links analysis
if links_count > 0:
    print(f"\n🔗 KNOWLEDGE GRAPH LINKS")
    try:
        cur.execute("SELECT link_type, COUNT(*) FROM links GROUP BY link_type")
        for row in cur.fetchall():
            link_type, count = row
            print(f"   {link_type}: {count}")
    except:
        print(f"   Total links: {links_count}")

# FAISS indices check
print(f"\n📦 FAISS INDICES")
faiss_paths = [
    ('Text', 'L:/_DATA/GoodQ_Data/faiss_indices/text/faiss_text.index'),
    ('DINO', 'L:/_DATA/GoodQ_Data/faiss_indices/dino/faiss_dino.index'),
    ('CLIP', 'L:/_DATA/GoodQ_Data/faiss_indices/clip/faiss_clip.index'),
    ('Audio', 'L:/_DATA/GoodQ_Data/faiss_indices/audio/faiss_audio.index'),
]

for name, path in faiss_paths:
    if Path(path).exists():
        size_kb = Path(path).stat().st_size / 1024
        print(f"   {name}: {size_kb:.1f} KB")
    else:
        print(f"   {name}: missing")

# Step runs summary
print(f"\n⚙️  PROCESSING STEPS")
step_log = Path('L:/_DATA/GoodQ_Data/logs/step_runs.jsonl')
if step_log.exists():
    steps = []
    with open(step_log) as f:
        for line in f:
            steps.append(json.loads(line))
    
    step_counts = Counter(s['step'] for s in steps)
    print(f"   Total step executions: {len(steps)}")
    print(f"   Unique steps: {len(step_counts)}")
    print(f"\n   Most frequent steps:")
    for step, count in step_counts.most_common(10):
        print(f"      {step}: {count}x")
    
    # Timing analysis
    print(f"\n   Slowest steps (avg duration):")
    step_times = {}
    for step in steps:
        name = step['step']
        duration = step.get('duration_ms', 0)
        if name not in step_times:
            step_times[name] = []
        step_times[name].append(duration)
    
    avg_times = {name: sum(times)/len(times) for name, times in step_times.items()}
    for step, avg_ms in sorted(avg_times.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"      {step}: {avg_ms:.0f}ms avg")

conn.close()

print("\n" + "=" * 70)
print("✅ ANALYSIS COMPLETE")
print("=" * 70)
