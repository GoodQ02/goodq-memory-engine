"""
Test Control Agent Phase 2: Auto-Healing Capabilities
======================================================

Tests the Control Agent's ability to diagnose and automatically
heal common pipeline errors.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.control_agent import ControlAgent


def test_auto_healing():
    """Test auto-healing with simulated errors"""
    
    print("="*70)
    print("[SYMBOL] CONTROL AGENT PHASE 2 - AUTO-HEALING TEST")
    print("="*70)
    print()
    
    # Initialize agent
    agent = ControlAgent()
    print()
    
    # Test scenarios
    test_cases = [
        {
            "name": "CUDA OOM Error",
            "error": """
Traceback (most recent call last):
  File "whisper_step.py", line 45, in process
    result = model.transcribe(audio)
RuntimeError: CUDA out of memory. Tried to allocate 2.50 GiB (GPU 0; 16.00 GiB total capacity; 14.21 GiB already allocated)
            """,
            "context": {
                "step_name": "whisper_transcription",
                "gpu_memory_mb": 15000,
                "file_size_mb": 850,
                "duration_sec": 180
            }
        },
        {
            "name": "No Audio Stream",
            "error": """
ValueError: No audio stream found in file: video.mp4
ffprobe output: Stream #0:0(und): Video: h264, 1920x1080
            """,
            "context": {
                "step_name": "audio_extraction",
                "file_size_mb": 500,
                "duration_sec": 5
            }
        },
        {
            "name": "PyAnnote Diarization Failure",
            "error": """
RuntimeError: PyAnnote diarization failed after 3 attempts
Possible GPU context conflict detected
Stack trace:
  File "diarization.py", line 88, in run_diarization
    diarization = pipeline(audio_file)
            """,
            "context": {
                "step_name": "speaker_diarization",
                "gpu_memory_mb": 12000,
                "duration_sec": 300
            }
        },
        {
            "name": "Connection Timeout (Unknown Pattern)",
            "error": """
TimeoutError: Connection to model server timed out after 45 seconds
No response from http://localhost:30000/v1/chat/completions
            """,
            "context": {
                "step_name": "llm_analysis",
                "duration_sec": 45
            }
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}/{len(test_cases)}: {test_case['name']}")
        print(f"{'='*70}\n")
        
        print(f"[SYMBOL] Simulated Error:")
        print(test_case['error'].strip())
        print()
        
        # Attempt auto-healing
        print(f"[CONFIG] Attempting auto-heal...")
        print()
        
        healing_report = agent.healer.auto_heal(
            error_log=test_case['error'],
            context=test_case['context']
        )
        
        # Display results
        if healing_report.get('success'):
            print(f"[OK] AUTO-HEALING SUCCESSFUL!")
            for action in healing_report['actions_taken']:
                if action['success']:
                    print(f"   [SYMBOL] {action['action']}: {action['message']}")
        else:
            print(f"[WARN]  Manual review required")
            if 'recommendation' in healing_report:
                print(f"\n[TIP] LLM Recommendation:")
                print(f"   {healing_report['recommendation'][:300]}...")
        
        # Record in agent memory
        for action in healing_report.get('actions_taken', []):
            agent.record_error(
                error_type=test_case['name'],
                error_msg=test_case['error'][:200],
                step=test_case['context'].get('step_name', ''),
                fix_attempted=action['action'],
                successful=action['success'],
                context=test_case['context']
            )
        
        results.append({
            "test": test_case['name'],
            "healed": healing_report.get('success', False),
            "actions": len(healing_report.get('actions_taken', []))
        })
        
        print()
    
    # Summary
    print("\n" + "="*70)
    print("[STATS] TEST SUMMARY")
    print("="*70)
    
    total_tests = len(results)
    successful_heals = sum(1 for r in results if r['healed'])
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Auto-Healed: {successful_heals}")
    print(f"Manual Review: {total_tests - successful_heals}")
    print(f"Success Rate: {successful_heals/total_tests*100:.1f}%")
    
    print("\nDetailed Results:")
    for r in results:
        status = "[OK] HEALED" if r['healed'] else "[WARN]  MANUAL"
        print(f"  {status} | {r['test']} ({r['actions']} actions)")
    
    print("\n" + "="*70)
    print("[TARGET] Phase 2 Testing Complete!")
    print("="*70)
    print("\nThe Control Agent can now:")
    print("  [SYMBOL] Diagnose errors using pattern matching")
    print("  [SYMBOL] Automatically apply safe healing actions")
    print("  [SYMBOL] Consult LLM for unknown error patterns")
    print("  [SYMBOL] Track healing attempts in memory")
    print("  [SYMBOL] Backup configs before modifications")
    print("\nNext: Integrate with live pipeline monitoring! [LAUNCH]")
    print()


if __name__ == "__main__":
    test_auto_healing()
