# GoodQ Watchdog Flow Diagram

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERACTION                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Drag & Drop Files
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      import_inbox/                               │
│  • video.mp4  • audio.mp3  • image.jpg  • document.pdf          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Monitor (2s poll)
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    WATCHDOG MONITOR THREAD                       │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 1. Scan directory for new files                          │  │
│  │ 2. Check file extension → determine type                 │  │
│  │ 3. Create FileState tracker                              │  │
│  │ 4. Monitor for stability (3s no changes)                 │  │
│  │ 5. Compute SHA-256 hash                                  │  │
│  │ 6. Check processed registry                              │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
             Known?                      Unknown?
                │                           │
                ↓                           ↓
        ┌──────────────┐          ┌────────────────┐
        │ Skip & Mark  │          │ Add to Queue   │
        │  PROCESSED   │          │                │
        └──────────────┘          └────────────────┘
                                          │
                                          ↓
┌─────────────────────────────────────────────────────────────────┐
│                    PROCESSING QUEUE                              │
│  ┌────────┐  ┌────────┐  ┌────────┐                             │
│  │ File 1 │→ │ File 2 │→ │ File 3 │→ ...                        │
│  └────────┘  └────────┘  └────────┘                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Dequeue
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    WORKER THREAD                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 1. Copy file to data/processing/                         │  │
│  │ 2. Determine pipeline (video/audio/image/document)       │  │
│  │ 3. Execute ingestion                                     │  │
│  │ 4. Monitor progress                                      │  │
│  │ 5. Capture result                                        │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
            SUCCESS?                     FAILURE?
                │                           │
                ↓                           ↓
┌───────────────────────────┐   ┌───────────────────────────┐
│   data/processed/         │   │     data/failed/          │
│  PROCESSED_video.mp4      │   │   FAILED_video.mp4        │
└───────────────────────────┘   └───────────────────────────┘
                │                           │
                └─────────────┬─────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              PROCESSED FILE REGISTRY                             │
