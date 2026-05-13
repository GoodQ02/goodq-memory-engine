# WSL2 Audio Processing - Quick Reference

## Service Control

### Start Service
```bash
# From Windows
.\wsl2_audio\start_wsl2_service.bat

# From WSL2
cd ~/goodq_audio
source setup_cuda_env.sh
python3 ~/goodq_audio/audio_service.py &
```

### Stop Service
```bash
wsl pkill -f audio_service.py
```

### Check Service Status
```bash
ps aux | grep audio_service | grep -v grep
```

### View Logs
```bash
tail -f ~/goodq_audio/logs/audio_service.log
```

## Environment Setup

### Activate CUDA Environment
```bash
cd ~/goodq_audio
source setup_cuda_env.sh
```

This sets:
- LD_LIBRARY_PATH (cuDNN libraries)
- HUGGINGFACE_TOKEN (model access)
- Activates Python venv

### Verify CUDA
```bash
cd ~/goodq_audio
source setup_cuda_env.sh
python3 -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

### Verify HF Token
```bash
cd ~/goodq_audio
grep huggingface_token config.json
```

## Testing

### Test Whisper Transcription
```bash
cd ~/goodq_audio
source setup_cuda_env.sh
python3 -c "
from faster_whisper import WhisperModel
model = WhisperModel('base', device='cuda')
segments, info = model.transcribe('./venv/lib/python3.12/site-packages/pyannote/audio/sample/sample.wav')
print('Transcript:', ' '.join([s.text for s in segments][:5]))
"
```

### Test Gated Model Access
```bash
cd ~/goodq_audio
source venv/bin/activate
python3 -c "
from huggingface_hub import HfApi
api = HfApi()
model_info = api.model_info('pyannote/speaker-diarization-3.1', token=os.getenv('HUGGINGFACE_TOKEN'))
print('Access:', 'OK' if model_info else 'FAILED')
"
```

## Important Files

### Configs
- `~/goodq_audio/config.json` - Main config (includes HF token)
- `wsl2_audio/config.json` - Repo-side service template

### Scripts
- `~/goodq_audio/setup_cuda_env.sh` - Environment setup (use instead of venv activation)
- `~/goodq_audio/fw_transcribe.py` - Direct transcription helper
- `wsl2_audio/start_wsl2_service.bat` - Windows startup script

### Logs
- `~/goodq_audio/logs/audio_service.log` - Service logs

## Expected Log Output

### Successful Startup
```
[INFO] GPU: NVIDIA GeForce RTX 4070 Ti SUPER
[INFO] CUDA: 12.8
[INFO] Loading Whisper model: medium
[INFO] [SYMBOL] Whisper model loaded
[INFO] Loading Silero VAD...
[INFO] [SYMBOL] Silero VAD loaded
[INFO] Loading diarization model: pyannote/speaker-diarization-3.1
[INFO] [SYMBOL] Diarization pipeline loaded
[INFO] Audio service initialized
[INFO] Starting queue watcher...
```

### Service Ready
- Whisper: ✅ Loaded
- VAD: ✅ Loaded
- Diarization: ✅ Loaded
- CUDA: ✅ Enabled
- HF Token: ✅ Working

## Troubleshooting

### Empty Transcripts
✅ **FIXED** - Service now uses `setup_cuda_env.sh` with proper cuDNN paths

### cuDNN Errors
```bash
# Verify LD_LIBRARY_PATH is set
echo $LD_LIBRARY_PATH | grep cudnn
```

### No Diarization
```bash
# Check token in config
grep huggingface_token ~/goodq_audio/config.json

# Should show: "huggingface_token": "hf_pnnV..."
```

### Service Won't Start
```bash
# Check for errors
cat /tmp/audio_restart.log

# Or run manually to see errors
cd ~/goodq_audio
source setup_cuda_env.sh
python3 ~/goodq_audio/audio_service.py
```

## Healthy State

- Service: running
- CUDA: enabled
- Whisper: loaded
- Diarization: loaded when `PYANNOTE_TOKEN` is available
- cuDNN: libraries accessible through `setup_cuda_env.sh`

---

**Last Updated:** December 13, 2024  
**Documentation:** See `WSL2_AUDIO_FIX_COMPLETE.md` and `HF_TOKEN_SETUP_COMPLETE.md`
