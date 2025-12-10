import sqlite3
import json

conn = sqlite3.connect('L:/_DATA/GoodQ_Data/memory.db')
c = conn.cursor()

# Get a fully enriched scene
c.execute('SELECT meta FROM scenes ORDER BY start LIMIT 1')
meta = json.loads(c.fetchone()[0])

print('Metadata keys:', len(meta))
print('Keys:', sorted(meta.keys()))

print('\nKey presence:')
print('  transcript:', 'transcript' in meta)
print('  emotions:', 'emotions' in meta) 
print('  sentiment:', 'sentiment' in meta)
print('  objects:', 'objects' in meta)
print('  tags:', 'tags' in meta)
print('  speakers:', 'speakers' in meta)
print('  caption:', 'caption' in meta)

conn.close()
