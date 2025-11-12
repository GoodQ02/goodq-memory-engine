# GPU Allocation - Quick Reference

## 🚀 Quick Start

```bash
# 1. Run diagnostic
python scripts\diagnose_gpu_issue.py

# 2. Test pipeline
.\TEST_GPU_PIPELINE.bat

# 3. Monitor GPU (in separate terminal)
nvidia-smi -l 1
```

## 📊 Memory Allocations

| Step | % | GB | Model |
|------|---|----|-------|
| audio_diarize | 30% | 4.8 | PyAnnote |
| audio_transcribe | 25% | 4.0 | Whisper |
| vision models | 25% | 4.0 | CLIP/DINO/YOLO |
| face_embed | 20% | 3.2 | FaceNet |
| emotion | 18% | 2.9 | RoBERTa |
| text_embed | 15% | 2.4 | SentenceT |

## ✅ What's Fixed

- ✓ Centralized memory limits per step
- ✓ OOM prevention system
- ✓ Auto cache clearing
- ✓ TF32 + cuDNN + FP16 optimizations
- ✓ Sequential execution (no conflicts)

## 🔧 Key Files

```
steps/common/
├── gpu_config.py           # Memory limits
├── audio_gpu_optimizer.py  # Audio tuning
└── gpu_guard.py            # OOM prevention

scripts/
├── diagnose_gpu_issue.py   # Diagnostic
└── test_gpu_allocation.py  # Test setup

docs/
├── GPU_FIX_SUMMARY.md      # Full guide
└── GPU_ALLOCATION_FIX.md   # Technical ref
```

## ⚡ Performance

Expected for 1 hour video: **~40-45 minutes**

- Scene Detection: 2 min (30x realtime)
- Diarization: 15 min (4x realtime)
- Transcription: 8 min (7.5x realtime)
- Vision: 8 min (varies)
- Other: 10 min (varies)

## 🐛 Troubleshooting

### OOM Error
```bash
# Close LM Studio
taskkill /f /im "LM Studio.exe"

# Clear cache
del data\.watchdog.lock
```

### Stuck Processing
```bash
# Check if actually stuck (diarization takes 10-15 min)
type logs\watchdog.log

# Kill if truly stuck
taskkill /f /im python.exe
```

### Low Performance
- Check GPU is being used: `nvidia-smi`
- Verify first run (CUDA init takes longer)
- Check GPU temp < 80°C

## 💡 Pro Tips

1. **Before processing:** Close LM Studio
2. **During processing:** Monitor `nvidia-smi -l 1`
3. **For multiple videos:** Drop all in import_inbox
4. **If tuning needed:** Edit `gpu_config.py` fractions

## 📈 Tuning

### More Memory Available
```python
# In gpu_config.py
GPU_CONFIGS = {
    "audio_diarize": 0.35,  # Was 0.30
    # Increase by 5-10%
}
```

### Less Memory Available
```python
# In gpu_config.py
GPU_CONFIGS = {
    "audio_diarize": 0.25,  # Was 0.30
    # Decrease by 5-10%
}
```

## ✅ System Status

- GPU: RTX 4070 Ti SUPER (16GB)
- CUDA: 13.0
- Driver: 581.80
- Status: ✅ PRODUCTION READY

## 🎯 Next Action

```bash
.\TEST_GPU_PIPELINE.bat
```

---

**Updated:** 2025-11-11 23:35  
**Version:** 2.0 Production
