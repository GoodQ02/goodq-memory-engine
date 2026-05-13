# WSL2 GPU Audio - Quick Start

## ✅ Setup Complete!

The WSL2 audio environment is installed and the pipeline has been updated to use it.

## 🚀 Starting the Service

Before running ingestion, start the WSL2 audio service:

```batch
.\wsl2_audio\start_wsl2_service.bat
```

This will launch the GPU-accelerated audio processing service in the background.

## 🎯 What Changed

### Before (CPU-based):
- Diarization: **SLOW** (hundreds of seconds per scene)
- Transcription: CPU-only
- Emotion: CPU-only

### After (GPU-accelerated):
- Diarization: **FAST** (GPU-accelerated via pyannote)
- Transcription: **FAST** (Faster Whisper with CUDA)
- Emotion: **FAST** (GPU-accelerated models)

## 🔍 Monitoring

Check the WSL2 service logs:
```bash
wsl tail -f ~/goodq_audio/logs/audio_service.log
```

Check GPU usage in WSL2:
```bash
wsl nvidia-smi
```

## 🛑 Stopping the Service

```batch
wsl pkill -f audio_service.py
```

## 📊 Expected Performance

- **Diarization**: ~5-10x faster than CPU
- **Transcription**: ~10-20x faster than CPU  
- **Overall audio processing**: Reduced from bottleneck to negligible

## ⚙️ Configuration

Edit `wsl2_audio\config.json` to customize:
- Whisper model size
- Diarization parameters
- GPU memory allocation

## 🐛 Troubleshooting

**Service won't start:**
- Check HuggingFace token in `~/goodq_audio/config.json`
- Verify CUDA available: `wsl python3 -c "import torch; print(torch.cuda.is_available())"`

**Slow processing:**
- Confirm GPU is being used: `wsl nvidia-smi`
- Check service logs for errors

**Files not processing:**
- Verify queue directories exist:
  - `wsl2_audio\queue_in`
  - `wsl2_audio\queue_out`

## ✨ Integration

The pipeline automatically detects and uses WSL2 audio when available.

No code changes needed - just start the service and run ingestion normally!
