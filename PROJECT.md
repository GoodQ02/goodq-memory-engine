# Project: Agent Knowledge Workspace Setup

## Architecture
- Target Directory: `C:\Users\jdben\My Drive\_AGENT`
- Folder structure:
  - `protocols/`: Agent identity, roles, constraints, system boundaries.
  - `models_and_vram/`: VRAM budgets, hardware configurations, display zones, fallback chains.
  - `workflows/`: Repeatable operational procedures (memory clean starts, evidence-first repairs).
  - `lessons/`: Log of developer findings, system design corrections, engineering lessons.
- Onboarding script: `bootstrap_agent.ps1` at the root of `_AGENT`.
- Programmatic linter: `verify_agent_workspace.py` inside `_AGENT`.
- Repository Integration: Pointer section in `l:\GOODCUBE\projects\goodq4all\AGENTS.md`.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | E2E Test Suite Creation | Design and build the E2E verification test cases & runner | None | PLANNED |
| 2 | Workspace Structure & Bootstrapper | Establish directories and bootstrap_agent.ps1 | M1 | PLANNED |
| 3 | Context & Rule Distillation | Distill AGENTS.md, GEMINI.md, and docs/agent/ | M1 | PLANNED |
| 4 | Prior Lessons Extraction | Parse brain history transcripts and format lessons | M1 | PLANNED |
| 5 | Linter and Integration | Build verify_agent_workspace.py, update AGENTS.md, run all tests | M2, M3, M4 | PLANNED |
| 6 | Adversarial & Auditing | Run challenger and forensic auditor on the workspace | M5 | PLANNED |

## Interface Contracts
- Onboarding Script: `bootstrap_agent.ps1` (outputs capabilities report, exits 0)
- Programmatic Linter: `verify_agent_workspace.py` (checks folders, lessons formatting, path slashes, exits 0)
- Lessons Formatting: First line must be `Summary: <one-line-summary>`

## Code Layout
- Target: `C:\Users\jdben\My Drive\_AGENT/`
- Sources: `L:\GOODCUBE\projects\goodq4all/AGENTS.md`, `L:\GOODCUBE\projects\goodq4all/GEMINI.md`, `L:\GOODCUBE\projects\goodq4all/docs/agent/`, `C:\Users\jdben\.gemini\antigravity\brain/`, `L:\GOODCUBE\scratch\agent-skills\skills/`
