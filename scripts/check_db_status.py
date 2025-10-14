"""Quick check of memory DB content."""
import sqlite3

conn = sqlite3.connect('L:/goodq4all/data/memory.db')
cur = conn.cursor()

print('=== Memory DB Status ===')
print(f'Scenes: {cur.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]}')
print(f'Embeddings: {cur.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]}')

print('\n=== Schema ===')
cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='scenes'")
schema = cur.fetchone()
if schema:
    print(f'Scenes table: {schema[0][:200]}...')

print('\n=== Recent Scenes ===')
try:
    cur.execute('SELECT * FROM scenes ORDER BY rowid DESC LIMIT 3')
    cols = [desc[0] for desc in cur.description]
    print(f'Columns: {", ".join(cols)}')
    for row in cur.fetchall():
        print(f'  Row: {dict(zip(cols, row))}')
except Exception as e:
    print(f'Error: {e}')

print('\n=== Embedding Types ===')
cur.execute('SELECT embedding_type, COUNT(*) FROM embeddings GROUP BY embedding_type')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

conn.close()
