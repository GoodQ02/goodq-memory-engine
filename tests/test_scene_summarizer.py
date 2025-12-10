#!/usr/bin/env python3
"""
Test Scene Summarization Function
Validates that summaries are generated correctly before full integration test
"""
import json
import sqlite3
from pathlib import Path

# Test the summarizer directly
print("="*80)
print("TESTING SCENE SUMMARIZATION FUNCTION")
print("="*80)

# Import the function
from steps.common.scene_summarizer import generate_scene_summary_template, generate_scene_summary

# Get a real scene from the database
conn = sqlite3.connect('L:/_DATA/GoodQ_Data/memory.db')
c = conn.cursor()

c.execute("SELECT id, meta FROM scenes LIMIT 1")
result = c.fetchone()

if result:
    scene_id, meta_json = result
    scene_meta = json.loads(meta_json)
    
    print(f"\n[SCENE ID] {scene_id}")
    print(f"\n[METADATA KEYS] {list(scene_meta.keys())}")
    
    # Test template-based summary
    print("\n" + "="*80)
    print("TEMPLATE-BASED SUMMARY")
    print("="*80)
    summary = generate_scene_summary_template(scene_meta)
    print(summary)
    
    # Test full function with config
    print("\n" + "="*80)
    print("FULL FUNCTION TEST (with config)")
    print("="*80)
    
    cfg = {
        'paths': {
            'db_path': 'L:/_DATA/GoodQ_Data/memory.db'
        },
        'llm': {
            'api_url': 'http://localhost:1234/v1/chat/completions'
        }
    }
    
    summary_full = generate_scene_summary(scene_meta, cfg, use_llm=False)
    print(summary_full)
    
    # Test storing to database
    print("\n" + "="*80)
    print("TESTING DATABASE STORAGE")
    print("="*80)
    
    from steps.common.memory import store_short_term_summary
    
    # Check current count
    c.execute("SELECT COUNT(*) FROM summaries WHERE category='scene_summary'")
    before_count = c.fetchone()[0]
    print(f"Summaries before: {before_count}")
    
    # Store a test summary
    summary_data = {
        'scene_id': scene_id,
        'summary': summary_full,
        'index': scene_meta.get('index', 0),
        'start': scene_meta.get('start', 0.0),
        'end': scene_meta.get('end', 0.0),
    }
    
    store_short_term_summary(cfg, summary_data, category='scene_summary_test')
    
    # Check new count
    c.execute("SELECT COUNT(*) FROM summaries WHERE category='scene_summary_test'")
    after_count = c.fetchone()[0]
    print(f"Summaries after: {after_count}")
    
    if after_count > 0:
        print("✅ Summary storage SUCCESSFUL!")
        
        # Retrieve and display
        c.execute("SELECT content FROM summaries WHERE category='scene_summary_test' ORDER BY id DESC LIMIT 1")
        stored = c.fetchone()
        if stored:
            stored_data = json.loads(stored[0])
            print(f"\nStored summary: {stored_data.get('summary', 'N/A')}")
    else:
        print("⚠️ Summary storage FAILED!")
    
else:
    print("No scenes found in database!")

conn.close()

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)
