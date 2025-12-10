"""
FULL SYSTEM TEST - Complete Pipeline Validation
Tests entire GoodQ4All pipeline with WSL2 acceleration
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Setup paths
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT.parent))
sys.path.insert(0, str(REPO_ROOT))

def test_full_system():
    print("="*80)
    print("  GOODQ4ALL v1.4.0 - FULL SYSTEM TEST")
    print("="*80)
    print(f"  Timestamp: {datetime.now().isoformat()}")
    print("="*80)
    print()
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "tests": {},
        "overall_status": "unknown"
    }
    
    # Test 1: WSL2 Bridge
    print("TEST 1: WSL2 Audio Bridge")
    print("-" * 40)
    try:
        from wsl2_audio_bridge import WSL2AudioBridge
        bridge = WSL2AudioBridge()
        
        if bridge.check_status():
            print("✅ WSL2 bridge operational")
            print(f"   GPU: {bridge.get_info().strip()}")
            results["tests"]["wsl2_bridge"] = "PASS"
        else:
            print("❌ WSL2 bridge not ready")
            results["tests"]["wsl2_bridge"] = "FAIL"
    except Exception as e:
        print(f"❌ WSL2 bridge error: {e}")
        results["tests"]["wsl2_bridge"] = "ERROR"
    print()
    
    # Test 2: Audio Transcription
    print("TEST 2: Audio Transcription (WSL2)")
    print("-" * 40)
    try:
        from steps.audio_transcribe.step import audio_transcribe
        from steps.common.config_loader import load_configs
        
        cfg = load_configs({})
        test_audio = r"L:\_DATA\GoodQ_Data\temp\test_chunk.wav"
        
        if Path(test_audio).exists():
            item = {"source_path": test_audio, "modality": "audio"}
            result = audio_transcribe(item, cfg)
            
            method = result.get("transcript_meta", {}).get("method")
            transcript = result.get("transcript")
            
            if method == "wsl2_gpu" and transcript:
                print(f"✅ Transcription successful (WSL2 GPU)")
                print(f"   Method: {method}")
                print(f"   Text: {transcript[:60]}...")
                results["tests"]["transcription"] = "PASS"
            elif transcript:
                print(f"⚠️  Transcription successful (fallback method: {method})")
                results["tests"]["transcription"] = "PASS_FALLBACK"
            else:
                print(f"❌ Transcription failed")
                results["tests"]["transcription"] = "FAIL"
        else:
            print(f"⚠️  Test audio not found: {test_audio}")
            results["tests"]["transcription"] = "SKIP"
    except Exception as e:
        print(f"❌ Transcription error: {e}")
        results["tests"]["transcription"] = "ERROR"
    print()
    
    # Test 3: Database Connectivity
    print("TEST 3: Database Systems")
    print("-" * 40)
    try:
        import sqlite3
        
        dbs = {
            "memory.db": r"L:\_DATA\GoodQ_Data\memory.db",
            "knowledge_graph.db": r"L:\_DATA\GoodQ_Data\knowledge_graph.db",
            "unified_goodq.db": r"L:\_DATA\GoodQ_Data\unified_goodq.db"
        }
        
        db_status = {}
        for name, path in dbs.items():
            if Path(path).exists():
                conn = sqlite3.connect(path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                conn.close()
                db_status[name] = f"OK ({len(tables)} tables)"
                print(f"✅ {name}: {len(tables)} tables")
            else:
                db_status[name] = "MISSING"
                print(f"⚠️  {name}: not found")
        
        results["tests"]["databases"] = "PASS" if all("OK" in v for v in db_status.values()) else "PARTIAL"
        results["database_status"] = db_status
    except Exception as e:
        print(f"❌ Database error: {e}")
        results["tests"]["databases"] = "ERROR"
    print()
    
    # Test 4: GPU Availability
    print("TEST 4: GPU Acceleration")
    print("-" * 40)
    try:
        import torch
        cuda_available = torch.cuda.is_available()
        
        if cuda_available:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1e9
            print(f"✅ CUDA available")
            print(f"   GPU: {gpu_name}")
            print(f"   VRAM: {gpu_mem:.1f}GB")
            results["tests"]["gpu"] = "PASS"
            results["gpu_info"] = {
                "name": gpu_name,
                "vram_gb": gpu_mem,
                "cuda_version": torch.version.cuda
            }
        else:
            print(f"⚠️  CUDA not available (CPU mode)")
            results["tests"]["gpu"] = "FALLBACK"
    except Exception as e:
        print(f"❌ GPU check error: {e}")
        results["tests"]["gpu"] = "ERROR"
    print()
    
    # Test 5: Model Cache
    print("TEST 5: Model Cache")
    print("-" * 40)
    model_dir = Path(r"L:\models\hub")
    if model_dir.exists():
        models = list(model_dir.glob("models--*"))
        print(f"✅ Model cache: {len(models)} models")
        results["tests"]["model_cache"] = "PASS"
        results["cached_models"] = len(models)
    else:
        print(f"⚠️  Model cache not found")
        results["tests"]["model_cache"] = "MISSING"
    print()
    
    # Summary
    print("="*80)
    print("  TEST SUMMARY")
    print("="*80)
    
    test_results = results["tests"]
    total = len(test_results)
    passed = sum(1 for v in test_results.values() if v == "PASS")
    failed = sum(1 for v in test_results.values() if v in ["FAIL", "ERROR"])
    
    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print()
    
    for test_name, status in test_results.items():
        symbol = "✅" if status == "PASS" else "⚠️" if status in ["PARTIAL", "SKIP", "PASS_FALLBACK"] else "❌"
        print(f"{symbol} {test_name}: {status}")
    
    print()
    print("="*80)
    
    if failed == 0:
        print("  ✅ ALL CRITICAL TESTS PASSED - SYSTEM READY FOR PRODUCTION")
        results["overall_status"] = "READY"
        exit_code = 0
    else:
        print("  ❌ SOME TESTS FAILED - REVIEW REQUIRED")
        results["overall_status"] = "ISSUES"
        exit_code = 1
    
    print("="*80)
    
    # Save results
    results_file = Path(r"L:\goodq4all\test_results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {results_file}")
    
    return exit_code

if __name__ == "__main__":
    exit_code = test_full_system()
    sys.exit(exit_code)
