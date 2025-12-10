import sqlite3

db_path = 'L:/_DATA/GoodQ_Data/memory.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get current scene count
c.execute('SELECT COUNT(*) FROM scenes')
before_count = c.fetchone()[0]
print(f'Scenes before deletion: {before_count}')

# Delete all scenes for 1987_1988.mp4
c.execute("DELETE FROM scenes WHERE video_id IN (SELECT video_id FROM videos WHERE filename = '1987_1988.mp4')")
deleted = c.rowcount
conn.commit()

# Get final count
c.execute('SELECT COUNT(*) FROM scenes')
after_count = c.fetchone()[0]
print(f'Deleted {deleted} scenes')
print(f'Scenes after deletion: {after_count}')

# Reset processing status
c.execute("UPDATE videos SET processed = 0 WHERE filename = '1987_1988.mp4'")
conn.commit()
print("Reset processing status for 1987_1988.mp4")

conn.close()
print("\n[SYMBOL] Database cleared and ready for reprocessing!")
