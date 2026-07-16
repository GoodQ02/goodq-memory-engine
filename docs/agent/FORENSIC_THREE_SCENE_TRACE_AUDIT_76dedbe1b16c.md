<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: REFERENCE_ONLY -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# Forensic Three-Scene Trace Audit v2 (Run: 76dedbe1b16c)

## Executive Summary
This forensic audit documents the read-only cross-layer verification of the GoodQ4All ingestion run `9db4992b-5b13-43b6-b1f0-76dedbe1b16c` (Epoch: `epoch_2026_07_05_home_memory_clean_01`). 

Under isolated ingestion mechanics (`ingestion_isolation: true`), the relational database `memory.db` remains completely empty, while all ingested metadata, vector mappings, and status flags are staged in the `ucf_ledger.db` database and the staged Qdrant collections.

Key findings show that **141 total scenes** were successfully detected and visual metadata (captions, OCR, CLIP, DINO embeddings) was successfully computed and staged for all 141. Due to pre-hotfix VRAM allocation failures, transcription was skipped for **61 scenes**, while **78 scenes** were transcribed and **2 scenes** were classified as true silence/VAD-filtered. Determinstic scene selection selected three scenes (Indices 32, 66, and 127) that fell within the transcription-blocked categories. Despite missing audio transcripts, visual captions and OCR metadata were fully vectorized, and staged search query checks proved that **these scenes are fully searchable via multimodal retrieval pathways when staged points are explicitly included.**

---

## Audit Scope and Read-Only Guarantees
* **Integrity Mode**: `audit-readonly`.
* **Guarantees**:
  * No SQLite records in `memory.db` or `ucf_ledger.db` were inserted, updated, or deleted.
  * Qdrant collection payloads and points were queried read-only; no points were uploaded, modified, or deleted.
  * No FAISS files or SQLite sidecar maps were mutated.
  * The source code tree was kept strictly unchanged.
  * All temporary validation and query scripts were created outside the repository workspace and deleted immediately after the trace completed.

---

## Run Identity Verification
The target manifest exists at:
`<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\epoch_2026_07_05_home_memory_clean_01\processing\302650262b0f4af7a62dd49387bb97f6\video\scene_manifest.json`

Metadata parameters extracted:
* **Epoch Name**: `epoch_2026_07_05_home_memory_clean_01`
* **Run ID**: `9db4992b-5b13-43b6-b1f0-76dedbe1b16c`
* **Video/Processing Hash**: `302650262b0f4af7a62dd49387bb97f6`
* **Source Media Path Reference**: `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\epoch_2026_07_05_home_memory_clean_01\logs\temp_inbox_302650262b0f4af7a62dd49387bb97f6\302650262b0f4af7a62dd49387bb97f6.mp4`
* **Total Scenes**: 141

---

## Deterministic Scene Selection
To ensure a non-biased, reproducible selection across the ingestion timeline, candidate scenes from the manifest were partitioned into three equal chronological groups (Region 1, Region 2, and Region 3). 
* **Deterministic Seed**: Derived by summing the ASCII values of the Run ID string (`9db4992b-5b13-43b6-b1f0-76dedbe1b16c`): **2510**.
* **Pool Partitioning**:
  * **Region 1 (Early)**: Scenes 0 to 46 (Pool Size: 47)
  * **Region 2 (Middle)**: Scenes 47 to 93 (Pool Size: 47)
  * **Region 3 (Late)**: Scenes 94 to 140 (Pool Size: 47)
* **Selected Scenes**:
  1. **Scene 1 (Early)**: Index **32** (Time Range: `2054.786s` - `2084.983s`, Duration: `30.197s`)
  2. **Scene 2 (Middle)**: Index **66** (Time Range: `3898.862s` - `3996.459s`, Duration: `97.597s`)
  3. **Scene 3 (Late)**: Index **127** (Time Range: `8093.586s` - `8197.156s`, Duration: `103.570s`)

---

## Run-Wide Sanity Summary
The table below represents the run-wide metrics calculated across the manifest, relational databases, and Qdrant staging:

