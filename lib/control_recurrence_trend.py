from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from lib import control_recurrence_index


_CATEGORIES = ("informational", "watch", "actionable", "blocking")
_RECOVERY_KEYS = ("recovered", "unrecovered", "skipped", "unknown")

_SAFETY_BOUNDARY = {
    "source": "existing recurrence index + referenced JSON only",
    "raw_run_roots_scanned": "not_attempted",
    "step_logs_read": "not_attempted",
    "reports_generated": "not_triggered",
    "ingestion": "not_triggered",
    "control_agent": "not_imported_or_activated",
    "auto_healing": "not_enabled",
    "config_mutation": "not_attempted",
    "source_artifact_mutation": "not_attempted",
    "index_mutation": "not_attempted",
    "llm_usage": "not_used",
}


def build_control_recurrence_trend(base_dir: str | None = None) -> Dict[str, Any]:
    """Build a derived read-only trend over indexed recurrence JSON reports."""

    index = control_recurrence_index.list_report_index(base_dir=base_dir)
    raw_entries = index.get("reports") if isinstance(index, dict) else []
    entries = [entry for entry in raw_entries or [] if isinstance(entry, dict)]
    scope_warnings: List[Dict[str, Any]] = []
    loaded_reports: List[Dict[str, Any]] = []
    timeline: List[Dict[str, Any]] = []

    for warning in index.get("warnings", []) if isinstance(index, dict) else []:
        scope_warnings.append({"warning": "index_warning", "detail": str(warning)})

    if index.get("status") == "empty":
        scope_warnings.append({"warning": "index_missing", "reason": index.get("reason", "index_missing")})
    elif index.get("status") == "warning":
        scope_warnings.append({"warning": "index_unavailable", "reason": index.get("reason", "index_warning")})

    for entry in sorted(entries, key=_timeline_sort_key):
        row, report_payload, warnings = _timeline_row_from_entry(entry, base_dir=base_dir)
        timeline.append(row)
        scope_warnings.extend(warnings)
        if report_payload is not None:
            loaded_reports.append({"entry": entry, "timeline": row, "report": report_payload})

    if entries and not loaded_reports:
        scope_warnings.append({"warning": "no_json_backed_reports", "reason": "trend_requires_durable_json"})
    if len(loaded_reports) < 2:
        scope_warnings.append({"warning": "insufficient_report_count", "json_backed_reports": len(loaded_reports)})

    groups = _comparable_groups(loaded_reports, scope_warnings)
    trend = {
        "trend_report": {
            "name": "control_recurrence_trend",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "mode": "read_only_derived_trend",
            "status": _trend_status(index=index, loaded_reports=loaded_reports, warnings=scope_warnings),
            "derived": True,
            "implemented_version": "0.5.0",
            "source_index_status": index.get("status", "ok") if isinstance(index, dict) else "warning",
            "source": "reports/control_recurrence/index.json and referenced durable JSON artifacts only",
        },
        "report_window": _report_window(entries=entries, timeline=timeline, groups=groups, warnings=scope_warnings),
        "report_timeline": timeline,
        "family_trends": _family_trends(groups),
        "category_trends": _category_trends(groups),
        "recovery_trends": _recovery_trends(groups),
        "health_trends": _health_trends(groups),
        "latency_trends": _latency_trends(groups),
        "recommendation_history": _recommendation_history(loaded_reports),
        "scope_warnings": scope_warnings,
        "safety_boundary": dict(_SAFETY_BOUNDARY),
    }
    return trend


