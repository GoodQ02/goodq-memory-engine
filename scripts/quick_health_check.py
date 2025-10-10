#!/usr/bin/env python3
"""Quick health check after lint session"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

print("=" * 70)
print("GOODQ HEALTH CHECK")
print("=" * 70)

checks = []

# 1. Imports
print("\n✓ Checking imports...")
try:
    from lib.knowledge_graph import KnowledgeGraph
    from lib.graph_query import GraphQuery  # Use the class instead
    from goodq4all.steps.common.config_loader import load_configs
    from goodq4all.steps.common.memory import ensure_scene
    checks.append(("Core imports", True))
    print("  ✓ All core modules import successfully")
except Exception as e:
    checks.append(("Core imports", False))
    print(f"  ✗ Import error: {e}")

# 2. Paths
print("\n✓ Checking paths...")
try:
    from configs.paths import (
        PROJECT_ROOT, DATA_ROOT, MEMORY_DB,
        LOGS_DIR, IMPORT_INBOX
    )
    paths_ok = all([
        PROJECT_ROOT.exists(),
        DATA_ROOT.exists(),
        IMPORT_INBOX.exists()
    ])
    checks.append(("Path configuration", paths_ok))
    if paths_ok:
        print("  ✓ All critical paths configured")
    else:
        print("  ⚠ Some paths missing (will be created on first run)")
except Exception as e:
    checks.append(("Path configuration", False))
    print(f"  ✗ Path error: {e}")

# 3. Database
print("\n✓ Checking database...")
try:
    from configs.paths import MEMORY_DB
    import sqlite3
    if not MEMORY_DB.exists():
        checks.append(("Database", True))
        print(f"  ⚠ Database will be created on first ingestion")
    else:
        conn = sqlite3.connect(str(MEMORY_DB))
        cursor = conn.cursor()
        # Check if schema exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scenes'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM scenes")
            scene_count = cursor.fetchone()[0]
            print(f"  ✓ Database accessible ({scene_count} scenes)")
        else:
            print(f"  ⚠ Database exists but schema not initialized (normal for first run)")
        conn.close()
        checks.append(("Database", True))
except Exception as e:
    checks.append(("Database", False))
    print(f"  ✗ Database error: {e}")

# 4. CLI Tools
print("\n✓ Checking CLI tools...")
try:
    import cli.run_ingestion
    import cli.memory
    import cli.retrieve
    checks.append(("CLI tools", True))
    print("  ✓ All CLI tools available")
except Exception as e:
    checks.append(("CLI tools", False))
    print(f"  ✗ CLI error: {e}")

# Summary
print("\n" + "=" * 70)
passed = sum(1 for _, ok in checks if ok)
total = len(checks)
print(f"RESULTS: {passed}/{total} checks passed")
print("=" * 70)

if passed == total:
    print("\n✅ ALL SYSTEMS GO! Ready for production testing.")
    sys.exit(0)
else:
    print("\n⚠️  Some checks failed. Review above for details.")
    sys.exit(1)
