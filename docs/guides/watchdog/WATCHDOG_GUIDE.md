# GoodQ Watchdog - Automatic File Ingestion

> Role: This is the primary, canonical user guide for the Watchdog automatic ingestion system. For quick commands, see `docs/WATCHDOG_QUICKREF.md`; for architecture diagrams, see `docs/diagrams/watchdog_flow.md`; for a high-level overview, see `docs/WATCHDOG_SUMMARY.md`. All other Watchdog docs should be read as supporting or historical context.

## Overview

The GoodQ Watchdog is an automatic file monitoring and ingestion system that watches the `import_inbox` folder for new files and automatically processes them through the appropriate pipeline.

## Features

- **Automatic Detection**: Monitors `import_inbox` folder for new files
- **File Type Recognition**: Automatically identifies video, audio, image, and document files
- **Queue Management**: Processes files one at a time to ensure system stability
- **Duplicate Detection**: Uses SHA-256 hashing to prevent reprocessing identical files
- **File Stability Check**: Waits for files to finish copying before processing
- **Error Handling**: Failed files are moved to `data/failed` folder
- **State Persistence**: Maintains registry of processed files across restarts
- **Comprehensive Logging**: All activity logged to `logs/watchdog.log`

## Supported File Types

### Video Files
- `.mp4`, `.avi`, `.mov`, `.mkv`, `.wmv`, `.flv`, `.webm`, `.m4v`

### Audio Files
- `.mp3`, `.wav`, `.flac`, `.m4a`, `.aac`, `.ogg`, `.wma`

### Image Files
- `.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.tiff`, `.webp`

### Document Files
- `.pdf`, `.txt`, `.md`, `.doc`, `.docx`

## Quick Start

### 1. Start the Watchdog

```batch
conda run -n goodq_core python -m cli.watchdog
```

This will:
- Start monitoring `import_inbox`
- Display real-time status

### 2. Add Files for Processing

Simply drag and drop files into:
```
<project_root>\import_inbox\
```

### 3. Monitor Progress

The watchdog will:
- Detect the new file within 2 seconds
- Wait 3 seconds to ensure the file is stable
- Compute file hash and check if already processed
- Add to processing queue
- Process through the appropriate pipeline
- Move to `data/processed` with `PROCESSED_` prefix

## File Flow

```
import_inbox/
    video.mp4              ← Drop file here
         ↓
    [Watchdog detects]
         ↓
    [Check stability - 3s wait]
         ↓
    [Compute SHA-256 hash]
         ↓
    [Check if already processed]
         ↓
data/processing/
    video.mp4              ← Temporary copy during processing
         ↓
    [Run ingestion pipeline]
         ↓
    [Success?]
         ↓
  ┌─────┴─────┐
  │           │
 YES         NO
  │           │
  ↓           ↓
data/processed/  data/failed/
PROCESSED_video.mp4  FAILED_video.mp4
```

## Directory Structure

```
goodq4all/
├── import_inbox/          # Drop files here
├── data/
│   ├── processing/        # Temp files during processing
│   ├── processed/         # Successfully processed files
│   └── failed/            # Failed processing attempts
├── logs/
│   ├── watchdog.log       # Watchdog activity log
│   └── watchdog_state.json # Processed file registry
└── cli/
    └── watchdog.py        # Canonical watchdog implementation
```

## Configuration

Adjust the polling constants in `cli/watchdog.py` to change:

```python
POLL_INTERVAL = 2.0      # How often to scan (seconds)
STABILITY_WAIT = 3.0     # Wait for file to stop changing
MAX_WORKERS = 1          # Number of concurrent processors
```

## Processing Status

### During Processing
Files remain in `import_inbox` with their original name while being processed.

### After Success
- Original file: `import_inbox/video.mp4` → `data/processed/PROCESSED_video.mp4`
- Log entry: Added to `logs/watchdog_state.json`

### After Failure
- Original file: `import_inbox/video.mp4` → `data/failed/FAILED_video.mp4`
- Error logged in `logs/watchdog.log`

## Duplicate Detection

The watchdog uses SHA-256 hashing to detect duplicate files:

