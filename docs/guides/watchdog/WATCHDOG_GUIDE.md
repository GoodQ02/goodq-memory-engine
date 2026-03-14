# GoodQ Watchdog - Automatic File Ingestion

> Role: This is the primary, canonical user guide for the Watchdog automatic ingestion system. For quick commands, see `docs/guides/watchdog/WATCHDOG_QUICKREF.md`; for architecture diagrams, see `docs/architecture/diagrams/watchdog_flow.md`; for a high-level overview, see `docs/guides/watchdog/WATCHDOG_SUMMARY.md`. All other Watchdog docs should be read as supporting or historical context.

## Overview

The GoodQ Watchdog is an automatic file monitoring and ingestion system that watches the configured import inbox and automatically processes new files through the appropriate pipeline. Runtime paths are resolved from the active config and local overrides, not fixed to repo-root directories.

## Features

- **Automatic Detection**: Monitors `<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox` for new files
- **File Type Recognition**: Automatically identifies video, audio, image, and document files
- **Queue Management**: Processes files one at a time to ensure system stability
- **Duplicate Detection**: Uses SHA-256 hashing to prevent reprocessing identical files
- **File Stability Check**: Waits for files to finish copying before processing
- **Error Handling**: Failed files are moved to the configured failed directory
- **State Persistence**: Maintains registry of processed files across restarts
- **Comprehensive Logging**: Activity logged under `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\`
- **Control-Plane Visibility**: Records Control Agent state every run; AI diagnosis remains optional

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
- Start monitoring the resolved import inbox
- Display real-time status

### 2. Add Files for Processing

Simply drag and drop files into:
```
<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\
```

### 3. Monitor Progress

The watchdog will:
- Detect the new file within 2 seconds
- Wait 3 seconds to ensure the file is stable
- Compute file hash and check if already processed
- Add to processing queue
- Process through the appropriate pipeline
- Move to the resolved processed directory with `PROCESSED_` prefix

## File Flow

```
<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\
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
<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\processing\
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
<GOODQ_DATA_ROOT>\GoodQ_Data\processed\  <GOODQ_DATA_ROOT>\GoodQ_Data\failed\
PROCESSED_video.mp4  FAILED_video.mp4
```

## Directory Structure

```
<GOODQ_DATA_ROOT>\GoodQ_Data\
├── import_inbox\                          # Drop files here
├── processed\                             # Successfully processed files
├── failed\                                # Failed processing attempts
└── epochs\<epoch>\
    ├── processing\                        # Temp files during processing
    └── logs\
        ├── watchdog.log                   # Watchdog activity log
        └── watchdog_state.json            # Processed file registry
```

## Configuration

`cli/watchdog.py` resolves directories through `load_configs()` + `get_runtime_paths()`. The inbox, processing, processed, failed, lock, and log locations come from the active config. Adjust the polling constants below only if you need to change runtime behavior:

```python
POLL_INTERVAL = 2.0      # How often to scan (seconds)
STABILITY_WAIT = 3.0     # Wait for file to stop changing
MAX_WORKERS = 1          # Number of concurrent processors
```

## Processing Status

### During Processing
Files remain in `<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox` with their original name while being processed.

### After Success
- Original file: `<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\video.mp4` → `<GOODQ_DATA_ROOT>\GoodQ_Data\processed\PROCESSED_video.mp4`
- Log entry: Added to `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\watchdog_state.json`

### After Failure
- Original file: `<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\video.mp4` → `<GOODQ_DATA_ROOT>\GoodQ_Data\failed\FAILED_video.mp4`
- Error logged in `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\watchdog.log`

## Duplicate Detection

The watchdog uses SHA-256 hashing to detect duplicate files:

1. When a stable file is detected, compute its hash
2. Check `watchdog_state.json` in the resolved `log_dir` for this hash
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
Get-Content <GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\watchdog.log -Wait -Tail 20
```

### Check Processed Files
```powershell
Get-Content <GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\watchdog_state.json | ConvertFrom-Json
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
   Test-Path <GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox
   ```

2. Verify file type is supported (check extensions)

3. Check logs:
   ```powershell
   Get-Content <GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\watchdog.log -Tail 50
   ```

### Files Not Processing

1. Check if already processed:
   ```powershell
   Get-Content <GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\watchdog_state.json | ConvertFrom-Json
   ```

2. Check for errors in log

3. Try moving file out and back in

### Processing Fails

1. Check `<GOODQ_DATA_ROOT>\GoodQ_Data\failed\` for the failed file
2. Review `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\watchdog.log` for error details
3. Check the `goodq_core` environment is available
4. Verify ingestion pipeline works manually:
   ```batch
   conda run -n goodq_core python -m cli.run_ingestion ingest path\to\video.mp4
   ```

## Best Practices

1. **Start watchdog before dropping files** to ensure immediate detection
2. **Use stable file copies** - wait for large files to finish copying
3. **Monitor logs** during initial testing
4. **Check processed registry** to avoid duplicates
5. **Clean up processed/failed directories** periodically
6. **Don't delete the resolved `watchdog_state.json`** unless intentionally resetting

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
from steps.common.config_loader import load_configs

cfg = load_configs({})
watchdog = WatchdogProcessor(cfg)

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

**Need Help?** Check `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\watchdog.log` for detailed activity logs.

**Want to Contribute?** See `CONTRIBUTING.md` for development guidelines.
