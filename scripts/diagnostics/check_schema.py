#!/usr/bin/env python3
import sqlite3
from pathlib import Path

db_path = Path("data/memory.db")
if db_path.exists():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print("=== memory.db tables ===")
    for t in tables:
        print(f"  - {t[0]}")
        cols = cur.execute(f"PRAGMA table_info({t[0]})").fetchall()
        for col in cols:
            print(f"      {col[1]} ({col[2]})")
    conn.close()

db_path2 = Path("data/unified_goodq.db")
if db_path2.exists():
    conn = sqlite3.connect(db_path2)
    cur = conn.cursor()
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print("\n=== unified_goodq.db tables ===")
    for t in tables:
        print(f"  - {t[0]}")
        cols = cur.execute(f"PRAGMA table_info({t[0]})").fetchall()
        for col in cols:
            print(f"      {col[1]} ({col[2]})")
    conn.close()
