"""
Comprehensive GoodQ Status Checker
Shows current processing status and statistics
"""
import sqlite3
import json
import sys
from pathlib import Path
from datetime import datetime
from collections import Counter

# Ensure UTF-8 output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def check_processing_status():
    """Check if processing is currently active"""
    step_log = Path('L:/goodq4all/logs/step_runs.jsonl')
    
    if not step_log.exists():
        return False, "No step log found"
    
    # Check last 5 lines for recent activity
    with open(step_log, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    if not lines:
        return False, "Step log is empty"
    
    # Parse last entry
    try:
        last_entry = json.loads(lines[-1])
        last_time = datetime.fromisoformat(last_entry['ts'])
        now = datetime.now()
        
        minutes_ago = (now - last_time).total_seconds() / 60
        
        if minutes_ago < 2:
            return True, f"Active (last step: {minutes_ago:.1f}min ago)"
        else:
            return False, f"Idle ({minutes_ago:.0f}min since last activity)"
    except:
        return False, "Could not parse log"

def analyze_step_performance():
    """Analyze which steps are taking longest"""
    step_log = Path('L:/goodq4all/logs/step_runs.jsonl')
    
    if not step_log.exists():
        return {}
    
    step_times = Counter()
    step_counts = Counter()
    
    # Read last 1000 entries
    with open(step_log, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line in lines[-1000:]:
        try:
            entry = json.loads(line)
            step_name = entry.get('step', 'unknown')
            duration = entry.get('duration_ms', 0)
            
            step_times[step_name] += duration
            step_counts[step_name] += 1
        except:
            continue
    
    # Calculate averages
    step_averages = {}
    for step, total_time in step_times.items():
        count = step_counts[step]
        avg_time = total_time / count
        step_averages[step] = {
            'avg_ms': avg_time,
            'count': count,
            'total_ms': total_time
        }
    
    return step_averages

def main():
    print("\n╔═══════════════════════════════════════════════════════════════╗")
    print("║         [!] GoodQ Comprehensive Status Report                ║")
    print("╚═══════════════════════════════════════════════════════════════╝\n")
    
    # Check processing status
    is_active, status_msg = check_processing_status()
    status_icon = "[>>>]" if is_active else "[---]"
    print(f"{status_icon} Processing Status: {status_msg}\n")
    
    # Check database
    db_path = Path('L:/goodq4all/data/memory.db')
    
    if not db_path.exists():
        print("[!] No database found - no videos processed yet\n")
        return
    
    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        
        # Scene statistics
        print("=" * 65)
        print("[!] DATABASE STATISTICS")
        print("=" * 65)
        
        c.execute('SELECT COUNT(*) FROM scenes')
        scene_count = c.fetchone()[0]
        print(f"  Total Scenes:          {scene_count:,}")
        
        c.execute('SELECT COUNT(*) FROM embeddings')
        embedding_count = c.fetchone()[0]
        print(f"  Total Embeddings:      {embedding_count:,}")
        
        c.execute('SELECT COUNT(*) FROM links')
        link_count = c.fetchone()[0]
        print(f"  Knowledge Links:       {link_count:,}")
        
        # Embeddings by modality
        c.execute('SELECT modality, COUNT(*) FROM embeddings GROUP BY modality ORDER BY COUNT(*) DESC')
        print("\n  Embeddings by Type:")
        for mod, cnt in c.fetchall():
            bar_len = int((cnt / embedding_count) * 30) if embedding_count > 0 else 0
            bar = "=" * bar_len
            print(f"    {mod:20s} [{bar:30s}] {cnt:4d}")
        
        # Video info
        c.execute("SELECT DISTINCT video_hash FROM scenes")
        video_hashes = [row[0] for row in c.fetchall() if row[0]]
        
        if video_hashes:
            print(f"\n  Videos Processed:      {len(video_hashes)}")
            for vh in video_hashes[:3]:
                c.execute('SELECT COUNT(*) FROM scenes WHERE video_hash = ?', (vh,))
                scene_cnt = c.fetchone()[0]
                print(f"    - {vh[:16]}...  ({scene_cnt} scenes)")
        
        conn.close()
        
    except Exception as e:
        print(f"\n[ERROR] Database error: {e}")
    
    # Step performance analysis
    print("\n" + "=" * 65)
    print("[!] STEP PERFORMANCE ANALYSIS (Recent 1000 steps)")
    print("=" * 65)
    
    perf = analyze_step_performance()
    
    if perf:
        # Sort by average time, descending
        sorted_steps = sorted(perf.items(), key=lambda x: x[1]['avg_ms'], reverse=True)
        
        print("\n  Slowest Steps (avg time):")
        for step, data in sorted_steps[:10]:
            avg_sec = data['avg_ms'] / 1000
            total_sec = data['total_ms'] / 1000
            count = data['count']
            
            if avg_sec > 1:
                print(f"    {step:25s} {avg_sec:7.2f}s  (x{count}, total: {total_sec:.1f}s)")
        
        print("\n  Most Frequent Steps:")
        most_common = sorted(perf.items(), key=lambda x: x[1]['count'], reverse=True)
        for step, data in most_common[:10]:
            count = data['count']
            avg_ms = data['avg_ms']
            print(f"    {step:25s} {count:4d}x  (avg: {avg_ms:.1f}ms)")
    
    # Check watchdog status
    watchdog_log = Path('L:/goodq4all/logs/watchdog.log')
    if watchdog_log.exists():
        print("\n" + "=" * 65)
        print("[!] WATCHDOG STATUS")
        print("=" * 65)
        
        with open(watchdog_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Find last few important entries
        recent = []
        for line in reversed(lines[-50:]):
            if '[INFO]' in line and any(keyword in line for keyword in 
                ['Successfully processed', 'Queued', 'Processing', 'Starting']):
                recent.append(line.strip())
                if len(recent) >= 5:
                    break
        
        for line in reversed(recent):
            print(f"  {line}")
    
    print("\n" + "=" * 65)
    print("\n[OK] Status check complete\n")

if __name__ == "__main__":
    main()
