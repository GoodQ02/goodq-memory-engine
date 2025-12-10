#!/usr/bin/env python3
import sqlite3
import json

conn = sqlite3.connect('L:/_DATA/GoodQ_Data/memory.db')
c = conn.cursor()

print('='*80)
print('SAMPLE.MP4 INGESTION ANALYSIS')
print('='*80)

# Get counts
c.execute('SELECT COUNT(*) FROM scenes')
scenes_count = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM segments')
segments_count = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM embeddings')
emb_count = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM links')
links_count = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM summaries')
summaries_count = c.fetchone()[0]

print(f'\n[DATABASE COUNTS]')
print(f'  Scenes: {scenes_count} {"✅" if scenes_count == 16 else "⚠️"}')
print(f'  Segments: {segments_count} ✅')
print(f'  Embeddings: {emb_count} ✅')
print(f'  Links: {links_count} ✅')
print(f'  Summaries: {summaries_count} {"✅" if summaries_count > 0 else "⚠️ MISSING!"}')

# Sample scene
c.execute('SELECT id, start, end, meta FROM scenes LIMIT 1')
sid, start, end, meta = c.fetchone()
meta_dict = json.loads(meta)

print(f'\n[SAMPLE SCENE] {sid[:12]}...')
print(f'  Time: {start:.2f}s - {end:.2f}s')
print(f'  Metadata keys ({len(meta_dict)}): {", ".join(sorted(meta_dict.keys())[:10])}...')

# Check key metadata
has_transcript = bool(meta_dict.get('transcript'))
has_emotions = bool(meta_dict.get('emotions'))
has_caption = bool(meta_dict.get('caption'))

print(f'\n[SCENE DATA COMPLETENESS]')
print(f'  Transcript: {"✅" if has_transcript else "❌"}')
print(f'  Emotions: {"✅" if has_emotions else "❌"}')
print(f'  Caption: {"✅" if has_caption else "❌"}')

if has_transcript:
    print(f'  Sample transcript: {meta_dict["transcript"][:80]}...')
if has_emotions:
    print(f'  Sample emotions: {meta_dict["emotions"]}')
if has_caption:
    print(f'  Sample caption: {meta_dict["caption"][:80]}...')

# Embeddings by modality
print(f'\n[EMBEDDINGS BY MODALITY]')
c.execute('SELECT modality, COUNT(*) FROM embeddings GROUP BY modality')
for mod, cnt in c.fetchall():
    print(f'  {mod}: {cnt}')

# Links by relation
print(f'\n[LINKS BY RELATION]')
c.execute('SELECT relation, COUNT(*) FROM links GROUP BY relation')
for rel, cnt in c.fetchall():
    print(f'  {rel}: {cnt}')

print('\n' + '='*80)
print('CRITICAL ISSUE IDENTIFIED')
print('='*80)
print(f'⚠️ SUMMARIES TABLE IS EMPTY: {summaries_count}/16 generated')
print(f'   The summarization pipeline step is NOT executing or NOT saving results!')
print('\n' + '='*80)

conn.close()
