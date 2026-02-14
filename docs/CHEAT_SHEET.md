# GoodQ Command Cheat Sheet
**Quick Reference - Keep This Handy!**

═══════════════════════════════════════════════════════════════════════
                         🚀 GETTING STARTED
═══════════════════════════════════════════════════════════════════════

START SYSTEM         <project_root>\LAUNCH_GOODQ.bat
START WATCHDOG       <project_root>\START_WATCHDOG.bat
STOP ALL             <project_root>\STOP_GOODQ.bat (or close windows)

DROP FILES HERE      <project_root>\import_inbox\
API DOCS             http://localhost:30000/docs

═══════════════════════════════════════════════════════════════════════
                        📊 STATUS & MONITORING
═══════════════════════════════════════════════════════════════════════

# Dashboard (real-time)
pwsh scripts\command_center.ps1

# Full system health check
pwsh scripts\verify_project_readiness.ps1

# Current processing status
conda run -n goodq_zenml python scripts\check_production_status.py

# Watch live processing
Get-Content <GOODQ_DATA_ROOT>\GoodQ_Data\logs\step_runs.jsonl -Wait

# Watchdog status
pwsh scripts\watchdog_status.ps1

# View recent logs
Get-Content <project_root>\logs\watchdog.log -Tail 50

═══════════════════════════════════════════════════════════════════════
                       🎬 MANUAL PROCESSING
═══════════════════════════════════════════════════════════════════════

# Activate environment first
conda activate goodq_zenml
cd <project_root>

# Process one video
python cli\run_ingestion.py --video "path\to\video.mp4"

# Process with verbose output
python cli\run_ingestion.py --video "path\to\video.mp4" --verbose

# List files in inbox
python cli\list_inbox.py

═══════════════════════════════════════════════════════════════════════
                      🔍 SEARCH & RETRIEVAL
═══════════════════════════════════════════════════════════════════════

# Text search
python cli\retrieve.py --query "kids playing at beach" --top 5

# Knowledge graph query
python cli\graph_query.py --query "people wearing blue"
python cli\graph_query.py --entity "birthday party"

# List all scenes
python cli\memory.py --list-scenes

# Export data
python cli\memory.py --export --output "my_export.json"

═══════════════════════════════════════════════════════════════════════
                         🌐 API ENDPOINTS
═══════════════════════════════════════════════════════════════════════

GET  http://localhost:30000/health
POST http://localhost:30000/retrieve
GET  http://localhost:30000/docs              (interactive)

# Example API call
curl -X POST http://localhost:30000/retrieve `
  -H "Content-Type: application/json" `
  -d ''{"query": "sunset beach", "top_k": 5}''

═══════════════════════════════════════════════════════════════════════
                         🔧 MAINTENANCE
═══════════════════════════════════════════════════════════════════════

# Clear port 8000 (if stuck)
pwsh -Command "Get-NetTCPConnection -LocalPort 8000 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"

# Check GPU
nvidia-smi

# Kill all Python processes (nuclear option!)
taskkill /F /IM python.exe

# Rebuild environment (if corrupted)
cd <project_root>\envs
pwsh create_all_envs.ps1

# Clean database (DANGER - deletes all data!)
Remove-Item <GOODQ_DATA_ROOT>\GoodQ_Data\databases\*.db

═══════════════════════════════════════════════════════════════════════
                        📂 KEY LOCATIONS
═══════════════════════════════════════════════════════════════════════

Project Code         <project_root>\
Drop Files           <project_root>\import_inbox\
Databases            <GOODQ_DATA_ROOT>\GoodQ_Data\databases\
Logs                 <GOODQ_DATA_ROOT>\GoodQ_Data\logs\
Models               <GOODQ_DATA_ROOT>\models\
Processing Output    <GOODQ_DATA_ROOT>\GoodQ_Data\logs\workspace\

═══════════════════════════════════════════════════════════════════════
                    🎯 SUPPORTED FILE TYPES
═══════════════════════════════════════════════════════════════════════

VIDEO   .mp4 .avi .mov .mkv .wmv .flv .webm .m4v
AUDIO   .mp3 .wav .flac .m4a .aac .ogg .wma
IMAGE   .jpg .jpeg .png .bmp .gif .tiff .webp
DOCS    .pdf .txt .md (future)

═══════════════════════════════════════════════════════════════════════
                    🔥 COMMON ISSUES & FIXES
═══════════════════════════════════════════════════════════════════════

PROBLEM                          FIX
─────────────────────────────── ────────────────────────────────────
Port 8000 in use                 Stop services or kill process
Database locked                  Close all Python processes
Environment error                Verify: verify_project_readiness.ps1
Watchdog not processing          Check logs: watchdog.log
Out of VRAM                      Reduce concurrent processes
Model download fails             Check internet, HF_HOME setting

═══════════════════════════════════════════════════════════════════════
                      ⏱️ PROCESSING ESTIMATES
═══════════════════════════════════════════════════════════════════════

5 min video      →  2-5 min processing
30 min video     → 10-20 min processing  
1 hour video     → 30-60 min processing
8GB home movie   →  2-4 hour processing

(RTX 4070 Ti SUPER, 16GB VRAM)

═══════════════════════════════════════════════════════════════════════
                        💡 PRO TIPS
═══════════════════════════════════════════════════════════════════════

✓ Use watchdog for batch processing (drop multiple files)
✓ Monitor VRAM usage in Command Center
✓ Check step_runs.jsonl if processing seems stuck
✓ Backup databases before big processing runs
✓ Clear _INGESTED files periodically
✓ Keep LM Studio or Ollama running for best results

═══════════════════════════════════════════════════════════════════════
                         📚 DOCUMENTATION
═══════════════════════════════════════════════════════════════════════

QUICK_START.md               - Detailed getting started guide
WORKFLOW_VISUAL_GUIDE.md     - Visual flow diagrams
TROUBLESHOOTING.md           - Detailed problem solving
WATCHDOG_GUIDE.md            - Automatic processing setup
knowledge_graph.md           - Graph database structure
MODEL_LOCKDOWN.md            - Version control details

═══════════════════════════════════════════════════════════════════════

GitHub: https://github.com/JoesDomingo/goodq4all
Status: Production Ready ✅
Version: 1.0.0

═══════════════════════════════════════════════════════════════════════
