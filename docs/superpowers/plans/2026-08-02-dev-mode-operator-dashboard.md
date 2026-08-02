# Dev Mode Operator Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Dev On and Dev Off display an accessible, CRT-style, check-driven operator receipt without adding a service or making the runtime depend on cosmetic tooling.

**Architecture:** Add one PowerShell presentation helper that emits a fixed signal path and event lines from explicit `start`, `node`, and `final` calls. The existing batch launchers retain all runtime ownership and invoke the helper only after their real checks. The helper has a `-NoColor` mode for deterministic tests; status words and symbols remain authoritative without color.

**Tech Stack:** Windows batch, PowerShell 7, Python pytest, existing GoodQ launcher contracts.

## Global Constraints

- Keep `dev_on.bat` and `dev_off.bat` as the sole operator entry points.
- Do not add a browser page, background service, network call, model load, or repository-data access.
- Use text and symbols in addition to ANSI color: lime `[READY]`, blue `[INFO]`, white `[CHECK]`, yellow `[WARN]`, and red `[BLOCKED]`.
- Keep the final window open until user close; callers using `GOODQ_NO_PAUSE=1` remain non-interactive for test/control flows.
- Invoke all launcher PowerShell automation with `-NoProfile`.
- Oh My Posh remains optional and must not be referenced by launcher code.

---

### Task 1: Build the deterministic dashboard renderer

**Files:**
- Create: `scripts/dev_mode_dashboard.ps1`
- Create: `tests/unit/test_dev_mode_dashboard.py`

**Interfaces:**
- Consumes: `-Mode dev-on|dev-off`, `-Event start|node|final`, optional `-Node`, `-State pending|check|ready|warn|blocked|retained|released`, optional `-Message`, and switch `-NoColor`.
- Produces: one readable line per event; no process, network, filesystem, or runtime-service side effects.

- [ ] **Step 1: Write the failing renderer tests**

```python
def _dashboard(*args: str) -> str:
    completed = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(REPO_ROOT / "scripts" / "dev_mode_dashboard.ps1"), *args, "-NoColor"],
        check=True, capture_output=True, text=True,
    )
    return completed.stdout


def test_start_renders_the_fixed_build_mode_signal_path():
    output = _dashboard("-Mode", "dev-on", "-Event", "start")
    assert "DEV ON / BUILD MODE" in output
    assert "[CONFIG]" in output
    assert "[WSL AUDIO]" in output
    assert "[vLLM]" in output
    assert "[QDRANT]" in output
    assert "[API]" in output


def test_blocked_node_names_the_node_and_actionable_reason():
    output = _dashboard("-Mode", "dev-on", "-Event", "node", "-Node", "vLLM", "-State", "blocked", "-Message", "endpoint did not respond")
    assert "[BLOCKED] vLLM" in output
    assert "endpoint did not respond" in output


def test_dev_off_final_calls_out_retained_qdrant():
    output = _dashboard("-Mode", "dev-off", "-Event", "final", "-State", "ready", "-Message", "Qdrant retained on loopback")
    assert "OPEN DESKTOP — GPU SERVICES RELEASED" in output
    assert "Qdrant retained on loopback" in output
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/test_dev_mode_dashboard.py -q`

Expected: FAIL because `scripts/dev_mode_dashboard.ps1` does not exist.

- [ ] **Step 3: Implement the minimal renderer**

```powershell
param(
    [ValidateSet('dev-on', 'dev-off')] [string] $Mode,
    [ValidateSet('start', 'node', 'final')] [string] $Event,
    [string] $Node,
    [ValidateSet('pending', 'check', 'ready', 'warn', 'blocked', 'retained', 'released')] [string] $State,
    [string] $Message,
    [switch] $NoColor
)

function Write-DashboardLine([string] $Label, [string] $Text) {
    if ($NoColor) { Write-Output "$Label $Text"; return }
    $color = @{ '[READY]' = 'Green'; '[INFO]' = 'Cyan'; '[CHECK]' = 'White'; '[WARN]' = 'Yellow'; '[BLOCKED]' = 'Red' }[$Label]
    Write-Host $Label -ForegroundColor $color -NoNewline
    Write-Host " $Text"
}

switch ($Event) {
    'start' { ... }  # print the fixed path and a mode-specific [CHECK] line
    'node'  { ... }  # map state to text label and print "$Node — $Message"
    'final' { ... }  # print only the mode-specific success/failure banner and message
}
```

