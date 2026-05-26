import sqlite3

db_path = 'L:/_DATA/GoodQ_Data/memory.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get all tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = c.fetchall()
print('Tables in database:')
for table in tables:
    print(f'  - {table[0]}')

conn.close()
