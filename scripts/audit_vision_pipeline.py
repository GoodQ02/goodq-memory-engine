"""
GoodQ4All - Vision Pipeline Functionality Audit
Comprehensive test of all vision components
"""

import subprocess
import sys
import os
import json
from pathlib import Path
from datetime import datetime

def run_cmd(cmd, timeout=120):
    """Run command and return output"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def test_face_detection():
    """Test face detection pipeline"""
    print("\n" + "="*80)
    print("Testing Face Detection")
    print("="*80)
    
    test_script = """
import sys
import os
sys.path.insert(0, 'L:/goodq4all')

# Mock item and config
item = {'source_path': 'L:/goodq4all/test_data/sample_frame.jpg'}
cfg = {}

from steps.face_embed.step import face_embed
result = face_embed(item, cfg)

print(f"Status: {result.get('faces_meta', {}).get('status', 'unknown')}")
print(f"Engine: {result.get('faces_meta', {}).get('engine', 'unknown')}")
print(f"Faces detected: {len(result.get('faces', []))}")

if result.get('faces'):
    face = result['faces'][0]
    print(f"  Bbox: {face['bbox']}")
    print(f"  Embedding dim: {len(face['encoding'])}")
"""
    
    success, stdout, stderr = run_cmd(f'conda run -n goodq_face_embed python -c "{test_script}"')
    
    if success and "Status: ok" in stdout:
        print("✅ Face detection working")
        print(stdout)
        return True
    else:
        print("❌ Face detection failed")
        print("STDOUT:", stdout)
        print("STDERR:", stderr)
        return False

def test_emotion_classification():
    """Test emotion classification"""
    print("\n" + "="*80)
    print("Testing Emotion Classification")
    print("="*80)
    
    test_script = """
import sys
sys.path.insert(0, 'L:/goodq4all')

item = {'transcript': 'I am so happy and excited about this amazing project!'}
cfg = {'config': {'analysis': {}}}

from steps.emotion_classify.step import emotion_classify
result = emotion_classify(item, cfg)

print(f"Status: {result.get('emotion_meta', {}).get('status', 'ok')}")
print(f"Engine: {result.get('emotion_meta', {}).get('engine', 'unknown')}")

if result.get('emotions'):
    print(f"Top emotions detected: {len(result['emotions'])}")
    for emo in result['emotions'][:3]:
        print(f"  {emo['label']}: {emo['score']:.3f}")
"""
    
    success, stdout, stderr = run_cmd(f'conda run -n goodq_emotion_classify python -c "{test_script}"')
    
    if success and "emotions detected" in stdout.lower():
        print("✅ Emotion classification working")
        print(stdout)
        return True
    else:
        print("❌ Emotion classification failed")
        print("STDOUT:", stdout)
        print("STDERR:", stderr)
        return False

def test_object_detection():
    """Test object detection"""
    print("\n" + "="*80)
    print("Testing Object Detection")
    print("="*80)
    
    test_script = """
import sys
sys.path.insert(0, 'L:/goodq4all')

item = {'source_path': 'L:/goodq4all/test_data/sample_frame.jpg'}
cfg = {'models': {'yolo_model_path': 'yolov8n.pt'}}

from steps.object_detect.step import object_detect
result = object_detect(item, cfg)

print(f"Status: {result.get('detect_meta', {}).get('status', 'ok')}")
print(f"Objects detected: {len(result.get('objects', []))}")

if result.get('objects'):
    for obj in result['objects'][:5]:
        print(f"  {obj['label']}: {obj['score']:.3f} at {obj['bbox']}")
"""
    
    success, stdout, stderr = run_cmd(f'conda run -n goodq_object_detect python -c "{test_script}"')
    
    if success:
        print("✅ Object detection working")
        print(stdout)
        return True
    else:
        print("❌ Object detection failed")
        print("STDOUT:", stdout)
        print("STDERR:", stderr)
        return False

def test_image_embeddings():
    """Test CLIP and DINO embeddings"""
    print("\n" + "="*80)
    print("Testing Image Embeddings (CLIP + DINO)")
    print("="*80)
    
    # Test CLIP
    print("\n[1/2] Testing CLIP...")
    clip_script = """
import sys
import os
sys.path.insert(0, 'L:/goodq4all')

item = {
    'source_path': 'L:/goodq4all/test_data/sample_frame.jpg',
    'scene_id': 'test_001'
}
cfg = {
    'paths': {
        'faiss_clip_path': 'L:/goodq4all/output/faiss_indices/clip_test.index',
        'clip_id_map_db': 'L:/goodq4all/output/faiss_indices/clip_id_map_test.sqlite'
    }
}

from steps.image_embed_clip.step import image_embed_clip
result = image_embed_clip(item, cfg)

