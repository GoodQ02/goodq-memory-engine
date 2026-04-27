<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: REFERENCE_ONLY -->
<!-- DOC_LAST_VERIFIED: 2026-04-27 -->

> Historical note: This assessment captures a dated WSL/vLLM port investigation.
> It is not a live runtime status source. Verify current ports through active
> config, health checks, and operator docs before acting on this snapshot.

# Port Architecture Assessment - WSL/vLLM Integration Issues

**Date**: 2025-11-18  
**Context**: Evaluating unified port standardization approach for resolving WSL localhost connectivity issues

---

## Current Port Landscape

### Production Ports (Active)
| Service | Port | Location | Status | Notes |
|---------|------|----------|--------|-------|
| **GoodQ API Server** | 30000 | Windows | ✅ Active | Primary user interface, FastAPI |
| **vLLM Llama-1B** | 38005 | WSL | ✅ Active | Primary LLM (178 tok/s) |
| **vLLM Llama-3B** | 38004 | WSL | Available | Optional balanced model |
| **vLLM Phi-3.5** | 38001 | WSL | Available | Optional long-context |
| **vLLM Qwen-7B** | 38000 | WSL | Available | Quality model |
| **vLLM Llama-11B-Vision** | 38006 | WSL | Available | Multimodal model |
| **Ollama** | 31434 | WSL | ✅ Active | Fallback LLM (Phi-4) |
| **LM Studio** | 1234 | Windows | Legacy | Not actively used |

### Legacy/Deprecated Ports
| Port | Previous Use | Current Status |
|------|-------------|----------------|
| 8000 | Old API server, web_interface.py | ❌ Archived |
| 5000 | serve_chat.py static server | ❌ Archived |

---

## Port Standardization Assessment

### ✅ GOOD NEWS: Port Architecture is Already Clean

1. **No Port Conflicts Detected**
   - API Server (30000) doesn't conflict with any LLM ports
   - vLLM ports (38000-38006) are isolated in WSL (use `sudo scripts/wsl/update_vllm_service_port.sh` to retarget the systemd unit to 38005 if needed)
   - Ollama (31434) is unique
   - Legacy ports (5000, 8000) are archived, not active

2. **Logical Port Ranges Already Established**
   - 30000: User-facing API/UI
   - 1234: LM Studio (legacy)
   - 38000-38006: vLLM model servers (WSL)
   - 31434: Ollama (standard port)

3. **WSL Networking Already Configured**
   - `.wslconfig` with `networkingMode=mirrored` exists
   - Localhost forwarding already enabled
   - vLLM server IS running and responding (confirmed from logs)

---

## Root Cause Analysis: NOT a Port Problem

### Evidence from Recent Logs
```
(APIServer pid=20919) INFO:     127.0.0.1:52111 - "GET /v1/models HTTP/1.1" 200 OK
(APIServer pid=20919) INFO:     127.0.0.1:39572 - "POST /v1/chat/completions HTTP/1.1" 200 OK
```

**CRITICAL FINDING**: vLLM IS WORKING and responding successfully to:
- Health checks (`/v1/models`)
- Chat completions (`/v1/chat/completions`)
- Connections from both localhost (127.0.0.1) and network (192.168.0.229)

### The Real Issue is NOT Port Configuration

The localhost issues you're experiencing are likely:

1. **Service Discovery/Health Monitoring**
   - LLM client may not be detecting healthy vLLM servers
   - Health check cache may be stale
   - Fallback logic may be prematurely triggered

2. **Request Routing**
   - Client code may not be using the correct model IDs
   - vLLM expects full model paths: `/mnt/l/_DATA/models/llm/huggingface/Llama-3.2-1B-Instruct`
   - Not short names like "Llama-1B"

3. **WSL Network State**
   - WSL may need restart to refresh networking
   - Firewall/antivirus may be blocking certain traffic patterns
   - DNS resolution issues (localhost vs 127.0.0.1)

