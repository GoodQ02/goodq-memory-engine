from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


_DRIVE_ROOT_RE = re.compile(r"\b[A-Za-z]:[\\/]")
_WSL_ROOT_RE = re.compile(r"\\\\" + r"wsl" + r"\$", re.IGNORECASE)


def audit_control_recurrence_path_hygiene(
    *,
    durable_artifacts: Mapping[str, str | Path],
    operational_outputs: Optional[Mapping[str, str | Path]] = None,
    audit_pattern_text: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Classify path leaks in report artifacts separately from log chatter."""

    artifact_hits = _scan_named_texts(durable_artifacts)
    chatter_hits = _scan_named_texts(operational_outputs or {})
    ignored_patterns = [
        pattern for pattern in (audit_pattern_text or []) if _contains_local_path_pattern(str(pattern))
    ]
    return {
        "status": "fail" if artifact_hits else "pass",
        "report_artifact_leakage": artifact_hits,
        "operational_output_path_chatter": chatter_hits,
        "pattern_self_hits_ignored": len(ignored_patterns),
        "durable_artifacts_scanned": sorted(str(name) for name in durable_artifacts),
        "operational_outputs_scanned": sorted(str(name) for name in (operational_outputs or {})),
    }


def _scan_named_texts(named_values: Mapping[str, str | Path]) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    for name, value in named_values.items():
        text = _read_text_or_value(value)
        for pattern_name, pattern in (("drive_root", _DRIVE_ROOT_RE), ("wsl_root", _WSL_ROOT_RE)):
            for match in pattern.finditer(text):
                hits.append(
                    {
                        "source": str(name),
                        "pattern": pattern_name,
                        "offset": match.start(),
                    }
                )
    return hits


def _read_text_or_value(value: str | Path) -> str:
    if isinstance(value, Path):
        try:
            return value.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return f"unreadable_path: {exc}"
    return str(value)


def _contains_local_path_pattern(text: str) -> bool:
    return bool(_DRIVE_ROOT_RE.search(text) or _WSL_ROOT_RE.search(text))
