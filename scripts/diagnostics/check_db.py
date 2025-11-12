import sqlite3

conn = sqlite3.connect('data/memory.db')
cur = conn.cursor()

print('=== TABLES ===')
for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
    print(row[0])

print('\n=== SCENES TABLE SCHEMA ===')
try:
    for row in cur.execute('PRAGMA table_info(scenes)').fetchall():
        print(f'{row[1]}: {row[2]}')
    
    print('\n=== SCENES COUNT & SAMPLE ===')
    count = cur.execute('SELECT COUNT(*) FROM scenes').fetchone()[0]
    print(f'Total scenes: {count}')
    
    if count > 0:
        sample = cur.execute('SELECT * FROM scenes LIMIT 3').fetchall()
        for s in sample:
            print(s)
except Exception as e:
    print(f"Error: {e}")

conn.close()
