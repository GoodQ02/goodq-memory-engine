#!/usr/bin/env python3
"""Quick database inspection script"""
import sqlite3
import json

def inspect_db(db_path, name):
    print(f"\n{'='*60}")
    print(f"{name}: {db_path}")
    print('='*60)
    
    try:
        conn = sqlite3.connect(db_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f"Tables: {[t[0] for t in tables]}\n")
        
        for table in tables:
            table_name = table[0]
            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            schema = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            cols = [s[1] for s in schema]
            print(f"{table_name}: {count} rows")
            print(f"  Columns: {', '.join(cols)}")
            
            # Show sample row if exists
            if count > 0:
                sample = conn.execute(f"SELECT * FROM {table_name} LIMIT 1").fetchone()
                print(f"  Sample: {dict(zip(cols, sample))}")
            print()
        conn.close()
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    inspect_db("L:/goodq4all/data/memory.db", "Memory Database")
    inspect_db("L:/goodq4all/data/knowledge_graph.db", "Knowledge Graph")
