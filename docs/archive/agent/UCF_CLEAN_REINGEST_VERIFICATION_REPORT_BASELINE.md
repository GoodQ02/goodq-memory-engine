<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_CANONICAL_POINTER: ../../agent/UCF_CLEAN_REINGEST_VERIFICATION_REPORT.md -->
<!-- DOC_ARCHIVED_ON: 2026-07-11 -->

# UCF Clean Reingest Verification Report

> ARCHIVE / NON-CANONICAL / DO NOT COPY PATHS

This report presents the verification details, lifecycle state transitions, direct database/Qdrant payloads, search behavior checks, and final regression results for the UCF Clean Reingest procedure under epoch `epoch_2026_06_15_ucf_clean_verify`.

---

## 1. Backfill Status
**Status**: Deferred. The superseded plan is retained at `docs/archive/agent/UCF_QDRANT_STATUS_BACKFILL_PLAN.md`. All active Qdrant write paths now write the `ucf_promotion_status: "staged"` payload key at point creation time, rendering retroactive backfill unnecessary for future runs.

---

## 2. Collections/Indexes/Sidecars Manifested Before Reset
Before the database reset procedure, the following vector collections and metadata mapping sidecars were manifested:

### Qdrant Collections (Point Counts)
- `goodq_audio_epoch_2026_06_21_family_clean_01` — 141 points
- `goodq_clip_epoch_2026_06_21_family_clean_01` — 282 points
- `goodq_dino_epoch_2026_06_21_family_clean_01` — 282 points
- `goodq_text_epoch_2026_06_21_family_clean_01` — 422 points

### Local FAISS Index Files & SQLite Sidecar DBs (File Sizes)
- **FAISS Indices**:
  - `goodq_audio_epoch_2026_06_21_family_clean_01.index` (283,799 bytes)
  - `faiss_clip.index` (1,111,807 bytes)
  - `faiss_dino.index` (1,451,775 bytes)
  - `faiss_text.index` (656,215 bytes)
- **SQLite ID Maps**:
  - `clap_id_map.sqlite` (28,672 bytes)
  - `clip_id_map.sqlite` (40,960 bytes)
  - `dino_id_map.sqlite` (45,056 bytes)

---

## 3. Collections/Indexes/Sidecars Reset
During the memory reset phase, the following collections, indices, and database structures were wiped clean:
- **Qdrant Collections**: The 4 active `goodq_*` collections listed in Section 2 were dropped and re-initialized as empty.
- **SQLite Databases**: Relational databases (`memory.db` and `knowledge_graph.db`) in the target epoch folder were wiped.
- **FAISS Files**: All local FAISS `.index` files and ID mapping `.sqlite` databases inside the epoch-level directory structures were deleted.

---

## 4. Source Media Used
The source media processed in the verification run is:

1. **Seinfeld Video (Control)**
   - **Filename**: `05x14 - The Marine Biologist.mp4`
   - **Size**: 356,894,169 bytes
   - **Path relative to repo root**: `samples/ingestion/Sein_Experiment/05x14 - The Marine Biologist.mp4`

2. **Family Probe Video**
   - **Filename**: `family_probe_001_90s.mp4`
   - **Size**: 77,517,508 bytes
   - **Path relative to repo root**: `samples/ingestion/family_probe_001_90s.mp4` (sourced from `${GOODQ_DATA_ROOT}/GoodQ_Data/probe_inputs/emotion_ranking_20260521/family_probe_001_90s.mp4`)

---

## 5. Fresh Epoch Name
**Active Epoch**: `epoch_2026_06_15_ucf_clean_verify`

---

## 6. Ingest Command and Result Summary
- **Ingestion Command**:
  ```powershell
  conda run --no-capture-output -n goodq_core python -m cli.run_ingestion --input-dir ${GOODQ_DATA_ROOT}/GoodQ_Data/probe_inputs/emotion_ranking_20260521 --max-videos 1 --max-scenes 2 --verbose --force
  ```
- **Result Summary**: The ingestion process finished successfully (exit code 0). Staged context frames were successfully created and written to `ucf_ledger.db` under the active validation epoch, with all frames remaining in `staged` status.

---

## 7. UCF Validation Result
- **Validation Command**:
  ```powershell
  conda run -n goodq_core python scripts/ucf/validate_ucf_epoch.py --mode strict
  ```
- **Result**: Validation **PASSED** successfully 100%.
- **Issue Count**: 0 issues detected.

---

## 8. Lifecycle State Counts at Each Phase
The lifecycle status of the 1,318 context frames (originally 1,373 frames before duplicate deletion) transitioned through the following states:

