#!/usr/bin/env python3
import sqlite3

db_path = r"L:\_DATA\GoodQ_Data\data\memory_db\memory.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

print("="*70)
print("DATABASE SCHEMA")
print("="*70)

schemas = c.execute("SELECT name, sql FROM sqlite_master WHERE type='table'").fetchall()

for name, sql in schemas:
    if sql:
        print(f"\n{name}:")
        print("-" * 70)
        print(sql)
        print()

conn.close()
