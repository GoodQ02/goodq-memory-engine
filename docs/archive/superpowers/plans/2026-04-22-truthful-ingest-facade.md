<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: REFERENCE_ONLY -->
<!-- DOC_CANONICAL_POINTER: docs/reference/CLI-REFERENCE.md -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# Truthful Ingest Facade Implementation Plan

> Status note (2026-05-17): This is a historical implementation plan, not an
> active TODO queue. The active ingest facade is documented in
> `docs/reference/API.md` and
> `docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a truthful ingest facade that stages requests into the canonical inbox, records a durable request ledger, and exposes request-centric status without creating a second ingest engine.

**Architecture:** The API remains a controlled entry point only. `POST /api/ingest/submit` validates and stages a request into `import_inbox`, writes a durable request record, and returns a `request_id`; `GET /api/ingest/status/{request_id}` resolves lifecycle state from the request ledger outward into watchdog/runtime artifacts. Watchdog and `cli.run_ingestion` remain the canonical execution path.

**Tech Stack:** FastAPI, Pydantic, pathlib, JSON request ledger, existing config/runtime path loaders, watchdog state file, targeted pytest coverage.

---

### Task 1: Define the request-ledger contract

**Files:**
- Create: `api/utils/ingest_requests.py`
- Modify: `api/utils/response_models.py`
- Test: `tests/unit/test_ingest_request_ledger.py`

- [ ] **Step 1: Write the failing tests for request records**

```python
from pathlib import Path

from api.utils.ingest_requests import (
    IngestRequestRecord,
    IngestRequestStore,
    derive_pickup_estimate,
)


def test_request_store_round_trips_record(tmp_path: Path) -> None:
    store = IngestRequestStore(tmp_path / "ingest_requests")
    record = IngestRequestRecord(
        request_id="req_123",
        status="submitted",
        source_path="<LOCAL_MEDIA_ROOT>/example.mp4",
        staged_path="<GOODQ_DATA_ROOT>/GoodQ_Data/import_inbox/example__req_123.mp4",
        filename="example.mp4",
        file_type="video",
        file_size_bytes=1024,
        file_hash="abc123",
        created_at="2026-04-22T00:00:00Z",
        queue_depth_snapshot=2,
        watchdog_detection_window_seconds=5,
        pickup_estimate="best_effort",
    )

    store.save(record)
    loaded = store.load("req_123")

    assert loaded is not None
    assert loaded.request_id == "req_123"
    assert loaded.staged_path.endswith("example__req_123.mp4")


def test_pickup_estimate_is_best_effort() -> None:
    estimate = derive_pickup_estimate(queue_depth_snapshot=3, watchdog_detection_window_seconds=5)

    assert estimate["mode"] == "best_effort"
    assert estimate["queue_depth_snapshot"] == 3
    assert estimate["watchdog_detection_window_seconds"] == 5
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
conda run -n goodq_core python -m pytest tests/unit/test_ingest_request_ledger.py -q
```

Expected: FAIL because `api.utils.ingest_requests` and the new response fields do not exist yet.

- [ ] **Step 3: Add the minimal request-ledger implementation**

```python
class IngestRequestRecord(BaseModel):
    request_id: str
    status: str
    source_path: str
    staged_path: str
    filename: str
    file_type: str
    file_size_bytes: int
    file_hash: str
    created_at: str
    queue_depth_snapshot: int
    watchdog_detection_window_seconds: int
    pickup_estimate: Dict[str, Any]
    run_id: Optional[str] = None
    completed_at: Optional[str] = None
    failure_reason: Optional[str] = None


class IngestRequestStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
```

Also extend `response_models.py` with typed outward surfaces for:
- submit response
- ingest status response
- pickup estimate metadata

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```powershell
conda run -n goodq_core python -m pytest tests/unit/test_ingest_request_ledger.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add api/utils/ingest_requests.py api/utils/response_models.py tests/unit/test_ingest_request_ledger.py docs/superpowers/plans/2026-04-22-truthful-ingest-facade.md
git commit -m "feat: add ingest request ledger contract"
```

### Task 2: Add the submit facade over the canonical inbox

**Files:**
- Modify: `api/routes/system.py`
- Modify: `api/utils/response_models.py`
- Modify: `api/utils/ingest_requests.py`
- Test: `tests/unit/test_ingest_submit_route.py`

- [ ] **Step 1: Write the failing submit-route tests**

```python
import asyncio
from pathlib import Path


def test_submit_stages_file_and_returns_request_handle(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video-bytes")

    response = asyncio.run(system_module.submit_ingest(system_module.IngestSubmitRequest(
        file_path=str(source),
        confirmation_token="confirmed",
        policy_profile="local_facade",
    )))

    assert response.status == "submitted"
    assert response.allowed is True
    assert response.request_id
    assert response.staged_path.endswith(".mp4")
    assert response.pickup_estimate["mode"] == "best_effort"


def test_submit_rejects_missing_confirmation_token(tmp_path: Path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video-bytes")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(system_module.submit_ingest(system_module.IngestSubmitRequest(
            file_path=str(source),
            policy_profile="local_facade",
        )))

    assert exc.value.status_code == 400
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
conda run -n goodq_core python -m pytest tests/unit/test_ingest_submit_route.py -q
```

Expected: FAIL because the submit route and its request model do not exist yet.

- [ ] **Step 3: Implement the minimal submit route**

```python
@router.post("/submit", response_model=IngestSubmitResponse)
async def submit_ingest(request: IngestSubmitRequest = Body(...)):
    if request.confirmation_token != "confirmed":
        raise HTTPException(status_code=400, detail="confirmation_token required")

    source_path = Path(request.file_path)
    # validate supported type, hash file, copy to import_inbox with request-id suffix,
    # write request record, return request handle
