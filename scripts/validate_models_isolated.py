"""
Comprehensive model validation using isolated conda environments.
Each step is tested in its designated environment.
"""
import os
import sys
import subprocess
import json
from pathlib import Path


def run_in_conda_env(env_name, python_code):
    """Run Python code in a specific conda environment"""
    cmd = [
        "conda", "run", "-n", env_name, "--no-capture-output",
        "python", "-c", python_code
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr


def test_object_detection():
    """Test YOLO in goodq_object_detect env"""
    print("\n=== Testing Object Detection (YOLO) in goodq_object_detect env ===")
    code = """
import os
os.environ['HF_HOME'] = 'L:/models'
os.environ['TORCH_HOME'] = 'L:/models'

from ultralytics import YOLO
model = YOLO('L:/models/yolo/yolov8n.pt')
img = 'L:/goodq4all/logs/ingest_full/1987_1988/frames/scene_0000.jpg'
results = model.predict(source=img, verbose=False)
detections = []
for r in results:
    boxes = getattr(r, 'boxes', None)
    if boxes:
        for b in boxes:
            detections.append(True)
print(f"Detected {len(detections)} objects")
if len(detections) > 0:
    print("✅ PASS")
else:
    print("⚠️  No objects (might be normal)")
"""
    success, stdout, stderr = run_in_conda_env("goodq_object_detect", code)
    print(stdout)
    if stderr:
        print(f"Stderr: {stderr[:500]}")
    return success and "✅" in stdout


def test_image_caption():
    """Test BLIP in goodq_image_caption env"""
    print("\n=== Testing Image Caption (BLIP) in goodq_image_caption env ===")
    code = """
import os
os.environ['HF_HOME'] = 'L:/models'
os.environ['TORCH_HOME'] = 'L:/models'
os.environ['TRANSFORMERS_CACHE'] = 'L:/models/transformers'

import torch
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image

device = "cuda" if torch.cuda.is_available() else "cpu"
proc = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(device)
model.eval()

img_path = 'L:/goodq4all/logs/ingest_full/1987_1988/frames/scene_0000.jpg'
img = Image.open(img_path).convert("RGB")
inputs = proc(images=img, return_tensors="pt").to(device)
out = model.generate(**inputs, max_new_tokens=32)
text = proc.decode(out[0], skip_special_tokens=True)
print(f"Caption: {text}")
if text:
    print("✅ PASS")
else:
    print("❌ FAIL")
"""
    success, stdout, stderr = run_in_conda_env("goodq_image_caption", code)
    print(stdout)
    if stderr and "error" in stderr.lower():
        print(f"Stderr: {stderr[:500]}")
    return success and "✅" in stdout


def test_audio_transcription():
    """Test Whisper in goodq_audio_transcribe env"""
    print("\n=== Testing Audio Transcription (Whisper) in goodq_audio_transcribe env ===")
    code = """
import os
os.environ['HF_HOME'] = 'L:/models'
os.environ['TORCH_HOME'] = 'L:/models'
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

from faster_whisper import WhisperModel
model = WhisperModel("medium", device="cuda", compute_type="float16")
audio = 'L:/goodq4all/logs/ingest_full/1987_1988/audio/scene_0000.wav'
segments, info = model.transcribe(audio, beam_size=5, vad_filter=True)
transcript = " ".join([seg.text for seg in segments if seg.text])
print(f"Transcript length: {len(transcript)} chars")
if transcript:
    print(f"Sample: {transcript[:100]}")
    print("✅ PASS")
else:
    print("⚠️  No transcript (audio might be silent)")
"""
    success, stdout, stderr = run_in_conda_env("goodq_audio_transcribe", code)
    print(stdout)
    if stderr and "error" in stderr.lower():
        print(f"Stderr: {stderr[:500]}")
    return success and ("✅" in stdout or "⚠️" in stdout)


def test_emotion_classification():
    """Test emotion model in goodq_emotion_classify env"""
    print("\n=== Testing Emotion Classification in goodq_emotion_classify env ===")
    code = """
import os
os.environ['HF_HOME'] = 'L:/models'
os.environ['TORCH_HOME'] = 'L:/models'
os.environ['TRANSFORMERS_CACHE'] = 'L:/models/transformers'

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

name = "cardiffnlp/twitter-roberta-base-emotion-multilabel-latest"
tok = AutoTokenizer.from_pretrained(name)
model = AutoModelForSequenceClassification.from_pretrained(name)
device = "cuda" if torch.cuda.is_available() else "cpu"
model = model.to(device).eval()

text = "I'm so excited and happy!"
inputs = tok(text, return_tensors="pt", truncation=True, max_length=512).to(device)
with torch.no_grad():
    logits = model(**inputs).logits
    probs = torch.sigmoid(logits).cpu().numpy().tolist()[0]

print(f"Generated {len(probs)} emotion scores")
print("✅ PASS")
"""
    success, stdout, stderr = run_in_conda_env("goodq_emotion_classify", code)
    print(stdout)
    if stderr and "error" in stderr.lower():
        print(f"Stderr: {stderr[:500]}")
    return success and "✅" in stdout


def test_text_embedding():
    """Test sentence transformers in goodq_text_embed env"""
    print("\n=== Testing Text Embedding in goodq_text_embed env ===")
    code = """
import os
os.environ['HF_HOME'] = 'L:/models'
os.environ['TORCH_HOME'] = 'L:/models'

import torch
from sentence_transformers import SentenceTransformer

device = "cuda" if torch.cuda.is_available() else "cpu"
model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
text = "This is a test sentence."
vec = model.encode([text], normalize_embeddings=True)
print(f"Embedding shape: {vec.shape}")
print("✅ PASS")
"""
    success, stdout, stderr = run_in_conda_env("goodq_text_embed", code)
    print(stdout)
    if stderr and "error" in stderr.lower():
        print(f"Stderr: {stderr[:500]}")
    return success and "✅" in stdout


def main():
    """Run all validation tests in isolated environments"""
    print("="*60)
    print("ISOLATED ENVIRONMENT MODEL VALIDATION")
    print("="*60)
    
    results = {
        "Object Detection (YOLO)": test_object_detection(),
        "Image Captioning (BLIP)": test_image_caption(),
        "Audio Transcription (Whisper)": test_audio_transcription(),
        "Emotion Classification": test_emotion_classification(),
        "Text Embedding": test_text_embedding(),
    }
    
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    
    if failed > 0:
        print("\n⚠️  Some models failed. Check errors above.")
        return 1
    else:
        print("\n✅ All models are working in their isolated environments!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
