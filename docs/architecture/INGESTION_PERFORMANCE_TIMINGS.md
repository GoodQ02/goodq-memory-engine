# Ingestion Performance Timings Report

This report summarizes execution metrics for the GoodQ4All local multimodal ingestion pipeline, compiled from the `step_runs.jsonl` logs for epoch `epoch_2026_05_22_family_full_01`.

---

## Executive Summary

*   **Total Video Ingestion Runs Analyzed**: 3 (Unique Videos)
*   **Total Cumulative Pipeline Time**: 285.65 minutes (17139.2 seconds)
*   **Average Ingestion Time per Video**: 95.22 minutes (5713.1 seconds)

---

## Detailed Step Performance Leaderboard

The table below breaks down performance metrics across all pipeline steps, ordered by cumulative total duration (descending).

| Step Name | Executions | Total Time (s) | Avg Duration (s) | Min Duration (s) | Max Duration (s) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `audio_unified_wsl2` | 147 | 9420.75s | 64.09s | 45.00s | 124.22s |
| `video_scene_detect` | 5 | 1176.26s | 235.25s | 0.00s | 426.13s |
| `tagger` | 298 | 1068.20s | 3.58s | 0.00s | 4.94s |
| `text_embed` | 297 | 854.39s | 2.88s | 0.00s | 6.21s |
| `object_detect` | 149 | 824.82s | 5.54s | 0.00s | 7.86s |
| `emotion_classify` | 149 | 660.22s | 4.43s | 0.00s | 7.74s |
| `audio_embed_clap` | 149 | 650.81s | 4.37s | 0.00s | 11.83s |
| `sentiment` | 149 | 520.64s | 3.49s | 0.00s | 5.20s |
| `image_ocr` | 149 | 475.62s | 3.19s | 0.00s | 6.30s |
| `image_caption` | 149 | 444.31s | 2.98s | 0.00s | 12.74s |
| `image_embed_dino` | 150 | 375.09s | 2.50s | 0.00s | 3.20s |
| `image_embed_clip` | 149 | 374.31s | 2.51s | 0.00s | 4.07s |
| `face_embed` | 149 | 155.48s | 1.04s | 0.00s | 2.87s |
| `cross_modal_harmonization` | 5 | 79.34s | 15.87s | 1.15s | 65.28s |
| `scene_visual_embeddings` | 5 | 52.59s | 10.52s | 2.91s | 38.11s |
| `audio_metadata` | 149 | 5.72s | 0.04s | 0.00s | 0.06s |
| `audio_time_hints` | 149 | 0.30s | 0.00s | 0.00s | 0.00s |
| `audio_music_events` | 149 | 0.19s | 0.00s | 0.00s | 0.00s |
| `audio_speaker_merge` | 149 | 0.14s | 0.00s | 0.00s | 0.00s |
| `audio_emotion` | 2 | 0.00s | 0.00s | 0.00s | 0.00s |

---

## Key Hardware Inferences & Recommendations

1.  **Diarization & Voice Processing (`audio_unified_wsl2` / Whisper)**:
    *   This is typically the most expensive phase of memory ingestion.
    *   Running under WSL2 with GPU acceleration (RTX 4070 Ti SUPER) reduces transcription to a fraction of playback runtime, whereas CPU-only execution can exceed real-time durations.
2.  **Visual Embeddings (`scene_visual_embeddings`)**:
    *   Generates 512-dim CLIP and 768-dim DINO vectors per scene keyframe.
    *   Execution is highly parallelized and benefits directly from CUDA core allocations.
3.  **Cross-Modal Harmonization (`cross_modal_harmonization`)**:
    *   A lightweight SQLite-centric logic pass that reconciles identified speakers, facial patterns, and transcripts.
    *   Takes negligible time but represents the core epistemic arbitration layer.
