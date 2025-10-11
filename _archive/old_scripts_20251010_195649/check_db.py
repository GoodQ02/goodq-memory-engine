import sqlite3
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else "L:/_DATA/GoodQ_Data/data/memory_db/memory.db"

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall()]
    print(f"Tables: {tables}")
    
    # Count rows in each table
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"{table}: {count} rows")
        except Exception as e:
            print(f"{table}: Error - {e}")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
