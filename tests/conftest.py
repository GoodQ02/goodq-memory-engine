from __future__ import annotations

import os
import sys
from pathlib import Path

# Prevent OpenMP duplicate initialization crash on Windows when running full suite
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

REPO_ROOT = Path(__file__).resolve().parents[1]
repo_root_str = str(REPO_ROOT)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)
