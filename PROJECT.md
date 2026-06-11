# Project: GoodQ4All Codebase Indexing and Auditing

## Architecture
- This is a documentation, indexing, and skills integration project. It has no dynamic software dependencies but must safely query, map, and output documentation/metadata.
- No source code or configuration files outside the `docs/` folder are modified or deleted.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Planning & Setup | Initialize plan, briefing, progress, and project trackers | None | DONE |
| 2 | Codebase Indexing | Map Python modules in 10 directories to JSON/Markdown database | None | DONE |
| 3 | Codebase Health Audit | Crawl repositories for legacy/redundant code, write health audit | M2 | DONE |
| 4 | Workflow Skills Integration | Copy workflow skills from host scratch directory to docs/agent/skills/ | None | DONE |
| 5 | Validation & Handoff | Verify indexing completeness and health checklist, write final handoff | M2, M3, M4 | DONE |

## Interface Contracts
### Programmatic Index DB Format
- Output path: `docs/codebase_index/codebase_index.json`
- Schema: Dict mapping relative file path to its metadata (subsystem, imports, class/function definitions, tags)

### Codebase Health Audit Format
- Output path: `docs/codebase_index/codebase_health_audit.md`
- Content: Itemized checklist with clear explanations of legacy/redundant logic, outdated files, underutilized components.

### Workflow Skills Destination
- Destination: `docs/agent/skills/`
- Target skills: `using-agent-skills`, `documentation-and-adrs`, and other relevant workflow skills from host.

## Code Layout
- Input code paths: `agents/`, `api/`, `cli/`, `common/`, `configs/`, `lib/`, `pipelines/`, `retrieval/`, `steps/`, `wsl2_audio/`
- Output documentation paths: `docs/codebase_index/`, `docs/agent/skills/`
