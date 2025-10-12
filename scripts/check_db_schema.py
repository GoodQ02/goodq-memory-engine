#!/usr/bin/env python3
"""Check database schema"""
import sqlite3
from pathlib import Path

db_path = Path("L:/goodq4all/data/memory.db")
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

print("\n=== Memory Database Schema ===\n")
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table'")
for row in cursor.fetchall():
    print(row[0])
    print()

conn.close()
