import sqlite3
import json
import os

# Check database for scene data
db_path = "data/memory.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("=== DATABASE TABLES ===")
    for table in tables:
        print(f"  - {table[0]}")
    
    # Check for videos table
    cursor.execute("SELECT COUNT(*) FROM videos WHERE filename LIKE '%sample%'")
    video_count = cursor.fetchone()[0]
    print(f"\n=== VIDEOS (sample) ===")
    print(f"Count: {video_count}")
    
    if video_count > 0:
        cursor.execute("SELECT id, filename, status, created_at FROM videos WHERE filename LIKE '%sample%'")
        for row in cursor.fetchall():
            print(f"  ID: {row[0]}, File: {row[1]}, Status: {row[2]}, Created: {row[3]}")
            video_id = row[0]
            
            # Check scenes for this video
            cursor.execute("SELECT COUNT(*) FROM scenes WHERE video_id = ?", (video_id,))
            scene_count = cursor.fetchone()[0]
            print(f"  Scenes: {scene_count}")
            
            if scene_count > 0:
                cursor.execute("""
                    SELECT scene_number, start_time, end_time, duration 
                    FROM scenes WHERE video_id = ? 
                    ORDER BY scene_number
                """, (video_id,))
                scenes = cursor.fetchall()
                print(f"\n  === SCENE DETAILS ===")
                for scene in scenes:
                    print(f"    Scene {scene[0]}: {scene[1]:.2f}s - {scene[2]:.2f}s (duration: {scene[3]:.2f}s)")
                
                # Check transcriptions
                cursor.execute("SELECT COUNT(*) FROM transcriptions WHERE video_id = ?", (video_id,))
                trans_count = cursor.fetchone()[0]
                print(f"\n  Transcriptions: {trans_count}")
                
                if trans_count > 0:
                    cursor.execute("""
                        SELECT scene_number, text, confidence 
                        FROM transcriptions WHERE video_id = ? 
                        ORDER BY scene_number 
                        LIMIT 5
                    """, (video_id,))
                    trans = cursor.fetchall()
                    print(f"  Sample transcriptions:")
                    for t in trans:
                        print(f"    Scene {t[0]}: {t[1][:100]}... (conf: {t[2]:.2f})")
                
                # Check image analysis
                cursor.execute("SELECT COUNT(*) FROM image_analysis WHERE video_id = ?", (video_id,))
                img_count = cursor.fetchone()[0]
                print(f"\n  Image analyses: {img_count}")
                
                if img_count > 0:
                    cursor.execute("""
                        SELECT scene_number, caption, detected_objects 
                        FROM image_analysis WHERE video_id = ? 
                        ORDER BY scene_number 
                        LIMIT 5
                    """, (video_id,))
                    imgs = cursor.fetchall()
                    print(f"  Sample image analyses:")
                    for img in imgs:
                        print(f"    Scene {img[0]}: {img[1][:80]}...")
                        if img[2]:
                            print(f"      Objects: {img[2][:80]}...")
                
                # Check embeddings
                cursor.execute("SELECT COUNT(*) FROM embeddings WHERE video_id = ?", (video_id,))
                emb_count = cursor.fetchone()[0]
                print(f"\n  Embeddings: {emb_count}")
    
    conn.close()
else:
    print(f"Database not found at {db_path}")

# Check for JSON output files
print("\n\n=== CHECKING FOR JSON OUTPUT FILES ===")
output_dir = "output"
if os.path.exists(output_dir):
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            if 'sample' in file.lower() and file.endswith('.json'):
                filepath = os.path.join(root, file)
                print(f"\nFound: {filepath}")
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    print(f"  Keys: {list(data.keys())}")
else:
    print("Output directory not found")

# Check logs directory for scene files
print("\n\n=== SCENE FILES IN LOGS ===")
scene_dir = "logs/test_full_sample/sample"
if os.path.exists(scene_dir):
    frames = len([f for f in os.listdir(f"{scene_dir}/frames") if f.endswith('.jpg')])
    audio = len([f for f in os.listdir(f"{scene_dir}/audio") if f.endswith('.wav')])
    print(f"Frames extracted: {frames}")
    print(f"Audio clips extracted: {audio}")
else:
    print("Scene directory not found")