print(f"Status: {result.get('clip_meta', {}).get('status', 'unknown')}")
if result.get('clip_meta', {}).get('faiss_id') is not None:
    print(f"FAISS ID: {result['clip_meta']['faiss_id']}")
"""
    
    success, stdout, stderr = run_cmd(f'conda run -n goodq_text_embed python -c "{clip_script}"')
    
    clip_ok = success and "Status: ok" in stdout
    if clip_ok:
        print("  ✅ CLIP embedding working")
        print("  " + stdout.replace("\n", "\n  "))
    else:
        print("  ❌ CLIP embedding failed")
        print("  STDOUT:", stdout)
        print("  STDERR:", stderr)
    
    # Test DINO
    print("\n[2/2] Testing DINO...")
    dino_script = """
import sys
sys.path.insert(0, 'L:/goodq4all')

item = {
    'source_path': 'L:/goodq4all/test_data/sample_frame.jpg',
    'scene_id': 'test_001'
}
cfg = {
    'paths': {
        'faiss_dino_path': 'L:/goodq4all/output/faiss_indices/dino_test.index',
        'dino_id_map_db': 'L:/goodq4all/output/faiss_indices/dino_id_map_test.sqlite'
    }
}

from steps.image_embed_dino.step import image_embed_dino
result = image_embed_dino(item, cfg)

print(f"Status: {result.get('dino_meta', {}).get('status', 'unknown')}")
if result.get('dino_meta', {}).get('faiss_id') is not None:
    print(f"FAISS ID: {result['dino_meta']['faiss_id']}")
"""
    
    success, stdout, stderr = run_cmd(f'conda run -n goodq_text_embed python -c "{dino_script}"')
    
    dino_ok = success and "Status: ok" in stdout
    if dino_ok:
        print("  ✅ DINO embedding working")
        print("  " + stdout.replace("\n", "\n  "))
    else:
        print("  ❌ DINO embedding failed")
        print("  STDOUT:", stdout)
        print("  STDERR:", stderr)
    
    return clip_ok and dino_ok

def test_image_captioning():
    """Test image captioning"""
    print("\n" + "="*80)
    print("Testing Image Captioning")
    print("="*80)
    
    test_script = """
import sys
sys.path.insert(0, 'L:/goodq4all')

item = {'source_path': 'L:/goodq4all/test_data/sample_frame.jpg'}
cfg = {}

from steps.image_caption.step import image_caption
result = image_caption(item, cfg)

print(f"Status: {result.get('caption_meta', {}).get('status', 'ok')}")
print(f"Engine: {result.get('caption_meta', {}).get('engine', 'unknown')}")

if result.get('caption'):
    print(f"Caption: {result['caption']}")
"""
    
    success, stdout, stderr = run_cmd(f'conda run -n goodq_text_embed python -c "{test_script}"')
    
    if success and result.get('caption'):
        print("✅ Image captioning working")
        print(stdout)
        return True
    else:
        print("❌ Image captioning failed")
        print("STDOUT:", stdout)
        print("STDERR:", stderr)
        return False

def test_gpu_utilization():
    """Test GPU is actually being used"""
    print("\n" + "="*80)
    print("Testing GPU Utilization")
    print("="*80)
    
    gpu_test = """
import torch
print(f"CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA Version: {torch.version.cuda}")
    print(f"Device Count: {torch.cuda.device_count()}")
    print(f"Current Device: {torch.cuda.current_device()}")
    print(f"Device Name: {torch.cuda.get_device_name(0)}")
    
    # Allocate tensor on GPU to verify
    x = torch.randn(1000, 1000).cuda()
    y = torch.matmul(x, x)
    
    print(f"GPU Memory Allocated: {torch.cuda.memory_allocated()/1024**2:.1f} MB")
    print(f"GPU Memory Cached: {torch.cuda.memory_reserved()/1024**2:.1f} MB")
    print("✅ GPU tensor operations working")
else:
    print("❌ CUDA not available")
