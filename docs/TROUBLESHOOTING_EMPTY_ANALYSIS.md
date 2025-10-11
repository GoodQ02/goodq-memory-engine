# Troubleshooting: Empty Analysis Fields (No Tags, Captions, Transcripts)

## Problem Description

After ingesting videos, the database shows scenes and embeddings, but all AI analysis fields are empty:
- No tags
- No captions
- No object detections
- No transcripts
- No sentiment analysis
- No emotion classification

**Symptoms:**
```json
{
  "tags": null,
  "caption": null,
  "ocr_text": null,
  "transcript": null,
  "sentiment": null,
  "emotions": null
}
```

## Root Cause

The GoodQ pipeline has a **dedupe/caching system** that prevents reprocessing of scenes that already exist in the database. The system checks if a scene has a `keyframe` hash and `audio` hash in the database - if they exist, it skips ALL processing steps.

### What Happened

1. **Initial ingestion** extracted frames and audio files from videos
2. **Scene metadata was saved** to the database with file hashes
3. **AI models were NOT run** (possibly due to an error, timeout, or incomplete processing)
4. **Database now contains** skeleton scenes with hashes but no analysis data
5. **Subsequent ingestions skip** these scenes because they "already exist" (dedupe)

### Evidence

Looking at the step logs shows ALL steps being skipped:
```
10/11/25 13:43:33 [goodq_zenml] audio_transcribe 0ms skipped scene_0000.wav
10/11/25 13:43:33 [goodq_zenml] sentiment 0ms skipped scene_0000.wav
10/11/25 13:43:33 [goodq_zenml] image_caption 0ms skipped scene_0000.jpg
```

Database query shows scenes exist but have no enrichment:
```sql
SELECT * FROM scenes WHERE id='...';
-- Result: scene exists with null tags, null caption, null transcript, etc.
```

## Solution

### Option 1: Force Reprocessing (Recommended)

The `--force` flag has been added to bypass dedupe and reprocess all scenes:

```bash
# Stop any running watchdog first
# Then restart with force reprocessing enabled
START_WATCHDOG.bat
```

The watchdog now automatically includes `--force` to ensure complete analysis.

**Manual ingestion with force:**
```bash
conda activate goodq_zenml
python -m goodq4all.cli.run_ingestion --input-dir L:\goodq4all\import_inbox --force --verbose
```

### Option 2: Clear Database and Start Fresh

If you want to completely start over:

```bash
# Run the provided cleanup script
CLEAR_AND_REINGEST.bat
```

This will:
1. Backup existing databases
2. Clear all memory databases
3. Clear FAISS indexes  
4. Clear step logs
5. Restart ingestion for fresh processing

**Manual cleanup:**
```powershell
# Backup first
copy L:\goodq4all\data\memory.db L:\goodq4all\data\memory.db.backup

# Clear databases
del L:\goodq4all\data\memory.db
del L:\_DATA\GoodQ_Data\data\memory_db\memory.db
del L:\goodq4all\data\faiss\*
del L:\goodq4all\logs\steps.jsonl

# Then re-ingest
START_WATCHDOG.bat
```

## Prevention

To prevent this issue in the future:

1. **Always use `--force` flag** during development/testing
2. **Monitor step logs** to ensure processing completes:
   ```powershell
   Get-Content L:\goodq4all\logs\steps.jsonl -Tail 20
   ```
3. **Check for "ok" status**, not "skipped":
   ```
   2025-10-11T01:12:46 [goodq_audio_transcribe] audio_transcribe 8278ms ok scene_0006.wav
   ```
4. **Use Command Center** to verify enrichment is happening:
   ```powershell
   L:\goodq4all\scripts\command_center.ps1
   ```

## Technical Details

### Dedupe Logic Location

File: `goodq4all/cli/run_ingestion.py`
```python
# Lines 738-741 (now respects force_reprocess flag)
force = cfg.get('force_reprocess', False)
skip_frame = bool(materialized.get('keyframe')) if isinstance(materialized, dict) and not force else False
skip_audio = bool(materialized.get('audio')) if isinstance(materialized, dict) and not force else False
```

### Materialization Check

File: `goodq4all/steps/common/memory.py`
```python
def scene_has_materialized(cfg, scene_id, components=['keyframe', 'audio']):
    # Returns True if scene has hashes for requested components
    # This triggers skip logic unless --force is used
```

### Watchdog Configuration

File: `goodq4all/scripts/watchdog_ingest.py`
```python
cmd = [
    'conda', 'run', '-n', 'goodq_zenml',
    'python', '-m', 'goodq4all.cli.run_ingestion',
    '--force',  # Now included by default
    '--verbose'
]
```

## Verification

After reprocessing with `--force`, verify the data is populated:

### Check Database
```python
import sqlite3
conn = sqlite3.connect('L:/goodq4all/data/memory.db')
cursor = conn.cursor()

# Check scene metadata
scene = cursor.execute('SELECT meta FROM scenes LIMIT 1').fetchone()
import json
meta = json.loads(scene[0])

# These should now have data (not null):
print("Caption:", meta['keyframe']['caption'])
print("Tags:", meta['keyframe']['tags'])
print("Objects:", meta['keyframe']['objects'])
print("Transcript:", meta['audio']['transcript'])
print("Sentiment:", meta['audio']['sentiment'])
```

### Check Step Logs
```bash
# Should see "ok" status with processing times
grep "ok," L:\goodq4all\logs\steps.jsonl | tail -20
```

### Check Command Center
```powershell
# Run command center - should show populated fields
L:\goodq4all\scripts\command_center.ps1
```

## Related Files

- `goodq4all/cli/run_ingestion.py` - Main ingestion logic with --force flag
- `goodq4all/scripts/watchdog_ingest.py` - Automatic file monitor (now uses --force)
- `goodq4all/steps/common/memory.py` - Database operations and materialization checks
- `CLEAR_AND_REINGEST.bat` - Cleanup and fresh start script

## Commit History

- **2025-10-11**: Added `--force` flag to bypass dedupe (commit 583e3b3)
- **2025-10-11**: Enabled `--force` by default in watchdog
- **2025-10-11**: Created troubleshooting documentation
