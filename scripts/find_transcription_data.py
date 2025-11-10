import sqlite3
import json

db_path = "data/memory.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== SEARCHING FOR TRANSCRIPTION DATA ===\n")

# Get video hash
cursor.execute("SELECT DISTINCT video_hash FROM scenes LIMIT 1")
video_hash = cursor.fetchone()[0]

# Check if there's a transcript/text field in segments
cursor.execute("PRAGMA table_info(segments)")
segment_columns = [col[1] for col in cursor.fetchall()]
print(f"Segment table columns: {segment_columns}\n")

# Get sample segments with all fields
cursor.execute(f"SELECT * FROM segments LIMIT 5")
segments = cursor.fetchall()
print(f"Sample segments ({len(segments)}):")
for seg in segments:
    print(f"  {seg}\n")

# Check if there's any text-based data in links or other tables
cursor.execute("""
    SELECT hash, modality, source_path, created_at 
    FROM embeddings 
    WHERE modality LIKE '%text%'
    LIMIT 10
""")
text_embeddings = cursor.fetchall()
print(f"\nText-based embeddings ({len(text_embeddings)}):")
for emb in text_embeddings:
    print(f"  {emb[1]}: {emb[2]}")

# Check if scenes table has any text data in meta
cursor.execute("SELECT id, start, end, meta FROM scenes LIMIT 3")
scenes = cursor.fetchall()
print(f"\n\nScene metadata samples:")
for scene in scenes:
    meta = json.loads(scene[3]) if scene[3] else {}
    print(f"\nScene {scene[0][:16]}...")
    print(f"  Time: {scene[1]:.2f}s - {scene[2]:.2f}s")
    
    # Check if meta has any useful data
    keys_to_check = ['transcription', 'transcript', 'text', 'caption', 'description', 
                     'objects', 'faces', 'ocr', 'emotion', 'sentiment']
    
    for key in keys_to_check:
        if key in meta:
            value = meta[key]
            if isinstance(value, str):
                print(f"  {key}: {value[:100]}...")
            else:
                print(f"  {key}: {value}")
    
    # Print all keys
    print(f"  All meta keys: {list(meta.keys())}")

conn.close()

print("\n\n=== CHECKING FILE SYSTEM FOR INTERMEDIATE DATA ===")

import os

# Check for any JSON files that might have analysis results
search_paths = [
    "logs/test_full_sample",
    "output",
    "data",
]

for search_path in search_paths:
    if os.path.exists(search_path):
        for root, dirs, files in os.walk(search_path):
            for file in files:
                if file.endswith('.json') and 'scene' not in file.lower():
                    filepath = os.path.join(root, file)
                    print(f"\nFound JSON: {filepath}")
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, dict):
                                print(f"  Keys: {list(data.keys())[:10]}")
                            elif isinstance(data, list) and len(data) > 0:
                                print(f"  List with {len(data)} items")
                                if isinstance(data[0], dict):
                                    print(f"  First item keys: {list(data[0].keys())[:10]}")
                    except Exception as e:
                        print(f"  Error reading: {e}")
