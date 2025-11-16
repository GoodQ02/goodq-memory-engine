#!/usr/bin/env python3
"""
Phase 3 Test: Control Agent Pipeline Integration
Tests the live integration of AI Control Agent with the ingestion pipeline.
"""

import sys
import time
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from agents.control_agent import ControlAgent
from lib.llm_client import LLMClient

def test_phase3_integration():
    """Test Control Agent pipeline integration"""
    print("=" * 80)
    print("[TEST] PHASE 3: CONTROL AGENT PIPELINE INTEGRATION")
    print("=" * 80)
    print()
    
    # Test 1: Initialize Control Agent
    print("[*] Test 1: Initialize Control Agent")
    print("-" * 80)
    try:
        agent = ControlAgent()
        print("[OK] Control Agent initialized successfully")
        print(f"   - LLM Client: {agent.llm.__class__.__name__}")
        print(f"   - Config Healer: {agent.healer.__class__.__name__}")
        print(f"   - Memory DB: {agent.db_path}")
        print()
    except Exception as e:
        print(f"[FAIL] Failed to initialize Control Agent: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Test file detection callback
    print("[*] Test 2: Test File Detection Callback")
    print("-" * 80)
    try:
        agent.on_file_detected("test_video.mp4", "video", 100 * 1024 * 1024)
        print("[OK] File detection callback successful")
        print()
    except Exception as e:
        print(f"[FAIL] File detection callback failed: {e}")
        return False
    
    # Test 3: Test processing start callback
    print("[*] Test 3: Test Processing Start Callback")
    print("-" * 80)
    try:
        agent.on_processing_start("test_video.mp4", "video")
        print("[OK] Processing start callback successful")
        print()
    except Exception as e:
        print(f"[FAIL] Processing start callback failed: {e}")
        return False
    
    # Test 4: Simulate an error and get AI diagnosis
    print("[*] Test 4: AI Error Diagnosis")
    print("-" * 80)
    try:
        test_error = "RuntimeError: CUDA out of memory. Tried to allocate 2.5 GB"
        context = {
            'step': 'whisper_transcription',
            'file': 'test_video.mp4',
            'gpu_memory_used': '14 GB',
            'gpu_memory_total': '16 GB'
        }
        
        diagnosis = agent.analyze_error(test_error, context)
        
        print("[OK] AI Diagnosis received:")
        print(f"   [DIAG] Diagnosis: {diagnosis.get('diagnosis', 'N/A')[:200]}...")
        print(f"   [ROOT] Root Cause: {diagnosis.get('root_cause', 'N/A')[:200]}...")
        print(f"   [FIX] Recommended Action: {diagnosis.get('recommended_action', 'N/A')}")
        print(f"   [CONF] Confidence: {diagnosis.get('confidence', 'N/A')}")
        print()
    except Exception as e:
        print(f"[FAIL] AI diagnosis failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 5: Test processing completion callback
    print("[*] Test 5: Test Processing Completion Callback")
    print("-" * 80)
    try:
        # Simulate success
        agent.on_processing_complete("test_video.mp4", success=True)
        print("[OK] Success callback successful")
        
        # Simulate failure
        agent.on_processing_complete("test_video.mp4", success=False, error="Test error")
        print("[OK] Failure callback successful")
        print()
    except Exception as e:
        print(f"[FAIL] Processing completion callback failed: {e}")
        return False
    
    # Test 6: Generate comprehensive report
    print("[*] Test 6: Get System Status")
    print("-" * 80)
    try:
        # Query database for recent activity
        import sqlite3
        conn = sqlite3.connect(agent.db_path)
        cursor = conn.cursor()
        
        # Get recent file tracking
        cursor.execute("SELECT * FROM file_tracking ORDER BY created_at DESC LIMIT 5")
        files = cursor.fetchall()
        
        # Get recent errors
        cursor.execute("SELECT * FROM error_memory ORDER BY created_at DESC LIMIT 5")
        errors = cursor.fetchall()
        
        conn.close()
        
        print("[OK] System status retrieved successfully")
        print(f"   - Files tracked: {len(files)}")
        print(f"   - Errors recorded: {len(errors)}")
        print()
    except Exception as e:
        print(f"[FAIL] Status retrieval failed: {e}")
        return False
    
    # Test 7: Verify watchdog integration
    print("[*] Test 7: Verify Watchdog Integration")
    print("-" * 80)
    try:
        from scripts.watchdog_ingest import WatchdogProcessor
        monitor = WatchdogProcessor()
        
        if monitor.control_agent:
            print("[OK] Watchdog has Control Agent integrated")
            print(f"   - Agent Type: {monitor.control_agent.__class__.__name__}")
        else:
            print("[WARN] Watchdog running without Control Agent (graceful degradation)")
        print()
    except Exception as e:
        print(f"[FAIL] Watchdog integration check failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("=" * 80)
    print("[SUCCESS] PHASE 3 INTEGRATION TEST COMPLETE!")
    print("=" * 80)
    print()
    print("[OK] All tests passed!")
    print()
    print("[NEXT STEPS]:")
    print("   1. Start the ingestion pipeline: python scripts/watchdog_ingest.py")
    print("   2. Drop a test file in L:/goodq4all/import_inbox/")
    print("   3. Watch the AI Control Agent provide real-time diagnostics")
    print("   4. Check the report: python scripts/run_control_agent.py")
    print()
    
    return True


if __name__ == "__main__":
    try:
        success = test_phase3_integration()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[WARN] Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[FAIL] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
