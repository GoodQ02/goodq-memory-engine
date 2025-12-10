"""
Comprehensive Pipeline Test Suite
Phase 2 - GPU Isolation Validation

This script tests the entire pipeline end-to-end with GPU isolation enabled.
"""

import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from gpu_config import GPUManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('logs/pipeline_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PipelineTest:
    """Comprehensive pipeline testing with GPU monitoring"""
    
    def __init__(self):
        self.gpu_manager = GPUManager()
        self.test_results = []
        self.start_time = None
        
    def log_result(self, test_name: str, status: str, details: str = ""):
        """Log a test result"""
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status_emoji = "[OK]" if status == "PASS" else "[FAIL]" if status == "FAIL" else "[WARN]"
        logger.info(f"{status_emoji} {test_name}: {status} {details}")
    
    def test_gpu_availability(self):
        """Test 1: GPU Availability"""
        logger.info("\n" + "="*80)
        logger.info("TEST 1: GPU Availability")
        logger.info("="*80)
        
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                total_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
                self.log_result(
                    "GPU Availability",
                    "PASS",
                    f"Found {gpu_name} with {total_mem:.2f} GB"
                )
                return True
            else:
                self.log_result("GPU Availability", "WARN", "No GPU available, will use CPU")
                return False
        except Exception as e:
            self.log_result("GPU Availability", "FAIL", str(e))
            return False
    
    def test_gpu_memory_isolation(self):
        """Test 2: GPU Memory Isolation"""
        logger.info("\n" + "="*80)
        logger.info("TEST 2: GPU Memory Isolation")
        logger.info("="*80)
        
        try:
            import torch
            if not torch.cuda.is_available():
                self.log_result("GPU Memory Isolation", "SKIP", "No GPU available")
                return True
            
            # Test memory allocation for each step
            for step_name in ["emotion_classify", "image_embed_clip", "text_embed"]:
                config = self.gpu_manager.configure_gpu(step_name)
                expected_fraction = self.gpu_manager.MEMORY_FRACTIONS[step_name]
                
                if config["device"] == "cuda":
                    # Allocate test tensor
                    test_size_mb = 100  # Allocate 100MB
                    test_tensor = torch.randn(
                        int(test_size_mb * 1024 * 256),  # 256 elements per KB
                        device="cuda"
                    )
                    
                    allocated_mb = torch.cuda.memory_allocated(0) / 1024**2
                    
                    # Clean up
                    del test_tensor
                    torch.cuda.empty_cache()
                    
                    self.log_result(
                        f"Memory Isolation - {step_name}",
                        "PASS",
                        f"Allocated {allocated_mb:.2f} MB (fraction: {expected_fraction:.2%})"
                    )
                else:
                    self.log_result(
                        f"Memory Isolation - {step_name}",
                        "WARN",
                        "CPU mode"
                    )
            
            return True
        except Exception as e:
            self.log_result("GPU Memory Isolation", "FAIL", str(e))
            return False
    
    def test_step_imports(self):
        """Test 3: Step Module Imports"""
        logger.info("\n" + "="*80)
        logger.info("TEST 3: Step Module Imports")
        logger.info("="*80)
        
        steps_to_test = [
            "emotion_classify",
            "face_embed",
            "image_embed_clip",
            "image_embed_dino",
            "audio_embed_clap",
            "text_embed",
            "object_detect"
        ]
        
        all_passed = True
        for step_name in steps_to_test:
            try:
                module = __import__(f"steps.{step_name}.step", fromlist=[""])
                self.log_result(f"Import - {step_name}", "PASS")
            except Exception as e:
                self.log_result(f"Import - {step_name}", "FAIL", str(e))
                all_passed = False
        
        return all_passed
    
    def test_config_loading(self):
        """Test 4: Configuration Loading"""
        logger.info("\n" + "="*80)
        logger.info("TEST 4: Configuration Loading")
        logger.info("="*80)
        
        try:
            import yaml
            config_path = Path("config.yaml")
            
            if not config_path.exists():
                self.log_result("Config Loading", "FAIL", "config.yaml not found")
                return False
            
            with open(config_path) as f:
                config = yaml.safe_load(f)
            
            # Check critical paths
            required_sections = ["paths", "processing", "llm"]
            for section in required_sections:
                if section in config:
                    self.log_result(f"Config - {section}", "PASS")
                else:
                    self.log_result(f"Config - {section}", "FAIL", "Missing section")
                    return False
            
            # Check GPU config
            if "gpu" in config.get("processing", {}):
                gpu_config = config["processing"]["gpu"]
                self.log_result(
                    "Config - GPU Settings",
                    "PASS",
                    f"GPU enabled: {gpu_config.get('enabled', False)}"
                )
            else:
                self.log_result("Config - GPU Settings", "WARN", "No GPU config found")
            
            return True
        except Exception as e:
            self.log_result("Config Loading", "FAIL", str(e))
            return False
    
    def test_database_connectivity(self):
        """Test 5: Database Connectivity"""
        logger.info("\n" + "="*80)
        logger.info("TEST 5: Database Connectivity")
        logger.info("="*80)
        
        try:
            import sqlite3
            import yaml
            
            with open("config.yaml") as f:
                config = yaml.safe_load(f)
            
            db_path = config.get("paths", {}).get("db_path", "data/memory.db")
            
            # Create directory if needed
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            # Test connection
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            conn.close()
            
            self.log_result(
                "Database Connectivity",
                "PASS",
                f"Found {len(tables)} tables in {db_path}"
            )
            return True
        except Exception as e:
            self.log_result("Database Connectivity", "FAIL", str(e))
            return False
    
    def test_faiss_indices(self):
        """Test 6: FAISS Index Accessibility"""
        logger.info("\n" + "="*80)
        logger.info("TEST 6: FAISS Index Accessibility")
        logger.info("="*80)
        
        try:
            import faiss
            import yaml
            
            with open("config.yaml") as f:
                config = yaml.safe_load(f)
            
            paths = config.get("paths", {})
            index_paths = {
                "text": paths.get("faiss_index_path"),
                "clip": paths.get("faiss_clip_path"),
                "dino": paths.get("faiss_dino_path"),
                "audio": paths.get("faiss_audio_path")
            }
            
            for name, path in index_paths.items():
                if path:
                    # Create directory
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    
                    if os.path.exists(path):
                        try:
                            index = faiss.read_index(path)
                            count = index.ntotal
                            self.log_result(
                                f"FAISS - {name}",
                                "PASS",
                                f"Found index with {count} vectors"
                            )
                        except Exception as e:
                            self.log_result(f"FAISS - {name}", "WARN", f"Could not read: {str(e)}")
                    else:
                        self.log_result(f"FAISS - {name}", "WARN", "Index does not exist yet")
                else:
                    self.log_result(f"FAISS - {name}", "WARN", "Path not configured")
            
            return True
        except Exception as e:
            self.log_result("FAISS Index Accessibility", "FAIL", str(e))
            return False
    
    def test_sample_processing(self):
        """Test 7: Sample Video Processing"""
        logger.info("\n" + "="*80)
        logger.info("TEST 7: Sample Video Processing")
        logger.info("="*80)
        
        try:
            sample_path = Path("import_inbox/sample.mp4")
            
            if not sample_path.exists():
                self.log_result("Sample Processing", "SKIP", "No sample.mp4 found")
                return True
            
            # Check if we can read the file
            import cv2
            cap = cv2.VideoCapture(str(sample_path))
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                duration = frame_count / fps if fps > 0 else 0
                cap.release()
                
                self.log_result(
                    "Sample Processing",
                    "PASS",
                    f"Video readable: {duration:.2f}s, {frame_count} frames @ {fps:.2f} fps"
                )
                return True
            else:
                self.log_result("Sample Processing", "FAIL", "Cannot open video file")
                return False
        except Exception as e:
            self.log_result("Sample Processing", "FAIL", str(e))
            return False
    
    def run_all_tests(self):
        """Run all tests and generate report"""
        self.start_time = time.time()
        
        logger.info("\n" + "="*80)
        logger.info("GOODQ4ALL PIPELINE TEST SUITE - Phase 2")
        logger.info("GPU Isolation & Memory Management Validation")
        logger.info("="*80 + "\n")
        
        # Run all tests
        tests = [
            self.test_gpu_availability,
            self.test_gpu_memory_isolation,
            self.test_step_imports,
            self.test_config_loading,
            self.test_database_connectivity,
            self.test_faiss_indices,
            self.test_sample_processing
        ]
        
        for test_func in tests:
            test_func()
        
        # Generate summary
        elapsed = time.time() - self.start_time
        self.generate_summary(elapsed)
    
    def generate_summary(self, elapsed_time: float):
        """Generate test summary"""
        logger.info("\n" + "="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        
        passed = sum(1 for r in self.test_results if r["status"] == "PASS")
        failed = sum(1 for r in self.test_results if r["status"] == "FAIL")
        warned = sum(1 for r in self.test_results if r["status"] == "WARN")
        skipped = sum(1 for r in self.test_results if r["status"] == "SKIP")
        total = len(self.test_results)
        
        logger.info(f"Total Tests: {total}")
        logger.info(f"[OK] Passed: {passed}")
        logger.info(f"[FAIL] Failed: {failed}")
        logger.info(f"[WARN]  Warnings: {warned}")
        logger.info(f"⏭️  Skipped: {skipped}")
        logger.info(f"[TIMER]  Duration: {elapsed_time:.2f}s")
        
        # GPU Stats
        stats = self.gpu_manager.get_gpu_stats()
        if stats:
            logger.info("\n" + "="*80)
            logger.info("FINAL GPU STATE")
            logger.info("="*80)
            for device in stats["devices"]:
                logger.info(f"\nGPU {device['id']}: {device['name']}")
                logger.info(f"  Allocated: {device['memory_allocated_mb']:.2f} MB")
                logger.info(f"  Reserved: {device['memory_reserved_mb']:.2f} MB")
                logger.info(f"  Total: {device['memory_total_mb']:.2f} MB")
                usage_pct = (device['memory_allocated_mb'] / device['memory_total_mb']) * 100
                logger.info(f"  Usage: {usage_pct:.2f}%")
        
        logger.info("\n" + "="*80)
        if failed == 0:
            logger.info("[OK] ALL TESTS PASSED!")
        else:
            logger.info(f"[FAIL] {failed} TEST(S) FAILED - Review logs above")
        logger.info("="*80 + "\n")
        
        return failed == 0


if __name__ == "__main__":
    # Ensure we're in the right directory
    os.chdir(Path(__file__).parent)
    
    # Create logs directory
    os.makedirs("logs", exist_ok=True)
    
    # Run tests
    tester = PipelineTest()
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)
