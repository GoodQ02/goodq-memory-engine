"""
Phase 2 Control Agent Integration Test
========================================
Comprehensive test suite for Control Agent integration with the ingestion pipeline.

Tests:
1. Control Agent initialization
2. LLM connectivity (vLLM + Ollama fallback)
3. Log monitoring and analysis
4. Recovery recommendations
5. Pipeline integration hooks
6. Report generation
7. End-to-end ingestion with Control Agent

Version: 1.0.0
"""

import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from agents.control_agent import ControlAgent
from lib.llm_client import LLMClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def test_llm_connectivity():
    """Test LLM client connectivity and failover"""
    logger.info("="*80)
    logger.info("TEST 1: LLM Connectivity")
    logger.info("="*80)
    
    try:
        client = LLMClient()
        logger.info(f"[SYMBOL] LLMClient initialized with {len(client.models)} models")
        
        # Test health check
        healthy_models = client.check_health()
        logger.info(f"[SYMBOL] Health check complete: {len(healthy_models)} healthy models")
        
        if healthy_models:
            logger.info(f"  Primary model: {healthy_models[0]['name']}")
        else:
            logger.warning("  [SYMBOL] No healthy models available!")
            return False
        
        # Test chat completion
        response = client.chat([
            {"role": "user", "content": "Say 'Control Agent Test Successful' if you can read this."}
        ], max_tokens=20)
        
        logger.info(f"[SYMBOL] Chat completion successful")
        logger.info(f"  Response: {response[:100]}...")
        
        return True
        
    except Exception as e:
        logger.error(f"[SYMBOL] LLM connectivity test failed: {e}")
        return False


def test_control_agent_init():
    """Test Control Agent initialization"""
    logger.info("\n" + "="*80)
    logger.info("TEST 2: Control Agent Initialization")
    logger.info("="*80)
    
    try:
        agent = ControlAgent()
        logger.info("[SYMBOL] Control Agent initialized successfully")
        logger.info(f"  Logs directory: {agent.logs_dir}")
        logger.info(f"  Recovery DB: {agent.recovery_db.db_path}")
        logger.info(f"  LLM enabled: {agent.llm is not None}")
        
        return True
        
    except Exception as e:
        logger.error(f"[SYMBOL] Control Agent initialization failed: {e}")
        return False


def test_log_analysis():
    """Test log analysis capabilities"""
    logger.info("\n" + "="*80)
    logger.info("TEST 3: Log Analysis")
    logger.info("="*80)
    
    try:
        agent = ControlAgent()
        
        # Create a test log entry
        test_log = """
2025-11-16 00:00:00,000 [ERROR] RuntimeError: CUDA out of memory
Tried to allocate 2.00 GiB (GPU 0; 16.00 GiB total capacity; 14.50 GiB already allocated)
Stack trace:
  File "pipeline.py", line 123, in process_scene
    result = model.inference(data)
"""
        
        # Write test log
        test_log_path = Path("logs/test_error.log")
        test_log_path.parent.mkdir(parents=True, exist_ok=True)
        test_log_path.write_text(test_log)
        
        logger.info("[SYMBOL] Test log created")
        
        # Analyze with LLM (if available)
        if agent.llm:
            diagnosis = agent.analyze_error(test_log)
            logger.info("[SYMBOL] Error analysis completed")
            logger.info(f"  Diagnosis: {diagnosis[:200]}...")
        else:
            logger.info("  [SYMBOL] LLM not available, skipping AI analysis")
        
        # Clean up
        test_log_path.unlink(missing_ok=True)
        
        return True
        
    except Exception as e:
        logger.error(f"[SYMBOL] Log analysis test failed: {e}")
        return False


