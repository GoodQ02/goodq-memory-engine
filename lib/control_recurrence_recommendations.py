from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from lib import control_recurrence_index


_CATEGORY_LEVEL = {
    "none": -1,
    "informational": 0,
    "watch": 1,
    "actionable": 2,
    "blocking": 3,
}

_SAFETY_BOUNDARY = {
    "mode": "read_only_deterministic_operator_draft",
    "control_agent": "not_activated",
    "auto_healing": "not_enabled",
    "config_mutation": "not_attempted",
    "command_execution": "not_attempted",
    "report_generation": "not_triggered",
    "ingestion": "not_triggered",
    "llm_usage": "not_used",
}


def build_recommendation_draft(
    report_id: str,
    base_dir: str | Path | None = None,
) -> Tuple[Dict[str, Any], int]:
    """Build a deterministic operator inspection draft for an indexed report."""

    report, status_code = control_recurrence_index.load_report_json(report_id, base_dir=base_dir)
    if status_code != 200 or report.get("status") in {"warning", "not_available", "not_found", "rejected"}:
        return report, status_code
    return build_recommendation_draft_from_report(report_id=report_id, report=report), 200


def build_recommendation_draft_from_report(report_id: str, report: Dict[str, Any]) -> Dict[str, Any]:
    report_type = _report_type(report)
    recommendation = _recommendation(report)
    classification = _classification(report)
    health = _health(report)
    families = _family_rows(report, classification)
    recovery_counts = _recovery_counts(report)
    highest_category = _highest_category(recommendation, classification)
    recommendation_status = str(recommendation.get("status") or "unknown").lower()

    blocking_summary = _blocking_summary(
        families=families,
        classification=classification,
        health=health,
        recovery_counts=recovery_counts,
    )
    top_priorities = _top_operator_priorities(
        families=families,
        highest_category=highest_category,
        health=health,
        recovery_counts=recovery_counts,
    )
    inspection_plan = _inspection_plan(
        families=families,
        highest_category=highest_category,
        health=health,
        recovery_counts=recovery_counts,
    )

    return {
        "status": "ok",
        "report_id": report_id,
        "report_type": report_type,
        "recommendation_status": recommendation_status,
        "highest_category": highest_category,
        "blocking_summary": blocking_summary,
        "top_operator_priorities": top_priorities,
        "inspection_plan": inspection_plan,
        "defer_mutation_reason": _defer_mutation_reason(
            highest_category=highest_category,
            health=health,
            recovery_counts=recovery_counts,
        ),
        "safety_boundary": dict(_SAFETY_BOUNDARY),
    }


def render_recommendation_draft(draft: Dict[str, Any]) -> str:
    if draft.get("status") != "ok":
        return "\n".join(
            [
                "GoodQ Control Recurrence Recommendation Draft",
                "================================================",
                f"Status: {draft.get('status', 'unknown')}",
                f"Report ID: {draft.get('report_id', 'unknown')}",
                f"Reason: {draft.get('reason', 'unknown')}",
            ]
        )

    lines = [
        "GoodQ Control Recurrence Recommendation Draft",
        "================================================",
        "Mode: read-only deterministic operator draft",
        f"Report ID: {draft.get('report_id')}",
        f"Recommendation: {str(draft.get('recommendation_status') or 'unknown').upper()}",
        f"Highest category: {draft.get('highest_category')}",
        "",
        "Blocking Summary:",
    ]
    blocking = draft.get("blocking_summary") if isinstance(draft.get("blocking_summary"), dict) else {}
    lines.append(f"  - blocking_signal_count: {blocking.get('blocking_signal_count', 0)}")
    lines.append(f"  - blocking_families: {', '.join(blocking.get('blocking_families') or []) or 'none'}")
    lines.append(f"  - phase6_health: {blocking.get('phase6_health', 'unknown')}")
    lines.append(f"  - qdrant_health: {blocking.get('qdrant_health', 'unknown')}")

    lines.append("")
    lines.append("Top Operator Priorities:")
    for index, item in enumerate(draft.get("top_operator_priorities") or [], start=1):
        lines.append(f"{index}. {item}")
    if not draft.get("top_operator_priorities"):
        lines.append("1. No operator priorities were produced.")

    lines.append("")
    lines.append("Inspection Plan:")
    for index, item in enumerate(draft.get("inspection_plan") or [], start=1):
        lines.append(f"{index}. {item}")
    if not draft.get("inspection_plan"):
        lines.append("1. No inspection steps were produced.")

    lines.append("")
    lines.append(f"Defer Mutation Reason: {draft.get('defer_mutation_reason')}")
    lines.append("")
    lines.append("Safety Boundary:")
    safety = draft.get("safety_boundary") if isinstance(draft.get("safety_boundary"), dict) else {}
    for key in sorted(safety):
        lines.append(f"  - {key}: {safety[key]}")
    return "\n".join(lines)


