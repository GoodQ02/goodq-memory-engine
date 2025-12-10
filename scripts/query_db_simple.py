import sqlite3
import json

conn = sqlite3.connect('L:/_DATA/GoodQ_Data/memory.db')
c = conn.cursor()

# Check tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = c.fetchall()
print(f'Tables: {[t[0] for t in tables]}')
print()

# Count rows in each table
for table in tables:
    c.execute(f'SELECT COUNT(*) FROM {table[0]}')
    count = c.fetchone()[0]
    print(f'{table[0]}: {count} rows')

print()

# Check scenes
c.execute('SELECT COUNT(*) FROM scenes')
scene_count = c.fetchone()[0]
print(f'Total scenes: {scene_count}')

if scene_count > 0:
    c.execute('SELECT * FROM scenes LIMIT 1')
    row = c.fetchone()
    c.execute("PRAGMA table_info(scenes)")
    cols = [col[1] for col in c.fetchall()]
    print(f'Scene columns: {cols}')
    print(f'Sample scene: {row}')

conn.close()
