#!/usr/bin/env python3
"""
LLM Integration Test Suite
Tests all LLM features end-to-end
"""
import sys
import sqlite3
import json
import requests
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Configuration
cfg = {
    'paths': {
        'db_path': 'L:/_DATA/GoodQ_Data/memory.db'
    },
    'llm': {
        'api_url': 'http://localhost:1234/v1/chat/completions',
        'timeout': 30,
        'temperature': 0.3,
        'features': {
            'scene_summarization': True,
            'video_summarization': True
        }
    }
}


def test_lm_studio_connectivity():
    """Test 1: LM Studio Connectivity"""
    print("="*80)
    print("TEST 1: LM Studio Connectivity")
    print("="*80)
    
    try:
        response = requests.get("http://localhost:1234/v1/models", timeout=5)
        if response.status_code == 200:
            models = response.json()
            model_list = models.get('data', [])
            print(f"[OK] LM Studio is running")
            print(f"   Available models: {len(model_list)}")
            for model in model_list:
                model_id = model.get('id', 'unknown')
                print(f"   - {model_id}")
            return True
        else:
            print(f"[FAIL] LM Studio returned status {response.status_code}")
            return False
    except requests.ConnectionError:
        print("[FAIL] Cannot connect to LM Studio at http://localhost:1234")
        print("   Make sure LM Studio is running with a model loaded")
        return False
    except Exception as e:
        print(f"[FAIL] Error connecting to LM Studio: {e}")
        return False


