import sqlite3
import os

db_path = "data/memory.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("=== DATABASE SCHEMA ===\n")
    for table in tables:
        table_name = table[0]
        print(f"\n--- {table_name.upper()} ---")
        
        # Get schema
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        print("Columns:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"Row count: {count}")
        
        # Show sample data
        if count > 0:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            rows = cursor.fetchall()
            print(f"Sample data (first 3 rows):")
            for row in rows:
                # Truncate long strings
                truncated_row = []
                for item in row:
                    if isinstance(item, str) and len(item) > 100:
                        truncated_row.append(item[:100] + "...")
                    elif isinstance(item, bytes):
                        truncated_row.append(f"<binary data {len(item)} bytes>")
                    else:
                        truncated_row.append(item)
                print(f"  {truncated_row}")
    
    conn.close()
else:
    print(f"Database not found at {db_path}")

# Check scene files
print("\n\n=== SCENE FILES ===")
scene_dir = "logs/test_full_sample/sample"
if os.path.exists(scene_dir):
    if os.path.exists(f"{scene_dir}/frames"):
        frames = sorted([f for f in os.listdir(f"{scene_dir}/frames") if f.endswith('.jpg')])
        print(f"\nFrames ({len(frames)}):")
        for f in frames:
            print(f"  {f}")
    
    if os.path.exists(f"{scene_dir}/audio"):
        audio = sorted([f for f in os.listdir(f"{scene_dir}/audio") if f.endswith('.wav')])
        print(f"\nAudio clips ({len(audio)}):")
        for f in audio:
            print(f"  {f}")
