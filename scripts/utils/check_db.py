import sqlite3
from pathlib import Path

db_path = Path('data/memory.db')
if not db_path.exists():
    print('[FAIL] Database not found')
    exit(1)

conn = sqlite3.connect(str(db_path))
c = conn.cursor()

try:
    c.execute('SELECT COUNT(*) FROM scenes')
    scenes = c.fetchone()[0]
    print(f'[SYMBOL] Scenes: {scenes}')
    
    c.execute('SELECT COUNT(*) FROM embeddings')
    embeddings = c.fetchone()[0]
    print(f'[SYMBOL] Embeddings: {embeddings}')
    
    c.execute('SELECT COUNT(*) FROM segments')
    segments = c.fetchone()[0]
    print(f'[SYMBOL] Segments: {segments}')
    
    c.execute('SELECT COUNT(*) FROM entities')
    entities = c.fetchone()[0]
    print(f'[SYMBOL] Entities: {entities}')
    
    c.execute('SELECT COUNT(*) FROM relationships')
    relationships = c.fetchone()[0]
    print(f'[SYMBOL] Relationships: {relationships}')
    
    c.execute('SELECT video_name, COUNT(*) FROM scenes GROUP BY video_name')
    print(f'\n[STATS] Scenes by video:')
    for row in c.fetchall():
        print(f'  {row[0]}: {row[1]} scenes')
    
    c.execute('''SELECT scene_id, start_time, end_time, 
                 (end_time - start_time) as duration 
                 FROM scenes 
                 ORDER BY duration DESC LIMIT 10''')
    print(f'\n[TIMER]  Top 10 longest scenes:')
    for row in c.fetchall():
        print(f'  Scene {row[0]}: {row[1]:.1f}s - {row[2]:.1f}s (duration: {row[3]:.1f}s)')
    
    c.execute('''SELECT scene_id, start_time, end_time, 
                 (end_time - start_time) as duration 
                 FROM scenes 
                 ORDER BY duration ASC LIMIT 10''')
    print(f'\n[WARN]  Top 10 shortest scenes:')
    for row in c.fetchall():
        print(f'  Scene {row[0]}: {row[1]:.1f}s - {row[2]:.1f}s (duration: {row[3]:.1f}s)')

except sqlite3.OperationalError as e:
    print(f'[FAIL] Error: {e}')
finally:
    conn.close()
