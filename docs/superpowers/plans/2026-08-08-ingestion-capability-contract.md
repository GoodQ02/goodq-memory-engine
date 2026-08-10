<!-- DOC_BADGE: EXPERIMENTAL -->
<!-- DOC_STATUS: DRAFT_REVIEW -->
<!-- DOC_LAST_VERIFIED: 2026-08-08 -->

# Ingestion Capability Contract Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Emit an always-on ingestion capability receipt, reconcile capability intent with runtime behavior, and make installer profiles select only contract-valid packs.

**Architecture:** A pure capability-contract library normalizes the run's existing evidence into a receipt and validates a matrix from registry, catalog, and explicit runtime policies. The ingestion CLI is the sole receipt writer. The current recurrence report consumes the persisted receipt read-only. Installer staging consumes the validated profile selection.

**Tech Stack:** Python 3.10, PyYAML, JSON, pytest, PowerShell, NSIS.

## Global Constraints

- CPU Baseline is the minimum useful profile and runs without a GPU.
- GPU Enhanced contains every CPU Baseline pack plus compatible GPU packs.
- Public profiles select only sealed distributable assets; personal profiles may select sealed personal or agreement-gated assets only with local acceptance evidence.
- A core failure exits nonzero. Every skip, fallback, retry, blocked capability, and profile exclusion is durable and visible.
- No new service, database, runtime authority, public release, or managed-offline build belongs to this source-change phase.

---

## File Structure

- Create lib/ingestion_capability_contract.py: receipt schemas, classification, matrix validation, and profile selection.
- Create tests/unit/test_ingestion_capability_contract.py: receipt, matrix, and profile invariant tests.
- Modify cli/run_ingestion.py: sole terminal receipt writer and console renderer.
- Modify lib/control_recurrence_report.py: read-only receipt aggregation.
- Modify tests/unit/test_control_recurrence_output_contract.py: receipt/report parity.
- Create configs/installer_profile_contract.yaml: CPU, GPU, and personal profile declarations.
- Create scripts/install/build_capability_matrix.py: deterministic matrix builder/checker.
- Modify scripts/install/stage_dependencies.ps1, scripts/install/goodq4all_installer.nsi, and scripts/install/verify_offline_suite.ps1: selected-profile payload and verification.
- Modify tests/unit/test_offline_asset_catalog.py and tests/unit/test_installer_release_contract.py: distribution and profile contracts.
- Modify docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md, docs/bootstrap/OFFLINE_RELEASE_ASSET_MODEL.md, and docs/releases/ROADMAP.md: current authority and validation gates.

## Task 1: Build the pure capability receipt contract

**Files:**
- Create lib/ingestion_capability_contract.py
- Create tests/unit/test_ingestion_capability_contract.py

**Interfaces:**
- build_capability_receipt(run_id, profile, terminal_status, step_rows, warnings, scenes, evidence_paths) returns a JSON-safe dict.
- render_capability_receipt(receipt) returns terminal text.

- [ ] **Step 1: Write failing outcome tests**

~~~python
def test_optional_skip_is_degraded_not_core_failure() -> None:
    receipt = build_capability_receipt(
        run_id="run-1", profile="PUBLIC_CPU_BASELINE", terminal_status="completed",
        step_rows=[{"step": "image_ocr", "status": "skipped",
                    "extra": {"optional": True, "reason": "dependency_missing"}},
                   {"step": "audio_transcribe_local", "status": "ok"}],
        warnings=[], scenes=[], evidence_paths={},
    )
    assert receipt["outcome"] == "degraded"
    assert receipt["summary"]["required_core_failures"] == 0
    assert receipt["capabilities_by_step"]["image_ocr"]["classification"] == "enhancement_optional"

def test_core_transcription_failure_is_failed() -> None:
    receipt = build_capability_receipt(
        run_id="run-2", profile="PUBLIC_CPU_BASELINE", terminal_status="failed",
        step_rows=[{"step": "audio_transcribe_local", "status": "error", "error": "engine unavailable"}],
        warnings=[], scenes=[], evidence_paths={},
    )
    assert receipt["outcome"] == "failed"
    assert receipt["summary"]["required_core_failures"] == 1
~~~