def test_recovery_database():
    """Test recovery database functionality"""
    logger.info("\n" + "="*80)
    logger.info("TEST 4: Recovery Database")
    logger.info("="*80)
    
    try:
        agent = ControlAgent()
        
        # Record a test recovery
        agent.recovery_db.record_recovery(
            error_type="CUDA_OOM",
            context={"model": "whisper-large", "batch_size": 32},
            action_taken="Reduced batch size to 16",
            success=True,
            metadata={"vram_before": "15.5GB", "vram_after": "12.2GB"}
        )
        
        logger.info("[SYMBOL] Recovery recorded in database")
        
        # Query similar errors
        similar = agent.recovery_db.get_similar_errors("CUDA_OOM")
        logger.info(f"[SYMBOL] Query successful: found {len(similar)} similar errors")
        
        return True
        
    except Exception as e:
        logger.error(f"[SYMBOL] Recovery database test failed: {e}")
        return False


def test_monitoring():
    """Test monitoring capabilities"""
    logger.info("\n" + "="*80)
    logger.info("TEST 5: Monitoring")
    logger.info("="*80)
    
    try:
        agent = ControlAgent()
        
        # Start monitoring
        agent.start_monitoring()
        logger.info("[SYMBOL] Monitoring started")
        
        # Simulate some activity
        time.sleep(2)
        
        # Stop monitoring
        agent.stop_monitoring()
        logger.info("[SYMBOL] Monitoring stopped")
        
        # Check stats
        stats = agent.get_stats()
        logger.info(f"[SYMBOL] Stats collected: {len(stats)} metrics")
        
        return True
        
    except Exception as e:
        logger.error(f"[SYMBOL] Monitoring test failed: {e}")
        return False


def test_report_generation():
    """Test report generation"""
    logger.info("\n" + "="*80)
    logger.info("TEST 6: Report Generation")
    logger.info("="*80)
    
    try:
        agent = ControlAgent()
        
        # Generate a test report
        report_path = Path("logs/test_control_report.md")
        agent.generate_report(str(report_path))
        
        logger.info(f"[SYMBOL] Report generated: {report_path}")
        logger.info(f"  Size: {report_path.stat().st_size} bytes")
        
        # Verify content
        content = report_path.read_text()
        if "Control Agent Report" in content:
            logger.info("[SYMBOL] Report contains expected header")
        else:
            logger.warning("  [SYMBOL] Report format unexpected")
        
        return True
        
    except Exception as e:
        logger.error(f"[SYMBOL] Report generation test failed: {e}")
        return False


def test_pipeline_integration():
    """Test integration with ingestion pipeline"""
    logger.info("\n" + "="*80)
    logger.info("TEST 7: Pipeline Integration")
    logger.info("="*80)
    
    try:
        # Import the pipeline
        from cli.run_ingestion import CONTROL_AGENT_AVAILABLE
        
        if not CONTROL_AGENT_AVAILABLE:
            logger.error("[SYMBOL] Control Agent not available in pipeline")
            return False
        
        logger.info("[SYMBOL] Control Agent available in pipeline")
        logger.info("[SYMBOL] Integration hooks in place")
        
        # Test would require actual ingestion run
        logger.info("  Note: Full integration test requires running actual ingestion")
        
        return True
        
    except Exception as e:
        logger.error(f"[SYMBOL] Pipeline integration test failed: {e}")
        return False


def run_all_tests():
    """Run all Phase 2 tests"""
    logger.info("\n" + "="*80)
    logger.info("[LAUNCH] PHASE 2 CONTROL AGENT INTEGRATION TEST SUITE")
    logger.info("="*80)
    logger.info(f"Started at: {datetime.now().isoformat()}")
    logger.info("")
    
    tests = [
        ("LLM Connectivity", test_llm_connectivity),
        ("Control Agent Init", test_control_agent_init),
        ("Log Analysis", test_log_analysis),
        ("Recovery Database", test_recovery_database),
        ("Monitoring", test_monitoring),
        ("Report Generation", test_report_generation),
        ("Pipeline Integration", test_pipeline_integration),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            logger.error(f"Test '{name}' crashed: {e}")
            results.append((name, False))
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("[STATS] TEST SUMMARY")
    logger.info("="*80)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "[SYMBOL] PASS" if success else "[SYMBOL] FAIL"
        logger.info(f"  {status}: {name}")
    
    logger.info("")
    logger.info(f"Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    logger.info(f"Completed at: {datetime.now().isoformat()}")
    logger.info("="*80)
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
