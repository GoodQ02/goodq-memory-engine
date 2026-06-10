<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_AGENT_WORKFLOW -->
<!-- DOC_LAST_VERIFIED: 2026-06-08 -->

# Pipeline Troubleshooting Flow: Verifiable Source-Driven Optimization

Use this workflow to diagnose pipeline failures, tune confidence thresholds, or optimize processor performance by isolating runs against verifiable external source materials.

## Purpose

To isolate and resolve pipeline regressions, file-sharing delays, transcription errors, or memory-indexing bugs deterministically. By utilizing known external ground truth (e.g., IMDb, Wikipedia, script records) and executing targeted scene reruns rather than full episodes, we minimize compute, avoid regression drift, and prevent duplicate debugging efforts.

---

## The Troubleshooting Loop

### 1. Identify Ground Truth Alignment
When testing or optimizing a pipeline segment, align your test file with a verified source record (e.g., an IMDb episode cast list, movie transcript, or scene index):
- Locate the correct movie, episode, or visual catalog on IMDb, Wikipedia, or transcript DBs.
- Determine the canonical truth (e.g., exact speaker names, chronological dialogue, visual elements present).

### 2. Isolate Target Scenes
Do not rerun the entire video or episode file. Ingesting full episodes takes significant time and compute, which hides micro-regressions and slows down iteration.
- Identify the specific scene index range (e.g., scenes 18–25) containing the bug or threshold seam.
- Inject temporary CLI filters or mock selectors into the ingestion runner (e.g., `cli/run_ingestion.py` or pipeline wrappers) to limit execution to just those target scenes.

### 3. Apply Single-Variable Tuning
Change **exactly one variable at a time** during troubleshooting runs to maintain mathematical determinism. Changing multiple variables concurrently makes it impossible to isolate the exact cause of a fix or regression.
- Examples of single variables:
  - Subprocess file-system check timeout threshold.
  - VRAM allocator safety boundary (`emergency_stop_gb`).
  - Audio overlap/diarization confidence threshold.
  - Visual description similarity index parameters.

### 4. Execute and Inspect Target Output
Run the target scene range. Inspect the database and manifest structures directly:
- Check `memory.db` (`scenes`, `segments`, `summaries`, `links`) for transcript correctness, speaker mapping, and entity relationships.
- Inspect `knowledge_graph.db` (`nodes`, `edges`) to ensure proper spatial, temporal, and semantic entity linking.
- Query vector databases (Qdrant/FAISS) to verify embeddings are present, non-duplicate, and return correct similarity search scores.

### 5. Validate for Regression & Drift
After implementing a fix or change:
- Re-run the isolated scenes to confirm the correction.
- Ensure the fix doesn't introduce side effects on adjacent pipeline steps (e.g., visual features generating successfully but audio falling back).
- Confirm that the changes are compatible across both `BASELINE` (CPU-safe) and `GPU_ENHANCED` profiles.

### 6. Catalog the Correction
To prevent "wack-a-mole" scenarios and duplicate debugging, all findings must be logged in the project's corrections index file:
- File location: [corrections.json](../../../.agents/index/corrections.json)
- Log format requirement:
  ```json
  {
    "id": "corr_unique_id",
    "date": "YYYY-MM-DD",
    "issue": "Detailed description of the issue encountered.",
    "target_scenes": ["scene_00XX"],
    "source_material": {
      "file_name": "filename.mp4",
      "description": "Short description of the media."
    },
    "failed_attempts": [
      "Detail of attempt 1 that did not work."
    ],
    "solution": "Detailed description of the actual working fix.",
    "notable_results": "Concrete proof of success (e.g., logs, execution time reduction, search match scores).",
    "variables_changed": [
      {
        "name": "variable_name",
        "before": "previous value/behavior",
        "after": "new value/behavior"
      }
    ]
  }
  ```

---

## Pass Criteria

A pipeline optimization or fix is ready to commit when:
1. **Target Verification Passes**: The isolated target scenes compile/ingest with zero warnings/errors.
2. **Deterministic Improvement**: Output quality (similarity search ranking, transcription correctness, or VRAM consumption) shows measurable improvement.
3. **No Baseline/WSL Regression**: The core pipeline continues running successfully without requiring active network access or causing baseline environment drift.
4. **Timeline Indexed**: A new entry is appended to `.agents/index/corrections.json` following the specified schema.
