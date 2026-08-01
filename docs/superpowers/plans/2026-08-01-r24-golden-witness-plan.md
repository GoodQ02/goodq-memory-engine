# R-24 Golden Witness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only preflight and isolated one-scene Golden Witness that proves the governed multimodal pipeline without canonical-memory promotion.

**Architecture:** A new `cli/golden_witness.py` owns witness-only configuration and receipts; it calls existing config, tool-resolution, and canonical ingestion interfaces rather than creating a second ingest engine. The first deliverable is preflight-only. The isolated run and human semantic acceptance remain separate approval gates.

**Tech Stack:** Python 3.12+, pytest, existing GoodQ config loader/tool resolver/model provisioner, canonical `cli.run_ingestion`.

## Global Constraints

- Input: `samples/ingestion/smoke_test/seinfeld_s01e01_clip.mp4`.
- Record SHA-256 and stream metadata before any run.
- `ingestion_isolation: true` is mandatory for a witness run.
- No canonical SQLite, knowledge graph, active-Qdrant promotion, model download, service/firewall change, or source-media mutation.
- All generated output stays below one uniquely named witness root.
- Preflight failure is explicit and must prevent the run.
- Human approval is required before the isolated run and before any later promotion.

---

### Task 1: Witness preflight contract

**Files:**
- Create: `cli/golden_witness.py`
- Create: `tests/unit/test_golden_witness_preflight.py`
- Modify: `docs/releases/ROADMAP.md`

**Interfaces:**
- Produces: `WitnessAuthorityError(RuntimeError)`.
- Produces: `build_witness_config(artifact_root: Path, input_path: Path) -> dict[str, Any]`.
- Produces: `preflight_witness(artifact_root: Path, input_path: Path) -> dict[str, Any]`.

- [ ] **Step 1: Write failing preflight tests**

```python
def test_preflight_records_input_identity_and_never_promotes(tmp_path: Path) -> None:
    receipt = preflight_witness(tmp_path / "witness", FIXTURE)
    assert receipt["status"] == "ready"
    assert receipt["input"]["sha256"] == sha256_file(FIXTURE)
    assert receipt["config"]["ingestion_isolation"] is True
    assert receipt["config"]["promotion_enabled"] is False

def test_preflight_rejects_model_cache_inside_witness_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("steps.common.model_provisioner.resolve_models_root", lambda: tmp_path / "witness" / "models")
    with pytest.raises(WitnessAuthorityError, match="model cache.*inside witness root"):
        build_witness_config(tmp_path / "witness", FIXTURE)
```

- [ ] **Step 2: Run the new tests to verify RED**

Run: `conda run --no-capture-output -n goodq_core python -m pytest tests/unit/test_golden_witness_preflight.py -q`

Expected: FAIL because the module and functions do not exist.

- [ ] **Step 3: Implement the minimal preflight**

```python
class WitnessAuthorityError(RuntimeError):
    pass

def build_witness_config(artifact_root: Path, input_path: Path) -> dict[str, Any]:
    root = artifact_root.resolve()
    models_root = resolve_models_root().resolve()
    try:
        models_root.relative_to(root)
    except ValueError:
        pass
    else:
        raise WitnessAuthorityError("Canonical model cache resolved inside witness root")
    return {"ingestion_isolation": True, "promotion_enabled": False, "paths": {"models_cache": str(models_root)}}
```

Implement `preflight_witness` to hash the input, call `ffprobe` through the existing tool resolver, verify FFmpeg and Tesseract bindings on a copied config, record CUDA/device policy without loading models, and return JSON-serializable facts only.

- [ ] **Step 4: Run focused validation**

Run: `conda run --no-capture-output -n goodq_core python -m pytest tests/unit/test_golden_witness_preflight.py tests/unit/test_tool_resolver.py -q`

Expected: PASS; no witness-root content other than an optional explicit receipt file is created.

- [ ] **Step 5: Document and commit**

Add an R-24 roadmap checkpoint that preflight is read-only and does not authorize a witness run. Commit:

```bash
git add cli/golden_witness.py tests/unit/test_golden_witness_preflight.py docs/releases/ROADMAP.md
git commit -m "feat(r24): add isolated witness preflight"
```

### Task 2: Isolated-run receipt preparation

**Files:**
- Modify: `cli/golden_witness.py`
- Modify: `tests/unit/test_golden_witness_preflight.py`

**Interfaces:**
- Consumes: `preflight_witness(artifact_root, input_path)`.
- Produces: `prepare_witness_run(artifact_root: Path, input_path: Path) -> dict[str, Any]`.

- [ ] **Step 1: Write a failing containment test**

```python
def test_prepare_witness_run_scopes_every_mutable_path_to_witness_root(tmp_path: Path) -> None:
    receipt = prepare_witness_run(tmp_path / "witness", FIXTURE)
    root = (tmp_path / "witness").resolve()
    for path in receipt["mutable_paths"].values():
        Path(path).resolve().relative_to(root)
    assert receipt["runner"]["module"] == "cli.run_ingestion"
    assert receipt["promotion_enabled"] is False
```

- [ ] **Step 2: Run the containment test to verify RED**

Run: `conda run --no-capture-output -n goodq_core python -m pytest tests/unit/test_golden_witness_preflight.py::test_prepare_witness_run_scopes_every_mutable_path_to_witness_root -q`

Expected: FAIL because `prepare_witness_run` does not exist.

- [ ] **Step 3: Implement only a receipt, not execution**

