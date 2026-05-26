<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_CANONICAL_POINTER: docs/architecture/SYSTEM_ARCHITECTURE.md -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

> [!WARNING]
> ARCHIVE / NON-CANONICAL / DO NOT COPY PATHS
> This document is preserved as historical evidence and may contain obsolete fixed-drive paths, host-specific assumptions, stale commands, or superseded runtime guidance.
> Do not use it for current runtime, setup, migration, or copy-paste path decisions.
> Use active documentation, `config_loader`, and canonical path abstractions such as `<project_root>`, `<GOODQ_DATA_ROOT>`, and `<GOODQ_WSL_WORKSPACE>` instead.

# L:/ Drive Architecture Audit
**Date:** 2025-11-19  
**Purpose:** Comprehensive analysis of L:/ drive structure, GitHub repo relationship, and system integration  
**Status:** ✅ Production System Analysis Complete

---

## 🎯 Executive Summary

The L:/ drive serves as a **unified development and production environment** for GoodQ4All, acting as:
1. **GitHub Repository** (`L:\goodq4all\`) - Version-controlled codebase
2. **System Sandbox** (`L:\`) - Large file storage, models, datasets, and runtime data
3. **Isolated Storage** - Keeping large assets (models, media, databases) out of GitHub

### Key Findings
- ✅ **Architecture is CORRECT**: Nested structure is intentional and follows Python packaging standards
- ⚠️ **Some redundancy exists**: Memory/data storage scattered across multiple locations
- ✅ **L:/ isolation working**: Models, datasets, and large files properly stored outside repo
- 🔧 **Needs consolidation**: Multiple memory.db and knowledge_graph.db locations need reconciliation

---

## 📁 L:/ Drive Structure Analysis

### Top-Level Organization

```
L:\
├── goodq4all\               # GitHub repository root (version controlled)
├── _DATA\                   # Runtime data (NOT in GitHub)
├── _TOOLS\                  # External tools and utilities
├── _UI\                     # UI assets and builds
├── _WORKSPACE\             # Working directory for experiments
├── _ARCHIVE\               # Historical/backup data
├── models\                  # Model cache (shared across projects)
├── tools\                   # Additional tooling
└── System Volume Information\  # Windows system files
```

---

## 🎯 goodq4all/ - GitHub Repository

### Purpose
- **Primary**: Version-controlled Python package and application code
- **Relationship**: This IS the git repository (`git remote` points here)
- **Structure**: Standard Python project layout with nested package

### Key Directories

#### `/goodq4all/goodq4all/` - Python Package (REQUIRED)
**Purpose:** This nested structure is INTENTIONAL and CORRECT
- Outer `goodq4all/` = Repository root (git, docs, scripts, configs)
- Inner `goodq4all/` = Importable Python package

**Why It Exists:**
```python
# Enables imports like:
from goodq4all.lib.llm_client import LLMClient
from goodq4all.steps.audio_transcribe import transcribe_step
```

**Contains:**
- `/lib/` - Core library modules
- `/steps/` - ZenML step implementations  
- `/pipelines/` - Pipeline orchestration
- `/api/` - FastAPI server endpoints
- `/cli/` - Command-line tools
- `/__init__.py` - Package initialization

#### `/goodq4all/api/` - Web API Server
**Status:** ✅ ACTIVE - Consolidated to main.py
**Purpose:** FastAPI endpoints for UI and external integrations
**Port:** 30000 (unified)
**Recent Changes:** All endpoints migrated to `/api/main.py`

#### `/goodq4all/configs/` - Configuration
**Status:** ✅ ACTIVE
**Files:**
- `config_open.yaml` - Main runtime config
- `paths.yaml` - Canonical path definitions
- `model_registry.yaml` - Pinned model versions
- `entities.yaml` - Home Assistant entities

#### `/goodq4all/data/` - Local Runtime Data
**Status:** ⚠️ NEEDS CONSOLIDATION
**Current Use:** Temporary/cache storage
**Issue:** Duplicates data also in `L:\_DATA\GoodQ_Data\`
**Recommendation:** Migrate to `L:\_DATA\` exclusively

#### `/goodq4all/docs/` - Documentation
**Status:** ✅ WELL ORGANIZED (as of 2025-11-15)
**Subdirectories:**
- `/audits/` - System audit reports
- `/phases/` - Development milestones
- `/releases/` - Release documentation
- `/wsl2/` - WSL integration guides
- `/guides/` - User and technical guides

#### `/goodq4all/scripts/` - Utilities
**Status:** ✅ CONSOLIDATED (2025-11-15)
**Contains:** All BAT, PS1, and Python utility scripts
**Key Scripts:**
- `launch_goodq.bat` - Main system launcher
- `system_readiness_check.py` - Health validation
- `download_datasets.py` - Dataset caching

#### `/goodq4all/web/` or `/goodq4all/_UI/`
**Status:** ⚠️ INVESTIGATE
**Issue:** UI files currently in `L:\_UI\`, may need consolidation
**Files:** index.html, dashboard.html, CSS, JS

---

## 🗄️ L:\_DATA\ - Runtime Data Storage

### Purpose
Large files and runtime data NOT suitable for GitHub

### Current Structure
```
L:\_DATA\
├── GoodQ_Data\              # Primary data directory
│   ├── logs\               # Step execution logs
│   ├── outputs\            # Processing outputs
│   ├── memory.db           # ⚠️ Duplicate DB location?
│   └── knowledge_graph.db  # ⚠️ Duplicate DB location?
├── FAMILY_FEAST\           # Sample/test media?
├── cache\                  # General cache
├── datasets\               # Downloaded datasets
└── models\                 # Model weights (duplicates L:\models?)
```

### Issues Found
1. **Database Duplication**
   - `memory.db` exists in multiple locations
   - `knowledge_graph.db` scattered
   - **Action Needed:** Define canonical location in `paths.yaml`

2. **Model Storage Confusion**
   - Both `L:\_DATA\models\` and `L:\models\` exist
   - **Recommendation:** Use `L:\models\` exclusively (already in use)

---

## 🤖 L:\models\ - Model Cache

### Purpose
Centralized model storage for ALL projects (not just goodq4all)

### Current Structure
```
L:\models\
├── hf\                      # Hugging Face models
│   ├── hub\                # HF Hub cache
│   └── datasets\           # HF datasets cache
├── llm\                     # LLM-specific models
├── yolo\                    # YOLO weights
├── embeddings\              # Embedding models
├── lexicons\                # NRC lexicons
└── torch\                   # PyTorch cache
```

### Configuration
```yaml
# From .env / environment variables
HF_HOME=L:\models\hf
TORCH_HOME=L:\models\torch
```

### Status
✅ **CORRECT** - Centralized, shared, outside GitHub

---

## 🔧 Configuration Alignment Issues

### Memory Database Locations
**Problem:** Multiple `memory.db` references

**Found in:**
1. `L:\goodq4all\data\memory.db`
2. `L:\_DATA\GoodQ_Data\memory.db`  
3. `L:\_DATA\knowledge_graph.db` (different schema?)

**Solution Required:**
```yaml
# configs/paths.yaml should define ONE canonical location:
database:
  memory: "L:\\_DATA\\GoodQ_Data\\memory.db"
  knowledge_graph: "L:\\_DATA\\GoodQ_Data\\knowledge_graph.db"
```

### UI File Locations
**Problem:** UI files scattered

**Current:**
- `L:\_UI\` - Some UI assets
- `L:\goodq4all\web\` - Web components?
- API serves from `/goodq4all/_UI/`?

**Recommendation:**
```
L:\goodq4all\
  └── web\
      ├── index.html
      ├── dashboard.html
      ├── css\
      ├── js\
      └── assets\
```

---

## 🎯 Recommended Consolidation Plan

### Phase 1: Database Consolidation
```powershell
# 1. Verify canonical location
$CANONICAL_DB = "L:\_DATA\GoodQ_Data\memory.db"

# 2. Update paths.yaml
# 3. Migrate any orphaned data
# 4. Update all scripts to use paths.yaml
```

### Phase 2: UI Organization  
```powershell
# Move all UI to L:\goodq4all\web\
# Update API static file serving
# Remove L:\_UI\ if redundant
```

### Phase 3: Model Cache Cleanup
```powershell
# Remove L:\_DATA\models\ if duplicate
# Ensure all envs use L:\models\
```

---

## 📊 Storage Breakdown

| Location | Purpose | Size | In GitHub? |
|----------|---------|------|------------|
| `L:\goodq4all\` | Code repository | ~500MB | ✅ Yes |
| `L:\_DATA\` | Runtime data | ~50GB+ | ❌ No (.gitignore) |
| `L:\models\` | Model cache | ~100GB+ | ❌ No (.gitignore) |
| `L:\_ARCHIVE\` | Backups/history | Variable | ❌ No |
| `L:\_TOOLS\` | External tools | ~5GB | ❌ No |

---

## ✅ What's Working Well

1. **Separation of Concerns**
   - Code (GitHub) vs Data (L:\_DATA) vs Models (L:\models)
   - Large files properly excluded from version control

2. **Model Centralization**
   - `L:\models\` shared across environments
   - Environment variables properly set

3. **Documentation**
   - Comprehensive docs in `/goodq4all/docs/`
   - Well-organized by topic and phase

---

## 🔧 Action Items

### High Priority
- [ ] Consolidate database locations (define canonical in paths.yaml)
- [ ] Verify UI file locations and consolidate
- [ ] Remove duplicate model caches

### Medium Priority
- [ ] Audit `L:\_DATA\GoodQ_Data\` vs `L:\goodq4all\data\`
- [ ] Document purpose of `L:\_WORKSPACE\`
- [ ] Clean up `L:\_ARCHIVE\` if no longer needed

### Low Priority
- [ ] Consider moving `L:\_TOOLS\` into `L:\goodq4all\vendor\`
- [ ] Standardize naming (underscores vs no underscores)

---

## 📖 References

- **README**: `L:\goodq4all\README.md`
- **Architecture**: `docs/ARCHITECTURE_REFERENCE.md`
- **Project Structure**: `docs/PROJECT_STRUCTURE.md`
- **Current Status**: `docs/CURRENT_SYSTEM_STATUS.md`

---

## 🎓 Key Insights

1. **The nested goodq4all/goodq4all/ is CORRECT**
   - Standard Python packaging pattern
   - Enables proper imports
   - DO NOT flatten

2. **L:/ acts as development sandbox**
   - GitHub repo lives here
   - Large files isolated from repo
   - Shared resources (models) available to all projects

3. **Some consolidation needed**
   - Database locations need reconciliation
   - UI files should have one home
   - Duplicate model caches should be removed

---

**Next Steps:** Review this audit and proceed with Phase 1 consolidation (database locations).
