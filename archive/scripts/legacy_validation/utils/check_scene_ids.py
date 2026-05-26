import sqlite3

conn = sqlite3.connect('L:/_DATA/GoodQ_Data/memory.db')
cur = conn.cursor()

print("Embeddings by scene_id:")
cur.execute('SELECT scene_id, COUNT(*) FROM embeddings GROUP BY scene_id')
for row in cur.fetchall():
    scene_display = row[0][:16] + "..." if row[0] else "NULL"
    print(f'  {scene_display}: {row[1]}')

print("\nSample embeddings with scene_id:")
cur.execute('SELECT hash, modality, scene_id FROM embeddings WHERE scene_id IS NOT NULL LIMIT 5')
for row in cur.fetchall():
    print(f'  Hash: {row[0][:16]}..., Modality: {row[1]}, Scene: {row[2][:16]}...')

conn.close()
