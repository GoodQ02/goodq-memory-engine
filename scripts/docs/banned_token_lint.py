#!/usr/bin/env python3
"""Linter to scan the repository for banned static confirmation tokens.

Excludes unit/integration tests and local developer caches.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Construct the token dynamically to avoid self-match violations
BANNED_TOKEN = "confirm" + "-" + "123"

TARGET_SUFFIXES = {
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".sh",
    ".bat",
    ".ps1",
    ".nsi",
    ".js",
    ".ts",
    ".html",
    ".css",
    ".md",
    ".txt",
}

EXCLUDED_DIR_NAMES = {
    ".git",
    ".worktrees",
    ".gemini",
    ".agents",
    "brain",
    "tests",
    "__pycache__",
    "envs",
    "node_modules",
    "_ci",
}


def is_excluded(path: Path, repo_root: Path) -> bool:
    # Check if any parent component is in excluded directory names
    try:
        relative = path.relative_to(repo_root)
        for part in relative.parts[:-1]:
            if part in EXCLUDED_DIR_NAMES:
                return True
    except Exception:
        pass
    return False


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    violations: list[tuple[Path, int, str]] = []

    # Recursively find all files
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TARGET_SUFFIXES:
            continue
        if is_excluded(path, repo_root):
            continue
        if path.name == "banned_token_lint.py":
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            print(f"[WARNING] Unable to read file {path}: {exc}")
            continue

        for line_no, line in enumerate(content.splitlines(), start=1):
            if BANNED_TOKEN in line.lower():
                relative_path = path.relative_to(repo_root).as_posix()
                if relative_path in {
                    "docs/agent/CURRENT_STATE.md",
                    "docs/agent/skills/goodq4all-audit/SKILL.md",
                    "docs/goodq4all_agent_status.md"
                }:
                    continue
                violations.append((path, line_no, line.strip()))

    if violations:
        print(f"[ERROR] Found {len(violations)} occurrences of banned token '{BANNED_TOKEN}':")
        for path, line_no, line in violations:
            print(f"  {path.relative_to(repo_root).as_posix()}:{line_no}: {line}")
        return 1

    print("Banned token check passed. No forbidden tokens found outside allowed docs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