def render_text_trend(trend: Dict[str, Any], *, limit: int = 12) -> str:
    meta = trend.get("trend_report") if isinstance(trend, dict) else {}
    window = trend.get("report_window") if isinstance(trend, dict) else {}
    lines = [
        "GoodQ Control Recurrence Trend",
        "================================",
        "Mode: read-only derived trend",
        f"Status: {str(meta.get('status') or 'unknown').upper()}",
        f"Reports indexed: {window.get('total_index_entries', 0)}",
        f"JSON-backed reports: {window.get('json_backed_reports', 0)}",
        f"Comparable groups: {window.get('comparable_scope_groups', 0)}",
        "",
        "Family Trends:",
    ]
    family_rows = trend.get("family_trends") or []
    for row in family_rows[: max(1, int(limit or 12))]:
        lines.append(
            "- {family}: {status} latest={latest} previous={previous} delta={delta}".format(
                family=row.get("error_family", "unknown"),
                status=row.get("trend_status", "unknown"),
                latest=row.get("latest_count", 0),
                previous=row.get("previous_count", 0),
                delta=row.get("delta", 0),
            )
        )
    if not family_rows:
        lines.append("- No comparable family trend rows.")

    latency_rows = trend.get("latency_trends") or []
    if latency_rows:
        lines.append("")
        lines.append("Latency Trends:")
        for row in latency_rows[: max(1, int(limit or 12))]:
            lines.append(
                "- {step}: {status} p95_delta_ms={p95_delta} max_delta_ms={max_delta} timeout_delta={timeout_delta}".format(
                    step=row.get("step_name", "unknown_step"),
                    status=row.get("trend_status", "unknown"),
                    p95_delta=row.get("p95_delta_ms"),
                    max_delta=row.get("max_delta_ms"),
                    timeout_delta=row.get("timeout_boundary_exceedance_delta", 0),
                )
            )

    warnings = trend.get("scope_warnings") or []
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in warnings[: max(1, int(limit or 12))]:
            lines.append(f"- {warning.get('warning', 'unknown')}: {warning.get('report_id') or warning.get('reason') or warning.get('detail') or ''}")

    lines.append("")
    lines.append("Safety Boundary:")
    safety = trend.get("safety_boundary") if isinstance(trend.get("safety_boundary"), dict) else {}
    lines.append(f"- source: {safety.get('source', 'unknown')}")
    lines.append(f"- raw_run_roots_scanned: {safety.get('raw_run_roots_scanned', 'unknown')}")
    lines.append(f"- reports_generated: {safety.get('reports_generated', 'unknown')}")
    lines.append(f"- ingestion: {safety.get('ingestion', 'unknown')}")
    lines.append(f"- control_agent: {safety.get('control_agent', 'unknown')}")
    lines.append(f"- auto_healing: {safety.get('auto_healing', 'unknown')}")
    return "\n".join(lines)


