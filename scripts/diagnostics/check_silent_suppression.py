#!/usr/bin/env python3
"""Fail when critical runtime files contain silent exception suppression patterns."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

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

WARN_SCAN_FILES = sorted(
    {
        *CRITICAL_FILES,
        REPO_ROOT / "steps" / "tts" / "step.py",
        REPO_ROOT / "steps" / "common" / "step_logger.py",
        REPO_ROOT / "steps" / "common" / "lexicon.py",
        REPO_ROOT / "steps" / "audio_transcribe" / "step.py",
        REPO_ROOT / "steps" / "audio_embed_clap" / "step.py",
        REPO_ROOT / "steps" / "text_embed" / "step.py",
        REPO_ROOT / "steps" / "image_embed_dino" / "step.py",
    },
    key=lambda p: str(p),
)

LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}
NUMERIC_CAST_FUNCS = {"float", "int"}
BACKEND_FALLBACK_HINTS = {
    "upsert",
    "add_with_ids",
    "add",
    "write_index",
    "read_index",
    "emit_memory_commit_event",
    "emit_memory_commit_events",
    "connect",
    "execute",
    "close",
}


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


def _contains_print_call(stmt: ast.stmt) -> bool:
    nodes: Iterable[ast.AST] = ast.walk(stmt)
    for node in nodes:
        if isinstance(node, ast.Call):
            name = _callee_name(node)
            if name == "print":
                return True
    return False


def _contains_logging_call(stmt: ast.stmt) -> bool:
    nodes: Iterable[ast.AST] = ast.walk(stmt)
    for node in nodes:
        if isinstance(node, ast.Call):
            name = _callee_name(node)
            if name in LOG_METHODS:
                return True
    return False


def _try_has_numeric_cast(try_node: ast.Try) -> bool:
    for stmt in try_node.body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                name = _callee_name(node)
                if name in NUMERIC_CAST_FUNCS:
                    return True
    return False


def _try_has_backend_hint(try_node: ast.Try) -> bool:
    for stmt in try_node.body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                name = _callee_name(node)
                if name in BACKEND_FALLBACK_HINTS:
                    return True
    return False


def _handler_has_fallback_action(handler: ast.ExceptHandler) -> bool:
    for stmt in handler.body:
        if isinstance(stmt, (ast.Pass, ast.Return, ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Break, ast.Continue)):
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


def scan_file(path: Path, *, hard_enforced: bool) -> Tuple[List[Finding], List[Finding]]:
    hard_findings: List[Finding] = []
    warn_findings: List[Finding] = []
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if hard_enforced:
                has_print = any(_contains_print_call(stmt) for stmt in handler.body)
                if has_print:
                    hard_findings.append(Finding(path, handler.lineno, "print(...) used inside except block"))

            if not _is_broad_handler(handler):
                continue

            if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                reason = "broad except silently passes"
                hard_findings.append(Finding(path, handler.lineno, reason))
                continue

            has_logging = any(_contains_logging_call(stmt) for stmt in handler.body)
            fallback_returns = [stmt for stmt in handler.body if _is_empty_fallback_return(stmt)]
            if fallback_returns and not has_logging:
                reason = "broad except returns fallback without logging"
                hard_findings.append(Finding(path, handler.lineno, reason))

            if not has_logging and _handler_has_fallback_action(handler):
                if _try_has_numeric_cast(node):
                    warn_findings.append(
                        Finding(path, handler.lineno, "numeric coercion fallback lacks logging context")
                    )
                if _try_has_backend_hint(node):
                    warn_findings.append(
                        Finding(path, handler.lineno, "backend fallback lacks logging context")
                    )

    return hard_findings, warn_findings


def main() -> int:
    hard_findings: List[Finding] = []
    warn_findings: List[Finding] = []

    for path in CRITICAL_FILES:
        if not path.exists():
            continue
        hard, warn = scan_file(path, hard_enforced=True)
        hard_findings.extend(hard)
        warn_findings.extend(warn)

    for path in WARN_SCAN_FILES:
        if path in CRITICAL_FILES:
            continue
        if not path.exists():
            continue
        _, warn = scan_file(path, hard_enforced=False)
        warn_findings.extend(warn)

    if hard_findings:
        print("[FAIL] Silent suppression patterns detected in critical runtime paths:")
        for finding in sorted(hard_findings, key=lambda f: (str(f.path), f.line)):
            print(f"  - {finding}")
        return 1

    print("[PASS] No silent suppression patterns detected in critical runtime paths.")
    seen_warn: Set[Tuple[str, int, str]] = set()
    uniq_warn: List[Finding] = []
    for finding in sorted(warn_findings, key=lambda f: (str(f.path), f.line, f.reason)):
        key = (str(finding.path), finding.line, finding.reason)
        if key in seen_warn:
            continue
        seen_warn.add(key)
        uniq_warn.append(finding)
    if uniq_warn:
        print("[WARN] Potential fallback handlers lacking logs (review recommended):")
        for finding in uniq_warn:
            print(f"  - {finding}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