```

Required behavior:
- enforce explicit confirmation token
- require `policy_profile`
- validate file exists and is a supported ingest type
- compute hash before staging
- detect duplicates via request ledger + watchdog registry if feasible
- copy into canonical `import_inbox`
- write request record
- return `request_id`, staged path, queue snapshot, and best-effort pickup estimate

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```powershell
conda run -n goodq_core python -m pytest tests/unit/test_ingest_submit_route.py tests/unit/test_ingest_request_ledger.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add api/routes/system.py api/utils/response_models.py api/utils/ingest_requests.py tests/unit/test_ingest_submit_route.py tests/unit/test_ingest_request_ledger.py docs/superpowers/plans/2026-04-22-truthful-ingest-facade.md
git commit -m "feat: add truthful ingest submit facade"
```

### Task 3: Add request-centric status resolution

**Files:**
- Modify: `api/routes/system.py`
- Modify: `api/utils/ingest_requests.py`
- Test: `tests/unit/test_ingest_status_route.py`

- [ ] **Step 1: Write the failing status-route tests**

```python
import asyncio


def test_status_reports_waiting_for_watchdog_when_staged_file_is_in_inbox(tmp_path: Path) -> None:
    store = seed_request_store(tmp_path, status="submitted", staged_exists=True)

    response = asyncio.run(system_module.get_ingest_status("req_123"))

    assert response.request_id == "req_123"
    assert response.status in {"staged", "waiting_for_watchdog"}
    assert response.run_id is None


def test_status_promotes_to_completed_when_watchdog_registry_has_success(tmp_path: Path) -> None:
    store = seed_request_store(tmp_path, status="submitted", staged_exists=False)
    seed_watchdog_registry(tmp_path, file_hash="abc123", status="success", run_id="run_456")

    response = asyncio.run(system_module.get_ingest_status("req_123"))

    assert response.status == "completed"
    assert response.run_id == "run_456"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
conda run -n goodq_core python -m pytest tests/unit/test_ingest_status_route.py -q
```

Expected: FAIL because the status route and state resolver do not exist yet.

- [ ] **Step 3: Implement status resolution**

```python
@router.get("/status/{request_id}", response_model=IngestStatusResponse)
async def get_ingest_status(request_id: str):
    record = store.load(request_id)
    if not record:
        raise HTTPException(status_code=404, detail="request not found")
    # resolve through ledger -> inbox presence -> watchdog state file -> latest runtime clues
```

Required outward states:
- `submitted`
- `staged`
- `waiting_for_watchdog`
- `completed`
- `failed`
- `duplicate`

This route must remain request-centric. It should not invent a second job engine.

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```powershell
conda run -n goodq_core python -m pytest tests/unit/test_ingest_status_route.py tests/unit/test_ingest_submit_route.py tests/unit/test_ingest_request_ledger.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add api/routes/system.py api/utils/ingest_requests.py tests/unit/test_ingest_status_route.py tests/unit/test_ingest_submit_route.py tests/unit/test_ingest_request_ledger.py docs/superpowers/plans/2026-04-22-truthful-ingest-facade.md
git commit -m "feat: add request-centric ingest status surface"
```

### Task 4: Align docs and re-audit the boundary

**Files:**
- Modify: `docs/reference/API.md`
- Modify: `docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md`
- Modify: `docs/README.md`
- Test: `tests/unit/test_system_route_policy.py`

- [ ] **Step 1: Write the failing doc/truth assertions if needed**

```python
def test_ingest_policy_docs_reference_submit_and_status_facade():
    text = Path("docs/reference/API.md").read_text(encoding="utf-8")
    assert "POST /api/ingest/submit" in text
    assert "GET /api/ingest/status/{request_id}" in text
```

- [ ] **Step 2: Run the doc-facing test to verify it fails**

Run:

```powershell
conda run -n goodq_core python -m pytest tests/unit/test_system_route_policy.py -q
```

Expected: FAIL only if new assertions are added; otherwise skip this step and update docs directly.

- [ ] **Step 3: Update active docs with the truthful facade**

Required doc truth:
- API submit/status routes are explicit facade surfaces
- execution remains owned by watchdog + `cli.run_ingestion`
- `reindex` and `reload` remain operator-only

- [ ] **Step 4: Run final targeted verification**

Run:

```powershell
conda run -n goodq_core python -m pytest tests/unit/test_ingest_request_ledger.py tests/unit/test_ingest_submit_route.py tests/unit/test_ingest_status_route.py tests/unit/test_system_route_policy.py tests/unit/test_api_surface_truth.py tests/unit/test_system_engine_truth.py -q
conda run -n goodq_core python scripts/docs/doc_drift_lint.py
```

Expected:
- all targeted tests pass
- doc drift lint passes

- [ ] **Step 5: Commit**

```powershell
git add api/routes/system.py api/utils/ingest_requests.py api/utils/response_models.py docs/reference/API.md docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md docs/README.md tests/unit/test_ingest_request_ledger.py tests/unit/test_ingest_submit_route.py tests/unit/test_ingest_status_route.py docs/superpowers/plans/2026-04-22-truthful-ingest-facade.md
git commit -m "feat: add truthful ingest facade over watchdog runtime"
```