4. **Configuration Mismatches**
   - `llm_client.py` model configs vs actual running servers
   - Timeout values too aggressive
   - Connection pooling issues

---

## Recommendation: **DO NOT** Implement Full Port Standardization

### Why Not

1. **Overkill Solution**
   - Ports are already well-organized
   - No actual conflicts exist
   - Would require changing 200+ files unnecessarily
   - High risk of breaking working systems

2. **Won't Fix the Real Problem**
   - vLLM is already responding on correct ports
   - Issue is in client-side service discovery/routing
   - Changing ports won't fix health checks or model ID mismatches

3. **Breaking Change Risk**
   - Could disrupt existing vLLM processes
   - Would require rebuilding all startup scripts
   - Documentation would be massively out of sync
   - Testing burden would be enormous

### Better Approach: Targeted Diagnostics & Fixes

**PRIORITY 1: Verify Current State**
```bash
# Test vLLM connectivity
curl http://localhost:38005/v1/models
curl http://localhost:38005/v1/chat/completions -X POST -H "Content-Type: application/json" \
  -d '{"model": "/mnt/l/_DATA/models/llm/huggingface/Llama-3.2-1B-Instruct", "messages": [{"role": "user", "content": "test"}]}'

# Test from Windows
python <project_root>\scripts\test_llm_client.py
```

**PRIORITY 2: Fix LLM Client Issues**
1. Update model IDs in `lib/llm_client.py` to match vLLM expectations
2. Adjust health check timeouts (may be too short)
3. Force fresh health check (bypass cache)
4. Add better logging to see where failures occur

**PRIORITY 3: WSL Network Refresh**
```powershell
# Restart WSL networking
wsl --shutdown
wsl
# Restart vLLM service
wsl -d <GOODQ_WSL_DISTRO> -- sudo systemctl restart vllm-llama1b
```

**PRIORITY 4: Configuration Audit**
- Verify all configs point to correct ports
- Check timeout values
- Review connection pool settings
- Validate model paths

---

## Minimal Port Updates (If Any)

### Only Update Documentation References

These files have **inconsistent documentation** (not actual config issues):

#### Docs with Wrong Port References (for docs only, not config):
- Some docs still reference `localhost:8000` for API (should be 30000)
- Some docs reference old LM Studio integration (1234) instead of vLLM

#### Quick Fix: Doc Updates Only
```bash
# These are documentation corrections, not port changes:
- Update remaining docs that say "port 8000" for API → "port 30000"
- Update LLM docs to emphasize vLLM (38005) as primary, not LM Studio (1234)
- Add WSL port table to architecture docs
```

---

## Action Plan: Surgical Fixes, Not Rewrite

### Phase 1: Diagnose (30 min)
1. Run comprehensive connectivity test
2. Check LLM client health cache
3. Review vLLM logs for errors
4. Test manual curl requests

### Phase 2: Targeted Fixes (1-2 hours)
1. Fix model ID paths in `llm_client.py`
2. Adjust health check parameters
3. Add debug logging
4. Update stale documentation references

### Phase 3: Validation (30 min)
1. Test full LLM client failover chain
2. Verify vLLM → Ollama fallback works
3. Run integration tests
4. Update troubleshooting docs

**Total Time**: 2-3 hours vs 20+ hours for full port standardization

---

## Conclusion

**RECOMMENDATION**: ❌ **DO NOT** proceed with unified port architecture refactor

**INSTEAD**: ✅ Implement targeted diagnostics and fixes for actual issues:
1. Service discovery/health monitoring
2. Model ID path configuration
3. WSL network state
4. Client timeout tuning

The port architecture is **already good**. The problem is elsewhere.

---

## Next Steps

Would you like me to:
1. **Run comprehensive diagnostics** on current vLLM/WSL connectivity?
2. **Fix LLM client configuration** to properly connect to vLLM?
3. **Update only the documentation** that has wrong port references?
4. **Investigate the specific error** you're experiencing?

Please describe the actual localhost issue you're seeing so we can fix the root cause.