The final implementation must reject empty `-Node` for `node` events and empty `-State` for `node`/`final` events with exit code 1 and a readable message. It must use the literal final banners `SYSTEM READY — BUILD MODE` and `OPEN DESKTOP — GPU SERVICES RELEASED`.

- [ ] **Step 4: Run renderer tests to verify they pass**

Run: `python -m pytest tests/unit/test_dev_mode_dashboard.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the renderer seam**

```bash
git add scripts/dev_mode_dashboard.ps1 tests/unit/test_dev_mode_dashboard.py
git commit -m "feat(dev-mode): add operator dashboard renderer"
```

### Task 2: Integrate Dev On with real readiness events

**Files:**
- Modify: `dev_on.bat`
- Modify: `tests/unit/test_dev_mode_contract.py`

**Interfaces:**
- Consumes: existing strict config validation, audio sync, `start_vllm_servers.bat`, Qdrant endpoint probe, API/watchdog starts.
- Produces: dashboard `start`, `node`, and `final` calls driven only by their corresponding success/failure checks.

- [ ] **Step 1: Write the failing Dev On contract tests**

```python
def test_dev_on_reports_each_real_readiness_gate_through_the_dashboard():
    dev_on = (REPO_ROOT / "dev_on.bat").read_text(encoding="utf-8").lower()
    for node in ("config", "wsl audio", "vllm", "qdrant", "api", "watchdog"):
        assert f'-node "{node}"' in dev_on
    assert "system ready — build mode" in dev_on
    assert "-noprofile" in dev_on
```

- [ ] **Step 2: Run the contract test to verify it fails**

Run: `python -m pytest tests/unit/test_dev_mode_contract.py::test_dev_on_reports_each_real_readiness_gate_through_the_dashboard -q`

Expected: FAIL because the launcher has no dashboard calls.

- [ ] **Step 3: Add the smallest batch integration**

At the start of `dev_on.bat`, define:

```bat
set "DASHBOARD=powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev_mode_dashboard.ps1""
%DASHBOARD% -Mode dev-on -Event start
```

After each existing successful gate, emit exactly one ready event, for example:

```bat
%DASHBOARD% -Mode dev-on -Event node -Node "Config" -State ready -Message "strict validation passed"
```

Before every existing `exit /b 1`, emit the corresponding blocked event with the same actionable failure reason. After API/watchdog launch, add bounded loopback/process checks before marking each node ready. Convert existing unqualified `powershell -Command` calls in this file to `powershell -NoProfile -Command`. On success emit:

```bat
%DASHBOARD% -Mode dev-on -Event final -State ready -Message "vLLM, Qdrant, API, watchdog, and WSL anchor verified"
```

- [ ] **Step 4: Run focused Dev On tests**

Run: `python -m pytest tests/unit/test_dev_mode_contract.py tests/unit/test_dev_mode_dashboard.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the Dev On integration**

```bash
git add dev_on.bat tests/unit/test_dev_mode_contract.py
git commit -m "feat(dev-mode): report build mode readiness"
```

### Task 3: Integrate Dev Off with bounded release events

**Files:**
- Modify: `dev_off.bat`
- Modify: `tests/unit/test_dev_mode_contract.py`

**Interfaces:**
- Consumes: existing `stop_vllm_servers.bat`, `wsl --shutdown`, API/watchdog termination, and intentionally retained Qdrant policy.
- Produces: a release receipt that distinguishes released resources from retained Qdrant.

- [ ] **Step 1: Write the failing Dev Off contract tests**

```python
def test_dev_off_reports_release_and_retained_qdrant_through_the_dashboard():
    dev_off = (REPO_ROOT / "dev_off.bat").read_text(encoding="utf-8").lower()
    for node in ("vllm", "wsl", "api", "watchdog", "qdrant"):
        assert f'-node "{node}"' in dev_off
    assert "open desktop — gpu services released" in dev_off
    assert "-noprofile" in dev_off
```

- [ ] **Step 2: Run the contract test to verify it fails**

Run: `python -m pytest tests/unit/test_dev_mode_contract.py::test_dev_off_reports_release_and_retained_qdrant_through_the_dashboard -q`

Expected: FAIL because the launcher has no dashboard calls.

- [ ] **Step 3: Add the smallest batch integration**