- [ ] **Step 2: Verify the tests fail**

Run: conda run --no-capture-output -n goodq_core python -m pytest -q tests/unit/test_ingestion_capability_contract.py

Expected: FAIL because the contract module does not exist.

- [ ] **Step 3: Implement the contract**

~~~python
CAPABILITY_SCHEMA_VERSION = 1
RUNTIME_CAPABILITY_POLICIES = {
    "audio_transcribe_local": {"classification": "core_required", "status_surface": "transcript_meta", "fallbacks": []},
    "audio_embed_clap": {"classification": "enhancement_optional", "status_surface": "clap_meta", "fallbacks": ["wsl_unified_audio_embedding"]},
    "object_detect": {"classification": "enhancement_optional", "status_surface": "object_meta", "fallbacks": ["opencv_nanodet_cpu"]},
}
~~~

Implement pure normalization that retains requested/effective implementation, fallback chain, reason, affected scenes, and evidence paths. Unknown values are explicit unknown fields, never omitted.

- [ ] **Step 4: Add fallback and exclusion fixtures**

Add a GPU-to-CPU fixture that yields degraded with both paths retained, and a profile-exclusion fixture that yields not_applicable rather than skipped.

- [ ] **Step 5: Verify and commit**

Run: conda run --no-capture-output -n goodq_core python -m pytest -q tests/unit/test_ingestion_capability_contract.py

~~~powershell
git add lib/ingestion_capability_contract.py tests/unit/test_ingestion_capability_contract.py
git commit -m "feat: add ingestion capability receipt contract"
~~~

## Task 2: Make run_ingestion the always-on receipt writer

**Files:**
- Modify cli/run_ingestion.py
- Modify tests/unit/test_run_ingestion_step_observer_metadata.py
- Modify tests/unit/test_ingestion_capability_contract.py

**Interfaces:**
- Produces run-root/capability_receipt.json on normal completion and before every terminal failure exit.

- [ ] **Step 1: Write failing runner tests**

~~~python
def test_optional_failure_writes_degraded_receipt(tmp_path, monkeypatch) -> None:
    result = invoke_isolated_ingestion_with_optional_clap_failure(tmp_path, monkeypatch)
    receipt = json.loads((result.run_root / "capability_receipt.json").read_text(encoding="utf-8"))
    assert receipt["outcome"] == "degraded"
    assert receipt["capabilities_by_step"]["audio_embed_clap"]["reason"] == "optional_step_failed"

def test_core_failure_writes_receipt_before_nonzero_exit(tmp_path, monkeypatch) -> None:
    result = invoke_isolated_ingestion_with_core_transcript_failure(tmp_path, monkeypatch)
    assert result.exit_code != 0
    assert (result.run_root / "capability_receipt.json").is_file()
~~~

- [ ] **Step 2: Verify the runner tests fail**

Run: conda run --no-capture-output -n goodq_core python -m pytest -q tests/unit/test_run_ingestion_step_observer_metadata.py tests/unit/test_ingestion_capability_contract.py

Expected: FAIL because the receipt is absent.

- [ ] **Step 3: Add one finalizer**

~~~python
def _finalize_capability_receipt(*, terminal_status: str, results: list[dict], output: Path) -> dict:
    receipt = build_capability_receipt(
        run_id=str(_CURRENT_RUN_CONTEXT.get("run_id") or "unknown"),
        profile=str(_CURRENT_RUN_CONTEXT.get("profile") or "PUBLIC_CPU_BASELINE"),
        terminal_status=terminal_status,
        step_rows=_read_current_run_step_rows(),
        warnings=list(_CURRENT_RUN_CONTEXT.get("warnings") or []),
        scenes=_flatten_scene_outputs(results),
        evidence_paths=_current_run_evidence_paths(output),
    )
    _atomic_write_json(output.parent / "capability_receipt.json", receipt, indent=2)
    typer.echo(render_capability_receipt(receipt), err=receipt["outcome"] in {"blocked", "failed"})
    return receipt
~~~

Call the helper from normal completion and each terminal failure path. Do not allow a step, watchdog, or Control Agent to write a competing receipt.

- [ ] **Step 4: Preserve existing recovery evidence**

