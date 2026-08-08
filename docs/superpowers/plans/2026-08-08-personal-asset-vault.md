# Personal Asset Vault Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an immutable, append-only personal asset vault and a complete
asset-acquisition catalog so every GoodQ runtime reference is classified before
it becomes an installer input.

**Architecture:** A small Python vault module owns content hashing, source
inventory, duplicate detection, atomic snapshot sealing, and source cleanup
only after verification. A versioned catalog records every runtime, optional,
and installer-referenced asset with its source, license disposition, hardware
profile, and pack eligibility. Pack generation remains a subsequent plan and
can consume only sealed vault snapshots.

**Tech Stack:** Python 3.10 standard library, PyYAML, JSON manifests, pytest,
PowerShell operator commands.

## Global Constraints

- Use `GOODQ_ASSET_VAULT_ROOT` for the personal archive; never hardcode a drive
  root in active source or documentation.
- Preserve raw source files byte-for-byte; write manifests and terms beside,
  never into, the source material.
- Create a new immutable snapshot when any source member differs; never modify
  an existing sealed snapshot.
- Keep incomplete transfers in a caller-selected quarantine directory and never
  accept them as snapshot input.
- Require a SHA-256 for every retained source member and explicit terms files
  for every source snapshot.
- Treat a source as distributable only when the source terms for the exact
  artifact permit the intended distribution; personal-only and agreement-gated
  sources may never enter a public pack.
- Do not install GoodQ on the canonical desktop, alter runtime data, or build
  an installer in this plan.

---

## File Structure

- Create `scripts/assets/__init__.py`: package marker.
- Create `scripts/assets/personal_asset_vault.py`: inventory, hash, seal,
  duplicate, and cleanup command-line implementation.
- Create `configs/offline_asset_catalog.yaml`: complete asset classification
  contract derived from active runtime and installer references.
- Create `tests/unit/test_personal_asset_vault.py`: vault invariants and NRC
  source-snapshot tests.
- Create `tests/unit/test_offline_asset_catalog.py`: catalog coverage tests.
- Modify `docs/releases/OFFLINE_PAYLOAD_ELIGIBILITY.md`: link the catalog and
  distinguish source-vault eligibility from pack eligibility.
- Modify `docs/releases/ROADMAP.md`: record the sealed NRC snapshot and asset
  catalog verification after the implementation succeeds.

### Task 1: Establish the complete asset catalog contract

**Files:**
- Create: `configs/offline_asset_catalog.yaml`
- Create: `tests/unit/test_offline_asset_catalog.py`

**Interfaces:**
- Consumes: `configs/model_registry.yaml`, `scripts/bootstrap_models.py`,
  `scripts/install/goodq4all_installer.nsi`, and
  `docs/releases/OFFLINE_PAYLOAD_ELIGIBILITY.md`.
- Produces: YAML records with `asset_id`, `kind`, `source`, `revision`,
  `license_class`, `vault_scope`, `pack_scope`, `hardware_profile`, and
  `status`.

- [ ] **Step 1: Write the failing catalog-coverage test**

```python
def test_catalog_covers_every_registry_and_installer_asset() -> None:
    catalog = load_catalog()
    assert registry_asset_ids() <= set(catalog["assets"])
    assert installer_asset_ids() <= set(catalog["assets"])
    assert all(record["status"] in {"eligible", "agreement_gated", "personal_only", "excluded"}
               for record in catalog["assets"].values())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `conda run --no-capture-output -n goodq_core python -m pytest tests/unit/test_offline_asset_catalog.py -q`

Expected: FAIL because the catalog loader and catalog file do not exist.

- [ ] **Step 3: Add the catalog and minimal parser helpers**

```yaml
schema_version: 1
assets:
  nrc_emotion:
    kind: lexicon
    source: saifmohammad/nrc-emotion-lexicon
    revision: "0.92"
    license_class: research_only_no_redistribution
    vault_scope: personal
    pack_scope: none
    hardware_profile: cpu
    status: personal_only
