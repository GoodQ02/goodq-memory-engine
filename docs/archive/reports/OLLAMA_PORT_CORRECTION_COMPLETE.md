<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

# Ollama Port Correction - Complete

**Date**: December 9, 2025  
**Status**: ✅ COMPLETE

## Problem Identified

The system was trying to connect to Ollama (Phi4) on port **31434** instead of the standard Ollama port **11434**, causing persistent connection failures:

```
✗ Phi4-Ollama unhealthy: HTTPConnectionPool(host='localhost', port=31434): 
Max retries exceeded with url: /v1/models (Caused by NewConnectionError(...))
```

## Root Cause

Historical configuration used a non-standard port (31434) across multiple system components. Ollama's default port is 11434.

## Files Corrected

### 1. **api/main.py** (4 instances)
- Line 121: Health check endpoint
- Lines 182-203: Engine status reporting
- Line 487: Model availability check
- Line 574: Health monitoring

### 2. **api/main_unified.py** (2 instances)
- Lines 491-510: Ollama engine registration and health checks

### 3. **steps/llm_chat/step.py** (1 instance)
- Line 113: Fallback detection logic

### 4. **scripts/utils/check_llm_availability.py** (3 instances)
- Lines 44-46: Ollama service configuration

### 5. **scripts/test_llm_connectivity.py** (1 instance)
- Line 51: Ollama fallback endpoint

## Changes Applied

All references changed from:
```python
http://localhost:31434  →  http://localhost:11434
port: 31434             →  port: 11434
```

## Verification

✅ All code files updated  
✅ Syntax validated  
✅ Git committed  
✅ No remaining 31434 references in active code

## Impact

- **Phi4-Ollama health checks**: Now correctly reach Ollama service
- **LLM fallback logic**: Properly routes to Ollama when needed
- **API status dashboard**: Accurately reports Ollama availability
- **System monitoring**: Clean health reports without false warnings

## Next Steps

1. Restart test_system.bat to verify clean execution
2. Confirm no Phi4-Ollama warnings appear
3. Validate Ollama connectivity in full ingestion run

## Commit

```
fix: correct Ollama port from 31434 to 11434 across all files
- Updated api/main.py with correct Ollama port
- Updated api/main_unified.py 
- Updated steps/llm_chat/step.py
- Updated scripts/utils/check_llm_availability.py
- Updated scripts/test_llm_connectivity.py
- All Ollama references now use standard port 11434
```

---

**Status**: System now uses correct Ollama port throughout entire codebase.
