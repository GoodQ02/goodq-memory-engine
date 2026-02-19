# goodq4all Quick Reference Card
**Version**: 1.4.0 | **Status**: Production Ready | **Location**: `<project_root>\`

---

## 🚀 One-Line Launchers

```bash
# Launch everything (API + Command Center + Docs)
<project_root>\LAUNCH_GOODQ.bat

# Start watchdog (auto-ingestion)
<project_root>\START_WATCHDOG.bat

# Stop all services
<project_root>\STOP_GOODQ.bat
```

---

## 📂 Key Directories

| Location | Purpose |
|----------|---------|
| `<project_root>\` | Main codebase (GitHub synced) |
| `<GOODQ_DATA_ROOT>\GoodQ_Data\` | Databases & exports |
| `<project_root>\_WORKSPACE\` | Processing workspace |
| `<GOODQ_DATA_ROOT>\models (See LEGACY_PATHS_DEPRECATED.md)\` | HuggingFace cache |
| `<project_root>\tools\` | External tools |
| `<GOODQ_DATA_ROOT>\archive\` | Old versions |

---

## 🎬 Quick Commands

### Ingestion
```bash
# Manual ingestion
conda run -n goodq_core python -m goodq4all.cli.run_ingestion <video_path>

# Auto-ingestion (drop files in)
# → <project_root>\import_inbox\
```

### Health Checks
```bash
# Full system check
conda run -n goodq_core python scripts\system_readiness_check.py

# Quick health
conda run -n goodq_core python scripts\quick_health_check.py

# Production status
conda run -n goodq_core python scripts\check_production_status.py
```

### Memory/Database
```bash
# Diagnostics
conda run -n goodq_core python -m goodq4all.cli.memory diagnostics

# List scenes
conda run -n goodq_core python -m goodq4all.cli.memory list-scenes

# Clear (DESTRUCTIVE!)
conda run -n goodq_core python scripts\clear_databases.py
```

### Monitoring
```bash
# Command center dashboard
cd <project_root> && pwsh scripts\command_center.ps1

# Watch logs
Get-Content <GOODQ_DATA_ROOT>\GoodQ_Data\logs\step_runs.jsonl -Tail 20 -Wait

# Watchdog status
pwsh scripts\watchdog_status.ps1 -Follow
```

---

## 🌐 Web Interfaces

- **API Docs**: http://localhost:30000/docs
- **API Server**: http://localhost:30000
- **Retrieve**: http://localhost:30000/retrieve?q=your+query

---

## 📊 Status Indicators

| Color | Meaning |
|-------|---------|
| 🟢 GREEN | Fully operational |
| 🟡 YELLOW | Working, minor warnings |
| 🔴 RED | Needs attention |

---

## 🛠️ Common Tasks

### Drop & Process Video
1. Ensure watchdog is running: `START_WATCHDOG.bat`
2. Drop video in: `<project_root>\import_inbox\`
3. Monitor: `pwsh scripts\watchdog_status.ps1 -Follow`

### Manual Processing
1. Place video anywhere
2. Run: `conda run -n goodq_core python -m goodq4all.cli.run_ingestion <path>`
3. Watch Command Center for progress

### Check What's Processed
```bash
conda run -n goodq_core python scripts\check_production_status.py
```

### Search Memories
```bash
# Via CLI
conda run -n goodq_core python -m goodq4all.cli.retrieve "dancing"

# Via API (when running)
curl "http://localhost:30000/retrieve?q=dancing"
```

---

## 🔧 Troubleshooting

### Import Errors
```bash
# Test imports
conda run -n goodq_core python scripts\test_all_imports.py
```

### Path Issues
```bash
# Verify paths
conda run -n goodq_core python scripts\test_paths_config.py
```

### Environment Issues
```bash
# Rebuild if needed (takes ~30 min)
pwsh scripts\prepare_step_envs.ps1
```

### Database Corruption
```bash
# Backup first!
conda run -n goodq_core python -m goodq4all.cli.memory backup

# Then clear if needed
conda run -n goodq_core python scripts\clear_databases.py
```

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| `README.md` | Project overview |
| `docs/QUICK_START.md` | 5-min setup |
| `docs/DOCUMENTATION_INDEX.md` | Full doc listing |
| `PROJECT_STATUS.md` | Current status |
| `RENAME_SUCCESS_SUMMARY.md` | Recent changes |

---

## 🎯 Project Stats

- **Environments**: 22 isolated conda envs
- **Models**: Locked with commit hashes
- **Datasets**: 60+ cached datasets
- **GPU**: CUDA 12.1 support
- **Storage**: Centralized in <GOODQ_DATA_ROOT>\

---

## ⚡ Performance Tips

1. **Use watchdog** for hands-off processing
2. **Monitor GPU** with Command Center
3. **Check logs** regularly for issues
4. **Keep models cached** (already done!)
5. **Regular backups** of memory.db

---

## 🔐 Safety Reminders

- ✅ All data in `<GOODQ_DATA_ROOT>\` (backed up separately)
- ✅ Old `GoodQ_4_All\` preserved as backup
- ✅ Git history intact
- ✅ Environments isolated (no conflicts)
- ✅ Models pinned (no surprise upgrades)

---

## 🆘 Emergency Commands

```bash
# Stop everything
<project_root>\STOP_GOODQ.bat

# Kill all Python
Get-Process python | Stop-Process -Force

# Rollback to old version (if needed)
cd <project_root>

# Clear port 8000
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

---

## 📞 Quick Links

- **GitHub**: https://github.com/JoesDomingo/Goodq4all
- **Local**: `<project_root>\`
- **Data**: `<GOODQ_DATA_ROOT>\GoodQ_Data\`

---

**Print this card** | **Bookmark this file** | **Keep handy!**

*Last updated: October 9, 2025 - v1.4.0*
