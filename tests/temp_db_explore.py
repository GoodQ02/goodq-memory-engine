import sqlite3
import json

# Connect to database
conn = sqlite3.connect('data/memory.db')
cursor = conn.cursor()

print("=" * 80)
print("DATABASE STRUCTURE ANALYSIS")
print("=" * 80)

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print(f"\nTables found: {len(tables)}")

for table in tables:
    print(f"\n--- TABLE: {table} ---")
    cursor.execute(f"PRAGMA table_info({table})")
    columns = cursor.fetchall()
    print("Columns:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"Total records: {count}")
    
    if count > 0 and count < 100:
        cursor.execute(f"SELECT * FROM {table} LIMIT 5")
        rows = cursor.fetchall()
        print(f"\nSample data (first 5 rows):")
        col_names = [col[1] for col in columns]
        for row in rows:
            print(f"\n  Record:")
            for i, col_name in enumerate(col_names):
                value = row[i]
                if isinstance(value, str) and len(value) > 200:
                    value = value[:200] + "..."
                print(f"    {col_name}: {value}")

# Check for sample.mp4 references
print("\n" + "=" * 80)
print("SEARCHING FOR SAMPLE.MP4 REFERENCES")
print("=" * 80)

for table in tables:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Look for text columns that might contain filenames
    text_cols = [col for col in columns if 'file' in col.lower() or 'path' in col.lower() or 'source' in col.lower() or 'name' in col.lower() or 'id' in col.lower()]
    
    for col in text_cols:
        try:
            cursor.execute(f"SELECT * FROM {table} WHERE {col} LIKE '%sample%' LIMIT 3")
            results = cursor.fetchall()
            if results:
                print(f"\n{table}.{col} contains 'sample':")
                col_names = [c[1] for c in cursor.execute(f"PRAGMA table_info({table})").fetchall()]
                for row in results:
                    print(f"  Found:")
                    for i, col_name in enumerate(col_names):
                        value = row[i]
                        if isinstance(value, str) and len(value) > 150:
                            value = value[:150] + "..."
                        print(f"    {col_name}: {value}")
        except:
            pass

conn.close()

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
