# E2E Test Infrastructure

This document defines the E2E verification plan, tiers, and environment configurations for auditing the Agent Knowledge Workspace.

## 1. Overview
The testing track is designed to verify the compliance, structure, formatting, and onboarding functionality of the Agent Knowledge Workspace located at the target directory. It utilizes `pytest` to execute opaque-box and structured validation tests.

- **Workspace Target**: `%USERPROFILE%\My Drive\_AGENT` (referred to as `%WORKSPACE_ROOT%`)
- **Repository Integration Pointer**: `%GOODQ_ROOT%\AGENTS.md`
- **Test Runner Location**: `%GOODQ_ROOT%\tests\e2e\test_agent_workspace.py`

## 2. Test Execution Tiers
The E2E test suite is structured into 4 logical tiers of increasing complexity:

### Tier 1: Basic Smoke & Existence Checks
Verifies that the core folder tree (`protocols/`, `models_and_vram/`, `workflows/`, `lessons/`) exists, directories are readable/writeable, and required scripts (bootstrapper, linter) are present.

### Tier 2: Structure & Schema Checks
Asserts the content layout, checks that markdown files in rule folders are not empty, ensures relative path links are used for cross-references, and verifies that no literal Windows drive letters are hardcoded in the active documents.

### Tier 3: Execution & Integration Checks
Executes the linter (`verify_agent_workspace.py`) and onboarding bootstrapper (`bootstrap_agent.ps1`) under real and simulated environments, confirming they output appropriate capability reports and exit with a `0` code.

### Tier 4: Adversarial, Bounds & Integrity Checks
Performs negative and boundary testing. Verifies that the linter correctly flags missing directories, empty folders, non-conforming lesson headers, trailing slashes in path variables, and hardcoded drive roots. It also ensures the repository pointer in `AGENTS.md` maintains operating protocol integrity.

## 3. How to Run the Tests
Ensure you are in the correct conda environment (`goodq_core`) and execute:

```powershell
# Run the E2E test suite
conda run -n goodq_core pytest tests/e2e/test_agent_workspace.py
```

## 4. Feature Mapping and Inventory
The suite consists of exactly 82 test cases mapping to the 7 required features:

1. **Directory Tree Architecture (F1)**: Verification of folder existence, layout, and permissions (12 tests).
2. **Context & Rule Distillation (F2)**: Rule conversion correctness, absence of contradictions, and relative markdown links (12 tests).
3. **Lessons Learned Integration (F3)**: Enforcement of formatting rules including the `Summary: ` header line (12 tests).
4. **Programmatic Verification Linter (F4)**: Verification of the linter script execution, return codes, and rule coverage (12 tests).
5. **Previous Sessions Reflection & Lessons Extraction (F5)**: Ensuring lessons cover VRAM limits, installers, and pipeline debugging (11 tests).
6. **Agent Workspace Onboarding Bootstrapper (F6)**: Power Shell preflight check, capabilities reporting, and environment tests (12 tests).
7. **Repository Pointer Update (F7)**: Verifying `AGENTS.md` correctly points future agents to the workspace (11 tests).
