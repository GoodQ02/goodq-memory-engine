# GoodQ v2.2 - Quick Start Guide

> Note: This guide reflects a specific historical configuration (GoodQ v2.2). For the canonical, up-to-date Quick Start, agents and users should follow `docs/user-guides/QUICK_START_CLEAN.md`.

## 🚀 System is LIVE and READY!

Your GoodQ system is now fully operational with a production-grade web interface showing real data from your pipeline.

---

## ✅ What's Working NOW

### 1. **Web Interface** 
- **URL:** http://localhost:30000
- **Status:** ✅ RUNNING
- **Real-time updates:** Every 10 seconds

### 2. **Current Data**
- **25 Scenes** processed and indexed
- **69 Embeddings** created for search
- **208 Entities** extracted (people, objects, locations)
- **37 Relationships** mapped between entities

### 3. **API Endpoints** (All Functional)
- ✅ Status monitoring
- ✅ Progress tracking  
- ✅ Scene explorer
- ✅ Entity browser
- ✅ Analytics dashboard
- ✅ Live log streaming
- ✅ Process control

---

## 📱 How to Use the Interface

### Dashboard (Home)
- **Quick stats** - See your data at a glance
- **System status** - Check processing state
- **Recent scenes** - Preview latest processed content

### Scene Explorer
1. Click "Scenes" in left sidebar
2. Browse all 25 processed scenes
3. See timestamps, emotions, and transcripts
4. Click any scene for details (coming soon)

### Entity Browser
1. Click "Entities" in left sidebar
2. View all extracted entities grouped by type
3. See entity properties and metadata
4. Currently showing: people, objects, locations

### Analytics Dashboard
1. Click "Analytics" in left sidebar
2. View emotion distribution charts
3. See sentiment analysis (positive/negative/neutral)
4. Explore entity type breakdowns

### Command Center
1. Click "Command Center" for live logs
2. See real-time watchdog activity
3. Monitor processing status
4. Logs auto-refresh every 5 seconds
5. Scroll to bottom for latest entries

### Chat Interface
1. Click "Chat" to interact with AI
2. Ask questions about your data
3. Get context-aware responses
4. LLM integration with fallback mode

### Process Control
1. Click "Processes" to see system status
2. View running processes
3. Start/stop/restart components
4. Monitor PIDs and health

---

## 🎬 Processing New Videos

### Method 1: Drop Files
```
1. Copy video files to: L:\goodq4all\import_inbox\
2. Watchdog auto-detects and processes
3. Watch progress in Command Center or Dashboard
4. Processed files appear in Scene Explorer
```

### Method 2: Launch Watchdog
```batch
# If not running, start watchdog:
cd L:\goodq4all
python scripts\watchdog_ingest.py

# Or use the batch file:
START_WATCHDOG.bat
```

---

## 📊 Real-Time Monitoring

### What Updates Automatically
- ✅ **Processing status** (10s interval)
- ✅ **Database stats** (10s interval)
- ✅ **Progress bars** (5s interval)
- ✅ **Command Center logs** (5s interval when viewing)
- ✅ **Scene counts** (10s interval)

### Progress Tracking
When a video is processing, you'll see:
- Current file name
- Current step (Scene Detection, Audio Analysis, etc.)
- Progress percentage
- Estimated time remaining

---

## 🔍 Exploring Your Data

### Search for Specific Emotions
1. Go to Analytics
2. See emotion distribution
3. Most common emotions shown with counts

### Find Specific People
1. Go to Entities
2. Scroll to "Person" section
3. See all detected people

### View Scene Timeline
1. Go to Scenes
2. Scenes are ordered by timestamp
3. Each shows: start/end time, duration, summary

---

## ⚙️ System Controls

### Check System Health
- **Green dot** on API = Server running
- **Green dot** on Processing = Active ingestion
- **Stats updating** = All systems operational

### If Something Stops Working
1. Check Command Center for errors
2. View Process Control for status
3. Restart API server if needed:
   ```batch
   python api_server.py
   ```

---

## 📁 File Locations

### Important Paths
- **UI:** `L:\goodq4all\index.html`
- **API Server:** `L:\goodq4all\api_server.py`
- **Import Inbox:** `L:\goodq4all\import_inbox\`
- **Output Data:** `L:\goodq4all\output\`
- **Databases:** `L:\goodq4all\data\`
- **Logs:** `L:\goodq4all\logs\`

### Databases
- **memory.db** - Scenes, embeddings, segments
- **knowledge_graph.db** - Entities, relationships
- **unified_goodq.db** - Unified data store
- **faiss_indices/** - Vector search indices

---

## 🎯 Next Steps

### Immediate Actions
1. ✅ Open http://localhost:30000 in browser
2. ✅ Explore all 7 interface sections
3. ✅ Check Command Center logs
4. ✅ Review current 25 scenes

### Test Processing
1. Copy a home movie to `import_inbox/`
2. Watch Command Center for activity
3. Monitor progress bar in top bar
4. Check Scenes tab for new results

### Advanced Usage
1. Use Chat to query your data
2. Export analytics for reporting
3. Browse knowledge graph
4. Search across all content

---

## 🐛 Troubleshooting

### UI Won't Load
```batch
# Check if API server is running
curl http://localhost:30000/api/status

# If not, start it:
cd L:\goodq4all
python api_server.py
```

### No Data Showing
1. Check database files exist in `data/`
2. Verify scenes count in API status
3. Check logs for errors

### Processing Stuck
1. Open Command Center
2. Look for ERROR or WARNING lines
3. Check current file being processed
4. Review `logs/watchdog.log` for details

### Chat Not Responding
- LLM may be loading (first request slow)
- Check fallback mode is working
- Verify LM Studio is running

---

## 💡 Pro Tips

1. **Keep Command Center open** while processing to monitor progress
2. **Use Dashboard** for quick health checks
3. **Analytics updates** after each scene is processed
4. **Scenes are paginated** - scroll to see all
5. **Entities grouped by type** for easy browsing
6. **Progress bar appears** automatically when processing starts

---

## 🎉 You're All Set!

Your GoodQ system is:
- ✅ Fully operational
- ✅ Processing ready
- ✅ UI functional
- ✅ Data wired correctly
- ✅ Real-time monitoring active

**Access now:** http://localhost:30000

**Questions?** Check `PHASE_2_2_COMPLETE.md` for technical details.

---

**Enjoy exploring your memories! 🎬❤️**
