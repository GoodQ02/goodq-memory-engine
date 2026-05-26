<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: HISTORICAL_POINTER -->
<!-- DOC_CANONICAL_POINTER: docs/reference/WSL_AUDIO_RUNTIME.md -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# WSL2 Audio Processing - Quick Reference Card

> Historical bridge-era quick reference. For current WSL audio setup and
> runtime authority, use `docs/reference/WSL_AUDIO_RUNTIME.md`,
> `docs/guides/install/INSTALL.md`, and `wsl2_audio/README.md`.

## Installation (First Time)

```batch
cd <project_root>
INSTALL_WSL2_AUDIO.bat
```

**Time:** 10-15 minutes  
**Requires:** Sudo password in WSL2

---

## Verify Installation

```batch
python wsl2_audio_bridge.py
```

**Expected Output:**
```
Status: Ready
System Info:
Device: cuda
GPU: NVIDIA GeForce RTX 4070 Ti SUPER
VRAM: 16.0GB
```

---

## Basic Usage

### Python API

```python
from wsl2_audio_bridge import WSL2AudioBridge

# Initialize
bridge = WSL2AudioBridge()

# Check status
if bridge.check_status():
    # Process audio
    result = bridge.process_audio("<GOODQ_DATA_ROOT>\\audio\\file.wav")
    
    # Read transcription
    for seg in result['segments']:
        print(f"{seg['start']:.1f}s: {seg['text']}")
```

### Quick Test

```python
from wsl2_audio_bridge import WSL2AudioBridge

bridge = WSL2AudioBridge()
print("Ready:", bridge.check_status())
print(bridge.get_info())
```

---

## Integration Pattern

The active runtime does not require pipeline-file edits.

- Launch GoodQ4All via `LAUNCH_GOODQ.bat` or `LAUNCH_GOODQ.ps1`
- Ingestion is owned by `cli.run_ingestion`
- WSL audio is selected by profile and runtime flags, with structured fallback when strict mode is not enabled

---

## Troubleshooting

### Problem: "Not Ready"

```bash
# Check WSL2 is running
wsl --list --verbose

# Check workspace exists
wsl ls ~/goodq_audio

# Reinstall if needed
INSTALL_WSL2_AUDIO.bat
```

### Problem: GPU Not Detected

```bash
# Check in WSL2
wsl -d Ubuntu -- nvidia-smi

# If fails:
# 1. Update Windows NVIDIA driver
# 2. Restart WSL2
wsl --shutdown
wsl
```

### Problem: Import Errors

```bash
# Reinstall packages in WSL2
wsl -d Ubuntu
source ~/goodq_audio/venv/bin/activate
pip install <missing-package>
```

---

## Performance Quick Facts

| Metric | Value |
|--------|-------|
| Setup Time | 10-15 min |
| Speed Gain | 2-5x faster |
| GPU Usage | 75-90% (vs 40-60%) |
| Fallback | Automatic to Windows |
| Models | Whisper, PyAnnote, VAD |

---

## File Locations

### Windows
- Bridge: `<project_root>\wsl2_audio_bridge.py`
- Installer: `<project_root>\INSTALL_WSL2_AUDIO.bat`
- Runtime docs: `<project_root>\docs\reference\WSL_AUDIO_RUNTIME.md`
- Setup docs: `<project_root>\docs\guides\llm\WSL2_AUDIO_SETUP.md`

### WSL2
- Workspace: `~/goodq_audio/`
- Venv: `~/goodq_audio/venv/`
- Processor: `~/goodq_audio/process_audio.py`
- Models: `~/.cache/huggingface/`

---

## Common Commands

### Check Status
```python
python wsl2_audio_bridge.py
```

### Manual Process
```bash
wsl -d Ubuntu -- ~/goodq_audio/venv/bin/python \
    ~/goodq_audio/process_audio.py \
    /mnt/l/audio/file.wav \
    /mnt/l/output/result.json
```

### View Logs
```bash
wsl -d Ubuntu -- cat ~/goodq_audio/logs/latest.log
```

### GPU Monitor
```bash
wsl -d Ubuntu -- nvidia-smi -l 1
```

---

## Documentation Links

1. **Current setup:** `docs\guides\llm\WSL2_AUDIO_SETUP.md`
   - Architecture details
   - Integration guide
   - Testing procedures

2. **Runtime truth:** `docs\reference\WSL_AUDIO_RUNTIME.md`
   - Active execution model
   - Fallback behavior
   - Successful payload surface

---

## Quick Wins

✅ **Easy Install** - One command setup  
✅ **Fast Processing** - 2-5x speed increase  
✅ **Auto Fallback** - Works without WSL2  
✅ **GPU Powered** - Full CUDA acceleration  
✅ **Drop-in** - Minimal code changes  

---

## Next Steps After Install

1. ✅ Install: `INSTALL_WSL2_AUDIO.bat`
2. ✅ Verify: `python wsl2_audio_bridge.py`
3. ⬜ Launch the canonical runtime
4. ⬜ Test with sample audio
5. ⬜ Process home movies
6. ⬜ Measure performance gains

---

**Need Help?**
- Check: `docs\guides\llm\WSL2_AUDIO_SETUP.md`
- Review: `docs\reference\WSL_AUDIO_RUNTIME.md`
- Test: `python wsl2_audio_bridge.py`