Map native_retry_mode, direct interpreter fallback, audio_backend_effective, and audio_backend_downgrade_reason into receipt rows. Preserve original error and effective path.

- [ ] **Step 5: Verify and commit**

Run: conda run --no-capture-output -n goodq_core python -m pytest -q tests/unit/test_run_ingestion_step_observer_metadata.py tests/unit/test_run_ingestion_modality_status.py tests/unit/test_ingestion_capability_contract.py

~~~powershell
git add cli/run_ingestion.py tests/unit/test_run_ingestion_step_observer_metadata.py tests/unit/test_ingestion_capability_contract.py
git commit -m "feat: emit terminal ingestion capability receipt"
~~~

## Task 3: Have the existing control report aggregate the receipt

**Files:**
- Modify lib/control_recurrence_report.py
- Modify cli/control_recurrence_report.py
- Modify tests/unit/test_control_recurrence_output_contract.py

**Interfaces:**
- capability_outcome is a read-only top-level recurrence-report field.

- [ ] **Step 1: Write a failing receipt/report parity test**

~~~python
def test_recurrence_report_reads_receipt_without_reclassification(tmp_path: Path) -> None:
    reports_root, run_root = _write_fixture_run(tmp_path, "receipt_run", runtime_run_id="r1", video_id="v1", step_rows=[])
    _write_json(run_root / "capability_receipt.json", {"schema_version": 1, "outcome": "degraded", "summary": {"optional_skips": 2}})
    report = build_control_recurrence_report(run_id=run_root.name, reports_root=reports_root)
    assert report["capability_outcome"]["status"] == "degraded"
    assert report["capability_outcome"]["source"] == "capability_receipt.json"
~~~

- [ ] **Step 2: Verify the report test fails**

Run: conda run --no-capture-output -n goodq_core python -m pytest -q tests/unit/test_control_recurrence_output_contract.py

Expected: FAIL because capability_outcome is absent.

- [ ] **Step 3: Implement the passive reader**

~~~python
def _load_capability_outcome(run_root: Path) -> dict:
    path = run_root / "capability_receipt.json"
    if not path.is_file():
        return {"status": "not_available", "source": "capability_receipt.json", "warnings": ["receipt_missing"]}
    payload = _safe_read_json_dict(path)
    return {"status": payload.get("outcome", "unknown"), "source": "capability_receipt.json",
            "summary": payload.get("summary", {}), "warnings": []}
~~~

Render Capability Outcome in the existing report. It must not start services or mutate configuration.

- [ ] **Step 4: Verify and commit**

Run: conda run --no-capture-output -n goodq_core python -m pytest -q tests/unit/test_control_recurrence_output_contract.py tests/unit/test_control_recurrence_report.py tests/unit/test_control_recurrence_recommendations.py

~~~powershell
git add lib/control_recurrence_report.py cli/control_recurrence_report.py tests/unit/test_control_recurrence_output_contract.py
git commit -m "feat: report ingestion capability outcomes"
~~~

## Task 4: Reconcile runtime, registry, catalog, and selection semantics

**Files:**
- Modify lib/ingestion_capability_contract.py
- Create scripts/install/build_capability_matrix.py
- Modify tests/unit/test_ingestion_capability_contract.py
- Modify tests/unit/test_offline_asset_catalog.py

**Interfaces:**
- build_capability_matrix(registry, catalog, runtime_policies) returns matrix evidence.
- validate_profile_selection(matrix, profile) returns selected assets or raises a deterministic conflict.
- CLI: python scripts/install/build_capability_matrix.py --check.

- [ ] **Step 1: Write failing contradiction tests**

~~~python
def test_matrix_rejects_unreported_required_runtime_path() -> None:
    with pytest.raises(ValueError, match="runtime classification conflict"):
        build_capability_matrix(
            registry={"caption": {"classification": "REQUIRED_FIRST_LAUNCH"}},
            catalog={"caption": eligible_asset()},
            runtime_policies={"caption": {"classification": "enhancement_optional", "status_surface": None}},
        )

def test_matrix_rejects_public_personal_asset_selection() -> None:
    with pytest.raises(ValueError, match="public profile selects non-distributable asset"):
        validate_profile_selection(matrix_with_personal_asset(), "PUBLIC_GPU_ENHANCED")
