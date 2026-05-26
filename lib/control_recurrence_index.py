from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = _REPO_ROOT / "reports" / "control_recurrence"
_INDEX_FILENAME = "index.json"
_DRIVE_ROOT_RE = re.compile(r"[A-Za-z]:[\\/][^\s,\"'`<>)]*")


def list_report_index(base_dir: str | Path | None = None) -> Dict[str, Any]:
    """Read the durable recurrence report index without regenerating reports."""

    report_dir = _resolve_report_dir(base_dir)
    index_path = report_dir / _INDEX_FILENAME
    if not index_path.is_file():
        return {"status": "empty", "reports": [], "reason": "index_missing"}

    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "status": "warning",
            "reports": [],
            "reason": "index_malformed",
            "warnings": [f"index_malformed:{type(exc).__name__}"],
        }

    if not isinstance(payload, dict):
        return {
            "status": "warning",
            "reports": [],
            "reason": "index_malformed",
            "warnings": ["index_malformed:root_not_object"],
        }

    payload.setdefault("reports", [])
    payload.setdefault("warnings", [])
    return _sanitize_payload(payload, report_dir)


def latest_report_entry(base_dir: str | Path | None = None) -> Dict[str, Any]:
    index = list_report_index(base_dir=base_dir)
    reports = index.get("reports") if isinstance(index, dict) else []
    if not reports:
        return {
            "status": "empty",
            "reports": [],
            "reason": index.get("reason", "no_reports") if isinstance(index, dict) else "no_reports",
        }

    report_dir = _resolve_report_dir(base_dir)
    report_entries = [entry for entry in reports if isinstance(entry, dict)]
    if not report_entries:
        return {"status": "empty", "reports": [], "reason": "no_reports"}

    latest = max(report_entries, key=lambda entry: _entry_sort_time(entry, report_dir))
    return {"status": "ok", "report": _sanitize_payload(latest, report_dir)}


def load_report_json(report_id: str, base_dir: str | Path | None = None) -> Tuple[Dict[str, Any], int]:
    report_dir = _resolve_report_dir(base_dir)
    invalid_reason = _validate_report_id(report_id)
    if invalid_reason:
        return _problem("rejected", report_id, invalid_reason), 400

    entry, index_problem, index_status = _lookup_entry(report_id, report_dir)
    if index_problem is not None:
        return index_problem, index_status

    json_path_value = entry.get("json_path") if isinstance(entry, dict) else None
    if not json_path_value:
        return _problem("not_available", report_id, "json_path_missing"), 200

    artifact_path, reason = _resolve_artifact_path(json_path_value, report_dir)
    if artifact_path is None:
        return _problem("rejected", report_id, reason or "path_rejected"), 400
    if not artifact_path.is_file():
        return _problem("not_available", report_id, "json_artifact_missing"), 200

    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "status": "warning",
            "report_id": report_id,
            "reason": "json_artifact_malformed",
            "warnings": [f"json_artifact_malformed:{type(exc).__name__}"],
        }, 200

    if not isinstance(payload, dict):
        return {
            "status": "warning",
            "report_id": report_id,
            "reason": "json_artifact_malformed",
            "warnings": ["json_artifact_malformed:root_not_object"],
        }, 200

    return _sanitize_payload(payload, report_dir), 200


def load_report_markdown(report_id: str, base_dir: str | Path | None = None) -> Tuple[str | Dict[str, Any], int]:
    report_dir = _resolve_report_dir(base_dir)
    invalid_reason = _validate_report_id(report_id)
    if invalid_reason:
        return _problem("rejected", report_id, invalid_reason), 400

    entry, index_problem, index_status = _lookup_entry(report_id, report_dir)
    if index_problem is not None:
        return index_problem, index_status

    markdown_path_value = entry.get("markdown_path") if isinstance(entry, dict) else None
    if not markdown_path_value:
        return _problem("not_available", report_id, "markdown_path_missing"), 200

    artifact_path, reason = _resolve_artifact_path(markdown_path_value, report_dir)
    if artifact_path is None:
        return _problem("rejected", report_id, reason or "path_rejected"), 400
    if not artifact_path.is_file():
        return _problem("not_available", report_id, "markdown_artifact_missing"), 200

    try:
        text = artifact_path.read_text(encoding="utf-8")
    except Exception as exc:
        return {
            "status": "warning",
            "report_id": report_id,
            "reason": "markdown_artifact_unreadable",
            "warnings": [f"markdown_artifact_unreadable:{type(exc).__name__}"],
        }, 200

    return _sanitize_text(text, report_dir), 200


