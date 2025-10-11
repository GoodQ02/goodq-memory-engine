"""Quick diagnostic script to check database state"""
import sqlite3
from pathlib import Path

db_paths = [
    Path("L:/goodq4all/data/memory.db"),
    Path("L:/_DATA/GoodQ_Data/data/memory_db/memory.db"),
]

for db_path in db_paths:
    if db_path.exists() and db_path.stat().st_size > 0:
        print(f"\n{'='*60}")
        print(f"Database: {db_path}")
        print(f"Size: {db_path.stat().st_size} bytes")
        print('='*60)
        
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Count records
            scenes_count = cursor.execute('SELECT COUNT(*) FROM scenes').fetchone()[0]
            embeddings_count = cursor.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0]
            
            print(f"Scenes: {scenes_count}")
            print(f"Embeddings: {embeddings_count}")
            
            if scenes_count > 0:
                print("\nRecent scenes:")
                for row in cursor.execute('SELECT video_id, scene_idx, start_time, end_time FROM scenes ORDER BY rowid DESC LIMIT 5').fetchall():
                    print(f"  Video: {row[0]}, Scene: {row[1]}, Time: {row[2]:.1f}-{row[3]:.1f}s")
            
            if embeddings_count > 0:
                print("\nEmbedding types:")
                for row in cursor.execute('SELECT embedding_type, COUNT(*) FROM embeddings GROUP BY embedding_type').fetchall():
                    print(f"  {row[0]}: {row[1]}")
            
            conn.close()
        except Exception as e:
            print(f"Error reading database: {e}")
    else:
        print(f"\n{db_path}: Not found or empty")
