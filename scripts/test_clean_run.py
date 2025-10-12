#!/usr/bin/env python3
"""
Clean Test Run - Full pipeline verification with detailed logging
"""

import sys
import subprocess
import time
import json
import sqlite3
from pathlib import Path
from datetime import datetime

def clear_databases():
    """Clear all databases for clean test"""
    print("🧹 Clearing databases for clean test...")
    
    db_paths = [
        Path("L:/goodq4all/data/memory.db"),
        Path("L:/goodq4all/data/databases/clap_id_map.sqlite"),
        Path("L:/goodq4all/data/databases/clip_id_map.sqlite"),
        Path("L:/goodq4all/data/databases/dino_id_map.sqlite"),
    ]
    
    for db_path in db_paths:
        if db_path.exists():
            try:
                db_path.unlink()
                print(f"   ✓ Deleted: {db_path.name}")
            except Exception as e:
                print(f"   ✗ Failed to delete {db_path.name}: {e}")
    
    # Clear FAISS indices
    faiss_dir = Path("L:/goodq4all/data/faiss_indices")
    if faiss_dir.exists():
        for index_file in faiss_dir.rglob("*.index"):
            try:
                index_file.unlink()
                print(f"   ✓ Deleted FAISS index: {index_file.name}")
            except Exception as e:
                print(f"   ✗ Failed to delete {index_file.name}: {e}")
    
    print()

def run_ingestion(video_path: Path, workspace: Path) -> bool:
    """Run ingestion and return success status"""
    
    print(f"🎬 Starting ingestion: {video_path.name}")
    print(f"📂 Workspace: {workspace}")
    print()
    
    cmd = [
        'conda', 'run', '-n', 'goodq_zenml',
        'python', '-m', 'cli.run_ingestion',
        '--input-dir', str(video_path.parent),
        '--workspace', str(workspace),
        '--output', str(workspace / 'results.json'),
        '--force',
        '--verbose'
    ]
    
    print(f"🔧 Command: {' '.join(cmd)}")
    print()
    print("=" * 70)
    print("MISSION LOG (real-time output)")
    print("=" * 70)
    print()
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            cwd='L:/goodq4all',
            text=True,
            timeout=1800  # 30 minutes for sample.mp4
        )
        
        elapsed = time.time() - start_time
        print()
        print("=" * 70)
        print(f"⏱️  Mission completed in {elapsed:.1f}s ({elapsed/60:.1f}m)")
        print("=" * 70)
        print()
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("\n❌ TIMEOUT: Mission exceeded 30 minutes")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

def check_results(workspace: Path):
    """Check results and report findings"""
    print("📊 MISSION DEBRIEF:")
    print("=" * 70)
    print()
    
    # Check workspace artifacts
    print("🗂️  Workspace Artifacts:")
    frames = list(workspace.rglob("*.jpg"))
    audio = list(workspace.rglob("*.wav"))
    print(f"   Frames extracted: {len(frames)}")
    print(f"   Audio clips: {len(audio)}")
    
    # Check step_log.jsonl
    step_log = workspace / "step_log.jsonl"
    if step_log.exists():
        with open(step_log, 'r') as f:
            lines = f.readlines()
        print(f"   Step log entries: {len(lines)}")
        
        # Count by status
        statuses = {}
        for line in lines:
            try:
                entry = json.loads(line)
                status = entry.get('status', 'unknown')
                statuses[status] = statuses.get(status, 0) + 1
            except:
                pass
        
        print(f"   Status breakdown:")
        for status, count in sorted(statuses.items()):
            icon = "✓" if status == "ok" else "✗" if status == "error" else "⚠"
            print(f"      {icon} {status}: {count}")
    else:
        print("   ❌ step_log.jsonl NOT FOUND")
    
    print()
    
    # Check database
    print("💾 Memory Database:")
    db_path = Path("L:/goodq4all/data/memory.db")
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM embeddings")
            emb_count = cursor.fetchone()[0]
            print(f"   Embeddings: {emb_count}")
            
            try:
                cursor.execute("SELECT COUNT(*) FROM scenes")
                scene_count = cursor.fetchone()[0]
                print(f"   Scenes: {scene_count}")
            except:
                print(f"   Scenes: (table not found)")
            
            try:
                cursor.execute("SELECT COUNT(*) FROM links")
                link_count = cursor.fetchone()[0]
                print(f"   Links: {link_count}")
            except:
                print(f"   Links: (table not found)")
            
            # Show a sample embedding
            cursor.execute("SELECT id, video_path, scene_id, modality, embedding_type FROM embeddings LIMIT 3")
            samples = cursor.fetchall()
            if samples:
                print(f"   Sample embeddings:")
                for sample in samples:
                    print(f"      - ID:{sample[0]} | Scene:{sample[2]} | {sample[3]}/{sample[4]}")
            
            conn.close()
        except Exception as e:
            print(f"   ❌ Error reading database: {e}")
    else:
        print("   ❌ memory.db NOT FOUND")
    
    print()
    
    # Check FAISS indices
    print("🔍 FAISS Indices:")
    faiss_dir = Path("L:/goodq4all/data/faiss_indices")
    if faiss_dir.exists():
        for index_type in ['text', 'audio', 'dino', 'clip']:
            index_file = faiss_dir / index_type / f"faiss_{index_type}.index"
            if index_file.exists():
                size_mb = index_file.stat().st_size / (1024**2)
                print(f"   ✓ {index_type}: {size_mb:.2f} MB")
            else:
                print(f"   ✗ {index_type}: MISSING")
    else:
        print("   ❌ FAISS directory not found")
    
    print()
    print("=" * 70)

def main():
    print("━" * 70)
    print("🎯 GoodQ CLEAN TEST RUN")
    print("━" * 70)
    print()
    
    # Step 1: Clear databases
    clear_databases()
    
    # Step 2: Run ingestion on sample.mp4
    video_path = Path("L:/goodq4all/import_inbox/sample.mp4")
    if not video_path.exists():
        print(f"❌ Test video not found: {video_path}")
        sys.exit(1)
    
    workspace = Path(f"L:/goodq4all/logs/clean_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    workspace.mkdir(parents=True, exist_ok=True)
    
    success = run_ingestion(video_path, workspace)
    
    # Step 3: Check results
    check_results(workspace)
    
    # Step 4: Final verdict
    print()
    if success:
        print("✅ MISSION SUCCESS: Clean test run completed")
    else:
        print("❌ MISSION FAILED: Check logs above for errors")
    
    print()

if __name__ == "__main__":
    main()