~~~

- [ ] **Step 2: Verify the matrix tests fail**

Run: conda run --no-capture-output -n goodq_core python -m pytest -q tests/unit/test_ingestion_capability_contract.py tests/unit/test_offline_asset_catalog.py

Expected: FAIL because the matrix builder does not exist.

- [ ] **Step 3: Implement deterministic validation**

Every active runtime step needs an explicit policy row. Reject unclassified active steps, missing status surfaces, registry/catalog revision mismatches, public personal selections, and runtime assets absent from the catalog.

- [ ] **Step 4: Add deterministic CLI behavior**

Check mode validates without writing. Normal mode writes sorted capability_matrix.json only after every conflict check passes.

- [ ] **Step 5: Verify and commit**

~~~powershell
conda run --no-capture-output -n goodq_core python -m pytest -q tests/unit/test_ingestion_capability_contract.py tests/unit/test_offline_asset_catalog.py
conda run --no-capture-output -n goodq_core python scripts/install/build_capability_matrix.py --check
git add lib/ingestion_capability_contract.py scripts/install/build_capability_matrix.py tests/unit/test_ingestion_capability_contract.py tests/unit/test_offline_asset_catalog.py
git commit -m "feat: reconcile runtime and installer capabilities"
~~~

## Task 5: Make installer profile selection complete and enforceable

**Files:**
- Create configs/installer_profile_contract.yaml
- Modify scripts/install/stage_dependencies.ps1
- Modify scripts/install/goodq4all_installer.nsi
- Modify scripts/install/verify_offline_suite.ps1
- Modify tests/unit/test_installer_release_contract.py
- Modify tests/unit/test_offline_asset_catalog.py

**Interfaces:**
- Public profile names: PUBLIC_CPU_BASELINE and PUBLIC_GPU_ENHANCED.
- Personal profile name: PERSONAL_AIR_GAP.
- Staging writes selected_capabilities.json; install receipt records its digest.

- [ ] **Step 1: Write failing profile tests**

~~~python
def test_public_gpu_is_superset_of_public_cpu() -> None:
    profiles = load_profile_contract(REPO_ROOT / "configs/installer_profile_contract.yaml")
    assert set(profiles["PUBLIC_CPU_BASELINE"]["include_packs"]) <= set(profiles["PUBLIC_GPU_ENHANCED"]["resolved_packs"])

def test_public_profile_never_selects_personal_asset() -> None:
    assets = resolve_profile_assets("PUBLIC_GPU_ENHANCED")
    assert all(row["status"] == "eligible" and row["vault_scope"] == "personal_and_distributable" for row in assets)
~~~

- [ ] **Step 2: Verify the installer tests fail**

Run: conda run --no-capture-output -n goodq_core python -m pytest -q tests/unit/test_installer_release_contract.py tests/unit/test_offline_asset_catalog.py

Expected: FAIL because no profile contract exists.

- [ ] **Step 3: Add the declarative profile contract**

~~~yaml
profiles:
  PUBLIC_CPU_BASELINE:
    distribution: public
    include_hardware: [cpu]
    include_statuses: [eligible]
    include_packs: [core_cpu, vision_cpu, audio_cpu, object_detection_cpu]
  PUBLIC_GPU_ENHANCED:
    distribution: public
    extends: PUBLIC_CPU_BASELINE
    include_hardware: [cpu, gpu]
    include_statuses: [eligible]
    include_packs: [audio_gpu, local_vlm_gpu, object_detection_gpu]
  PERSONAL_AIR_GAP:
    distribution: personal
    extends: PUBLIC_GPU_ENHANCED
    include_hardware: [cpu, gpu]
    include_statuses: [eligible, personal_only, agreement_gated]
    acceptance_required: true
~~~

The resolver expands extends before filtering. It requires a sealed manifest for every asset and local acceptance evidence for each non-public asset.

- [ ] **Step 4: Wire staging, installer, and verification**

stage_dependencies.ps1 accepts ProfileManifest and refuses missing, unsealed, mismatched, or disallowed assets. It writes selected_capabilities.json. NSIS copies only that selected staged payload and stores profile plus selected_capabilities_sha256 in install_receipt.json. The offline suite validates digest, declared payload existence, and absence of undeclared packageable model files.

