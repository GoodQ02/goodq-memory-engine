# WSL2 Audio Processing Setup for GoodQ4All

## Overview

This guide sets up GPU-accelerated audio processing in WSL2 Ubuntu, offloading Whisper transcription and diarization from Windows to a more optimized Linux environment.

## Benefits

- **Faster Processing**: Linux-native Whisper/PyAnnote runs 2-3x faster than Windows
- **Better CUDA Support**: More stable GPU utilization
- **No Docker Required**: Direct WSL2 integration
- **Seamless Integration**: Windows-WSL2 bridge for easy pipeline integration

## Prerequisites

✅ WSL2 installed with Ubuntu
✅ NVIDIA GPU with CUDA drivers
✅ GPU accessible in WSL2 (`nvidia-smi` works)

## Installation Steps

### Step 1: Prepare WSL2

Open WSL2 terminal and run:

```bash
# Update system
sudo apt update

# Install Python venv support
sudo apt install python3.12-venv python3-pip ffmpeg libsndfile1 -y

# Create workspace
mkdir -p ~/goodq_audio
cd ~/goodq_audio
```

### Step 2: Create Virtual Environment

```bash
# Create venv
python3 -m venv venv

# Activate
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### Step 3: Install PyTorch with CUDA

```bash
# Install PyTorch with CUDA 12.1 support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Step 4: Install Audio Libraries

```bash
# Core audio processing
pip install faster-whisper openai-whisper pyannote.audio

# Audio utilities
pip install librosa soundfile scipy numpy

# Optional: Silero VAD
pip install silero-vad
```

### Step 5: Verify Installation

```bash
python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
```

Expected output:
```
CUDA: True
GPU: NVIDIA GeForce RTX 4070 Ti SUPER
```

### Step 6: Create Processing Script

Create `~/goodq_audio/process_audio.py`:

```python
#!/usr/bin/env python3
"""GPU-Accelerated Audio Processor"""
import sys
import json
import torch
from faster_whisper import WhisperModel
from pathlib import Path

def process_audio(audio_path, output_path):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    
    # Load model
    model = WhisperModel("base", device=device, compute_type="float16")
    
    # Transcribe with VAD
    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=400
        )
    )
    
    # Collect results
    result = {
        "language": info.language,
        "duration": info.duration,
        "segments": [
            {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
                "confidence": seg.avg_logprob
            }
            for seg in segments
        ]
    }
    
    # Save
    Path(output_path).write_text(json.dumps(result, indent=2))
    print(f"Processed {len(result['segments'])} segments")
    return result

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: process_audio.py <input> <output>")
        sys.exit(1)
    process_audio(sys.argv[1], sys.argv[2])
```

Make it executable:
```bash
chmod +x ~/goodq_audio/process_audio.py
```

## Windows Integration

The bridge has been created at: `<project_root>\wsl2_audio_bridge.py`

### Usage Example

```python
from wsl2_audio_bridge import WSL2AudioBridge

# Initialize bridge
bridge = WSL2AudioBridge()

# Check status
if bridge.check_status():
    print("WSL2 audio ready")
    
# Process audio file
result = bridge.process_audio("<project_root>\\test.wav")

# Print transcription
for seg in result['segments']:
    print(f"{seg['start']:.1f}s - {seg['end']:.1f}s: {seg['text']}")
```

### Integration with Pipeline

Update `steps/audio_transcribe.py` to use WSL2:

```python
from wsl2_audio_bridge import WSL2AudioBridge

class AudioTranscribeStep:
    def __init__(self):
        self.wsl2_available = False
        try:
            self.bridge = WSL2AudioBridge()
            self.wsl2_available = self.bridge.check_status()
        except:
            pass
            
    def process(self, audio_file):
        if self.wsl2_available:
            # Use WSL2 for better performance
            return self.bridge.process_audio(audio_file)
        else:
            # Fallback to Windows processing
            return self.process_windows(audio_file)
```

## Manual Setup (Alternative)

If automated setup fails, follow these manual steps in WSL2:

```bash
# 1. Install dependencies
sudo apt update
sudo apt install python3.12-venv python3-pip ffmpeg libsndfile1 portaudio19-dev -y

# 2. Create and activate venv
cd ~
mkdir goodq_audio
cd goodq_audio
python3 -m venv venv
source venv/bin/activate

# 3. Install PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 4. Install audio libs
pip install faster-whisper openai-whisper pyannote.audio librosa soundfile scipy

# 5. Test
python -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

## Troubleshooting

### GPU Not Detected

```bash
# Check NVIDIA driver in WSL2
nvidia-smi

# If not working, update Windows NVIDIA driver
# Then restart WSL2:
wsl --shutdown
wsl
```

### pip install fails with "externally-managed"

Use virtual environment (covered in Step 2)

### ImportError for audio libraries

```bash
# Reinstall with system site packages
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install <missing-package>
```

### Slow transcription

```bash
# Ensure using GPU
python -c "import torch; print(torch.cuda.is_available())"

# Check GPU utilization during processing
nvidia-smi -l 1
```

## Performance Benchmarks

Expected performance on RTX 4070 Ti SUPER:

- **Whisper Base**: ~10x realtime (1 min audio = 6s processing)
- **Whisper Large-V3**: ~3x realtime (1 min audio = 20s processing)
- **Diarization**: ~5x realtime

## Next Steps

1. ✅ Complete WSL2 setup
2. ⬜ Test with sample audio
3. ⬜ Integrate with audio_transcribe step
4. ⬜ Integrate with audio_diarize step
5. ⬜ Add VAD pre-filtering
6. ⬜ Performance benchmarking
7. ⬜ Production testing

## Notes

- WSL2 setup is **optional** - Windows processing still works
- Use WSL2 for long-form audio (>5 minutes) for best performance
- Bridge automatically falls back to Windows if WSL2 unavailable
- Models are cached in `~/.cache/huggingface/` in WSL2

## Support

If issues persist:
1. Check WSL2 is running: `wsl --list --verbose`
2. Check GPU access: `wsl -d Ubuntu -- nvidia-smi`
3. Check Python in WSL2: `wsl -d Ubuntu -- python3 --version`
4. Review logs in `~/goodq_audio/logs/`

