#!/usr/bin/env python3
"""Lint documentation drift against Bootstrap Contract semantics.

Checks:
1. Hardcoded L:/ paths are not allowed outside docs/archive/.
2. Hardcoded drive-root paths (e.g., C:/, D:\\) are not allowed outside docs/archive/.
3. CUDA/NVIDIA mandatory wording is not allowed outside docs/guides/gpu/ and docs/archive/.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

L_PATH_PATTERN = re.compile(r"\bL:(?:/|\\)")
DRIVE_ROOT_PATTERN = re.compile(r"\b[A-Za-z]:[\\/]")
LEGACY_HINT_PATTERN = re.compile(r"\blegacy\b", re.IGNORECASE)

ALLOWED_LEGACY_DOCS = [
    "docs/technical/LEGACY_PATHS_DEPRECATED.md",
    "docs/architecture/DOCUMENTATION_REORGANIZATION_PLAN.md",
    "docs/guides/llm/LLM_IMPLEMENTATION_PLAN_PHASE1.md",
    "docs/diagnostics/ENV_DISCOVERY_REPORT.md",
    "docs/diagnostics/HOST_COMPAT_DISCOVERY_REPORT.md",
    "docs/diagnostics/HOST_COMPAT_PATCH_NOTES.md",
    "docs/diagnostics/LAUNCHER_PORTABILITY_DISCOVERY.md",
    "docs/diagnostics/LAUNCHER_PORTABILITY_PATCH_NOTES.md",
]

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
    docs = sorted(
        path
        for path in (repo_root / "docs").rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}
    )
    readmes = sorted(
        path
        for path in repo_root.glob("README*")
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}
    )
    return docs + readmes


def sanitize_console(text: str) -> str:
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    archive_root = repo_root / "docs" / "archive"
    gpu_guides_root = repo_root / "docs" / "guides" / "gpu"
    allowed_legacy_docs = set(ALLOWED_LEGACY_DOCS)

    targets = collect_targets(repo_root)
    l_path_violations: list[tuple[Path, int, str]] = []
    drive_root_violations: list[tuple[Path, int, str]] = []
    cuda_violations: list[tuple[Path, int, str]] = []

    for file_path in targets:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            print(f"[ERROR] unable to read {file_path}: {exc}", file=sys.stderr)
            return 2

        in_archive = is_under(file_path, archive_root)
        in_gpu_guide = is_under(file_path, gpu_guides_root)
        relative_path = file_path.relative_to(repo_root).as_posix()
        in_allowed_legacy_doc = relative_path in allowed_legacy_docs

        in_fenced_block = False
        in_legacy_fenced_block = False
        recent_context: list[str] = []

        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()

            if stripped.startswith("```"):
                if not in_fenced_block:
                    context_window = " ".join(recent_context[-3:])
                    in_legacy_fenced_block = bool(LEGACY_HINT_PATTERN.search(context_window))
                    in_fenced_block = True
                else:
                    in_fenced_block = False
                    in_legacy_fenced_block = False

                if stripped:
                    recent_context.append(stripped)
                continue

            skip_path_checks = in_archive or in_allowed_legacy_doc or (in_fenced_block and in_legacy_fenced_block)

            if not skip_path_checks and L_PATH_PATTERN.search(line):
                l_path_violations.append((file_path, line_no, stripped))

            if not skip_path_checks and DRIVE_ROOT_PATTERN.search(line):
                drive_root_violations.append((file_path, line_no, stripped))

            if in_archive or in_gpu_guide:
                if stripped:
                    recent_context.append(stripped)
                continue

            for pattern in CUDA_MANDATORY_PATTERNS:
                if pattern.search(line):
                    cuda_violations.append((file_path, line_no, stripped))
                    break

            if stripped:
                recent_context.append(stripped)

    for path, line_no, line in l_path_violations:
        print(f"[L_PATH] {path}:{line_no}: {sanitize_console(line)}")

    for path, line_no, line in drive_root_violations:
        print(f"[DRIVE_ROOT] {path}:{line_no}: {sanitize_console(line)}")

    for path, line_no, line in cuda_violations:
        print(f"[CUDA_MANDATORY] {path}:{line_no}: {sanitize_console(line)}")

    print(
        f"doc_drift_lint summary: files_scanned={len(targets)} "
        f"l_path_violations={len(l_path_violations)} "
        f"drive_root_violations={len(drive_root_violations)} "
        f"cuda_mandatory_violations={len(cuda_violations)}"
    )

    return 1 if (l_path_violations or drive_root_violations or cuda_violations) else 0


if __name__ == "__main__":
    raise SystemExit(main())
