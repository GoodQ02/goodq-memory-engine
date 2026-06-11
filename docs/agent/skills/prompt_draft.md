# Teamwork Project Prompt — Draft

> Status: Ready for launch — awaiting user approval
> Goal: Craft prompt → get user approval → delegate to teamwork_preview

Implement security, conformance, and concurrency hardening fixes for the GoodQ4All codebase based on the findings in `reports/llm_audit_report.md` and the guidelines in `AGENTS.md`.

Working directory: C:\Users\jdben\GOOD_DEV\projects\goodq4all
Integrity mode: development

## Requirements

### R1. Conformance and Path Hardening (AGENTS.md Rules)
- **agents/config_healer.py**: Remove the hardcoded Windows fallback path `"C:\\ProgramData\\GoodQ4All"` at line 70. Raise a `ValueError` if the `GOODQ_DATA_ROOT` environment variable is missing. At line 64, remove the default config directory fallback (`self.root / "configs"`) and require an explicit path configuration, failing fast if missing.
- **agents/llm_agent.py**: Remove the default hardcoded API URL fallback (`'http://localhost:1234/v1/chat/completions'`) at line 26. Raise a `ValueError` if `api_url` is not set in configuration.

### R2. Concurrency Safety Fixes
- **api/routes/ingest.py**: Wrap all accesses (`add`, `remove`, `in` / containment checks) to the global `_active_tokens` set with a `threading.Lock` to prevent race conditions during concurrent confirmation token submissions.

### R3. Robustness and Error Handling
- **cli/links.py**: Wrap `json.loads(meta)` in a try-except block to handle malformed JSON inputs gracefully without crashing the CLI.

## Acceptance Criteria

### AST and Import Verification
- [ ] All modified files (`agents/config_healer.py`, `agents/llm_agent.py`, `api/routes/ingest.py`, `cli/links.py`) must pass syntax validation (`python -m py_compile`).
- [ ] The codebase must be capable of running the native static auditor (`python scripts/audit_codebase.py`) successfully without crashing.

### Code Constraints Verification
- [ ] No hardcoded Windows drive roots (e.g. `C:\\`) remain in `agents/config_healer.py` or `agents/llm_agent.py`.
- [ ] The global `_active_tokens` set accesses in `api/routes/ingest.py` are synchronized via a thread lock.
