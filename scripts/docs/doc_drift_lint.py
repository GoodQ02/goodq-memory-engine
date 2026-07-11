#!/usr/bin/env python3
"""Lint documentation drift against Bootstrap Contract semantics.

Checks:
1. Hardcoded L:/ paths are not allowed outside docs/archive/.
2. Hardcoded drive-root paths (e.g., C:/, D:\\) are not allowed outside docs/archive/.
3. CUDA/NVIDIA mandatory wording is not allowed outside docs/guides/gpu/ and docs/archive/.
4. Archive docs with historical fixed-drive literals must carry the standard non-canonical warning banner.
5. Active docs must not contain suspicious control/replacement characters.
6. Generated snapshot docs must not claim canonical/authoritative status.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

L_PATH_PATTERN = re.compile(r"\bL:(?:/|\\)")
DRIVE_ROOT_PATTERN = re.compile(r"\b[A-Za-z]:[\\/]")
GHOST_PATH_PATTERN = re.compile(r"file:///|L:/GOODCUBE|L:\\GOODCUBE|C:/Users|C:\\Users|/GOODCUBE/", re.IGNORECASE)
LEGACY_HINT_PATTERN = re.compile(r"\blegacy\b", re.IGNORECASE)
ARCHIVE_WARNING_PATTERN = re.compile(r"ARCHIVE / NON-CANONICAL / DO NOT COPY PATHS")
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]")
REPLACEMENT_CHAR_PATTERN = re.compile("\uFFFD")
DOC_BADGE_PATTERN = re.compile(r"<!--\s*DOC_BADGE:\s*([A-Z_]+)\s*-->")
DOC_STATUS_PATTERN = re.compile(r"<!--\s*DOC_STATUS:\s*([A-Z_]+)\s*-->")
SNAPSHOT_HEADER_PATTERN = re.compile(
    r"(generated\s*:|generated.+snapshot|snapshot.+generated|generated_snapshot)",
    re.IGNORECASE,
)

ALLOWED_LEGACY_DOCS = [
    "docs/technical/LEGACY_PATHS_DEPRECATED.md",
    "docs/architecture/DOCUMENTATION_REORGANIZATION_PLAN.md",
    "docs/diagnostics/ENV_DISCOVERY_REPORT.md",
    "docs/diagnostics/HOST_COMPAT_DISCOVERY_REPORT.md",
    "docs/diagnostics/HOST_COMPAT_PATCH_NOTES.md",
    "docs/diagnostics/LAUNCHER_PORTABILITY_DISCOVERY.md",
    "docs/diagnostics/LAUNCHER_PORTABILITY_PATCH_NOTES.md",
    "docs/technical/PIPELINE_RESTORATION_BACKLOG.md",
    "docs/codebase_index/README.md",
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
    root_docs = sorted(
        path
        for path in repo_root.iterdir()
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}
    )
    return docs + root_docs


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
    ghost_path_violations: list[tuple[Path, int, str]] = []
    cuda_violations: list[tuple[Path, int, str]] = []
    archive_banner_violations: list[tuple[Path, str]] = []
    corrupt_char_violations: list[tuple[Path, int, str]] = []
    snapshot_authority_violations: list[tuple[Path, str]] = []
    archive_literal_doc_count = 0
    archive_literal_line_count = 0

    for file_path in targets:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            print(f"[ERROR] unable to read {file_path}: {exc}", file=sys.stderr)
            return 2

        in_docs_tree = is_under(file_path, repo_root / "docs")
        in_archive = is_under(file_path, archive_root)
        in_gpu_guide = is_under(file_path, gpu_guides_root)
        enforce_contract_checks = in_docs_tree or file_path.name.upper().startswith("README")
        relative_path = file_path.relative_to(repo_root).as_posix()
        in_allowed_legacy_doc = relative_path in allowed_legacy_docs
        has_archive_warning = bool(ARCHIVE_WARNING_PATTERN.search(text))
        header_preview = "\n".join(text.splitlines()[:25])
        badge_match = DOC_BADGE_PATTERN.search(header_preview)
        status_match = DOC_STATUS_PATTERN.search(header_preview)
        doc_badge = badge_match.group(1) if badge_match else ""
        doc_status = status_match.group(1) if status_match else ""
        is_generated_snapshot_doc = doc_status == "GENERATED_SNAPSHOT" or bool(
            SNAPSHOT_HEADER_PATTERN.search(header_preview)
        )
        claims_canonical_authority = doc_badge == "CANONICAL" or doc_status == "AUTHORITATIVE"

        if not in_archive and is_generated_snapshot_doc and claims_canonical_authority:
            snapshot_authority_violations.append(
                (
                    file_path,
                    f"generated snapshot metadata/body conflicts with DOC_BADGE={doc_badge or 'unset'} "
                    f"DOC_STATUS={doc_status or 'unset'}",
                )
            )

        in_fenced_block = False
        in_legacy_fenced_block = False
        recent_context: list[str] = []
        archive_literal_found = False

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

            skip_path_checks = (
                (not enforce_contract_checks)
                or in_archive
                or in_allowed_legacy_doc
                or (in_fenced_block and in_legacy_fenced_block)
            )
            has_l_path = bool(L_PATH_PATTERN.search(line))
            has_drive_root = bool(DRIVE_ROOT_PATTERN.search(line))
            has_ghost_path = bool(GHOST_PATH_PATTERN.search(line))
            has_control_char = bool(CONTROL_CHAR_PATTERN.search(line))
            has_replacement_char = bool(REPLACEMENT_CHAR_PATTERN.search(line))

            if in_archive and (has_l_path or has_drive_root):
                archive_literal_found = True
                archive_literal_line_count += 1

            if not in_archive and (has_control_char or has_replacement_char):
                corrupt_char_violations.append((file_path, line_no, stripped or repr(line)))

            if not skip_path_checks and has_l_path:
                l_path_violations.append((file_path, line_no, stripped))

            if not skip_path_checks and has_drive_root:
                drive_root_violations.append((file_path, line_no, stripped))

            if not skip_path_checks and has_ghost_path:
                ghost_path_violations.append((file_path, line_no, stripped))

            if (not enforce_contract_checks) or in_archive or in_gpu_guide:
                if stripped:
                    recent_context.append(stripped)
                continue

            for pattern in CUDA_MANDATORY_PATTERNS:
                if pattern.search(line):
                    cuda_violations.append((file_path, line_no, stripped))
                    break

            if stripped:
                recent_context.append(stripped)

        if in_archive and archive_literal_found:
            archive_literal_doc_count += 1
            if not has_archive_warning:
                archive_banner_violations.append(
                    (file_path, "archive doc contains historical fixed-drive literals without the standard warning banner")
                )

    for path, line_no, line in l_path_violations:
        print(f"[L_PATH] {path}:{line_no}: {sanitize_console(line)}")

    for path, line_no, line in drive_root_violations:
        print(f"[DRIVE_ROOT] {path}:{line_no}: {sanitize_console(line)}")

    for path, line_no, line in ghost_path_violations:
        print(f"[GHOST_PATH] {path}:{line_no}: {sanitize_console(line)}")

    for path, line_no, line in cuda_violations:
        print(f"[CUDA_MANDATORY] {path}:{line_no}: {sanitize_console(line)}")

    for path, detail in archive_banner_violations:
        print(f"[ARCHIVE_BANNER] {path}: {sanitize_console(detail)}")

    for path, line_no, line in corrupt_char_violations:
        print(f"[CORRUPT_CHARS] {path}:{line_no}: {sanitize_console(line)}")

    for path, detail in snapshot_authority_violations:
        print(f"[SNAPSHOT_AUTHORITY] {path}: {sanitize_console(detail)}")

    print(
        f"doc_drift_lint summary: files_scanned={len(targets)} "
        f"active_l_path_violations={len(l_path_violations)} "
        f"active_drive_root_violations={len(drive_root_violations)} "
        f"ghost_path_violations={len(ghost_path_violations)} "
        f"cuda_mandatory_violations={len(cuda_violations)} "
        f"archive_literal_docs={archive_literal_doc_count} "
        f"archive_literal_lines={archive_literal_line_count} "
        f"archive_banner_violations={len(archive_banner_violations)} "
        f"corrupt_char_violations={len(corrupt_char_violations)} "
        f"snapshot_authority_violations={len(snapshot_authority_violations)}"
    )

    return 1 if (
        l_path_violations
        or drive_root_violations
        or ghost_path_violations
        or cuda_violations
        or archive_banner_violations
        or corrupt_char_violations
        or snapshot_authority_violations
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
