# Seinfeld Experiment Artifact Index

This directory is the canonical home for the Season 1 benchmark first-pass analysis outputs.

## Structure

- `diagnostics/`
  - `scene_segmentation_report.md`
  - `embedding_health_report.md`
  - `entity_analysis_report.md`
  - `kg_structure_report.md`
  - `semantic_pattern_report.md`
  - `experiment_summary.md`
  - `SEASON1_WITNESS_RUN_2026-03-09.md`
  - `POST_WITNESS_ANALYTICS_COMPARISON_2026-03-09.md`

- `releases/`
  - `season1_witness_run_2026-03-09/`
    - curated witness-release bundle and selected rerun snapshots

- `umap/`
  - `generate_umap_clip_text.py`
  - `scene_umap_clip_text.png`
  - `scene_umap_clip_text_coords.csv`
  - `scene_umap_clip_text_meta.json`

## Notes

- Runtime logs remain under `logs/` (canonical operational location).
- This folder contains post-ingestion analysis artifacts only.
- Latest control milestone: `diagnostics/experiment_summary.md` now records the 2026-03-09 formal Season 1 witness run.
- Formal witness record: `diagnostics/SEASON1_WITNESS_RUN_2026-03-09.md`
- Post-witness comparison pack: `diagnostics/POST_WITNESS_ANALYTICS_COMPARISON_2026-03-09.md`
- Permanent release bundle: `releases/season1_witness_run_2026-03-09/`
