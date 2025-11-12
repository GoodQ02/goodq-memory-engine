import sqlite3
import json

# Check main database
conn = sqlite3.connect('data/memory.db')
cur = conn.cursor()

# Get tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)

# Get counts
stats = {}
for table in ['scenes', 'segments', 'entities', 'relationships', 'embeddings']:
    try:
        cur.execute(f'SELECT COUNT(*) FROM {table}')
        stats[table] = cur.fetchone()[0]
    except:
        stats[table] = 0

print("\nDatabase Stats:")
for k, v in stats.items():
    print(f"  {k}: {v}")

# Check scene schema and data
try:
    cur.execute('PRAGMA table_info(scenes)')
    cols = cur.fetchall()
    print("\nScenes table schema:")
    for col in cols:
        print(f"  {col[1]} ({col[2]})")
    
    # Get first few scenes with actual columns
    cur.execute('SELECT * FROM scenes LIMIT 5')
    rows = cur.fetchall()
    print("\nFirst 5 scenes (raw data):")
    for r in rows:
        print(f"  {r}")
except Exception as e:
    print(f"Error getting scenes: {e}")

# Check for any processing markers
try:
    cur.execute('SELECT video_file, status FROM videos ORDER BY created_at DESC LIMIT 5')
    videos = cur.fetchall()
    print("\nRecent videos:")
    for v in videos:
        print(f"  {v[0]}: {v[1]}")
except Exception as e:
    print(f"No videos table or error: {e}")

conn.close()
