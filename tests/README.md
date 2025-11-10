# GoodQ4All Test Suite

**Created:** November 7, 2025  
**Purpose:** Organized test suite for GoodQ4All project  
**Structure:** Unit, Integration, and Utility tests

---

## Directory Structure

```
tests/
├── README.md           # This file
├── __init__.py         # Python package marker
├── unit/               # Unit tests (isolated component testing)
│   ├── __init__.py
│   ├── test_db_creation.py
│   ├── test_memory_context.py
│   ├── test_config_values.py
│   └── test_knowledge_graph.py
├── integration/        # Integration tests (multi-component testing)
│   ├── __init__.py
│   ├── test_watchdog.py
│   ├── test_ingestion_verbose.py
│   ├── test_scene_comprehensive.py
│   └── verify_clip.py
└── utils/              # Test utilities and validation scripts
    ├── __init__.py
    ├── test_hf_auth.py
    ├── test_clean_run.py
    ├── test_mission_logger.py
    ├── quick_test_storage.py
    ├── validate_ingestion_output.py
    ├── validate_results.py
    └── validate_all_steps.py
```

---

## Test Categories

### Unit Tests (`tests/unit/`)

Isolated tests for individual components without external dependencies.

#### test_db_creation.py
- **Purpose:** Test SQLite database creation and schema
- **Coverage:** Database initialization, table creation, constraints
- **Dependencies:** None (uses in-memory DB)
- **Run:** `python tests/unit/test_db_creation.py`

#### test_memory_context.py
- **Purpose:** Test memory context management
- **Coverage:** Context storage, retrieval, deduplication
- **Dependencies:** SQLite
- **Run:** `python tests/unit/test_memory_context.py`

#### test_config_values.py
- **Purpose:** Test configuration loading and validation
- **Coverage:** YAML parsing, environment variables, defaults
- **Dependencies:** None
- **Run:** `python tests/unit/test_config_values.py`

#### test_knowledge_graph.py
- **Purpose:** Test knowledge graph construction
- **Coverage:** Entity extraction, relationship building, queries
- **Dependencies:** SQLite
- **Run:** `python tests/unit/test_knowledge_graph.py`

---

### Integration Tests (`tests/integration/`)

End-to-end tests that validate multiple components working together.

#### test_watchdog.py
- **Purpose:** Test watchdog file monitoring system
- **Coverage:** File detection, queue management, processing triggers
- **Dependencies:** Filesystem, watchdog library
- **Run:** `python tests/integration/test_watchdog.py`

#### test_ingestion_verbose.py
- **Purpose:** Test full ingestion pipeline with detailed output
- **Coverage:** Scene detection → processing → storage
- **Dependencies:** All pipeline steps, test video
- **Run:** `python tests/integration/test_ingestion_verbose.py`

#### test_scene_comprehensive.py
- **Purpose:** Comprehensive scene detection testing
- **Coverage:** Threshold tuning, scene quality, performance
- **Dependencies:** PySceneDetect, test videos
- **Run:** `python tests/integration/test_scene_comprehensive.py`

#### verify_clip.py
- **Purpose:** Verify CLIP embedding generation
- **Coverage:** CLIP model loading, embedding creation, storage
- **Dependencies:** CLIP model, CUDA (optional)
- **Run:** `python tests/integration/verify_clip.py`

---

### Utility Tests (`tests/utils/`)

Testing and validation utilities for development and debugging.

#### test_hf_auth.py
- **Purpose:** Test HuggingFace authentication
- **Coverage:** Token validation, gated model access
- **Dependencies:** HF_TOKEN environment variable
- **Run:** `python tests/utils/test_hf_auth.py`

#### test_clean_run.py
- **Purpose:** Test clean pipeline run after reset
- **Coverage:** Database cleanup, fresh start validation
- **Dependencies:** Full system
- **Run:** `python tests/utils/test_clean_run.py`

#### test_mission_logger.py
- **Purpose:** Test mission logging system
- **Coverage:** Log formatting, run tracking, metrics
- **Dependencies:** Logging infrastructure
- **Run:** `python tests/utils/test_mission_logger.py`

#### quick_test_storage.py
- **Purpose:** Quick validation of storage systems
- **Coverage:** DB connectivity, FAISS indices, file access
- **Dependencies:** SQLite, FAISS
- **Run:** `python tests/utils/quick_test_storage.py`

#### validate_ingestion_output.py
- **Purpose:** Validate ingestion pipeline output
- **Coverage:** Completeness checks, quality metrics
- **Dependencies:** Completed ingestion run
- **Run:** `python tests/utils/validate_ingestion_output.py`

#### validate_results.py
- **Purpose:** Validate processing results
- **Coverage:** Embedding quality, metadata accuracy
- **Dependencies:** Processed data
- **Run:** `python tests/utils/validate_results.py`

#### validate_all_steps.py
- **Purpose:** Validate all pipeline steps independently
- **Coverage:** Each step's functionality, environment isolation
- **Dependencies:** All 22 environments
- **Run:** `python tests/utils/validate_all_steps.py`

