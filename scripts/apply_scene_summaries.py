#!/usr/bin/env python3
"""
Apply Scene Summarization to All Existing Scenes
Generates and saves summaries for all scenes in the database
"""
import sqlite3
import json
from pathlib import Path

from steps.common.scene_summarizer import generate_scene_summary
from steps.common.memory import append_long_term_summary

# Configuration
cfg = {
    'paths': {
        'db_path': 'L:/_DATA/GoodQ_Data/memory.db'
    },
    'llm': {
        'api_url': 'http://localhost:1234/v1/chat/completions'
    }
}

conn = sqlite3.connect(cfg['paths']['db_path'])
c = conn.cursor()

print("="*80)
print("APPLYING SCENE SUMMARIZATION TO ALL SCENES")
print("="*80)

# Get all scenes
c.execute("SELECT id, meta FROM scenes ORDER BY start")
scenes = c.fetchall()

print(f"\nFound {len(scenes)} scenes")

# Check existing summaries
c.execute("SELECT COUNT(*) FROM summaries WHERE category='scene_summary'")
existing = c.fetchone()[0]
print(f"Existing scene summaries: {existing}")

if existing > 0:
    print("\nClearing old scene summaries...")
    conn.execute("DELETE FROM summaries WHERE category='scene_summary'")
    conn.commit()

# Generate summaries for all scenes
print(f"\nGenerating summaries...")
success_count = 0
error_count = 0

for i, (scene_id, meta_json) in enumerate(scenes, 1):
    try:
        scene_meta = json.loads(meta_json)
        
        # Generate summary
        summary_text = generate_scene_summary(scene_meta, cfg, use_llm=True)
        
        # Prepare summary data
        summary_data = {
            'scene_id': scene_id,
            'summary': summary_text,
            'index': scene_meta.get('index', i-1),
            'start': scene_meta.get('start', 0.0),
            'end': scene_meta.get('end', 0.0),
            'duration': scene_meta.get('duration', 0.0)
        }
        
        # Store summary
        append_long_term_summary(
            cfg, 
            summary_data, 
            category='scene_summary',
            fields=['scene_id', 'summary', 'index', 'start', 'end', 'duration'],
            max_entries=1000
        )
        
        print(f"  [{i}/{len(scenes)}] Scene {scene_meta.get('index', i-1)}: SUCCESS")
        success_count += 1
        
    except Exception as e:
        print(f"  [{i}/{len(scenes)}] Scene {i-1}: ERROR - {e}")
        error_count += 1

# Verify results
c.execute("SELECT COUNT(*) FROM summaries WHERE category='scene_summary'")
final_count = c.fetchone()[0]

print("\n" + "="*80)
print("SUMMARY GENERATION COMPLETE")
print("="*80)
print(f"Total scenes: {len(scenes)}")
print(f"Summaries created: {final_count}")
print(f"Success: {success_count}")
print(f"Errors: {error_count}")

if final_count == len(scenes):
    print("\nSTATUS: ALL SCENES SUMMARIZED!")
else:
    print(f"\nWARNING: Expected {len(scenes)}, got {final_count}")

# Show sample summaries
print("\n" + "="*80)
print("SAMPLE SUMMARIES (First 3)")
print("="*80)

c.execute("SELECT content FROM summaries WHERE category='scene_summary' ORDER BY id LIMIT 3")
for i, (content_json,) in enumerate(c.fetchall(), 1):
    content = json.loads(content_json)
    print(f"\nScene {i-1}:")
    print(f"  {content.get('summary', 'No summary')[:200]}")

conn.close()

print("\n" + "="*80)
print("DONE!")
print("="*80)
