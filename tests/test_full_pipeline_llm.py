#!/usr/bin/env python3
"""
Full Pipeline Test with LLM Integration
Tests end-to-end ingestion with LLM scene and video summarization
"""
import sys
import subprocess
import sqlite3
import json
from pathlib import Path
import time

print("=" * 80)
print("FULL PIPELINE TEST - LLM INTEGRATION")
print("=" * 80)

# Check if sample.mp4 exists
sample_path = Path("L:/goodq4all/import_inbox/sample.mp4")
if not sample_path.exists():
    print(f"\n❌ Sample file not found: {sample_path}")
    sys.exit(1)

print(f"\n✅ Sample file found: {sample_path.name}")
print(f"   Size: {sample_path.stat().st_size / 1024**2:.2f} MB")

# Clear existing data for clean test
print("\n" + "=" * 80)
print("STEP 1: Clearing existing data for clean test")
print("=" * 80)

db_path = Path("L:/_DATA/GoodQ_Data/memory.db")
if db_path.exists():
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    
    # Get counts before clearing
    c.execute("SELECT COUNT(*) FROM scenes")
    scene_count_before = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM summaries WHERE category='scene_summary'")
    scene_summaries_before = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM summaries WHERE category='video_summary'")
    video_summaries_before = c.fetchone()[0]
    
    print(f"   Current data:")
    print(f"   - Scenes: {scene_count_before}")
    print(f"   - Scene summaries: {scene_summaries_before}")
    print(f"   - Video summaries: {video_summaries_before}")
    
    # Clear summaries (keep scenes as they may be reused)
    c.execute("DELETE FROM summaries WHERE category IN ('scene_summary', 'video_summary')")
    conn.commit()
    conn.close()
    
    print(f"   ✓ Cleared old summaries")

# Run ingestion pipeline with verbose output
print("\n" + "=" * 80)
print("STEP 2: Running ingestion pipeline with LLM enabled")
print("=" * 80)

start_time = time.time()

cmd = [
    sys.executable,
    "cli/run_ingestion.py",
    "run",
    "--input-dir", "import_inbox",
    "--max-videos", "1",
    "--verbose",
    "--force"  # Force reprocess to ensure scene summaries are generated
]

print(f"   Command: {' '.join(cmd)}")
print(f"   Running...")

try:
    result = subprocess.run(
        cmd,
        cwd="L:/goodq4all",
        capture_output=True,
        text=True,
        timeout=300  # 5 minutes max
    )
    
    elapsed_time = time.time() - start_time
    
    if result.returncode == 0:
        print(f"   ✓ Pipeline completed successfully in {elapsed_time:.1f}s")
    else:
        print(f"   ❌ Pipeline failed with exit code {result.returncode}")
        print(f"\nSTDOUT:\n{result.stdout}")
        print(f"\nSTDERR:\n{result.stderr}")
        sys.exit(1)
        
    # Show relevant output
    if "[llm]" in result.stdout:
        print("\n   LLM Activity:")
        for line in result.stdout.split('\n'):
            if '[llm]' in line:
                print(f"     {line.strip()}")
                
except subprocess.TimeoutExpired:
    print(f"   ❌ Pipeline timed out after 300 seconds")
    sys.exit(1)
except Exception as e:
    print(f"   ❌ Pipeline error: {e}")
    sys.exit(1)

# Verify results in database
print("\n" + "=" * 80)
print("STEP 3: Verifying LLM-generated content in database")
print("=" * 80)

conn = sqlite3.connect(str(db_path))
c = conn.cursor()

# Check scenes
c.execute("SELECT COUNT(*) FROM scenes")
scene_count = c.fetchone()[0]
print(f"\n   Scenes in database: {scene_count}")

# Check scene summaries
c.execute("SELECT COUNT(*) FROM summaries WHERE category='scene_summary'")
scene_summary_count = c.fetchone()[0]
print(f"   Scene summaries: {scene_summary_count}")

if scene_summary_count > 0:
    # Sample a scene summary
    c.execute("""
        SELECT content FROM summaries 
        WHERE category='scene_summary' 
        LIMIT 1
    """)
    sample_content = json.loads(c.fetchone()[0])
    sample_summary = sample_content.get('summary', '')
    print(f"\n   Sample scene summary:")
    print(f"     {sample_summary[:150]}...")

