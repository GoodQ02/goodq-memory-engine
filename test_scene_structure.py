import sqlite3
import json

conn = sqlite3.connect('data/memory.db')
cur = conn.cursor()

# Get first scene
scene = cur.execute('SELECT * FROM scenes LIMIT 1').fetchone()
cols = [d[0] for d in cur.description]

print('Available columns in scenes table:')
for i, col in enumerate(cols):
    value = scene[i] if i < len(scene) else None
    print(f'  {col}: {value}')

conn.close()
