import sqlite3

conn = sqlite3.connect('data/memory.db')
c = conn.cursor()

# Get all tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in c.fetchall()]

print("=" * 60)
print("Database Statistics")
print("=" * 60)

for table in tables:
    try:
        c.execute(f'SELECT COUNT(*) FROM "{table}"')
        count = c.fetchone()[0]
        print(f"{table:30} {count:>10,}")
    except Exception as e:
        print(f"{table:30} ERROR: {e}")

conn.close()
