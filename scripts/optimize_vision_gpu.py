"""
GoodQ4All - Vision Stack GPU Optimization
Optimizes all vision-related steps for GPU acceleration
"""

import subprocess
import sys
import os
from pathlib import Path

# Vision environments and their GPU memory allocations
VISION_ENVS = {
    "goodq_face_embed": {
        "memory_fraction": 0.20,  # Increased from 0.15
        "packages": [
            "pytorch-cuda=11.8",
            "facenet-pytorch",
            "pillow",
            "torchvision"
        ],
        "description": "Face detection and embeddings (FaceNet + MTCNN)"
    },
    "goodq_emotion_classify": {
        "memory_fraction": 0.18,  # Increased from 0.15
        "packages": [
            "pytorch-cuda=11.8",
            "transformers",
            "accelerate"
        ],
        "description": "Emotion classification (RoBERTa)"
    },
    "goodq_object_detect": {
        "memory_fraction": 0.25,  # New allocation
        "packages": [
            "pytorch-cuda=11.8",
            "ultralytics",  # YOLOv8
            "opencv-python"
        ],
        "description": "Object detection and tracking (YOLO)"
    },
    "goodq_ocr": {
        "memory_fraction": 0.20,  # New allocation
        "packages": [
            "pytorch-cuda=11.8",
            "easyocr",
            "pillow"
        ],
        "description": "Optical character recognition"
    }
}

def run_cmd(cmd, shell=True):
    """Run command and return success status"""
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def optimize_environment(env_name, config):
    """Optimize a single environment for GPU"""
    print(f"\n{'='*80}")
    print(f"Optimizing: {env_name}")
    print(f"Description: {config['description']}")
    print(f"GPU Memory: {config['memory_fraction']*100:.0f}%")
    print(f"{'='*80}")
    
    # Check if environment exists
    success, stdout, stderr = run_cmd(f"conda env list")
    if env_name not in stdout:
        print(f"❌ Environment {env_name} not found. Skipping...")
        return False
    
    # Activate and upgrade PyTorch with CUDA
    print("\n[1/4] Installing PyTorch with CUDA support...")
    cmd = f'conda run -n {env_name} pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118 --upgrade --force-reinstall'
    success, stdout, stderr = run_cmd(cmd)
    if not success:
        print(f"❌ Failed to install PyTorch: {stderr}")
        return False
    print("✅ PyTorch with CUDA installed")
    
    # Install environment-specific packages
    print("\n[2/4] Installing vision-specific packages...")
    for package in config['packages']:
        if 'pytorch-cuda' in package:
            continue  # Already installed
        
        cmd = f'conda run -n {env_name} pip install {package} --upgrade'
        success, stdout, stderr = run_cmd(cmd)
        if success:
            print(f"  ✅ {package}")
        else:
            print(f"  ⚠️  {package} (may need manual install)")
    
    # Verify CUDA availability
    print("\n[3/4] Verifying CUDA support...")
    verify_script = """
import torch
print(f"CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA Version: {torch.version.cuda}")
    print(f"Device: {torch.cuda.get_device_name(0)}")
    print(f"Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
"""
    
    cmd = f'conda run -n {env_name} python -c "{verify_script}"'
    success, stdout, stderr = run_cmd(cmd)
    if success and "CUDA Available: True" in stdout:
        print("✅ CUDA verification passed")
        print(stdout)
    else:
        print("❌ CUDA not available")
        print(stderr)
        return False
    
    # Test model loading
    print("\n[4/4] Testing model loading...")
    if "face_embed" in env_name:
        test_script = """
import torch
from facenet_pytorch import MTCNN, InceptionResnetV1
device = 'cuda' if torch.cuda.is_available() else 'cpu'
mtcnn = MTCNN(device=device)
model = InceptionResnetV1(pretrained='vggface2').to(device).eval()
print(f"✅ FaceNet loaded on {device}")
"""
    elif "emotion" in env_name:
        test_script = """
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = AutoModelForSequenceClassification.from_pretrained('cardiffnlp/twitter-roberta-base-emotion-multilabel-latest').to(device)
print(f"✅ Emotion model loaded on {device}")
"""
    elif "object_detect" in env_name:
        test_script = """
import torch
from ultralytics import YOLO
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = YOLO('yolov8n.pt')
print(f"✅ YOLO loaded, device will be set at runtime")
"""
    elif "ocr" in env_name:
        test_script = """
import torch
import easyocr
reader = easyocr.Reader(['en'], gpu=torch.cuda.is_available())
print(f"✅ EasyOCR configured for GPU: {torch.cuda.is_available()}")
"""
    else:
        print("⚠️  No model test available for this environment")
        return True
    
    cmd = f'conda run -n {env_name} python -c "{test_script}"'
    success, stdout, stderr = run_cmd(cmd)
    if success:
        print(stdout)
        print(f"\n✅ {env_name} optimization complete!\n")
        return True
    else:
        print(f"❌ Model loading failed: {stderr}")
        return False

