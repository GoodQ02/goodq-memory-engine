#!/usr/bin/env python3
"""Monitor GoodQ ingestion with scene detection verification"""
import sqlite3
import time
import sys
from datetime import datetime

db_path = 'L:/_DATA/GoodQ_Data/memory.db'

print("=" * 80)
print("  GoodQ Scene Detection Monitor")
print("  Verifying 5-minute minimum scene length")
print("=" * 80)
print()

last_scene_count = 0

try:
    while True:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Get scene count
        c.execute('SELECT COUNT(*) FROM scenes')
        scene_count = c.fetchone()[0]
        
        # Get scene duration stats
        c.execute('''
            SELECT 
                COUNT(*) as total_scenes,
                AVG(end - start) as avg_duration,
                MIN(end - start) as min_duration,
                MAX(end - start) as max_duration
            FROM scenes
        ''')
        stats = c.fetchone()
        
        # Get latest scenes
        c.execute('''
            SELECT id, video_hash, start, end, (end - start) as duration
            FROM scenes
            ORDER BY created_at DESC
            LIMIT 3
        ''')
        latest = c.fetchall()
        
        conn.close()
        
        # Display status
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"\r[{timestamp}] Scenes: {scene_count}", end='')
        
        if scene_count > last_scene_count:
            print(f"\n\n[STATS] Scene Stats:")
            if stats[0] > 0:
                print(f"   Total: {stats[0]}")
                print(f"   Average duration: {stats[1]/60:.2f} minutes")
                print(f"   Min duration: {stats[2]/60:.2f} minutes")
                print(f"   Max duration: {stats[3]/60:.2f} minutes")
                
                # Check if any scenes are < 5 minutes
                if stats[2] < 300:
                    print(f"   [WARN]  WARNING: Minimum scene is {stats[2]/60:.2f} minutes (expected >= 5 min)")
                else:
                    print(f"   [SYMBOL] All scenes meet 5-minute minimum!")
                
                print(f"\n[LOG] Latest scenes:")
                for scene in latest:
                    dur_min = scene[4] / 60
                    print(f"   - {scene[0][:8]}... | {scene[2]/60:.1f}m - {scene[3]/60:.1f}m | Duration: {dur_min:.2f} min")
            
            last_scene_count = scene_count
            print()
        
        time.sleep(5)
        
except KeyboardInterrupt:
    print("\n\n[SYMBOL] Monitor stopped")
    sys.exit(0)
except Exception as e:
    print(f"\n\n[FAIL] Error: {e}")
    sys.exit(1)