```

Implement `registry_asset_ids()` and `installer_asset_ids()` in the test module
as read-only YAML/text extraction helpers. Add records for every model-registry
entry and every installer-staged external asset. Use `agreement_gated` for
Gemma and Qwen 3B, `personal_only` for NRC, and `excluded` for assets whose
exact source terms do not permit the required distribution.

- [ ] **Step 4: Run the catalog test to verify it passes**

Run: `conda run --no-capture-output -n goodq_core python -m pytest tests/unit/test_offline_asset_catalog.py -q`

Expected: PASS, with every current asset reference represented once.

- [ ] **Step 5: Commit the catalog contract**

```powershell
git add configs/offline_asset_catalog.yaml tests/unit/test_offline_asset_catalog.py
git commit -m "Catalog offline asset dispositions"
```

### Task 2: Implement immutable source inventory and sealing

**Files:**
- Create: `scripts/assets/__init__.py`
- Create: `scripts/assets/personal_asset_vault.py`
- Create: `tests/unit/test_personal_asset_vault.py`

**Interfaces:**
- Consumes: `--source-dir`, `--vault-root`, `--asset-id`, `--source-url`,
  `--revision`, and `--terms-file` command-line arguments.
- Produces: `<vault-root>/<asset-id>/<revision>-<manifest-prefix>/` with
  `source/`, `terms/`, `source-manifest.json`, `duplicates.json`,
  `disposition.json`, `README.md`, and `seal.json`.

- [ ] **Step 1: Write failing sealing and duplicate tests**

```python
def test_seal_copies_canonical_members_and_records_duplicate_hashes(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "one.zip").write_bytes(b"same")
    (source / "two.zip").write_bytes(b"same")
    result = seal_snapshot(source, tmp_path / "vault", "nrc", "0.92", [terms_file])
    assert (result.path / "seal.json").exists()
    assert len(json.loads((result.path / "duplicates.json").read_text())["duplicates"]) == 1
    assert not (result.path / "source" / "two.zip").exists()
```

```python
def test_seal_refuses_missing_terms_or_changed_copy(tmp_path: Path) -> None:
    with pytest.raises(VaultError, match="terms"):
        seal_snapshot(source, vault, "nrc", "0.92", [])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `conda run --no-capture-output -n goodq_core python -m pytest tests/unit/test_personal_asset_vault.py -q`

Expected: FAIL because `personal_asset_vault` does not exist.

- [ ] **Step 3: Implement the vault module**

```python
def seal_snapshot(
    source_dir: Path,
    vault_root: Path,
    asset_id: str,
    revision: str,
    terms_files: list[Path],
) -> SnapshotResult:
    """Copy canonical hash-distinct members, verify copies, then atomically seal."""
```

Implement `sha256_file`, `inventory_source`, `find_duplicate_members`,
`copy_and_verify`, and `seal_snapshot`. Copy into a temporary sibling
directory, verify every destination hash against the source manifest, then
atomically rename it to its final snapshot directory. Refuse existing final
paths, missing terms, empty source directories, path traversal, and manifest
mismatches. `duplicates.json` records duplicate members without copying a
second byte-identical file into `source/`.

- [ ] **Step 4: Add CLI receipt and cleanup guard**

```text
python -m scripts.assets.personal_asset_vault seal \
  --source-dir <source> --vault-root <vault> --asset-id nrc_emotion \
  --revision 0.92 --source-url <url> --terms-file <terms> --disposition personal_only
```

Add `cleanup-duplicates` that accepts `--source-dir` and `--seal-path`, first
verifies the seal and source hashes, then deletes only source members named in
`duplicates.json`. It must refuse cleanup if any retained source member differs
from the sealed manifest.

- [ ] **Step 5: Run focused tests to verify the implementation passes**

Run: `conda run --no-capture-output -n goodq_core python -m pytest tests/unit/test_personal_asset_vault.py -q`

Expected: PASS, including atomic seal, duplicate detection, and refusal paths.

- [ ] **Step 6: Commit the vault implementation**

```powershell
git add scripts/assets tests/unit/test_personal_asset_vault.py
git commit -m "Add immutable personal asset vault"
```

### Task 3: Seal NRC as the first personal-only source snapshot

**Files:**
- Create: vault snapshot outside the repository through the Task 2 CLI.
- Modify: `docs/releases/OFFLINE_PAYLOAD_ELIGIBILITY.md`
- Modify: `docs/releases/ROADMAP.md`

**Interfaces:**
- Consumes: the NRC scratch source directory, official NRC terms captured as a
  terms input, and the Task 2 CLI.
- Produces: a sealed `nrc_emotion` personal-only snapshot and an evidence-backed
  release-ledger entry.

- [ ] **Step 1: Generate the NRC source inventory without mutation**

Run: `conda run --no-capture-output -n goodq_core python -m scripts.assets.personal_asset_vault inventory --source-dir <nrc-source> --output <inventory.json>`

Expected: an inventory that identifies the two identical NRC Hashtag Sentiment
archives and records every original source member hash.

- [ ] **Step 2: Seal the snapshot**

