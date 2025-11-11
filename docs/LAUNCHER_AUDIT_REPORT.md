# GoodQ4All Launcher Audit Report
**Date:** 2025-11-09  
**Issue:** Multiple watchdog instances causing file access conflicts

---

## Executive Summary

✅ **ROOT CAUSE IDENTIFIED:** Multiple watchdog instances starting simultaneously  
✅ **SOLUTION:** Single source of truth launcher system  
✅ **ISSUE:** Duplicate processes causing `[WinError 32]` file locks

---

## Current Launcher Files

### Primary Launchers (Root Directory)
1. **LAUNCH_GOODQ_SYSTEM.bat** (Most Recent: 2025-11-09 11:45:20)
   - ✅ Interactive menu with 7 options
   - ✅ Launches API + Watchdog + UI
   - ✅ Uses `conda run --no-capture-output`
   - ✅ Proper error checking
   - **RECOMMENDED PRIMARY LAUNCHER**

2. **LAUNCH_GOODQ_PRODUCTION.bat** (2025-11-09 03:21:41)
   - ⚠️ Auto-starts both API and Watchdog in minimized windows
   - ⚠️ Uses `conda activate` (older method)
   - ⚠️ Less control, more prone to duplicate processes
   - **SHOULD BE ARCHIVED**

3. **ANALYTICS_LAUNCHER.bat** (2025-11-08 11:38:50)
   - ✅ Separate analytics tool launcher
   - ✅ Does NOT interfere with main system
   - **KEEP AS-IS**

### Test/Diagnostic Launchers (Should Stay in /tests or /scripts)
- `TEST_PROGRESS_TRACKING.bat` → Keep in tests/
- `VALIDATE_PYTHON_PATHS.bat` → Keep as utility
- Various test scripts in scripts/ folder → Keep organized

---

## Current Problem: Duplicate Watchdog Processes

### Evidence from logs (watchdog.log):
```
2025-11-09 23:02:07,205 [INFO] New file detected: 01. 1987 - 1988.mp4
2025-11-09 23:02:09,072 [INFO] New file detected: 01. 1987 - 1988.mp4
                                ^^^ DUPLICATE DETECTION

2025-11-09 23:02:20,241 [INFO] Processing video: 01. 1987 - 1988.mp4
2025-11-09 23:02:22,300 [INFO] Processing video: 01. 1987 - 1988.mp4
                                ^^^ BOTH TRYING TO PROCESS

2025-11-09 23:02:26,148 [ERROR] Failed to copy video to temp dir: 
[WinError 32] The process cannot access the file because it is 
being used by another process
```

**This happens when:**
- User launches `LAUNCH_GOODQ_PRODUCTION.bat` which starts watchdog
- User also launches `LAUNCH_GOODQ_SYSTEM.bat` → Option 3 (watchdog only)
- OR UI "Start Processing" button tries to start watchdog when it's already running

---

## Recommended Single Source of Truth Structure

### 1. Master Launcher: `LAUNCH_GOODQ_SYSTEM.bat`
**Purpose:** Main entry point for all users  
**Location:** `L:\goodq4all\`  
**Features:**
- Interactive menu
- Process checking (prevents duplicates)
- Status monitoring
- Diagnostics

### 2. Component Scripts (Internal Use Only)
**Location:** `L:\goodq4all\scripts\`  
These should ONLY be called by the master launcher or process_manager:
- `watchdog_ingest.py` - Auto-ingestion worker
- `api_server.py` - API backend (keep in root for clarity)
- `process_manager.py` - Process orchestration

### 3. Utilities (Keep Separate)
**Location:** `L:\goodq4all\` or `L:\goodq4all\scripts\`
- `ANALYTICS_LAUNCHER.bat` - Analytics tools
- `VALIDATE_PYTHON_PATHS.bat` - System validation
- `diagnose_system.py` - Health checks

### 4. Archive Candidates → Move to `L:\_ARCHIVE\`
- `LAUNCH_GOODQ_PRODUCTION.bat` - Replaced by SYSTEM launcher
- Any old START_*.bat variants
- Deprecated test scripts

---

## Action Items

### Immediate Fixes Needed:

1. **Add Process Locking to Watchdog**
   - Use PID file or mutex to prevent duplicate instances
   - Check if watchdog is already running before starting

2. **Update LAUNCH_GOODQ_SYSTEM.bat**
   - Add process detection before launching
   - Warn user if services already running
   - Offer to kill existing processes before starting new ones

3. **Fix UI "Start Processing" Button**
   - Should check if watchdog is running first
   - If running: show "Already running" status
   - If not running: start watchdog via API call to process_manager

4. **Archive Redundant Launchers**
   - Move `LAUNCH_GOODQ_PRODUCTION.bat` to archive
   - Document why it was deprecated

5. **Create Process Manager Integration**
   - UI should use process_manager.py to start/stop services
   - process_manager should enforce single instances
   - Add status endpoints to API

---

## Correct Launch Sequence

### For Users:
1. Run `LAUNCH_GOODQ_SYSTEM.bat`
2. Choose Option 1 (Complete System)
3. Wait for all 3 services to start
4. Access UI at http://localhost:3000

### For Developers/Testing:
1. Run individual components via menu options
2. Use `process_manager.py` for programmatic control
3. Use diagnostic options for troubleshooting

### Current State Check:
```bash
# No processes running on port 3000
# Watchdog last ran at 23:02:26 and crashed
# Need clean restart with proper process management
```

---

## Next Steps

1. ✅ Identify issue (DONE)
2. 🔧 Add watchdog process locking (NEXT)
3. 🔧 Update launcher with process checking (NEXT)
4. 🔧 Wire UI buttons to process_manager (NEXT)
5. 🧪 Test clean start/stop/restart cycle
6. 📦 Archive deprecated launchers
7. 📝 Update user documentation

---

## Summary

**Problem:** Multiple watchdog processes fighting over the same file  
**Root Cause:** No process locking, multiple launcher entry points  
**Solution:** Single launcher + process locking + process_manager integration  
**Status:** Ready to implement fixes