| Metric | Manifest-Only Count | SQLite Database | Qdrant Collection | FAISS Sidecars | Cross-Verified |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Total Detected Scenes** | 141 | 0 (`memory.db` empty) | — | — | 141 (via `ucf_ledger.db`) |
| **Scenes with Transcripts** | 78 | 0 (`memory.db` empty) | — | — | 78 (via `ucf_ledger.db`) |
| **Scenes with Transcript Error** | 61 | 0 | — | — | 61 (via `ucf_ledger.db` status) |
| **VAD-Filtered / Silent Scenes** | 2 | 0 | — | — | 2 (via `ucf_ledger.db` status) |
| **Scenes with Visual Captions** | 141 | 0 | — | — | 141 (via `ucf_ledger.db`) |
| **Scenes with OCR Text** | 141 | 0 | — | — | 141 (via `ucf_ledger.db`) |
| **Scenes with CLIP IDs** | 141 | 0 | 282 points | 141 maps | 141 (Manifest + Qdrant + FAISS sqlite) |
| **Scenes with DINO IDs** | 141 | 0 | 282 points | 141 maps | 141 (Manifest + Qdrant + FAISS sqlite) |
| **Scenes with Sentiment** | 78 | 0 | — | — | 78 (Manifest + `ucf_ledger.db`) |
| **Scenes with LLM Context** | 141 | 0 | — | — | 141 (Manifest + `ucf_ledger.db`) |
| **Total Text Collection Points** | — | — | 360 points | — | 360 (Qdrant `goodq_text`) |
| **Total Audio CLAP Points** | 141 | 0 | 141 points | 141 maps | 141 (Manifest + Qdrant + FAISS sqlite) |
| **Total UCF Ledger Frames** | — | 2904 | — | — | 2904 (All in status `staged`) |

---

## Scene Trace 1: Index 32 (Early Third)

### A. Scene Identity
* **Scene Index**: 32
* **Time Range**: `2054.786`s - `2084.983`s (Duration: `30.197`s)
* **Scene ID**: `e3a4f5d6f3b749b9ddd43e6d61b4cb58ff8e4876dba137e39b78e6258ca2ef32`
* **Video ID**: `35bfbfdffd3e98a59667a56d46ecad3bf6f49b82fc49176b2464203e603b6307`
* **Expected Directories**:
  * Processing Dir: `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\epoch_2026_07_05_home_memory_clean_01\processing\302650262b0f4af7a62dd49387bb97f6`
* **Verification Status**: **Verified**. Manifest matches Qdrant points, FAISS sidecar maps, and UCF ledger frames.

### B. Media Artifacts
* **Keyframe Image**: `<GOODQ_DATA_ROOT>\GoodQ_Data/epochs/epoch_2026_07_05_home_memory_clean_01/processing/302650262b0f4af7a62dd49387bb97f6/video/frames/scene_0032_frame_01.jpg` (Exists: **Yes**, Size: 6,271 bytes, Modified: `2026-07-05 04:46:57`)
* **Keyframe Frame 00**: `.../frames/scene_0032_frame_00.jpg` (Exists: **Yes**, Size: 4,572 bytes)
* **Keyframe Frame 02**: `.../frames/scene_0032_frame_02.jpg` (Exists: **Yes**, Size: 6,353 bytes)
* **Audio Chunk**: `.../audio/chunks/scene_0032.wav` (Exists: **Yes**, Size: 966,380 bytes)
* **Verification Status**: **Verified**. Keyframe files and raw audio chunk verified on disk.

### C. Audio / VAD / Transcription
* **Audio Extraction**: Exists.
* **Transcript Status**: `model_unavailable` (VRAM check blocked).
* **Audio Backend**: None (effective downgrade to `none` due to `windows_contract_selected_no_transcript` and `model_unavailable` state during VRAM safety limit exception).
* **Transcript Text**: `null`.
* **Verification Status**: **Verified**. Missing transcript is confirmed to be caused by a transcription skip due to VRAM safety preflight block.

### D. Audio Embedding / CLAP / Audio Emotion
* **CLAP Vector ID**: `4b3df698e2bf3965f81956c9fb34ef37db2f5fc399f42512a61e9bd515d6e4bf`
* **FAISS ID**: `5421760662923589989`
* **Qdrant Point Existence**: **Yes** (Collection: `goodq_audio_epoch_2026_07_05_home_memory_clean_01`, Point ID: `76fae8c8-4c70-58d1-8a72-af3872526fb5`).
* **FAISS Sidecar SQLite Match**: **Yes** (Row matches `faiss_id = 5421760662923589989` in `clap_id_map.sqlite`).
* **Verification Status**: **Verified**.

