import sqlite3

conn = sqlite3.connect('L:/goodq4all/data/memory.db')
cur = conn.cursor()

print('=== SCENES TABLE SCHEMA ===')
for row in cur.execute('PRAGMA table_info(scenes)').fetchall():
    print(f'  {row[1]}: {row[2]}')

print('\n=== SAMPLE SCENES ===')
for row in cur.execute('SELECT id, video_hash, start, end FROM scenes LIMIT 10').fetchall():
    duration = row[3] - row[2]
    print(f'Scene {row[0]}: {row[2]:.2f}s to {row[3]:.2f}s (duration: {duration:.2f}s)')

print('\n=== SCENE STATISTICS ===')
stats = cur.execute('''
    SELECT 
        COUNT(*) as total_scenes,
        MIN(end - start) as min_duration,
        MAX(end - start) as max_duration,
        AVG(end - start) as avg_duration
    FROM scenes
''').fetchone()
print(f'Total scenes: {stats[0]}')
print(f'Min duration: {stats[1]:.2f}s')
print(f'Max duration: {stats[2]:.2f}s')
print(f'Avg duration: {stats[3]:.2f}s')

conn.close()
