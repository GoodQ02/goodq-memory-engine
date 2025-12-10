#!/usr/bin/env python3
"""
Comprehensive System Status Check
Verifies all components and configuration
"""
import sqlite3
import yaml
import json
from pathlib import Path
from datetime import datetime

print("=" * 80)
print("  GoodQ4All System Status Check")
print("=" * 80)
print()

# 1. Check configuration
print("[LOG] Configuration Check:")
config_path = Path('L:/goodq4all/config.yaml')
if config_path.exists():
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    scene_cfg = config.get('video', {}).get('scene_detect', {})
    print(f"  [SYMBOL] Config file loaded")
    print(f"  - Scene threshold: {scene_cfg.get('threshold', 'NOT SET')}")
    print(f"  - Min scene length: {scene_cfg.get('min_scene_len_sec', 'NOT SET')}s ({scene_cfg.get('min_scene_len_sec', 0)/60:.1f} minutes)")
    print(f"  - Adaptive mode: {scene_cfg.get('adaptive', 'NOT SET')}")
    
    # Check LLM config
    llm_cfg = config.get('llm', {})
    print(f"\n[SYMBOL] LLM Configuration:")
    print(f"  - Enabled: {llm_cfg.get('enabled', False)}")
    print(f"  - API URL: {llm_cfg.get('api_url', 'NOT SET')}")
    print(f"  - Model: {llm_cfg.get('model_id', 'NOT SET')}")
    print(f"  - Scene summarization: {llm_cfg.get('features', {}).get('scene_summarization', False)}")
else:
    print(f"  [FAIL] Config file not found!")

# 2. Check database
print(f"\n[SYMBOL]️  Database Status:")
db_path = Path('L:/_DATA/GoodQ_Data/memory.db')
if db_path.exists():
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    
    # Get table counts
    c.execute("SELECT COUNT(*) FROM scenes")
    scene_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM segments")
    segment_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM embeddings")
    embedding_count = c.fetchone()[0]
    
    print(f"  [SYMBOL] Database connected")
    print(f"  - Scenes: {scene_count}")
    print(f"  - Segments: {segment_count}")
    print(f"  - Embeddings: {embedding_count}")
    
    # Check for recent activity
    c.execute("SELECT created_at FROM scenes ORDER BY created_at DESC LIMIT 1")
    latest = c.fetchone()
    if latest:
        print(f"  - Latest scene: {latest[0]}")
    
    conn.close()
else:
    print(f"  [FAIL] Database not found!")

# 3. Check processing status
print(f"\n[SYMBOL]️  Processing Status:")
import_inbox = Path('L:/goodq4all/import_inbox')
if import_inbox.exists():
    files = list(import_inbox.glob('*.mp4'))
    print(f"  - Files in inbox: {len(files)}")
    for f in files[:5]:  # Show first 5
        size_gb = f.stat().st_size / (1024**3)
        print(f"    • {f.name} ({size_gb:.2f} GB)")
else:
    print(f"  [FAIL] Import inbox not found!")

# 4. Check logs
print(f"\n[NOTE] Recent Logs:")
log_files = {
    'Watchdog': 'logs/watchdog.log',
    'API Server': 'logs/api_server.log'
}

for name, log_path in log_files.items():
    p = Path(f'L:/goodq4all/{log_path}')
    if p.exists():
        # Get last line
        try:
            with open(p) as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    # Truncate if too long
                    if len(last_line) > 80:
                        last_line = last_line[:77] + '...'
                    print(f"  {name}: {last_line}")
        except Exception as e:
            print(f"  {name}: Error reading log - {e}")
    else:
        print(f"  {name}: Log file not found")

print()
print("=" * 80)
print("[SYMBOL] Status check complete")
print("=" * 80)