---

## Running Tests

### Individual Tests
```bash
cd L:\goodq4all

# Run specific unit test
python tests/unit/test_db_creation.py

# Run specific integration test
python tests/integration/test_watchdog.py

# Run specific utility
python tests/utils/validate_all_steps.py
```

### All Tests by Category
```bash
# Run all unit tests
python -m pytest tests/unit/

# Run all integration tests
python -m pytest tests/integration/

# Run all utility tests
python -m pytest tests/utils/
```

### All Tests
```bash
# Run entire test suite
python -m pytest tests/

# With verbose output
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=goodq4all
```

---

## Test Data

### Sample Data Location
Test data should be placed in:
```
L:\goodq4all\tests\data\
├── videos/         # Sample video files
├── audio/          # Sample audio files
├── images/         # Sample image files
└── fixtures/       # Test fixtures and mocks
```

### Creating Test Data
```bash
# Create test data directory
mkdir L:\goodq4all\tests\data

# Copy sample files
# (Add your test media files here)
```

---

## Test Environment

### Required Environments
Tests use the existing Conda environments:
- `goodq_zenml` - Main orchestration
- Environment-specific tests use their respective envs

### Environment Variables
Tests require:
```bash
HF_TOKEN=your_huggingface_token
PYANNOTE_TOKEN=your_pyannote_token
```

Set in `.env.local` or export manually.

---

## Continuous Integration

### GitHub Actions
Tests can be automated in CI/CD:

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest tests/
```

---

## Adding New Tests

### Test Naming Convention
- Unit tests: `test_<component>.py`
- Integration tests: `test_<feature>_integration.py`
- Utilities: `<purpose>_<action>.py`

### Test Structure Template
```python
"""
Test: test_new_feature.py
Purpose: Brief description
Category: Unit | Integration | Utils
Dependencies: List dependencies
"""

import unittest
from pathlib import Path

class TestNewFeature(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        pass
    
    def test_basic_functionality(self):
        """Test basic feature works"""
        result = your_function()
        self.assertTrue(result)
    
    def tearDown(self):
        """Clean up after tests"""
        pass

if __name__ == '__main__':
    unittest.main()
```

---

## Test Maintenance

### Review Schedule
- **Weekly:** Run full test suite
- **Before commits:** Run relevant tests
- **Before releases:** Complete test pass

### Coverage Goals
- **Unit tests:** 80%+ coverage
- **Integration tests:** Core workflows covered
- **Utilities:** All critical paths tested

### Updating Tests
When updating code:
1. Update related tests
2. Add tests for new features
3. Verify all tests pass
4. Update this README if structure changes

---

## Troubleshooting

### Common Issues

**Import Errors:**
```bash
# Ensure goodq4all is in Python path
export PYTHONPATH="${PYTHONPATH}:L:/goodq4all"
```

**Missing Dependencies:**
```bash
# Install test requirements
pip install pytest pytest-cov
```

**Environment Issues:**
```bash
# Verify environment
conda activate goodq_zenml
python -c "import goodq4all; print('OK')"
```

**Test Failures:**
1. Check logs in `L:\_DATA\GoodQ_Data\logs\`
2. Verify environment variables set
3. Ensure test data available
4. Check database connectivity

---

## Best Practices

### Writing Tests
- ✅ Test one thing per test
- ✅ Use descriptive test names
- ✅ Include docstrings
- ✅ Clean up test artifacts
- ✅ Make tests reproducible
- ✅ Mock external dependencies

### Test Data
- ✅ Use small sample files
- ✅ Include edge cases
- ✅ Document test data sources
- ✅ Version test data with tests
- ❌ Don't commit large files
- ❌ Don't use production data

### Test Organization
- ✅ Group related tests
- ✅ Use setUp/tearDown
- ✅ Share fixtures wisely
- ✅ Document dependencies
- ❌ Don't create test interdependencies
- ❌ Don't hardcode paths

---

## Migration Notes

**Moved from:** Various locations (scripts/, root/)  
**Moved on:** November 7, 2025  
**Reason:** Organizational cleanup Phase 2

**Previous Locations:**
- `scripts/test_*.py` → `tests/unit/` or `tests/integration/`
- Root `test_*.py` → `tests/integration/`
- Root `verify_*.py` → `tests/integration/`

**Import Changes:**
Old imports may need updating:
```python
# Old
from scripts.some_module import function

# New
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.some_module import function
```

---

## Related Documentation

- **Main README:** `L:\goodq4all\README.md`
- **Architecture:** `L:\goodq4all\docs\ARCHITECTURE_REFERENCE.md`
- **Script Audit:** `L:\goodq4all\docs\SCRIPT_AUDIT_REPORT_2025-11-07.md`
- **Contributing:** `L:\goodq4all\CONTRIBUTING.md` (to be created)

---

**Maintained by:** GoodQ Development Team  
**Last Updated:** November 7, 2025  
**Review Schedule:** Monthly

---

_This test suite ensures GoodQ4All maintains high quality and reliability through comprehensive automated testing._
