#!/usr/bin/env python3
"""Lint documentation drift against Bootstrap Contract semantics.

Checks:
1. Hardcoded L:/ paths are not allowed outside docs/archive/.
2. CUDA/NVIDIA mandatory wording is not allowed outside docs/guides/gpu/ and docs/archive/.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

L_PATH_PATTERN = re.compile(r"\bL:(?:/|\\)")

CUDA_MANDATORY_PATTERNS = [
    re.compile(r"\brequires?\s+cuda\b", re.IGNORECASE),
    re.compile(
        r"\bcuda\b.{0,40}\b(is required|required|mandatory for|must be installed|must be available)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bnvidia\s+gpu\b.{0,40}\b(is required|required|mandatory for|must be installed|must be available)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bmust\s+have\s+(an?\s+)?nvidia\s+gpu\b", re.IGNORECASE),
    re.compile(r"\bwithout\s+cuda\b.{0,40}\b(cannot run|will not run|unsupported)\b", re.IGNORECASE),
    re.compile(r"\bcpu[- ]only\b.{0,30}\b(not supported|unsupported)\b", re.IGNORECASE),
]


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def collect_targets(repo_root: Path) -> list[Path]:
    docs = sorted((repo_root / "docs").rglob("*.md"))
    readmes = sorted(repo_root.glob("README*.md"))
    return docs + readmes


def sanitize_console(text: str) -> str:
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    archive_root = repo_root / "docs" / "archive"
    gpu_guides_root = repo_root / "docs" / "guides" / "gpu"

    targets = collect_targets(repo_root)
    l_path_violations: list[tuple[Path, int, str]] = []
    cuda_violations: list[tuple[Path, int, str]] = []

    for file_path in targets:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            print(f"[ERROR] unable to read {file_path}: {exc}", file=sys.stderr)
            return 2

        in_archive = is_under(file_path, archive_root)
        in_gpu_guide = is_under(file_path, gpu_guides_root)

        for line_no, line in enumerate(text.splitlines(), start=1):
            if not in_archive and L_PATH_PATTERN.search(line):
                l_path_violations.append((file_path, line_no, line.strip()))

            if in_archive or in_gpu_guide:
                continue

            for pattern in CUDA_MANDATORY_PATTERNS:
                if pattern.search(line):
                    cuda_violations.append((file_path, line_no, line.strip()))
                    break

    for path, line_no, line in l_path_violations:
        print(f"[L_PATH] {path}:{line_no}: {sanitize_console(line)}")

    for path, line_no, line in cuda_violations:
        print(f"[CUDA_MANDATORY] {path}:{line_no}: {sanitize_console(line)}")

    print(
        f"doc_drift_lint summary: files_scanned={len(targets)} "
        f"l_path_violations={len(l_path_violations)} "
        f"cuda_mandatory_violations={len(cuda_violations)}"
    )

    return 1 if (l_path_violations or cuda_violations) else 0


if __name__ == "__main__":
    raise SystemExit(main())
