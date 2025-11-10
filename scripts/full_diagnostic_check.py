#!/usr/bin/env python3
"""
Full Diagnostic Check - Analyze Complete Ingestion Results
Identifies missing data, configuration issues, and pipeline failures
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path("L:/goodq4all")
MEMORY_DB = PROJECT_ROOT / "data" / "memory.db"
LOGS_DIR = PROJECT_ROOT / "logs"

def analyze_database():
    """Comprehensive database analysis"""
    print("="*80)
    print("FULL DIAGNOSTIC CHECK - SAMPLE.MP4 INGESTION")
    print("="*80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    conn = sqlite3.connect(str(MEMORY_DB))
    c = conn.cursor()
    
    # 1. SCENES
    print("\n[1] SCENES ANALYSIS")
    print("-"*80)
    c.execute("SELECT COUNT(*) FROM scenes")
    scene_count = c.fetchone()[0]
    print(f"Total scenes: {scene_count} {'✅' if scene_count == 16 else '⚠️'}")
    
    if scene_count > 0:
        c.execute("SELECT id, start, end, meta FROM scenes ORDER BY start")
        scenes = c.fetchall()
        
        print(f"\nScene breakdown:")
        for i, (sid, start, end, meta) in enumerate(scenes, 1):
            duration = end - start
            meta_dict = json.loads(meta) if meta else {}
            print(f"  Scene {i:2d} ({sid[:8]}...): {start:7.2f}s - {end:7.2f}s ({duration:6.2f}s)")
            
            # Check meta content
            if meta_dict:
                print(f"           Meta keys: {list(meta_dict.keys())}")
            else:
                print(f"           ⚠️ NO METADATA")
    
    # 2. SEGMENTS
    print("\n[2] SEGMENTS ANALYSIS")
    print("-"*80)
    c.execute("SELECT COUNT(*) FROM segments")
    segment_count = c.fetchone()[0]
    print(f"Total segments: {segment_count}")
    
    if segment_count > 0:
        c.execute("SELECT id, start, end, speaker, meta FROM segments ORDER BY start LIMIT 5")
        print(f"\nFirst 5 segments:")
        for sid, start, end, speaker, meta in c.fetchall():
            meta_dict = json.loads(meta) if meta else {}
            text = meta_dict.get('text', 'NO TEXT')
            print(f"  {sid[:8]}... ({start:.2f}s-{end:.2f}s): [{speaker or 'UNKNOWN'}] {text[:50]}...")
    
    # 3. EMBEDDINGS
    print("\n[3] EMBEDDINGS ANALYSIS")
    print("-"*80)
    c.execute("SELECT COUNT(*) FROM embeddings")
    emb_count = c.fetchone()[0]
    print(f"Total embeddings: {emb_count}")
    
    c.execute("SELECT content_type, source_type, COUNT(*) FROM embeddings GROUP BY content_type, source_type")
    print(f"\nEmbedding breakdown:")
    for content_type, source_type, count in c.fetchall():
        print(f"  {content_type}/{source_type}: {count}")
    
    # 4. LINKS
    print("\n[4] LINKS ANALYSIS")
    print("-"*80)
    c.execute("SELECT COUNT(*) FROM links")
    link_count = c.fetchone()[0]
    print(f"Total links: {link_count}")
    
    c.execute("SELECT link_type, COUNT(*) FROM links GROUP BY link_type")
    print(f"\nLink breakdown:")
    for link_type, count in c.fetchall():
        print(f"  {link_type}: {count}")
    
    # 5. SUMMARIES - CRITICAL
    print("\n[5] SUMMARIES ANALYSIS ⚠️ CRITICAL")
    print("-"*80)
    c.execute("SELECT COUNT(*) FROM summaries")
    summary_count = c.fetchone()[0]
    print(f"Total summaries: {summary_count}")
    
    if summary_count == 0:
        print(f"⚠️ CRITICAL ISSUE: Expected 16 summaries (1 per scene), found {summary_count}")
        print(f"   This indicates the summarization pipeline step is NOT executing!")
    else:
        c.execute("SELECT summary_type, category, content FROM summaries")
        for stype, cat, content in c.fetchall():
            print(f"  {stype}/{cat}: {content[:100]}...")
    
    # 6. DATA COMPLETENESS CHECK
    print("\n[6] DATA COMPLETENESS CHECK")
    print("-"*80)
    
    # Check for scene metadata
    c.execute("SELECT COUNT(*) FROM scenes WHERE meta IS NULL OR meta = ''")
    empty_meta = c.fetchone()[0]
    if empty_meta > 0:
        print(f"⚠️ {empty_meta} scenes missing metadata")
    else:
        print(f"✅ All scenes have metadata")
    
    # Check for segment text
    c.execute("SELECT COUNT(*) FROM segments WHERE meta IS NULL OR meta = ''")
    empty_segment_meta = c.fetchone()[0]
    if empty_segment_meta > 0:
        print(f"⚠️ {empty_segment_meta} segments missing metadata/text")
    else:
        print(f"✅ All segments have metadata")
    
    # Check embedding distribution
    c.execute("SELECT COUNT(DISTINCT source_id) FROM embeddings WHERE source_type = 'scene'")
    scenes_with_emb = c.fetchone()[0]
    print(f"Scenes with embeddings: {scenes_with_emb}/{scene_count}")
    
    # 7. EXAMINE SAMPLE SCENE DATA
    print("\n[7] SAMPLE SCENE DEEP DIVE")
    print("-"*80)
    c.execute("SELECT id, meta FROM scenes ORDER BY start LIMIT 1")
    result = c.fetchone()
    if result:
        scene_id, meta = result
        meta_dict = json.loads(meta) if meta else {}
        print(f"Scene ID: {scene_id}")
        print(f"Metadata keys: {list(meta_dict.keys())}")
        print(f"\nFull metadata:")
        print(json.dumps(meta_dict, indent=2))
    
    conn.close()
    
    # 8. CHECK PIPELINE ARTIFACTS
    print("\n[8] PIPELINE ARTIFACTS CHECK")
    print("-"*80)
    
    workspace = LOGS_DIR / "watchdog_20251108_032434" / "sample"
    if workspace.exists():
        print(f"Workspace: {workspace}")
        
        # Audio files
        audio_dir = workspace / "audio"
        if audio_dir.exists():
            audio_files = list(audio_dir.glob("*.wav"))
            print(f"  Audio files: {len(audio_files)}")
        
        # Frame files
        frames_dir = workspace / "frames"
        if frames_dir.exists():
            frame_files = list(frames_dir.glob("*.jpg"))
            print(f"  Frame files: {len(frame_files)}")
        
        # Transcriptions
        transcripts_dir = workspace / "transcripts"
        if transcripts_dir.exists():
            transcript_files = list(transcripts_dir.glob("*.json"))
            print(f"  Transcript files: {len(transcript_files)}")
        else:
            print(f"  ⚠️ No transcripts directory found")
        
        # Emotions
        emotions_dir = workspace / "emotions"
        if emotions_dir.exists():
            emotion_files = list(emotions_dir.glob("*.json"))
            print(f"  Emotion files: {len(emotion_files)}")
        else:
            print(f"  ⚠️ No emotions directory found")
        
        # Vision analysis
        vision_dir = workspace / "vision"
        if vision_dir.exists():
            vision_files = list(vision_dir.glob("*.json"))
            print(f"  Vision files: {len(vision_files)}")
        else:
            print(f"  ⚠️ No vision directory found")
    
    # SUMMARY
    print("\n" + "="*80)
    print("DIAGNOSTIC SUMMARY")
    print("="*80)
    
    issues = []
    if scene_count != 16:
        issues.append(f"Expected 16 scenes, got {scene_count}")
    if summary_count == 0:
        issues.append("CRITICAL: No summaries generated")
    if empty_meta > 0:
        issues.append(f"{empty_meta} scenes missing metadata")
    if empty_segment_meta > 0:
        issues.append(f"{empty_segment_meta} segments missing metadata")
    
    if issues:
        print("⚠️ ISSUES FOUND:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✅ All checks passed!")
    
    print("\nNext steps:")
    if summary_count == 0:
        print("  1. Check summarization pipeline configuration")
        print("  2. Verify summarization step is registered in pipeline")
        print("  3. Check for errors in pipeline execution logs")

if __name__ == "__main__":
    analyze_database()
