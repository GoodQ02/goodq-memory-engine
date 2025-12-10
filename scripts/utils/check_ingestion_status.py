#!/usr/bin/env python3
"""Check current ingestion status and progress"""
import sqlite3
import os
from pathlib import Path
from datetime import datetime

def check_status():
    print("=" * 80)
    print("GOODQ INGESTION STATUS CHECK")
    print("=" * 80)
    print(f"Timestamp: {datetime.now()}\n")
    
    # Check database
    db_path = Path("L:/_DATA/GoodQ_Data/memory.db")
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get table list
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f"📊 Database Tables: {[t[0] for t in tables]}\n")
        
        # Check scenes
        try:
            scene_count = cursor.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]
            print(f"🎬 Total Scenes: {scene_count}")
            
            if scene_count > 0:
                # Get latest scenes
                cursor.execute("SELECT * FROM scenes ORDER BY id DESC LIMIT 1")
                latest = cursor.fetchone()
                print(f"   Latest Scene ID: {latest[0] if latest else 'None'}")
                
                # Get column names
                cols = [description[0] for description in cursor.description]
                print(f"   Scene columns: {cols}")
        except Exception as e:
            print(f"❌ Error checking scenes: {e}")
        
        # Check workflow executions
        try:
            exec_count = cursor.execute("SELECT COUNT(*) FROM workflow_executions").fetchone()[0]
            print(f"\n📝 Workflow Executions: {exec_count}")
            
            if exec_count > 0:
                cursor.execute("SELECT * FROM workflow_executions ORDER BY id DESC LIMIT 1")
                latest_exec = cursor.fetchone()
                if latest_exec:
                    cols = [description[0] for description in cursor.description]
                    exec_dict = dict(zip(cols, latest_exec))
                    print(f"   Latest execution: {exec_dict}")
        except Exception as e:
            print(f"❌ Error checking executions: {e}")
        
        # Check all tables for record counts
        print("\n📋 All Table Counts:")
        for table in tables:
            try:
                count = cursor.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
                print(f"   {table[0]}: {count} records")
            except Exception as e:
                print(f"   {table[0]}: Error - {e}")
        
        conn.close()
    else:
        print("❌ Database not found!")
    
    # Check processing directory
    print("\n📁 Processing Directory:")
    processing_paths = [
        "L:/_DATA/GoodQ_Data/processing",
        "L:/goodq4all/output/processing",
        "L:/_DATA/GoodQ_Data/processing"
    ]
    
    for proc_path in processing_paths:
        if Path(proc_path).exists():
            files = list(Path(proc_path).rglob("*"))
            if files:
                print(f"   {proc_path}: {len(files)} items")
                recent = sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:5]
                for f in recent:
                    print(f"     - {f.name} ({datetime.fromtimestamp(f.stat().st_mtime)})")
        else:
            print(f"   {proc_path}: Not found")
    
    # Check output directory
    print("\n📤 Output Directory:")
    output_path = Path("L:/goodq4all/output")
    if output_path.exists():
        for item in output_path.iterdir():
            if item.is_dir():
                file_count = len(list(item.rglob("*")))
                print(f"   {item.name}/: {file_count} items")
    
    # Check workspace
    print("\n🔧 Workspace Artifacts:")
    workspace_paths = [
        "L:/_DATA/GoodQ_Data/workspace",
        "L:/goodq4all/.zen/workspace"
    ]
    
    for ws_path in workspace_paths:
        ws = Path(ws_path)
        if ws.exists():
            runs = list(ws.glob("*"))
            if runs:
                print(f"   {ws_path}: {len(runs)} runs")
                recent_run = max(runs, key=lambda x: x.stat().st_mtime)
                print(f"     Latest: {recent_run.name} ({datetime.fromtimestamp(recent_run.stat().st_mtime)})")
    
    # Check import inbox
    print("\n📬 Import Inbox:")
    inbox = Path("L:/goodq4all/import_inbox")
    if inbox.exists():
        for f in inbox.iterdir():
            size_gb = f.stat().st_size / (1024**3)
            print(f"   {f.name}: {size_gb:.2f} GB")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    check_status()