def _timeline_row_from_entry(
    entry: Dict[str, Any],
    *,
    base_dir: str | None,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    report_id = str(entry.get("report_id") or "unknown")
    warnings: List[Dict[str, Any]] = []
    warning_flags: List[str] = []
    json_backed = bool(entry.get("json_path"))
    report_payload: Optional[Dict[str, Any]] = None

    if not json_backed:
        warning_flags.extend(["json_missing", "metadata_only", "limited_trendability"])
        warnings.append({"warning": "json_missing", "report_id": report_id})
        if entry.get("markdown_path"):
            warnings.append({"warning": "markdown_only_entry", "report_id": report_id})
    else:
        loaded, status_code = control_recurrence_index.load_report_json(report_id, base_dir=base_dir)
        if status_code != 200 or loaded.get("status") in {"warning", "not_available", "not_found", "rejected"}:
            reason = str(loaded.get("reason") or f"status_code_{status_code}")
            warning_flags.extend(["json_unavailable", "limited_trendability"])
            warnings.append({"warning": reason, "report_id": report_id})
        else:
            report_payload = loaded

    scope_signature, scope_notes = _derive_scope_signature(entry, report_payload, json_backed=bool(report_payload))
    warning_flags.extend(scope_notes)
    for note in scope_notes:
        warnings.append({"warning": note, "report_id": report_id})

    if report_payload is not None and not _schema_version(report_payload):
        warning_flags.append("missing_schema_version")
        warnings.append({"warning": "missing_schema_version", "report_id": report_id})

    return (
        {
            "report_id": report_id,
            "report_path": entry.get("json_path") or entry.get("markdown_path"),
            "created_or_updated_at": entry.get("created_or_updated_at"),
            "report_type": entry.get("report_type") or _report_type(report_payload),
            "recommendation_status": entry.get("recommendation_status") or _recommendation_status(report_payload),
            "highest_category": entry.get("highest_category") or _highest_category(report_payload),
            "total_signals": _safe_int(entry.get("total_signals")),
            "blocking_signal_count": _safe_int(entry.get("blocking_signal_count")),
            "json_backed": bool(report_payload),
            "artifact_status": entry.get("artifact_status") or ("json_backed" if report_payload else "metadata_only"),
            "scope_signature": scope_signature,
            "warning_flags": _dedupe(warning_flags),
            "latency_summary": _latency_timeline_summary(report_payload),
            "phase6_health_summary": entry.get("phase6_health_summary") or {},
            "qdrant_health_summary": entry.get("qdrant_health_summary") or {},
        },
        report_payload,
        warnings,
    )


def _derive_scope_signature(
    entry: Dict[str, Any],
    report: Optional[Dict[str, Any]],
    *,
    json_backed: bool,
) -> Tuple[Dict[str, Any], List[str]]:
    notes: List[str] = []
    report_type = str(entry.get("report_type") or _report_type(report) or "unknown")
    report_kind = "comparison" if report_type == "comparison" else "single_run"
    schema_version = _schema_version(report)
    videos = _list_from_nested(report, ("scope", "videos"))
    run_roots = _list_from_nested(report, ("scope", "run_roots"))
    runtime_run_ids = _list_from_nested(report, ("scope", "runtime_run_ids"))
    run_id = entry.get("run_id") or _single_run_id(report)
    baseline_run_id = entry.get("baseline_run_id") or _nested(report, ("baseline", "run_id"))
    candidate_run_id = entry.get("candidate_run_id") or _nested(report, ("candidate", "run_id"))

    if report_kind == "comparison":
        scope_values = [str(baseline_run_id or ""), str(candidate_run_id or "")]
        scope_basis = "baseline_candidate"
    elif videos:
        scope_values = videos
        scope_basis = "videos"
    elif run_roots:
        scope_values = run_roots
        scope_basis = "run_roots"
    elif run_id:
        scope_values = [str(run_id)]
        scope_basis = "run_id"
    else:
        scope_values = []
        scope_basis = "missing"
        notes.append("limited_trendability")
        notes.append("missing_scope_data")

    if not schema_version and json_backed:
        notes.append("missing_schema_version")
    if not json_backed:
        notes.append("limited_trendability")

    basis_text = ",".join(sorted(value for value in scope_values if value))
    key = "|".join(
        [
            f"kind={report_kind}",
            f"basis={scope_basis}",
            f"values={basis_text or 'unknown'}",
            f"schema={schema_version or 'unknown'}",
        ]
    )
    return (
        {
            "key": key,
            "derived": True,
            "report_kind": report_kind,
            "scope_basis": scope_basis,
            "values": sorted(scope_values),
            "schema_version": schema_version,
            "json_backed": json_backed,
            "runtime_run_ids": runtime_run_ids,
        },
        _dedupe(notes),
    )


def _comparable_groups(
    loaded_reports: List[Dict[str, Any]],
    scope_warnings: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in loaded_reports:
        key = str(_nested(item, ("timeline", "scope_signature", "key")) or "unknown")
        groups[key].append(item)

    for key, items in groups.items():
        items.sort(key=lambda item: _parse_time(_nested(item, ("timeline", "created_or_updated_at"))))
        if len(items) < 2:
            scope_warnings.append(
                {
                    "warning": "insufficient_comparable_data",
                    "scope_signature": key,
                    "report_count": len(items),
                }
            )
    if len(groups) > 1:
        scope_warnings.append(
            {
                "warning": "incomparable_scope_groups",
                "scope_group_count": len(groups),
                "mode": "timeline_only_between_different_scope_signatures",
            }
        )
    return groups


def _family_trends(groups: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key, items in sorted(groups.items()):
        family_names = sorted({family for item in items for family in _family_counts(item["report"])})
        for family in family_names:
            counts_by_report = {
                item["timeline"]["report_id"]: _family_counts(item["report"]).get(family, 0)
                for item in items
            }
            ordered_counts = list(counts_by_report.values())
            previous = ordered_counts[-2] if len(ordered_counts) >= 2 else 0
            latest = ordered_counts[-1] if ordered_counts else 0
            positive_reports = [
                item["timeline"]["report_id"]
                for item in items
                if _family_counts(item["report"]).get(family, 0) > 0
            ]
            latest_row = _family_row(items[-1]["report"], family)
            rows.append(
                {
                    "error_family": family,
                    "scope_signature": key,
                    "trend_status": _trend_label(previous, latest, comparable=len(items) >= 2),
                    "first_seen_report_id": positive_reports[0] if positive_reports else None,
                    "latest_seen_report_id": positive_reports[-1] if positive_reports else None,
                    "report_count": len(items),
                    "counts_by_report": counts_by_report,
                    "latest_count": latest,
                    "previous_count": previous,
                    "delta": latest - previous,
                    "category": (latest_row or {}).get("category") or _family_category(items, family),
                    "recovery_outcomes": (latest_row or {}).get("recovery_outcomes") or {},
                    "inspection_targets": (latest_row or {}).get("inspection_targets") or [],
                }
            )
    return rows


def _category_trends(groups: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key, items in sorted(groups.items()):
        for category in _CATEGORIES:
            counts_by_report = {
                item["timeline"]["report_id"]: _category_counts(item["report"]).get(category, 0)
                for item in items
            }
            ordered_counts = list(counts_by_report.values())
            previous = ordered_counts[-2] if len(ordered_counts) >= 2 else 0
            latest = ordered_counts[-1] if ordered_counts else 0
            rows.append(
                {
                    "category": category,
                    "scope_signature": key,
                    "trend_status": _trend_label(previous, latest, comparable=len(items) >= 2),
                    "counts_by_report": counts_by_report,
                    "latest_count": latest,
                    "previous_count": previous,
                    "delta": latest - previous,
                    "latest_highest_category": _highest_category(items[-1]["report"]) if items else "none",
                }
            )
    return rows


def _recovery_trends(groups: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key, items in sorted(groups.items()):
        for recovery_key in _RECOVERY_KEYS:
            counts_by_report = {
                item["timeline"]["report_id"]: _recovery_counts(item["report"]).get(recovery_key, 0)
                for item in items
            }
            ordered_counts = list(counts_by_report.values())
            previous = ordered_counts[-2] if len(ordered_counts) >= 2 else 0
            latest = ordered_counts[-1] if ordered_counts else 0
            rows.append(
                {
                    "recovery_key": recovery_key,
                    "scope_signature": key,
                    "trend_status": _trend_label(previous, latest, comparable=len(items) >= 2),
                    "counts_by_report": counts_by_report,
                    "latest_count": latest,
                    "previous_count": previous,
                    "delta": latest - previous,
                }
            )
    return rows


def _health_trends(groups: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key, items in sorted(groups.items()):
        for health_key in ("phase6", "qdrant"):
            counts_by_report = {
                item["timeline"]["report_id"]: _health_count(item["report"], health_key)
                for item in items
            }
            statuses_by_report = {
                item["timeline"]["report_id"]: _health_status(item["report"], health_key)
                for item in items
            }
            ordered_counts = list(counts_by_report.values())
            previous = ordered_counts[-2] if len(ordered_counts) >= 2 else 0
            latest = ordered_counts[-1] if ordered_counts else 0
            rows.append(
                {
                    "health_key": health_key,
                    "scope_signature": key,
                    "trend_status": _trend_label(previous, latest, comparable=len(items) >= 2),
                    "healthy_counts_by_report": counts_by_report,
                    "statuses_by_report": statuses_by_report,
                    "latest_healthy_count": latest,
                    "previous_healthy_count": previous,
                    "delta": latest - previous,
                    "root_cause_inference": "not_attempted",
                }
            )
    return rows


def _latency_trends(groups: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key, items in sorted(groups.items()):
        step_names = sorted({step for item in items for step in _latency_steps(item["report"])})
        for step in step_names:
            counts_by_report: Dict[str, int] = {}
            p50_by_report: Dict[str, Optional[float]] = {}
            p95_by_report: Dict[str, Optional[float]] = {}
            max_by_report: Dict[str, Optional[float]] = {}
            slow_outliers_by_report: Dict[str, int] = {}
            timeout_exceedances_by_report: Dict[str, int] = {}

            for item in items:
                report_id = item["timeline"]["report_id"]
                row = _latency_steps(item["report"]).get(step, {})
                counts_by_report[report_id] = _safe_int(row.get("count"))
                p50_by_report[report_id] = _safe_float(row.get("p50_ms"))
                p95_by_report[report_id] = _safe_float(row.get("p95_ms"))
                max_by_report[report_id] = _safe_float(row.get("max_ms"))
                slow_outliers_by_report[report_id] = _safe_int(row.get("slow_outlier_count"))
                timeout_exceedances_by_report[report_id] = _safe_int(row.get("timeout_boundary_exceedance_count"))

            ordered_counts = list(counts_by_report.values())
            ordered_p50 = list(p50_by_report.values())
            ordered_p95 = list(p95_by_report.values())
            ordered_max = list(max_by_report.values())
            ordered_slow = list(slow_outliers_by_report.values())
            ordered_timeout = list(timeout_exceedances_by_report.values())
            previous_count = ordered_counts[-2] if len(ordered_counts) >= 2 else 0
            latest_count = ordered_counts[-1] if ordered_counts else 0
            previous_p50 = ordered_p50[-2] if len(ordered_p50) >= 2 else None
            latest_p50 = ordered_p50[-1] if ordered_p50 else None
            previous_p95 = ordered_p95[-2] if len(ordered_p95) >= 2 else None
            latest_p95 = ordered_p95[-1] if ordered_p95 else None
            previous_max = ordered_max[-2] if len(ordered_max) >= 2 else None
            latest_max = ordered_max[-1] if ordered_max else None
            previous_slow = ordered_slow[-2] if len(ordered_slow) >= 2 else 0
            latest_slow = ordered_slow[-1] if ordered_slow else 0
            previous_timeout = ordered_timeout[-2] if len(ordered_timeout) >= 2 else 0
            latest_timeout = ordered_timeout[-1] if ordered_timeout else 0

            rows.append(
                {
                    "step_name": step,
                    "scope_signature": key,
                    "trend_status": _latency_trend_label(
                        previous_count=previous_count,
                        latest_count=latest_count,
                        previous_p95=previous_p95,
                        latest_p95=latest_p95,
                        comparable=len(items) >= 2,
                    ),
                    "report_count": len(items),
                    "source": "existing recurrence JSON step_latency_summary",
                    "counts_by_report": counts_by_report,
                    "p50_ms_by_report": p50_by_report,
                    "p95_ms_by_report": p95_by_report,
                    "max_ms_by_report": max_by_report,
                    "slow_outlier_counts_by_report": slow_outliers_by_report,
                    "timeout_boundary_exceedance_counts_by_report": timeout_exceedances_by_report,
                    "latest_count": latest_count,
                    "previous_count": previous_count,
                    "count_delta": latest_count - previous_count,
                    "latest_p50_ms": _round_ms(latest_p50),
                    "previous_p50_ms": _round_ms(previous_p50),
                    "p50_delta_ms": _delta_ms(previous_p50, latest_p50),
                    "latest_p95_ms": _round_ms(latest_p95),
                    "previous_p95_ms": _round_ms(previous_p95),
                    "p95_delta_ms": _delta_ms(previous_p95, latest_p95),
                    "latest_max_ms": _round_ms(latest_max),
                    "previous_max_ms": _round_ms(previous_max),
                    "max_delta_ms": _delta_ms(previous_max, latest_max),
                    "latest_slow_outlier_count": latest_slow,
                    "previous_slow_outlier_count": previous_slow,
                    "slow_outlier_delta": latest_slow - previous_slow,
                    "latest_timeout_boundary_exceedance_count": latest_timeout,
                    "previous_timeout_boundary_exceedance_count": previous_timeout,
                    "timeout_boundary_exceedance_delta": latest_timeout - previous_timeout,
                }
            )

    rows.sort(
        key=lambda row: (
            -abs(float(row.get("p95_delta_ms") or 0.0)),
            -abs(float(row.get("max_delta_ms") or 0.0)),
            str(row.get("step_name")),
        )
    )
    return rows


def _recommendation_history(loaded_reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in sorted(loaded_reports, key=lambda row: _parse_time(_nested(row, ("timeline", "created_or_updated_at")))):
        recommendation = _recommendation(item["report"])
        rows.append(
            {
                "report_id": item["timeline"]["report_id"],
                "created_or_updated_at": item["timeline"].get("created_or_updated_at"),
                "scope_signature": item["timeline"]["scope_signature"],
                "recommendation_status": recommendation.get("status") or "unknown",
                "highest_category": recommendation.get("highest_category") or _highest_category(item["report"]),
                "reasons": list(recommendation.get("reasons") or []),
            }
        )
    return rows


def _report_window(
    *,
    entries: List[Dict[str, Any]],
    timeline: List[Dict[str, Any]],
    groups: Dict[str, List[Dict[str, Any]]],
    warnings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    times = [row.get("created_or_updated_at") for row in timeline if row.get("created_or_updated_at")]
    return {
        "total_index_entries": len(entries),
        "json_backed_reports": sum(1 for row in timeline if row.get("json_backed")),
        "metadata_only_entries": sum(1 for row in timeline if not row.get("json_backed")),
        "malformed_entries": sum(1 for row in timeline if "json_unavailable" in (row.get("warning_flags") or [])),
        "skipped_entries": sum(1 for row in timeline if "metadata_only" in (row.get("warning_flags") or [])),
        "warning_count": len(warnings),
        "first_created_or_updated_at": min(times) if times else None,
        "last_created_or_updated_at": max(times) if times else None,
        "report_ids": [row.get("report_id") for row in timeline],
        "comparable_scope_groups": sum(1 for items in groups.values() if len(items) >= 2),
        "scope_group_count": len(groups),
    }


def _trend_status(index: Dict[str, Any], loaded_reports: List[Dict[str, Any]], warnings: List[Dict[str, Any]]) -> str:
    if index.get("status") == "empty":
        return "empty"
    if not loaded_reports:
        return "warning"
    return "warning" if warnings else "ok"


def _family_counts(report: Dict[str, Any]) -> Dict[str, int]:
    rows = report.get("top_repeated_failure_families")
    if not isinstance(rows, list):
        rows = _nested(report, ("recurrence_classification", "families")) or []
    counts: Dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        family = str(row.get("error_family") or "").strip()
        if family:
            counts[family] = _safe_int(row.get("count"))
    return counts


def _family_row(report: Dict[str, Any], family: str) -> Optional[Dict[str, Any]]:
    for rows in (report.get("top_repeated_failure_families"), _nested(report, ("recurrence_classification", "families"))):
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("error_family") == family:
                return row
    return None


def _family_category(items: List[Dict[str, Any]], family: str) -> str:
    for item in reversed(items):
        row = _family_row(item["report"], family)
        if isinstance(row, dict) and row.get("category"):
            return str(row.get("category"))
    return "unknown"


def _category_counts(report: Dict[str, Any]) -> Dict[str, int]:
    counts = _nested(report, ("recurrence_classification", "signal_counts"))
    if not isinstance(counts, dict):
        counts = _nested(report, ("recurrence_classification", "category_counts"))
    if not isinstance(counts, dict):
        counts = {}
    return {category: _safe_int(counts.get(category)) for category in _CATEGORIES}


def _recovery_counts(report: Dict[str, Any]) -> Dict[str, int]:
    counts = report.get("recovered_vs_unrecovered_failures")
    if not isinstance(counts, dict):
        counts = _nested(report, ("candidate", "recovery_counts"))
    if not isinstance(counts, dict):
        counts = {}
    return {key: _safe_int(counts.get(key)) for key in _RECOVERY_KEYS}


def _health_count(report: Dict[str, Any], health_key: str) -> int:
    health = report.get("phase6_qdrant_truth") if isinstance(report.get("phase6_qdrant_truth"), dict) else {}
    if health_key == "phase6":
        return _safe_int(health.get("episodes_healthy"))
    episodes = health.get("episodes") if isinstance(health.get("episodes"), list) else []
    if episodes:
        return sum(1 for row in episodes if isinstance(row, dict) and row.get("qdrant_ok") is True)
    return _safe_int(_nested(report, ("phase6_qdrant_truth", "episodes_healthy")))


def _health_status(report: Dict[str, Any], health_key: str) -> str:
    health = report.get("phase6_qdrant_truth") if isinstance(report.get("phase6_qdrant_truth"), dict) else {}
    if health_key == "phase6":
        return str(health.get("status") or "unknown")
    episodes = health.get("episodes") if isinstance(health.get("episodes"), list) else []
    if episodes:
        healthy = sum(1 for row in episodes if isinstance(row, dict) and row.get("qdrant_ok") is True)
        return "healthy" if healthy == len(episodes) else "degraded"
    return str(health.get("status") or "unknown")


def _latency_timeline_summary(report: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    latency = report.get("step_latency_summary") if isinstance(report, dict) else {}
    if not isinstance(latency, dict):
        latency = {}
    return {
        "status": str(latency.get("status") or "unavailable"),
        "duration_row_count": _safe_int(latency.get("duration_row_count")),
        "step_count": _safe_int(latency.get("step_count")),
        "slow_outlier_count": _safe_int(latency.get("slow_outlier_count")),
        "timeout_boundary_exceedance_count": _safe_int(latency.get("timeout_boundary_exceedance_count")),
    }


def _latency_steps(report: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    latency = report.get("step_latency_summary") if isinstance(report.get("step_latency_summary"), dict) else {}
    rows = latency.get("steps") if isinstance(latency.get("steps"), list) else []
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        step = str(row.get("step_name") or "").strip()
        if step:
            out[step] = row
    return out


def _latency_trend_label(
    *,
    previous_count: int,
    latest_count: int,
    previous_p95: Optional[float],
    latest_p95: Optional[float],
    comparable: bool,
) -> str:
    if not comparable:
        return "insufficient_comparable_data"
    if previous_count <= 0 and latest_count > 0:
        return "new"
    if previous_count > 0 and latest_count <= 0:
        return "resolved"
    if previous_p95 is None or latest_p95 is None:
        return "insufficient_data"
    if latest_p95 > previous_p95:
        return "increased"
    if latest_p95 < previous_p95:
        return "decreased"
    return "stable"


def _trend_label(previous: int, latest: int, *, comparable: bool) -> str:
    if not comparable:
        return "insufficient_comparable_data"
    if previous == 0 and latest > 0:
        return "new"
    if previous > 0 and latest == 0:
        return "resolved"
    if latest > previous:
        return "increased"
    if latest < previous:
        return "decreased"
    return "stable"


def _timeline_sort_key(entry: Dict[str, Any]) -> datetime:
    return _parse_time(entry.get("created_or_updated_at"))


def _parse_time(value: Any) -> datetime:
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)
    return datetime.min.replace(tzinfo=timezone.utc)


def _report_type(report: Optional[Dict[str, Any]]) -> str:
    meta = report.get("report") if isinstance(report, dict) else {}
    if isinstance(meta, dict) and meta.get("name") == "control_recurrence_comparison":
        return "comparison"
    return "single_run"


def _single_run_id(report: Optional[Dict[str, Any]]) -> Optional[str]:
    roots = _list_from_nested(report, ("scope", "run_roots"))
    if roots:
        return str(roots[0]).rstrip("/\\").split("/")[-1].split("\\")[-1]
    return None


def _recommendation(report: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    value = report.get("recommendation") if isinstance(report, dict) else {}
    return value if isinstance(value, dict) else {}


def _recommendation_status(report: Optional[Dict[str, Any]]) -> str:
    return str(_recommendation(report).get("status") or "unknown")


def _highest_category(report: Optional[Dict[str, Any]]) -> str:
    recommendation = _recommendation(report)
    classification = report.get("recurrence_classification") if isinstance(report, dict) else {}
    if isinstance(classification, dict):
        return str(recommendation.get("highest_category") or classification.get("highest_category") or "none")
    return str(recommendation.get("highest_category") or "none")


def _schema_version(report: Optional[Dict[str, Any]]) -> Optional[str]:
    meta = report.get("report") if isinstance(report, dict) else {}
    if not isinstance(meta, dict):
        return None
    value = meta.get("schema_version") or meta.get("version") or meta.get("policy_version")
    return str(value) if value is not None else None


def _list_from_nested(report: Optional[Dict[str, Any]], path: Iterable[str]) -> List[str]:
    value = _nested(report, tuple(path))
    if isinstance(value, list):
        return sorted(str(item) for item in value if item is not None and str(item).strip())
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def _nested(value: Any, path: Tuple[str, ...]) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _round_ms(value: Any) -> Optional[float]:
    number = _safe_float(value)
    if number is None:
        return None
    return round(number, 3)


def _delta_ms(previous: Any, latest: Any) -> Optional[float]:
    previous_number = _safe_float(previous)
    latest_number = _safe_float(latest)
    if previous_number is None or latest_number is None:
        return None
    return _round_ms(latest_number - previous_number)


def _dedupe(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