def _report_type(report: Dict[str, Any]) -> str:
    name = _nested(report, ("report", "name"))
    if name == "control_recurrence_comparison":
        return "comparison"
    return "single_run"


def _recommendation(report: Dict[str, Any]) -> Dict[str, Any]:
    recommendation = report.get("recommendation")
    return recommendation if isinstance(recommendation, dict) else {}


def _classification(report: Dict[str, Any]) -> Dict[str, Any]:
    if _report_type(report) == "comparison":
        value = _nested(report, ("candidate", "recurrence_classification"))
        return value if isinstance(value, dict) else {}
    value = report.get("recurrence_classification")
    return value if isinstance(value, dict) else {}


def _health(report: Dict[str, Any]) -> Dict[str, Any]:
    if _report_type(report) == "comparison":
        value = _nested(report, ("candidate", "phase6_qdrant_truth"))
        return value if isinstance(value, dict) else {}
    value = report.get("phase6_qdrant_truth")
    return value if isinstance(value, dict) else {}


def _family_rows(report: Dict[str, Any], classification: Dict[str, Any]) -> List[Dict[str, Any]]:
    top_by_family = {
        str(row.get("error_family")): row
        for row in (report.get("top_repeated_failure_families") or [])
        if isinstance(row, dict) and row.get("error_family")
    }
    rows: List[Dict[str, Any]] = []
    for item in classification.get("families") or []:
        if not isinstance(item, dict):
            continue
        family = str(item.get("error_family") or "unknown")
        merged = dict(item)
        if family in top_by_family:
            merged.update({key: value for key, value in top_by_family[family].items() if key not in merged})
        rows.append(merged)

    if not rows and _report_type(report) == "comparison":
        for family, count in (_nested(report, ("candidate", "error_families")) or {}).items():
            rows.append({"error_family": family, "count": count, "category": "informational"})

    return sorted(
        rows,
        key=lambda row: (
            -_CATEGORY_LEVEL.get(str(row.get("category") or "informational"), 0),
            -int(row.get("count") or 0),
            str(row.get("error_family") or ""),
        ),
    )


def _recovery_counts(report: Dict[str, Any]) -> Dict[str, int]:
    if _report_type(report) == "comparison":
        value = _nested(report, ("candidate", "recovery_counts"))
    else:
        value = report.get("recovered_vs_unrecovered_failures")
    if not isinstance(value, dict):
        return {}
    out: Dict[str, int] = {}
    for key, count in value.items():
        try:
            out[str(key)] = int(count or 0)
        except Exception:
            out[str(key)] = 0
    return out


def _highest_category(recommendation: Dict[str, Any], classification: Dict[str, Any]) -> str:
    value = recommendation.get("highest_category") or classification.get("highest_category") or "none"
    return str(value)


