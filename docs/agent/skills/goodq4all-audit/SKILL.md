---
name: goodq4all-audit
description: Use for running automated LLM codebase audits with Gemini 2.5 Pro, ensuring AGENTS.md compliance, API thread safety, and security hardening.
---

# GoodQ4All Automated Codebase Audit

Use this skill when performing static and LLM-based compliance and security audits on the codebase.

## Prerequisites

1. Active Google Cloud SDK authentication:
   ```powershell
   gcloud auth login
   gcloud auth application-default login
   ```
2. The billing/quota project must be set (e.g., `project-begood`):
   ```powershell
   gcloud config set project project-begood
   gcloud config set billing/quota_project project-begood
   ```

## Running the Codebase Audit

Run the native LLM-based audit tool using the base python environment:
```powershell
conda run -n base python scripts/audit_llm.py --project project-begood
```

### Command Parameters

* `--project`: GCP Project ID to charge Vertex AI billing.
* `--region`: Google Cloud location region (defaults to `us-central1`).
* `--output`: Path to write the generated markdown audit report (defaults to `reports/llm_audit_report.md`).

## Verification & Conformance Checklist

When auditing the codebase, ensure that:
1. **No Hardcoded Absolute Paths:** Check that no literal Windows drive roots (e.g., `C:\\` or `C:/`) exist in runtime code. Use environment variables (like `GOODQ_DATA_ROOT`) instead.
2. **Explicit Config Gating:** Ensure config dependencies fail fast (`ValueError`) when required directories or environment variables are not supplied.
3. **Concurrency Locks:** Wrap mutable global data structures accessed by ASGI web entry points (like `_active_tokens` in `api/routes/ingest.py`) with thread-safe synchronization locks (`threading.Lock`).
4. **Observable Exception Handling:** Avoid silent suppression or bare `except:` clauses. Always catch specific exceptions (like `json.JSONDecodeError` or `ValueError`) and log descriptive warnings to preserve the "fail visible, not loud" protocol.
5. **No Test Backdoors:** Verify that no hardcoded debug bypass tokens (like `"confirm-123"`) exist in the route handlers.