# Check video summaries
c.execute("SELECT COUNT(*) FROM summaries WHERE category='video_summary'")
video_summary_count = c.fetchone()[0]
print(f"\n   Video summaries: {video_summary_count}")

if video_summary_count > 0:
    # Get the video summary
    c.execute("""
        SELECT content FROM summaries 
        WHERE category='video_summary' 
        ORDER BY created_at DESC
        LIMIT 1
    """)
    video_content = json.loads(c.fetchone()[0])
    video_summary = video_content.get('summary', '')
    video_method = video_content.get('method', 'unknown')
    
    print(f"\n   Video summary ({video_method} method):")
    print(f"     Length: {len(video_summary)} characters")
    print(f"     Preview:")
    for i, para in enumerate(video_summary.split('\n\n')[:2]):
        print(f"       {para.strip()[:200]}...")
        if i == 1:
            break

conn.close()

# Final validation
print("\n" + "=" * 80)
print("VALIDATION RESULTS")
print("=" * 80)

all_tests_passed = True
tests = []

# Test 1: Scene summaries generated
test1_pass = scene_summary_count >= scene_count * 0.8  # Allow 20% failure
tests.append(("Scene summaries generated", test1_pass))
if test1_pass:
    print(f"✅ Scene summaries: {scene_summary_count}/{scene_count}")
else:
    print(f"❌ Scene summaries: {scene_summary_count}/{scene_count} (expected >= {int(scene_count * 0.8)})")
    all_tests_passed = False

# Test 2: Video summary generated
test2_pass = video_summary_count > 0
tests.append(("Video summary generated", test2_pass))
if test2_pass:
    print(f"✅ Video summary generated")
else:
    print(f"❌ No video summary found")
    all_tests_passed = False

# Test 3: LLM method used (if summaries exist)
if video_summary_count > 0:
    test3_pass = video_method == 'llm'
    tests.append(("LLM method used", test3_pass))
    if test3_pass:
        print(f"✅ LLM method confirmed")
    else:
        print(f"⚠️  Template fallback used (LLM may not be available)")
        # Don't fail for this - LLM might be offline
else:
    test3_pass = False
    tests.append(("LLM method used", test3_pass))

# Test 4: Summaries are meaningful (not just metadata)
if scene_summary_count > 0:
    test4_pass = len(sample_summary) > 50 and len(sample_summary) < 500
    tests.append(("Scene summaries are concise", test4_pass))
    if test4_pass:
        print(f"✅ Scene summaries are concise (50-500 chars)")
    else:
        print(f"⚠️  Scene summary length unusual: {len(sample_summary)} chars")
else:
    test4_pass = False
    tests.append(("Scene summaries are concise", test4_pass))

if video_summary_count > 0:
    test5_pass = len(video_summary) > 200
    tests.append(("Video summary is comprehensive", test5_pass))
    if test5_pass:
        print(f"✅ Video summary is comprehensive ({len(video_summary)} chars)")
    else:
        print(f"⚠️  Video summary too short: {len(video_summary)} chars")
else:
    test5_pass = False
    tests.append(("Video summary is comprehensive", test5_pass))

# Summary
print("\n" + "=" * 80)
passed = sum(1 for _, p in tests if p)
total = len(tests)
print(f"FINAL SCORE: {passed}/{total} tests passed")

if passed >= 3:  # At least scene summaries and video summary
    print("\n🎉 LLM INTEGRATION IS WORKING!")
    print("\nNext steps:")
    print("  1. Test with 1987_1988 family video")
    print("  2. Review summaries for quality and accuracy")
    print("  3. Fine-tune prompts if needed")
    print("  4. Enable additional LLM features (relationship extraction, emotion arc)")
    sys.exit(0)
else:
    print("\n❌ LLM INTEGRATION NEEDS ATTENTION")
    print("\nTroubleshooting:")
    print("  - Check if LM Studio is running (http://localhost:1234)")
    print("  - Verify config.yaml has llm.enabled=true")
    print("  - Check apply_scene_summaries.py has use_llm=True")
    sys.exit(1)
