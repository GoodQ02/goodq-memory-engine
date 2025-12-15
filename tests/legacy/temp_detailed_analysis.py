import sqlite3
import json
from pathlib import Path

conn = sqlite3.connect('data/memory.db')
cursor = conn.cursor()

print("=" * 80)
print("DETAILED DATABASE ANALYSIS FOR SAMPLE.MP4")
print("=" * 80)

# First, let's look at the scenes table more carefully
print("\n--- SCENES TABLE FULL DATA ---")
cursor.execute("SELECT * FROM scenes")
scenes = cursor.fetchall()
cursor.execute("PRAGMA table_info(scenes)")
scene_cols = [col[1] for col in cursor.fetchall()]

for scene in scenes:
    print(f"\nScene record:")
    for i, col in enumerate(scene_cols):
        value = scene[i]
        if col == 'meta' and value:
            try:
                meta_data = json.loads(value)
                print(f"  {col}:")
                for key, val in meta_data.items():
                    if isinstance(val, dict):
                        print(f"    {key}: {json.dumps(val, indent=6)}")
                    else:
                        print(f"    {key}: {val}")
            except:
                print(f"  {col}: {value[:200] if len(str(value)) > 200 else value}")
        else:
            print(f"  {col}: {value}")

# Check embeddings
print("\n--- EMBEDDINGS TABLE FULL DATA ---")
cursor.execute("SELECT * FROM embeddings")
embeddings = cursor.fetchall()
cursor.execute("PRAGMA table_info(embeddings)")
emb_cols = [col[1] for col in cursor.fetchall()]

for emb in embeddings:
    print(f"\nEmbedding record:")
    for i, col in enumerate(emb_cols):
        value = emb[i]
        print(f"  {col}: {value if col != 'embedding' else f'<vector data>'}")

# Get video hash from scene
if scenes:
    video_hash = scenes[0][1]  # video_hash is second column
    print(f"\n--- VIDEO HASH: {video_hash} ---")
    
    # Check all tables for this hash
    print("\n--- SEARCHING ALL TABLES FOR THIS HASH ---")
    
    # Scenes
    cursor.execute("SELECT COUNT(*) FROM scenes WHERE video_hash = ?", (video_hash,))
    print(f"Scenes with this hash: {cursor.fetchone()[0]}")
    
    # Segments
    cursor.execute("SELECT COUNT(*) FROM segments WHERE video_hash = ?", (video_hash,))
    print(f"Segments with this hash: {cursor.fetchone()[0]}")
    
    # Links
    cursor.execute("SELECT COUNT(*) FROM links WHERE parent_hash = ? OR child_hash = ?", (video_hash, video_hash))
    print(f"Links involving this hash: {cursor.fetchone()[0]}")

# Check if there are JSON files in the workspace
print("\n--- CHECKING WORKSPACE FOR ADDITIONAL OUTPUT ---")
workspace_path = Path('logs/test_workspace')
if workspace_path.exists():
    for json_file in workspace_path.rglob('*.json'):
        print(f"\nFound JSON file: {json_file}")
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                print(f"  Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        except Exception as e:
            print(f"  Error reading: {e}")

# Check if there are other output files
for ext in ['*.txt', '*.csv', '*.jsonl']:
    for file in workspace_path.rglob(ext):
        print(f"\nFound {ext} file: {file}")
        print(f"  Size: {file.stat().st_size} bytes")

conn.close()

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