1. When a stable file is detected, compute its hash
2. Check `logs/watchdog_state.json` for this hash
3. If found, mark as `PROCESSED_` without re-ingestion
4. If not found, process and add hash to registry

This means:
- Renaming a file doesn't fool the system
- Copying the same video multiple times only processes once
- Different files with same name are processed separately

## Testing

### Test File Classification
```batch
conda run -n goodq_core python tests\integration\test_watchdog.py
```

This tests:
- File type detection
- Directory scanning
- Processed file registry
- File stability checks

## Monitoring

### View Live Logs
```powershell
Get-Content <project_root>\logs\watchdog.log -Wait -Tail 20
```

### Check Processed Files
```powershell
Get-Content <project_root>\logs\watchdog_state.json | ConvertFrom-Json
```

### View Queue Status
The watchdog console shows:
- Files detected
- Stability checks
- Queue additions
- Processing status
- Success/failure results

## Integration with LAUNCH_GOODQ

The watchdog is **not** included in `LAUNCH_GOODQ.bat` by default to avoid automatic processing of all inbox files on every startup.

To add it to the launch sequence, edit `LAUNCH_GOODQ.bat`:

```batch
REM Add before "Press any key to close"
start "GoodQ Watchdog" /MIN cmd /k "conda run -n goodq_core python -m cli.watchdog"
```

## Troubleshooting

### Watchdog Not Detecting Files

1. Check watch directory exists:
   ```powershell
   Test-Path <project_root>\import_inbox
   ```

2. Verify file type is supported (check extensions)

3. Check logs:
   ```powershell
   Get-Content <project_root>\logs\watchdog.log -Tail 50
   ```

### Files Not Processing

1. Check if already processed:
   ```powershell
   Get-Content <project_root>\logs\watchdog_state.json | ConvertFrom-Json
   ```

2. Check for errors in log

3. Try moving file out and back in

### Processing Fails

1. Check `data/failed/` for the failed file
2. Review `logs/watchdog.log` for error details
3. Check environment is activated
4. Verify ingestion pipeline works manually:
   ```batch
   conda activate goodq_core
   python cli\run_ingestion.py ingest path\to\video.mp4
   ```

## Best Practices

1. **Start watchdog before dropping files** to ensure immediate detection
2. **Use stable file copies** - wait for large files to finish copying
3. **Monitor logs** during initial testing
4. **Check processed registry** to avoid duplicates
5. **Clean up processed/failed directories** periodically
6. **Don't delete watchdog_state.json** unless intentionally resetting

## Performance Notes

- Processes one file at a time to ensure GPU/memory stability
- 2-second polling is lightweight and responsive
- 3-second stability wait prevents incomplete file processing
- File hashing is fast even for large files (streaming computation)
- Queue system prevents file loss during high-volume drops

## Future Enhancements

- [ ] Multi-file parallel processing (configurable workers)
- [ ] Priority queue based on file type/size
- [ ] Web interface for queue management
- [ ] Email notifications on completion
- [ ] Batch file upload API
- [ ] Cloud storage integration (S3, Drive, etc.)
- [ ] Mobile app for remote monitoring

## Advanced Usage

### Manual Queue Management

Start Python REPL in the environment:
```python
from cli.watchdog import WatchdogProcessor

watchdog = WatchdogProcessor()

# Check queue
print(f"Queue size: {watchdog.queue.qsize()}")

# View processed files
for hash_val, info in watchdog.registry.processed.items():
    print(f"{info['original_name']}: {info['status']}")
```

### Custom Processing Pipelines

Extend `cli/watchdog.py` to customize ingestion methods:

```python
def ingest_video(self, video_path: Path) -> bool:
    # Add custom preprocessing
    # Call custom pipeline
    # Add custom postprocessing
    pass
```

### Integration with External Systems

The watchdog can be extended to:
- Trigger webhooks on completion
- Update external databases
- Send notifications
- Generate reports
- Archive to cloud storage

## Security Notes

- Watchdog runs with user permissions
- No network access required
- Files never leave local system
- State file is plain JSON (human-readable)
- Logs contain no sensitive data
- Failed files preserved for debugging

---

**Need Help?** Check `logs/watchdog.log` for detailed activity logs.

**Want to Contribute?** See `CONTRIBUTING.md` for development guidelines.
