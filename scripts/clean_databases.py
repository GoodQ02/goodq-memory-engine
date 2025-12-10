#!/usr/bin/env python3
"""Clean all databases and FAISS indices for a fresh start

MISSION: SANITIZE DATABASES
   _____ ____  ____  ____   ___
  / ____|  _ \|  _ \|  _ \ / _ \
 | |  __| | | | | | | |_) | | | |
 | | |_ | | | | | | |  __/| | | |
 | |__| | |_| | |_| | |   | |_| |
  \_____|____/|____/|_|    \___/

This script will:
1. Remove all embeddings from memory.db
2. Delete all FAISS indices
3. Clear knowledge graph database
4. Archive old log files
5. Prepare system for clean ingestion run
"""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


def clean_memory_db(db_path: Path) -> dict:
    """Clean embeddings and scenes from memory database"""
    if not db_path.exists():
        return {"status": "not_found", "message": f"Database not found: {db_path}"}
    
    # Backup first
    backup_path = db_path.parent / f"memory_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(db_path, backup_path)
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get counts before deletion
    tables = {}
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    for (table_name,) in cursor.fetchall():
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        tables[table_name] = {"before": count}
    
    # Delete all data but keep schema
    for table_name in tables.keys():
        cursor.execute(f"DELETE FROM {table_name}")
    
    # Get counts after deletion
    for table_name in tables.keys():
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        tables[table_name]["after"] = count
        tables[table_name]["deleted"] = tables[table_name]["before"] - count
    
    conn.commit()
    conn.close()
    
    return {
        "status": "success",
        "backup": str(backup_path),
        "tables": tables,
        "total_deleted": sum(t["deleted"] for t in tables.values())
    }


def clean_faiss_indices(faiss_dir: Path) -> dict:
    """Remove all FAISS index files"""
    if not faiss_dir.exists():
        return {"status": "not_found", "message": f"FAISS directory not found: {faiss_dir}"}
    
    # Backup FAISS directory
    backup_dir = faiss_dir.parent / f"faiss_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if faiss_dir.exists():
        shutil.copytree(faiss_dir, backup_dir)
    
    # Count files before deletion
    index_files = list(faiss_dir.glob("**/*.index")) + list(faiss_dir.glob("**/*.pkl"))
    file_count = len(index_files)
    total_size = sum(f.stat().st_size for f in index_files)
    
    # Remove FAISS indices
    for index_file in index_files:
        index_file.unlink()
    
    return {
        "status": "success",
        "backup": str(backup_dir),
        "files_deleted": file_count,
        "bytes_freed": total_size
    }


def clean_knowledge_graph(kg_path: Path) -> dict:
    """Clean knowledge graph database"""
    if not kg_path.exists():
        return {"status": "not_found", "message": f"Knowledge graph not found: {kg_path}"}
    
    # Backup first
    backup_path = kg_path.parent / f"kg_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(kg_path, backup_path)
    
    # Get size before deletion
    size_before = kg_path.stat().st_size
    
    # Delete the database file
    kg_path.unlink()
    
    return {
        "status": "success",
        "backup": str(backup_path),
        "bytes_freed": size_before
    }


def archive_logs(log_dir: Path) -> dict:
    """Archive old log files"""
    if not log_dir.exists():
        return {"status": "not_found", "message": f"Log directory not found: {log_dir}"}
    
    archive_dir = log_dir.parent / f"logs_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    archived_files = []
    total_size = 0
    
    # Archive JSONL and CSV files
    for log_file in log_dir.glob("*.jsonl") + list(log_dir.glob("*.csv")):
        if log_file.is_file():
            dest = archive_dir / log_file.name
            shutil.move(str(log_file), str(dest))
            archived_files.append(log_file.name)
            total_size += dest.stat().st_size
    
    return {
        "status": "success",
        "archive_location": str(archive_dir),
        "files_archived": len(archived_files),
        "bytes_archived": total_size
    }


def main():
    """Execute database cleaning operations"""
    print("=" * 70)
    print("MISSION: SANITIZE DATABASES")
    print("=" * 70)
    print("\n[BRIEFING] Preparing to clean all databases for fresh ingestion")
    print("\n[WARN]  WARNING: This will delete ALL processed data!")
    print("   Backups will be created before deletion.\n")
    
    response = input("Proceed with database sanitization? (yes/no): ")
    if response.lower() not in ["yes", "y"]:
        print("\n[MISSION ABORTED] Database cleaning cancelled")
        return
    
    print("\n" + "=" * 70)
    print("[OPERATION COMMENCED]")
    print("=" * 70)
    
    # Define paths
    data_dir = Path("L:/_DATA/GoodQ_Data")
    memory_db = data_dir / "memory.db"
    faiss_dir = data_dir / "faiss"
    kg_db = data_dir / "knowledge_graph.db"
    log_dir = data_dir / "logs"
    
    results = {}
    
    # Clean memory database
    print("\n[TARGET] Memory Database")
    result = clean_memory_db(memory_db)
    results["memory_db"] = result
    if result["status"] == "success":
        print(f"  [SYMBOL] Deleted {result['total_deleted']} rows across {len(result['tables'])} tables")
        print(f"  [SYMBOL] Backup: {result['backup']}")
    else:
        print(f"  [WARN]  {result['message']}")
    
    # Clean FAISS indices
    print("\n[TARGET] FAISS Indices")
    result = clean_faiss_indices(faiss_dir)
    results["faiss"] = result
    if result["status"] == "success":
        print(f"  [SYMBOL] Deleted {result['files_deleted']} index files")
        print(f"  [SYMBOL] Freed {result['bytes_freed']:,} bytes")
        print(f"  [SYMBOL] Backup: {result['backup']}")
    else:
        print(f"  [WARN]  {result['message']}")
    
    # Clean knowledge graph
    print("\n[TARGET] Knowledge Graph")
    result = clean_knowledge_graph(kg_db)
    results["knowledge_graph"] = result
    if result["status"] == "success":
        print(f"  [SYMBOL] Deleted knowledge graph database")
        print(f"  [SYMBOL] Freed {result['bytes_freed']:,} bytes")
        print(f"  [SYMBOL] Backup: {result['backup']}")
    else:
        print(f"  [WARN]  {result['message']}")
    
    # Archive logs
    print("\n[TARGET] Log Files")
    result = archive_logs(log_dir)
    results["logs"] = result
    if result["status"] == "success":
        print(f"  [SYMBOL] Archived {result['files_archived']} log files")
        print(f"  [SYMBOL] Archive: {result['archive_location']}")
    else:
        print(f"  [WARN]  {result['message']}")
    
    print("\n" + "=" * 70)
    print("[MISSION COMPLETE] Database sanitization successful")
    print("=" * 70)
    print("\nSystem is ready for fresh ingestion of:")
    print("  [SYMBOL] 1987_1988.mp4")
    print("\nAll backups have been preserved for recovery if needed.")
    print("\n[Q] \"Now then, Agent. Time for a proper intelligence gathering mission.\"")
    

if __name__ == "__main__":
    main()
