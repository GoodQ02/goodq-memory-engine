# Project: GoodQ4All Legacy Audio Steps Archival

## Architecture
- Relocate and archive legacy Windows-native steps to `archive/` directory.
- Relocate unit tests to `tests/legacy/`.
- Clean up deprecated test functions in `tests/unit/test_bootstrap_install_wsl.py`.
- Run all unit tests to verify codebase behavior.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Planning & Setup | Initialize plan, briefing, progress, and project trackers | None | DONE |
| 2 | Codebase Indexing | Map Python modules in 10 directories to JSON/Markdown database | None | DONE |
| 3 | Codebase Health Audit | Crawl repositories for legacy/redundant code, write health audit | M2 | DONE |
| 4 | Workflow Skills Integration | Copy workflow skills from host scratch directory to docs/agent/skills/ | None | DONE |
| 5 | Validation & Handoff | Verify indexing completeness and health checklist, write final handoff | M2, M3, M4 | DONE |
| 6 | Legacy Audio Steps Archival | Move steps files to `archive/` | None | DONE |
| 7 | Unit Tests Relocation | Relocate test files to `tests/legacy/` | None | DONE |
| 8 | WSL Test Cleanup | Delete deprecated test functions in `tests/unit/test_bootstrap_install_wsl.py` | None | DONE |
| 9 | Audit Report & Test Execution | Check off audit report box, run all 700+ pytest tests inside goodq_core | M6, M7, M8 | DONE |

## Interface Contracts
### Programmatic Index DB Format
- Output path: `docs/codebase_index/codebase_index.json`
- Schema: Dict mapping relative file path to its metadata (subsystem, imports, class/function definitions, tags)

### Codebase Health Audit Format
- Output path: `docs/codebase_index/codebase_health_audit.md`
- Content: Update "Legacy Local Audio Steps" to [x] RESOLVED with status note.

### Workflow Skills Destination
- Destination: `docs/agent/skills/`
- Target skills: `using-agent-skills`, `documentation-and-adrs`, and other relevant workflow skills from host.

## Code Layout
- Input code paths: `agents/`, `api/`, `cli/`, `common/`, `configs/`, `lib/`, `pipelines/`, `retrieval/`, `steps/`, `wsl2_audio/`, `tests/`
- Output/Archive paths: `archive/`, `tests/legacy/`, `docs/codebase_index/`

