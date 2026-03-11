# GoodQ Watchdog - Quick Reference Card

> Role: Quick command and operations reference for the Watchdog system. For full explanations, edge cases, and troubleshooting, use `docs/guides/watchdog/WATCHDOG_GUIDE.md` and `docs/guides/watchdog/WATCHDOG_INDEX.md`.

## One-Line Summary
Drop files in `import_inbox/`, watchdog auto-processes them.

---

## Quick Commands

| Task | Command |
|------|---------|
| **Start Watchdog** | `python -m cli.watchdog` |
| **Check Status** | `python scripts/utils/check_watchdog_status.py` |
| **Live Monitor** | `scripts/monitoring/monitor_live.bat` |
| **Stop Watchdog** | `Ctrl+C` in watchdog window |

---

## Drop Zone

```
<project_root>\import_inbox\
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
Get-Content <project_root>\logs\watchdog.log -Wait -Tail 20
```

### Check Registry
```powershell
Get-Content <project_root>\logs\watchdog_state.json | ConvertFrom-Json
```

### Count Files
```powershell
# Inbox
(Get-ChildItem <project_root>\import_inbox -File).Count

# Processed
(Get-ChildItem <project_root>\data\processed -File).Count

# Failed
(Get-ChildItem <project_root>\data\failed -File).Count
```

---

## Testing

### Run Tests
```batch
conda run -n goodq_core python tests\integration\test_watchdog.py
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
  conda activate goodq_core
  python cli\run_ingestion.py ingest path\to\file.mp4
  ```

### Already Processed
- File with same content (hash) already exists
- Check `logs/watchdog_state.json`
- Original marked as `PROCESSED_*`

---

## Configuration

Adjust the watchdog constants in `cli/watchdog.py`:

```python
POLL_INTERVAL = 2.0      # Scan every 2 seconds
STABILITY_WAIT = 3.0     # Wait 3s for stability
MAX_WORKERS = 1          # Process 1 file at a time
```

---

## Status Dashboard

When you run `python scripts/utils/check_watchdog_status.py`, you see:
- ✅ Watchdog running status
- 📊 File counts (inbox, processing, processed, failed)
- 📁 Recent inbox files
- 📈 All-time statistics
- 📝 Recent log activity

---

## Tips

- **Start watchdog before dropping files** for immediate processing
- **Use `scripts/monitoring/monitor_live.bat`** for real-time status during batch processing
- **Check failed directory** if processing seems stuck
- **Don't delete watchdog_state.json** unless resetting registry
- **Archive processed files** periodically to save space

---

## Full Documentation

- **User Guide**: `docs/guides/watchdog/WATCHDOG_GUIDE.md`
- **Architecture**: `docs/diagrams/watchdog_flow.md`
- **Summary**: `docs/guides/watchdog/WATCHDOG_SUMMARY.md`
- **Changelog**: `docs/guides/watchdog/WATCHDOG_CHANGELOG.md`

---

## Need Help?

1. Check `logs/watchdog.log`
2. Read `docs/guides/watchdog/WATCHDOG_GUIDE.md`
3. Run `python tests\integration\test_watchdog.py`
4. Report issues on GitHub

---

**Version**: 1.0.0 | **Updated**: October 7, 2025