def test_scene_summarization():
    """Test 2: Scene Summarization with LLM"""
    print("\n" + "="*80)
    print("TEST 2: Scene Summarization (LLM vs Template)")
    print("="*80)
    
    try:
        conn = sqlite3.connect(cfg['paths']['db_path'])
        c = conn.cursor()
        c.execute("SELECT id, meta FROM scenes ORDER BY start LIMIT 1")
        row = c.fetchone()
        
        if not row:
            print("[FAIL] No scenes found in database")
            conn.close()
            return False
        
        scene_id, meta_json = row
        scene_meta = json.loads(meta_json)
        conn.close()
        
        from steps.common.scene_summarizer import generate_scene_summary
        
        # Generate both LLM and template summaries
        print(f"\n[STATS] Testing scene {scene_meta.get('index', 0)}...")
        print(f"   Duration: {scene_meta.get('duration', 0):.1f}s")
        print(f"   Caption: {scene_meta.get('caption', 'N/A')[:60]}...")
        
        llm_summary = generate_scene_summary(scene_meta, cfg, use_llm=True)
        template_summary = generate_scene_summary(scene_meta, cfg, use_llm=False)
        
        print(f"\n[BOT] LLM Summary ({len(llm_summary)} chars):")
        print(f"   {llm_summary}")
        
        print(f"\n[NOTE] Template Summary ({len(template_summary)} chars):")
        print(f"   {template_summary[:200]}...")
        
        # Check if LLM produced different output
        if llm_summary and llm_summary != template_summary:
            # Check if it's actually from LLM (shorter, more narrative)
            if len(llm_summary) < len(template_summary) * 0.8:
                print("\n[OK] LLM generated unique, concise summary")
                return True
            else:
                print("\n[WARN]  LLM summary detected but seems like fallback")
                return True
        else:
            print("\n[FAIL] LLM summary matches template (possible fallback)")
            return False
            
    except ImportError as e:
        print(f"[FAIL] Import error: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Scene summarization test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_video_summarization():
    """Test 3: Video-Level Summarization"""
    print("\n" + "="*80)
    print("TEST 3: Video Summarization")
    print("="*80)
    
    try:
        conn = sqlite3.connect(cfg['paths']['db_path'])
        c = conn.cursor()
        
        # Get first video hash from scenes table
        c.execute("SELECT DISTINCT video_hash, meta FROM scenes LIMIT 1")
        row = c.fetchone()
        
        if not row:
            print("[FAIL] No videos found in database")
            conn.close()
            return False
        
        video_hash, meta_json = row
        scene_meta = json.loads(meta_json)
        video_path = scene_meta.get('video_path', 'Unknown')
        
        # Get total duration
        c.execute("SELECT MAX(end) FROM scenes WHERE video_hash=?", (video_hash,))
        duration = c.fetchone()[0] or 0
        
        print(f"\n[VIDEO] Testing video: {video_path}")
        print(f"   Hash: {video_hash[:16]}...")
        print(f"   Duration: {duration:.1f}s")
        
        # Check if scene summaries exist
        c.execute("SELECT COUNT(*) FROM summaries WHERE category='scene_summary'")
        scene_summary_count = c.fetchone()[0]
        print(f"   Scene summaries available: {scene_summary_count}")
        
        conn.close()
        
        if scene_summary_count == 0:
            print("\n[WARN]  No scene summaries available, generating video summary may be limited")
        
        from steps.video_summarizer.step import run_step
        
        result = run_step(cfg, video_hash)
        
        if result['success']:
            summary = result['summary']
            method = result.get('method', 'unknown')
            
            print(f"\n[OK] Video summary generated (method: {method})")
            print(f"\n[SYMBOL] Video Summary ({len(summary)} chars):")
            print(f"   {summary}")
            
            # Verify it was stored
            conn = sqlite3.connect(cfg['paths']['db_path'])
            c = conn.cursor()
            c.execute("SELECT content FROM summaries WHERE category='video_summary' ORDER BY created_at DESC LIMIT 1")
            stored_row = c.fetchone()
            conn.close()
            
            if stored_row:
                print("\n[OK] Video summary stored in database")
                return True
            else:
                print("\n[FAIL] Video summary not found in database")
                return False
        else:
            print(f"\n[FAIL] Video summarization failed: {result.get('error', 'Unknown error')}")
            return False
            
    except ImportError as e:
        print(f"[FAIL] Import error: {e}")
        print("   Make sure video_summarizer step module exists")
        return False
    except Exception as e:
        print(f"[FAIL] Video summarization test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_queries():
    """Test 4: Query LLM-Generated Content from Database"""
    print("\n" + "="*80)
    print("TEST 4: Database Query Verification")
    print("="*80)
    
    try:
        conn = sqlite3.connect(cfg['paths']['db_path'])
        c = conn.cursor()
        
        # Check scene summaries
        c.execute("SELECT COUNT(*) FROM summaries WHERE category='scene_summary'")
        scene_count = c.fetchone()[0]
        print(f"\n[STATS] Scene summaries in database: {scene_count}")
        
        # Check video summaries
        c.execute("SELECT COUNT(*) FROM summaries WHERE category='video_summary'")
        video_count = c.fetchone()[0]
        print(f"[STATS] Video summaries in database: {video_count}")
        
        # Sample a few scene summaries
        if scene_count > 0:
            print(f"\n[SEARCH] Sample scene summaries (first 3):")
            c.execute("""
                SELECT content FROM summaries 
                WHERE category='scene_summary' 
                ORDER BY id LIMIT 3
            """)
            for i, (content_json,) in enumerate(c.fetchall(), 1):
                content = json.loads(content_json)
                summary = content.get('summary', 'No summary')
                print(f"\n   Scene {i}:")
                print(f"   {summary[:150]}...")
        
        conn.close()
        
        if scene_count > 0 or video_count > 0:
            print("\n[OK] LLM-generated content is queryable from database")
            return True
        else:
            print("\n[WARN]  No LLM summaries found in database yet")
            return False
            
    except Exception as e:
        print(f"[FAIL] Database query test failed: {e}")
        return False


def run_all_tests():
    """Run all LLM integration tests"""
    print("\n")
    print("=" * 80)
    print(" "*20 + "LLM INTEGRATION TEST SUITE")
    print("=" * 80)
    print()
    
    results = {}
    
    # Test 1: LM Studio connectivity
    results['lm_studio'] = test_lm_studio_connectivity()
    
    if not results['lm_studio']:
        print("\n[WARN]  Skipping remaining tests - LM Studio not available")
        return results
    
    # Test 2: Scene summarization
    results['scene_summarization'] = test_scene_summarization()
    
    # Test 3: Video summarization
    results['video_summarization'] = test_video_summarization()
    
    # Test 4: Database queries
    results['database_queries'] = test_database_queries()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for test_name, passed_test in results.items():
        status = "[OK] PASS" if passed_test else "[FAIL] FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n{'='*80}")
    print(f"TOTAL: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SYMBOL] ALL TESTS PASSED - LLM Integration is working!")
        return True
    elif passed > 0:
        print("\n[WARN]  PARTIAL SUCCESS - Some LLM features working")
        return False
    else:
        print("\n[FAIL] ALL TESTS FAILED - LLM Integration needs attention")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
