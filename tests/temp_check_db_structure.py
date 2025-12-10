import sqlite3
from pathlib import Path

# Check memory.db
db_path = Path("L:/_DATA/GoodQ_Data/memory.db")
print(f"=== Checking {db_path} ===")
print(f"Size: {db_path.stat().st_size:,} bytes\n")

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Get tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print(f"Tables ({len(tables)}):")
for table in tables:
    print(f"  - {table}")
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"    Rows: {count}")
    
    # Show sample data for scenes table
    if table == 'scenes' and count > 0:
        cursor.execute(f"SELECT * FROM {table} LIMIT 1")
        row = cursor.fetchone()
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [c[1] for c in cursor.fetchall()]
        print(f"    Columns: {', '.join(columns)}")
        print(f"    Sample: {row[:5] if row else 'None'}...")

conn.close()

# Check knowledge_graph.db
db_path2 = Path("L:/_DATA/GoodQ_Data/knowledge_graph.db")
print(f"\n=== Checking {db_path2} ===")
print(f"Size: {db_path2.stat().st_size:,} bytes\n")

conn2 = sqlite3.connect(str(db_path2))
cursor2 = conn2.cursor()

cursor2.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables2 = [t[0] for t in cursor2.fetchall()]
print(f"Tables ({len(tables2)}):")
for table in tables2:
    print(f"  - {table}")
    cursor2.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor2.fetchone()[0]
    print(f"    Rows: {count}")

conn2.close()
