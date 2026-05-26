import sqlite3

conn = sqlite3.connect('data/unified_goodq.db')
cur = conn.cursor()

print('Total entities:', cur.execute('SELECT COUNT(*) FROM global_entities').fetchone()[0])
cur.execute('SELECT id, canonical_name, entity_type FROM global_entities LIMIT 5')

print('\nFirst 5 entities:')
for r in cur.fetchall():
    print(f'  ID={r[0]} | Name={r[1]} | Type={r[2]}')

conn.close()
