#!/usr/bin/env python3
"""Verify GoodQ documentation authority, links, indexes, and semantic parity."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import unquote


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
AGENT_FILE_INDEX_PATH = Path("docs/reference/indexes/AGENT_FILE_INDEX.md")
CODEBASE_INDEX_PATH = Path("docs/codebase_index/README.md")
INDEX_SCHEMA_VERIFIED = "2026-07-11"

DOC_BADGE_RE = re.compile(r"<!--\s*DOC_BADGE:\s*([^>]*?)\s*-->")
DOC_STATUS_RE = re.compile(r"<!--\s*DOC_STATUS:\s*([^>]*?)\s*-->")
QDRANT_CONFIG_RE = re.compile(r"^\s*qdrant_storage:\s*([^#\r\n]+)", re.MULTILINE)
QDRANT_DOC_RE = re.compile(r"\$\{GOODQ_DATA_ROOT\}[/\\][^\s`<>]*qdrant_storage")
EPOCH_RE = re.compile(r"epoch_\d{4}_\d{2}_\d{2}_[A-Za-z0-9_]+")

EXCLUDED_INDEX_PREFIXES = (
    "archive/",
    "docs/archive/",
    "vendor/",
)
ALLOWED_DOC_BADGES = {"CANONICAL", "OPERATIONAL", "HISTORICAL", "EXPERIMENTAL"}
ALLOWED_DOC_STATUSES = {
    "ACTIVE",
    "ACTIVE_AGENT_OFFICE_INDEX",
    "ACTIVE_AGENT_WORKFLOW",
    "ACTIVE_BOUNDED_MISSION",
    "ACTIVE_CONTRACT",
    "ACTIVE_CONTRIBUTOR_GUIDE",
    "ACTIVE_GUIDE",
    "ACTIVE_INDEX",
    "ACTIVE_MANIFEST",
    "ACTIVE_NOTE",
    "ACTIVE_OPERATOR_REFERENCE",
    "ACTIVE_POINTER",
    "ACTIVE_RELEASE_REFERENCE",
    "ACTIVE_ROADMAP",
    "ACTIVE_RUNBOOK",
    "ACTIVE_SUPPORT_GUIDE",
    "AUTHORITATIVE",
    "AUTHORITATIVE_LEGAL_NOTICE",
    "CHECKPOINT_EVIDENCE_COMPLETE",
    "CURATED_AUTHORITY_INDEX",
    "CURRENT_STATE_REDIRECT",
    "DEFERRED",
    "DRAFT_REVIEW",
    "DRAFT_SELECTION",
    "GENERATED_CURRENT_STATE",
    "GENERATED_INDEX",
    "GENERATED_SNAPSHOT",
    "GUIDE",
    "HISTORICAL_NOTE",
    "HISTORICAL_POINTER",
    "HISTORICAL_REFERENCE",
    "INVENTORY",
    "OPERATOR_NOTE",
    "REFERENCE_ONLY",
    "RELEASE_LEDGER",
    "SUPPORTING_EVIDENCE",
    "TIMELESS_AGENT_OVERVIEW",
    "VERIFIED_CHECKLIST",
    "WORKSTATION_INTEGRATION_GUIDE",
}
TERMINAL_ROADMAP_STATUSES = {"VERIFIED", "CLOSED", "COMPLETE", "COMPLETED"}


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    path: str
    detail: str


def _active_markdown(repo_root: Path) -> list[Path]:
    root_docs = [path for path in repo_root.glob("*.md") if path.is_file()]
    docs = [
        path
        for path in (repo_root / "docs").rglob("*.md")
        if path.is_file() and "archive" not in path.relative_to(repo_root).parts
    ] if (repo_root / "docs").is_dir() else []
    return sorted(root_docs + docs)


def _relative(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _header(text: str, lines: int = 40) -> str:
    return "\n".join(text.splitlines()[:lines])


def check_metadata(repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in _active_markdown(repo_root):
        if path.name == "SKILL.md":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        header = _header(text)
        details: list[str] = []
        badges = [value.strip() for value in DOC_BADGE_RE.findall(header)]
        statuses = [value.strip() for value in DOC_STATUS_RE.findall(header)]
        verified_values = re.findall(r"<!--\s*DOC_LAST_VERIFIED:\s*([^>]+?)\s*-->", header)
        for name, values in (
            ("DOC_BADGE", badges),
            ("DOC_STATUS", statuses),
            ("DOC_LAST_VERIFIED", verified_values),
        ):
            if not values:
                details.append(f"missing {name}")
            elif len(values) > 1:
                details.append(f"duplicate {name}")
        for badge in badges:
            if badge not in ALLOWED_DOC_BADGES:
                details.append(f"invalid DOC_BADGE={badge}")
        for status in statuses:
            if status not in ALLOWED_DOC_STATUSES:
                details.append(f"invalid DOC_STATUS={status}")
        for value in verified_values:
            try:
                parsed = date.fromisoformat(value.strip())
                if parsed > date.today():
                    raise ValueError("future date")
            except ValueError:
                details.append(f"invalid DOC_LAST_VERIFIED={value.strip()}")
        if details:
            findings.append(
                Finding("DOC_METADATA", _relative(path, repo_root), ", ".join(details))
            )
    return sorted(findings)


def _link_target(raw: str) -> str | None:
    target = raw.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    elif " " in target:
        target = target.split(None, 1)[0]
    target = unquote(target).split("#", 1)[0].split("?", 1)[0]
    if not target or target.startswith(("#", "/", "//")):
        return None
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
        return None
    return target.replace("/", str(Path("/")).strip("/") or "/")


def _iter_markdown_targets(text: str):
    """Yield balanced Markdown link/image targets outside fenced blocks."""
    in_fence = False
    fence_marker = ""
    for line in text.splitlines():
        stripped = line.lstrip()
        marker = "```" if stripped.startswith("```") else "~~~" if stripped.startswith("~~~") else ""
        if marker:
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = ""
            continue
        if in_fence:
            continue

        cursor = 0
        while True:
            close_label = line.find("](", cursor)
            if close_label < 0:
                break
            start = close_label + 2
            depth = 1
            index = start
            while index < len(line) and depth:
                char = line[index]
                if char == "\\":
                    index += 2
                    continue
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0:
                        yield line[start:index]
                        cursor = index + 1
                        break
                index += 1
            else:
                cursor = start
                continue


def check_links(repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in _active_markdown(repo_root):
        text = path.read_text(encoding="utf-8", errors="replace")
        for raw_target in _iter_markdown_targets(text):
            target = _link_target(raw_target)
            if target is None:
                continue
            resolved = (path.parent / Path(target)).resolve()
            try:
                resolved.relative_to(repo_root.resolve())
            except ValueError:
                findings.append(
                    Finding("BROKEN_LINK", _relative(path, repo_root), raw_target.strip())
                )
                continue
            if not resolved.exists():
                findings.append(
                    Finding("BROKEN_LINK", _relative(path, repo_root), raw_target.strip())
                )
    return sorted(set(findings))


def _is_indexed_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    return bool(normalized) and not normalized.startswith(EXCLUDED_INDEX_PREFIXES)


def _tracked_paths(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [
        item.decode("utf-8", errors="strict")
        for item in result.stdout.split(b"\0")
        if item
    ]


def _component(path: str) -> tuple[str, str]:
    first = path.split("/", 1)[0]
    mapping = {
        ".github": ("Repository automation", "Workflow or repository automation asset."),
        "agents": ("Agent control", "Agent control or contract implementation."),
        "api": ("API", "API or local control-plane implementation."),
        "cli": ("CLI", "Command-line operator surface."),
        "configs": ("Configuration", "Configuration, schema, or runtime profile."),
        "docs": ("Documentation", "Active documentation or governance surface."),
        "lib": ("Core library", "Core memory, control, or persistence implementation."),
        "scripts": ("Tooling", "Operator, validation, bootstrap, or development utility."),
        "steps": ("Pipeline", "Pipeline processing step or shared step utility."),
        "tests": ("Verification", "Test, fixture, or verification asset."),
        "ui": ("User interface", "User-interface implementation or asset."),
        "wsl2_audio": ("WSL audio", "WSL audio runtime, bootstrap, or verification asset."),
    }
    return mapping.get(first, ("Repository root", "Root-level project or runtime surface."))


def render_agent_file_index(tracked_paths: list[str]) -> str:
    active_paths = sorted(
        {path.replace("\\", "/") for path in tracked_paths if _is_indexed_path(path)}
    )
    lines = [
        "<!-- DOC_BADGE: OPERATIONAL -->",
        "<!-- DOC_STATUS: GENERATED_INDEX -->",
        f"<!-- DOC_LAST_VERIFIED: {INDEX_SCHEMA_VERIFIED} -->",
        "<!-- DOC_GENERATOR: scripts/docs/doc_authority_lint.py render-index -->",
        "",
        "# Active Repository File Index",
        "",
        "This operational index is generated from `git ls-files`. It is a discovery",
        "surface, not runtime or architecture authority. The explicit active scope",
        "excludes `archive/`, `docs/archive/`, and `vendor/`.",
        "",
        "Regenerate with:",
        "",
        "```powershell",
        "conda run --no-capture-output -n goodq_core python scripts/docs/doc_authority_lint.py render-index",
        "```",
        "",
        f"Indexed active tracked paths: **{len(active_paths)}**",
        "",
        "| File Path | Component | Purpose |",
        "|---|---|---|",
    ]
    for path in active_paths:
        component, purpose = _component(path)
        lines.append(f"| `/{path}` | {component} | {purpose} |")
    return "\n".join(lines) + "\n"


def check_agent_file_index(
    repo_root: Path,
    *,
    tracked_paths: list[str] | None = None,
) -> list[Finding]:
    path = repo_root / AGENT_FILE_INDEX_PATH
    expected = render_agent_file_index(
        tracked_paths if tracked_paths is not None else _tracked_paths(repo_root)
    )
    if not path.is_file() or path.read_text(encoding="utf-8") != expected:
        return [
            Finding(
                "INDEX_DRIFT",
                AGENT_FILE_INDEX_PATH.as_posix(),
                "run doc_authority_lint.py render-index",
            )
        ]
    return []


def _is_codebase_python(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    if not normalized.endswith(".py"):
        return False
    return not normalized.startswith(("archive/", "docs/", "tests/", "vendor/"))


def render_codebase_index(tracked_paths: list[str]) -> str:
    python_paths = sorted(
        {path.replace("\\", "/") for path in tracked_paths if _is_codebase_python(path)}
    )
    lines = [
        "<!-- DOC_BADGE: OPERATIONAL -->",
        "<!-- DOC_STATUS: GENERATED_INDEX -->",
        f"<!-- DOC_LAST_VERIFIED: {INDEX_SCHEMA_VERIFIED} -->",
        "<!-- DOC_GENERATOR: scripts/docs/doc_authority_lint.py render-index -->",
        "",
        "# Active Python Codebase Index",
        "",
        "This operational discovery index is generated from tracked Python files.",
        "It excludes `archive/`, `docs/`, `tests/`, and `vendor/`; tests and docs",
        "have their own discovery surfaces. It does not define runtime authority.",
        "",
        "Regenerate with:",
        "",
        "```powershell",
        "conda run --no-capture-output -n goodq_core python scripts/docs/doc_authority_lint.py render-index",
        "```",
        "",
        f"Indexed active Python paths: **{len(python_paths)}**",
        "",
    ]
    groups: dict[str, list[str]] = {}
    for path in python_paths:
        group = path.split("/", 1)[0] if "/" in path else "Repository root"
        groups.setdefault(group, []).append(path)
    for group in sorted(groups):
        lines.extend((f"## {group}", ""))
        lines.extend(f"- `{path}`" for path in groups[group])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def check_codebase_index(
    repo_root: Path,
    *,
    tracked_paths: list[str] | None = None,
) -> list[Finding]:
    path = repo_root / CODEBASE_INDEX_PATH
    expected = render_codebase_index(
        tracked_paths if tracked_paths is not None else _tracked_paths(repo_root)
    )
    if not path.is_file() or path.read_text(encoding="utf-8") != expected:
        return [
            Finding(
                "INDEX_DRIFT",
                CODEBASE_INDEX_PATH.as_posix(),
                "run doc_authority_lint.py render-index",
            )
        ]
    return []


def check_mission_contract(repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    plan_path = repo_root / "PLAN.md"
    plan = plan_path.read_text(encoding="utf-8", errors="replace") if plan_path.is_file() else ""
    if "PLANS.md" in plan:
        findings.append(Finding("PLAN_NAME_DRIFT", "PLAN.md", "references nonexistent PLANS.md"))

    project_path = repo_root / "PROJECT.md"
    project = project_path.read_text(encoding="utf-8", errors="replace") if project_path.is_file() else ""
    header = _header(project)
    roadmap_ids = re.findall(r"\bR-\d+\b", project)
    roadmap_path = repo_root / "docs" / "releases" / "ROADMAP.md"
    roadmap = roadmap_path.read_text(encoding="utf-8", errors="replace") if roadmap_path.is_file() else ""
    mission_is_open = False
    if len(roadmap_ids) == 1:
        roadmap_id = roadmap_ids[0]
        section_match = re.search(
            rf"^###\s+{re.escape(roadmap_id)}\b.*?(?=^###\s+R-\d+\b|\Z)",
            roadmap,
            flags=re.MULTILINE | re.DOTALL,
        )
        if section_match:
            status_match = re.search(r"^- Status:\s*([^\r\n]+)", section_match.group(0), re.MULTILINE)
            if status_match:
                status = status_match.group(1).strip().split()[0].rstrip("—:-").upper()
                mission_is_open = status not in TERMINAL_ROADMAP_STATUSES
    if not (
        "# Active bounded mission" in project
        and len(roadmap_ids) == 1
        and f"Roadmap item: {roadmap_ids[0]}" in project
        and mission_is_open
        and "DOC_BADGE: OPERATIONAL" in header
        and "DOC_STATUS: ACTIVE_BOUNDED_MISSION" in header
    ):
        findings.append(
            Finding(
                "PROJECT_MISSION_DRIFT",
                "PROJECT.md",
                "must describe one active ROADMAP item, not completed work",
            )
        )
    return sorted(findings)


def _authoritative_epoch(state: dict) -> str:
    authority = state.get("authority")
    if isinstance(authority, dict) and isinstance(authority.get("epoch_id"), str):
        return authority["epoch_id"]
    legacy = state.get("authoritative_epoch")
    if isinstance(legacy, dict) and isinstance(legacy.get("epoch_id"), str):
        return legacy["epoch_id"]
    if isinstance(legacy, str):
        return legacy
    raise ValueError("current_state.json does not expose an authoritative epoch")


def check_epoch_parity(repo_root: Path) -> list[Finding]:
    state_path = repo_root / "docs" / "agent" / "current_state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        epoch = _authoritative_epoch(state)
    except Exception as exc:
        return [Finding("EPOCH_DRIFT", "docs/agent/current_state.json", str(exc))]

    findings: list[Finding] = []
    for relative in (
        "docs/agent/CURRENT_STATE.md",
        "docs/GOODQ_RAG_CONTEXT_PACK.md",
    ):
        path = repo_root / relative
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        if epoch not in text:
            findings.append(Finding("EPOCH_DRIFT", relative, f"missing {epoch}"))

    status_relative = "docs/goodq4all_agent_status.md"
    status_path = repo_root / status_relative
    if status_path.is_file():
        text = status_path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if "active api" not in line.lower():
                continue
            for candidate in EPOCH_RE.findall(line):
                if candidate != epoch:
                    findings.append(
                        Finding("EPOCH_DRIFT", status_relative, f"stale active API epoch {candidate}")
                    )
    return sorted(set(findings))


def _normalize_storage_path(value: str) -> str:
    return value.strip().strip("`'\"").replace("\\", "/").rstrip("/")


def check_qdrant_storage_parity(repo_root: Path) -> list[Finding]:
    config_path = repo_root / "configs" / "config.yaml"
    config_text = config_path.read_text(encoding="utf-8", errors="replace") if config_path.is_file() else ""
    config_match = QDRANT_CONFIG_RE.search(config_text)
    if not config_match:
        return [Finding("QDRANT_STORAGE_DRIFT", "configs/config.yaml", "qdrant_storage not found")]
    configured = _normalize_storage_path(config_match.group(1))

    claims: dict[str, list[str]] = {}
    for relative in (
        "docs/architecture/MEMORY_STORAGE.md",
        "docs/architecture/ARCHITECTURE_REFERENCE.md",
    ):
        path = repo_root / relative
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        claims[relative] = sorted({_normalize_storage_path(item) for item in QDRANT_DOC_RE.findall(text)})
    mismatches = {
        relative: values
        for relative, values in claims.items()
        if values != [configured]
    }
    if mismatches:
        detail = f"config={configured}; docs={mismatches}"
        return [Finding("QDRANT_STORAGE_DRIFT", "configs/config.yaml", detail)]
    return []


def check_current_state_projection(repo_root: Path) -> list[Finding]:
    try:
        from scripts.docs import build_current_state

        json_path = repo_root / "docs" / "agent" / "current_state.json"
        projected = json.loads(json_path.read_text(encoding="utf-8"))
        evidence_relative = projected["generated_from"]
        evidence_candidate = Path(evidence_relative)
        if evidence_candidate.is_absolute() or ".." in evidence_candidate.parts:
            raise ValueError("generated_from must stay under docs/diagnostics/evidence")
        evidence_path = (repo_root / evidence_candidate).resolve()
        evidence_root = (repo_root / "docs" / "diagnostics" / "evidence").resolve()
        try:
            evidence_path.relative_to(evidence_root)
        except ValueError as exc:
            raise ValueError("generated_from must stay under docs/diagnostics/evidence") from exc
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        drift = build_current_state.verify_projection_files(
            evidence,
            repo_root / "docs" / "agent" / "CURRENT_STATE.md",
            json_path,
            repo_root / "docs" / "GOODQ_RAG_CONTEXT_PACK.md",
            evidence_source=evidence_relative,
        )
    except Exception as exc:
        return [Finding("CURRENT_STATE_DRIFT", "docs/agent/current_state.json", str(exc))]
    return [
        Finding("CURRENT_STATE_DRIFT", Path(path).relative_to(repo_root).as_posix(), "projection differs")
        for path in drift
    ]


@contextmanager
def _exclusive_file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"documentation index lock already exists: {path.name}") from exc
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        yield
    finally:
        os.close(descriptor)
        path.unlink(missing_ok=True)


def _write_temp(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.write-",
        suffix=".tmp",
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return temp_path


def publish_indexes(outputs: dict[Path, str]) -> None:
    """Publish generated indexes as one rollback-protected transaction."""
    ordered = sorted(((path.resolve(), content) for path, content in outputs.items()), key=lambda item: str(item[0]))
    if not ordered or len({path for path, _ in ordered}) != len(ordered):
        raise ValueError("documentation index outputs must be distinct and non-empty")
    common = Path(os.path.commonpath([str(path.parent) for path, _ in ordered]))
    lock_path = common / ".doc-indexes.lock"
    originals = {path: path.read_bytes() if path.is_file() else None for path, _ in ordered}
    temporary: dict[Path, Path] = {}
    with _exclusive_file_lock(lock_path):
        try:
            for path, content in ordered:
                temporary[path] = _write_temp(path, content.encode("utf-8"))
            for path, _ in ordered:
                os.replace(temporary[path], path)
                temporary.pop(path)
        except Exception:
            for path, original in originals.items():
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    restore_temp = _write_temp(path, original)
                    try:
                        os.replace(restore_temp, path)
                    finally:
                        restore_temp.unlink(missing_ok=True)
            raise
        finally:
            for temp_path in temporary.values():
                temp_path.unlink(missing_ok=True)


def collect_findings(repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for checker in (
        check_metadata,
        check_links,
        check_agent_file_index,
        check_codebase_index,
        check_mission_contract,
        check_epoch_parity,
        check_current_state_projection,
        check_qdrant_storage_parity,
    ):
        findings.extend(checker(repo_root))
    return sorted(set(findings))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("verify", help="verify all documentation authority gates")
    subparsers.add_parser("render-index", help="regenerate both active repository indexes")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "render-index":
        tracked_paths = _tracked_paths(REPO_ROOT)
        outputs = {
            REPO_ROOT / AGENT_FILE_INDEX_PATH: render_agent_file_index(tracked_paths),
            REPO_ROOT / CODEBASE_INDEX_PATH: render_codebase_index(tracked_paths),
        }
        publish_indexes(outputs)
        for path in outputs:
            print(f"rendered {path.relative_to(REPO_ROOT).as_posix()}")
        return 0

    findings = collect_findings(REPO_ROOT)
    for finding in findings:
        print(f"[{finding.code}] {finding.path}: {finding.detail}")
    if findings:
        print(f"doc authority verification failed: findings={len(findings)}")
        return 1
    print("doc authority verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
