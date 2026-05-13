# 🔧 Quick API Debug Instructions

## The Issue:
- API server is running ✓
- API responds in PowerShell ✓
- But UI shows "No response from API" ✗

## Quick Test:

### Step 1: Open Debug Page
Navigate to: **http://localhost:30000/test_chat_debug.html**

### Step 2: Click Button 2
"Test Chat (hardcoded)" - uses exact same query as you typed

### Step 3: Check Results
- If it works → Problem is in main UI JavaScript
- If it fails → Check browser console for actual error

## What to Look For:

### In Browser Console (F12):
- Red errors?
- Network request failing?
- CORS errors?
- JavaScript exceptions?

### Common Issues:

**1. Browser Cache**
Solution: Hard refresh (Ctrl+Shift+R)

**2. CORS Blocking**
Solution: the API should allow localhost origins only; check the browser console
to confirm you are running from `http://localhost:30000` or `http://127.0.0.1:30000`

**3. JavaScript Error**
Solution: Check console for red text, tell me what it says

**4. Wrong Response Format**
Solution: API might be returning different structure than expected

## API Server Configuration:

Current settings in the canonical API server (`api/server.py` + `api/main.py`):
```python
# Canonical localhost-only CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:30000",
        "http://127.0.0.1:30000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Manual Test (Bypass UI Completely):

**Open browser console on http://localhost:30000 and paste:**
```javascript
fetch('/api/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({message: "how many scenes", context: {mode: "natural"}})
})
.then(r => r.json())
.then(d => console.log('SUCCESS:', d))
.catch(e => console.error('ERROR:', e));
```

**Expected Result:**
```json
{
  "message": "I've identified 102 distinct scenes in your videos",
  "context": {...},
  "suggestions": [...]
}
```

## If Still Not Working:

Tell me:
1. What do you see in browser console? (F12 → Console tab)
2. What do you see in Network tab? (F12 → Network → look for /api/chat request)
3. Does test_chat_debug.html work?

Then I can pinpoint the exact issue and fix it!
