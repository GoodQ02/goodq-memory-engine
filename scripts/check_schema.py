"""Check actual database schema and data"""
import sqlite3
from pathlib import Path

db_path = Path("L:/goodq4all/data/memory.db")

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

print("=" * 70)
print("DATABASE SCHEMA")
print("=" * 70)

# Get all tables
tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"\nTables: {[t[0] for t in tables]}\n")

for table in tables:
    table_name = table[0]
    print(f"\n--- {table_name} ---")
    
    # Get schema
    schema = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    for col in schema:
        print(f"  {col[1]} ({col[2]})")
    
    # Get count
    count = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    print(f"  Total rows: {count}")
    
    # Get sample
    if count > 0:
        print(f"  Sample data (first 3 rows):")
        sample = cursor.execute(f"SELECT * FROM {table_name} LIMIT 3").fetchall()
        for i, row in enumerate(sample, 1):
            print(f"    Row {i}: {row[:5]}...")  # First 5 columns

print("\n" + "=" * 70)
print("DETAILED SCENE DATA")
print("=" * 70)

scenes = cursor.execute("SELECT * FROM scenes LIMIT 5").fetchall()
for scene in scenes:
    print(f"\nScene: {scene}")

print("\n" + "=" * 70)
print("DETAILED EMBEDDING DATA")
print("=" * 70)

# Check embedding types
emb_types = cursor.execute("SELECT embedding_type, COUNT(*) FROM embeddings GROUP BY embedding_type").fetchall()
for emb_type, count in emb_types:
    print(f"\n{emb_type}: {count} embeddings")
    sample = cursor.execute("SELECT scene_id, source_type FROM embeddings WHERE embedding_type=? LIMIT 3", (emb_type,)).fetchall()
    for s in sample:
        print(f"  Scene ID: {s[0]}, Source: {s[1]}")

conn.close()