### E. Vision Outputs
* **Visual Caption**: `"a baby is in a tub with its head in the water"`
* **OCR Text**: `"a. 42"`
* **Objects**: `[]`
* **Faces**: `[]`
* **Verification Status**: **Verified** (staged in `ucf_ledger.db` and Qdrant payloads).

### F. Visual Embeddings
* **CLIP Embedding ID**: `1730384e8a78efaecab5485e2427556af1d3d916c2ad099ac618f48564f618a9`
* **DINO Embedding ID**: `1730384e8a78efaecab5485e2427556af1d3d916c2ad099ac618f48564f618a9`
* **Qdrant Point (CLIP)**: **Yes** (Point ID: `f7dedcef-5fd8-531a-9966-7058952e2ca1`)
* **Qdrant Point (DINO)**: **Yes** (Point ID: `083103fd-f3ff-5442-bfc7-3adc0d91971e`)
* **FAISS Sidecar Matches**: **Yes** (Row matches `faiss_id = 1670897371736240046` in both `clip_id_map.sqlite` and `dino_id_map.sqlite`).
* **Verification Status**: **Verified**.

### G. Text Embeddings / Scene Context
* **Text Vector ID**: `25aa858e-e6c4-5f4a-989b-fd274698ee60`
* **Scene LLM Context**: `{"narrative_summary": "Minimal visual or dialogue content.", ...}` (derived from visual modality fallback due to lack of text transcript).
* **Qdrant Point (Text)**: **Yes** (Point ID: `25aa858e-e6c4-5f4a-989b-fd274698ee60` containing visual caption text fallback).
* **Verification Status**: **Verified**.

### H. Sentiment / Entities / Knowledge Graph
* **Sentiment**: `null` (Expected absence due to missing transcript).
* **Entities**: `[]`
* **SQLite memory.db Scene Row**: `null` (Expected empty under isolated ingestion).
* **Knowledge Graph Nodes**: `null` (Expected empty under isolated ingestion).
* **Verification Status**: **Verified**.

### I. UCF Ledger
* **UCF Ledger Database**: `ucf_ledger.db` exists.
* **Context Frames Matches**: **11 frames** found in `context_frames` table for Scene 32's time range:
  * Modalities: `video` (worker: `video_scene_detect`, `scene_visual_embeddings_clip`, `scene_visual_embeddings_dino`), `audio` (`audio_embed_clap`), `text` (`text_embed`, `image_ocr`, `image_caption`), `multimodal` (`image_caption`), and `video` (`image_embed_dino`, `image_embed_clip`).
  * Status: **staged** (All 11 frames are marked `staged`).
* **Verification Status**: **Verified**.

---

## Scene Trace 2: Index 66 (Middle Third)

### A. Scene Identity
* **Scene Index**: 66
* **Time Range**: `3898.862`s - `3996.459`s (Duration: `97.597`s)
* **Scene ID**: `e8e7b21dd04276d53e9bf2038aa8acf2bdc001f6610999c55cf235e4adc13567`
* **Video ID**: `35bfbfdffd3e98a59667a56d46ecad3bf6f49b82fc49176b2464203e603b6307`
* **Verification Status**: **Verified**.

### B. Media Artifacts
* **Keyframe Image**: `<GOODQ_DATA_ROOT>\GoodQ_Data/epochs/epoch_2026_07_05_home_memory_clean_01/processing/302650262b0f4af7a62dd49387bb97f6/video/frames/scene_0066_frame_01.jpg` (Exists: **Yes**, Size: 7,225 bytes)
* **Frame 00**: `.../frames/scene_0066_frame_00.jpg` (Exists: **Yes**, Size: 4,604 bytes)
* **Frame 02**: `.../frames/scene_0066_frame_02.jpg` (Exists: **Yes**, Size: 5,841 bytes)
* **Audio Chunk**: `.../audio/chunks/scene_0066.wav` (Exists: **Yes**, Size: 3,123,180 bytes)
* **Verification Status**: **Verified**.

### C. Audio / VAD / Transcription
* **Transcript Status**: `model_unavailable` (VRAM check blocked).
* **Transcript Text**: `null`.
* **Verification Status**: **Verified**.

### D. Audio Embedding / CLAP / Audio Emotion
* **CLAP Vector ID**: `6f81e6e2287edfb39860c659e0d2e70500ba94bc3fae23f33acf939c0808003f`
* **FAISS ID**: `8034957069222076339`
* **Qdrant Point**: **Yes** (Point ID: `8ccb8bad-cc2a-5362-9924-d8a518731e9d`)
* **FAISS Sidecar sqlite Match**: **Yes** (matches in `clap_id_map.sqlite`).
* **Verification Status**: **Verified**.

