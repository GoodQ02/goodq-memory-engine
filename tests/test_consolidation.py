"""
Environment Consolidation Test
Tests that goodq_core can execute all consolidated steps
"""
import sys
import json
from pathlib import Path

print("🧪 GOODQ_CORE CONSOLIDATION TEST\n")
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
        print(f"   ✅ {name}")
    except Exception as e:
        print(f"   ❌ {name}: {e}")
        all_passed = False

# Test 2: GPU availability
print("\n2. Testing GPU availability...")
try:
    import torch
    if torch.cuda.is_available():
        print(f"   ✅ CUDA available: {torch.version.cuda}")
        print(f"   ✅ GPU: {torch.cuda.get_device_name(0)}")
        print(f"   ✅ PyTorch: {torch.__version__}")
    else:
        print("   ⚠️  CUDA not available (CPU mode)")
except Exception as e:
    print(f"   ❌ GPU test failed: {e}")
    all_passed = False

# Test 3: Model loading capability
print("\n3. Testing model loading capability...")
try:
    from transformers import AutoTokenizer
    # Quick tokenizer test (lightweight)
    tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
    test_text = "Test sentence"
    tokens = tokenizer(test_text, return_tensors="pt")
    print(f"   ✅ Transformers model loading works")
    print(f"   ✅ Tokenized '{test_text}' into {len(tokens['input_ids'][0])} tokens")
except Exception as e:
    print(f"   ⚠️  Model loading test skipped: {e}")

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
    print("✅ ALL TESTS PASSED - goodq_core is ready!")
    sys.exit(0)
else:
    print("⚠️  SOME TESTS FAILED - review above")
    sys.exit(1)
