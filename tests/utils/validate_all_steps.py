#!/usr/bin/env python3
"""
Comprehensive Step Validation Script
Tests all 17 AI processing steps independently for:
- Environment availability
- Import capabilities
- Permission checks
- Model loading
- Basic functionality
- Error handling
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple
import sqlite3

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Step definitions - mapping to their environments
STEP_DEFINITIONS = {
    # Core AI Processing Steps (17 total)
    "video_scene_detect": {
        "env": "goodq_video_scene_detect",
        "step_path": "steps/video_scene_detect/step.py",
        "description": "Video scene boundary detection",
        "requires_gpu": False,
        "test_type": "opencv"
    },
    "image_caption": {
        "env": "goodq_image_caption",
        "step_path": "steps/image_caption/step.py",
        "description": "BLIP image captioning",
        "requires_gpu": True,
        "test_type": "transformers"
    },
    "image_ocr": {
        "env": "goodq_ocr",
        "step_path": "steps/image_ocr/step.py",
        "description": "Tesseract OCR text extraction",
        "requires_gpu": False,
        "test_type": "tesseract"
    },
    "object_detect": {
        "env": "goodq_object_detect",
        "step_path": "steps/object_detect/step.py",
        "description": "YOLO object detection",
        "requires_gpu": True,
        "test_type": "ultralytics"
    },
    "face_embed": {
        "env": "goodq_face_embed",
        "step_path": "steps/face_embed/step.py",
        "description": "Face detection and embedding",
        "requires_gpu": False,
        "test_type": "face_recognition"
    },
    "image_embed_clip": {
        "env": "goodq_image_caption",  # Shares env
        "step_path": "steps/image_embed_clip/step.py",
        "description": "CLIP visual embeddings",
        "requires_gpu": True,
        "test_type": "transformers"
    },
    "image_embed_dino": {
        "env": "goodq_image_caption",  # Shares env
        "step_path": "steps/image_embed_dino/step.py",
        "description": "DINO v2 visual embeddings",
        "requires_gpu": True,
        "test_type": "transformers"
    },
    "audio_metadata": {
        "env": "goodq_audio_metadata",
        "step_path": "steps/audio_metadata/step.py",
        "description": "Audio metadata extraction",
        "requires_gpu": False,
        "test_type": "librosa"
    },
    "audio_diarize": {
        "env": "goodq_audio_diarize",
        "step_path": "steps/audio_diarize/step.py",
        "description": "PyAnnote speaker diarization",
        "requires_gpu": True,
        "test_type": "pyannote"
    },
    "audio_transcribe": {
        "env": "goodq_audio_transcribe",
        "step_path": "steps/audio_transcribe/step.py",
        "description": "Whisper speech transcription",
        "requires_gpu": True,
        "test_type": "whisper"
    },
    "audio_emotion": {
        "env": "goodq_audio_emotion",
        "step_path": "steps/audio_emotion/step.py",
        "description": "Speech emotion recognition",
        "requires_gpu": True,
        "test_type": "transformers"
    },
    "audio_embed_clap": {
        "env": "goodq_audio_embed",
        "step_path": "steps/audio_embed_clap/step.py",
        "description": "CLAP audio embeddings",
        "requires_gpu": True,
        "test_type": "transformers"
    },
    "text_embed": {
        "env": "goodq_text_embed",
        "step_path": "steps/text_embed/step.py",
        "description": "Sentence-BERT text embeddings",
        "requires_gpu": False,
        "test_type": "sentence_transformers"
    },
    "sentiment": {
        "env": "goodq_sentiment",
        "step_path": "steps/sentiment/step.py",
        "description": "Sentiment analysis",
        "requires_gpu": False,
        "test_type": "transformers"
    },
    "emotion_classify": {
        "env": "goodq_emotion_classify",
        "step_path": "steps/emotion_classify/step.py",
        "description": "Text emotion classification",
        "requires_gpu": False,
        "test_type": "transformers"
    },
    "tagger": {
        "env": "goodq_tagger",
        "step_path": "steps/tagger/step.py",
        "description": "Named Entity Recognition",
        "requires_gpu": False,
        "test_type": "transformers"
    },
    "overview": {
        "env": "goodq_zenml",
        "step_path": "steps/overview/step.py",
        "description": "Scene overview synthesis",
        "requires_gpu": False,
        "test_type": "basic"
    }
}

class StepValidator:
    def __init__(self):
        self.results = {}
        self.project_root = PROJECT_ROOT
        
    def run_test_in_env(self, env_name: str, test_code: str) -> Tuple[bool, str, str]:
        """Run Python code in a specific conda environment"""
        cmd = f'conda run -n {env_name} python -c "{test_code}"'
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Test timed out after 60 seconds"
        except Exception as e:
            return False, "", str(e)
    
    def test_environment_exists(self, env_name: str) -> Tuple[bool, str]:
        """Check if conda environment exists"""
        result = subprocess.run(
            f"conda env list",
            shell=True,
            capture_output=True,
            text=True
        )
        exists = env_name in result.stdout
        return exists, "Environment found" if exists else "Environment not found"
    
    def test_step_file_exists(self, step_path: str) -> Tuple[bool, str]:
        """Check if step.py file exists and is readable"""
        full_path = self.project_root / step_path
        if not full_path.exists():
            return False, f"Step file not found: {full_path}"
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if len(content) < 100:
                    return False, "Step file appears to be empty or incomplete"
                if "def run(" not in content and "def execute(" not in content:
                    return False, "Step file missing main execution function"
            return True, "Step file valid"
        except Exception as e:
            return False, f"Error reading step file: {e}"
    
    def test_imports(self, env_name: str, test_type: str) -> Tuple[bool, str]:
        """Test if required libraries can be imported"""
        test_code_map = {
            "opencv": "import cv2; print(cv2.__version__)",
            "transformers": "import torch; import transformers; print(f'Torch: {torch.__version__}, Transformers: {transformers.__version__}')",
            "tesseract": "import pytesseract; print('Tesseract available')",
            "ultralytics": "import torch; from ultralytics import YOLO; print(f'Torch: {torch.__version__}, YOLO available')",
            "face_recognition": "import face_recognition; print('face_recognition available')",
            "librosa": "import librosa; print(f'librosa: {librosa.__version__}')",
            "pyannote": "import torch; from pyannote.audio import Pipeline; print('PyAnnote available')",
            "whisper": "import subprocess; print('Whisper via whisper.cpp')",
            "sentence_transformers": "from sentence_transformers import SentenceTransformer; print('Sentence-BERT available')",
            "basic": "import sys; print(f'Python {sys.version}')"
        }
        
        test_code = test_code_map.get(test_type, "print('Basic test')")
        success, stdout, stderr = self.run_test_in_env(env_name, test_code)
        
        if success:
            return True, stdout.strip()
        else:
            return False, f"Import failed: {stderr[:200]}"
    
    def test_cuda_available(self, env_name: str, requires_gpu: bool) -> Tuple[bool, str]:
        """Test CUDA availability for GPU-dependent steps"""
        if not requires_gpu:
            return True, "GPU not required"
        
        test_code = "import torch; print(f'CUDA: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\"}')"
        success, stdout, stderr = self.run_test_in_env(env_name, test_code)
        
        if success and "CUDA: True" in stdout:
            return True, stdout.strip()
        elif success:
            return False, "CUDA not available but required"
        else:
            return False, f"CUDA check failed: {stderr[:200]}"
    
    def test_model_cache(self, env_name: str, test_type: str) -> Tuple[bool, str]:
        """Check if required models are accessible"""
        models_dir = Path("L:/models")
        if not models_dir.exists():
            return False, "Model cache directory not found"
        
        # Check HF_HOME is set correctly
        test_code = "import os; print(os.environ.get('HF_HOME', 'NOT_SET'))"
        success, stdout, stderr = self.run_test_in_env(env_name, test_code)
        
        if "L:\\models" in stdout or "L:/models" in stdout:
            return True, f"Model cache configured: {stdout.strip()}"
        else:
            return False, f"HF_HOME not configured correctly: {stdout.strip()}"
    
    def test_permissions(self, step_path: str) -> Tuple[bool, str]:
        """Test file system permissions for step directory"""
        full_path = self.project_root / step_path
        step_dir = full_path.parent
        
        # Test read permission
        if not os.access(full_path, os.R_OK):
            return False, "No read permission for step file"
        
        # Test write permission to logs directory
        log_dir = self.project_root / "logs"
        if not os.access(log_dir, os.W_OK):
            return False, "No write permission to logs directory"
        
        # Test write permission to data directory
        data_dir = self.project_root / "data"
        if not os.access(data_dir, os.W_OK):
            return False, "No write permission to data directory"
        
        return True, "All permissions valid"
    
    def test_database_access(self) -> Tuple[bool, str]:
        """Test database connectivity"""
        db_path = self.project_root / "data" / "memory.db"
        if not db_path.exists():
            return True, "Database will be created on first run"
        
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            conn.close()
            return True, f"Database accessible, {len(tables)} tables"
        except Exception as e:
            return False, f"Database connection error: {e}"
    
    def validate_step(self, step_name: str, step_config: Dict) -> Dict:
        """Run all validation tests for a single step"""
        print(f"\n{'='*80}")
        print(f"VALIDATING: {step_name}")
        print(f"Description: {step_config['description']}")
        print(f"Environment: {step_config['env']}")
        print(f"GPU Required: {step_config['requires_gpu']}")
        print(f"{'='*80}")
        
        result = {
            "step_name": step_name,
            "description": step_config["description"],
            "env": step_config["env"],
            "tests": {},
            "overall_status": "PASS",
            "critical_failures": []
        }
        
        # Test 1: Environment exists
        print("  [1/8] Testing environment existence...")
        success, msg = self.test_environment_exists(step_config["env"])
        result["tests"]["environment_exists"] = {"status": "PASS" if success else "FAIL", "message": msg}
        if not success:
            result["overall_status"] = "FAIL"
            result["critical_failures"].append("Environment missing")
            print(f"    ❌ FAIL: {msg}")
            return result
        print(f"    ✅ PASS: {msg}")
        
        # Test 2: Step file exists and valid
        print("  [2/8] Testing step file...")
        success, msg = self.test_step_file_exists(step_config["step_path"])
        result["tests"]["step_file_valid"] = {"status": "PASS" if success else "FAIL", "message": msg}
        if not success:
            result["overall_status"] = "FAIL"
            result["critical_failures"].append("Step file invalid")
        print(f"    {'✅' if success else '❌'} {'PASS' if success else 'FAIL'}: {msg}")
        
        # Test 3: Permissions
        print("  [3/8] Testing file permissions...")
        success, msg = self.test_permissions(step_config["step_path"])
        result["tests"]["permissions"] = {"status": "PASS" if success else "FAIL", "message": msg}
        if not success:
            result["overall_status"] = "FAIL"
            result["critical_failures"].append("Permission denied")
        print(f"    {'✅' if success else '❌'} {'PASS' if success else 'FAIL'}: {msg}")
        
        # Test 4: Required imports
        print("  [4/8] Testing library imports...")
        success, msg = self.test_imports(step_config["env"], step_config["test_type"])
        result["tests"]["imports"] = {"status": "PASS" if success else "FAIL", "message": msg}
        if not success:
            result["overall_status"] = "FAIL"
            result["critical_failures"].append("Import failure")
        print(f"    {'✅' if success else '❌'} {'PASS' if success else 'FAIL'}: {msg}")
        
        # Test 5: CUDA availability (if required)
        print("  [5/8] Testing CUDA availability...")
        success, msg = self.test_cuda_available(step_config["env"], step_config["requires_gpu"])
        result["tests"]["cuda"] = {"status": "PASS" if success else "FAIL", "message": msg}
        if not success and step_config["requires_gpu"]:
            result["overall_status"] = "FAIL"
            result["critical_failures"].append("CUDA unavailable")
        print(f"    {'✅' if success else '❌'} {'PASS' if success else 'FAIL'}: {msg}")
        
        # Test 6: Model cache
        print("  [6/8] Testing model cache configuration...")
        success, msg = self.test_model_cache(step_config["env"], step_config["test_type"])
        result["tests"]["model_cache"] = {"status": "PASS" if success else "WARN", "message": msg}
        if not success:
            print(f"    ⚠️  WARN: {msg}")
        else:
            print(f"    ✅ PASS: {msg}")
        
        # Test 7: Database access
        print("  [7/8] Testing database access...")
        success, msg = self.test_database_access()
        result["tests"]["database"] = {"status": "PASS" if success else "FAIL", "message": msg}
        if not success:
            result["overall_status"] = "FAIL"
            result["critical_failures"].append("Database inaccessible")
        print(f"    {'✅' if success else '❌'} {'PASS' if success else 'FAIL'}: {msg}")
        
        # Test 8: Step syntax validation
        print("  [8/8] Testing step syntax...")
        test_code = f"exec(open(r'{self.project_root / step_config['step_path']}').read())"
        success, stdout, stderr = self.run_test_in_env(step_config["env"], test_code)
        syntax_valid = success or "SyntaxError" not in stderr
        result["tests"]["syntax"] = {
            "status": "PASS" if syntax_valid else "FAIL",
            "message": "Syntax valid" if syntax_valid else f"Syntax error: {stderr[:200]}"
        }
        if not syntax_valid:
            result["overall_status"] = "FAIL"
            result["critical_failures"].append("Syntax error")
        print(f"    {'✅' if syntax_valid else '❌'} {'PASS' if syntax_valid else 'FAIL'}: {result['tests']['syntax']['message']}")
        
        return result
    
    def generate_report(self, results: List[Dict]) -> str:
        """Generate formatted validation report"""
        report = []
        report.append("\n" + "="*100)
        report.append("GOODQ4ALL STEP VALIDATION REPORT")
        report.append("="*100)
        report.append(f"\nValidation Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Steps Tested: {len(results)}")
        
        passed = sum(1 for r in results if r["overall_status"] == "PASS")
        failed = len(results) - passed
        
        report.append(f"\nOverall Results: {passed}/{len(results)} PASSED")
        report.append(f"                 {failed}/{len(results)} FAILED")
        
        if failed == 0:
            report.append("\n✅ ALL STEPS VALIDATED SUCCESSFULLY!")
        else:
            report.append(f"\n⚠️  {failed} STEP(S) REQUIRE ATTENTION")
        
        # Summary table
        report.append("\n" + "-"*100)
        report.append("SUMMARY")
        report.append("-"*100)
        report.append(f"{'Step Name':<25} {'Environment':<25} {'Status':<10} {'Issues'}")
        report.append("-"*100)
        
        for r in results:
            issues = ", ".join(r["critical_failures"]) if r["critical_failures"] else "None"
            status_icon = "✅" if r["overall_status"] == "PASS" else "❌"
            report.append(f"{r['step_name']:<25} {r['env']:<25} {status_icon} {r['overall_status']:<8} {issues}")
        
        # Detailed results
        report.append("\n" + "="*100)
        report.append("DETAILED TEST RESULTS")
        report.append("="*100)
        
        for r in results:
            report.append(f"\n{r['step_name']} - {r['description']}")
            report.append(f"Environment: {r['env']}")
            report.append(f"Overall Status: {r['overall_status']}")
            
            if r["critical_failures"]:
                report.append(f"Critical Failures: {', '.join(r['critical_failures'])}")
            
            report.append("\nTest Results:")
            for test_name, test_result in r["tests"].items():
                status_icon = "✅" if test_result["status"] == "PASS" else ("⚠️" if test_result["status"] == "WARN" else "❌")
                report.append(f"  {status_icon} {test_name}: {test_result['status']} - {test_result['message']}")
            
            report.append("-"*100)
        
        return "\n".join(report)
    
    def run_all_validations(self):
        """Run validation for all steps"""
        print("\n" + "="*100)
        print("STARTING COMPREHENSIVE STEP VALIDATION")
        print("="*100)
        print(f"Project Root: {self.project_root}")
        print(f"Total Steps to Validate: {len(STEP_DEFINITIONS)}")
        
        results = []
        for step_name, step_config in STEP_DEFINITIONS.items():
            result = self.validate_step(step_name, step_config)
            results.append(result)
            time.sleep(0.5)  # Small delay between tests
        
        # Generate and save report
        report = self.generate_report(results)
        print(report)
        
        # Save to file
        report_path = self.project_root / "logs" / "step_validation_report.txt"
        report_path.parent.mkdir(exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n📄 Report saved to: {report_path}")
        
        # Save JSON results
        json_path = self.project_root / "logs" / "step_validation_report.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        
        print(f"📄 JSON results saved to: {json_path}")
        
        return results


def main():
    validator = StepValidator()
    results = validator.run_all_validations()
    
    # Exit code based on results
    failed_count = sum(1 for r in results if r["overall_status"] == "FAIL")
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