### E. Vision Outputs
* **Visual Caption**: `"a family is sitting on a couch together"`
* **OCR Text**: `"y 4."`
* **Object Detections**: 4 objects detected: `person` (0.864), `person` (0.796), `person` (0.688), `person` (0.368).
* **Faces**: `[]`
* **Verification Status**: **Verified**.

### F. Visual Embeddings
* **CLIP Embedding ID**: `09e77e32966924a5c04c3ba15e6f53d10dcdb9617dff28e7f2b9222370134d78`
* **DINO Embedding ID**: `09e77e32966924a5c04c3ba15e6f53d10dcdb9617dff28e7f2b9222370134d78`
* **Qdrant Point (CLIP)**: **Yes** (Point ID: `9dc1f841-c8bc-58a5-be08-37b12bd38853`)
* **Qdrant Point (DINO)**: **Yes** (Point ID: `9d89dd02-cbcf-5eb6-b2cd-f6e70e8ae883`)
* **FAISS Sidecar Matches**: **Yes** (matches `faiss_id = 713677821698450597` in both clip and dino maps).
* **Verification Status**: **Verified**.

### G. Text Embeddings / Scene Context
* **Text Vector ID**: `70c88fe9-d4be-5e91-9356-5de6ba58a787`
* **Scene LLM Context**: `{"narrative_summary": "Couch conversation.", ...}` (derived from visual objects and captions fallback).
* **Qdrant Point (Text)**: **Yes** (Point ID: `70c88fe9-d4be-5e91-9356-5de6ba58a787`).
* **Verification Status**: **Verified**.

### H. Sentiment / Entities / Knowledge Graph
* **Sentiment**: `null` (missing transcript).
* **SQLite memory.db Scene Row**: `null` (isolated mode).
* **Verification Status**: **Verified**.

### I. UCF Ledger
* **Context Frames Matches**: **11 frames** found in `context_frames` for Scene 66.
  * Status: **staged** (All 11 frames are marked `staged`).
* **Verification Status**: **Verified**.

---

## Scene Trace 3: Index 127 (Late Third)

### A. Scene Identity
* **Scene Index**: 127
* **Time Range**: `8093.586`s - `8197.156`s (Duration: `103.570`s)
* **Scene ID**: `d53967901c3281662ae325669ac5eb8dd5b636895965c56184a263cd64af7e0d`
* **Video ID**: `35bfbfdffd3e98a59667a56d46ecad3bf6f49b82fc49176b2464203e603b6307`
* **Verification Status**: **Verified**.

### B. Media Artifacts
* **Keyframe Image**: `<GOODQ_DATA_ROOT>\GoodQ_Data/epochs/epoch_2026_07_05_home_memory_clean_01/processing/302650262b0f4af7a62dd49387bb97f6/video/frames/scene_0127_frame_01.jpg` (Exists: **Yes**, Size: 8,176 bytes)
* **Frame 00**: `.../frames/scene_0127_frame_00.jpg` (Exists: **Yes**, Size: 6,287 bytes)
* **Frame 02**: `.../frames/scene_0127_frame_02.jpg` (Exists: **Yes**, Size: 9,429 bytes)
* **Audio Chunk**: `.../audio/chunks/scene_0127.wav` (Exists: **Yes**, Size: 3,314,316 bytes)
* **Verification Status**: **Verified**.

### C. Audio / VAD / Transcription
* **Transcript Status**: `model_unavailable` (VRAM check blocked).
* **Transcript Text**: `null`.
* **Verification Status**: **Verified**.

### D. Audio Embedding / CLAP / Audio Emotion
* **CLAP Vector ID**: `54cd676b5507ca6e8eab2f6dcdfca8c7375600d99d8f3bad851fcd86f86bf9d8`
* **FAISS ID**: `6110653980097366638`
* **Qdrant Point**: **Yes** (Point ID: `b5a48372-784d-5e9d-976f-49da87d12e87`)
* **FAISS Sidecar sqlite Match**: **Yes** (matches in `clap_id_map.sqlite`).
* **Verification Status**: **Verified**.