Create the unique epoch/run identifiers and all mutable witness paths below the supplied root. Store canonical-runner arguments in the receipt, but do not invoke `cli.run_ingestion`.

- [ ] **Step 4: Run validation and commit**

Run: `conda run --no-capture-output -n goodq_core python -m pytest tests/unit/test_golden_witness_preflight.py -q`

Commit:

```bash
git add cli/golden_witness.py tests/unit/test_golden_witness_preflight.py
git commit -m "feat(r24): prepare contained witness receipt"
```

### Task 2A: Seal the prepared receipt without execution

**Files:**
- Modify: `cli/golden_witness.py`
- Modify: `tests/unit/test_golden_witness_preflight.py`

The in-memory Task 2 receipt cannot safely be an execution input until it has
been inspected and sealed. This bridge may create exactly one fresh witness
root containing `prepared-receipt.json`; it must reject an existing root or any
mutable path that escapes the root. It does not copy media, create processing
directories, load models, access stores, or invoke the canonical runner.

- [ ] Write a failing test proving that sealing creates only the receipt file.
- [ ] Implement `seal_prepared_receipt(prepared_receipt) -> Path` with a
  fresh-root and path-containment guard.
- [ ] Run the focused preflight tests and commit the seal-only gate.

### Task 2B: Add a fail-closed runner configuration boundary

**Files:**
- Modify: `cli/run_ingestion.py`
- Create: `tests/unit/test_run_ingestion_isolated_config.py`

The historical R-24 planner projected a runner `--config` argument that the
canonical runner did not accept. Add that option only for a JSON snapshot that
declares witness isolation, disables promotion, keeps every mutable runtime path
under the witness root, preserves the model cache outside it, and selects a
noncanonical loopback Qdrant endpoint. Existing non-witness invocations keep
their current configuration path.

- [ ] Write failing acceptance/rejection tests for isolated snapshot loading.
- [ ] Add the CLI option and fail-closed validation without starting services.
- [ ] Run focused runner and R-24 regression tests, then commit.

### Task 2C: Seal the runtime snapshot with the receipt

**Files:**
- Modify: `cli/golden_witness.py`
- Modify: `tests/unit/test_golden_witness_preflight.py`

The sealed plan now needs both the receipt and the runner snapshot. Produce
exactly these two files below a new witness root. The snapshot must be accepted
by the canonical runner's isolation validator before it is treated as sealed.
Do not launch the separate Qdrant endpoint or invoke the runner in this task.

- [ ] Write a failing consumer-validation test for the sealed snapshot.
- [ ] Build the witness-owned paths and noncanonical loopback Qdrant endpoint.
- [ ] Run focused validation and commit the sealed-plan artifact contract.

### Task 3: Operator-approved witness execution and acceptance report

**Files:**
- Modify: `cli/golden_witness.py`
- Create: `tests/unit/test_golden_witness_acceptance.py`

**Interfaces:**
- Consumes: the Task 2 prepared receipt and explicit operator approval.
- Produces: `execute_witness(prepared_receipt: Path) -> dict[str, Any]`.
- Produces: `render_acceptance_report(receipt: dict[str, Any]) -> dict[str, Any]`.

- [ ] **Step 1: Write failing approval and failure-semantics tests**

```python
def test_execute_witness_requires_explicit_approval(tmp_path: Path) -> None:
    with pytest.raises(WitnessAuthorityError, match="explicit approval"):
        execute_witness(tmp_path / "prepared.json")

def test_acceptance_report_marks_missing_summary_as_failed() -> None:
    report = render_acceptance_report({"stages": {"summary": {"status": "missing"}}})
    assert report["status"] == "failed"
    assert report["failed_stage"] == "summary"
```

- [ ] **Step 2: Run tests to verify RED**

Run: `conda run --no-capture-output -n goodq_core python -m pytest tests/unit/test_golden_witness_acceptance.py -q`

Expected: FAIL because execution and reporting are not implemented.

- [ ] **Step 3: Implement the approval-gated execution wrapper**

Invoke only the canonical `cli.run_ingestion` command from the prepared receipt. Read back isolated artifacts, record scene/transcript/visual/audio/vector stage facts, and request a configured local factual summary. Do not promote, retry into success, or delete artifacts.

- [ ] **Step 4: Run the approval gate**

Before executing against the Seinfeld fixture, present the exact prepared receipt, witness root, expected input SHA-256, and local model selection to the user. Wait for explicit approval.

- [ ] **Step 5: Run exactly one isolated witness and produce acceptance report**

Run the prepared command once. Report factual summary, candidate names, scene boundaries, all stage statuses, and the explicit `promotion_enabled: false` proof. Wait for the user’s semantic acceptance response.

- [ ] **Step 6: Validate, document, and commit**

Run: `conda run --no-capture-output -n goodq_core python -m pytest tests/unit/test_golden_witness_preflight.py tests/unit/test_golden_witness_acceptance.py -q`

Run: `git diff --check`

Commit:

```bash
git add cli/golden_witness.py tests/unit/test_golden_witness_preflight.py tests/unit/test_golden_witness_acceptance.py docs/releases/ROADMAP.md
git commit -m "feat(r24): add approval-gated golden witness"
```

## Plan review

- Spec coverage: Tasks 1-3 cover preflight, containment, isolated evidence, local summary, and human acceptance.
- Placeholder scan: no incomplete implementation markers remain.
- Scope: execution is deliberately deferred behind a prepared-receipt approval gate; no R-24 Qdrant profile expansion or historical artifact import is included.