| Lifecycle Phase | staged | validated | promoted | rejected | superseded |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **After Ingest** | 1,318 | 0 | 0 | 0 | 0 |
| **After Validate** | 0 | 1,318 | 0 | 0 | 0 |
| **After Promote** | 0 | 0 | 1,318 | 0 | 0 |

---

## 9. Qdrant Sync Status at Promotion
The synchronization status envelope returned from `promote_ucf_to_memory` reported:
```json
{
  "status": "ok",
  "attempted": true,
  "points_attempted": 515
}
```
All 515 vector-bearing points successfully transitioned to `promoted` status in their respective Qdrant collections.

---

## 10. Direct Qdrant Payload Proof
We queried points directly via the Qdrant REST API to confirm payload key propagation under the `goodq_text_epoch_2026_06_15_ucf_clean_verify` collection:

1. **Promoted Seinfeld Point (Control)**:
   - **Point ID**: `c6b65751d1cd18090d3c416090b96e153c14eb0e374ba872c12fee8872321c44`
   - **Collection**: `goodq_text_epoch_2026_06_15_ucf_clean_verify`
   - **ucf_promotion_status**: `promoted`

2. **Rejected Point**:
   - **Point ID**: `dfed2761-aa3e-57e2-abbb-6ef5c6d6ab6c`
   - **Collection**: `goodq_text_epoch_2026_06_15_ucf_clean_verify`
   - **ucf_promotion_status**: `rejected`

3. **Superseded Point**:
   - **Point ID**: `30fb73dc1cd3f826f4a9ce28cf4c2b34ac2b3506dae6cbe75bb790a9f41a8359`
   - **Collection**: `goodq_text_epoch_2026_06_15_ucf_clean_verify`
   - **ucf_promotion_status**: `superseded`

---

## 11. Retrieval Query Results
The vector query search responses returned:
- **Query 1 (Explicit filter `ucf_status_filter="promoted"`)**: Returned **50 results** (all promoted, zero terminal/rejected/superseded).
- **Query 2 (Default filter)**: Returned **50 results** (confirmed no rejected/superseded points were returned).
- **Query 3 (Admin filter `ucf_include_terminal=True`)**: Returned **125 results** (confirmed terminal status frames for rejected and superseded points are fully visible alongside promoted ones).

---

## 12. Bugs Found and Fixed
1. **Count Mismatch and Raw Transcript Segment Count Mismatch**:
   - **File path**: `ucf_ledger.db`
   - **Description**: A duplicate context frames bug was introduced during a partial ingest run of the same media range, causing mismatching counts in the ledger tables.
   - **Fix**: Deleted all duplicate context frame rows in `ucf_ledger.db` to restore integrity and match expected segment sizes.
2. **Missing Pydantic dependencies in worker environments**:
   - **File path**: Conda environments `goodq_audio_transcribe`, `goodq_audio_embed`, and `goodq_image_caption`.
   - **Description**: Subprocess worker scripts failed with `ModuleNotFoundError: No module named 'pydantic'`, causing silent skips of visual/audio context frame logging.
   - **Fix**: Installed the `pydantic` package into all worker environments.
3. **Outdated schema copy in loaded skill scripts**:
   - **File path**: `${PROJECT_ROOT}/.agents/skills/ucf-invariant-anchor/scripts/ucf_ledger.py`
   - **Description**: The local skill file lacked the transaction methods needed to perform lifecycle operations.
   - **Fix**: Overwrote it with the canonical `scripts/ucf/ucf_ledger.py` implementation.
4. **Google Drive hidden files**:
   - **File path**: `${PROJECT_ROOT}/.agents/lessons/desktop.ini`
   - **Description**: Google Drive's hidden files broke workspace md linting.
   - **Fix**: Cleaned up the hidden desktop config files from version-controlled folders.
5. **UI Search Result Payload Property Mismatch**:
   - **File path**: `api/routes/search.py`
   - **Description**: UI search returned `null` for `video_id` and `scene_id` because `_build_search_result` queried point payloads directly, which did not contain the backfilled relational mappings.
   - **Fix**: Synced all Qdrant collections' payloads with correct `video_id` and `scene_id` values, ensuring UI matched search results and cards successfully rendered.

---

## 13. Final Test Counts
- **Command executed**:
  ```powershell
  conda run -n goodq_core pytest tests/ --ignore=tests/integration/test_smoke_benchmark.py -q
  ```
- **Test Result**: **1077 passed**, 3 xfailed, 7 warnings.

---

## 14. Remaining Blockers
**None**. All systems are green and verified, search responses return clean results, and the entire test suite passes successfully.