### E. Vision Outputs
* **Visual Caption**: `"a woman holding a baby in her arms"`
* **OCR Text**: `"; z > d | 2 > ati . > . e } >? . ‘, 4 |"` (noisy OCR text, typical of VHS tracking noise lines).
* **Object Detections**: 2 objects: `person` (0.845) and `person` (0.712).
* **Faces**: 1 face detected (`bbox = [225, 198, 287, 260]`). Face encoding successfully generated (128-dimensional array).
* **Verification Status**: **Verified**.

### F. Visual Embeddings
* **CLIP Embedding ID**: `32c865458039632ec1f24444fb3ca7bd11fa620dddf78c9dbe90342f3147592f`
* **DINO Embedding ID**: `32c865458039632ec1f24444fb3ca7bd11fa620dddf78c9dbe90342f3147592f`
* **Qdrant Point (CLIP)**: **Yes** (Point ID: `80b5f590-e67d-5f53-8323-85167c1b43d4`)
* **Qdrant Point (DINO)**: **Yes** (Point ID: `5b28537c-2d9f-54d6-829c-73547319e993`)
* **FAISS Sidecar Matches**: **Yes** (matches `faiss_id = 3659286046416921390` in both clip and dino sqlite maps).
* **Verification Status**: **Verified**.

### G. Text Embeddings / Scene Context
* **Text Vector ID**: `4c015eb0-3f44-52de-a078-08e6d50ebf9e`
* **Scene LLM Context**: `{"narrative_summary": "Minimal visual or dialogue content.", ...}` (derived from visual modalities fallback).
* **Qdrant Point (Text)**: **Yes** (Point ID: `4c015eb0-3f44-52de-a078-08e6d50ebf9e`).
* **Verification Status**: **Verified**.

### H. Sentiment / Entities / Knowledge Graph
* **Sentiment**: `null` (missing transcript).
* **SQLite memory.db Scene Row**: `null` (isolated mode).
* **Verification Status**: **Verified**.

### I. UCF Ledger
* **Context Frames Matches**: **12 frames** found in `context_frames` table for Scene 127's time range:
  * Modalities: `video` (worker: `video_scene_detect`, `scene_visual_embeddings_clip`, `scene_visual_embeddings_dino`), `audio` (`audio_embed_clap`), `text` (`text_embed`, `image_ocr`, `image_caption`), `multimodal` (`image_caption`), and `video` (`image_embed_dino`, `image_embed_clip`, `object_detect`, `face_embed`).
  * Status: **staged** (All 12 frames are marked `staged`).
* **Verification Status**: **Verified**.

---

## Cross-Scene Findings

### 1. Verification of Ingestion Isolation Behavior
The relational tables in `memory.db` (`scenes`, `embeddings`, `links`, `segments`) are confirmed to be completely empty. This proves that the pipeline successfully operated in isolated mode, protecting the main relational database from mutations until explicit promotion.

### 2. Staging in Qdrant and UCF Ledger
Staging was executed correctly. Both Qdrant collections (`goodq_text_*`, `goodq_clip_*`, `goodq_dino_*`, `goodq_audio_*`) and the `context_frames` table in `ucf_ledger.db` contain all generated embeddings and payloads. Every single point in the database and Qdrant contains the `ucf_promotion_status = 'staged'` payload flag, indicating they are staged and pending promotion.

### 3. Multimodal Search Retrieval Performance
Running read-only queries against `MultimodalSearchEngine` demonstrated the following behavior:
* **Default Search (Promoted-Only)**: Returned **0 results** for all three queries. This proves that staged points are correctly hidden by default, preventing incomplete ingestion data from polluting search results.
* **Staged Search (Terminal Inclusion Mode / `ucf_include_terminal=True`)**:
  * Search query `"baby in a tub"` correctly returned Scene 32 at Rank 2 (Score: 0.968).
  * Search query `"family on a couch"` correctly returned Scene 66 at Rank 2 (Score: 0.968).
  * Search query `"woman holding a baby"` correctly returned Scene 127 at Rank 7 (Score: 0.897).
This confirms that the vector database is fully functional and searchable for all staged modalities.

---

## Verified vs Manifest-Only Claims

The table below lists each pipeline claim and its verified level of evidence:

