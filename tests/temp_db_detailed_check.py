import sqlite3
import json

conn = sqlite3.connect('L:/_DATA/GoodQ_Data/memory.db')
c = conn.cursor()

print('='*60)
print('DATABASE CONTENTS CHECK')
print('='*60)

# Check embeddings
print('\n=== EMBEDDINGS ===')
embeddings = c.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0]
print(f'Total embeddings: {embeddings}')
if embeddings > 0:
    sample = c.execute('SELECT hash, modality, source_path, scene_id, sentiment_label, sentiment_score FROM embeddings LIMIT 5').fetchall()
    for e in sample:
        print(f'  Hash: {e[0][:16]}... | Modality: {e[1]} | Path: {e[2]} | Scene: {e[3][:16] if e[3] else None}... | Sentiment: {e[4]} ({e[5]})')

# Check scenes
print('\n=== SCENES ===')
scenes = c.execute('SELECT COUNT(*) FROM scenes').fetchone()[0]
print(f'Total scenes: {scenes}')
if scenes > 0:
    sample = c.execute('SELECT id, video_hash, start, end, meta FROM scenes LIMIT 5').fetchall()
    for s in sample:
        meta = json.loads(s[4]) if s[4] else {}
        print(f'  ID: {s[0][:16]}... | Video: {s[1][:16] if s[1] else None}... | Time: {s[2]}-{s[3]}s')
        if meta:
            print(f'    Meta keys: {list(meta.keys())}')

# Check segments
print('\n=== SEGMENTS ===')
segments = c.execute('SELECT COUNT(*) FROM segments').fetchone()[0]
print(f'Total segments: {segments}')
if segments > 0:
    sample = c.execute('SELECT id, video_hash, start, end, speaker, meta FROM segments LIMIT 5').fetchall()
    for s in sample:
        meta = json.loads(s[5]) if s[5] else {}
        print(f'  ID: {s[0][:16]}... | Video: {s[1][:16] if s[1] else None}... | Time: {s[2]}-{s[3]}s | Speaker: {s[4]}')
        if meta:
            print(f'    Meta keys: {list(meta.keys())}')

# Check summaries
print('\n=== SUMMARIES ===')
summaries = c.execute('SELECT COUNT(*) FROM summaries').fetchone()[0]
print(f'Total summaries: {summaries}')
if summaries > 0:
    sample = c.execute('SELECT id, summary_type, category, LENGTH(content), content FROM summaries LIMIT 5').fetchall()
    for s in sample:
        print(f'  ID: {s[0]} | Type: {s[1]} | Category: {s[2]} | Length: {s[3]}')
        print(f'    Content preview: {s[4][:100]}...')

# Check links
print('\n=== LINKS ===')
links = c.execute('SELECT COUNT(*) FROM links').fetchone()[0]
print(f'Total links: {links}')
if links > 0:
    sample = c.execute('SELECT parent_hash, child_hash, relation, meta FROM links LIMIT 10').fetchall()
    for l in sample:
        print(f'  {l[0][:16]}... -> {l[1][:16]}... [{l[2]}]')

print('\n' + '='*60)
print('CHECKING FAISS INDICES')
print('='*60)

import os
faiss_dir = 'L:/_DATA/GoodQ_Data/faiss_indices'
for root, dirs, files in os.walk(faiss_dir):
    for f in files:
        path = os.path.join(root, f)
        size = os.path.getsize(path)
        print(f'  {path}: {size:,} bytes')

conn.close()
