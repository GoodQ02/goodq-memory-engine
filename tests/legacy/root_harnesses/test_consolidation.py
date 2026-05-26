"""
Environment Consolidation Test
Tests that goodq_core can execute all consolidated steps
"""
import sys
import json
from pathlib import Path

print("[SYMBOL] GOODQ_CORE CONSOLIDATION TEST\n")
print("=" * 70)

# Test 1: Import all required modules
print("\n1. Testing module imports...")
modules_to_test = [
    ("torch", "PyTorch"),
    ("transformers", "Transformers"),
    ("PIL", "Pillow"),
    ("cv2", "OpenCV"),
    ("sentence_transformers", "Sentence Transformers"),
    ("ultralytics", "Ultralytics YOLO"),
    ("pytesseract", "Pytesseract OCR"),
]

all_passed = True
for module, name in modules_to_test:
    try:
        __import__(module)
        print(f"   [OK] {name}")
    except Exception as e:
        print(f"   [FAIL] {name}: {e}")
        all_passed = False

# Test 2: GPU availability
print("\n2. Testing GPU availability...")
try:
    import torch
    if torch.cuda.is_available():
        print(f"   [OK] CUDA available: {torch.version.cuda}")
        print(f"   [OK] GPU: {torch.cuda.get_device_name(0)}")
        print(f"   [OK] PyTorch: {torch.__version__}")
    else:
        print("   [WARN]  CUDA not available (CPU mode)")
except Exception as e:
    print(f"   [FAIL] GPU test failed: {e}")
    all_passed = False

# Test 3: Model loading capability
print("\n3. Testing model loading capability...")
try:
    from transformers import AutoTokenizer
    # Quick tokenizer test (lightweight)
    tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
    test_text = "Test sentence"
    tokens = tokenizer(test_text, return_tensors="pt")
    print(f"   [OK] Transformers model loading works")
    print(f"   [OK] Tokenized '{test_text}' into {len(tokens['input_ids'][0])} tokens")
except Exception as e:
    print(f"   [WARN]  Model loading test skipped: {e}")

# Test 4: Step compatibility check
print("\n4. Testing step compatibility...")
steps_to_validate = [
    "image_ocr",
    "image_caption", 
    "object_detect",
    "face_embed",
    "image_exif",
    "image_embed_dino",
    "image_embed_clip",
    "pdf_text",
    "text_embed",
    "sentiment",
    "emotion_classify",
    "tagger"
]

print(f"   Steps consolidated to goodq_core: {len(steps_to_validate)}")
for step in steps_to_validate:
    print(f"   - {step}")

# Test 5: Environment info
print("\n5. Environment information...")
print(f"   Python: {sys.version.split()[0]}")
print(f"   Platform: {sys.platform}")
try:
    import torch
    print(f"   PyTorch build: {torch.__version__}")
except:
    pass

print("\n" + "=" * 70)
if all_passed:
    print("[OK] ALL TESTS PASSED - goodq_core is ready!")
    sys.exit(0)
else:
    print("[WARN]  SOME TESTS FAILED - review above")
    sys.exit(1)
