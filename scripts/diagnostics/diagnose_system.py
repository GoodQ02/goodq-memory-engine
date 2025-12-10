#!/usr/bin/env python3
"""
GoodQ System Diagnostic Tool
Checks all components and shows real-time status
"""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import psutil


def check_section(title):
    """Print section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print('='*80)


def check_status(msg, condition):
    """Print status check result"""
    symbol = "[SYMBOL]" if condition else "[SYMBOL]"
    status = "OK" if condition else "FAIL"
    print(f"  [{symbol}] {msg}: {status}")
    return condition


def check_python_processes():
    """Check running Python processes related to GoodQ"""
    check_section("Running Processes")
    
    found_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any('goodq' in str(arg).lower() for arg in cmdline):
                uptime = datetime.now() - datetime.fromtimestamp(proc.info['create_time'])
                found_processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'uptime': f"{int(uptime.total_seconds()//3600)}h {int((uptime.total_seconds()%3600)//60)}m"
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if found_processes:
        for proc in found_processes:
            print(f"  [SYMBOL] {proc['name']} (PID: {proc['pid']}, Uptime: {proc['uptime']})")
    else:
        print("  [SYMBOL] No GoodQ processes found running")
    
    return found_processes


def check_databases():
    """Check database status"""
    check_section("Database Status")
    
    db_paths = {
        "Memory DB": Path("L:/_DATA/GoodQ_Data/memory.db"),
        "Knowledge Graph": Path("L:/_DATA/GoodQ_Data/knowledge_graph.db"),
        "Unified DB": Path("L:/_DATA/GoodQ_Data/unified_goodq.db"),
    }
    
    results = {}
    for name, path in db_paths.items():
        exists = path.exists()
        check_status(name, exists)
        
        if exists:
            try:
                conn = sqlite3.connect(str(path))
                cursor = conn.cursor()
                
                # Get table counts
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                print(f"      Tables: {', '.join(tables[:5])}")
                
                # Get some stats
                if 'scenes' in tables:
                    cursor.execute("SELECT COUNT(*) FROM scenes")
                    count = cursor.fetchone()[0]
                    print(f"      Scenes: {count}")
                
                if 'nodes' in tables:
                    cursor.execute("SELECT COUNT(*) FROM nodes")
                    count = cursor.fetchone()[0]
                    print(f"      Nodes: {count}")
                
                if 'edges' in tables:
                    cursor.execute("SELECT COUNT(*) FROM edges")
                    count = cursor.fetchone()[0]
                    print(f"      Edges: {count}")
                
                conn.close()
                results[name] = True
            except Exception as e:
                print(f"      Error reading: {e}")
                results[name] = False
        else:
            results[name] = False
    
    return results


def check_faiss_indices():
    """Check FAISS index status"""
    check_section("FAISS Indices")
    
    faiss_dir = Path("L:/_DATA/GoodQ_Data/faiss_indices")
    indices = {
        "Text": faiss_dir / "text" / "faiss_text.index",
        "CLIP": faiss_dir / "clip" / "faiss_clip.index",
        "DINO": faiss_dir / "dino" / "faiss_dino.index",
        "Audio (CLAP)": faiss_dir / "audio" / "faiss_audio.index",
    }
    
    results = {}
    for name, path in indices.items():
        exists = path.exists()
        check_status(name, exists)
        if exists:
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"      Size: {size_mb:.2f} MB")
        results[name] = exists
    
    return results


def check_video_files():
    """Check for videos in import inbox"""
    check_section("Import Inbox")
    
    inbox = Path("L:/goodq4all/import_inbox")
    
    if not inbox.exists():
        print("  [SYMBOL] Import inbox not found")
        return []
    
    video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.wmv'}
    videos = []
    for ext in video_exts:
        videos.extend(inbox.glob(f'*{ext}'))
    
    if videos:
        print(f"  [SYMBOL] Found {len(videos)} video(s):")
        for video in videos[:5]:  # Show first 5
            size_gb = video.stat().st_size / (1024**3)
            print(f"      - {video.name} ({size_gb:.2f} GB)")
        if len(videos) > 5:
            print(f"      ... and {len(videos)-5} more")
    else:
        print("  [SYMBOL] No videos found in import inbox")
    
    return videos


def check_progress():
    """Check current processing progress"""
    check_section("Current Progress")
    
    progress_file = Path("L:/goodq4all/logs/progress.json")
    
    if not progress_file.exists():
        print("  [SYMBOL] No active processing (progress.json not found)")
        return None
    
    try:
        with open(progress_file, 'r', encoding='utf-8') as f:
            progress = json.load(f)
        
        status = progress.get('status', 'unknown')
        current_file = progress.get('current_file', 'None')
        current_step = progress.get('current_step', 'None')
        progress_percent = progress.get('progress_percent', 0)
        
        print(f"  Status: {status.upper()}")
        print(f"  File: {current_file}")
        print(f"  Step: {current_step}")
        print(f"  Progress: {progress_percent}%")
        
        errors = progress.get('errors', [])
        if errors:
            print(f"  [SYMBOL] Errors: {len(errors)}")
            for error in errors[-2:]:
                print(f"      - {error.get('message', 'Unknown')}")
        
        return progress
    except Exception as e:
        print(f"  [SYMBOL] Error reading progress: {e}")
        return None


def check_logs():
    """Check recent log entries"""
    check_section("Recent Logs")
    
    log_files = {
        "Watchdog": Path("L:/goodq4all/logs/watchdog.log"),
        "Command Center": Path("L:/goodq4all/logs/command_center.log"),
    }
    
    for name, log_path in log_files.items():
        if log_path.exists():
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    recent = lines[-3:] if len(lines) >= 3 else lines
                    print(f"  {name} (last {len(recent)} lines):")
                    for line in recent:
                        # Truncate long lines
                        line = line.strip()[:100]
                        print(f"      {line}")
            except Exception as e:
                print(f"  [SYMBOL] Error reading {name}: {e}")
        else:
            print(f"  [SYMBOL] {name} not found")


def check_api_server():
    """Check if API server is responding"""
    check_section("API Server")
    
    try:
        import urllib.request
        import urllib.error
        
        url = "http://localhost:30000/api/status"
        
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read())
                print("  [SYMBOL] API server is responding")
                print(f"      Status: {data.get('status', 'unknown')}")
                
                db_stats = data.get('database', {})
                if db_stats:
                    print(f"      Scenes: {db_stats.get('scenes', 0)}")
                    print(f"      Entities: {db_stats.get('entities', 0)}")
                
                return True
        except urllib.error.URLError:
            print("  [SYMBOL] API server not responding")
            print("      URL: http://localhost:30000")
            return False
    except Exception as e:
        print(f"  [SYMBOL] Error checking API: {e}")
        return False


def main():
    print("\n" + "="*80)
    print("  GoodQ System Diagnostics")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*80)
    
    # Run all checks
    processes = check_python_processes()
    databases = check_databases()
    faiss = check_faiss_indices()
    videos = check_video_files()
    progress = check_progress()
    api_status = check_api_server()
    check_logs()
    
    # Summary
    check_section("Summary")
    
    total_checks = 0
    passed_checks = 0
    
    checks = [
        ("Processes Running", len(processes) > 0),
        ("Databases Available", any(databases.values())),
        ("FAISS Indices", any(faiss.values())),
        ("API Server", api_status),
        ("Videos Ready", len(videos) > 0),
    ]
    
    for name, status in checks:
        total_checks += 1
        if status:
            passed_checks += 1
        check_status(name, status)
    
    print(f"\n  Overall: {passed_checks}/{total_checks} checks passed")
    
    # Recommendations
    if passed_checks < total_checks:
        print("\n  Recommendations:")
        if not api_status:
            print("    - Start API server: python api_server.py")
        if len(videos) == 0:
            print("    - Add videos to L:\\goodq4all\\import_inbox")
        if not any(databases.values()):
            print("    - Run ingestion to populate databases")
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
