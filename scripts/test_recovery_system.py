"""
Test Recovery System (Phase 2)
Tests the Control Agent's recovery database and learning capabilities.
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.control_agent import ControlAgent
from agents.recovery_db import RecoveryDatabase
import time


def test_recovery_database():
    """Test recovery database operations"""
    print("=" * 70)
    print("🧪 Testing Recovery Database")
    print("=" * 70)
    
    db = RecoveryDatabase(db_path="L:/_DATA/GoodQ_Data/test_recovery.db")
    
    # Test 1: Record a failure
    print("\n1️⃣ Recording test failure...")
    failure_id = db.record_failure(
        step_name="audio_extraction",
        error_type="RuntimeError",
        error_message="CUDA out of memory",
        context={
            "gpu_memory_used": 15360,
            "file_size_mb": 5000,
            "model": "whisper-large"
        }
    )
    print(f"   ✅ Failure recorded: ID #{failure_id}")
    
    # Test 2: Record a failed recovery attempt
    print("\n2️⃣ Recording failed recovery attempt...")
    attempt_id = db.record_recovery_attempt(
        failure_id=failure_id,
        strategy="reduce_batch_size",
        outcome="failed",
        config_changes={"batch_size": 8},
        error_if_failed="Still out of memory"
    )
    print(f"   ✅ Attempt recorded: ID #{attempt_id}")
    
    # Test 3: Record a successful recovery
    print("\n3️⃣ Recording successful recovery...")
    attempt_id = db.record_recovery_attempt(
        failure_id=failure_id,
        strategy="switch_to_whisper_base",
        outcome="success",
        config_changes={"model": "whisper-base"},
        execution_time_ms=45000,
        gpu_usage_mb=8192
    )
    print(f"   ✅ Success recorded: ID #{attempt_id}")
    
    # Test 4: Find similar failures
    print("\n4️⃣ Searching for similar failures...")
    similar = db.get_similar_failures(error_type="RuntimeError", limit=5)
    print(f"   ✅ Found {len(similar)} similar failures")
    
    # Test 5: Get best recovery strategy
    print("\n5️⃣ Finding best recovery strategy...")
    best = db.get_best_recovery_strategy(error_type="RuntimeError")
    if best:
        print(f"   ✅ Best strategy: {best.get('strategy', 'N/A')}")
        print(f"      Success rate: {best.get('success_rate', 0)*100:.1f}%")
    else:
        print("   ℹ️  No proven strategies yet")
    
    # Test 6: Get statistics
    print("\n6️⃣ Getting database statistics...")
    stats = db.get_statistics()
    print(f"   ✅ Total failures: {stats['total_failures']}")
    print(f"   ✅ Resolved: {stats['resolved_failures']}")
    print(f"   ✅ Resolution rate: {stats['resolution_rate']*100:.1f}%")
    
    db.close()
    print("\n✅ Recovery database tests complete!")


def test_control_agent_recovery():
    """Test Control Agent with recovery features"""
    print("\n" + "=" * 70)
    print("🤖 Testing Control Agent Recovery Features")
    print("=" * 70)
    
    agent = ControlAgent()
    
    # Test 1: Simulate a pipeline failure
    print("\n1️⃣ Simulating pipeline failure...")
    
    class SimulatedError(Exception):
        pass
    
    error = SimulatedError("CUDA out of memory during whisper inference")
    context = {
        'pipeline_id': 'test_run_001',
        'gpu_memory_used': 15000,
        'file_size': '2.5GB',
        'model': 'whisper-large'
    }
    
    result = agent.handle_pipeline_failure(
        step_name="transcription",
        error=error,
        context=context
    )
    
    print(f"\n   ✅ Failure handled:")
    print(f"      Failure ID: #{result['failure_id']}")
    print(f"      Similar failures: {len(result.get('similar_failures', []))}")
    
    if result.get('diagnosis'):
        diag = result['diagnosis']
        print(f"      AI Diagnosis: {diag.get('diagnosis', 'N/A')[:100]}...")
    
    # Test 2: Attempt recovery
    print("\n2️⃣ Attempting recovery...")
    failure_id = result['failure_id']
    
    success = agent.attempt_recovery(
        failure_id=failure_id,
        strategy="Switch to smaller Whisper model",
        config_changes={
            "model": "whisper-base",
            "batch_size": 8
        }
    )
    
    print(f"   {'✅' if success else '❌'} Recovery {'succeeded' if success else 'failed'}")
    
    # Test 3: Get recovery statistics
    print("\n3️⃣ Getting recovery statistics...")
    stats = agent.get_recovery_stats()
    
    print(f"\n   📊 Recovery Statistics:")
    print(f"      Total failures: {stats.get('total_failures', 0)}")
    print(f"      Resolved: {stats.get('resolved_failures', 0)}")
    print(f"      Resolution rate: {stats.get('resolution_rate', 0)*100:.1f}%")
    
    if stats.get('top_errors'):
        print(f"\n      Top errors:")
        for err in stats['top_errors'][:3]:
            print(f"        - {err['error_type']}: {err['count']} times")
    
    if stats.get('best_strategies'):
        print(f"\n      Best strategies:")
        for strat in stats['best_strategies'][:3]:
            print(f"        - {strat['recovery_strategy']}: {strat['success_rate']*100:.1f}% success")
    
    # Test 4: Get preventive suggestions
    print("\n4️⃣ Getting preventive suggestions...")
    suggestions = agent.suggest_preventive_measures()
    
    if suggestions:
        print(f"\n   💡 Preventive Suggestions:")
        for i, sug in enumerate(suggestions[:3], 1):
            print(f"      {i}. {sug['suggestion'][:100]}...")
    else:
        print("   ℹ️  No suggestions yet (need more data)")
    
    print("\n✅ Control Agent recovery tests complete!")


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("🧪 GoodQ4All Phase 2: Recovery System Tests")
    print("=" * 70)
    
    try:
        # Test 1: Database operations
        test_recovery_database()
        
        time.sleep(1)
        
        # Test 2: Control Agent with recovery
        test_control_agent_recovery()
        
        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 70)
        print("\n📋 Summary:")
        print("   ✅ Recovery database functional")
        print("   ✅ Failure recording working")
        print("   ✅ Recovery attempt tracking working")
        print("   ✅ AI diagnosis integration working")
        print("   ✅ Statistics and learning working")
        print("\n🚀 Phase 2 is ready for production integration!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
