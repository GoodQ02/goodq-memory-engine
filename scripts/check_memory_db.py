#!/usr/bin/env python3
"""
Check memory database contents
"""
import sqlite3
import json
from pathlib import Path

def check_memory_db():
    # Try multiple possible locations
    possible_paths = [
        Path("L:/GoodQ_Data/memory.db"),
        Path("L:/_DATA/GoodQ_Data/data/memory_db/memory.db"),
        Path("L:/zenml_project/data/memory.db"),
    ]
    
    db_path = None
    for p in possible_paths:
        if p.exists():
            db_path = p
            break
    
    
    if not db_path.exists():
        print("❌ Memory database not found at", db_path)
        return
    
    print("="*70)
    print("MEMORY DATABASE INSPECTION")
    print("="*70)
    print(f"Database: {db_path}")
    print(f"Size: {db_path.stat().st_size:,} bytes")
    print()
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get all tables
    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"📋 Tables: {', '.join(tables)}")
    print()
    
    # Check each table
    for table in tables:
        count = c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        print(f"  {table}: {count} rows")
        
        # Show sample data if exists
        if count > 0:
            sample = c.execute(f'SELECT * FROM {table} LIMIT 1').fetchone()
            if sample:
                print(f"    Sample columns: {', '.join(sample.keys())}")
    
    print()
    
    # Detailed scene inspection
    if 'scenes' in tables:
        print("🎬 SCENE DETAILS")
        print("-" * 70)
        scenes = c.execute('''
            SELECT video_id, scene_id, start_time, end_time, 
                   frame_path, audio_path
            FROM scenes 
            LIMIT 10
        ''').fetchall()
        
        for scene in scenes:
            print(f"  Scene: {scene['scene_id']}")
            print(f"    Video: {scene['video_id']}")
            print(f"    Time: {scene['start_time']:.2f}s - {scene['end_time']:.2f}s")
            print(f"    Frame: {scene['frame_path'] if scene['frame_path'] else 'None'}")
            print(f"    Audio: {scene['audio_path'] if scene['audio_path'] else 'None'}")
            print()
    
    # Check for actual analysis data
    print("🔍 ANALYSIS DATA CHECK")
    print("-" * 70)
    
    # Check if scenes have captions
    if 'scenes' in tables:
        caption_count = c.execute('''
            SELECT COUNT(*) FROM scenes 
            WHERE caption IS NOT NULL AND caption != ''
        ''').fetchone()[0]
        print(f"  Scenes with captions: {caption_count}")
        
        # Sample caption
        if caption_count > 0:
            sample = c.execute('''
                SELECT scene_id, caption FROM scenes 
                WHERE caption IS NOT NULL AND caption != ''
                LIMIT 1
            ''').fetchone()
            print(f"    Sample: [{sample['scene_id']}] {sample['caption'][:100]}...")
        print()
    
    # Check embeddings
    if 'embeddings' in tables:
        emb_count = c.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0]
        print(f"  Total embeddings: {emb_count}")
        
        if emb_count > 0:
            types = c.execute('''
                SELECT embedding_type, COUNT(*) as count 
                FROM embeddings 
                GROUP BY embedding_type
            ''').fetchall()
            for t in types:
                print(f"    {t['embedding_type']}: {t['count']}")
        print()
    
    # Check objects detected
    if 'objects' in tables:
        obj_count = c.execute('SELECT COUNT(*) FROM objects').fetchone()[0]
        print(f"  Objects detected: {obj_count}")
        
        if obj_count > 0:
            top_objects = c.execute('''
                SELECT label, COUNT(*) as count 
                FROM objects 
                GROUP BY label 
                ORDER BY count DESC 
                LIMIT 10
            ''').fetchall()
            print("    Top objects:")
            for obj in top_objects:
                print(f"      {obj['label']}: {obj['count']}")
        print()
    
    conn.close()
    print("="*70)

if __name__ == "__main__":
    check_memory_db()
