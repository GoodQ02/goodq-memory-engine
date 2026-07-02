# Project: GoodQ4All v2.5.8-rc5 Comprehensive Final Release Audit

## Architecture
- **Installed Runtime Resolution**: In installed mode, the launcher and runtime must strictly use the relative `.\runtime\python.exe` binary. It must fail visibly if this file is missing to prevent fallback to system Python.
- **Bootstrap Intercept**: The launcher must parse the bootstrap report (`bootstrap_report.json` or similar) to intercept and display failures on first-run setup.
- **WSL Distro Mapping**: WSL integration maps dynamically, preferring `GoodQ_Audio_Distro` for GPU/audio workloads.
- **Model Token Safety**: Hugging Face gated models are skipped or warning messages are logged on missing credentials instead of halting the launch flow.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Codebase Cross-Reference Verification | Verify python.exe resolution, bootstrap reporting, version surfaces, WSL fallback, and gated model token handling. | None | DONE |
| 2 | M2: Post-Build Installer & Manifest Validation | Verify setup.exe and launcher hashes, source_commit, and source_tree_clean status. | None | DONE |
| 3 | M3: Linter & Static Analysis Verification | Execute doc, dependency, and banned token linters, and run pytest unit tests. | None | DONE |
| 4 | M4: Forensic Verification and Final Synthesis | Run the forensic auditor, aggregate all streams, and compile the final audit report. | M1, M2, M3 | DONE |

## Interface Contracts
- **Version Surfacing**: Version strings must match exactly across all 8 surfaces (NSIS, versioninfo.json, goodq_version.py, etc.).
- **Installer Manifest**: Manifest metadata `source_commit` must align with the target tag and HEAD commit, and `source_tree_clean` must be `true`.

## Code Layout
- `goodq_version.py` - Core package version definitions
- `scripts/install/` - NSIS build scripts, compiler configs, and sync scripts
- `dist/` - Released installers and JSON manifests
- `tests/unit/` - Unit tests for configuration, launcher, and APIs
- `scripts/utils/` - Static linters (banned_token_lint.py, doc_drift_lint.py)
