# 🎯 GoodQ UI Connection Guide

## ✅ API SERVER IS WORKING!

The diagnostic shows:
- ✓ API running on port 30000
- ✓ Endpoints responding correctly
- ✓ Database has 102 scenes
- ✓ Chat endpoint works perfectly

---

## 🔧 ACCESSING THE UI CORRECTLY

### ✅ **CORRECT WAY:**
Open your browser to: **http://localhost:30000**

The API server serves the UI at the root URL.

### ❌ **WRONG WAY:**
Do NOT open: `file:///<project_root>/index.html`

Why? Relative URLs (`/api/chat`) don't work from `file://` protocol.

---

## 🧪 TEST THE CONNECTION

### 1. Open Browser
Navigate to: **http://localhost:30000**

### 2. Open Browser Console
Press **F12** → Go to "Console" tab

### 3. Type a Message
Type anything in the chat box and press Enter

### 4. Check Console
You should see:
```
🔄 Calling API endpoint: /api/chat
📥 Response status: 200 OK
✓ Response data: {...}
```

If you see these, **it's working!**

If you see errors, copy them and we'll fix them.

---

## 🤖 LLM INTEGRATION STATUS

### Current Setup:
- **API Server:** ✅ Running (FastAPI on port 30000)
- **Database:** ✅ Has data (102 scenes, 277 embeddings)
- **Knowledge Graph:** ✅ Has data (59 entities, 943 relationships)
- **Chat Endpoint:** ✅ Responds with database queries

### What's Working NOW:
✓ Query database for scenes, embeddings, entities
✓ Search by keywords
✓ Get statistics
✓ Basic Q&A from structured data

### What's NOT Active Yet:
⚠️ LLM-powered natural language understanding
⚠️ Semantic search using embeddings
⚠️ RAG (Retrieval Augmented Generation)
⚠️ Advanced reasoning

---

## 🚀 ACTIVATING THE LLM AGENT

The LLM agent needs to be connected to the API. Here's what we need:

### Option 1: Local LLM (LM Studio or Ollama)

**If you have LM Studio running:**
1. Check it's on port 1234: http://localhost:1234/v1/models
2. Update `config.yaml` with LLM endpoint
3. Restart API server

**If you have Ollama running:**
1. Check it's running: `ollama list`
2. Pull a model: `ollama pull llama2`
3. Update config for Ollama endpoint

### Option 2: OpenAI API (requires API key)
1. Set environment variable: `OPENAI_API_KEY=your-key`
2. API will use OpenAI automatically

### Option 3: No LLM (Current State)
- Uses database queries only
- Still functional, just not "intelligent"
- Good for testing and basic queries

---

## 📋 WATCHDOG AUTO-INGESTION

### Status: ⚠️ NOT RUNNING

The watchdog monitors `import_inbox/` and auto-processes new files.

**To start it:**
```batch
START_WATCHDOG.bat
```

**What it does:**
- Watches `<project_root>\import_inbox\`
- Detects new video/audio/image files
- Automatically processes them through the pipeline
- Uses deduplication (SHA-256 hash)
- Updates database with new content

**Current inbox files:**
- 1987_1988.mp4 (waiting)
- sample.mp4 (waiting)

**To process these:**
1. Start watchdog: `START_WATCHDOG.bat`
2. Watchdog sees files and queues them
3. Processing begins automatically
4. Monitor progress at: http://localhost:30000/dashboard.html

---

## 🔄 PROCESSING PIPELINE

### Does UI Auto-Launch Pipeline?
**NO** - The UI just displays data. Pipeline runs separately.

### Ways to Process Files:

**Method 1: Watchdog (Automatic)**
```batch
START_WATCHDOG.bat
```
- Drop files in `import_inbox/`
- Auto-processes with deduplication
- Runs in background

**Method 2: Manual Processing**
```batch
conda activate goodq_core
python cli\run_ingestion.py <project_root>\import_inbox\sample.mp4
```

**Method 3: Full System**
```batch
LAUNCH_GOODQ.bat
```
- Starts API + Command Center + Watchdog
- Everything runs together

---

## 🎯 CURRENT STATE SUMMARY

| Component | Status | Notes |
|-----------|--------|-------|
| API Server | ✅ Running | Port 30000 |
| Database | ✅ Has Data | 102 scenes |
| Knowledge Graph | ✅ Has Data | 59 entities |
| Web UI | ✅ Available | http://localhost:30000 |
| LLM Agent | ⚠️ Not Connected | Basic queries only |
| Watchdog | ⚠️ Not Running | Files won't auto-process |
| Local LLM | ❓ Unknown | Need to check if running |

---

## ✅ IMMEDIATE ACTIONS

### 1. Access UI Correctly
**Open:** http://localhost:30000 (NOT file://)

### 2. Test Chat
Type: "How many scenes do I have?"
Expected: "I've identified 102 distinct scenes in your videos"

### 3. Check Browser Console
Press F12, check for errors

### 4. Start Watchdog (Optional)
```batch
START_WATCHDOG.bat
```

### 5. Connect LLM (Optional - for advanced features)
- Check if LM Studio/Ollama is running
- Update config with endpoint
- Restart API server

---

## 🆘 TROUBLESHOOTING

### UI Shows "Error: API failed to fetch"
**Check:**
- Are you at `http://localhost:30000`? (not `file://`)
- Is API server still running?
- Check browser console for actual error

### Chat Doesn't Respond
**Check:**
- Browser console (F12)
- Network tab shows request to `/api/chat`?
- What's the response status code?

### Want Advanced LLM Features
**Need to:**
1. Connect a local LLM (LM Studio/Ollama)
2. OR set OpenAI API key
3. Update config
4. Restart API server

---

**Next:** Tell me what you see when you open http://localhost:30000 and try to chat!

