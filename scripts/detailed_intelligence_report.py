#!/usr/bin/env python3
"""
GoodQ Detailed Intelligence Report
Comprehensive analysis of processed video intelligence
"""
import sqlite3
import json
from pathlib import Path
from collections import Counter
from datetime import datetime

DB_PATH = Path("L:/goodq4all/data/memory.db")

def main():
    if not DB_PATH.exists():
        print("[!] No intelligence database found")
        return
    
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    # Header
    print("\n" + "="*70)
    print("    🎬 GoodQ INTELLIGENCE REPORT - 1987-1988 Home Movie")
    print("="*70 + "\n")
    
    # Core metrics
    print("📊 CORE METRICS")
    print("-" * 70)
    
    c.execute("SELECT COUNT(*) FROM scenes")
    scene_count = c.fetchone()[0]
    print(f"  Scenes Analyzed: {scene_count}")
    
    c.execute("SELECT COUNT(*) FROM embeddings")
    emb_count = c.fetchone()[0]
    print(f"  Embeddings Created: {emb_count}")
    
    c.execute("SELECT COUNT(*) FROM links")
    link_count = c.fetchone()[0]
    print(f"  Knowledge Links: {link_count}")
    
    c.execute("SELECT COUNT(*) FROM segments")
    seg_count = c.fetchone()[0]
    print(f"  Audio Segments: {seg_count}")
    
    # Embeddings by modality
    print("\n📈 EMBEDDINGS BY MODALITY")
    print("-" * 70)
    c.execute("SELECT modality, COUNT(*) FROM embeddings GROUP BY modality ORDER BY COUNT(*) DESC")
    for mod, cnt in c.fetchall():
        pct = (cnt / emb_count * 100) if emb_count > 0 else 0
        print(f"  {mod:20s}: {cnt:4d} ({pct:5.1f}%)")
    
    # Links by type
    print("\n🔗 KNOWLEDGE LINKS BY TYPE")
    print("-" * 70)
    c.execute("SELECT relation, COUNT(*) FROM links GROUP BY relation ORDER BY COUNT(*) DESC")
    for rel, cnt in c.fetchall():
        print(f"  {rel:30s}: {cnt:4d}")
    
    # Scene analysis
    print("\n🎬 SCENE ANALYSIS")
    print("-" * 70)
    c.execute("SELECT MIN(start), MAX(end) FROM scenes")
    min_start, max_end = c.fetchone()
    if min_start is not None and max_end is not None:
        duration_sec = max_end - min_start
        duration_min = duration_sec / 60
        print(f"  Video Duration: {duration_min:.1f} minutes ({duration_sec:.1f}s)")
        print(f"  Average Scene Length: {duration_sec/scene_count:.1f}s")
    
    # Sample scenes with captions
    print("\n🎭 SCENE HIGHLIGHTS (Sample)")
    print("-" * 70)
    c.execute("""
        SELECT start, end, meta 
        FROM scenes 
        WHERE meta IS NOT NULL 
        ORDER BY start 
        LIMIT 10
    """)
    
    for i, (start, end, meta_json) in enumerate(c.fetchall(), 1):
        try:
            meta = json.loads(meta_json) if meta_json else {}
            caption = meta.get('caption', '(processing)')[:55]
            timestamp = f"{int(start//60):02d}:{int(start%60):02d}"
            duration = end - start
            print(f"  {i:2d}. [{timestamp}] ({duration:.1f}s) {caption}")
        except:
            pass
    
    # Audio segments with speakers
    print("\n🎤 AUDIO INTELLIGENCE")
    print("-" * 70)
    c.execute("""
        SELECT speaker, COUNT(*) 
        FROM segments 
        WHERE speaker IS NOT NULL 
        GROUP BY speaker 
        ORDER BY COUNT(*) DESC
    """)
    speakers = c.fetchall()
    if speakers:
        print(f"  Unique Speakers Detected: {len(speakers)}")
        for speaker, count in speakers[:5]:
            print(f"    {speaker}: {count} segments")
    else:
        print("  No speaker data available")
    
    # Check if segments have transcript data in meta
    c.execute("""
        SELECT start, meta 
        FROM segments 
        WHERE meta IS NOT NULL 
        ORDER BY start 
        LIMIT 5
    """)
    segments_meta = c.fetchall()
    if segments_meta:
        print("\n  Sample Audio Segments:")
        for start, meta_json in segments_meta:
            try:
                meta = json.loads(meta_json) if meta_json else {}
                text = meta.get('text', meta.get('transcript', ''))
                if text:
                    timestamp = f"{int(start//60):02d}:{int(start%60):02d}"
                    text_short = text[:60] + "..." if len(text) > 60 else text
                    print(f"    [{timestamp}] {text_short}")
            except:
                pass
    
    # Storage info
    print("\n💾 DATA STORAGE")
    print("-" * 70)
    db_size_mb = DB_PATH.stat().st_size / (1024 * 1024)
    print(f"  Database Size: {db_size_mb:.2f} MB")
    print(f"  Location: {DB_PATH}")
    
    # Workspace info
    workspace_dir = Path("L:/goodq4all/logs")
    if workspace_dir.exists():
        workspaces = list(workspace_dir.glob("watchdog_*"))
        if workspaces:
            latest = max(workspaces, key=lambda p: p.stat().st_mtime)
            print(f"  Latest Workspace: {latest.name}")
    
    print("\n" + "="*70)
    print("✅ Mission Status: INTELLIGENCE SUCCESSFULLY EXTRACTED")
    print("="*70 + "\n")
    
    conn.close()

if __name__ == "__main__":
    main()