"""
    
    # Test in each vision environment
    envs = ["goodq_face_embed", "goodq_emotion_classify", "goodq_object_detect", "goodq_text_embed"]
    results = {}
    
    for env in envs:
        print(f"\n  Testing {env}...")
        success, stdout, stderr = run_cmd(f'conda run -n {env} python -c "{gpu_test}"')
        
        cuda_available = "CUDA Available: True" in stdout
        if cuda_available:
            print(f"    ✅ GPU active")
            # Extract memory info
            for line in stdout.split('\n'):
                if 'Device Name:' in line or 'Memory' in line:
                    print(f"    {line.strip()}")
        else:
            print(f"    ❌ GPU not available")
            if stderr:
                print(f"    Error: {stderr[:100]}")
        
        results[env] = cuda_available
    
    all_ok = all(results.values())
    if all_ok:
        print("\n✅ All environments have GPU access")
    else:
        failed = [env for env, ok in results.items() if not ok]
        print(f"\n❌ Environments without GPU: {', '.join(failed)}")
    
    return all_ok

def check_model_caching():
    """Check if models are properly cached"""
    print("\n" + "="*80)
    print("Checking Model Caching")
    print("="*80)
    
    model_paths = {
        "HF_HOME": os.environ.get("HF_HOME", "Not set"),
        "TORCH_HOME": os.environ.get("TORCH_HOME", "Not set"),
        "TRANSFORMERS_CACHE": os.environ.get("TRANSFORMERS_CACHE", "Not set")
    }
    
    print("\nEnvironment variables:")
    for var, path in model_paths.items():
        print(f"  {var}: {path}")
        if path != "Not set" and Path(path).exists():
            size_mb = sum(f.stat().st_size for f in Path(path).rglob('*') if f.is_file()) / 1024**2
            print(f"    Size: {size_mb:.1f} MB")
    
    # Check for cached models
    cache_dir = Path("L:/models")
    if cache_dir.exists():
        print(f"\nModels cached in {cache_dir}:")
        
        # Check for specific models
        models_to_check = [
            "models--openai--clip-vit-base-patch16",
            "models--facebook--dinov2-base",
            "models--Salesforce--blip-image-captioning-base",
            "models--cardiffnlp--twitter-roberta-base-emotion-multilabel-latest"
        ]
        
        for model_dir in models_to_check:
            model_path = cache_dir / "transformers" / model_dir
            if model_path.exists():
                print(f"  ✅ {model_dir.replace('models--', '')}")
            else:
                print(f"  ❌ {model_dir.replace('models--', '')} (not cached)")
    
    return True

def generate_report(results):
    """Generate audit report"""
    print("\n" + "="*80)
    print("VISION PIPELINE AUDIT REPORT")
    print("="*80)
    print(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    total_tests = len(results)
    passed = sum(1 for ok in results.values() if ok)
    
    print(f"\nOverall: {passed}/{total_tests} tests passed ({passed/total_tests*100:.0f}%)")
    
    print("\nDetailed Results:")
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {test_name}")
    
    # Recommendations
    print("\n" + "="*80)
    print("Recommendations:")
    print("="*80)
    
    if results.get("GPU Utilization"):
        print("  ✅ GPU acceleration is working correctly")
    else:
        print("  ⚠️  Consider running run_vision_optimization.bat to enable GPU")
    
    if passed == total_tests:
        print("  ✅ All vision components are functional")
        print("  ℹ️  Ready for production ingestion")
    else:
        failed_tests = [name for name, ok in results.items() if not ok]
        print(f"  ⚠️  Failed tests need attention: {', '.join(failed_tests)}")
    
    # Save report
    report_path = Path("L:/goodq4all/output/vision_audit_report.txt")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, 'w') as f:
        f.write(f"Vision Pipeline Audit Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(f"Results: {passed}/{total_tests} passed\n\n")
        for test_name, result in results.items():
            f.write(f"{'PASS' if result else 'FAIL'}: {test_name}\n")
    
    print(f"\n📄 Report saved to: {report_path}")

def main():
    print("="*80)
    print("GoodQ4All - Vision Pipeline Functionality Audit")
    print("="*80)
    print("\nThis will test all vision processing components:")
    print("  • Face Detection")
    print("  • Emotion Classification")
    print("  • Object Detection")
    print("  • Image Embeddings (CLIP + DINO)")
    print("  • Image Captioning")
    print("  • GPU Utilization")
    print("\nEstimated time: 5-10 minutes...")
    
    # Check test data exists
    test_frame = Path("L:/goodq4all/test_data/sample_frame.jpg")
    if not test_frame.exists():
        print(f"\n⚠️  Test image not found at {test_frame}")
        print("Creating test data directory...")
        test_frame.parent.mkdir(parents=True, exist_ok=True)
        print("Please add a sample image to test_data/sample_frame.jpg")
        print("You can extract a frame from your videos for testing")
        input("\nPress ENTER once test image is ready...")
    
    input("\nPress ENTER to start audit or CTRL+C to cancel...")
    
    # Run tests
    results = {}
    
    results["GPU Utilization"] = test_gpu_utilization()
    results["Face Detection"] = test_face_detection()
    results["Emotion Classification"] = test_emotion_classification()
    results["Object Detection"] = test_object_detection()
    results["Image Embeddings"] = test_image_embeddings()
    results["Image Captioning"] = test_image_captioning()
    results["Model Caching"] = check_model_caching()
    
    # Generate report
    generate_report(results)
    
    input("\nPress ENTER to exit...")

if __name__ == "__main__":
    main()
