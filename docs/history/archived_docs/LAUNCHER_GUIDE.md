# GoodQ Launcher Guide

## 🚀 One-Click Launchers

### LAUNCH_GOODQ.bat (Full Stack)
**Recommended for normal use**

Starts:
- ✅ API Server (http://localhost:8000)
- ✅ Command Center Dashboard
- ✅ Opens browser to API docs

**Usage:** Double-click LAUNCH_GOODQ.bat

---

### LAUNCH_GOODQ_SIMPLE.bat (Dashboard Only)
**For quick monitoring without API**

Starts:
- ✅ Command Center Dashboard only

**Usage:** Double-click LAUNCH_GOODQ_SIMPLE.bat

---

### PowerShell Launcher (Advanced)
**For customization and scripting**

```powershell
# Full stack with options
pwsh scripts/launch_goodq_full.ps1 -ApiPort 8000 -HealthCheckFirst

# Skip Command Center
pwsh scripts/launch_goodq_full.ps1 -NoCommandCenter

# Skip browser
pwsh scripts/launch_goodq_full.ps1 -NoBrowser

# Custom API host/port
pwsh scripts/launch_goodq_full.ps1 -ApiHost 127.0.0.1 -ApiPort 8080
```

---

## 🛑 Stopping Services

### Quick Stop
Double-click: STOP_GOODQ.bat

### PowerShell Stop
```powershell
pwsh scripts/stop_goodq_services.ps1
```

### Manual Stop
Close the PowerShell windows titled:
- "GoodQ API Server"
- "GoodQ Command Center"

---

## 🌐 Accessing Services

Once launched:

| Service | URL | Purpose |
|---------|-----|---------|
| API Endpoint | http://localhost:8000 | REST API |
| API Docs | http://localhost:8000/docs | Interactive Swagger docs |
| API Health | http://localhost:8000/health | Health check |
| Command Center | PowerShell Window | Real-time dashboard |

---

## 🔧 Troubleshooting

### "Port 8000 already in use"
Run the stop script first:
```powershell
pwsh scripts/stop_goodq_services.ps1
```

### "Conda not found"
Open **Anaconda PowerShell Prompt** instead of regular PowerShell.

### "Services not starting"
Run health check first:
```powershell
pwsh scripts/mission_health_check.ps1 -EnvPrefix goodq
```

### API not responding
Check the API Server window for errors. You may need to install API dependencies:
```powershell
conda run -n goodq_text_embed pip install -r api/requirements.txt
```

---

## 📊 Command Center Features

The Command Center shows:
- **GPU Stats:** Temperature, usage, memory
- **System Metrics:** CPU, RAM, disk
- **Pipeline Status:** Current processing
- **Memory Stats:** Scene counts, vector indices
- **Recent Logs:** Live tail of step runs

**Keyboard shortcuts:**
- R - Refresh display
- Q - Quit
- L - Show last 50 log entries
- D - Detailed database stats

---

## 🎯 Quick Commands

While services are running:

```powershell
# View job status
Get-Job

# Check API
Invoke-WebRequest http://localhost:8000/health

# Query API
Invoke-RestMethod http://localhost:8000/search/text -Method POST -Body '{"query":"test"}' -ContentType "application/json"

# Stop all
pwsh scripts/stop_goodq_services.ps1
```

---

*For complete documentation, see docs/guides/USER_GUIDE.md*
