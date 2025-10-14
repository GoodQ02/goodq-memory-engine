"""Quick database check"""
import sqlite3

db_path = r'L:/goodq4all/data/memory.db'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get tables
tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"Tables: {[t[0] for t in tables]}")

# Count scenes
scene_count = cursor.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]
print(f"Scenes: {scene_count}")

# Count embeddings  
emb_count = cursor.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
print(f"Embeddings: {emb_count}")

# Get sample scene if any
if scene_count > 0:
    sample = cursor.execute("SELECT * FROM scenes LIMIT 1").fetchone()
    print(f"\nSample scene columns: {[desc[0] for desc in cursor.description]}")
    print(f"Sample scene data: {sample}")

conn.close()
