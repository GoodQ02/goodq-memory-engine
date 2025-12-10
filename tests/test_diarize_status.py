"""
Simple Audio Diarization Test - Checks current state
"""
import sys
from pathlib import Path

print("="*80)
print("  AUDIO DIARIZATION STATUS CHECK")
print("="*80)

# Test 1: Check if we're in the right environment
print("\n[1/5] Environment Check...")
print(f"  Python: {sys.executable}")
print(f"  Version: {sys.version}")

# Test 2: Check PyTorch and CUDA
print("\n[2/5] PyTorch Check...")
try:
    import torch
    print(f"  [SYMBOL] PyTorch: {torch.__version__}")
    print(f"  [SYMBOL] CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  [SYMBOL] GPU: {torch.cuda.get_device_name(0)}")
        print(f"  [SYMBOL] Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")
except Exception as e:
    print(f"  [SYMBOL] PyTorch error: {e}")

# Test 3: Check PyAnnote
print("\n[3/5] PyAnnote Check...")
try:
    from pyannote.audio import Pipeline
    print("  [SYMBOL] pyannote.audio is installed")
    pyannote_available = True
except ImportError as e:
    print(f"  [SYMBOL] pyannote.audio not installed: {e}")
    pyannote_available = False

# Test 4: Check Whisper
print("\n[4/5] Whisper Check...")
try:
    import whisper
    print("  [SYMBOL] Whisper is installed")
except ImportError:
    print("  [SYMBOL] Whisper not installed")

# Test 5: Check our step code
print("\n[5/5] GoodQ Step Code Check...")
try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from steps.audio_diarize import step
    print("  [SYMBOL] audio_diarize step module exists")
except Exception as e:
    print(f"  [SYMBOL] Failed to import step: {e}")

# Summary
print("\n" + "="*80)
if pyannote_available:
    print("STATUS: [SYMBOL] Ready for diarization testing")
else:
    print("STATUS: [SYMBOL] Missing pyannote.audio - installation needed")
print("="*80)