def _blocking_summary(
    *,
    families: List[Dict[str, Any]],
    classification: Dict[str, Any],
    health: Dict[str, Any],
    recovery_counts: Dict[str, int],
) -> Dict[str, Any]:
    blocking_families = [
        str(row.get("error_family"))
        for row in families
        if str(row.get("category") or "") == "blocking" and row.get("error_family")
    ]
    blocking_signals = int(_nested(classification, ("signal_counts", "blocking")) or 0)
    unrecovered = _sum_by_prefix(recovery_counts, "unrecovered")
    if unrecovered > 0 and blocking_signals == 0:
        blocking_signals = unrecovered
    return {
        "blocking_signal_count": blocking_signals,
        "blocking_families": blocking_families,
        "unrecovered_count": unrecovered,
        "canonical_artifact_missing_families": [
            family
            for family in blocking_families
            if "missing" in family or "incomplete" in family or "unhealthy" in family
        ],
        "phase6_health": _phase6_status(health),
        "qdrant_health": _qdrant_status(health),
    }


def _top_operator_priorities(
    *,
    families: List[Dict[str, Any]],
    highest_category: str,
    health: Dict[str, Any],
    recovery_counts: Dict[str, int],
) -> List[str]:
    focus = _families_at_or_above(families, highest_category)
    if highest_category == "blocking":
        return _dedupe(
            [
                *_family_priority_lines(focus, "Inspect blocking recurrence family"),
                "Inspect canonical artifact paths, scene manifests, temporal indexes, and run ledger before considering any mutation.",
                "Confirm whether Phase 6 or Qdrant truth is incomplete or unhealthy.",
            ]
        )
    if highest_category == "actionable":
        lines = _family_priority_lines(focus, "Inspect actionable recovered/runtime recurrence family")
        lines.extend(
            [
                "Inspect affected step distribution, stderr/error tails, retry/fallback outcomes, and final scene survival.",
                "Confirm Phase 6 and Qdrant remained healthy after recovery.",
            ]
        )
        if _sum_by_prefix(recovery_counts, "unrecovered") == 0:
            lines.append("Defer mutation because unrecovered count is zero.")
        return _dedupe(lines)
    if highest_category == "watch":
        return _dedupe(
            [
                *_family_priority_lines(focus, "Trend watch recurrence family"),
                "Inspect targeted status fields and persisted metadata for correlation with unhealthy Phase 6 or Qdrant output.",
                "Keep this as observation unless counts increase or final truth surfaces degrade.",
            ]
        )

    healthy = bool(health.get("healthy")) if health else False
    return [
        "No immediate action while recurrence remains informational and final truth surfaces are healthy."
        if healthy
        else "Inspect informational recurrence only for correlation with degraded final truth surfaces.",
        "Watch for sharp count increases across future indexed reports.",
    ]


def _inspection_plan(
    *,
    families: List[Dict[str, Any]],
    highest_category: str,
    health: Dict[str, Any],
    recovery_counts: Dict[str, int],
) -> List[str]:
    focus = _families_at_or_above(families, highest_category)
    plan: List[str] = []

    if highest_category == "blocking":
        plan.extend(
            [
                "Inspect blocking families in the durable report and identify which canonical artifact or health surface failed.",
                "Inspect canonical processing paths, scene_manifest.json, temporal_index.json, scene_ingest_results.json, and experiment_log/run ledger entries.",
                "Confirm whether Phase 6 completion or Qdrant health is incomplete before discussing any corrective action.",
                "Do not start with a broad rerun; establish the missing or unhealthy truth surface first.",
            ]
        )
    elif highest_category == "actionable":
        step_names = _step_names(focus)
        family_label = _family_label(focus)
        if family_label:
            plan.append(f"Inspect recovered/actionable recurrence in {family_label}.")
        if step_names:
            plan.append(f"Inspect affected step distribution: {', '.join(step_names)}.")
        plan.extend(
            [
                "Inspect stderr/error tails, run warnings, retry/fallback outcome, and whether each affected final scene output survived.",
                "Compare affected scenes against successful fallback output and final scene artifacts.",
                "Confirm Phase 6 and Qdrant remained healthy.",
            ]
        )
        if _sum_by_prefix(recovery_counts, "unrecovered") == 0:
            plan.append("Defer mutation because unrecovered count is zero.")
    elif highest_category == "watch":
        plan.extend(
            [
                "Trend watch-level recurrence counts across indexed reports before proposing any change.",
                "Inspect only the targeted status/meta fields named by the report operator hints.",
                "Confirm watch signals do not correlate with unhealthy Phase 6 or Qdrant output.",
            ]
        )
    else:
        plan.extend(
            [
                "Take no action while expected informational skips remain isolated and Phase 6/Qdrant stay healthy.",
                "Record informational counts and compare against future reports for sharp increases.",
                "Inspect targeted optional-enrichment metadata only if final truth surfaces become unhealthy.",
            ]
        )

    hint_lines = _hint_lines(focus)
    plan.extend(hint_lines[:3])
    return _dedupe(plan)


