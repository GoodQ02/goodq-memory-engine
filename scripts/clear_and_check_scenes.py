import sqlite3

db_path = 'L:/goodq4all/data/memory.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Check scenes table structure
c.execute("PRAGMA table_info(scenes)")
columns = c.fetchall()
print('Scenes table structure:')
for col in columns:
    print(f'  {col[1]} ({col[2]})')

# Get current scene count and sample
c.execute('SELECT COUNT(*) FROM scenes')
count = c.fetchone()[0]
print(f'\nTotal scenes: {count}')

# Get sample scenes with their durations
c.execute('SELECT scene_id, file_path, start_time, end_time, (end_time - start_time) as duration FROM scenes LIMIT 5')
samples = c.fetchall()
print('\nSample scenes:')
for s in samples:
    print(f'  Scene {s[0]}: {s[1]} | {s[2]:.2f}s - {s[3]:.2f}s | Duration: {s[4]:.2f}s')

# Delete all scenes (since we're reprocessing everything)
print(f'\nDeleting all {count} scenes...')
c.execute('DELETE FROM scenes')
conn.commit()

c.execute('SELECT COUNT(*) FROM scenes')
after_count = c.fetchone()[0]
print(f'Scenes remaining: {after_count}')

conn.close()
print('\n✓ Database cleared and ready for reprocessing with 5-minute scenes!')
