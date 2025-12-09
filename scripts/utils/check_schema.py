import sqlite3
from pathlib import Path

db_path = Path('data/memory.db')
conn = sqlite3.connect(str(db_path))
c = conn.cursor()

# Get schema for each table
c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = c.fetchall()

for table in tables:
    table_name = table[0]
    if table_name != 'sqlite_sequence':
        print(f'\n📋 Table: {table_name}')
        c.execute(f'PRAGMA table_info({table_name})')
        columns = c.fetchall()
        for col in columns:
            print(f'  - {col[1]} ({col[2]})')
        
        # Get count
        c.execute(f'SELECT COUNT(*) FROM {table_name}')
        count = c.fetchone()[0]
        print(f'  Total rows: {count}')

# Check latest scene
c.execute('SELECT * FROM scenes ORDER BY rowid DESC LIMIT 1')
row = c.fetchone()
if row:
    print(f'\n📊 Latest scene: {row}')

conn.close()
