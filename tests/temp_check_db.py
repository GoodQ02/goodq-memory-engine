import sqlite3

conn = sqlite3.connect('L:/_DATA/GoodQ_Data/memory.db')
c = conn.cursor()

# Get all tables
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('=== TABLES ===')
for t in tables:
    print(f'  {t[0]}')
    
# Check segments
print('\n=== SEGMENTS ===')
segments = c.execute('SELECT COUNT(*) FROM segments').fetchone()[0]
print(f'Total segments: {segments}')
if segments > 0:
    sample = c.execute('SELECT video_path, scene_id, start_time, end_time FROM segments LIMIT 3').fetchall()
    for s in sample:
        print(f'  {s}')

# Check embeddings
print('\n=== EMBEDDINGS ===')
embeddings = c.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0]
print(f'Total embeddings: {embeddings}')
if embeddings > 0:
    sample = c.execute('SELECT segment_id, modality, model, LENGTH(embedding) FROM embeddings LIMIT 5').fetchall()
    for e in sample:
        print(f'  {e}')

# Check scenes
print('\n=== SCENES ===')
scenes = c.execute('SELECT COUNT(*) FROM scenes').fetchone()[0]
print(f'Total scenes: {scenes}')
if scenes > 0:
    sample = c.execute('SELECT scene_id, video_path, scene_index FROM scenes LIMIT 3').fetchall()
    for s in sample:
        print(f'  Scene: {s}')
        
# Check summaries
print('\n=== SUMMARIES ===')
summaries = c.execute('SELECT COUNT(*) FROM summaries').fetchone()[0]
print(f'Total summaries: {summaries}')
if summaries > 0:
    sample = c.execute('SELECT segment_id, summary_type, LENGTH(summary_text) FROM summaries LIMIT 3').fetchall()
    for s in sample:
        print(f'  {s}')

# Check links
print('\n=== LINKS ===')
links = c.execute('SELECT COUNT(*) FROM links').fetchone()[0]
print(f'Total links: {links}')
if links > 0:
    sample = c.execute('SELECT link_type, source_type, target_type FROM links LIMIT 5').fetchall()
    for l in sample:
        print(f'  {l}')

conn.close()
