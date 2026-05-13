#!/usr/bin/env python3
"""Fail when authoritative runtime JSON artifacts are written without atomic_write_json."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]

CRITICAL_DIRS = [
    REPO_ROOT / "cli",
    REPO_ROOT / "steps" / "video",
    REPO_ROOT / "steps" / "common",
]

AUTHORITATIVE_JSON_ARTIFACTS = {
    "scene_manifest.json",
    "temporal_index.json",
    "watchdog_state.json",
    "watchdog_registry.json",
    "progress.json",
    "knowledge_graph.json",
}


class Finding:
    def __init__(self, path: Path, line: int, reason: str):
        self.path = path
        self.line = line
        self.reason = reason

    def __str__(self) -> str:
        rel = self.path.relative_to(REPO_ROOT)
        return f"{rel}:{self.line}: {self.reason}"


def _is_test_or_backup(path: Path) -> bool:
    name = path.name.lower()
    if "backup" in name or name.endswith(".bak"):
        return True
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return False


def _iter_runtime_files() -> Iterable[Path]:
    for root in CRITICAL_DIRS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if _is_test_or_backup(path):
                continue
            yield path


def _str_contains_authoritative(value: str) -> bool:
    return any(token in value for token in AUTHORITATIVE_JSON_ARTIFACTS)


def _expr_contains_authoritative_literal(expr: ast.AST) -> bool:
    for node in ast.walk(expr):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _str_contains_authoritative(node.value):
                return True
    return False


def _expr_is_authoritative(expr: ast.AST, authoritative_vars: Set[str]) -> bool:
    if _expr_contains_authoritative_literal(expr):
        return True
    if isinstance(expr, ast.Name):
        return expr.id in authoritative_vars
    if isinstance(expr, ast.Attribute):
        return _expr_is_authoritative(expr.value, authoritative_vars)
    if isinstance(expr, ast.BinOp):
        return _expr_is_authoritative(expr.left, authoritative_vars) or _expr_is_authoritative(expr.right, authoritative_vars)
    if isinstance(expr, ast.Call):
        if _expr_is_authoritative(expr.func, authoritative_vars):
            return True
        for arg in expr.args:
            if _expr_is_authoritative(arg, authoritative_vars):
                return True
        for kw in expr.keywords:
            if kw.value is not None and _expr_is_authoritative(kw.value, authoritative_vars):
                return True
    return False


def _collect_authoritative_vars(tree: ast.AST) -> Set[str]:
    authoritative_vars: Set[str] = set()
    assign_nodes: List[ast.AST] = [n for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.AnnAssign))]

    changed = True
    while changed:
        changed = False
        for node in assign_nodes:
            if isinstance(node, ast.Assign):
                value = node.value
                targets = node.targets
            else:
                value = node.value
                targets = [node.target]

            if value is None:
                continue
            if not _expr_is_authoritative(value, authoritative_vars):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in authoritative_vars:
                    authoritative_vars.add(target.id)
                    changed = True
    return authoritative_vars


def _with_open_write_mode(call: ast.Call) -> bool:
    if not isinstance(call.func, ast.Name) or call.func.id != "open":
        return False
    mode_value = None
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant) and isinstance(call.args[1].value, str):
        mode_value = call.args[1].value
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            mode_value = kw.value.value
            break
    if mode_value is None:
        mode_value = "r"
    return any(ch in mode_value for ch in ("w", "a", "x"))


def scan_file(path: Path) -> List[Finding]:
    findings: List[Finding] = []
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    authoritative_vars = _collect_authoritative_vars(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            for item in node.items:
                ctx = item.context_expr
                if not isinstance(ctx, ast.Call):
                    continue
                if not _with_open_write_mode(ctx):
                    continue
                if not ctx.args:
                    continue
                path_expr = ctx.args[0]
                if _expr_is_authoritative(path_expr, authoritative_vars):
                    findings.append(
                        Finding(path, node.lineno, "direct open(...,'w') write to authoritative JSON artifact")
                    )
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "write_text":
                if not _expr_is_authoritative(node.func.value, authoritative_vars):
                    continue
                findings.append(Finding(path, node.lineno, "direct write_text(...) to authoritative JSON artifact"))
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "dump":
                if not isinstance(node.func.value, ast.Name) or node.func.value.id != "json":
                    continue
                if len(node.args) >= 2:
                    file_arg = node.args[1]
                    if isinstance(file_arg, ast.Call) and _with_open_write_mode(file_arg):
                        if file_arg.args and _expr_is_authoritative(file_arg.args[0], authoritative_vars):
                            findings.append(
                                Finding(path, node.lineno, "json.dump(open(...,'w')) on authoritative JSON artifact")
                            )

    return findings


def main() -> int:
    findings: List[Finding] = []
    for path in sorted(set(_iter_runtime_files()), key=lambda p: str(p)):
        findings.extend(scan_file(path))

    if findings:
        print("[FAIL] Non-atomic JSON writes detected for authoritative runtime artifacts:")
        for finding in sorted(findings, key=lambda f: (str(f.path), f.line)):
            print(f"  - {finding}")
        return 1

    print("[PASS] Authoritative runtime JSON writes are atomic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