Run: `conda run --no-capture-output -n goodq_core python -m scripts.assets.personal_asset_vault seal --source-dir <nrc-source> --vault-root <asset-vault> --asset-id nrc_emotion --revision 0.92 --source-url https://saifmohammad.com/WebPages/AccessResource.htm --terms-file <captured-terms> --disposition personal_only`

Expected: a new immutable snapshot with full source, terms, manifest,
duplicates record, and seal receipt.

- [ ] **Step 3: Verify the sealed snapshot independently**

Run: `conda run --no-capture-output -n goodq_core python -m scripts.assets.personal_asset_vault verify --seal-path <nrc-seal>`

Expected: PASS; every canonical source file and terms file matches its sealed
hash.

- [ ] **Step 4: Remove only the accidental source duplicate**

Run: `conda run --no-capture-output -n goodq_core python -m scripts.assets.personal_asset_vault cleanup-duplicates --source-dir <nrc-source> --seal-path <nrc-seal>`

Expected: exactly one duplicate source archive removed; retained source files
remain hash-equal to the seal.

- [ ] **Step 5: Record the personal-only disposition**

Update the eligibility ledger and roadmap with the sealed NRC snapshot digest,
official terms source, and the invariant that it cannot be packed for public
redistribution.

- [ ] **Step 6: Run documentation validation and commit**

Run: `conda run --no-capture-output -n goodq_core python scripts/docs/doc_drift_lint.py`

Expected: PASS.

```powershell
git add docs/releases/OFFLINE_PAYLOAD_ELIGIBILITY.md docs/releases/ROADMAP.md
git commit -m "Record sealed personal NRC asset"
```

### Task 4: Add acquisition and pack-admission preflight

**Files:**
- Modify: `scripts/assets/personal_asset_vault.py`
- Modify: `tests/unit/test_personal_asset_vault.py`
- Modify: `docs/releases/OFFLINE_PAYLOAD_ELIGIBILITY.md`

**Interfaces:**
- Consumes: `configs/offline_asset_catalog.yaml` and a candidate source
  snapshot manifest.
- Produces: an acquisition plan and a pack-admission result; it does not
  download, package, or install assets.

- [ ] **Step 1: Write failing preflight tests**

```python
def test_pack_admission_refuses_unsealed_or_personal_only_assets(tmp_path: Path) -> None:
    result = evaluate_pack_admission(catalog, asset_id="nrc_emotion", distribution="public")
    assert result.allowed is False
    assert "personal_only" in result.reason
```

```python
def test_acquisition_plan_requires_exact_revision_and_terms() -> None:
    with pytest.raises(VaultError, match="revision"):
        build_acquisition_plan({"asset_id": "missing-revision"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run --no-capture-output -n goodq_core python -m pytest tests/unit/test_personal_asset_vault.py -q`

Expected: FAIL because the admission and acquisition-plan functions do not
exist.

- [ ] **Step 3: Implement the preflight functions**

```python
def build_acquisition_plan(record: dict[str, object]) -> dict[str, object]: ...
def evaluate_pack_admission(
    catalog: dict[str, object], asset_id: str, distribution: str
) -> AdmissionResult: ...
```

Require `source`, immutable `revision`, `license_class`, `vault_scope`,
`hardware_profile`, and expected terms for every acquisition-plan record. Allow
personal installer admission only for `eligible`, `agreement_gated` with a
receipt, and `personal_only` with a personal installer target. Allow public
admission only for `eligible` assets backed by a sealed source snapshot.

- [ ] **Step 4: Run focused tests to verify they pass**

Run: `conda run --no-capture-output -n goodq_core python -m pytest tests/unit/test_personal_asset_vault.py tests/unit/test_offline_asset_catalog.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the preflight contract**

```powershell
git add scripts/assets/personal_asset_vault.py tests/unit/test_personal_asset_vault.py docs/releases/OFFLINE_PAYLOAD_ELIGIBILITY.md
git commit -m "Gate model packs on sealed asset sources"
```

## Plan Self-Review

- Spec coverage: Tasks 1 through 4 cover source classification, immutable
  snapshots, duplicate handling, NRC first-asset proof, personal/public
  separation, and pack-admission gating.
- Scope: installer UI, archive acquisition, and model-pack construction are
  deliberately deferred until this foundation is tested and NRC is sealed.
- Unresolved markers: none. Commands use operator-provided paths only where those
  paths are machine-local runtime inputs.
- Type consistency: `SnapshotResult`, `VaultError`, `AdmissionResult`,
  `seal_snapshot`, `build_acquisition_plan`, and `evaluate_pack_admission` are
  defined before dependent tasks use them.
