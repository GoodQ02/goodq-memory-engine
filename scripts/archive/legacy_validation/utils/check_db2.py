import sqlite3
from pathlib import Path

db_path = Path('data/memory.db')
conn = sqlite3.connect(str(db_path))
c = conn.cursor()

# List all tables
c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = c.fetchall()
print('[LOG] Tables in database:')
for table in tables:
    print(f'  - {table[0]}')

# Check scenes
c.execute('SELECT COUNT(*) FROM scenes')
scenes = c.fetchone()[0]
print(f'\n[SYMBOL] Total Scenes: {scenes}')

# Check for sample.mp4 specifically
c.execute('SELECT DISTINCT video_name FROM scenes')
videos = c.fetchall()
print(f'\n[SCENE] Videos in database:')
for v in videos:
    c.execute('SELECT COUNT(*) FROM scenes WHERE video_name = ?', (v[0],))
    count = c.fetchone()[0]
    print(f'  {v[0]}: {count} scenes')

# Show latest scene
c.execute('''SELECT scene_id, video_name, start_time, end_time,  
             (end_time - start_time) as duration
             FROM scenes ORDER BY rowid DESC LIMIT 1''')
row = c.fetchone()
if row:
    print(f'\n[STATS] Latest scene added:')
    print(f'  Scene ID: {row[0]}')
    print(f'  Video: {row[1]}')
    print(f'  Duration: {row[4]:.1f}s ({row[2]:.1f}s - {row[3]:.1f}s)')

conn.close()
