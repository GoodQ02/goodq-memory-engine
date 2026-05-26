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

try:
    import psutil
except Exception:
    psutil = None

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_RUNTIME_PATHS = None


def get_runtime_paths():
    """Resolve canonical runtime paths once for this diagnostic session."""
    global _RUNTIME_PATHS
    if _RUNTIME_PATHS is None:
        from steps.common.config_loader import get_runtime_paths as _get_runtime_paths
        from steps.common.config_loader import load_configs

        cfg = load_configs({})
        resolved = _get_runtime_paths(cfg, "db_dir", "faiss_dir")
        db_dir = Path(resolved["db_dir"])
        log_dir = Path(resolved["log_dir"])
        resolved["unified_db_path"] = str(db_dir / "unified_goodq.db")
        resolved["progress_file"] = str(log_dir / "progress.json")
        resolved["watchdog_log"] = str(log_dir / "watchdog.log")
        resolved["command_center_log"] = str(log_dir / "command_center.log")
        resolved["step_runs_log"] = str(log_dir / "step_runs.jsonl")
        _RUNTIME_PATHS = resolved
    return _RUNTIME_PATHS


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

    if psutil is None:
        print("  [SYMBOL] psutil not available; skipping process scan")
        return []

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

    runtime_paths = get_runtime_paths()
    db_paths = {
        "Memory DB": Path(runtime_paths["db_path"]),
        "Knowledge Graph": Path(runtime_paths["knowledge_graph_db"]),
        "Unified DB": Path(runtime_paths["unified_db_path"]),
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

    faiss_dir = Path(get_runtime_paths()["faiss_dir"])
    results = {}
    if not faiss_dir.exists():
        print(f"  [SYMBOL] FAISS directory not found: {faiss_dir}")
        return results

    index_files = sorted(faiss_dir.rglob("*.index"))
    if not index_files:
        print("  [SYMBOL] No FAISS index files found")
        return results

    for path in index_files:
        name = path.stem
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

    inbox = Path(get_runtime_paths()["import_inbox"])
    
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

    progress_file = Path(get_runtime_paths()["progress_file"])
    
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

    runtime_paths = get_runtime_paths()
    log_files = {
        "Watchdog": Path(runtime_paths["watchdog_log"]),
        "Command Center": Path(runtime_paths["command_center_log"]),
        "Step Runs": Path(runtime_paths["step_runs_log"]),
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

    try:
        runtime_paths = get_runtime_paths()
        print(f"  Runtime Inbox: {runtime_paths['import_inbox']}")
        print(f"  Runtime Log Dir: {runtime_paths['log_dir']}")
        print(f"  Runtime DB Dir: {runtime_paths['db_dir']}")
    except Exception as e:
        print(f"  [SYMBOL] Failed to resolve canonical runtime paths: {e}")
        raise

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
            print("    - Start API server: python -m api.server")
        if len(videos) == 0:
            print(f"    - Add videos to {runtime_paths['import_inbox']}")
        if not any(databases.values()):
            print("    - Run ingestion to populate databases")
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
