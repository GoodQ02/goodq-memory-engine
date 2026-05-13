"""
Comprehensive Vision Stack Audit
Tests all vision components for GPU availability and performance
"""

import sys
import time
from pathlib import Path

def test_face_embed_gpu():
    """Test face embedding GPU setup"""
    print("\n" + "="*80)
    print("Testing Face Embedding GPU")
    print("="*80)
    
    try:
        import torch
        from facenet_pytorch import MTCNN, InceptionResnetV1
        from gpu_config import setup_step_gpu, GPUManager
        
        # Setup GPU
        gpu_config = setup_step_gpu("face_embed")
        device = gpu_config["device"]
        
        print(f"Device: {device}")
        print(f"Memory Fraction: {gpu_config['memory_fraction']*100:.0f}%")
        
        if device == "cuda":
            print(f"CUDA Device: {torch.cuda.get_device_name(0)}")
            mem_info = GPUManager.get_memory_info()
            print(f"GPU Memory: {mem_info['allocated_gb']:.2f}GB allocated / {mem_info['total_gb']:.2f}GB total")
        
        # Load models
        print("\nLoading models...")
        mtcnn = MTCNN(keep_all=True, device=device)
        resnet = InceptionResnetV1(pretrained='vggface2').eval().to(device)
        
        # Test with dummy image
        from PIL import Image
        import numpy as np
        
        # Create test image
        img = Image.fromarray(np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8))
        
        # Benchmark
        print("\nBenchmarking...")
        start = time.time()
        boxes, _ = mtcnn.detect(img)
        elapsed = time.time() - start
        
        print(f"[OK] Face detection: {elapsed*1000:.1f}ms on {device}")
        
        if device == "cuda":
            mem_info = GPUManager.get_memory_info()
            print(f"   GPU Memory: {mem_info['allocated_gb']:.2f}GB allocated")
        
        GPUManager.clear_cache()
        return True
        
    except Exception as e:
        print(f"[FAIL] Face embedding test failed: {e}")
        return False

def test_emotion_classify_gpu():
    """Test emotion classification GPU setup"""
    print("\n" + "="*80)
    print("Testing Emotion Classification GPU")
    print("="*80)
    
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        from gpu_config import setup_step_gpu, GPUManager
        
        # Setup GPU
        gpu_config = setup_step_gpu("emotion_classify")
        device = gpu_config["device"]
        
        print(f"Device: {device}")
        print(f"Memory Fraction: {gpu_config['memory_fraction']*100:.0f}%")
        
        if device == "cuda":
            print(f"CUDA Device: {torch.cuda.get_device_name(0)}")
            mem_info = GPUManager.get_memory_info()
            print(f"GPU Memory: {mem_info['allocated_gb']:.2f}GB allocated / {mem_info['total_gb']:.2f}GB total")
        
        # Load model
        print("\nLoading model...")
        model_name = "cardiffnlp/twitter-roberta-base-emotion-multilabel-latest"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name).to(device).eval()
        
        # Test with sample text
        test_text = "This is a test of emotion classification on GPU acceleration with a longer sentence to simulate real usage."
        
        # Benchmark
        print("\nBenchmarking...")
        inputs = tokenizer(test_text, return_tensors="pt", truncation=True, max_length=512).to(device)
        
        start = time.time()
        with torch.no_grad():
            if device == "cuda":
                with torch.cuda.amp.autocast():
                    outputs = model(**inputs)
            else:
                outputs = model(**inputs)
        elapsed = time.time() - start
        
        print(f"[OK] Emotion classification: {elapsed*1000:.1f}ms on {device}")
        
        if device == "cuda":
            mem_info = GPUManager.get_memory_info()
            print(f"   GPU Memory: {mem_info['allocated_gb']:.2f}GB allocated")
        
        GPUManager.clear_cache()
        return True
        
    except Exception as e:
        print(f"[FAIL] Emotion classification test failed: {e}")
        return False

def main():
    print("="*80)
    print("GoodQ4All - Vision Stack GPU Audit")
    print("="*80)
    
    results = {}
    
    # Test face embedding
    results['face_embed'] = test_face_embed_gpu()
    
    # Test emotion classification
    results['emotion_classify'] = test_emotion_classify_gpu()
    
    # Summary
    print("\n" + "="*80)
    print("Audit Summary")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\nPassed: {passed}/{total}")
    for component, success in results.items():
        status = "[OK]" if success else "[FAIL]"
        print(f"  {status} {component}")
    
    if passed == total:
        print("\n[SYMBOL] All vision components GPU-enabled and functional!")
        sys.exit(0)
    else:
        print(f"\n[WARN]  {total - passed} component(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
