# WITNESS_RUN_001 — End-to-End Memory Integrity (Witness)

## Purpose
Prove that GoodQ4All can perform a single-file, end-to-end ingestion run where:
- Visual (CLIP/DINO), audio (CLAP), and text embeddings commit successfully.
- `memory_commit_events` records each write attempt with `attempted=true` and `committed=true`.
- Retrieval results are annotated with `provenance` (including `provenance_version=1`) and confidence scaffolding (all fields present, null values).
- Retrieval behavior (count/order/ranking) is unchanged; only metadata is added.

## Scope
- Single input file: `<repo_root>/smoke_inbox/sample.mp4`
- Human-invoked run (from repo root), with vector debug enabled:
  - `GOODQ_VECTOR_DEBUG=1 python -m cli.run_ingestion --input-dir smoke_inbox --max-videos 1 --verbose --force-reprocess`
- Watchdog disabled; no batch mode.
- No code/config/schema changes during the witness run.

## Ingestion Summary
- Scene count: 3 scenes detected and processed.
- Phase 6a (visual embeddings): `[PASS]`
- Phase 6b (cross-modal harmonization): `[PASS]`
- Modalities exercised (and committed):
  - Visual: `clip`, `dino`
  - Audio: `audio` (CLAP)
  - Text: `frame_text`, `audio_transcript` (transcript-derived text)

## Memory Commit Evidence (`memory_commit_events`)
The witness run produced **15** `memory_commit_events` rows (3 scenes × 5 modalities) in a contiguous UTC window.

Paths below are intentionally redacted to config keys (e.g., `<cfg.paths.db_path>`), not machine-specific absolute paths.

| Modality | Model | Component | Events | Attempted | Committed | Targets (observed) | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `clip` | `clip` | `scene_visual_embeddings.clip` | 3 | 3 | 3 | Qdrant: `goodq_clip` | Direct Qdrant commit path |
| `dino` | `dino` | `scene_visual_embeddings.dino` | 3 | 3 | 3 | Qdrant: `goodq_dino` | Direct Qdrant commit path |
| `audio` | `laion/clap-htsat-unfused` | `audio_embed_clap` | 3 | 3 | 3 | Qdrant: `goodq_audio`; FAISS: `<cfg.paths.faiss_audio_path>`; SQLite: `<cfg.paths.db_path>` | Dual-write: FAISS + Qdrant |
| `frame_text` | `all-MiniLM-L6-v2` | `text_embed` | 3 | 3 | 3 | Qdrant: `goodq_text`; SQLite: `<cfg.paths.db_path>` | FAISS not attempted (`store_missing`) |
| `audio_transcript` | `all-MiniLM-L6-v2` | `text_embed` | 3 | 3 | 3 | Qdrant: `goodq_text`; SQLite: `<cfg.paths.db_path>` | FAISS not attempted (`store_missing`) |

## Retrieval Proof (Provenance + Confidence)
One representative retrieval hit (CLIP) was queried from Qdrant with an exact payload filter (`video_id="sample"`, `scene_id=<redacted>`), then annotated via `memory_commit_events` correlation.

The full hit (sanitized) is stored at:
- `docs/proof_of_concept/artifacts/WITNESS_RUN_001_retrieval_hit.json`

## Validation Checklist
- [x] Ingestion completes end-to-end for a single file.
- [x] Commit events recorded for `clip`, `dino`, `audio`, `frame_text`, `audio_transcript` with `attempted=true` and `committed=true`.
- [x] Retrieval hit includes `provenance.provenance_version=1`.
- [x] Retrieval hit includes a `confidence` object with fields present and null values (no confidence computation yet).
- [x] Retrieval behavior unchanged (metadata only): `count_before=4`, `count_after=4`, `order_preserved=True`.

## Notes (Non-Behavioral)
- Step subprocess stdout/stderr is captured by `cli/run_ingestion.py` on success; step-emitted `[VECTOR_DEBUG]` lines may not appear in the top-level ingestion log even when `GOODQ_VECTOR_DEBUG=1`. `memory_commit_events` is the authoritative write-attempt record.
- This proof intentionally does not include raw logs, SQLite databases, Qdrant dumps, or media files.
