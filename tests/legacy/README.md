# Legacy Test Scripts

**Purpose:** Historical diagnostic and one-off testing scripts  
**Status:** Archived - not part of active test suite  
**Moved:** December 15, 2025

---

## Contents

This directory contains temporary diagnostic scripts created during development and debugging sessions. These scripts were used for:

- **Database diagnostics** (`temp_check_db*.py`, `temp_db_*.py`)
- **Scene analysis** (`temp_check_scenes.py`, `temp_scene_analysis.py`)
- **Configuration validation** (`temp_check_config.py`)
- **Sample data analysis** (`temp_analyze_*.py`, `temp_run_sample.py`)
- **System diagnostics** (`temp_full_diagnostic.py`)

---

## Why Archived?

These scripts served specific debugging purposes during development but:
- Are superseded by organized test suite (`tests/unit/`, `tests/integration/`, `tests/utils/`)
- May reference outdated code paths or configurations
- Were one-off diagnostic tools, not repeatable tests
- Could confuse users about which tests are current

---

## If You Need Them

These scripts are preserved for historical reference and may contain useful debugging patterns. However:

⚠️ **They may not work with current codebase**  
⚠️ **Use organized test suite for current testing**  
⚠️ **Check git history for context on when/why they were created**

---

## Current Testing

For current, maintained tests, use:
- **Unit tests:** `tests/unit/`
- **Integration tests:** `tests/integration/`
- **Utilities:** `tests/utils/`
- **Quick tests:** `tests/run_test_ingestion.py`, `tests/test_wsl_audio.py`

See `tests/README.md` for complete testing documentation.

---

**Archived:** December 15, 2025  
**Reason:** GitHub release preparation - cleanup of forward-facing documentation
