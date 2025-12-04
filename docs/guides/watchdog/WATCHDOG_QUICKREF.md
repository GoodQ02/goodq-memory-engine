# GoodQ Watchdog - Quick Reference Card

> Role: Quick command and operations reference for the Watchdog system. For full explanations, edge cases, and troubleshooting, use `docs/WATCHDOG_GUIDE.md` and `docs/WATCHDOG_INDEX.md`.

## One-Line Summary
Drop files in `import_inbox/`, watchdog auto-processes them.

---

## Quick Commands

| Task | Command |
|------|---------|
| **Start Watchdog** | `START_WATCHDOG.bat` |
| **Check Status** | `CHECK_WATCHDOG.bat` |
| **Live Monitor** | `MONITOR_WATCHDOG.bat` |
| **Stop Watchdog** | `Ctrl+C` in watchdog window |

---

## Drop Zone

```
L:\goodq4all\import_inbox\
```

---

## Supported Files

| Type | Extensions |
|------|------------|
| Video | `.mp4` `.avi` `.mov` `.mkv` `.wmv` `.flv` `.webm` `.m4v` |
| Audio | `.mp3` `.wav` `.flac` `.m4a` `.aac` `.ogg` `.wma` |
| Image | `.jpg` `.jpeg` `.png` `.bmp` `.gif` `.tiff` `.webp` |
| Document | `.pdf` `.txt` `.md` `.doc` `.docx` |

---

## File Flow

```
import_inbox/
    ↓ (detected in 2s)
    ↓ (stable for 3s)
    ↓ (hash checked)
processing/
    ↓ (pipeline runs)
    ↓
processed/  or  failed/
```

---

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `import_inbox/` | Drop files here |
| `data/processing/` | Temp during processing |
| `data/processed/` | Successfully processed |
| `data/failed/` | Failed processing |

---

## Logs

| File | Purpose |
|------|---------|
| `logs/watchdog.log` | Activity log |
| `logs/watchdog_state.json` | Processed files registry |

---

## Common Tasks

### Check if Running
```powershell
Get-Process python | Where-Object {$_.CommandLine -like '*watchdog*'}
```

### View Live Logs
```powershell
Get-Content L:\goodq4all\logs\watchdog.log -Wait -Tail 20
```

### Check Registry
```powershell
Get-Content L:\goodq4all\logs\watchdog_state.json | ConvertFrom-Json
```

### Count Files
```powershell
# Inbox
(Get-ChildItem L:\goodq4all\import_inbox -File).Count

# Processed
(Get-ChildItem L:\goodq4all\data\processed -File).Count

# Failed
(Get-ChildItem L:\goodq4all\data\failed -File).Count
```

---

## Testing

### Run Tests
```batch
conda activate goodq_zenml
python scripts\test_watchdog.py
```

### Create Test File
```batch
python scripts\test_watchdog_simple.py
```

---

## Troubleshooting

### Files Not Detected
- Check file extension is supported
- Verify watchdog is running
- Check `logs/watchdog.log` for errors

### Processing Fails
- Check `data/failed/` for file
- Review error in `logs/watchdog.log`
- Try manual processing:
  ```batch
  conda activate goodq_zenml
  python cli\run_ingestion.py ingest path\to\file.mp4
  ```

### Already Processed
- File with same content (hash) already exists
- Check `logs/watchdog_state.json`
- Original marked as `PROCESSED_*`

---

## Configuration

Edit `scripts/watchdog_ingest.py`:

```python
POLL_INTERVAL = 2.0      # Scan every 2 seconds
STABILITY_WAIT = 3.0     # Wait 3s for stability
MAX_WORKERS = 1          # Process 1 file at a time
```

---

## Status Dashboard

When you run `CHECK_WATCHDOG.bat`, you see:
- ✅ Watchdog running status
- 📊 File counts (inbox, processing, processed, failed)
- 📁 Recent inbox files
- 📈 All-time statistics
- 📝 Recent log activity

---

## Tips

- **Start watchdog before dropping files** for immediate processing
- **Use MONITOR_WATCHDOG.bat** for real-time status during batch processing
- **Check failed directory** if processing seems stuck
- **Don't delete watchdog_state.json** unless resetting registry
- **Archive processed files** periodically to save space

---

## Full Documentation

- **User Guide**: `docs/WATCHDOG_GUIDE.md`
- **Architecture**: `docs/diagrams/watchdog_flow.md`
- **Summary**: `docs/WATCHDOG_SUMMARY.md`
- **Changelog**: `docs/WATCHDOG_CHANGELOG.md`

---

## Need Help?

1. Check `logs/watchdog.log`
2. Read `docs/WATCHDOG_GUIDE.md`
3. Run `python scripts\test_watchdog.py`
4. Report issues on GitHub

---

**Version**: 1.0.0 | **Updated**: October 7, 2025
