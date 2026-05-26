#!/usr/bin/env python3
"""
GoodQ Mission Logger - Test & Demo Script
Tests all mission logging features and provides usage examples
"""

import sys
import time
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parents[1]))

from lib.goodq_logger import get_goodq_logger, QuickMission, MissionColors
from lib.mission_components import get_component_name, format_duration, format_file_size

def test_basic_logging():
    """Test basic mission logging"""
    print(f"\n{MissionColors.BOLD}{'='*70}{MissionColors.END}")
    print(f"{MissionColors.BOLD}TEST 1: Basic Mission Logging{MissionColors.END}")
    print(f"{MissionColors.BOLD}{'='*70}{MissionColors.END}\n")
    
    logger = get_goodq_logger('test.basic', component='System Test')
    
    logger.debug("Q Branch technical diagnostics online")
    logger.info("Mission system initialized")
    logger.warning("Proceeding with test protocol - proceed with caution")
    logger.error("Simulated mission failure for testing")
    logger.critical("Simulated critical alert for testing")
    
    time.sleep(1)


def test_mission_methods():
    """Test mission-specific logging methods"""
    print(f"\n{MissionColors.BOLD}{'='*70}{MissionColors.END}")
    print(f"{MissionColors.BOLD}TEST 2: Mission-Specific Methods{MissionColors.END}")
    print(f"{MissionColors.BOLD}{'='*70}{MissionColors.END}\n")
    
    logger = get_goodq_logger('test.mission', component='Visual Intel')
    
    logger.mission_start("Image Analysis Test")
    time.sleep(0.5)
    
    logger.agent_action("Loading YOLO model", "v8n configuration")
    time.sleep(0.3)
    
    logger.gadget_deployed("CUDA Acceleration", "active")
    time.sleep(0.3)
    
    logger.target_acquired("person", confidence=0.95)
    logger.target_acquired("car", confidence=0.88)
    logger.target_acquired("dog", confidence=0.92)
    time.sleep(0.3)
    
    logger.intel_received("Detection Results", "3 targets identified")
    time.sleep(0.3)
    
    logger.classified("GPU memory usage: 8.2 GB / 16 GB")
    time.sleep(0.3)
    
    logger.mission_complete("Image Analysis Test", duration=2.1)
    time.sleep(1)


def test_progress_tracking():
    """Test progress bar functionality"""
    print(f"\n{MissionColors.BOLD}{'='*70}{MissionColors.END}")
    print(f"{MissionColors.BOLD}TEST 3: Progress Tracking{MissionColors.END}")
    print(f"{MissionColors.BOLD}{'='*70}{MissionColors.END}\n")
    
    logger = get_goodq_logger('test.progress', component='Recon Scanner')
    
    logger.mission_start("Scene Detection")
    
    # Test progress bar
    total_scenes = 50
    progress = logger.create_progress(
        'scenes',
        total=total_scenes,
        desc='Analyzing surveillance footage',
        unit='scenes'
    )
    
    for i in range(total_scenes):
        time.sleep(0.05)  # Simulate processing
        logger.update_progress('scenes', 1)
    
    logger.complete_progress('scenes')
    logger.intel_received("Scene Detection", f"{total_scenes} scenes identified")
    logger.mission_complete("Scene Detection", duration=2.5)
    time.sleep(1)


def test_mission_phases():
    """Test mission phase context manager"""
    print(f"\n{MissionColors.BOLD}{'='*70}{MissionColors.END}")
    print(f"{MissionColors.BOLD}TEST 4: Mission Phases{MissionColors.END}")
    print(f"{MissionColors.BOLD}{'='*70}{MissionColors.END}\n")
    
    logger = get_goodq_logger('test.phases', component='Comms Decrypt')
    
    logger.mission_start("Audio Intelligence")
    
    with logger.mission_phase("Audio Extraction"):
        time.sleep(0.5)
        logger.info("Extracted 42 audio segments")
    
    with logger.mission_phase("Speaker Diarization"):
        time.sleep(0.8)
        logger.info("Identified 3 distinct speakers")
    
    with logger.mission_phase("Transcription"):
        time.sleep(1.0)
        logger.info("Generated 127 transcript segments")
    
    logger.mission_complete("Audio Intelligence", duration=2.3)
    time.sleep(1)


def test_component_names():
    """Test component name mapping"""
    print(f"\n{MissionColors.BOLD}{'='*70}{MissionColors.END}")
    print(f"{MissionColors.BOLD}TEST 5: Component Name Mapping{MissionColors.END}")
    print(f"{MissionColors.BOLD}{'='*70}{MissionColors.END}\n")
    
    steps = [
        'video_scene_detect',
        'audio_transcribe',
        'image_caption',
        'object_detect',
        'face_embed',
        'graph_builder',
        'home_assistant_status',
    ]
    
    for step in steps:
        component = get_component_name(step)
        print(f"  {step:25s} → {MissionColors.INFO}{component}{MissionColors.END}")
    
    time.sleep(1)


