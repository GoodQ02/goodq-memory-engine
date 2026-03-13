# GoodQ4All Process Management - Quick Reference Card
> Historical quick reference — covers an older process-management stack that is not part of the canonical supported runtime. References to `api_server.py` and legacy batch launchers are preserved for context only.

## 🚀 Quick Start

```batch
# Test everything works
TEST_PROCESS_MANAGER.bat

# Start system
START_GOODQ_SYSTEM.bat

# Open browser
http://localhost:30000

# Stop system  
STOP_GOODQ_SYSTEM.bat
```

## 📋 Common Commands

### Batch Scripts (Easiest)
```batch
START_GOODQ_SYSTEM.bat    # Start all services
STOP_GOODQ_SYSTEM.bat     # Stop all services
STATUS_CHECK.bat          # Check what's running
TEST_PROCESS_MANAGER.bat  # Run system tests
```

### Python CLI (More Control)
```bash
# Status
python process_manager.py status

# Start a process
python process_manager.py start api_server
python process_manager.py start watchdog

# Stop a process
python process_manager.py stop watchdog

# Restart a process
python process_manager.py restart api_server

# View logs
python process_manager.py logs api_server --lines 50

# Stop everything
python process_manager.py stop-all
```

### Web UI (Visual)
1. Start system: `START_GOODQ_SYSTEM.bat`
2. Open: http://localhost:30000
3. Click: **⚙️ Process Control**
4. Use buttons to control processes

## 🎯 Process Overview

| Process | What it does | When to start |
|---------|--------------|---------------|
| **api_server** | Web interface & API | Always (required for UI) |
| **watchdog** | Auto-process new files | When ready to ingest videos |
| **analytics** | Analytics dashboard | Optional (for insights) |

## 🔧 Troubleshooting

### Process won't start
```bash
# View the error
python process_manager.py logs api_server

# Check if port 30000 is in use
netstat -ano | findstr :30000

# Reset everything
STOP_GOODQ_SYSTEM.bat
del <project_root>\logs\process_state.json
del <project_root>\logs\pids\*.pid
START_GOODQ_SYSTEM.bat
```

### Process shows "running" but isn't
```bash
# Clean up stale state
del <project_root>\logs\process_state.json
del <project_root>\logs\pids\*.pid

# Check actual status
python process_manager.py status
```

### Can't access web UI
```bash
# Make sure API server is running
python process_manager.py status

# If stopped, start it
python process_manager.py start api_server

# Wait 5 seconds, then try
http://localhost:30000
```

## 📁 Important Files

```
<project_root>\
├── process_manager.py              # Core process manager
├── START_GOODQ_SYSTEM.bat         # Quick start
├── STOP_GOODQ_SYSTEM.bat          # Quick stop
├── STATUS_CHECK.bat               # Quick status
├── TEST_PROCESS_MANAGER.bat       # Run tests
├── logs/
│   ├── process_manager.log        # Manager log
│   ├── api_server_*.log           # API logs
│   ├── watchdog_*.log             # Watchdog logs
│   ├── process_state.json         # Current state
│   └── pids/                      # Process IDs
└── PROCESS_MANAGEMENT_GUIDE.md    # Full documentation
```

## 🌐 Web UI Navigation

After starting system (http://localhost:30000):

- **💬 Chat** - Talk to GoodQ assistant
- **🎬 Scene Explorer** - Browse processed scenes  
- **🔍 Search** - Find specific content
- **📊 Analytics** - View insights
- **🧠 Knowledge Graph** - Explore connections
- **💭 Memories** - Browse your memories
- **🔴 Command Center** - System monitoring
- **⚙️ Process Control** - Manage processes (NEW!)

## 💡 Pro Tips

### Tip 1: Daily Workflow
```batch
# Morning
START_GOODQ_SYSTEM.bat

# Work in browser all day
http://localhost:30000

# Evening
STOP_GOODQ_SYSTEM.bat
```

### Tip 2: Development Mode
```bash
# Keep API running, stop watchdog to prevent auto-processing
python process_manager.py start api_server
python process_manager.py stop watchdog
```

### Tip 3: Monitoring
```bash
# Keep Command Center open while processing
http://localhost:30000 → Click "🔴 Command Center"

# Real-time log viewing
http://localhost:30000 → Click "⚙️ Process Control" → Click "Logs"
```

### Tip 4: Quick Health Check
```batch
# One command to see everything
STATUS_CHECK.bat
```

## 🆘 Get Help

1. **Read the docs**: `PROCESS_MANAGEMENT_GUIDE.md`
2. **Check logs**: `logs/process_manager.log`
3. **View process logs**: `python process_manager.py logs <process>`
4. **Test system**: `TEST_PROCESS_MANAGER.bat`
5. **Reset state**: Delete `logs/process_state.json` and `logs/pids/`

## ✅ Verification Checklist

After starting system:

- [ ] Status check shows processes running
- [ ] Can access http://localhost:30000
- [ ] Process Control view loads
- [ ] Can view logs in UI
- [ ] Command Center shows live data

## 📞 Quick Reference URLs

- Main UI: http://localhost:30000
- API Docs: http://localhost:30000/docs
- Process Status: http://localhost:30000/api/processes
- Command Center: http://localhost:30000/api/command-center

---

**Version**: 1.0.0  
**Last Updated**: 2025-11-09

*Print this card and keep it handy!*
