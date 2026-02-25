#!/usr/bin/env python3
"""Fail when critical runtime files contain silent exception suppression patterns."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]

CRITICAL_FILES = [
    REPO_ROOT / "cli" / "run_ingestion.py",
    REPO_ROOT / "cli" / "watchdog.py",
    REPO_ROOT / "steps" / "common" / "memory.py",
    REPO_ROOT / "steps" / "common" / "memory_stores.py",
    REPO_ROOT / "steps" / "common" / "qdrant_client.py",
    REPO_ROOT / "steps" / "video" / "cross_modal_harmonizer.py",
    REPO_ROOT / "steps" / "video" / "scene_visual_embeddings.py",
    REPO_ROOT / "wsl2_audio" / "audio_bridge.py",
]

LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}


class Finding:
    def __init__(self, path: Path, line: int, reason: str):
        self.path = path
        self.line = line
        self.reason = reason

    def __str__(self) -> str:
        rel = self.path.relative_to(REPO_ROOT)
        return f"{rel}:{self.line}: {self.reason}"


def _is_empty_fallback_return(stmt: ast.stmt) -> bool:
    if not isinstance(stmt, ast.Return):
        return False
    value = stmt.value
    if value is None:
        return True
    if isinstance(value, ast.Constant):
        return value.value in {False, None, "", 0}
    if isinstance(value, ast.List):
        return len(value.elts) == 0
    if isinstance(value, ast.Dict):
        return len(value.keys) == 0
    if isinstance(value, ast.Tuple):
        return len(value.elts) == 0
    return False


def _callee_name(call: ast.Call) -> Optional[str]:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _contains_logging_call(stmt: ast.stmt) -> bool:
    nodes: Iterable[ast.AST] = ast.walk(stmt)
    for node in nodes:
        if isinstance(node, ast.Call):
            name = _callee_name(node)
            if name in LOG_METHODS:
                return True
    return False


def _is_broad_handler(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    if isinstance(handler.type, ast.Name) and handler.type.id == "Exception":
        return True
    if isinstance(handler.type, ast.Tuple):
        for elt in handler.type.elts:
            if isinstance(elt, ast.Name) and elt.id == "Exception":
                return True
    return False


def scan_file(path: Path) -> List[Finding]:
    findings: List[Finding] = []
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if not _is_broad_handler(handler):
                continue

            if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                reason = "broad except silently passes"
                findings.append(Finding(path, handler.lineno, reason))
                continue

            has_logging = any(_contains_logging_call(stmt) for stmt in handler.body)
            fallback_returns = [stmt for stmt in handler.body if _is_empty_fallback_return(stmt)]
            if fallback_returns and not has_logging:
                reason = "broad except returns fallback without logging"
                findings.append(Finding(path, handler.lineno, reason))

    return findings


def main() -> int:
    all_findings: List[Finding] = []
    for path in CRITICAL_FILES:
        if not path.exists():
            continue
        all_findings.extend(scan_file(path))

    if all_findings:
        print("[FAIL] Silent suppression patterns detected in critical runtime paths:")
        for finding in sorted(all_findings, key=lambda f: (str(f.path), f.line)):
            print(f"  - {finding}")
        return 1

    print("[PASS] No silent suppression patterns detected in critical runtime paths.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