│  logs/watchdog_state.json                                        │
│  {                                                               │
│    "abc123...": {                                                │
│      "original_name": "video.mp4",                               │
│      "status": "success",                                        │
│      "timestamp": "2025-10-07T22:00:00"                          │
│    }                                                             │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

## File Lifecycle

```
┌───────────┐
│  NEW FILE │
│  DETECTED │
└─────┬─────┘
      │
      ↓
┌─────────────┐     ┌──────────┐
│  Stability  │────→│  Stable? │
│   Check     │     └────┬─────┘
└─────────────┘          │
      ↑                  │ Yes
      │ No (wait 1s)     ↓
      └──────────┌───────────┐
                 │ Compute   │
                 │   Hash    │
                 └─────┬─────┘
                       │
                       ↓
                 ┌───────────┐
                 │ Already   │──Yes──→ Skip
                 │Processed? │
                 └─────┬─────┘
                       │ No
                       ↓
                 ┌───────────┐
                 │   Copy    │
                 │    to     │
                 │Processing │
                 └─────┬─────┘
                       │
                       ↓
                 ┌───────────┐
                 │  Execute  │
                 │ Pipeline  │
                 └─────┬─────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
      Success                     Failure
         │                           │
         ↓                           ↓
┌────────────────┐          ┌────────────────┐
│ Move to        │          │ Move to        │
│ processed/     │          │ failed/        │
│ PROCESSED_*    │          │ FAILED_*       │
└────────┬───────┘          └────────┬───────┘
         │                           │
         └───────────┬───────────────┘
                     │
                     ↓
              ┌─────────────┐
              │ Update      │
              │ Registry    │
              └─────────────┘
```

## State Machine

```
                    ┌─────────┐
                    │ UNKNOWN │
                    └────┬────┘
                         │ File appears
                         ↓
                    ┌─────────┐
                ┌───│ PENDING │
                │   └────┬────┘
    Size/time   │        │ Stable for 3s
    changed     │        ↓
                │   ┌─────────┐
                └───│ STABLE  │
                    └────┬────┘
                         │ Hash computed
                         ↓
                    ┌─────────┐
                ┌───│ HASHED  │
                │   └────┬────┘
    Already     │        │ Check registry
    processed   │        ↓
                │   ┌─────────┐
                │   │ QUEUED  │
                │   └────┬────┘
                │        │ Worker picks up
                │        ↓
                │   ┌─────────┐
                │   │PROCESSING│
                │   └────┬────┘
                │        │
                │  ┌─────┴─────┐
                │  │           │
                │Success     Failure
                │  │           │
                ↓  ↓           ↓
           ┌─────────┐   ┌─────────┐
           │PROCESSED│   │ FAILED  │
           └─────────┘   └─────────┘
```

## Component Interaction

```
┌────────────────────────────────────────────────────────────────┐
│                    WATCHDOG PROCESS                             │
│                                                                 │
│  ┌──────────────┐         ┌──────────────┐                     │
│  │   Monitor    │         │    Worker    │                     │
│  │   Thread     │────────→│   Thread     │                     │
│  │              │  Queue  │              │                     │
│  └──────┬───────┘         └──────┬───────┘                     │
│         │                        │                             │
│         │ Scans                  │ Processes                   │
│         ↓                        ↓                             │
│  ┌──────────────┐         ┌──────────────┐                     │
│  │  FileState   │         │  Ingestion   │                     │
│  │  Tracker     │         │  Pipeline    │                     │
│  └──────────────┘         └──────────────┘                     │
│         │                        │                             │
│         └────────┬───────────────┘                             │
│                  │                                             │
│                  ↓                                             │
│         ┌──────────────────┐                                   │
│         │ Processed        │                                   │
│         │ Registry         │                                   │
│         │ (JSON file)      │                                   │
│         └──────────────────┘                                   │
└────────────────────────────────────────────────────────────────┘
```

## Threading Model

```
Main Thread
    │
    ├── Monitor Thread (daemon)
    │   │
    │   └── while not shutdown:
    │           scan_directory()
    │           check_stability()
    │           queue.put()
    │           sleep(2s)
    │
    ├── Worker Thread 1 (daemon)
    │   │
    │   └── while not shutdown:
    │           file = queue.get()
    │           process_file()
    │           queue.task_done()
    │
    ├── Worker Thread 2 (daemon)
    │   │
    │   └── (future expansion)
    │
    └── while True:
            wait_for_signal()
            on Ctrl+C:
                shutdown.set()
                queue.join()
                threads.join()
```

## File Type Decision Tree

```
                    ┌─────────┐
                    │  File   │
                    └────┬────┘
                         │
            ┌────────────┴────────────┐
            │                         │
        Extension?              Check bytes
            │                    (future)
    ┌───────┴───────┐
    │               │
.mp4, .avi, ...  .mp3, .wav, ...
    │               │
    ↓               ↓
┌─────────┐   ┌─────────┐
│  VIDEO  │   │  AUDIO  │
│Pipeline │   │Pipeline │
└─────────┘   └─────────┘

    │               │
.jpg, .png, ...  .pdf, .txt, ...
    │               │
    ↓               ↓
┌─────────┐   ┌──────────┐
│  IMAGE  │   │ DOCUMENT │
│Pipeline │   │ Pipeline │
└─────────┘   └──────────┘
```

## Error Handling Flow

```
┌──────────────┐
│ Process File │
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ Try: Copy    │──Exception──→ Log & Mark Failed
└──────┬───────┘
       │ OK
       ↓
┌──────────────┐
│ Try: Ingest  │──Exception──→ Log & Mark Failed
└──────┬───────┘              Move to failed/
       │ OK
       ↓
┌──────────────┐
│ Try: Move    │──Exception──→ Log but Continue
│  to processed│              (file processed OK)
└──────┬───────┘
       │ OK
       ↓
┌──────────────┐
│ Update       │──Exception──→ Log Warning
│ Registry     │              (will retry next run)
└──────────────┘
```

---

For implementation details, see `cli/watchdog.py`

For usage guide, see `docs/guides/watchdog/WATCHDOG_GUIDE.md`
