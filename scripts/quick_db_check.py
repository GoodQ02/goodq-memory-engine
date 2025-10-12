#!/usr/bin/env python3
"""Quick database structure check"""
import sqlite3
import os

db_path = r'L:\_DATA\GoodQ_Data\memory\goodq.db'

if not os.path.exists(db_path):
    print(f"❌ Database does not exist: {db_path}")
    exit(1)

print(f"✓ Database exists: {db_path}")
print(f"  Size: {os.path.getsize(db_path) / (1024*1024):.2f} MB\n")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Get all tables
tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()

if not tables:
    print("❌ NO TABLES FOUND IN DATABASE!")
else:
    print(f"✓ Found {len(tables)} table(s):\n")
    for (table_name,) in tables:
        # Get row count
        count = cur.execute(f"SELECT COUNT(*) FROM `{table_name}`").fetchone()[0]
        
        # Get columns
        columns = cur.execute(f"PRAGMA table_info(`{table_name}`)").fetchall()
        col_names = [col[1] for col in columns]
        
        print(f"  📊 {table_name}: {count} rows")
        print(f"     Columns: {', '.join(col_names[:5])}" + ("..." if len(col_names) > 5 else ""))
        
        # Show sample row if exists
        if count > 0:
            sample = cur.execute(f"SELECT * FROM `{table_name}` LIMIT 1").fetchone()
            print(f"     Sample: {str(sample)[:100]}...")
        print()

conn.close()
