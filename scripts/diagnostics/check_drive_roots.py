#!/usr/bin/env python3
"""
Fail-fast scanner for Windows drive-root literals in critical runtime paths.

Hard-fail scope:
- cli/**
- steps/**
- pipelines/**
- api/**
- wsl2_audio/**
- lib/**
- selected runtime scripts under scripts/

Allowlist:
- docs/**
- tests/**
- archive folders
- backup files
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVE_ROOT_PATTERN = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]")

RUNTIME_ROOTS = [
    REPO_ROOT / "cli",
    REPO_ROOT / "steps",
    REPO_ROOT / "pipelines",
    REPO_ROOT / "api",
    REPO_ROOT / "wsl2_audio",
    REPO_ROOT / "lib",
]

RUNTIME_SCRIPT_FILES = [
    REPO_ROOT / "scripts" / "monitor_ingestion.py",
    REPO_ROOT / "scripts" / "promote_wsl_audio.py",
    REPO_ROOT / "scripts" / "rotate_logs.py",
    REPO_ROOT / "scripts" / "setup" / "install_goodq.py",
]

ALLOWLIST_PATH_PARTS = {
    "docs",
    "tests",
    "archive",
    "__pycache__",
}
CODE_EXTENSIONS = {".py", ".sh", ".ps1", ".bat"}


def _is_allowlisted(path: Path) -> bool:
    parts = set(path.parts)
    if parts.intersection(ALLOWLIST_PATH_PARTS):
        return True
    name = path.name.lower()
    if "backup" in name or name.endswith(".bak"):
        return True
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return False


def _iter_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        if not _is_allowlisted(root):
            yield root
        return
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in CODE_EXTENSIONS:
            continue
        rel = path.relative_to(REPO_ROOT)
        if _is_allowlisted(rel):
            continue
        yield path


def _scan_file(path: Path) -> List[Tuple[int, str]]:
    hits: List[Tuple[int, str]] = []
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return hits
    except OSError:
        return hits

    for idx, line in enumerate(content.splitlines(), start=1):
        if DRIVE_ROOT_PATTERN.search(line):
            hits.append((idx, line.strip()))
    return hits


def main() -> int:
    targets = [*RUNTIME_ROOTS, *RUNTIME_SCRIPT_FILES]
    violations: List[Tuple[Path, int, str]] = []
    seen: set[Path] = set()
    for target in targets:
        for file_path in _iter_files(target):
            if file_path in seen:
                continue
            seen.add(file_path)
            for line_no, text in _scan_file(file_path):
                violations.append((file_path, line_no, text))

    if violations:
        print("Drive-root literal violations detected:")
        for file_path, line_no, text in violations:
            rel = file_path.relative_to(REPO_ROOT)
            print(f"  {rel}:{line_no}: {text}")
        print(f"\nFAILED: {len(violations)} violation(s)")
        return 1

    print("PASS: no drive-root literals in critical runtime paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