Emit a Dev Off `start` event before the existing stop flow. After `stop_vllm_servers.bat` and `wsl --shutdown`, use bounded checks to confirm `:38005` is absent and WSL has stopped before marking the nodes released. After API/watchdog termination, use bounded process/port checks before marking them released. Probe `http://127.0.0.1:6333/collections`; on success emit:

```bat
%DASHBOARD% -Mode dev-off -Event node -Node "Qdrant" -State retained -Message "loopback index service remains available"
%DASHBOARD% -Mode dev-off -Event final -State ready -Message "Qdrant retained on loopback"
```

Use `powershell -NoProfile` for every PowerShell call in this file. If a release verification fails, emit a blocked node and return nonzero without claiming OPEN DESKTOP.

- [ ] **Step 4: Run focused Dev Off tests**

Run: `python -m pytest tests/unit/test_dev_mode_contract.py tests/unit/test_dev_mode_dashboard.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the Dev Off integration**

```bash
git add dev_off.bat tests/unit/test_dev_mode_contract.py
git commit -m "feat(dev-mode): report open desktop release"
```

### Task 4: Verify the live toggle contract and operator documentation

**Files:**
- Modify: `docs/guides/llm/LLM_INFRASTRUCTURE.md`
- Modify: `docs/guides/llm/VLLM_SYSTEMD_SETUP.md`
- Test: `tests/unit/test_dev_mode_contract.py`
- Test: `tests/unit/test_dev_mode_dashboard.py`

**Interfaces:**
- Consumes: completed renderer and both launcher integrations.
- Produces: an operator-facing explanation of BUILD MODE, OPEN DESKTOP, retained Qdrant, and the user-closed receipt.

- [ ] **Step 1: Write the failing documentation/contract assertion**

```python
def test_dev_mode_docs_describe_operator_receipts_without_oh_my_posh_dependency():
    guide = (REPO_ROOT / "docs" / "guides" / "llm" / "LLM_INFRASTRUCTURE.md").read_text(encoding="utf-8").lower()
    assert "build mode" in guide
    assert "open desktop" in guide
    assert "oh my posh" not in guide
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/unit/test_dev_mode_contract.py::test_dev_mode_docs_describe_operator_receipts_without_oh_my_posh_dependency -q`

Expected: FAIL because the guide does not yet define the receipts.

- [ ] **Step 3: Document the operator contract**

Add a compact “Dev Mode Operator Receipt” subsection to `LLM_INFRASTRUCTURE.md` and a brief reference from `VLLM_SYSTEMD_SETUP.md`. State that Dev On verifies configuration, WSL audio, vLLM, Qdrant, API, watchdog, and anchor state; Dev Off verifies release of GPU/WSL/API/watchdog while retaining loopback Qdrant. State that the window remains open for user confirmation and that status text is authoritative over color.

- [ ] **Step 4: Run final narrow validation**

Run:

```bash
python -m pytest tests/unit/test_dev_mode_contract.py tests/unit/test_dev_mode_dashboard.py -q
python scripts/docs/doc_drift_lint.py
git diff --check
```

Expected: all tests and lint pass; no active documentation path violations.

- [ ] **Step 5: Run the live operator gates**

Run `dev_off.bat`, verify vLLM/API/watchdog are unavailable and Qdrant returns HTTP 200; then run `dev_on.bat`, verify vLLM `/v1/models`, API `/`, Qdrant `/collections`, and one WSL keepalive client group. Inspect the visible receipts before closing their windows.

- [ ] **Step 6: Commit the documentation and verification lane**

```bash
git add docs/guides/llm/LLM_INFRASTRUCTURE.md docs/guides/llm/VLLM_SYSTEMD_SETUP.md tests/unit/test_dev_mode_contract.py
git commit -m "docs(dev-mode): describe operator receipts"
```

## Self-Review

- Spec coverage: Tasks 1–3 cover the signal path, color-plus-text accessibility, real checks, first-failure stops, user-visible end states, retained Qdrant, and `-NoProfile` isolation. Task 4 covers documentation and live proof.
- Placeholder scan: no unresolved implementation placeholders remain; each runtime node and acceptance command is named.
- Type consistency: every batch call uses the same renderer parameters: `-Mode`, `-Event`, `-Node`, `-State`, `-Message`, and optional `-NoColor` for tests only.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-02-dev-mode-operator-dashboard.md`.

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task and review each lane.
2. **Inline Execution** — execute the tasks in this session using the execution skill, with checkpoints.
