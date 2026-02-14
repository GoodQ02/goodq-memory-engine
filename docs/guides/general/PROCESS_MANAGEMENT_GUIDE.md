# GoodQ4All Process Management System - Complete Guide

## Overview

The GoodQ4All Process Management System provides centralized, reliable control over all system components with proper lifecycle management, logging, and monitoring.

## Architecture

### Components

1. **Process Manager (`process_manager.py`)** - Core process lifecycle management
2. **API Integration** - REST endpoints for web-based control
3. **Web UI** - Browser-based process control interface
4. **Batch Scripts** - Quick start/stop commands

### Managed Processes

- **api_server** - FastAPI backend serving the web interface and API
- **watchdog** - File ingestion monitor for automatic processing
- **analytics** - Analytics dashboard (optional)

## Quick Start

### Method 1: Batch Scripts (Recommended)

```batch
# Start all services
START_GOODQ_SYSTEM.bat

# Check status
STATUS_CHECK.bat

# Stop all services
STOP_GOODQ_SYSTEM.bat
```

### Method 2: Python CLI

```bash
# Start a process
python process_manager.py start api_server
python process_manager.py start watchdog

# Check status
python process_manager.py status

# Stop a process
python process_manager.py stop watchdog

# Restart a process
python process_manager.py restart api_server

# View logs
python process_manager.py logs api_server --lines 50

# Stop all
python process_manager.py stop-all
```

### Method 3: Web UI

1. Start the API server (if not running)
2. Open http://localhost:30000
3. Click "⚙️ Process Control" in the sidebar
4. Use the buttons to start/stop/restart processes
5. View live logs by clicking "Logs" button

## Features

### Process Lifecycle Management

- **Graceful Shutdown**: Processes are sent termination signals before being killed
- **PID Tracking**: Each process PID is tracked and verified
- **State Persistence**: Process state is saved between sessions
- **Auto-Recovery**: Detects if processes are already running from previous sessions

### Logging

- **Dedicated Logs**: Each process gets its own timestamped log file
- **Centralized Storage**: All logs stored in `<project_root>\logs\`
- **Log Viewing**: View logs via CLI or web interface
- **Rotation**: Logs are automatically rotated on restart

### Monitoring

- **Real-time Status**: Check if processes are running
- **Resource Tracking**: Monitor PIDs, start times
- **Health Checks**: Verify process responsiveness
- **Web Dashboard**: Live status updates in browser

## File Structure

```
<project_root>\
├── process_manager.py              # Core process manager
├── START_GOODQ_SYSTEM.bat         # Start all services
├── STOP_GOODQ_SYSTEM.bat          # Stop all services
├── STATUS_CHECK.bat               # Quick status check
├── api_server.py                  # API server (includes process endpoints)
├── logs/
│   ├── process_manager.log        # Process manager log
│   ├── api_server_*.log           # API server logs
│   ├── watchdog_*.log             # Watchdog logs
│   ├── pids/                      # PID files
│   │   ├── api_server.pid
│   │   └── watchdog.pid
│   └── process_state.json         # State persistence
```

## API Endpoints

### GET /api/processes
Get status of all processes.

**Response:**
```json
{
  "processes": {
    "api_server": {
      "name": "api_server",
      "pid": 12345,
      "status": "running",
      "started_at": "2025-11-08T23:25:00",
      "log_file": "<project_root>\\logs\\api_server_20251108_232500.log"
    }
  },
  "timestamp": "2025-11-08T23:30:00"
}
```

### POST /api/processes/{name}/start
Start a process.

### POST /api/processes/{name}/stop
Stop a process.

### POST /api/processes/{name}/restart
Restart a process.

### GET /api/processes/{name}/logs?lines=100
Get recent log lines for a process.

## Troubleshooting

### Process Won't Start

1. Check logs: `python process_manager.py logs <process_name>`
2. Verify Python environment: `C:\Users\jdben\miniconda3\envs\goodq_zenml\python.exe --version`
3. Check for port conflicts (API server uses port 30000)
4. Ensure working directory exists and is accessible

### Process Won't Stop

1. Try force stop: Kill the process via Task Manager
2. Clean up PID files: Delete `logs/pids/<process>.pid`
3. Reset state: Delete `logs/process_state.json`

### State Issues

If processes show as "running" but aren't:
```bash
# Reset state
del <project_root>\logs\process_state.json
del <project_root>\logs\pids\*.pid

# Check actual status
python process_manager.py status
```

### Import Errors

Ensure psutil is installed:
```bash
C:\Users\jdben\miniconda3\envs\goodq_zenml\python.exe -m pip install psutil
```

## Best Practices

### Starting the System

1. Always use `START_GOODQ_SYSTEM.bat` for initial startup
2. Wait 3-5 seconds between starting processes
3. Check status after starting: `STATUS_CHECK.bat`

### Stopping the System

1. Use `STOP_GOODQ_SYSTEM.bat` for clean shutdown
2. Wait for processes to terminate gracefully
3. Verify all stopped: `python process_manager.py status`

### Monitoring

1. Keep Command Center open during processing
2. Check logs regularly for errors
3. Monitor disk space in logs directory

### Development

1. Stop watchdog during development to prevent auto-processing
2. Keep API server running for UI access
3. Restart processes after code changes

## Advanced Usage

### Custom Process Configuration

Edit `process_manager.py` to add new processes:

```python
def create_goodq_manager() -> ProcessManager:
    manager = ProcessManager()
    
    # Add custom process
    manager.register_process(
        name='my_custom_process',
        command=[str(python_exe), 'my_script.py', '--arg', 'value'],
        cwd=BASE_DIR,
        env={'CUSTOM_VAR': 'value'}  # Optional environment variables
    )
    
    return manager
```

### Process Groups

Start/stop related processes together:

```python
# Web stack
for proc in ['api_server']:
    manager.start(proc)

# Processing stack
for proc in ['watchdog', 'analytics']:
    manager.start(proc)
```

### Health Monitoring

Implement custom health checks:

```python
def check_health(self, name: str) -> bool:
    proc_info = self.processes.get(name)
    if not proc_info or not proc_info.is_running():
        return False
    
    # Custom health check (e.g., HTTP ping for API server)
    if name == 'api_server':
        try:
            response = requests.get('http://localhost:30000/api/status', timeout=2)
            return response.status_code == 200
        except:
            return False
    
    return True
```

## Integration with GoodQ4All Pipeline

The process manager integrates seamlessly with the GoodQ4All video processing pipeline:

1. **API Server**: Provides web interface and REST API access
2. **Watchdog**: Automatically detects and processes new videos
3. **Analytics**: Generates insights and visualizations

### Typical Workflow

1. Start system: `START_GOODQ_SYSTEM.bat`
2. Open UI: http://localhost:30000
3. Drop video in `import_inbox/`
4. Watchdog detects and processes automatically
5. Monitor progress in Command Center
6. View results in Scene Explorer
7. Stop system: `STOP_GOODQ_SYSTEM.bat`

## Future Enhancements

- [ ] WebSocket notifications for process events
- [ ] Automatic restart on crash
- [ ] Resource usage monitoring (CPU, memory)
- [ ] Process scheduling and cron jobs
- [ ] Multi-machine deployment support
- [ ] Docker container integration

## Support

For issues or questions:
1. Check logs in `<project_root>\logs\`
2. Review this documentation
3. Check API status: http://localhost:30000/api/status
4. Reset system state if needed

---

**Version**: 1.0.0  
**Last Updated**: 2025-11-09  
**Author**: GoodQ4All Development Team