- [ ] **Step 5: Verify and commit**

~~~powershell
conda run --no-capture-output -n goodq_core python -m pytest -q tests/unit/test_installer_release_contract.py tests/unit/test_installer_paths.py tests/unit/test_offline_asset_catalog.py tests/unit/test_ingestion_capability_contract.py
conda run --no-capture-output -n goodq_core python scripts/install/build_capability_matrix.py --check
git add configs/installer_profile_contract.yaml scripts/install/stage_dependencies.ps1 scripts/install/goodq4all_installer.nsi scripts/install/verify_offline_suite.ps1 tests/unit/test_installer_release_contract.py tests/unit/test_offline_asset_catalog.py
git commit -m "feat: enforce complete installer capability profiles"
~~~

## Task 6: Lock documentation and the final source gate

**Files:**
- Modify docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md
- Modify docs/bootstrap/OFFLINE_RELEASE_ASSET_MODEL.md
- Modify docs/releases/ROADMAP.md
- Modify tests/unit/test_control_recurrence_output_contract.py

- [ ] **Step 1: Write one end-to-end fixture**

~~~python
def test_receipt_matrix_and_report_agree_for_cpu_fallback(tmp_path: Path) -> None:
    run_root = build_fixture_run_with_gpu_to_cpu_fallback(tmp_path)
    receipt = load_capability_receipt(run_root)
    report = build_control_recurrence_report(run_root=run_root)
    assert receipt["outcome"] == "degraded"
    assert report["capability_outcome"]["status"] == receipt["outcome"]
    assert receipt["summary"]["recovered_fallbacks"] == 1
~~~

- [ ] **Step 2: Document evidence order and profiles**

State that receipt rows point to, but never override, step logs, warnings, results, and manifests. Document complete CPU, additive GPU, and sealed personal-air-gap selection exactly as implemented.

- [ ] **Step 3: Run final source gates**

~~~powershell
conda run --no-capture-output -n goodq_core python -m pytest -q tests/unit/test_ingestion_capability_contract.py tests/unit/test_run_ingestion_step_observer_metadata.py tests/unit/test_run_ingestion_modality_status.py tests/unit/test_control_recurrence_output_contract.py tests/unit/test_control_recurrence_report.py tests/unit/test_control_recurrence_recommendations.py tests/unit/test_installer_release_contract.py tests/unit/test_installer_paths.py tests/unit/test_offline_asset_catalog.py
conda run --no-capture-output -n goodq_core python scripts/install/build_capability_matrix.py --check
conda run --no-capture-output -n goodq_core python scripts/docs/doc_drift_lint.py
~~~

Expected: all pass. A contradiction, missing status surface, public/private leak, or documentation authority violation blocks the later rebuild gate.

- [ ] **Step 4: Commit and prepare the separate runtime gate**

~~~powershell
git add docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md docs/bootstrap/OFFLINE_RELEASE_ASSET_MODEL.md docs/releases/ROADMAP.md tests/unit/test_control_recurrence_output_contract.py
git commit -m "docs: codify ingestion capability profiles"
~~~

After the source gate passes, run one managed-offline build in a new output root, install on an approved clean target, run the offline suite, then process exactly one isolated scene. Receipt, manifest, step log, and read-only recurrence report must agree before release work resumes.

## Self-Review

- Spec coverage: Tasks 1–3 deliver the receipt and existing operator aggregation; Tasks 4–5 reconcile and enforce public/personal CPU/GPU selection; Task 6 provides source and real-boundary validation.
- Placeholder scan: each task has named files, interfaces, tests, expected outcomes, validation commands, and a commit boundary.
- Type consistency: sole receipt filename capability_receipt.json; public profiles PUBLIC_CPU_BASELINE and PUBLIC_GPU_ENHANCED; personal profile PERSONAL_AIR_GAP.

## Execution Handoff

Plan complete and saved to docs/superpowers/plans/2026-08-08-ingestion-capability-contract.md.

Recommended execution is inline, task-by-task, with review gates after Tasks 3 and 5. The managed-offline build and clean-device scene witness remain the final, separate runtime validation gate.