def update_gpu_config():
    """Update gpu_config.py with vision memory allocations"""
    print("\n" + "="*80)
    print("Updating GPU Configuration")
    print("="*80)
    
    config_path = Path("L:/goodq4all/gpu_config.py")
    if not config_path.exists():
        print("❌ gpu_config.py not found")
        return False
    
    # Read current config
    with open(config_path, 'r') as f:
        lines = f.readlines()
    
    # Update memory limits
    new_lines = []
    in_limits_section = False
    for line in lines:
        if "GPU_MEMORY_LIMITS = {" in line:
            in_limits_section = True
            new_lines.append(line)
            new_lines.append(f'    "goodq_audio_diarize": 0.25,  # Audio diarization (reduced for vision)\n')
            new_lines.append(f'    "goodq_audio_transcribe": 0.20,  # Whisper transcription\n')
            new_lines.append(f'    "goodq_emotion_classify": 0.18,  # Emotion classification\n')
            new_lines.append(f'    "goodq_face_embed": 0.20,  # Face embeddings\n')
            new_lines.append(f'    "goodq_object_detect": 0.25,  # Object detection (YOLO)\n')
            new_lines.append(f'    "goodq_ocr": 0.20,  # OCR\n')
            new_lines.append(f'    "goodq_text_embed": 0.15,  # Text embeddings\n')
        elif in_limits_section and "}" in line:
            in_limits_section = False
            new_lines.append(line)
        elif not in_limits_section:
            new_lines.append(line)
    
    # Write updated config
    with open(config_path, 'w') as f:
        f.writelines(new_lines)
    
    print("✅ GPU configuration updated")
    return True

def run_vision_benchmark():
    """Run a quick benchmark of vision steps"""
    print("\n" + "="*80)
    print("Vision Stack Benchmark")
    print("="*80)
    
    # Create test image if needed
    test_image_path = Path("L:/goodq4all/test_data/sample_frame.jpg")
    if not test_image_path.exists():
        print("⚠️  Test image not found, skipping benchmark")
        return
    
    benchmarks = []
    
    # Benchmark face detection
    print("\n[1/4] Benchmarking face detection...")
    face_script = f"""
import torch
import time
from facenet_pytorch import MTCNN
from PIL import Image

device = 'cuda' if torch.cuda.is_available() else 'cpu'
mtcnn = MTCNN(device=device)
img = Image.open(r'{test_image_path}')

start = time.time()
boxes, _ = mtcnn.detect(img)
elapsed = time.time() - start

print(f"Face Detection: {{elapsed*1000:.1f}}ms on {{device}}")
if torch.cuda.is_available():
    print(f"GPU Memory: {{torch.cuda.max_memory_allocated()/1024**2:.1f}} MB")
"""
    
    success, stdout, stderr = run_cmd(f'conda run -n goodq_face_embed python -c "{face_script}"')
    if success:
        print(stdout)
        benchmarks.append(("Face Detection", stdout))
    
    # Benchmark emotion classification  
    print("\n[2/4] Benchmarking emotion classification...")
    emotion_script = """
import torch
import time
from transformers import AutoTokenizer, AutoModelForSequenceClassification

device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = AutoModelForSequenceClassification.from_pretrained('cardiffnlp/twitter-roberta-base-emotion-multilabel-latest').to(device).eval()
tok = AutoTokenizer.from_pretrained('cardiffnlp/twitter-roberta-base-emotion-multilabel-latest')

text = "This is a test of emotion classification on GPU acceleration"
inputs = tok(text, return_tensors='pt').to(device)

start = time.time()
with torch.no_grad():
    outputs = model(**inputs)
elapsed = time.time() - start

print(f"Emotion Classification: {elapsed*1000:.1f}ms on {device}")
if torch.cuda.is_available():
    print(f"GPU Memory: {torch.cuda.max_memory_allocated()/1024**2:.1f} MB")
"""
    
    success, stdout, stderr = run_cmd(f'conda run -n goodq_emotion_classify python -c "{emotion_script}"')
    if success:
        print(stdout)
        benchmarks.append(("Emotion Classification", stdout))
    
    # Benchmark object detection
    print("\n[3/4] Benchmarking object detection...")
    yolo_script = f"""
import torch
import time
from ultralytics import YOLO

device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = YOLO('yolov8n.pt')

start = time.time()
results = model.predict(r'{test_image_path}', device=device, verbose=False)
elapsed = time.time() - start

print(f"Object Detection (YOLO): {{elapsed*1000:.1f}}ms on {{device}}")
if torch.cuda.is_available():
    print(f"GPU Memory: {{torch.cuda.max_memory_allocated()/1024**2:.1f}} MB")
"""
    
    success, stdout, stderr = run_cmd(f'conda run -n goodq_object_detect python -c "{yolo_script}"')
    if success:
        print(stdout)
        benchmarks.append(("Object Detection", stdout))
    
    print("\n" + "="*80)
    print("Benchmark Summary")
    print("="*80)
    for name, result in benchmarks:
        print(f"\n{name}:")
        print(result)

def main():
    print("="*80)
    print("GoodQ4All - Vision Stack GPU Optimization")
    print("="*80)
    print("\nThis will optimize all vision processing steps for GPU acceleration:")
    for env_name, config in VISION_ENVS.items():
        print(f"  • {env_name}: {config['description']}")
    
    print("\nThis may take 15-20 minutes...")
    input("\nPress ENTER to continue or CTRL+C to cancel...")
    
    # Update GPU config first
    update_gpu_config()
    
    # Optimize each environment
    results = {}
    for env_name, config in VISION_ENVS.items():
        results[env_name] = optimize_environment(env_name, config)
    
    # Print summary
    print("\n" + "="*80)
    print("Optimization Summary")
    print("="*80)
    
    successful = [env for env, success in results.items() if success]
    failed = [env for env, success in results.items() if not success]
    
    print(f"\nSuccessful: {len(successful)}/{len(VISION_ENVS)}")
    for env in successful:
        print(f"  ✅ {env}")
    
    if failed:
        print(f"\nFailed: {len(failed)}")
        for env in failed:
            print(f"  ❌ {env}")
    
    # Run benchmark if all successful
    if len(successful) == len(VISION_ENVS):
        print("\n🎉 All environments optimized successfully!")
        run_vision_benchmark()
    else:
        print(f"\n⚠️  Some environments failed. Check errors above.")
    
    input("\nPress ENTER to exit...")

if __name__ == "__main__":
    main()
