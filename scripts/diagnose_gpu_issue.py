"""
Comprehensive GPU and processing diagnostics
"""

import os
import sys
import sqlite3
from pathlib import Path

def check_python_processes():
    """Check for running Python processes"""
    print("="*80)
    print("Python Processes")
    print("="*80)
    
    try:
        import psutil
        python_procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info']):
            try:
                if 'python' in proc.info['name'].lower():
                    python_procs.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmdline': ' '.join(proc.info['cmdline'][:3]) if proc.info['cmdline'] else '',
                        'memory_mb': proc.info['memory_info'].rss / 1024 / 1024
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if python_procs:
            print(f"Found {len(python_procs)} Python processes:")
            for proc in python_procs:
                print(f"  PID {proc['pid']:>6}: {proc['name']:<15} {proc['memory_mb']:>7.1f} MB - {proc['cmdline'][:60]}")
        else:
            print("No Python processes found")
            
        return python_procs
    except ImportError:
        print("⚠ psutil not available, cannot check processes")
        return []

def check_gpu_usage():
    """Check current GPU usage"""
    print("\n" + "="*80)
    print("GPU Status")
    print("="*80)
    
    try:
        import torch
        
        if not torch.cuda.is_available():
            print("CUDA not available")
            return
        
        print(f"Device: {torch.cuda.get_device_name(0)}")
        props = torch.cuda.get_device_properties(0)
        total_gb = props.total_memory / 1024**3
        
        allocated_gb = torch.cuda.memory_allocated(0) / 1024**3
        reserved_gb = torch.cuda.memory_reserved(0) / 1024**3
        
        print(f"Total VRAM: {total_gb:.2f} GB")
        print(f"Allocated: {allocated_gb:.2f} GB ({allocated_gb/total_gb*100:.1f}%)")
        print(f"Reserved: {reserved_gb:.2f} GB ({reserved_gb/total_gb*100:.1f}%)")
        print(f"Free: {total_gb - reserved_gb:.2f} GB")
        
    except ImportError:
        print("PyTorch not available in base environment")
    except Exception as e:
        print(f"Error checking GPU: {e}")

def check_database():
    """Check database status"""
    print("\n" + "="*80)
    print("Database Status")
    print("="*80)
    
    db_path = Path("L:/goodq4all/output/knowledge.db")
    
    if not db_path.exists():
        print(f"✗ Database not found: {db_path}")
        return
    
    print(f"✓ Database found: {db_path}")
    print(f"  Size: {db_path.stat().st_size / 1024 / 1024:.2f} MB")
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # List tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"  Tables ({len(tables)}): {', '.join(tables)}")
        
        # Check scene count
        if 'scenes' in tables:
            cursor.execute("SELECT COUNT(*) FROM scenes")
            scene_count = cursor.fetchone()[0]
            print(f"  Scenes: {scene_count}")
            
            # Get recent scenes
            cursor.execute("SELECT scene_id, video_id, start_time, end_time FROM scenes ORDER BY scene_id DESC LIMIT 3")
            recent_scenes = cursor.fetchall()
            if recent_scenes:
                print("  Recent scenes:")
                for scene in recent_scenes:
                    print(f"    Scene {scene[0]}: Video {scene[1]}, {scene[2]:.1f}s - {scene[3]:.1f}s")
        
        # Check embeddings
        if 'embeddings' in tables:
            cursor.execute("SELECT COUNT(*) FROM embeddings")
            embed_count = cursor.fetchone()[0]
            print(f"  Embeddings: {embed_count}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"✗ Database error: {e}")

def check_processing_status():
    """Check current processing status"""
    print("\n" + "="*80)
    print("Processing Status")
    print("="*80)
    
    # Check import inbox
    inbox = Path("L:/goodq4all/import_inbox")
    if inbox.exists():
        files = list(inbox.glob("*.mp4"))
        print(f"Import inbox: {len(files)} files")
        for f in files:
            size_mb = f.stat().st_size / 1024 / 1024
            print(f"  - {f.name} ({size_mb:.1f} MB)")
    
    # Check processing directory
    processing = Path("L:/_DATA/GoodQ_Data/processing")
    if processing.exists():
        files = list(processing.glob("*.mp4"))
        dirs = [d for d in processing.iterdir() if d.is_dir()]
        print(f"\nProcessing directory: {len(files)} files, {len(dirs)} directories")
        
        for f in files[:5]:  # Show first 5
            size_mb = f.stat().st_size / 1024 / 1024
            print(f"  - {f.name} ({size_mb:.1f} MB)")
        
        for d in dirs[:5]:  # Show first 5
            print(f"  - {d.name}/ (directory)")
    
    # Check for lock files
    locks = list(Path("L:/goodq4all").rglob("*.lock"))
    if locks:
        print(f"\n⚠ Found {len(locks)} lock files:")
        for lock in locks:
            print(f"  - {lock}")
    else:
        print("\n✓ No lock files found")

def check_logs():
    """Check recent log entries"""
    print("\n" + "="*80)
    print("Recent Logs")
    print("="*80)
    
    log_files = [
        "L:/goodq4all/logs/watchdog.log",
        "L:/goodq4all/logs/command_center.log",
        "L:/goodq4all/logs/api_server.log"
    ]
    
    for log_path in log_files:
        p = Path(log_path)
        if p.exists():
            print(f"\n{p.name} (last 10 lines):")
            try:
                with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    for line in lines[-10:]:
                        print(f"  {line.rstrip()}")
            except Exception as e:
                print(f"  Error reading log: {e}")
        else:
            print(f"\n{p.name}: Not found")

def main():
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "GoodQ4All GPU & Processing Diagnostics" + " "*20 + "║")
    print("╚" + "="*78 + "╝")
    print()
    
    check_python_processes()
    check_gpu_usage()
    check_database()
    check_processing_status()
    check_logs()
    
    print("\n" + "="*80)
    print("Diagnostic Complete")
    print("="*80)

if __name__ == "__main__":
    main()
