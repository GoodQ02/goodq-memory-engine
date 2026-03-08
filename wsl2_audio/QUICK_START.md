# WSL2 Audio - Quick Start Guide

## What is This?

A GPU-accelerated audio processing system that runs in WSL2 Linux for **3-5x faster transcription** and **2-3x faster diarization** compared to Windows-native processing.

## One-Command Install

```cmd
cd <repo_root>
INSTALL_WSL2_AUDIO.bat
```

Follow the prompts. Total time: ~30 minutes.

## What You Need

- Windows 11 or Windows 10 21H2+
- NVIDIA GPU (8GB+ VRAM)
- WSL2 with Ubuntu
- HuggingFace account (free)

## 5-Step Setup

### 1. Run Installer

```cmd
INSTALL_WSL2_AUDIO.bat
```

### 2. Get HuggingFace Token

- Visit: https://huggingface.co/settings/tokens
- Copy your token
- Paste into `~/goodq_audio/config.json` in WSL2

### 3. Start Service

```cmd
wsl2_audio\start_wsl2_service.bat
```

### 4. Test It

```cmd
python wsl2_audio\test_bridge.py
```

### 5. Enable in Pipeline

```cmd
python wsl2_audio\enable_in_pipeline.py
```

## Done!

Your pipeline now uses WSL2 for audio processing.

## Daily Use

**Start the service:**
```cmd
wsl2_audio\start_wsl2_service.bat
```

**Run the pipeline:**
```cmd
launch_goodq.bat
```

**Check service status:**
```cmd
wsl pgrep -f audio_service
```

**View logs:**
```cmd
wsl tail -f ~/goodq_audio/logs/audio_service.log
```

**Stop service:**
```cmd
wsl pkill -f audio_service
```

## Troubleshooting

**Service won't start?**
```cmd
wsl cat ~/goodq_audio/logs/audio_service.log
```

**CUDA not working?**
```cmd
wsl nvidia-smi
```

**Jobs timeout?**
Edit `wsl2_audio\bridge_config.json`:
```json
{
  "timeout_seconds": 7200
}
```

## Performance

**Example: 1 hour home movie**

| Method | Time | Speed |
|--------|------|-------|
| Windows (GPU) | 50 min | 1.2x |
| WSL2 (GPU + VAD) | 14 min | 4.3x |

**Real savings over 24 hours of video:**
- Windows: ~20 hours
- WSL2: ~5.6 hours
- **Saved: 14.4 hours!**

## More Info

- Full docs: `wsl2_audio\README.md`
- Migration guide: `docs\WSL2_AUDIO_MIGRATION_GUIDE.md`
- Troubleshooting: Check canonical Windows logs plus `~/goodq_audio/logs/`

## Support

Common fixes:
1. Restart WSL2: `wsl --shutdown`
2. Restart service: `wsl pkill -f audio_service` then start again
3. Check GPU: `wsl nvidia-smi`
4. Update drivers: https://developer.nvidia.com/cuda/wsl

## Rollback

To disable WSL2 audio:

```cmd
wsl pkill -f audio_service
copy pipelines\ingest_multimodal_conda.py.backup_before_wsl2 pipelines\ingest_multimodal_conda.py
```

Then restart the pipeline.

---

**Questions?** Check the logs or re-run the installer.
