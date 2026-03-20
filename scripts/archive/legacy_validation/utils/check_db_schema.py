#!/usr/bin/env python3
"""Check database schema and tables."""

import sqlite3
import os

db_path = "L:\\goodq4all\\data\\memory.db"

if not os.path.exists(db_path):
    print(f"DATABASE DOES NOT EXIST: {db_path}")
    exit(1)

print(f"Database exists: {db_path}")
print(f"Size: {os.path.getsize(db_path) / 1024 / 1024:.2f} MB\n")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all tables
tables = cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()

print(f"=== TABLES IN DATABASE ({len(tables)}) ===\n")
for (table_name,) in tables:
    print(f"  {table_name}")
    
    # Get row count
    try:
        count = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"    Rows: {count}")
    except Exception as e:
        print(f"    Error counting: {e}")
    
    # Get schema
    schema = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    print(f"    Columns:")
    for col in schema:
        print(f"      {col[1]} ({col[2]})")
    print()

conn.close()