def _defer_mutation_reason(
    *,
    highest_category: str,
    health: Dict[str, Any],
    recovery_counts: Dict[str, int],
) -> str:
    if highest_category == "blocking":
        return "Mutation deferred: inspect blocking truth surfaces and run ledger first; this draft has no healing authority."
    if highest_category == "actionable":
        if _sum_by_prefix(recovery_counts, "unrecovered") == 0:
            return "Mutation deferred: actionable recurrences were recovered and unrecovered count is zero."
        return "Mutation deferred: actionable recurrences require human inspection before any scoped fix."
    if highest_category == "watch":
        return "Mutation deferred: watch-level signals require trending and targeted inspection only."
    if isinstance(health, dict) and bool(health.get("healthy")):
        return "No mutation indicated: informational recurrence only and final truth surfaces are healthy."
    return "Mutation deferred: inspect final truth surface health before considering any change."


def _families_at_or_above(families: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
    threshold = _CATEGORY_LEVEL.get(category, 0)
    return [
        row
        for row in families
        if _CATEGORY_LEVEL.get(str(row.get("category") or "informational"), 0) >= threshold
    ] or families[:3]


def _family_priority_lines(rows: Iterable[Dict[str, Any]], prefix: str) -> List[str]:
    lines: List[str] = []
    for row in rows:
        family = row.get("error_family") or "unknown"
        count = int(row.get("count") or 0)
        step_names = _step_names([row])
        suffix = f" across {', '.join(step_names)}" if step_names else ""
        lines.append(f"{prefix}: {family} (count={count}){suffix}.")
    return lines


def _hint_lines(rows: Iterable[Dict[str, Any]]) -> List[str]:
    lines: List[str] = []
    for row in rows:
        family = row.get("error_family") or "unknown"
        for hint in row.get("operator_hints") or []:
            lines.append(f"Use report hint for {family}: {hint}")
        for target in row.get("inspection_targets") or []:
            lines.append(f"Inspect target for {family}: {target}")
    return lines


def _step_names(rows: Iterable[Dict[str, Any]]) -> List[str]:
    names: List[str] = []
    for row in rows:
        for value in row.get("step_names") or []:
            if value and str(value) not in names:
                names.append(str(value))
    return names


def _family_label(rows: Iterable[Dict[str, Any]]) -> str:
    names = [str(row.get("error_family")) for row in rows if row.get("error_family")]
    return ", ".join(names[:3])


def _phase6_status(health: Dict[str, Any]) -> str:
    if not isinstance(health, dict):
        return "unknown"
    if health.get("healthy") is True:
        return "healthy"
    return str(health.get("status") or "unknown")


def _qdrant_status(health: Dict[str, Any]) -> str:
    if not isinstance(health, dict):
        return "unknown"
    episodes = health.get("episodes")
    if isinstance(episodes, list) and episodes:
        healthy = sum(1 for row in episodes if isinstance(row, dict) and row.get("qdrant_ok") is True)
        if healthy == len(episodes):
            return "healthy"
        return "degraded"
    if health.get("healthy") is True:
        return "healthy"
    return str(health.get("status") or "unknown")


def _sum_by_prefix(values: Dict[str, int], prefix: str) -> int:
    return sum(int(value or 0) for key, value in values.items() if str(key).startswith(prefix))


def _nested(value: Any, keys: Tuple[str, ...]) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _dedupe(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in out:
            out.append(text)
    return out
