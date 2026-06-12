# Codebase Health Audit Report

## 1. Executive Summary

This codebase health audit provides an itemized analysis of the legacy scripts, outdated files, step runner mapping issues, and redundant or underutilized modules in the GoodQ4All repository. 

As the codebase has transitioned toward a unified, WSL2-based GPU-accelerated audio pipeline (leveraging PyTorch, Faster Whisper, and PyAnnote in WSL2), several Windows-native steps and transitional compatibility facades have become obsolete. Additionally, a couple of configuration/mapping mismatches have been identified that could cause runtime errors.

---

## 2. Itemized Health Audit Checklist

### [x] Legacy Local Audio Steps (CPU/GPU-heavy Windows scripts) (RESOLVED)
*   **Path**: `steps/audio_diarize/step.py`
    *   **Description**: Contains local PyAnnote pipeline diarization logic requiring massive environment footprint (200+ Python packages).
    *   **Status**: **RESOLVED**. Archived to `archive/deprecated_audio_diarize_step.py`.
    *   **Recommendation**: Keep as fallback reference or deprecate/remove.
*   **Path**: `steps/audio_transcribe/step.py`
    *   **Description**: Local Faster Whisper execution.
    *   **Status**: **RESOLVED**. Archived to `archive/deprecated_audio_transcribe_step.py`.
    *   **Recommendation**: Keep as fallback reference or deprecate/remove.
*   **Path**: `steps/audio_emotion/step.py`
    *   **Description**: Local HuBERT/Wav2Vec2 speech emotion classification.
    *   **Status**: **RESOLVED**. Archived to `archive/deprecated_audio_emotion_step.py`.
    *   **Recommendation**: Keep as fallback reference or deprecate/remove.

### [ ] Transitional WSL2 Compatibility Facades
*   **Paths**: `steps/audio_diarize/step_wsl2.py` and `steps/audio_transcribe/step_wsl2.py`
    *   **Description**: Older single-purpose WSL2 wrappers that invoke `wsl2_audio/audio_bridge.py`.
    *   **Status**: **Superceded**. The pipeline now runs `steps/audio/audio_wsl2_bridge.py` directly for unified processing.
    *   **Recommendation**: Retain for test suite backward-compatibility but mark as deprecated.
*   **Paths**: `steps/audio_ingest_unified/step_wsl2.py` and `wsl2_audio/audio_bridge.py`
    *   **Description**: Transitional facade interfaces that delegate tasks to `scripts.wsl2_audio_bridge`.
    *   **Status**: **Legacy Compatibility**.
    *   **Recommendation**: Keep for backwards compatibility with older pipelines but avoid using in new runs.

### [x] Broken Step Mapping in `cli/step_runner.py` (RESOLVED)
*   **Path**: `cli/step_runner.py` (Line 199 or surrounding)
    *   **Issue**: Mismatch in `object_track` key mapping.
    *   **Details**: The registry contained:
        ```python
        "object_track": lambda cfg: import_module("steps.object_track.step").object_track
        ```
        However, there was no directory `steps/object_track` in the codebase; only `steps/object_track_yolo` exists. Attempting to execute `object_track` via `step_runner.py` threw an immediate `ImportError`.
    *   **Status**: **Resolved**. The step registry mapping has been updated to import and run `object_track_yolo` as a fallback/alias, ensuring safety.

### [ ] Redundant or Underutilized Steps
*   **Path**: `steps/tts/step.py` (Voice Synthesis) (REMOVED)
    *   **Description**: Voice synthesis using Piper/ElevenLabs.
    *   **Status**: **Resolved**. The entire `steps/tts/` folder has been deleted from the repository.
*   **Path**: `steps/pdf_text/step.py` (PDF Text Extraction)
    *   **Description**: Extracted text from PDF files using `pdftotext`.
    *   **Status**: **Underutilized**. Mapped in `step_runner.py` but unused in the main video/audio processing pipeline.
*   **Paths**: `steps/home_assistant_status/step.py` (Smart Home Context) and `steps/system_metrics/step.py` (System Resource Metrics)
    *   **Description**: Standalone auxiliary scripts for logging environmental and system context.
    *   **Status**: **Underutilized**. Not part of core video ingestion.
*   **Path**: `steps/discover_sources/step.py` (Inbox Scanner)
    *   **Description**: Scans inbox folder for new media files.
    *   **Status**: **Underutilized**. Only called by `cli/list_inbox.py` for displaying pending items; not used in processing.

---

## 3. Detailed Audit & Architecture Findings

### A. The WSL2 Audio Transition
The primary driver of legacy code in the `steps/` directory is the shift to a **unified WSL2 audio execution model**. Running heavy machine learning pipelines (Faster Whisper and PyAnnote) on Windows desktops proved fragile due to package dependency conflicts, CUDA version mismatches, and file locking issues. Offloading these tasks to a dockerized/virtualized WSL2 service (`wsl2_audio/audio_service.py`) solved environment complexity, but left behind several local-execution steps (`steps/audio_diarize/step.py`, etc.).

During production runs, the orchestrator (`cli/run_ingestion.py`) bypasses all transitional audio steps and calls the unified WSL2 bridge `steps/audio/audio_wsl2_bridge.py` (`audio_unified_wsl2`) directly. This collects diarization, transcription, emotion, and speaker identification results in a single WSL2 transaction, making the intermediate single-task steps completely dormant.

### B. Directory Structure & Mapping Correctness
*   `control_recurrence_report.py` is duplicated in name under both `cli/` and `lib/`. However, this is **not a bug** but a clean separation of concerns:
    *   `cli/control_recurrence_report.py` defines the command-line flags and entry point.
    *   `lib/control_recurrence_report.py` implements the comparative reporting and rendering logic.
*   The `object_track` mapping in `cli/step_runner.py` is a genuine bug. The folder is named `steps/object_track_yolo`, but the runner lists:
    ```python
    "object_track": lambda cfg: import_module("steps.object_track.step").object_track
    ```
    This should be corrected or documented as a known defect.
