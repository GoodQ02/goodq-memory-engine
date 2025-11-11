import sqlite3
from pathlib import Path

dbs = [
    ('data/memory.db', Path('data/memory.db')),
    ('data/knowledge_graph.db', Path('data/knowledge_graph.db')),
    ('data/unified_goodq.db', Path('data/unified_goodq.db')),
    ('output/goodq_memory.db', Path('output/goodq_memory.db'))
]

for name, path in dbs:
    if path.exists() and path.stat().st_size > 0:
        try:
            conn = sqlite3.connect(str(path))
            cursor = conn.cursor()
            cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
            tables = [row[0] for row in cursor.fetchall()]
            if tables:
                print(f'\n{name}:')
                for table in tables:
                    try:
                        cursor.execute(f'SELECT COUNT(*) FROM {table}')
                        count = cursor.fetchone()[0]
                        print(f'  {table}: {count} rows')
                    except Exception as e:
                        print(f'  {table}: Error - {e}')
            else:
                print(f'\n{name}: No tables')
            conn.close()
        except Exception as e:
            print(f'\n{name}: Error - {e}')
    else:
        print(f'\n{name}: Empty or does not exist')