def test_quick_mission():
    """Test quick mission logging"""
    print(f"\n{MissionColors.BOLD}{'='*70}{MissionColors.END}")
    print(f"{MissionColors.BOLD}TEST 6: Quick Mission Logging{MissionColors.END}")
    print(f"{MissionColors.BOLD}{'='*70}{MissionColors.END}\n")
    
    QuickMission.start("Quick Test Operation")
    time.sleep(0.5)
    
    QuickMission.status("Deploying test assets")
    time.sleep(0.5)
    
    QuickMission.success("Test assets deployed successfully")
    time.sleep(0.5)
    
    QuickMission.status("Running validation checks")
    time.sleep(0.5)
    
    QuickMission.fail("Simulated validation failure for testing")
    time.sleep(1)


def test_formatting_utils():
    """Test formatting utilities"""
    print(f"\n{MissionColors.BOLD}{'='*70}{MissionColors.END}")
    print(f"{MissionColors.BOLD}TEST 7: Formatting Utilities{MissionColors.END}")
    print(f"{MissionColors.BOLD}{'='*70}{MissionColors.END}\n")
    
    # Test duration formatting
    durations = [0.5, 45.2, 125.8, 3725.5]
    print(f"  Duration Formatting:")
    for d in durations:
        formatted = format_duration(d)
        print(f"    {d:8.1f}s → {formatted}")
    
    # Test file size formatting
    sizes = [1024, 1024*1024, 1024*1024*1024, 1024*1024*1024*50]
    print(f"\n  File Size Formatting:")
    for s in sizes:
        formatted = format_file_size(s)
        print(f"    {s:15d} bytes → {formatted}")
    
    time.sleep(1)


def test_error_handling():
    """Test error logging"""
    print(f"\n{MissionColors.BOLD}{'='*70}{MissionColors.END}")
    print(f"{MissionColors.BOLD}TEST 8: Error Handling{MissionColors.END}")
    print(f"{MissionColors.BOLD}{'='*70}{MissionColors.END}\n")
    
    logger = get_goodq_logger('test.errors', component='Target Identification')
    
    logger.mission_start("Object Detection")
    
    try:
        with logger.mission_phase("Model Deployment"):
            logger.gadget_deployed("YOLO v8n", "loading")
            # Simulate error
            raise RuntimeError("Simulated GPU memory allocation failure")
    except Exception as e:
        logger.error(f"Mission compromised: {e}")
        logger.classified(f"Technical details: {type(e).__name__}")
        logger.info("Attempting recovery with CPU fallback")
    
    logger.warning("Operation completed with degraded performance")
    logger.mission_complete("Object Detection", duration=1.5)
    time.sleep(1)


def run_all_tests():
    """Run all test suites"""
    print(f"\n{MissionColors.BOLD}{MissionColors.CLASSIFIED}")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║                  GOODQ MISSION LOGGER TEST SUITE                   ║")
    print("║                    Q BRANCH - CLASSIFIED                           ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print(f"{MissionColors.END}\n")
    
    tests = [
        test_basic_logging,
        test_mission_methods,
        test_progress_tracking,
        test_mission_phases,
        test_component_names,
        test_quick_mission,
        test_formatting_utils,
        test_error_handling,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n{MissionColors.ERROR}[SYMBOL] Test failed: {test_func.__name__}{MissionColors.END}")
            print(f"{MissionColors.ERROR}  Error: {e}{MissionColors.END}\n")
    
    # Summary
    print(f"\n{MissionColors.BOLD}{'='*70}{MissionColors.END}")
    print(f"{MissionColors.BOLD}TEST SUMMARY{MissionColors.END}")
    print(f"{MissionColors.BOLD}{'='*70}{MissionColors.END}\n")
    
    total = passed + failed
    print(f"  Tests Run: {total}")
    print(f"  {MissionColors.SUCCESS}Passed: {passed}{MissionColors.END}")
    if failed > 0:
        print(f"  {MissionColors.ERROR}Failed: {failed}{MissionColors.END}")
    
    if failed == 0:
        print(f"\n{MissionColors.SUCCESS}[SYMBOL] ALL SYSTEMS GO - MISSION LOGGER OPERATIONAL{MissionColors.END}\n")
        return 0
    else:
        print(f"\n{MissionColors.ERROR}[SYMBOL] SYSTEM CHECK FAILED - REVIEW ERRORS ABOVE{MissionColors.END}\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
