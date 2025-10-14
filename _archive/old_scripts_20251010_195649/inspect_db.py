"""Quick DB inspection script"""
import sqlite3
import json

db_path = 'L:/goodq4all/data/memory.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get tables
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = [r[0] for r in cursor.fetchall()]
print('Tables:', tables)

# Get scene count
cursor.execute('SELECT COUNT(*) FROM scenes')
scene_count = cursor.fetchone()[0]
print(f'Scene count: {scene_count}')

# Get embedding counts
cursor.execute('SELECT COUNT(*) FROM embeddings')
embedding_count = cursor.fetchone()[0]
print(f'Embedding count: {embedding_count}')

# Get schema
cursor.execute('PRAGMA table_info(scenes)')
scene_columns = cursor.fetchall()
print(f'\nScenes table schema:')
for col in scene_columns:
    print(f'  {col[1]} ({col[2]})')

# Get sample scenes
cursor.execute('SELECT * FROM scenes LIMIT 3')
scenes = cursor.fetchall()
print(f'\nSample scenes:')
for s in scenes:
    print(f'  {s}')

conn.close()