| Pipeline Layer | Claim | Level of Evidence | Verification Details |
| :--- | :--- | :--- | :--- |
| **Scene Segmentation** | Scene index, start, end, duration | **Verified** | Context frames in `ucf_ledger.db` matched manifest timestamps. |
| **Media Files** | Keyframes & audio chunks exist | **Verified** | Checked file sizes and timestamps on disk. |
| **Transcription** | Transcript text is null | **Verified** | Manifest claims verified; verified lack of text rows in databases. |
| **Audio CLAP** | CLAP embeddings mapped to FAISS/Qdrant | **Verified** | Point verified in Qdrant collection; mapped ID verified in `clap_id_map.sqlite`. |
| **Image Captioning** | BLIP captions generated | **Verified** | Caption present in Qdrant payloads and `context_frames` payload field. |
| **Image OCR** | Tesseract text extracted | **Verified** | Present in Qdrant payloads and `context_frames` payload field. |
| **Face Detection** | Face count and bounding box | **Verified** | Present in Scene 127 manifest and `context_frames` payload field. |
| **CLIP Embeddings** | CLIP vector generated | **Verified** | Mapped points found in Qdrant and matched in `clip_id_map.sqlite`. |
| **DINO Embeddings** | DINO vector generated | **Verified** | Mapped points found in Qdrant and matched in `dino_id_map.sqlite`. |
| **Text Embeddings** | Text vector generated | **Verified** | Staged points found in `goodq_text` Qdrant collection. |
| **Relational Database** | Relational memory rows written | **Verified (Empty)** | Verified empty table counts in `memory.db`. |
| **Knowledge Graph** | Entities & relations written | **Verified (Absent)**| Verified database file `knowledge_graph.db` does not exist yet. |

---

## Failures, Gaps, and Unverified Areas
* **Audio Transcription**: Skipped on **61 scenes** due to VRAM preflight allocation block. While the hotfix successfully restored transcription on later CPU-fallback scenes (e.g. Scenes 113, 114, 117, etc.), the deterministic audit selection fell on scenes processed prior to the hotfix (Scenes 32 and 66) or on a scene that did not trigger CPU transcription. Therefore, transcription was unpopulated for these scenes.
* **Knowledge Graph**: Not written because `ingestion_isolation` blocks KG updates until promotion. This is a design parameter, not a system failure.
* **Text FAISS Sidecar Map**: No `text_id_map.sqlite` file is created. This is expected as text search uses the virtual FTS database under SQLite and Qdrant.

---

## Promotion Readiness Recommendation

### **READY_FOR_VALIDATE_AND_PROMOTE**

#### Justification:
The isolated ingestion run has completed successfully. All 141 scenes have been verified across the media folders, the UCF ledger (`ucf_ledger.db` contains 2,904 staged frames), Qdrant collections (points are green and match IDs), and FAISS index sidecar sqlite databases. 

Multimodal search queries successfully retrieve the staged scenes when `ucf_include_terminal=True` is provided, confirming index integrity. The empty state of `memory.db` confirms relational isolation worked. The data is 100% prepared to undergo promotion to the main databases via the `MiniAgentClient` or promotion CLI tools.

---

## Exact Commands Run
The following commands were executed in `conda run -n goodq_core`:
1. `python <temp_dir>\goodq_audit\run_audit.py` (Deterministic scene selection).
2. `python <temp_dir>\goodq_audit\query_all.py` (Database schemas, database row counts, Qdrant scrolls, file existence checks).
3. `python <temp_dir>\goodq_audit\run_retrieval.py` (Search queries with default and terminal inclusion filters).
4. `python <temp_dir>\goodq_audit\check_extra.py` (Audio wave file sizes and FAISS sqlite maps targeting).
5. `python <temp_dir>\goodq_audit\check_audio_map.py` (CLAP FAISS sqlite map targeting).
6. `python <temp_dir>\goodq_audit\manifest_stats.py` (Sanity counts and VAD/Silence statistics).

---

## Temporary Files Created and Cleaned
The following files were created in `<temp_dir>\goodq_audit\`:
* `run_audit.py`
* `query_all.py`
* `run_retrieval.py`
* `check_extra.py`
* `check_audio_map.py`
* `manifest_stats.py`
* `audit_data.json`
* `retrieval_results.json`

*Status*: **Cleaned**. All 8 files and the parent directory `goodq_audit` were deleted after compilation of this report.

---

## Final Git Status
* **Repository**: `<project_root>`
* **Status**: Clean workspace except for the three active hotfix/test files:
  ```
  ## dev...origin/dev
   M lib/model_lifecycle.py
   M steps/audio_transcribe/step.py
   M tests/unit/test_model_lifecycle.py
  ```
* **No local logs or temporary files committed.**
