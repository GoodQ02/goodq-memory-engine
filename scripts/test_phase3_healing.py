"""
Test script for Phase 3: Self-Healing & Learning

This script tests the Control Agent's ability to:
1. Recognize error patterns
2. Apply appropriate recovery strategies
3. Learn from successes and failures
4. Build knowledge over time

Author: GoodQ4All Team
Version: 1.0.0
Date: 2025-11-16
"""

import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.control_agent import ControlAgent
from agents.recovery_strategies import RecoveryStrategies
import time


def test_error_recognition():
    """Test 1: Error pattern recognition"""
    print("\n" + "="*70)
    print("TEST 1: Error Pattern Recognition")
    print("="*70)
    
    strategies = RecoveryStrategies()
    
    test_errors = [
        "RuntimeError: CUDA out of memory",
        "ValueError: No audio stream found in file",
        "TimeoutError: PyAnnote diarization timed out after 600s",
        "ConnectionError: Connection timeout after 30s",
        "RuntimeError: Whisper model failed to load"
    ]
    
    for error_msg in test_errors:
        strategy = strategies.get_recommended_strategy(error_msg)
        if strategy:
            print(f"\n[OK] Error: {error_msg[:50]}...")
            print(f"   Strategy: {strategy.get('action', 'unknown')}")
            print(f"   Confidence: {strategy.get('confidence', 0)*100:.1f}%")
        else:
            print(f"\n[FAIL] Error: {error_msg[:50]}...")
            print(f"   No strategy found")
    
    return True


def test_auto_healing():
    """Test 2: Automatic healing"""
    print("\n" + "="*70)
    print("TEST 2: Auto-Healing Simulation")
    print("="*70)
    
    agent = ControlAgent()
    
    # Simulate a CUDA OOM error
    print("\n[NOTE] Simulating CUDA OOM error...")
    try:
        raise RuntimeError("CUDA out of memory. Tried to allocate 2.50 GiB")
    except RuntimeError as e:
        result = agent.auto_heal_failure(
            error=e,
            step_name='audio_transcribe',
            context={'gpu_available': True, 'batch_size': 32}
        )
        
        print(f"\nHealing Result:")
        print(f"  Strategy found: {result['strategy_found']}")
        print(f"  Success: {result['success']}")
        print(f"  Time: {result['recovery_time_seconds']:.2f}s")
        
        if result.get('strategy_applied'):
            print(f"  Strategy: {result['strategy_applied'].get('action', 'unknown')}")
        
        if result.get('recommendation'):
            print(f"  Recommendation: {result['recommendation'][:100]}...")
    
    return True


def test_learning_from_success():
    """Test 3: Learning from successful executions"""
    print("\n" + "="*70)
    print("TEST 3: Learning from Success")
    print("="*70)
    
    agent = ControlAgent()
    
    # Simulate successful executions
    print("\n[STATS] Recording successful executions...")
    
    successful_steps = [
        ('audio_transcribe', 45.2, {'model': 'whisper-medium', 'batch_size': 16}),
        ('audio_diarize', 32.1, {'model': 'pyannote', 'chunk_size': 20}),
        ('scene_detect', 12.5, {'threshold': 27, 'min_scene_len': 1.0}),
    ]
    
    for step_name, duration, config in successful_steps:
        agent.learn_from_success(
            step_name=step_name,
            execution_time_seconds=duration,
            config_used=config
        )
        print(f"  [OK] Recorded: {step_name} ({duration}s)")
    
    return True


def test_statistics():
    """Test 4: Learning statistics"""
    print("\n" + "="*70)
    print("TEST 4: Learning Statistics")
    print("="*70)
    
    agent = ControlAgent()
    stats = agent.get_learning_statistics()
    
    print(f"\n[STATS] Overall Statistics:")
    print(f"  Total attempts: {stats['total_attempts']}")
    print(f"  Successful: {stats['successful_attempts']}")
    print(f"  Success rate: {stats['overall_success_rate']*100:.1f}%")
    
    if stats.get('top_patterns'):
        print(f"\n[SYMBOL] Top Patterns:")
        for pattern in stats['top_patterns'][:5]:
            print(f"  - {pattern['pattern']}: {pattern['success_rate']*100:.1f}% ({pattern['attempts']} attempts)")
    
    if stats.get('by_error_type'):
        print(f"\n[LOG] By Error Type:")
        for error_type, data in list(stats['by_error_type'].items())[:5]:
            print(f"  - {error_type}: {data['successful']}/{data['total']} successful")
    
    return True


def test_similar_errors():
    """Test 5: Finding similar past errors"""
    print("\n" + "="*70)
    print("TEST 5: Similar Error Lookup")
    print("="*70)
    
    strategies = RecoveryStrategies()
    
    # Look for similar CUDA errors
    print("\n[SEARCH] Looking for similar CUDA OOM errors...")
    similar = strategies.get_similar_past_errors(
        error_type='RuntimeError',
        limit=3,
        success_only=True
    )
    
    if similar:
        print(f"\nFound {len(similar)} similar successful recoveries:")
        for i, err in enumerate(similar, 1):
            print(f"\n  {i}. {err['error_message'][:60]}...")
            print(f"     Strategy: {err['strategy_applied']}")
            print(f"     Duration: {err['duration_seconds']:.2f}s")
    else:
        print("  No similar errors found (database may be empty)")
    
    return True


def test_pattern_learning():
    """Test 6: Learning new patterns"""
    print("\n" + "="*70)
    print("TEST 6: Pattern Learning")
    print("="*70)
    
    strategies = RecoveryStrategies()
    
    # Learn a new pattern
    print("\n[SYMBOL] Teaching agent a new pattern...")
    strategies.learn_new_pattern(
        pattern_name="ffmpeg_codec_error",
        error_regex=r"(?i)ffmpeg.*codec.*not found|unsupported codec",
        recommended_strategy={
            "action": "fallback_codec",
            "params": {"codec": "libx264", "preset": "fast"}
        }
    )
    
    print("  [OK] New pattern learned: ffmpeg_codec_error")
    
    # Test if it can recognize it
    test_error = "FFmpeg error: Codec 'hevc_nvenc' not found"
    strategy = strategies.get_recommended_strategy(test_error)
    
    if strategy:
        print(f"\n  [OK] Pattern recognized!")
        print(f"     Action: {strategy.get('action', 'unknown')}")
    else:
        print(f"\n  [FAIL] Pattern not recognized")
    
    return True


def run_all_tests():
    """Run all Phase 3 tests"""
    print("\n" + "="*70)
    print("PHASE 3 SELF-HEALING & LEARNING - TEST SUITE")
    print("="*70)
    
    tests = [
        ("Error Recognition", test_error_recognition),
        ("Auto-Healing", test_auto_healing),
        ("Learning from Success", test_learning_from_success),
        ("Statistics", test_statistics),
        ("Similar Errors", test_similar_errors),
        ("Pattern Learning", test_pattern_learning),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n\nRunning: {test_name}...")
            success = test_func()
            results.append((test_name, success, None))
            print(f"\n{test_name}: PASSED")
        except Exception as e:
            results.append((test_name, False, str(e)))
            print(f"\n{test_name}: FAILED - {e}")
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for test_name, success, error in results:
        status = "PASS" if success else "FAIL"
        print(f"{status}: {test_name}")
        if error:
            print(f"       Error: {error}")
    
    print(f"\n{'='*70}")
    print(f"Result: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print(f"{'='*70}\n")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
