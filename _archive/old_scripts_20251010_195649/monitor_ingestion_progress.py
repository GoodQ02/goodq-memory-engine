"""Monitor ingestion progress in real-time"""
import time
import sqlite3
from pathlib import Path

DB_PATH = Path('L:/goodq4all/data/memory.db')
STEP_LOG = Path('L:/GoodQ_Data/logs/step_runs.jsonl')

last_scene_count = 0
last_emb_count = 0
last_step_count = 0

print("Monitoring ingestion progress (Ctrl+C to stop)...")
print(f"Database: {DB_PATH}")
print(f"Step log: {STEP_LOG}\n")

try:
    while True:
        # Check database
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            
            scene_count = cursor.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]
            emb_count = cursor.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
            
            conn.close()
            
            if scene_count != last_scene_count or emb_count != last_emb_count:
                print(f"[{time.strftime('%H:%M:%S')}] Scenes: {scene_count} (+{scene_count-last_scene_count})  Embeddings: {emb_count} (+{emb_count-last_emb_count})")
                last_scene_count = scene_count
                last_emb_count = emb_count
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] DB check error: {e}")
        
        # Check step log
        try:
            if STEP_LOG.exists():
                with open(STEP_LOG, 'r', encoding='utf-8') as f:
                    step_count = sum(1 for _ in f)
                if step_count != last_step_count:
                    print(f"[{time.strftime('%H:%M:%S')}] Step runs: {step_count} (+{step_count-last_step_count})")
                    last_step_count = step_count
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Step log check error: {e}")
        
        time.sleep(10)
except KeyboardInterrupt:
    print("\n\nStopped monitoring.")
    print(f"Final counts - Scenes: {last_scene_count}, Embeddings: {last_emb_count}, Steps: {last_step_count}")