def _resolve_report_dir(base_dir: str | Path | None = None) -> Path:
    return Path(base_dir) if base_dir is not None else DEFAULT_REPORT_DIR


def _lookup_entry(
    report_id: str,
    report_dir: Path,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], int]:
    index = list_report_index(base_dir=report_dir)
    if index.get("status") == "empty":
        return None, {"status": "not_found", "report_id": report_id, "reason": "index_missing"}, 404
    if index.get("status") == "warning":
        return None, {
            "status": "warning",
            "report_id": report_id,
            "reason": index.get("reason", "index_unavailable"),
            "warnings": index.get("warnings", []),
        }, 200

    for entry in index.get("reports", []):
        if isinstance(entry, dict) and entry.get("report_id") == report_id:
            return entry, None, 200
    return None, {"status": "not_found", "report_id": report_id, "reason": "report_not_indexed"}, 404


def _validate_report_id(report_id: str) -> Optional[str]:
    if not report_id:
        return "report_id_missing"
    if ".." in report_id or "/" in report_id or "\\" in report_id or ":" in report_id:
        return "report_id_path_traversal_rejected"
    return None


def _resolve_artifact_path(path_value: Any, report_dir: Path) -> Tuple[Optional[Path], Optional[str]]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None, "artifact_path_missing"
    if _looks_like_absolute_path(path_value):
        return None, "artifact_path_absolute_rejected"

    raw = Path(path_value)
    if any(part == ".." for part in raw.parts):
        return None, "artifact_path_traversal_rejected"

    base = report_dir.resolve()
    candidate = (base / raw).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None, "artifact_path_traversal_rejected"
    return candidate, None


def _entry_sort_time(entry: Dict[str, Any], report_dir: Path) -> datetime:
    created = entry.get("created_or_updated_at")
    if isinstance(created, str) and created.strip():
        parsed = _parse_datetime(created)
        if parsed is not None:
            return parsed

    for key in ("json_path", "markdown_path"):
        artifact_path, _ = _resolve_artifact_path(entry.get(key), report_dir)
        if artifact_path is not None and artifact_path.is_file():
            return datetime.fromtimestamp(artifact_path.stat().st_mtime, tz=timezone.utc)
    return datetime.min.replace(tzinfo=timezone.utc)


def _parse_datetime(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _problem(status: str, report_id: str, reason: str) -> Dict[str, Any]:
    return {"status": status, "report_id": report_id, "reason": reason}


def _sanitize_payload(value: Any, report_dir: Path) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize_payload(item, report_dir) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_payload(item, report_dir) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_payload(item, report_dir) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value, report_dir)
    return value


def _sanitize_text(value: str, report_dir: Path) -> str:
    if _looks_like_absolute_path(value):
        return _portable_path_text(value, report_dir)
    return _DRIVE_ROOT_RE.sub(lambda match: _portable_path_text(match.group(0), report_dir), value)


def _portable_path_text(value: str, report_dir: Path) -> str:
    path = Path(value)
    for base in (report_dir, _REPO_ROOT):
        try:
            return str(path.relative_to(base)).replace("\\", "/")
        except Exception:
            continue
    return "external/" + "/".join(part for part in path.parts[1:] if part)


def _looks_like_absolute_path(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:[\\/]", value)) or value.startswith("\\\\")
