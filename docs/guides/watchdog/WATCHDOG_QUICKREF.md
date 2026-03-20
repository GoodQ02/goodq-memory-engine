# GoodQ Watchdog - Quick Reference Card

> Role: Quick command and operations reference for the Watchdog system. For full explanations, edge cases, and troubleshooting, use `docs/guides/watchdog/WATCHDOG_GUIDE.md` and `docs/guides/watchdog/WATCHDOG_INDEX.md`.

## One-Line Summary
Drop files in the configured import inbox and Watchdog auto-processes them.

---

## Quick Commands

| Task | Command |
|------|---------|
| **Start Watchdog** | `conda run -n goodq_core python -m cli.watchdog` |
| **Check Status** | `python scripts/utils/check_watchdog_status.py` |
| **Live Monitor** | `scripts/monitoring/monitor_live.bat` |
| **Stop Watchdog** | `Ctrl+C` in watchdog window |

---

## Drop Zone

```
<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\
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
<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\
    ↓ (detected in 2s)
    ↓ (stable for 3s)
    ↓ (hash checked)
<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\processing\
    ↓ (pipeline runs)
    ↓
<GOODQ_DATA_ROOT>\GoodQ_Data\processed\  or  <GOODQ_DATA_ROOT>\GoodQ_Data\failed\
```

---

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\` | Drop files here |
| `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\processing\` | Temp during processing |
| `<GOODQ_DATA_ROOT>\GoodQ_Data\processed\` | Successfully processed |
| `<GOODQ_DATA_ROOT>\GoodQ_Data\failed\` | Failed processing |

---

## Logs

| File | Purpose |
|------|---------|
| `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\watchdog.log` | Activity log |
| `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\watchdog_state.json` | Processed files registry |

---

## Common Tasks

### Check if Running
```powershell
Get-Process python | Where-Object {$_.CommandLine -like '*watchdog*'}
```

### View Live Logs
```powershell
Get-Content <GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\watchdog.log -Wait -Tail 20
```

### Check Registry
```powershell
Get-Content <GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\watchdog_state.json | ConvertFrom-Json
```

### Count Files
```powershell
# Inbox
(Get-ChildItem <GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox -File).Count

# Processed
(Get-ChildItem <GOODQ_DATA_ROOT>\GoodQ_Data\processed -File).Count

# Failed
(Get-ChildItem <GOODQ_DATA_ROOT>\GoodQ_Data\failed -File).Count
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
- Check the resolved watchdog log for errors

### Processing Fails
- Check `<GOODQ_DATA_ROOT>\GoodQ_Data\failed\` for file
- Review error in `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\watchdog.log`
- Try manual processing:
  ```batch
  conda run -n goodq_core python -m cli.run_ingestion ingest path\to\file.mp4
  ```

### Already Processed
- File with same content (hash) already exists
- Check `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\watchdog_state.json`
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
- **Don't delete the resolved `watchdog_state.json`** unless resetting the registry
- **Archive processed files** periodically to save space

---

## Full Documentation

- **User Guide**: `docs/guides/watchdog/WATCHDOG_GUIDE.md`
- **Architecture**: `docs/architecture/diagrams/watchdog_flow.md`
- **Historical Summary**: `docs/archive/reports/WATCHDOG_SUMMARY.md`
- **Changelog**: `docs/guides/watchdog/WATCHDOG_CHANGELOG.md`

---

## Need Help?

1. Check `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\watchdog.log`
2. Read `docs/guides/watchdog/WATCHDOG_GUIDE.md`
3. Run `python tests\integration\test_watchdog.py`
4. Report issues on GitHub

---

