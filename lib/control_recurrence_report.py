from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from lib import run_index


_OK_STATUSES = {"", "ok", "success", "complete", "completed", "available"}
_SKIP_STATUSES = {"skipped", "skip", "no_text", "not_attempted", "unavailable"}
_ERROR_STATUSES = {"error", "failed", "fail", "missing", "timeout"}
_NATIVE_CRASH_CODES = {
    3221226505: "0xC0000409",
    -1073740791: "0xC0000409",
}
_INFORMATIONAL_FAMILIES = {
    "audio_silent",
    "insufficient_diverse_speech",
    "no_text",
    "too_short",
}
_CATEGORY_ORDER = {
    "informational": 0,
    "watch": 1,
    "actionable": 2,
    "blocking": 3,
}
_WATCH_FAMILIES = {
    "diarization_unavailable",
    "embedding_missing",
    "modality_degraded",
}
_BLOCKING_FAMILIES = {
    "canonical_artifact_missing",
    "missing_scene_manifest",
    "missing_temporal_index",
    "phase6_incomplete",
    "qdrant_unhealthy",
}
_REPO_ROOT = Path(__file__).resolve().parents[1]
_DATA_ROOT = os.environ.get("GOODQ_DATA_ROOT")
if _DATA_ROOT:
    _DEFAULT_MARKDOWN_OUTPUT_DIR = Path(_DATA_ROOT) / "reports" / "control_recurrence"
else:
    _DEFAULT_MARKDOWN_OUTPUT_DIR = _REPO_ROOT / "reports" / "control_recurrence"
_INDEX_FILENAME = "index.json"
_DEFAULT_STEP_TIMEOUT_BOUNDARY_MS = 1_800_000
_SLOW_STEP_OUTLIER_MS = 60_000
_TOP_LATENCY_ROWS_PER_STEP = 5


@dataclass(frozen=True)
class _EpisodeScope:
    report_run_id: str
    episode: str
    run_dir: Path
    runtime_run_id: Optional[str]
    video_id: Optional[str]
    video_hash: Optional[str]
    video_name: Optional[str]
    step_runs_path: Optional[Path]
    output_path: Optional[Path]
    scene_manifest_path: Optional[Path]
    temporal_index_path: Optional[Path]
    resolved_config_path: Optional[Path]
    episode_log_path: Optional[Path]
    stdout_path: Optional[Path] = None
    stderr_path: Optional[Path] = None
    output_item_index: Optional[int] = None


def build_control_recurrence_report(
    *,
    run_root: str | Path | None = None,
    run_id: str | None = None,
    reports_root: str | Path | None = None,
    limit_runs: int = 1,
    step_runs_path: str | Path | None = None,
) -> Dict[str, Any]:
    """Build a read-only recurrence report from persisted runtime truth surfaces."""

    run_roots = _select_run_roots(
        run_root=run_root,
        run_id=run_id,
        reports_root=reports_root,
        limit_runs=limit_runs,
    )

    files_read: List[str] = []
    warnings: List[str] = []
    episodes: List[_EpisodeScope] = []
    health_by_episode: List[Dict[str, Any]] = []
    signals: List[Dict[str, Any]] = []
    latency_rows: List[Dict[str, Any]] = []
    step_coverage_rows: List[Dict[str, Any]] = []

    for selected_root in run_roots:
        episode_scopes, root_files, root_warnings = _load_run_scope(selected_root)
        episodes.extend(episode_scopes)
        files_read.extend(root_files)
        warnings.extend(root_warnings)

    if step_runs_path is not None:
        explicit_step_path = Path(step_runs_path)
        episodes = [_replace_episode_step_path(episode, explicit_step_path) for episode in episodes]

    episode_by_runtime_id = _unique_episode_map((e.runtime_run_id, e) for e in episodes)
    episode_by_video_id = {
        e.video_id: e for e in episodes if isinstance(e.video_id, str) and e.video_id.strip()
    }
    target_runtime_run_ids = sorted(
        {e.runtime_run_id for e in episodes if isinstance(e.runtime_run_id, str) and e.runtime_run_id.strip()}
    )

    for episode in episodes:
        episode_signals, episode_files, episode_warnings, episode_health = _load_episode_artifact_signals(episode)
        signals.extend(episode_signals)
        files_read.extend(episode_files)
        warnings.extend(episode_warnings)
        health_by_episode.append(episode_health)

    step_paths = _dedupe_paths(e.step_runs_path for e in episodes if e.step_runs_path is not None)
    step_run_scope = {
        "strict_run_id_filter_applied": False,
        "target_run_ids": target_runtime_run_ids,
        "excluded_run_ids": {},
        "limited_run_id_scope": False,
    }
    for path in step_paths:
        (
            step_signals,
            step_latency_rows,
            step_coverage,
            step_files,
            step_warnings,
            step_scope_info,
        ) = _load_step_run_signals(
            path=path,
            episode_by_runtime_id=episode_by_runtime_id,
            episode_by_video_id=episode_by_video_id,
            target_runtime_run_ids=target_runtime_run_ids,
        )
        signals.extend(step_signals)
        latency_rows.extend(step_latency_rows)
        step_coverage_rows.extend(step_coverage)
        files_read.extend(step_files)
        warnings.extend(step_warnings)
        step_run_scope["strict_run_id_filter_applied"] = bool(
            step_run_scope["strict_run_id_filter_applied"] or step_scope_info.get("strict_run_id_filter_applied")
        )
        step_run_scope["limited_run_id_scope"] = bool(
            step_run_scope["limited_run_id_scope"] or step_scope_info.get("limited_run_id_scope")
        )
        excluded = step_run_scope["excluded_run_ids"]
        for excluded_run_id, count in (step_scope_info.get("excluded_run_ids") or {}).items():
            excluded[excluded_run_id] = int(excluded.get(excluded_run_id, 0)) + int(count or 0)

    for signal in signals:
        if not signal.get("recovery_outcome"):
            signal["recovery_outcome"] = _infer_recovery_outcome(signal, health_by_episode, signals)
    signals = _coalesce_runtime_event_duplicates(signals)
    signals = _dedupe_signals(signals)

    phase6_health = _phase6_health_summary(health_by_episode)
    latency_summary = _step_latency_summary(latency_rows)
    environment_summary = _environment_summary(step_coverage_rows, signals)
    grouped = _group_signals(signals)
    family_rows = _attach_family_categories(_top_families(signals), phase6_health)
    _attach_operator_hints_to_families(family_rows)
    family_categories = _category_by_family(family_rows)
    _attach_row_categories(grouped, family_categories)
    optional_skips = _optional_enrichment_skips(signals)
    _attach_row_categories(optional_skips, family_categories)
    optional_coverage = _optional_enrichment_coverage(step_coverage_rows)
    recovery_counts = _recovery_counts(signals)
    affected = _scenes_affected(signals)
    _attach_scene_categories(affected, family_categories)
    recurrence_classification = _classification_summary(family_rows)
    recommendation = _recommendation_from_classification(recurrence_classification)
    operator_guidance = _report_operator_guidance(family_rows, recurrence_classification)

    return {
        "report": {
            "name": "control_recurrence_report",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "mode": "read_only_observability",
            "control_agent": "not_activated",
            "auto_healing": "not_enabled",
            "config_mutation": "not_attempted",
            "truth_surfaces": [
                "step_runs.jsonl",
                "run.warnings from _resolved_config.json",
                "scene_ingest_results.json",
                "scene_manifest.json",
                "temporal_index.json",
                "direct-run operator logs when wrapper experiment_log.json is absent",
            ],
        },
        "scope": {
            "run_roots": [_display_path(p) for p in run_roots],
            "episodes": len(episodes),
            "runtime_run_ids": sorted(
                {e.runtime_run_id for e in episodes if isinstance(e.runtime_run_id, str) and e.runtime_run_id}
            ),
            "videos": sorted({e.video_name or e.episode for e in episodes if e.video_name or e.episode}),
            "signals": len(signals),
            "step_runs_files": [_display_path(p) for p in step_paths],
            "step_run_scope": step_run_scope,
        },
        "step_latency_summary": latency_summary,
        "environment_summary": environment_summary,
        "recurrence_summary": grouped,
        "top_repeated_failure_families": family_rows,
        "optional_enrichment_skips": optional_skips,
        "optional_enrichment_coverage": optional_coverage,
        "recovered_vs_unrecovered_failures": recovery_counts,
        "scenes_affected": affected,
        "phase6_qdrant_truth": phase6_health,
        "recurrence_classification": recurrence_classification,
        "recommendation": recommendation,
        "operator_hints": operator_guidance["operator_hints"],
        "inspection_targets": operator_guidance["inspection_targets"],
        "evidence": {
            "files_read": _dedupe_strings(_display_text(value) for value in files_read),
            "warnings": _dedupe_strings(_display_text(value) for value in warnings),
        },
    }


def build_control_recurrence_comparison(
    *,
    baseline_run_root: str | Path | None = None,
    baseline_run_id: str | None = None,
    candidate_run_root: str | Path | None = None,
    candidate_run_id: str | None = None,
    reports_root: str | Path | None = None,
) -> Dict[str, Any]:
    """Compare two read-only recurrence reports from persisted runtime artifacts."""

    baseline = build_control_recurrence_report(
        run_root=baseline_run_root,
        run_id=baseline_run_id,
        reports_root=reports_root,
        limit_runs=1,
    )
    candidate = build_control_recurrence_report(
        run_root=candidate_run_root,
        run_id=candidate_run_id,
        reports_root=reports_root,
        limit_runs=1,
    )

    baseline_family_counts = _family_counts(baseline)
    candidate_family_counts = _family_counts(candidate)
    baseline_step_counts = _signal_counts_by(baseline, "step_name")
    candidate_step_counts = _signal_counts_by(candidate, "step_name")
    baseline_episode_counts = _episode_video_counts(baseline)
    candidate_episode_counts = _episode_video_counts(candidate)
    baseline_recovery = _safe_int_map(baseline.get("recovered_vs_unrecovered_failures"))
    candidate_recovery = _safe_int_map(candidate.get("recovered_vs_unrecovered_failures"))
    family_categories = _merged_family_categories(baseline, candidate)
    latency_delta = _latency_delta(
        baseline.get("step_latency_summary"),
        candidate.get("step_latency_summary"),
    )
    optional_coverage_delta = _optional_enrichment_coverage_delta(
        baseline.get("optional_enrichment_coverage"),
        candidate.get("optional_enrichment_coverage"),
    )

    family_delta_map = _count_delta_map(baseline_family_counts, candidate_family_counts)
    _attach_delta_categories(family_delta_map, family_categories)
    new_families = sorted(set(candidate_family_counts) - set(baseline_family_counts))
    resolved_families = sorted(set(baseline_family_counts) - set(candidate_family_counts))
    increased = [row for row in _delta_rows(family_delta_map, category_by_key=family_categories) if int(row["delta"]) > 0]
    decreased = [row for row in _delta_rows(family_delta_map, category_by_key=family_categories) if int(row["delta"]) < 0]
    phase6_delta = _health_delta(baseline.get("phase6_qdrant_truth"), candidate.get("phase6_qdrant_truth"), "phase6")
    qdrant_delta = _health_delta(baseline.get("phase6_qdrant_truth"), candidate.get("phase6_qdrant_truth"), "qdrant")
    candidate_guidance = _guidance_from_report(candidate)

    delta = {
        "total_recurrence_signals": {
            "baseline": int(_nested_get(baseline, ("scope", "signals")) or 0),
            "candidate": int(_nested_get(candidate, ("scope", "signals")) or 0),
        },
        "signals_by_error_family": family_delta_map,
        "recovery_counts": _count_delta_map(baseline_recovery, candidate_recovery),
        "category_counts": _category_counts_delta(
            baseline.get("recurrence_classification"),
            candidate.get("recurrence_classification"),
        ),
        "new_error_families": new_families,
        "resolved_error_families": resolved_families,
        "increased_error_families": increased,
        "decreased_error_families": decreased,
        "per_step_changes": _delta_rows(
            _count_delta_map(baseline_step_counts, candidate_step_counts),
            key_name="step_name",
        ),
        "per_episode_video_changes": _delta_rows(
            _count_delta_map(baseline_episode_counts, candidate_episode_counts),
            key_name="episode_video",
        ),
        "step_latency_delta": latency_delta,
        "optional_enrichment_coverage_delta": optional_coverage_delta,
        "phase6_health_delta": phase6_delta,
        "qdrant_health_delta": qdrant_delta,
    }
    delta["total_recurrence_signals"]["delta"] = (
        delta["total_recurrence_signals"]["candidate"] - delta["total_recurrence_signals"]["baseline"]
    )

    recommendation = _comparison_recommendation(
        delta=delta,
        candidate_classification=candidate.get("recurrence_classification"),
        candidate_health=candidate.get("phase6_qdrant_truth"),
    )

    return {
        "report": {
            "name": "control_recurrence_comparison",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "mode": "read_only_observability_comparison",
            "control_agent": "not_activated",
            "auto_healing": "not_enabled",
            "config_mutation": "not_attempted",
            "truth_surfaces": [
                "step_runs.jsonl",
                "experiment_log.json",
                "scene_ingest_results.json",
                "scene_manifest.json",
                "temporal_index.json",
            ],
        },
        "baseline": _comparison_run_summary(baseline, label="baseline"),
        "candidate": _comparison_run_summary(candidate, label="candidate"),
        "delta": delta,
        "recommendation": recommendation,
        "operator_hints": candidate_guidance["operator_hints"],
        "inspection_targets": candidate_guidance["inspection_targets"],
        "evidence": {
            "files_read": _dedupe_strings(
                list(_nested_get(baseline, ("evidence", "files_read")) or [])
                + list(_nested_get(candidate, ("evidence", "files_read")) or [])
            ),
            "warnings": _dedupe_strings(
                list(_nested_get(baseline, ("evidence", "warnings")) or [])
                + list(_nested_get(candidate, ("evidence", "warnings")) or [])
            ),
        },
    }


def render_text_report(report: Dict[str, Any], *, limit: int = 12) -> str:
    lines: List[str] = []
    scope = report.get("scope") if isinstance(report, dict) else {}
    health = report.get("phase6_qdrant_truth") if isinstance(report, dict) else {}
    recovery = report.get("recovered_vs_unrecovered_failures") if isinstance(report, dict) else {}
    classification = report.get("recurrence_classification") if isinstance(report, dict) else {}
    recommendation = report.get("recommendation") if isinstance(report, dict) else {}
    latency = report.get("step_latency_summary") if isinstance(report, dict) else {}
    environment_summary = report.get("environment_summary") if isinstance(report, dict) else {}
    optional_coverage = report.get("optional_enrichment_coverage") if isinstance(report, dict) else {}

    lines.append("GoodQ Control Recurrence Report")
    lines.append("================================")
    lines.append("Mode: read-only observability")
    lines.append("ControlAgent: not activated")
    lines.append("Auto-healing: not enabled")
    lines.append(f"Run roots: {len(scope.get('run_roots') or [])}")
    lines.append(f"Episodes: {scope.get('episodes', 0)}")
    lines.append(f"Signals: {scope.get('signals', 0)}")
    step_scope = scope.get("step_run_scope") if isinstance(scope.get("step_run_scope"), dict) else {}
    if step_scope:
        lines.append(
            "Step run scope: strict_run_id_filter={strict} limited_run_id_scope={limited} excluded_run_ids={excluded}".format(
                strict=bool(step_scope.get("strict_run_id_filter_applied")),
                limited=bool(step_scope.get("limited_run_id_scope")),
                excluded=len(step_scope.get("excluded_run_ids") or {}),
            )
        )
    lines.append("")

    lines.append("Recommendation")
    lines.append(f"  - {str(recommendation.get('status') or 'unknown').upper()}")
    lines.append(f"  - highest category: {classification.get('highest_category', 'none')}")
    for reason in recommendation.get("reasons") or []:
        lines.append(f"  - {reason}")
    lines.append("")

    lines.append("Operator Hints")
    for hint in (report.get("operator_hints") or [])[:limit]:
        lines.append(f"  - {hint}")
    if not report.get("operator_hints"):
        lines.append("  - none")
    lines.append("")

    lines.append("Inspection Targets")
    for target in (report.get("inspection_targets") or [])[:limit]:
        lines.append(f"  - {target}")
    if not report.get("inspection_targets"):
        lines.append("  - none")
    lines.append("")

    lines.append("Category Counts")
    signal_counts = classification.get("signal_counts") if isinstance(classification, dict) else {}
    family_counts = classification.get("family_counts") if isinstance(classification, dict) else {}
    for category in _CATEGORY_ORDER:
        lines.append(
            f"  - {category}: families={family_counts.get(category, 0)} signals={signal_counts.get(category, 0)}"
        )
    lines.append("")

    lines.extend(_text_step_latency_summary(latency, limit=limit))
    lines.append("")
    lines.extend(_text_environment_summary(environment_summary, limit=limit))
    lines.append("")
    lines.extend(_text_optional_enrichment_coverage(optional_coverage, limit=limit))
    lines.append("")

    lines.append("Recurrence Summary")
    for row in (report.get("recurrence_summary") or [])[:limit]:
        lines.append(
            "  - count={count} run_id={run_id} episode={episode} step={step_name} "
            "status={status} reason={reason} family={error_family} category={category} scene={scene_id} recovery={recovery_outcome}".format(
                **_text_row_defaults(row)
            )
        )
    if not report.get("recurrence_summary"):
        lines.append("  - no non-ok recurrence signals found")
    lines.append("")

    lines.append("Top Repeated Failure Families")
    for row in (report.get("top_repeated_failure_families") or [])[:limit]:
        lines.append(
            f"  - {row.get('error_family')}: count={row.get('count')} "
            f"category={row.get('category')} episodes={row.get('episodes')} scenes={row.get('scenes')}"
        )
    if not report.get("top_repeated_failure_families"):
        lines.append("  - none")
    lines.append("")

    lines.append("Optional Enrichment Skips")
    for row in (report.get("optional_enrichment_skips") or [])[:limit]:
        lines.append(
            "  - count={count} episode={episode} step={step_name} status={status} "
            "reason={reason} family={error_family} recovery={recovery_outcome}".format(**_text_row_defaults(row))
        )
    if not report.get("optional_enrichment_skips"):
        lines.append("  - none")
    lines.append("")

    lines.append("Recovered vs Unrecovered")
    lines.append(
        "  - recovered={recovered} unrecovered={unrecovered} skipped={skipped} unknown={unknown}".format(
            recovered=recovery.get("recovered", 0),
            unrecovered=recovery.get("unrecovered", 0),
            skipped=recovery.get("skipped", 0),
            unknown=recovery.get("unknown", 0),
        )
    )
    lines.append("")

    lines.append("Scenes Affected")
    for row in (report.get("scenes_affected") or [])[:limit]:
        lines.append(
            f"  - scene={row.get('scene_id')} episode={row.get('episode')} "
            f"index={row.get('scene_index')} families={', '.join(row.get('error_families') or [])}"
        )
    if not report.get("scenes_affected"):
        lines.append("  - none")
    lines.append("")

    lines.append("Final Phase 6 / Qdrant Truth")
    lines.append(f"  - status={health.get('status', 'unknown')} healthy={health.get('healthy', False)}")
    for row in (health.get("episodes") or [])[:limit]:
        lines.append(
            f"  - episode={row.get('episode')} phase6={row.get('phase6_complete')} "
            f"harmonized={row.get('phase6_harmonized')} qdrant={row.get('qdrant_ok')} "
            f"scenes={row.get('scene_count')} status={row.get('status')}"
        )

    return "\n".join(lines)


def render_text_comparison(comparison: Dict[str, Any], *, limit: int = 12) -> str:
    baseline = comparison.get("baseline") if isinstance(comparison, dict) else {}
    candidate = comparison.get("candidate") if isinstance(comparison, dict) else {}
    delta = comparison.get("delta") if isinstance(comparison, dict) else {}
    recommendation = comparison.get("recommendation") if isinstance(comparison, dict) else {}
    total = delta.get("total_recurrence_signals") if isinstance(delta, dict) else {}
    coverage_delta = delta.get("optional_enrichment_coverage_delta") if isinstance(delta, dict) else {}
    phase6 = delta.get("phase6_health_delta") if isinstance(delta, dict) else {}
    qdrant = delta.get("qdrant_health_delta") if isinstance(delta, dict) else {}

    lines: List[str] = []
    lines.append("GoodQ Control Recurrence Comparison")
    lines.append("====================================")
    lines.append("Mode: read-only observability comparison")
    lines.append("ControlAgent: not activated")
    lines.append("Auto-healing: not enabled")
    lines.append(f"Baseline: {baseline.get('run_id') or 'unknown'}")
    lines.append(f"Candidate: {candidate.get('run_id') or 'unknown'}")
    lines.append(
        "Signals: baseline={baseline} candidate={candidate} delta={delta}".format(
            baseline=total.get("baseline", 0),
            candidate=total.get("candidate", 0),
            delta=total.get("delta", 0),
        )
    )
    lines.append("")

    lines.append("Recommendation")
    lines.append(f"  - {str(recommendation.get('status') or 'unknown').upper()}")
    lines.append(f"  - highest category: {recommendation.get('highest_category', 'none')}")
    for reason in recommendation.get("reasons") or []:
        lines.append(f"  - {reason}")
    lines.append("")

    lines.append("Operator Hints")
    for hint in (comparison.get("operator_hints") or [])[:limit]:
        lines.append(f"  - {hint}")
    if not comparison.get("operator_hints"):
        lines.append("  - none")
    lines.append("")

    lines.append("Inspection Targets")
    for target in (comparison.get("inspection_targets") or [])[:limit]:
        lines.append(f"  - {target}")
    if not comparison.get("inspection_targets"):
        lines.append("  - none")
    lines.append("")

    lines.append("Category Counts")
    for category, row in (delta.get("category_counts") or {}).items():
        lines.append(
            f"  - {category}: families {row.get('baseline_family_count')} -> {row.get('candidate_family_count')} "
            f"(delta={row.get('family_delta')}), signals {row.get('baseline_signal_count')} -> "
            f"{row.get('candidate_signal_count')} (delta={row.get('signal_delta')})"
        )
    lines.append("")

    lines.append("New Error Families")
    for family in (delta.get("new_error_families") or [])[:limit]:
        lines.append(f"  - {family}")
    if not delta.get("new_error_families"):
        lines.append("  - none")
    lines.append("")

    lines.append("Resolved Error Families")
    for family in (delta.get("resolved_error_families") or [])[:limit]:
        lines.append(f"  - {family}")
    if not delta.get("resolved_error_families"):
        lines.append("  - none")
    lines.append("")

    lines.append("Families Increased")
    for row in (delta.get("increased_error_families") or [])[:limit]:
        lines.append(
            f"  - {row.get('error_family')} [{row.get('category')}]: {row.get('baseline_count')} -> "
            f"{row.get('candidate_count')} (delta={row.get('delta')})"
        )
    if not delta.get("increased_error_families"):
        lines.append("  - none")
    lines.append("")

    lines.append("Families Decreased")
    for row in (delta.get("decreased_error_families") or [])[:limit]:
        lines.append(
            f"  - {row.get('error_family')} [{row.get('category')}]: {row.get('baseline_count')} -> "
            f"{row.get('candidate_count')} (delta={row.get('delta')})"
        )
    if not delta.get("decreased_error_families"):
        lines.append("  - none")
    lines.append("")

    lines.append("Recovered / Unrecovered / Skipped")
    for key, row in (delta.get("recovery_counts") or {}).items():
        lines.append(
            f"  - {key}: {row.get('baseline_count')} -> {row.get('candidate_count')} "
            f"(delta={row.get('delta')})"
        )
    lines.append("")

    lines.append("Per-Step Changes")
    for row in (delta.get("per_step_changes") or [])[:limit]:
        lines.append(
            f"  - {row.get('step_name')}: {row.get('baseline_count')} -> "
            f"{row.get('candidate_count')} (delta={row.get('delta')})"
        )
    if not delta.get("per_step_changes"):
        lines.append("  - none")
    lines.append("")

    lines.extend(_text_step_latency_delta(delta.get("step_latency_delta") or {}, limit=limit))
    lines.append("")
    lines.extend(_text_optional_enrichment_coverage_delta(coverage_delta, limit=limit))
    lines.append("")

    lines.append("Per-Episode/Video Changes")
    for row in (delta.get("per_episode_video_changes") or [])[:limit]:
        lines.append(
            f"  - {row.get('episode_video')}: {row.get('baseline_count')} -> "
            f"{row.get('candidate_count')} (delta={row.get('delta')})"
        )
    if not delta.get("per_episode_video_changes"):
        lines.append("  - none")
    lines.append("")

    lines.append("Phase 6 Health Delta")
    lines.append(
        f"  - healthy_episodes: {phase6.get('baseline_healthy_episodes', 0)} -> "
        f"{phase6.get('candidate_healthy_episodes', 0)} "
        f"(delta={phase6.get('delta_healthy_episodes', 0)}) status={phase6.get('status')}"
    )
    lines.append("Qdrant Health Delta")
    lines.append(
        f"  - healthy_episodes: {qdrant.get('baseline_healthy_episodes', 0)} -> "
        f"{qdrant.get('candidate_healthy_episodes', 0)} "
        f"(delta={qdrant.get('delta_healthy_episodes', 0)}) status={qdrant.get('status')}"
    )

    return "\n".join(lines)


def _text_step_latency_summary(latency: Dict[str, Any], *, limit: int) -> List[str]:
    lines = ["Step Latency Summary"]
    if not isinstance(latency, dict) or not latency.get("duration_row_count"):
        lines.append("  - no step duration rows found")
        return lines
    lines.append(
        "  - rows={rows} steps={steps} slow_outliers={slow} timeout_exceedances={timeout}".format(
            rows=int(latency.get("duration_row_count") or 0),
            steps=int(latency.get("step_count") or 0),
            slow=int(latency.get("slow_outlier_count") or 0),
            timeout=int(latency.get("timeout_boundary_exceedance_count") or 0),
        )
    )
    for row in (latency.get("steps") or [])[:limit]:
        if not isinstance(row, dict):
            continue
        lines.append(
            "  - step={step_name} rows={count} ok={ok_count} non_ok={non_ok_count} "
            "p50_ms={p50_ms} p95_ms={p95_ms} max_ms={max_ms} slow_outliers={slow_outlier_count} "
            "timeout_exceedances={timeout_boundary_exceedance_count}".format(
                step_name=row.get("step_name") or "unknown_step",
                count=int(row.get("count") or 0),
                ok_count=int(row.get("ok_count") or 0),
                non_ok_count=int(row.get("non_ok_count") or 0),
                p50_ms=_format_ms_text(row.get("p50_ms")),
                p95_ms=_format_ms_text(row.get("p95_ms")),
                max_ms=_format_ms_text(row.get("max_ms")),
                slow_outlier_count=int(row.get("slow_outlier_count") or 0),
                timeout_boundary_exceedance_count=int(row.get("timeout_boundary_exceedance_count") or 0),
            )
        )
    return lines


def _text_step_latency_delta(delta: Dict[str, Any], *, limit: int) -> List[str]:
    lines = ["Step Latency Delta"]
    if not isinstance(delta, dict) or not delta.get("steps"):
        lines.append("  - no comparable step latency rows found")
        return lines
    lines.append(
        "  - status={status} baseline_rows={baseline} candidate_rows={candidate}".format(
            status=delta.get("status") or "unknown",
            baseline=int(delta.get("baseline_duration_row_count") or 0),
            candidate=int(delta.get("candidate_duration_row_count") or 0),
        )
    )
    for row in (delta.get("steps") or [])[:limit]:
        if not isinstance(row, dict):
            continue
        lines.append(
            "  - step={step_name} rows={baseline_count}->{candidate_count} "
            "p95_delta_ms={p95_delta_ms} max_delta_ms={max_delta_ms} status={trend_status}".format(
                step_name=row.get("step_name") or "unknown_step",
                baseline_count=int(row.get("baseline_count") or 0),
                candidate_count=int(row.get("candidate_count") or 0),
                p95_delta_ms=_format_ms_text(row.get("p95_delta_ms")),
                max_delta_ms=_format_ms_text(row.get("max_delta_ms")),
                trend_status=row.get("trend_status") or "unknown",
            )
        )
    return lines


def _text_environment_summary(summary: Dict[str, Any], *, limit: int) -> List[str]:
    lines = ["Environment Summary"]
    if not isinstance(summary, dict) or summary.get("status") == "empty":
        lines.append("  - no environment rows found")
        return lines
    env_counts = summary.get("env_counts") if isinstance(summary.get("env_counts"), dict) else {}
    lines.append(
        "  - rows={rows} envs={envs} native_retry_fingerprints={fingerprints}".format(
            rows=int(summary.get("step_row_count") or 0),
            envs=len(env_counts),
            fingerprints=len(summary.get("native_retry_env_fingerprints") or []),
        )
    )
    for env_name, count in list(env_counts.items())[:limit]:
        lines.append(f"  - env={env_name} rows={count}")
    for row in (summary.get("native_retry_env_fingerprints") or [])[:limit]:
        if not isinstance(row, dict):
            continue
        lines.append(
            "  - native_retry step={step} family={family} fingerprint={fingerprint}".format(
                step=row.get("step_name") or "unknown_step",
                family=row.get("error_family") or "unknown",
                fingerprint=row.get("fingerprint") or "raw_available",
            )
        )
    return lines


def _text_optional_enrichment_coverage(coverage: Dict[str, Any], *, limit: int) -> List[str]:
    lines = ["Optional Enrichment Coverage"]
    if not isinstance(coverage, dict) or not coverage.get("steps"):
        lines.append("  - no optional step coverage rows found")
        return lines
    lines.append(
        "  - rows={rows} steps={steps} non_ok={non_ok}".format(
            rows=int(coverage.get("total_rows") or 0),
            steps=int(coverage.get("step_count") or 0),
            non_ok=int(coverage.get("non_ok_rows") or 0),
        )
    )
    for row in (coverage.get("steps") or [])[:limit]:
        if not isinstance(row, dict):
            continue
        lines.append(
            "  - step={step_name} rows={total_rows} ok={ok_count} skipped={skipped_count} "
            "errors={error_count} warnings={warning_count} emitted={embedding_emitted_count} scenes={scene_count}".format(
                step_name=row.get("step_name") or "unknown_step",
                total_rows=int(row.get("total_rows") or 0),
                ok_count=int(row.get("ok_count") or 0),
                skipped_count=int(row.get("skipped_count") or 0),
                error_count=int(row.get("error_count") or 0),
                warning_count=int(row.get("warning_count") or 0),
                embedding_emitted_count=int(row.get("embedding_emitted_count") or 0),
                scene_count=int(row.get("scene_count") or 0),
            )
        )
    return lines


def _text_optional_enrichment_coverage_delta(delta: Dict[str, Any], *, limit: int) -> List[str]:
    lines = ["Optional Enrichment Coverage Delta"]
    if not isinstance(delta, dict) or not delta.get("steps"):
        lines.append("  - no comparable optional enrichment coverage rows found")
        return lines
    lines.append(
        "  - status={status} baseline_rows={baseline} candidate_rows={candidate} baseline_non_ok={base_non_ok} candidate_non_ok={cand_non_ok}".format(
            status=delta.get("status") or "unknown",
            baseline=int(delta.get("baseline_total_rows") or 0),
            candidate=int(delta.get("candidate_total_rows") or 0),
            base_non_ok=int(delta.get("baseline_non_ok_rows") or 0),
            cand_non_ok=int(delta.get("candidate_non_ok_rows") or 0),
        )
    )
    for row in (delta.get("steps") or [])[:limit]:
        if not isinstance(row, dict):
            continue
        lines.append(
            "  - step={step_name} rows={baseline_total_rows}->{candidate_total_rows} "
            "non_ok_delta={non_ok_delta} emitted_delta={embedding_emitted_delta} status={trend_status}".format(
                step_name=row.get("step_name") or "unknown_step",
                baseline_total_rows=int(row.get("baseline_total_rows") or 0),
                candidate_total_rows=int(row.get("candidate_total_rows") or 0),
                non_ok_delta=int(row.get("non_ok_delta") or 0),
                embedding_emitted_delta=int(row.get("embedding_emitted_delta") or 0),
                trend_status=row.get("trend_status") or "unknown",
            )
        )
    return lines


def write_markdown_report(report: Dict[str, Any], output_dir: str | Path | None = None) -> Path:
    """Write a deterministic markdown operator artifact for a report or comparison."""

    out_dir = _resolve_output_dir(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = _markdown_filename(report)
    path = out_dir / name
    text = render_markdown_report(report)
    path.write_text(text, encoding="utf-8")
    return path


def write_json_report_file(report: Dict[str, Any], output_dir: str | Path | None = None) -> Path:
    """Write a durable JSON report artifact with the existing report shape."""

    out_dir = _resolve_output_dir(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / _json_filename(report)
    payload = _portable_artifact_payload(report, output_dir=out_dir)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def update_report_index(output_dir: str | Path | None = None) -> Dict[str, Any]:
    """Rebuild the durable report index from artifacts under the output directory."""

    out_dir = _resolve_output_dir(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    entries_by_id: Dict[str, Dict[str, Any]] = {}
    warnings: List[str] = []

    for json_path in sorted(out_dir.glob("*.json"), key=lambda p: p.name):
        if json_path.name == _INDEX_FILENAME:
            continue
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            warnings.append(f"malformed_json:{json_path.name}:{type(exc).__name__}:{exc}")
            continue
        if not isinstance(payload, dict):
            warnings.append(f"malformed_json:{json_path.name}:root_not_object")
            continue
        entry = _index_entry_from_report(payload, json_path=json_path, output_dir=out_dir)
        entries_by_id.setdefault(entry["report_id"], {}).update(entry)

    for md_path in sorted(out_dir.glob("*.md"), key=lambda p: p.name):
        report_id = md_path.stem
        entry = entries_by_id.setdefault(report_id, _index_entry_from_markdown_path(md_path, output_dir=out_dir))
        entry["markdown_path"] = _artifact_path_text(md_path, output_dir=out_dir)
        if not entry.get("created_or_updated_at"):
            entry["created_or_updated_at"] = _file_mtime_utc(md_path)

    for report_id, entry in entries_by_id.items():
        has_json = bool(entry.get("json_path"))
        has_markdown = bool(entry.get("markdown_path"))
        if has_json and has_markdown:
            entry["artifact_status"] = "complete"
        elif has_json:
            entry["artifact_status"] = "json_only"
        elif has_markdown:
            entry["artifact_status"] = "markdown_only"
            warnings.append(f"markdown_only_without_json:{report_id}")
        else:
            entry["artifact_status"] = "missing"

    reports = [entries_by_id[key] for key in sorted(entries_by_id)]
    index = {
        "index": {
            "name": "control_recurrence_index",
            "version": "0.2.0",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "output_dir": _artifact_path_text(out_dir, output_dir=out_dir),
        },
        "reports": reports,
        "warnings": warnings,
    }
    index_path = out_dir / _INDEX_FILENAME
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return index


def report_index_path(output_dir: str | Path | None = None) -> Path:
    return _resolve_output_dir(output_dir) / _INDEX_FILENAME


def read_report_index(output_dir: str | Path | None = None) -> Dict[str, Any]:
    """Read a previously written recurrence report index without regenerating reports."""

    out_dir = _resolve_output_dir(output_dir)
    index_path = out_dir / _INDEX_FILENAME
    if not index_path.is_file():
        return {
            "index": {
                "name": "control_recurrence_index",
                "version": "0.2.0",
                "generated_at_utc": None,
                "output_dir": _artifact_path_text(out_dir, output_dir=out_dir),
            },
            "reports": [],
            "warnings": [f"index_missing:{_INDEX_FILENAME}"],
        }
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "index": {
                "name": "control_recurrence_index",
                "version": "0.2.0",
                "generated_at_utc": None,
                "output_dir": _artifact_path_text(out_dir, output_dir=out_dir),
            },
            "reports": [],
            "warnings": [f"index_malformed:{type(exc).__name__}:{exc}"],
        }
    if not isinstance(payload, dict):
        return {
            "index": {
                "name": "control_recurrence_index",
                "version": "0.2.0",
                "generated_at_utc": None,
                "output_dir": _artifact_path_text(out_dir, output_dir=out_dir),
            },
            "reports": [],
            "warnings": ["index_malformed:root_not_object"],
        }
    payload.setdefault("reports", [])
    payload.setdefault("warnings", [])
    return payload


def render_report_index(index: Dict[str, Any]) -> str:
    """Render a concise human-readable report index."""

    reports = index.get("reports") if isinstance(index, dict) else []
    warnings = index.get("warnings") if isinstance(index, dict) else []
    lines = [
        "GoodQ Control Recurrence Report Index",
        "====================================",
        "Mode: read-only observability listing",
        f"Reports: {len(reports or [])}",
    ]
    if not reports:
        lines.append("")
        lines.append("No control recurrence reports indexed.")
    for entry in reports or []:
        if not isinstance(entry, dict):
            continue
        label = entry.get("report_id") or "unknown"
        report_type = entry.get("report_type") or "unknown"
        status = entry.get("recommendation_status") or "unknown"
        category = entry.get("highest_category") or "none"
        signals = int(entry.get("total_signals") or 0)
        artifact_status = entry.get("artifact_status") or "unknown"
        lines.append("")
        lines.append(f"- {label}")
        lines.append(
            f"  type={report_type} recommendation={status} highest_category={category} "
            f"signals={signals} artifacts={artifact_status}"
        )
        if entry.get("markdown_path"):
            lines.append(f"  markdown={entry.get('markdown_path')}")
        if entry.get("json_path"):
            lines.append(f"  json={entry.get('json_path')}")
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in warnings:
            lines.append(f"  - {warning}")
    return "\n".join(lines)


def render_markdown_report(report: Dict[str, Any]) -> str:
    report_meta = report.get("report") if isinstance(report, dict) else {}
    if isinstance(report_meta, dict) and report_meta.get("name") == "control_recurrence_comparison":
        return _render_markdown_comparison(report)
    return _render_markdown_single(report)


def _render_markdown_single(report: Dict[str, Any]) -> str:
    meta = report.get("report") if isinstance(report, dict) else {}
    scope = report.get("scope") if isinstance(report, dict) else {}
    recommendation = report.get("recommendation") if isinstance(report, dict) else {}
    classification = report.get("recurrence_classification") if isinstance(report, dict) else {}
    recovery = report.get("recovered_vs_unrecovered_failures") if isinstance(report, dict) else {}
    health = report.get("phase6_qdrant_truth") if isinstance(report, dict) else {}
    latency = report.get("step_latency_summary") if isinstance(report, dict) else {}
    environment_summary = report.get("environment_summary") if isinstance(report, dict) else {}
    optional_coverage = report.get("optional_enrichment_coverage") if isinstance(report, dict) else {}
    run_id = _single_report_run_id(report)

    lines: List[str] = []
    lines.append("# GoodQ Control Recurrence Report")
    lines.append("")
    lines.append(f"- Generated at: `{_md_text(meta.get('generated_at_utc'))}`")
    lines.append(f"- Run ID: `{_md_text(run_id)}`")
    lines.append("- Mode: `read_only_observability`")
    lines.append("")
    lines.append("## Run")
    lines.append(f"- Run root(s): {_md_join_code_paths(scope.get('run_roots') or [])}")
    lines.append(f"- Episodes: `{int(scope.get('episodes') or 0)}`")
    lines.append(f"- Signals: `{int(scope.get('signals') or 0)}`")
    step_scope = scope.get("step_run_scope") if isinstance(scope.get("step_run_scope"), dict) else {}
    if step_scope:
        lines.append(f"- Step run strict run_id filter: `{str(bool(step_scope.get('strict_run_id_filter_applied'))).lower()}`")
        lines.append(f"- Step run limited scope warning: `{str(bool(step_scope.get('limited_run_id_scope'))).lower()}`")
        lines.append(f"- Excluded run IDs: `{len(step_scope.get('excluded_run_ids') or {})}`")
    lines.append("")
    lines.extend(_markdown_recommendation(recommendation, classification.get("highest_category")))
    lines.append("")
    lines.extend(_markdown_category_counts(classification))
    lines.append("")
    lines.extend(_markdown_step_latency_summary(latency))
    lines.append("")
    lines.extend(_markdown_environment_summary(environment_summary))
    lines.append("")
    lines.extend(_markdown_optional_enrichment_coverage(optional_coverage))
    lines.append("")
    lines.extend(_markdown_recovery_counts(recovery))
    lines.append("")
    lines.extend(_markdown_phase6_health(health))
    lines.append("")
    lines.extend(_markdown_qdrant_health(health))
    lines.append("")
    lines.extend(_markdown_top_families(report.get("top_repeated_failure_families") or []))
    lines.append("")
    lines.extend(_markdown_blocking_signals(classification))
    lines.append("")
    lines.extend(_markdown_read_only_disclaimer())
    return "\n".join(lines).rstrip() + "\n"


def _render_markdown_comparison(comparison: Dict[str, Any]) -> str:
    meta = comparison.get("report") if isinstance(comparison, dict) else {}
    baseline = comparison.get("baseline") if isinstance(comparison, dict) else {}
    candidate = comparison.get("candidate") if isinstance(comparison, dict) else {}
    recommendation = comparison.get("recommendation") if isinstance(comparison, dict) else {}
    delta = comparison.get("delta") if isinstance(comparison, dict) else {}
    total = delta.get("total_recurrence_signals") if isinstance(delta, dict) else {}
    recovery = delta.get("recovery_counts") if isinstance(delta, dict) else {}
    category_counts = delta.get("category_counts") if isinstance(delta, dict) else {}
    latency_delta = delta.get("step_latency_delta") if isinstance(delta, dict) else {}
    coverage_delta = delta.get("optional_enrichment_coverage_delta") if isinstance(delta, dict) else {}
    phase6 = delta.get("phase6_health_delta") if isinstance(delta, dict) else {}
    qdrant = delta.get("qdrant_health_delta") if isinstance(delta, dict) else {}

    lines: List[str] = []
    lines.append("# GoodQ Control Recurrence Comparison")
    lines.append("")
    lines.append(f"- Generated at: `{_md_text(meta.get('generated_at_utc'))}`")
    lines.append(f"- Baseline run ID: `{_md_text(baseline.get('run_id'))}`")
    lines.append(f"- Candidate run ID: `{_md_text(candidate.get('run_id'))}`")
    lines.append("- Mode: `read_only_observability_comparison`")
    lines.append("")
    lines.append("## Runs")
    lines.append(f"- Baseline: `{_md_text(baseline.get('run_id'))}`")
    lines.append(f"- Candidate: `{_md_text(candidate.get('run_id'))}`")
    lines.append(
        "- Total recurrence signals: "
        f"`{int(total.get('baseline') or 0)}` -> `{int(total.get('candidate') or 0)}` "
        f"(delta `{int(total.get('delta') or 0)}`)"
    )
    lines.append("")
    lines.extend(_markdown_recommendation(recommendation, recommendation.get("highest_category")))
    lines.append("")
    lines.append("## Category Counts")
    lines.append("| Category | Baseline Families | Candidate Families | Family Delta | Baseline Signals | Candidate Signals | Signal Delta |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for category in _CATEGORY_ORDER:
        row = category_counts.get(category) if isinstance(category_counts, dict) else {}
        lines.append(
            f"| {_md_cell(category)} | {int(row.get('baseline_family_count') or 0)} | "
            f"{int(row.get('candidate_family_count') or 0)} | {int(row.get('family_delta') or 0)} | "
            f"{int(row.get('baseline_signal_count') or 0)} | {int(row.get('candidate_signal_count') or 0)} | "
            f"{int(row.get('signal_delta') or 0)} |"
        )
    lines.append("")
    lines.extend(_markdown_recovery_delta_counts(recovery))
    lines.append("")
    lines.extend(_markdown_step_latency_delta(latency_delta))
    lines.append("")
    lines.extend(_markdown_optional_enrichment_coverage_delta(coverage_delta))
    lines.append("")
    lines.extend(_markdown_phase6_delta(phase6))
    lines.append("")
    lines.extend(_markdown_qdrant_delta(qdrant))
    lines.append("")
    lines.extend(_markdown_comparison_family_changes(delta))
    lines.append("")
    lines.extend(_markdown_top_families(_candidate_family_rows_from_comparison(comparison)))
    lines.append("")
    lines.extend(_markdown_blocking_signals(candidate.get("recurrence_classification") or {}))
    lines.append("")
    lines.extend(_markdown_read_only_disclaimer())
    return "\n".join(lines).rstrip() + "\n"


def _markdown_read_only_disclaimer() -> List[str]:
    return [
        "## Read-Only Disclaimer",
        "This operator artifact is read-only. It was generated from persisted runtime truth surfaces only: `step_runs.jsonl`, `experiment_log.json`, `scene_ingest_results.json`, `scene_manifest.json`, and `temporal_index.json`.",
        "",
        "It does not activate ControlAgent, enable healing, mutate configs, touch `cli/run_ingestion.py`, use LLMs, or recommend broad reruns as the first action.",
    ]


def _markdown_recommendation(recommendation: Dict[str, Any], highest_category: Any) -> List[str]:
    lines = ["## Recommendation"]
    lines.append(f"- Status: `{_md_text(str(recommendation.get('status') or 'unknown').upper())}`")
    lines.append(f"- Highest category: `{_md_text(highest_category or recommendation.get('highest_category') or 'none')}`")
    reasons = recommendation.get("reasons") if isinstance(recommendation, dict) else []
    if reasons:
        lines.append("- Reasons:")
        for reason in reasons:
            lines.append(f"  - {_md_text(reason)}")
    else:
        lines.append("- Reasons: none")
    return lines


def _markdown_category_counts(classification: Dict[str, Any]) -> List[str]:
    lines = ["## Category Counts"]
    family_counts = classification.get("family_counts") if isinstance(classification, dict) else {}
    signal_counts = classification.get("signal_counts") if isinstance(classification, dict) else {}
    lines.append("| Category | Families | Signals |")
    lines.append("|---|---:|---:|")
    for category in _CATEGORY_ORDER:
        lines.append(
            f"| {_md_cell(category)} | {int((family_counts or {}).get(category) or 0)} | "
            f"{int((signal_counts or {}).get(category) or 0)} |"
        )
    return lines


def _markdown_recovery_counts(recovery: Dict[str, Any]) -> List[str]:
    lines = ["## Recovered / Unrecovered / Skipped Counts"]
    lines.append("| Outcome | Count |")
    lines.append("|---|---:|")
    for key in ("recovered", "unrecovered", "skipped", "unknown"):
        lines.append(f"| {_md_cell(key)} | {int((recovery or {}).get(key) or 0)} |")
    return lines


def _markdown_step_latency_summary(latency: Dict[str, Any]) -> List[str]:
    lines = ["## Step Latency Summary"]
    if not isinstance(latency, dict) or not latency.get("duration_row_count"):
        lines.append("No step duration rows found.")
        return lines
    lines.append(f"- Source: `{_md_text(latency.get('source'))}`")
    lines.append(f"- Duration rows: `{int(latency.get('duration_row_count') or 0)}`")
    lines.append(f"- Timeout boundary ms: `{int(latency.get('timeout_boundary_ms') or 0)}`")
    lines.append(f"- Slow outlier threshold ms: `{int(latency.get('slow_outlier_threshold_ms') or 0)}`")
    lines.append(f"- Timeout boundary exceedances: `{int(latency.get('timeout_boundary_exceedance_count') or 0)}`")
    lines.append("")
    lines.append("| Step | Rows | OK | Non-OK | p50 ms | p95 ms | Max ms | Slow Outliers | Timeout Exceedances |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in (latency.get("steps") or [])[:12]:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {_md_cell(row.get('step_name'))} | {int(row.get('count') or 0)} | "
            f"{int(row.get('ok_count') or 0)} | {int(row.get('non_ok_count') or 0)} | "
            f"{_format_ms_cell(row.get('p50_ms'))} | {_format_ms_cell(row.get('p95_ms'))} | "
            f"{_format_ms_cell(row.get('max_ms'))} | {int(row.get('slow_outlier_count') or 0)} | "
            f"{int(row.get('timeout_boundary_exceedance_count') or 0)} |"
        )
    return lines


def _markdown_environment_summary(summary: Dict[str, Any]) -> List[str]:
    lines = ["## Environment Summary"]
    if not isinstance(summary, dict) or summary.get("status") == "empty":
        lines.append("No environment rows found.")
        return lines
    env_counts = summary.get("env_counts") if isinstance(summary.get("env_counts"), dict) else {}
    lines.append(f"- Source: `{_md_text(summary.get('source'))}`")
    lines.append(f"- Step rows: `{int(summary.get('step_row_count') or 0)}`")
    lines.append(f"- Native retry fingerprints: `{len(summary.get('native_retry_env_fingerprints') or [])}`")
    lines.append("")
    lines.append("| Environment | Rows |")
    lines.append("|---|---:|")
    for env_name, count in env_counts.items():
        lines.append(f"| {_md_cell(env_name)} | {int(count or 0)} |")
    return lines


def _markdown_optional_enrichment_coverage(coverage: Dict[str, Any]) -> List[str]:
    lines = ["## Optional Enrichment Coverage"]
    if not isinstance(coverage, dict) or not coverage.get("steps"):
        lines.append("No optional step coverage rows found.")
        return lines
    lines.append(f"- Source: `{_md_text(coverage.get('source'))}`")
    lines.append(f"- Total rows: `{int(coverage.get('total_rows') or 0)}`")
    lines.append(f"- Non-OK rows: `{int(coverage.get('non_ok_rows') or 0)}`")
    lines.append("")
    lines.append("| Step | Rows | OK | Skipped | Errors | Warnings | Emitted | Scenes |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in (coverage.get("steps") or [])[:12]:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {_md_cell(row.get('step_name'))} | {int(row.get('total_rows') or 0)} | "
            f"{int(row.get('ok_count') or 0)} | {int(row.get('skipped_count') or 0)} | "
            f"{int(row.get('error_count') or 0)} | {int(row.get('warning_count') or 0)} | "
            f"{int(row.get('embedding_emitted_count') or 0)} | {int(row.get('scene_count') or 0)} |"
        )
    return lines


def _markdown_recovery_delta_counts(recovery: Dict[str, Any]) -> List[str]:
    lines = ["## Recovered / Unrecovered / Skipped Counts"]
    lines.append("| Outcome | Baseline | Candidate | Delta |")
    lines.append("|---|---:|---:|---:|")
    for key in ("recovered", "unrecovered", "skipped", "unknown"):
        row = recovery.get(key) if isinstance(recovery, dict) else {}
        lines.append(
            f"| {_md_cell(key)} | {int(row.get('baseline_count') or 0)} | "
            f"{int(row.get('candidate_count') or 0)} | {int(row.get('delta') or 0)} |"
        )
    return lines


def _markdown_step_latency_delta(delta: Dict[str, Any]) -> List[str]:
    lines = ["## Step Latency Delta"]
    if not isinstance(delta, dict) or not delta.get("steps"):
        lines.append("No comparable step latency rows found.")
        return lines
    lines.append(f"- Status: `{_md_text(delta.get('status') or 'unknown')}`")
    lines.append(f"- Baseline duration rows: `{int(delta.get('baseline_duration_row_count') or 0)}`")
    lines.append(f"- Candidate duration rows: `{int(delta.get('candidate_duration_row_count') or 0)}`")
    lines.append("")
    lines.append("| Step | Baseline Rows | Candidate Rows | p95 Delta ms | Max Delta ms | Status |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for row in (delta.get("steps") or [])[:12]:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {_md_cell(row.get('step_name'))} | {int(row.get('baseline_count') or 0)} | "
            f"{int(row.get('candidate_count') or 0)} | {_format_ms_cell(row.get('p95_delta_ms'))} | "
            f"{_format_ms_cell(row.get('max_delta_ms'))} | {_md_cell(row.get('trend_status'))} |"
        )
    return lines


def _markdown_optional_enrichment_coverage_delta(delta: Dict[str, Any]) -> List[str]:
    lines = ["## Optional Enrichment Coverage Delta"]
    if not isinstance(delta, dict) or not delta.get("steps"):
        lines.append("No comparable optional enrichment coverage rows found.")
        return lines
    lines.append(f"- Status: `{_md_text(delta.get('status') or 'unknown')}`")
    lines.append(f"- Baseline rows: `{int(delta.get('baseline_total_rows') or 0)}`")
    lines.append(f"- Candidate rows: `{int(delta.get('candidate_total_rows') or 0)}`")
    lines.append("")
    lines.append("| Step | Baseline Rows | Candidate Rows | Non-OK Delta | Emitted Delta | Status |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for row in (delta.get("steps") or [])[:12]:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {_md_cell(row.get('step_name'))} | {int(row.get('baseline_total_rows') or 0)} | "
            f"{int(row.get('candidate_total_rows') or 0)} | {int(row.get('non_ok_delta') or 0)} | "
            f"{int(row.get('embedding_emitted_delta') or 0)} | {_md_cell(row.get('trend_status'))} |"
        )
    return lines


def _markdown_phase6_health(health: Dict[str, Any]) -> List[str]:
    lines = ["## Phase 6 Health"]
    lines.append(f"- Status: `{_md_text((health or {}).get('status') or 'unknown')}`")
    lines.append(f"- Healthy: `{bool((health or {}).get('healthy'))}`")
    lines.append(f"- Episodes healthy: `{int((health or {}).get('episodes_healthy') or 0)}` / `{int((health or {}).get('episodes_total') or 0)}`")
    return lines


def _markdown_qdrant_health(health: Dict[str, Any]) -> List[str]:
    episodes = health.get("episodes") if isinstance(health, dict) else []
    total = len(episodes or [])
    healthy = sum(1 for row in episodes or [] if isinstance(row, dict) and row.get("qdrant_ok") is True)
    status = "healthy" if total > 0 and healthy == total else ("unknown" if total == 0 else "degraded")
    lines = ["## Qdrant Health"]
    lines.append(f"- Status: `{status}`")
    lines.append(f"- Episodes healthy: `{healthy}` / `{total}`")
    return lines


def _markdown_phase6_delta(delta: Dict[str, Any]) -> List[str]:
    lines = ["## Phase 6 Health"]
    lines.append(f"- Status: `{_md_text((delta or {}).get('status') or 'unknown')}`")
    lines.append(
        f"- Healthy episodes: `{int((delta or {}).get('baseline_healthy_episodes') or 0)}` -> "
        f"`{int((delta or {}).get('candidate_healthy_episodes') or 0)}` "
        f"(delta `{int((delta or {}).get('delta_healthy_episodes') or 0)}`)"
    )
    return lines


def _markdown_qdrant_delta(delta: Dict[str, Any]) -> List[str]:
    lines = ["## Qdrant Health"]
    lines.append(f"- Status: `{_md_text((delta or {}).get('status') or 'unknown')}`")
    lines.append(
        f"- Healthy episodes: `{int((delta or {}).get('baseline_healthy_episodes') or 0)}` -> "
        f"`{int((delta or {}).get('candidate_healthy_episodes') or 0)}` "
        f"(delta `{int((delta or {}).get('delta_healthy_episodes') or 0)}`)"
    )
    return lines


def _markdown_top_families(families: Sequence[Dict[str, Any]]) -> List[str]:
    lines = ["## Top Recurrence Families"]
    if not families:
        lines.append("No recurrence families found.")
        return lines
    lines.append("| Family | Count | Category | Operator Hints | Inspection Targets |")
    lines.append("|---|---:|---|---|---|")
    for row in families:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {_md_cell(row.get('error_family'))} | {int(row.get('count') or 0)} | "
            f"{_md_cell(row.get('category') or 'unknown')} | "
            f"{_md_cell('; '.join(row.get('operator_hints') or []))} | "
            f"{_md_cell('; '.join(row.get('inspection_targets') or []))} |"
        )
    return lines


def _markdown_comparison_family_changes(delta: Dict[str, Any]) -> List[str]:
    lines = ["## New / Increased / Resolved Families"]
    new_families = delta.get("new_error_families") if isinstance(delta, dict) else []
    resolved = delta.get("resolved_error_families") if isinstance(delta, dict) else []
    increased = delta.get("increased_error_families") if isinstance(delta, dict) else []
    lines.append("### New Families")
    lines.extend(_markdown_bullets(new_families))
    lines.append("")
    lines.append("### Increased Families")
    if increased:
        lines.append("| Family | Category | Baseline | Candidate | Delta |")
        lines.append("|---|---|---:|---:|---:|")
        for row in increased:
            if isinstance(row, dict):
                lines.append(
                    f"| {_md_cell(row.get('error_family'))} | {_md_cell(row.get('category'))} | "
                    f"{int(row.get('baseline_count') or 0)} | {int(row.get('candidate_count') or 0)} | "
                    f"{int(row.get('delta') or 0)} |"
                )
    else:
        lines.append("- none")
    lines.append("")
    lines.append("### Resolved Families")
    lines.extend(_markdown_bullets(resolved))
    return lines


def _markdown_blocking_signals(classification: Dict[str, Any]) -> List[str]:
    lines = ["## Blocking Signals"]
    families = [
        item
        for item in (classification.get("families") or [])
        if isinstance(item, dict) and item.get("category") == "blocking"
    ]
    if not families:
        lines.append("No blocking recurrence families found.")
        return lines
    lines.append("| Family | Count | Operator Hints | Inspection Targets |")
    lines.append("|---|---:|---|---|")
    for item in families:
        lines.append(
            f"| {_md_cell(item.get('error_family'))} | {int(item.get('count') or 0)} | "
            f"{_md_cell('; '.join(item.get('operator_hints') or []))} | "
            f"{_md_cell('; '.join(item.get('inspection_targets') or []))} |"
        )
    return lines


def _candidate_family_rows_from_comparison(comparison: Dict[str, Any]) -> List[Dict[str, Any]]:
    classification = _nested_get(comparison, ("candidate", "recurrence_classification"))
    if not isinstance(classification, dict):
        return []
    rows = []
    for item in classification.get("families") or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "error_family": item.get("error_family"),
                "count": int(item.get("count") or 0),
                "category": item.get("category"),
                "operator_hints": item.get("operator_hints") or [],
                "inspection_targets": item.get("inspection_targets") or [],
            }
        )
    rows.sort(key=lambda row: (-int(row.get("count") or 0), str(row.get("error_family"))))
    return rows


def _markdown_filename(report: Dict[str, Any]) -> str:
    return f"{_artifact_stem(report)}.md"


def _json_filename(report: Dict[str, Any]) -> str:
    return f"{_artifact_stem(report)}.json"


def _artifact_stem(report: Dict[str, Any]) -> str:
    meta = report.get("report") if isinstance(report, dict) else {}
    if isinstance(meta, dict) and meta.get("name") == "control_recurrence_comparison":
        baseline_id = _md_filename_part(_nested_get(report, ("baseline", "run_id")) or "baseline")
        candidate_id = _md_filename_part(_nested_get(report, ("candidate", "run_id")) or "candidate")
        return f"{baseline_id}__vs__{candidate_id}"
    return _md_filename_part(_single_report_run_id(report))


def _single_report_run_id(report: Dict[str, Any]) -> str:
    run_roots = _nested_get(report, ("scope", "run_roots"))
    if isinstance(run_roots, list) and run_roots:
        return Path(str(run_roots[0])).name
    runtime_ids = _nested_get(report, ("scope", "runtime_run_ids"))
    if isinstance(runtime_ids, list) and runtime_ids:
        return str(runtime_ids[0])
    return "control_recurrence_report"


def _md_filename_part(value: Any) -> str:
    text = str(value or "unknown").strip() or "unknown"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._") or "unknown"


def _md_join_code(values: Sequence[Any]) -> str:
    if not values:
        return "`none`"
    return ", ".join(f"`{_md_text(value)}`" for value in values)


def _md_join_code_paths(values: Sequence[Any]) -> str:
    if not values:
        return "`none`"
    return ", ".join(f"`{_md_path_text(value)}`" for value in values)


def _markdown_bullets(values: Sequence[Any]) -> List[str]:
    if not values:
        return ["- none"]
    return [f"- `{_md_text(value)}`" for value in values]


def _md_cell(value: Any) -> str:
    return _md_text(value).replace("|", "\\|").replace("\n", " ")


def _md_text(value: Any) -> str:
    if value is None:
        return "none"
    return str(value)


def _md_path_text(value: Any) -> str:
    text = _md_text(value)
    try:
        path = Path(text)
        if path.is_absolute():
            return str(path.relative_to(_REPO_ROOT)).replace("\\", "/")
    except Exception:
        return text
    return text


def _resolve_output_dir(output_dir: str | Path | None = None) -> Path:
    return Path(output_dir) if output_dir is not None else _DEFAULT_MARKDOWN_OUTPUT_DIR


def _portable_artifact_payload(value: Any, *, output_dir: Path) -> Any:
    if isinstance(value, dict):
        return {str(key): _portable_artifact_payload(item, output_dir=output_dir) for key, item in value.items()}
    if isinstance(value, list):
        return [_portable_artifact_payload(item, output_dir=output_dir) for item in value]
    if isinstance(value, tuple):
        return [_portable_artifact_payload(item, output_dir=output_dir) for item in value]
    if isinstance(value, str):
        return _portable_path_text(value, output_dir=output_dir)
    return value


def _portable_path_text(value: str, *, output_dir: Path) -> str:
    if not _looks_like_absolute_path(value):
        return value
    path = Path(value)
    for base in (output_dir, _REPO_ROOT):
        try:
            return str(path.relative_to(base)).replace("\\", "/")
        except Exception:
            continue
    return "external/" + "/".join(part for part in path.parts[1:] if part)


def _looks_like_absolute_path(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:[\\/]", value)) or value.startswith("\\\\")


def _artifact_path_text(path: Path, *, output_dir: Path) -> str:
    try:
        return str(path.relative_to(output_dir)).replace("\\", "/")
    except Exception:
        try:
            return str(path.relative_to(_REPO_ROOT)).replace("\\", "/")
        except Exception:
            return _portable_path_text(str(path), output_dir=output_dir)


def _index_entry_from_report(report: Dict[str, Any], *, json_path: Path, output_dir: Path) -> Dict[str, Any]:
    report_type = _report_type(report)
    report_id = _report_id(report)
    recommendation = report.get("recommendation") if isinstance(report.get("recommendation"), dict) else {}
    entry: Dict[str, Any] = {
        "report_type": report_type,
        "report_id": report_id,
        "json_path": _artifact_path_text(json_path, output_dir=output_dir),
        "artifact_status": "json_only",
        "recommendation_status": recommendation.get("status") or "unknown",
        "highest_category": _index_highest_category(report),
        "total_signals": _index_total_signals(report),
        "blocking_signal_count": _index_blocking_signal_count(report),
        "phase6_health_summary": _index_phase6_health_summary(report),
        "qdrant_health_summary": _index_qdrant_health_summary(report),
        "created_or_updated_at": _nested_get(report, ("report", "generated_at_utc")) or _file_mtime_utc(json_path),
    }
    if report_type == "comparison":
        entry["baseline_run_id"] = _nested_get(report, ("baseline", "run_id"))
        entry["candidate_run_id"] = _nested_get(report, ("candidate", "run_id"))
    else:
        entry["run_id"] = _single_report_run_id(report)
    md_path = json_path.with_suffix(".md")
    if md_path.is_file():
        entry["markdown_path"] = _artifact_path_text(md_path, output_dir=output_dir)
        entry["artifact_status"] = "complete"
    return entry


def _index_entry_from_markdown_path(path: Path, *, output_dir: Path) -> Dict[str, Any]:
    report_id = path.stem
    entry: Dict[str, Any] = {
        "report_type": "comparison" if "__vs__" in report_id else "single_run",
        "report_id": report_id,
        "markdown_path": _artifact_path_text(path, output_dir=output_dir),
        "artifact_status": "markdown_only",
        "recommendation_status": "unknown",
        "highest_category": "unknown",
        "total_signals": 0,
        "blocking_signal_count": 0,
        "phase6_health_summary": {"status": "unknown"},
        "qdrant_health_summary": {"status": "unknown"},
        "created_or_updated_at": _file_mtime_utc(path),
    }
    if entry["report_type"] == "comparison":
        baseline, _, candidate = report_id.partition("__vs__")
        entry["baseline_run_id"] = baseline or None
        entry["candidate_run_id"] = candidate or None
    else:
        entry["run_id"] = report_id
    return entry


def _report_type(report: Dict[str, Any]) -> str:
    meta = report.get("report") if isinstance(report, dict) else {}
    if isinstance(meta, dict) and meta.get("name") == "control_recurrence_comparison":
        return "comparison"
    return "single_run"


def _report_id(report: Dict[str, Any]) -> str:
    return _artifact_stem(report)


def _index_highest_category(report: Dict[str, Any]) -> str:
    value = _nested_get(report, ("recommendation", "highest_category"))
    if value:
        return str(value)
    value = _nested_get(report, ("recurrence_classification", "highest_category"))
    if value:
        return str(value)
    value = _nested_get(report, ("candidate", "recurrence_classification", "highest_category"))
    return str(value or "none")


def _index_total_signals(report: Dict[str, Any]) -> int:
    if _report_type(report) == "comparison":
        return int(_nested_get(report, ("candidate", "signals")) or 0)
    return int(_nested_get(report, ("scope", "signals")) or 0)


def _index_blocking_signal_count(report: Dict[str, Any]) -> int:
    if _report_type(report) == "comparison":
        return int(_nested_get(report, ("candidate", "recurrence_classification", "signal_counts", "blocking")) or 0)
    return int(_nested_get(report, ("recurrence_classification", "signal_counts", "blocking")) or 0)


def _index_phase6_health_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    if _report_type(report) == "comparison":
        delta = _nested_get(report, ("delta", "phase6_health_delta"))
        if isinstance(delta, dict):
            return {
                "status": delta.get("status") or "unknown",
                "baseline_healthy_episodes": int(delta.get("baseline_healthy_episodes") or 0),
                "candidate_healthy_episodes": int(delta.get("candidate_healthy_episodes") or 0),
                "delta_healthy_episodes": int(delta.get("delta_healthy_episodes") or 0),
            }
    health = report.get("phase6_qdrant_truth") if isinstance(report.get("phase6_qdrant_truth"), dict) else {}
    return {
        "status": health.get("status") or "unknown",
        "healthy": bool(health.get("healthy")),
        "episodes_healthy": int(health.get("episodes_healthy") or 0),
        "episodes_total": int(health.get("episodes_total") or 0),
    }


def _index_qdrant_health_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    if _report_type(report) == "comparison":
        delta = _nested_get(report, ("delta", "qdrant_health_delta"))
        if isinstance(delta, dict):
            return {
                "status": delta.get("status") or "unknown",
                "baseline_healthy_episodes": int(delta.get("baseline_healthy_episodes") or 0),
                "candidate_healthy_episodes": int(delta.get("candidate_healthy_episodes") or 0),
                "delta_healthy_episodes": int(delta.get("delta_healthy_episodes") or 0),
            }
    health = report.get("phase6_qdrant_truth") if isinstance(report.get("phase6_qdrant_truth"), dict) else {}
    episodes = health.get("episodes") if isinstance(health, dict) else []
    total = len(episodes or [])
    healthy = sum(1 for row in episodes or [] if isinstance(row, dict) and row.get("qdrant_ok") is True)
    status = "healthy" if total > 0 and healthy == total else ("unknown" if total == 0 else "degraded")
    return {"status": status, "episodes_healthy": healthy, "episodes_total": total}


def _file_mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _comparison_run_summary(report: Dict[str, Any], *, label: str) -> Dict[str, Any]:
    scope = report.get("scope") if isinstance(report, dict) else {}
    health = report.get("phase6_qdrant_truth") if isinstance(report, dict) else {}
    run_roots = list(scope.get("run_roots") or []) if isinstance(scope, dict) else []
    return {
        "label": label,
        "run_id": Path(run_roots[0]).name if run_roots else None,
        "run_roots": run_roots,
        "episodes": int(scope.get("episodes") or 0) if isinstance(scope, dict) else 0,
        "signals": int(scope.get("signals") or 0) if isinstance(scope, dict) else 0,
        "error_families": _family_counts(report),
        "recovery_counts": _safe_int_map(report.get("recovered_vs_unrecovered_failures")),
        "recurrence_classification": report.get("recurrence_classification") or {},
        "recommendation": report.get("recommendation") or {},
        "operator_hints": report.get("operator_hints") or [],
        "inspection_targets": report.get("inspection_targets") or [],
        "step_latency_summary": report.get("step_latency_summary") or {},
        "environment_summary": report.get("environment_summary") or {},
        "optional_enrichment_coverage": report.get("optional_enrichment_coverage") or {},
        "phase6_qdrant_truth": {
            "status": health.get("status") if isinstance(health, dict) else "unknown",
            "healthy": bool(health.get("healthy")) if isinstance(health, dict) else False,
            "episodes_total": int(health.get("episodes_total") or 0) if isinstance(health, dict) else 0,
            "episodes_healthy": int(health.get("episodes_healthy") or 0) if isinstance(health, dict) else 0,
        },
    }


def _family_counts(report: Dict[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in report.get("top_repeated_failure_families") or []:
        if not isinstance(row, dict):
            continue
        family = _clean_str(row.get("error_family"))
        if not family:
            continue
        counts[family] = int(row.get("count") or 0)
    return dict(sorted(counts.items()))


def _merged_family_categories(baseline: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for report in (baseline, candidate):
        for row in report.get("top_repeated_failure_families") or []:
            if not isinstance(row, dict):
                continue
            family = _clean_str(row.get("error_family"))
            category = _clean_str(row.get("category"))
            if family and category:
                existing = merged.get(family)
                if existing is None or _CATEGORY_ORDER.get(category, 0) > _CATEGORY_ORDER.get(existing, 0):
                    merged[family] = category
    return merged


def _attach_delta_categories(delta_map: Dict[str, Dict[str, int]], category_by_key: Dict[str, str]) -> None:
    for key, row in delta_map.items():
        if isinstance(row, dict):
            category = category_by_key.get(key, "informational")
            row["category"] = category
            bundle = _operator_hint_bundle(
                {
                    "error_family": key,
                    "category": category,
                    "statuses": [],
                    "recovery_outcomes": {},
                }
            )
            row["operator_hints"] = bundle["operator_hints"]
            row["inspection_targets"] = bundle["inspection_targets"]


def _category_counts_delta(baseline: Any, candidate: Any) -> Dict[str, Dict[str, int]]:
    baseline_family = _safe_int_map(_nested_get(baseline, ("family_counts",)) if isinstance(baseline, dict) else {})
    candidate_family = _safe_int_map(_nested_get(candidate, ("family_counts",)) if isinstance(candidate, dict) else {})
    baseline_signal = _safe_int_map(_nested_get(baseline, ("signal_counts",)) if isinstance(baseline, dict) else {})
    candidate_signal = _safe_int_map(_nested_get(candidate, ("signal_counts",)) if isinstance(candidate, dict) else {})
    out: Dict[str, Dict[str, int]] = {}
    for category in _CATEGORY_ORDER:
        bf = int(baseline_family.get(category, 0))
        cf = int(candidate_family.get(category, 0))
        bs = int(baseline_signal.get(category, 0))
        cs = int(candidate_signal.get(category, 0))
        out[category] = {
            "baseline_family_count": bf,
            "candidate_family_count": cf,
            "family_delta": cf - bf,
            "baseline_signal_count": bs,
            "candidate_signal_count": cs,
            "signal_delta": cs - bs,
        }
    return out


def _signal_counts_by(report: Dict[str, Any], field: str) -> Dict[str, int]:
    counts: Counter[str] = Counter()
    for row in report.get("recurrence_summary") or []:
        if not isinstance(row, dict):
            continue
        key = _clean_str(row.get(field)) or "unknown"
        counts[key] += int(row.get("count") or 0)
    return dict(sorted(counts.items()))


def _episode_video_counts(report: Dict[str, Any]) -> Dict[str, int]:
    counts: Counter[str] = Counter()
    for row in report.get("recurrence_summary") or []:
        if not isinstance(row, dict):
            continue
        episode = _clean_str(row.get("episode")) or "unknown_episode"
        video_id = _clean_str(row.get("video_id")) or "unknown_video"
        counts[f"{episode}|{video_id}"] += int(row.get("count") or 0)
    return dict(sorted(counts.items()))


def _safe_int_map(value: Any) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, int] = {}
    for key, raw in value.items():
        if not isinstance(key, str):
            continue
        out[key] = int(raw or 0)
    return dict(sorted(out.items()))


def _count_delta_map(baseline: Dict[str, int], candidate: Dict[str, int]) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}
    for key in sorted(set(baseline) | set(candidate)):
        b = int(baseline.get(key, 0) or 0)
        c = int(candidate.get(key, 0) or 0)
        out[key] = {
            "baseline_count": b,
            "candidate_count": c,
            "delta": c - b,
        }
    return out


def _delta_rows(
    delta_map: Dict[str, Dict[str, int]],
    *,
    key_name: str = "error_family",
    category_by_key: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key, value in delta_map.items():
        if not isinstance(value, dict):
            continue
        row = {
            key_name: key,
            "baseline_count": int(value.get("baseline_count") or 0),
            "candidate_count": int(value.get("candidate_count") or 0),
            "delta": int(value.get("delta") or 0),
        }
        if category_by_key is not None:
            row["category"] = category_by_key.get(key, "informational")
        elif isinstance(value.get("category"), str):
            row["category"] = value.get("category")
        if isinstance(value.get("operator_hints"), list):
            row["operator_hints"] = value.get("operator_hints")
        if isinstance(value.get("inspection_targets"), list):
            row["inspection_targets"] = value.get("inspection_targets")
        rows.append(row)
    rows.sort(key=lambda row: (-abs(int(row["delta"])), str(row[key_name])))
    return rows


def _health_delta(baseline: Any, candidate: Any, dimension: str) -> Dict[str, Any]:
    baseline_rows = list(baseline.get("episodes") or []) if isinstance(baseline, dict) else []
    candidate_rows = list(candidate.get("episodes") or []) if isinstance(candidate, dict) else []
    baseline_good = [row for row in baseline_rows if _episode_dimension_healthy(row, dimension)]
    candidate_good = [row for row in candidate_rows if _episode_dimension_healthy(row, dimension)]
    baseline_bad = [row for row in baseline_rows if not _episode_dimension_healthy(row, dimension)]
    candidate_bad = [row for row in candidate_rows if not _episode_dimension_healthy(row, dimension)]
    delta = len(candidate_good) - len(baseline_good)
    regressed = bool(baseline_rows) and (len(candidate_bad) > 0 or delta < 0)
    improved = not regressed and delta > 0
    status = "regressed" if regressed else ("improved" if improved else "unchanged")
    return {
        "dimension": dimension,
        "baseline_status": baseline.get("status") if isinstance(baseline, dict) else "unknown",
        "candidate_status": candidate.get("status") if isinstance(candidate, dict) else "unknown",
        "baseline_healthy": bool(baseline.get("healthy")) if isinstance(baseline, dict) else False,
        "candidate_healthy": bool(candidate.get("healthy")) if isinstance(candidate, dict) else False,
        "baseline_episodes": len(baseline_rows),
        "candidate_episodes": len(candidate_rows),
        "baseline_healthy_episodes": len(baseline_good),
        "candidate_healthy_episodes": len(candidate_good),
        "delta_healthy_episodes": delta,
        "baseline_unhealthy_episodes": [_health_episode_label(row) for row in baseline_bad],
        "candidate_unhealthy_episodes": [_health_episode_label(row) for row in candidate_bad],
        "status": status,
    }


def _episode_dimension_healthy(row: Any, dimension: str) -> bool:
    if not isinstance(row, dict):
        return False
    if dimension == "phase6":
        return bool(row.get("phase6_complete") is True and row.get("phase6_harmonized") is True)
    if dimension == "qdrant":
        return bool(row.get("qdrant_ok") is True)
    return bool(row.get("healthy"))


def _health_episode_label(row: Dict[str, Any]) -> str:
    return _clean_str(row.get("episode")) or _clean_str(row.get("video_id")) or "unknown"


def _attach_family_categories(rows: List[Dict[str, Any]], health: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        category, reason = _classify_family_category(enriched, health)
        enriched["category"] = category
        enriched["category_reason"] = reason
        out.append(enriched)
    return out


def _attach_operator_hints_to_families(rows: Sequence[Dict[str, Any]]) -> None:
    for row in rows:
        if not isinstance(row, dict):
            continue
        bundle = _operator_hint_bundle(row)
        row["operator_hints"] = bundle["operator_hints"]
        row["inspection_targets"] = bundle["inspection_targets"]


def _operator_hint_bundle(row: Dict[str, Any]) -> Dict[str, List[str]]:
    family = _clean_str(row.get("error_family")) or "unknown"
    category = _clean_str(row.get("category")) or "informational"
    statuses = {str(status).lower() for status in (row.get("statuses") or [])}
    recovery = row.get("recovery_outcomes") if isinstance(row.get("recovery_outcomes"), dict) else {}

    hints: List[str] = []
    targets: List[str] = []

    if family in {"no_text", "too_short", "audio_silent"}:
        hints.append("No action unless count increases sharply or correlates with unhealthy Phase 6/Qdrant output.")
        targets.extend(["temporal_index.json segments", "scene_ingest_results.json modality_status", "phase6_qdrant_truth"])
    elif family == "insufficient_diverse_speech":
        hints.append("Confirm this remains informational by checking speaker_voice_signature_meta and final Phase 6/Qdrant health.")
        targets.extend(["speaker_voice_signature_meta", "phase6_qdrant_truth", "temporal_index.json segments"])
    elif family == "diarization_unavailable":
        hints.append(
            "Inspect WSL audio readiness, diarization_status, diarization_error, and whether speaker_count/dominant_speaker_id persisted."
        )
        targets.extend(
            [
                "WSL audio readiness",
                "diarization_status",
                "diarization_error",
                "speaker_count",
                "dominant_speaker_id",
                "temporal_index.json",
            ]
        )
    elif family in {"embedding_missing", "modality_degraded"} or family.startswith("embedding_skip:"):
        hints.append("Inspect modality_status, embedding meta fields, and qdrant_ok.")
        targets.extend(["modality_status", "embedding meta fields", "qdrant_ok", "scene_manifest.json", "temporal_index.json"])
    elif family.startswith("native_crash_retry:") or family.startswith("native_subprocess_crash:"):
        hints.append("Inspect affected step distribution, stderr/error tails, retry/fallback outcome, and whether final scene output survived.")
        targets.extend(
            [
                "step_runs.jsonl affected step distribution",
                "step_runs.jsonl error tails",
                "run.warnings",
                "recovery_outcome",
                "scene_ingest_results.json",
                "phase6_qdrant_truth",
            ]
        )
    elif "direct_env" in family or "backend_downgrade" in family or "backend_downgraded" in family:
        hints.append("Inspect fallback frequency, affected step, and whether recovery remained bounded.")
        targets.extend(["run.warnings", "audio_backend_events", "step_runs.jsonl", "recovery_outcome"])
    elif family == "missing_scene_manifest":
        hints.append("Inspect canonical processing path and run ledger; treat run as incomplete.")
        targets.extend(["processing/<episode>/video/scene_manifest.json", "experiment_log.json", "run ledger"])
    elif family == "missing_temporal_index":
        hints.append("Inspect Phase 6b cross-modal harmonization output.")
        targets.extend(["processing/<episode>/temporal_index.json", "Phase 6b output", "cross_modal_harmonizer results"])
    elif family == "canonical_artifact_missing":
        hints.append("Inspect run output directory and experiment_log.")
        targets.extend(["output/scene_ingest_results.json", "experiment_log.json", "run output directory"])
    elif family == "phase6_incomplete":
        hints.append("Inspect scene_visual_embeddings and cross_modal_harmonizer results.")
        targets.extend(["scene_visual_embeddings", "cross_modal_harmonizer results", "temporal_index.json", "scene_manifest.json"])
    elif family == "qdrant_unhealthy":
        hints.append("Inspect Qdrant service, collection names, and qdrant_ok fields.")
        targets.extend(["Qdrant service", "Qdrant collection names", "qdrant_ok", "phase6_vector_commit", "scene_ingest_results.json"])
    elif any(str(key).startswith("unrecovered") and int(value or 0) > 0 for key, value in recovery.items()) or "error" in statuses:
        hints.append("Inspect step_runs.jsonl error rows, run warnings, and final canonical artifacts before considering the run complete.")
        targets.extend(["step_runs.jsonl error rows", "run.warnings", "scene_ingest_results.json", "scene_manifest.json", "temporal_index.json"])

    if not hints:
        if category == "blocking":
            hints.append("Inspect canonical artifacts and persisted error rows; treat the affected run as incomplete until truth surfaces are healthy.")
            targets.extend(["scene_ingest_results.json", "scene_manifest.json", "temporal_index.json", "step_runs.jsonl"])
        elif category == "actionable":
            hints.append("Inspect affected step distribution, recovered outcome, and whether final scene output survived.")
            targets.extend(["step_runs.jsonl", "run.warnings", "recovery_outcome", "scene_ingest_results.json"])
        elif category == "watch":
            hints.append("Inspect recurrence frequency and persisted status fields; keep this read-only unless it correlates with unhealthy truth surfaces.")
            targets.extend(["step_runs.jsonl", "temporal_index.json", "scene_manifest.json"])
        else:
            hints.append("No action unless count increases sharply or correlates with unhealthy Phase 6/Qdrant output.")
            targets.extend(["recurrence_summary", "phase6_qdrant_truth"])

    return {
        "operator_hints": _dedupe_strings(hints),
        "inspection_targets": _dedupe_strings(targets),
    }


def _report_operator_guidance(
    family_rows: Sequence[Dict[str, Any]],
    classification: Dict[str, Any],
) -> Dict[str, List[str]]:
    highest = _clean_str(classification.get("highest_category")) or "none"
    highest_rows = [
        row for row in family_rows if isinstance(row, dict) and row.get("category") == highest
    ] if highest != "none" else []
    source_rows = highest_rows or [row for row in family_rows if isinstance(row, dict)]

    hints: List[str] = []
    targets: List[str] = []
    for row in source_rows:
        hints.extend(row.get("operator_hints") or [])
        targets.extend(row.get("inspection_targets") or [])

    if not hints:
        hints.append("No recurrence families found; keep using persisted artifacts for read-only verification.")
        targets.extend(["step_runs.jsonl", "scene_ingest_results.json", "scene_manifest.json", "temporal_index.json"])

    return {
        "operator_hints": _dedupe_strings(hints),
        "inspection_targets": _dedupe_strings(targets),
    }


def _guidance_from_report(report: Dict[str, Any]) -> Dict[str, List[str]]:
    return {
        "operator_hints": list(report.get("operator_hints") or []),
        "inspection_targets": list(report.get("inspection_targets") or []),
    }


def _category_by_family(rows: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for row in rows:
        family = _clean_str(row.get("error_family"))
        category = _clean_str(row.get("category"))
        if family and category:
            out[family] = category
    return out


def _attach_row_categories(rows: Sequence[Dict[str, Any]], category_by_family: Dict[str, str]) -> None:
    for row in rows:
        if isinstance(row, dict):
            row["category"] = category_by_family.get(str(row.get("error_family") or ""), "informational")


def _attach_scene_categories(rows: Sequence[Dict[str, Any]], category_by_family: Dict[str, str]) -> None:
    for row in rows:
        if not isinstance(row, dict):
            continue
        categories = sorted(
            {
                category_by_family.get(family, "informational")
                for family in row.get("error_families") or []
            },
            key=lambda category: _CATEGORY_ORDER.get(category, 0),
            reverse=True,
        )
        row["categories"] = categories
        row["highest_category"] = categories[0] if categories else "none"


def _classification_summary(family_rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    family_counts = {category: 0 for category in _CATEGORY_ORDER}
    signal_counts = {category: 0 for category in _CATEGORY_ORDER}
    families: List[Dict[str, Any]] = []
    highest = "none"
    highest_level = -1

    for row in family_rows:
        category = _clean_str(row.get("category")) or "informational"
        if category not in _CATEGORY_ORDER:
            category = "informational"
        count = int(row.get("count") or 0)
        family_counts[category] += 1
        signal_counts[category] += count
        level = _CATEGORY_ORDER[category]
        if level > highest_level:
            highest = category
            highest_level = level
        families.append(
            {
                "error_family": row.get("error_family"),
                "category": category,
                "count": count,
                "reason": row.get("category_reason"),
                "operator_hints": list(row.get("operator_hints") or []),
                "inspection_targets": list(row.get("inspection_targets") or []),
            }
        )

    return {
        "policy_version": 1,
        "highest_category": highest,
        "highest_category_level": highest_level,
        "category_counts": dict(family_counts),
        "family_counts": family_counts,
        "signal_counts": signal_counts,
        "families": families,
        "policy": {
            "informational": sorted(_INFORMATIONAL_FAMILIES),
            "watch": sorted(_WATCH_FAMILIES | {"repeated_optional_enrichment_skips"}),
            "actionable": [
                "native_crash_retry:*",
                "native_subprocess_crash:*",
                "repeated_backend_downgrade",
                "repeated_direct_env_retry",
                "repeated_recovered_crashes",
            ],
            "blocking": sorted(_BLOCKING_FAMILIES | {"unrecovered_processing_error"}),
        },
    }


def _recommendation_from_classification(classification: Dict[str, Any]) -> Dict[str, Any]:
    highest = _clean_str(classification.get("highest_category")) or "none"
    highest_level = int(classification.get("highest_category_level") or -1)
    families = classification.get("families") if isinstance(classification, dict) else []
    reasons: List[str] = []

    if highest_level >= _CATEGORY_ORDER["blocking"]:
        status = "fail"
        reasons.append("highest recurrence category is blocking")
    elif highest_level >= _CATEGORY_ORDER["watch"]:
        status = "warn"
        reasons.append(f"highest recurrence category is {highest}")
    else:
        status = "pass"
        reasons.append("highest recurrence category is informational or none")

    top = [
        f"{item.get('error_family')} ({item.get('category')}, count={item.get('count')})"
        for item in families
        if isinstance(item, dict) and item.get("category") == highest
    ][:5]
    if top:
        reasons.append("top families at highest category: " + ", ".join(top))

    return {
        "status": status,
        "highest_category": highest,
        "highest_category_level": highest_level,
        "reasons": reasons,
        "policy_version": classification.get("policy_version") or 1,
    }


def _classify_family_category(row: Dict[str, Any], health: Dict[str, Any]) -> Tuple[str, str]:
    family = _clean_str(row.get("error_family")) or "unknown"
    count = int(row.get("count") or 0)
    recovery = row.get("recovery_outcomes") if isinstance(row.get("recovery_outcomes"), dict) else {}
    statuses = set(row.get("statuses") or [])
    healthy = bool(health.get("healthy")) if isinstance(health, dict) else False

    if family in _BLOCKING_FAMILIES:
        return "blocking", f"{family} is a blocking canonical truth condition"
    if any(str(key).startswith("unrecovered") and int(value or 0) > 0 for key, value in recovery.items()):
        return "blocking", "family includes unrecovered processing errors"
    if "error" in statuses and not any(str(key).startswith("recovered") for key in recovery):
        return "blocking", "family has error status without recovered outcome"

    if family.startswith("native_crash_retry:") or family.startswith("native_subprocess_crash:"):
        return "actionable", "native crash recurrence requires operator attention even when recovered"
    if "direct_env" in family or "backend_downgrade" in family or "backend_downgraded" in family:
        return "actionable", "runtime fallback recurrence requires operator attention"
    if count >= 2 and any(str(key).startswith("recovered") for key in recovery) and "crash" in family:
        return "actionable", "repeated recovered crashes require operator attention"

    if family in _WATCH_FAMILIES:
        return "watch", f"{family} is a watch condition"
    if family == "insufficient_diverse_speech":
        if healthy:
            return "informational", "insufficient diverse speech is informational while Phase 6 and Qdrant are healthy"
        return "watch", "insufficient diverse speech appears while Phase 6 or Qdrant is not healthy"
    if family in {"no_text", "too_short", "audio_silent"}:
        return "informational", f"{family} is an expected optional enrichment condition"
    if family.startswith("embedding_skip:") or family == "embedding_missing":
        return "watch", "embedding availability changed or was skipped"
    if count >= 2 and all(status in _SKIP_STATUSES or status == "warning" for status in statuses):
        return "watch", "repeated optional enrichment skips"

    return "informational", "no blocking, actionable, or watch policy matched"


def _family_category_from_classification(classification: Dict[str, Any], family: str) -> str:
    for item in classification.get("families") or []:
        if isinstance(item, dict) and item.get("error_family") == family:
            return _clean_str(item.get("category")) or "informational"
    return "informational"


def _comparison_recommendation(
    *,
    delta: Dict[str, Any],
    candidate_classification: Any,
    candidate_health: Any,
) -> Dict[str, Any]:
    classification = candidate_classification if isinstance(candidate_classification, dict) else {}
    highest = _clean_str(classification.get("highest_category")) or "none"
    highest_level = int(classification.get("highest_category_level") or _CATEGORY_ORDER.get(highest, -1))
    reasons: List[str] = []

    status = "pass"
    if highest_level >= _CATEGORY_ORDER["blocking"]:
        status = "fail"
        reasons.append("highest candidate recurrence category is blocking")
    elif highest_level >= _CATEGORY_ORDER["watch"]:
        status = "warn"
        reasons.append(f"highest candidate recurrence category is {highest}")
    else:
        reasons.append("highest candidate recurrence category is informational or none")

    phase6 = delta.get("phase6_health_delta") if isinstance(delta, dict) else {}
    qdrant = delta.get("qdrant_health_delta") if isinstance(delta, dict) else {}
    if isinstance(phase6, dict) and phase6.get("status") == "regressed":
        status = "fail"
        reasons.append("Phase 6 health regressed")
    if isinstance(qdrant, dict) and qdrant.get("status") == "regressed":
        status = "fail"
        reasons.append("Qdrant health regressed")

    increased = list(delta.get("increased_error_families") or [])
    sharp_info = [
        row
        for row in increased
        if isinstance(row, dict)
        and row.get("category") == "informational"
        and _is_sharp_increase(row)
    ]
    if sharp_info and status == "pass":
        status = "warn"
    if sharp_info:
        reasons.append(
            "informational skipped conditions increased sharply: "
            + ", ".join(str(row.get("error_family")) for row in sharp_info[:8])
        )

    candidate_unhealthy = isinstance(candidate_health, dict) and not bool(candidate_health.get("healthy"))
    info_increase = [
        row
        for row in increased
        if isinstance(row, dict)
        and row.get("category") == "informational"
        and int(row.get("delta") or 0) > 0
    ]
    if candidate_unhealthy and info_increase:
        status = "fail"
        reasons.append("informational skips increased while candidate Phase 6/Qdrant output is unhealthy")

    new_watch_or_higher = [
        family
        for family in delta.get("new_error_families") or []
        if _CATEGORY_ORDER.get(_family_category_from_classification(classification, family), 0)
        >= _CATEGORY_ORDER["watch"]
    ]
    if new_watch_or_higher and status == "pass":
        status = "warn"
    if new_watch_or_higher:
        reasons.append("new watch/actionable/blocking families: " + ", ".join(new_watch_or_higher[:8]))

    if not reasons:
        reasons.append("no recurrence categories present in candidate artifacts")

    return {
        "status": status,
        "highest_category": highest,
        "highest_category_level": highest_level,
        "reasons": _dedupe_strings(reasons),
        "policy_version": classification.get("policy_version") or 1,
        "sharp_increase_rule": "informational delta >= 5 and candidate_count >= max(5, baseline_count * 2)",
    }


def _is_informational_family(family: str) -> bool:
    family = (family or "").strip()
    if family in _INFORMATIONAL_FAMILIES:
        return True
    return any(family.endswith(f":{info}") for info in _INFORMATIONAL_FAMILIES)


def _is_sharp_increase(row: Dict[str, Any]) -> bool:
    baseline = int(row.get("baseline_count") or 0)
    candidate = int(row.get("candidate_count") or 0)
    delta = int(row.get("delta") or 0)
    return delta >= 5 and candidate >= max(5, baseline * 2)


def _select_run_roots(
    *,
    run_root: str | Path | None,
    run_id: str | None,
    reports_root: str | Path | None,
    limit_runs: int,
) -> List[Path]:
    if run_root is not None:
        return [Path(run_root)]
    if run_id:
        return [run_index.get_run_root(run_id, reports_root=reports_root)]

    limit = max(1, int(limit_runs or 1))
    roots = []
    for entry in run_index.list_runs(reports_root=reports_root, limit=limit):
        root = entry.get("run_root")
        if isinstance(root, str) and root.strip():
            roots.append(Path(root))
    return roots


def _load_run_scope(run_root: Path) -> Tuple[List[_EpisodeScope], List[str], List[str]]:
    files_read: List[str] = []
    warnings: List[str] = []
    root_log = run_root / "experiment_log.json"
    if not root_log.is_file():
        direct_scopes = _load_direct_run_scope(run_root, files_read, warnings)
        if direct_scopes:
            return direct_scopes, files_read, warnings
        warnings.append(f"run_root_missing_experiment_log: {run_root}")
        return [], files_read, warnings

    payload = _load_json(root_log, files_read, warnings)
    if not isinstance(payload, dict):
        direct_scopes = _load_direct_run_scope(run_root, files_read, warnings)
        if direct_scopes:
            return direct_scopes, files_read, warnings
        warnings.append(f"run_root_missing_experiment_log: {run_root}")
        return [], files_read, warnings

    plan = payload.get("plan")
    if not isinstance(plan, list):
        plan = []

    scopes: List[_EpisodeScope] = []
    for item in plan:
        if not isinstance(item, dict):
            continue
        run_dir_value = item.get("run_dir")
        run_dir = Path(run_dir_value) if isinstance(run_dir_value, str) and run_dir_value.strip() else run_root
        episode = _clean_str(item.get("episode")) or run_dir.name
        episode_log_path = run_dir / "experiment_log.json"
        episode_log = _load_json(episode_log_path, files_read, warnings)
        metrics = episode_log.get("metrics") if isinstance(episode_log, dict) else {}
        if not isinstance(metrics, dict):
            metrics = {}

        resolved_config_path = run_dir / "workspace" / "_resolved_config.json"
        resolved_config = _load_json(resolved_config_path, files_read, warnings)
        run_cfg = resolved_config.get("run") if isinstance(resolved_config, dict) else {}
        paths_cfg = resolved_config.get("paths") if isinstance(resolved_config, dict) else {}
        if not isinstance(run_cfg, dict):
            run_cfg = {}
        if not isinstance(paths_cfg, dict):
            paths_cfg = {}

        output_path = _path_from(metrics.get("output_path")) or (run_dir / "output" / "scene_ingest_results.json")
        result_items = _load_result_items(output_path, files_read, warnings)
        result_item = result_items[0] if result_items else {}
        if not isinstance(result_item, dict):
            result_item = {}

        video_id = _clean_str(result_item.get("video_id")) or _clean_str(result_item.get("video_hash"))
        video_hash = _clean_str(result_item.get("video_hash")) or video_id
        video_name = _clean_str(result_item.get("video_name")) or episode
        step_log_dir = _path_from(paths_cfg.get("log_dir"))
        step_path = step_log_dir / "step_runs.jsonl" if step_log_dir is not None else None

        temporal_path = _path_from(metrics.get("temporal_index_path")) or _path_from(result_item.get("temporal_index_path"))
        manifest_path = _path_from(metrics.get("scene_manifest_path")) or _derive_manifest_path(temporal_path)

        scopes.append(
            _EpisodeScope(
                report_run_id=run_root.name,
                episode=episode,
                run_dir=run_dir,
                runtime_run_id=_clean_str(run_cfg.get("id")),
                video_id=video_id,
                video_hash=video_hash,
                video_name=video_name,
                step_runs_path=step_path,
                output_path=output_path,
                scene_manifest_path=manifest_path,
                temporal_index_path=temporal_path,
                resolved_config_path=resolved_config_path if resolved_config_path.is_file() else None,
                episode_log_path=episode_log_path if episode_log_path.is_file() else None,
                stdout_path=None,
                stderr_path=None,
                output_item_index=None,
            )
        )

    return scopes, files_read, warnings


def _load_direct_run_scope(run_root: Path, files_read: List[str], warnings: List[str]) -> List[_EpisodeScope]:
    """Discover direct cli.run_ingestion run roots without a wrapper ledger."""

    operator_metadata_path = run_root / "operator_run_metadata.json"
    operator_metadata = (
        _load_json(operator_metadata_path, files_read, warnings)
        if operator_metadata_path.is_file()
        else {}
    )
    if not isinstance(operator_metadata, dict):
        operator_metadata = {}

    default_output_path = run_root / "output" / "scene_ingest_results.json"
    output_path = default_output_path if default_output_path.is_file() else _path_from(operator_metadata.get("output"))
    if output_path is None:
        output_path = default_output_path

    default_resolved_config_path = run_root / "workspace" / "_resolved_config.json"
    metadata_workspace = _path_from(operator_metadata.get("workspace"))
    resolved_config_path = default_resolved_config_path
    if not resolved_config_path.is_file() and metadata_workspace is not None:
        resolved_config_path = metadata_workspace / "_resolved_config.json"

    result_items = _load_result_items(output_path, files_read, warnings)
    resolved_config = _load_json(resolved_config_path, files_read, warnings)

    run_cfg = resolved_config.get("run") if isinstance(resolved_config, dict) else {}
    paths_cfg = resolved_config.get("paths") if isinstance(resolved_config, dict) else {}
    if not isinstance(run_cfg, dict):
        run_cfg = {}
    if not isinstance(paths_cfg, dict):
        paths_cfg = {}
    operator_run_cfg = operator_metadata.get("run") if isinstance(operator_metadata, dict) else {}
    if not isinstance(operator_run_cfg, dict):
        operator_run_cfg = {}
    metadata_run_id = (
        _clean_str(operator_metadata.get("run_id"))
        or _clean_str(operator_metadata.get("runtime_run_id"))
        or _clean_str(operator_run_cfg.get("id"))
    )

    if not result_items and not run_cfg:
        return []

    step_log_dir = _path_from(paths_cfg.get("log_dir"))
    step_path = step_log_dir / "step_runs.jsonl" if step_log_dir is not None else None

    stdout_path = _first_existing_run_path(
        [
            _path_from(operator_metadata.get("stdout")) if isinstance(operator_metadata, dict) else None,
            run_root / "ingestion.stdout.log",
            run_root / "ingest.stdout.log",
        ]
    )
    stderr_path = _first_existing_run_path(
        [
            _path_from(operator_metadata.get("stderr")) if isinstance(operator_metadata, dict) else None,
            run_root / "ingestion.stderr.log",
            run_root / "ingest.stderr.log",
        ]
    )

    if not result_items:
        result_items = [{}]

    scopes: List[_EpisodeScope] = []
    for output_item_index, result_item in enumerate(result_items):
        if not isinstance(result_item, dict):
            result_item = {}
        video_id = _clean_str(result_item.get("video_id")) or _clean_str(result_item.get("video_hash"))
        video_hash = _clean_str(result_item.get("video_hash")) or video_id
        video_name = _clean_str(result_item.get("video_name")) or run_root.name
        runtime_run_id = (
            metadata_run_id
            or _clean_str(result_item.get("run_id"))
            or _clean_str(result_item.get("runtime_run_id"))
            or _clean_str(run_cfg.get("id"))
        )
        temporal_path = _path_from(result_item.get("temporal_index_path"))
        manifest_path = _derive_manifest_path(temporal_path)
        scopes.append(_EpisodeScope(
            report_run_id=run_root.name,
            episode=video_name or run_root.name,
            run_dir=run_root,
            runtime_run_id=runtime_run_id,
            video_id=video_id,
            video_hash=video_hash,
            video_name=video_name,
            step_runs_path=step_path,
            output_path=output_path if output_path.is_file() else None,
            scene_manifest_path=manifest_path,
            temporal_index_path=temporal_path,
            resolved_config_path=resolved_config_path if resolved_config_path.is_file() else None,
            episode_log_path=None,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            output_item_index=output_item_index,
        ))
    return scopes


def _first_existing_run_path(candidates: Sequence[Optional[Path]]) -> Optional[Path]:
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate
    return None


def _load_episode_artifact_signals(episode: _EpisodeScope) -> Tuple[List[Dict[str, Any]], List[str], List[str], Dict[str, Any]]:
    files_read: List[str] = []
    warnings: List[str] = []
    signals: List[Dict[str, Any]] = []

    result_items = _load_result_items(episode.output_path, files_read, warnings)
    result_item = _select_episode_result_item(episode, result_items)
    manifest = _load_json(episode.scene_manifest_path, files_read, warnings) if episode.scene_manifest_path else None
    temporal = _load_json(episode.temporal_index_path, files_read, warnings) if episode.temporal_index_path else None
    resolved = _load_json(episode.resolved_config_path, files_read, warnings) if episode.resolved_config_path else None
    signals.extend(_artifact_presence_signals(episode))
    scene_ids, scene_indices = _episode_scene_identity_sets(result_item, manifest, temporal)

    if isinstance(resolved, dict):
        run_cfg = resolved.get("run")
        if isinstance(run_cfg, dict):
            for warning in run_cfg.get("warnings") or []:
                if isinstance(warning, dict) and _warning_applies_to_episode(warning, episode, scene_ids, scene_indices):
                    signals.append(_signal_from_run_warning(episode, warning))

    runtime_event_signals, runtime_files, runtime_warnings = _load_runtime_event_signals(
        episode,
        scene_ids,
        scene_indices,
    )
    signals.extend(runtime_event_signals)
    files_read.extend(runtime_files)
    warnings.extend(runtime_warnings)

    scene_status_surface = _select_scene_status_surface(result_item, manifest, temporal)
    if scene_status_surface is not None:
        surface_name, data, scenes_key = scene_status_surface
        scene_items = data.get(scenes_key)
        if isinstance(scene_items, list):
            for item in scene_items:
                if isinstance(item, dict):
                    signals.extend(_signals_from_scene_statuses(episode, item, surface_name))

    health = _episode_health(episode, result_item, manifest, temporal)
    signals.extend(_artifact_health_signals(episode, result_item, manifest, temporal))
    return signals, files_read, warnings, health


def _episode_scene_identity_sets(
    result_item: Any,
    manifest: Any,
    temporal: Any,
) -> Tuple[set[str], set[str]]:
    scene_ids: set[str] = set()
    scene_indices: set[str] = set()
    candidates = (
        (result_item if isinstance(result_item, dict) else {}, "scenes"),
        (manifest if isinstance(manifest, dict) else {}, "scenes"),
        (temporal if isinstance(temporal, dict) else {}, "segments"),
    )
    for payload, key in candidates:
        items = payload.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            scene_id = _clean_str(item.get("scene_id"))
            if scene_id:
                scene_ids.add(scene_id)
            for index_key in ("index", "scene_index"):
                if item.get(index_key) is not None:
                    scene_indices.add(str(item.get(index_key)))
    return scene_ids, scene_indices


def _warning_applies_to_episode(
    warning: Dict[str, Any],
    episode: _EpisodeScope,
    scene_ids: set[str],
    scene_indices: set[str],
) -> bool:
    context = warning.get("context")
    if not isinstance(context, dict):
        return True

    warning_video = _clean_str(context.get("video_id")) or _clean_str(context.get("video_hash"))
    if warning_video and warning_video not in {episode.video_id, episode.video_hash}:
        return False

    scene_id = _clean_str(context.get("scene_id"))
    if scene_id and scene_ids:
        return scene_id in scene_ids

    scene_index = context.get("scene_index")
    if scene_index is not None and scene_indices:
        return str(scene_index) in scene_indices

    return True


def _select_episode_result_item(episode: _EpisodeScope, result_items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if episode.output_item_index is not None:
        try:
            item = result_items[int(episode.output_item_index)]
        except Exception:
            item = None
        if isinstance(item, dict):
            return item

    for item in result_items:
        if not isinstance(item, dict):
            continue
        item_video_id = _clean_str(item.get("video_id")) or _clean_str(item.get("video_hash"))
        item_video_hash = _clean_str(item.get("video_hash")) or item_video_id
        item_video_name = _clean_str(item.get("video_name"))
        if episode.video_id and item_video_id == episode.video_id:
            return item
        if episode.video_hash and item_video_hash == episode.video_hash:
            return item
        if episode.video_name and item_video_name == episode.video_name:
            return item

    return result_items[0] if result_items and isinstance(result_items[0], dict) else {}


def _load_runtime_event_signals(
    episode: _EpisodeScope,
    scene_ids: set[str],
    scene_indices: set[str],
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    signals: List[Dict[str, Any]] = []
    files_read: List[str] = []
    warnings: List[str] = []
    events: List[Dict[str, Any]] = []
    if episode.stdout_path is not None and episode.stdout_path.is_file():
        try:
            lines = episode.stdout_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as exc:
            warnings.append(f"runtime_stdout_unreadable: {episode.stdout_path}: {exc}")
            lines = []

        files_read.append(str(episode.stdout_path))
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith("{"):
                continue
            try:
                event = json.loads(stripped)
            except Exception:
                continue
            if isinstance(event, dict) and _runtime_event_applies_to_episode(event, episode, scene_ids, scene_indices):
                events.append(event)

    for index, event in enumerate(events):
        if event.get("event") != "step_error":
            continue
        step = _clean_step_name(event.get("step"))
        error = _clean_str(event.get("error")) or "step_error"
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        return_code = _return_code_from_error(error)
        if return_code is None:
            continue
        retry_event = _find_runtime_retry_event(events[index + 1 :], event, metadata)
        retry_metadata = retry_event.get("metadata") if isinstance(retry_event, dict) else {}
        if not isinstance(retry_metadata, dict):
            retry_metadata = {}
        recovered = retry_event is not None
        code = "native_crash_retry" if recovered else None
        family = _classify_error_family(
            step=step,
            status="warning" if recovered else "error",
            reason=code or error,
            message=f"returncode={return_code}",
            code=code,
            row={"return_code": return_code},
        )
        signals.append(
            {
                "source": "runtime.events",
                "run_id": _clean_str(event.get("run_id")) or episode.runtime_run_id,
                "report_run_id": episode.report_run_id,
                "episode": episode.video_name or episode.episode,
                "video_id": _clean_str(metadata.get("video_id")) or episode.video_id,
                "env": _clean_str(metadata.get("env")) or _clean_str(metadata.get("env_name")),
                "step_name": step,
                "status": "warning" if recovered else "error",
                "reason": "native_crash_retry" if recovered else error,
                "error_family": family,
                "scene_id": _clean_str(metadata.get("scene_id")),
                "scene_index": metadata.get("scene_index"),
                "return_code": return_code,
                "retry_mode": _clean_str(retry_metadata.get("native_retry_mode")),
                "recovery_outcome": "recovered_retry" if recovered else None,
                "optional": _is_optional_runtime_step(step),
                "message": error,
                "ts": _clean_str(event.get("timestamp")),
            }
        )

    stderr_signals, stderr_files, stderr_warnings = _load_stderr_native_retry_signals(episode)
    signals.extend(stderr_signals)
    files_read.extend(stderr_files)
    warnings.extend(stderr_warnings)
    return signals, files_read, warnings


def _runtime_event_applies_to_episode(
    event: Dict[str, Any],
    episode: _EpisodeScope,
    scene_ids: set[str],
    scene_indices: set[str],
) -> bool:
    metadata = event.get("metadata")
    if not isinstance(metadata, dict):
        return True

    event_video = _clean_str(metadata.get("video_id")) or _clean_str(metadata.get("video_hash"))
    episode_videos = {value for value in (episode.video_id, episode.video_hash) if value}
    if event_video and episode_videos and event_video not in episode_videos:
        return False

    scene_id = _clean_str(metadata.get("scene_id"))
    if scene_id and scene_ids:
        return scene_id in scene_ids

    scene_index = metadata.get("scene_index")
    if scene_index is not None and scene_indices:
        return str(scene_index) in scene_indices

    return True


def _load_stderr_native_retry_signals(episode: _EpisodeScope) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    signals: List[Dict[str, Any]] = []
    files_read: List[str] = []
    warnings: List[str] = []
    if episode.stderr_path is None or not episode.stderr_path.is_file():
        return signals, files_read, warnings
    try:
        lines = episode.stderr_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:
        warnings.append(f"runtime_stderr_unreadable: {episode.stderr_path}: {exc}")
        return signals, files_read, warnings

    files_read.append(str(episode.stderr_path))
    seen = set()
    for line in lines:
        parsed = _parse_native_crash_stderr_line(line)
        if parsed is None:
            continue
        step, return_code, status_code, retry_mode = parsed
        key = (step, return_code, status_code, retry_mode)
        if key in seen:
            continue
        seen.add(key)
        family = _classify_error_family(
            step=step,
            status="warning",
            reason="native_crash_retry",
            message=f"returncode={return_code}" if return_code is not None else None,
            code="native_crash_retry",
            row={"return_code": return_code, "status_code_hex": status_code},
        )
        signals.append(
            {
                "source": "runtime.stderr",
                "run_id": episode.runtime_run_id,
                "report_run_id": episode.report_run_id,
                "episode": episode.video_name or episode.episode,
                "video_id": episode.video_id,
                "step_name": step,
                "status": "warning",
                "reason": "native_crash_retry",
                "error_family": family,
                "scene_id": None,
                "scene_index": None,
                "return_code": return_code,
                "retry_mode": retry_mode,
                "recovery_outcome": "recovered_retry",
                "optional": _is_optional_runtime_step(step),
                "message": line.strip(),
                "ts": None,
            }
        )
    return signals, files_read, warnings


def _is_optional_runtime_step(step: Any) -> bool:
    step_name = (_clean_step_name(step) or "").lower()
    return step_name in {
        "audio_embed_clap",
        "audio_emotion",
        "audio_backend",
        "diarization",
        "emotion",
        "image_caption",
        "image_embed_clip",
        "image_embed_dino",
        "image_ocr",
        "object_detect",
        "ocr",
        "sentiment",
        "speaker_voice_signature",
        "speaker_voice_signature_meta",
    }


def _parse_native_crash_stderr_line(line: str) -> Optional[Tuple[str, Optional[int], Optional[str], Optional[str]]]:
    text = line.strip()
    if not text or "native crash" not in text.lower():
        return None
    detected = re.search(
        r"Native crash detected for step=(?P<step>[^\s]+).*?return_code=(?P<return_code>[-]?\d+).*?status_code=(?P<status_code>0x[0-9A-Fa-f]+)",
        text,
        re.IGNORECASE,
    )
    if detected:
        return (
            _clean_step_name(detected.group("step")),
            _coerce_int(detected.group("return_code")),
            _normalize_status_code_hex(detected.group("status_code")),
            _native_retry_mode_from_text(text),
        )

    retry = re.search(
        r"Native crash for (?P<step>[^\s]+).*?\((?P<status_code>0x[0-9A-Fa-f]+)\).*?retry",
        text,
        re.IGNORECASE,
    )
    if retry:
        return (
            _clean_step_name(retry.group("step")),
            None,
            _normalize_status_code_hex(retry.group("status_code")),
            _native_retry_mode_from_text(text),
        )
    return None


def _native_retry_mode_from_text(text: str) -> Optional[str]:
    mode = re.search(r"\bmode=(?P<mode>[A-Za-z0-9_\-]+)", text)
    if mode:
        return _clean_str(mode.group("mode"))
    via = re.search(r"\bvia\s+(?P<mode>[A-Za-z0-9_\-]+)", text, re.IGNORECASE)
    if via:
        return _clean_str(via.group("mode"))
    return None


def _clean_step_name(value: Any) -> str:
    step = _clean_str(value) or "unknown_step"
    if step.startswith("step."):
        return step[5:]
    return step


def _return_code_from_error(value: Any) -> Optional[int]:
    text = _clean_str(value)
    if not text:
        return None
    match = re.search(r"(?:returncode|return_code)[_=]([-]?\d+)", text, re.IGNORECASE)
    if not match:
        return None
    return _coerce_int(match.group(1))


def _normalize_status_code_hex(value: Any) -> Optional[str]:
    text = _clean_str(value)
    if not text:
        return None
    if text.lower().startswith("0x"):
        return "0x" + text[2:].upper()
    return text


def _find_runtime_retry_event(
    events: Sequence[Dict[str, Any]],
    failed_event: Dict[str, Any],
    failed_metadata: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    failed_step = _clean_step_name(failed_event.get("step"))
    failed_run = _clean_str(failed_event.get("run_id"))
    failed_scene = _clean_str(failed_metadata.get("scene_id"))
    for event in events:
        event_name = _clean_str(event.get("event"))
        if event_name not in {"step_start", "step_retry"}:
            continue
        if _clean_step_name(event.get("step")) != failed_step:
            continue
        if failed_run and _clean_str(event.get("run_id")) != failed_run:
            continue
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        if failed_scene and _clean_str(metadata.get("scene_id")) != failed_scene:
            continue
        if _clean_str(metadata.get("native_retry_mode")) or _coerce_int(metadata.get("native_retry_attempt")):
            return event
    return None


def _artifact_presence_signals(episode: _EpisodeScope) -> List[Dict[str, Any]]:
    checks = (
        (episode.output_path, "scene_ingest_results", "canonical_artifact_missing", "missing_scene_ingest_results"),
        (episode.scene_manifest_path, "scene_manifest", "missing_scene_manifest", "missing_scene_manifest"),
        (episode.temporal_index_path, "temporal_index", "missing_temporal_index", "missing_temporal_index"),
    )
    signals: List[Dict[str, Any]] = []
    for path, step_name, family, reason in checks:
        if path is not None and path.is_file():
            continue
        signals.append(
            _artifact_signal(
                episode=episode,
                source="artifact_presence",
                step_name=step_name,
                reason=reason,
                family=family,
                message=f"Canonical artifact missing: {path}" if path is not None else f"Canonical artifact path missing: {step_name}",
            )
        )
    return signals


def _artifact_health_signals(
    episode: _EpisodeScope,
    result_item: Any,
    manifest: Any,
    temporal: Any,
) -> List[Dict[str, Any]]:
    result = result_item if isinstance(result_item, dict) else {}
    man = manifest if isinstance(manifest, dict) else {}
    temp = temporal if isinstance(temporal, dict) else {}
    signals: List[Dict[str, Any]] = []

    phase6_values = [
        result.get("phase6_complete"),
        man.get("phase6_complete"),
        man.get("phase6_harmonized"),
        temp.get("phase6_complete"),
        temp.get("phase6_harmonized"),
    ]
    qdrant_values = [
        result.get("qdrant_ok"),
        result.get("phase6_qdrant_ok"),
        _nested_get(man, ("phase6_vector_commit", "qdrant_ok")),
    ]
    if any(value is False for value in phase6_values):
        signals.append(
            _artifact_signal(
                episode=episode,
                source="artifact_health",
                step_name="phase6",
                reason="phase6_incomplete",
                family="phase6_incomplete",
                message="Phase 6 incomplete or not harmonized in canonical artifacts",
            )
        )
    if any(value is False for value in qdrant_values):
        signals.append(
            _artifact_signal(
                episode=episode,
                source="artifact_health",
                step_name="qdrant",
                reason="qdrant_unhealthy",
                family="qdrant_unhealthy",
                message="Qdrant unhealthy in canonical artifacts",
            )
        )
    return signals


def _artifact_signal(
    *,
    episode: _EpisodeScope,
    source: str,
    step_name: str,
    reason: str,
    family: str,
    message: str,
) -> Dict[str, Any]:
    return {
        "source": source,
        "run_id": episode.runtime_run_id,
        "report_run_id": episode.report_run_id,
        "episode": episode.video_name or episode.episode,
        "video_id": episode.video_id,
        "step_name": step_name,
        "status": "missing" if source == "artifact_presence" else "error",
        "reason": reason,
        "error_family": family,
        "scene_id": None,
        "scene_index": None,
        "recovery_outcome": None,
        "optional": False,
        "message": message,
        "ts": None,
    }


def _select_scene_status_surface(result_item: Any, manifest: Any, temporal: Any) -> Optional[Tuple[str, Dict[str, Any], str]]:
    if isinstance(temporal, dict) and isinstance(temporal.get("segments"), list):
        return "temporal_index.json", temporal, "segments"
    if isinstance(manifest, dict) and isinstance(manifest.get("scenes"), list):
        return "scene_manifest.json", manifest, "scenes"
    if isinstance(result_item, dict) and isinstance(result_item.get("scenes"), list):
        return "scene_ingest_results.json", result_item, "scenes"
    return None


def _load_step_run_signals(
    *,
    path: Path,
    episode_by_runtime_id: Dict[str, _EpisodeScope],
    episode_by_video_id: Dict[str, _EpisodeScope],
    target_runtime_run_ids: Sequence[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[str], List[str], Dict[str, Any]]:
    files_read: List[str] = []
    warnings: List[str] = []
    signals: List[Dict[str, Any]] = []
    latency_rows: List[Dict[str, Any]] = []
    coverage_rows: List[Dict[str, Any]] = []
    target_run_ids = {str(value) for value in target_runtime_run_ids if str(value).strip()}
    scope_info: Dict[str, Any] = {
        "strict_run_id_filter_applied": bool(target_run_ids),
        "target_run_ids": sorted(target_run_ids),
        "excluded_run_ids": {},
        "limited_run_id_scope": False,
    }
    if not path.is_file():
        warnings.append(f"step_runs_missing: {path}")
        return signals, latency_rows, coverage_rows, files_read, warnings, scope_info

    files_read.append(str(path))
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:
        warnings.append(f"step_runs_unreadable: {path}: {exc}")
        return signals, latency_rows, coverage_rows, files_read, warnings, scope_info

    excluded_run_ids: Counter[str] = Counter()
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue

        row_run_id = _clean_str(row.get("run_id")) or ""
        row_video_id = _clean_str(row.get("video_id")) or ""
        if target_run_ids:
            if row_run_id not in target_run_ids:
                excluded_run_ids[row_run_id or "<missing>"] += 1
                continue
            episode = episode_by_video_id.get(row_video_id)
            if episode is None:
                episode = episode_by_runtime_id.get(row_run_id)
        else:
            scope_info["limited_run_id_scope"] = True
            episode = episode_by_video_id.get(row_video_id)
            if episode is None:
                episode = episode_by_runtime_id.get(row_run_id)
        if episode is None:
            continue

        coverage_rows.append(_coverage_from_step_row(episode, row))

        latency_row = _latency_from_step_row(episode, row)
        if latency_row is not None:
            latency_rows.append(latency_row)

        status = (_clean_str(row.get("status")) or "unknown").lower()
        if status in _OK_STATUSES:
            continue

        signals.append(_signal_from_step_row(episode, row))

    if excluded_run_ids:
        scope_info["excluded_run_ids"] = dict(sorted(excluded_run_ids.items()))
        warnings.append(
            "excluded_run_ids: "
            + ", ".join(f"{run_id}={count}" for run_id, count in sorted(excluded_run_ids.items()))
        )
    if scope_info["limited_run_id_scope"]:
        warnings.append("limited_run_id_scope: target runtime run_id unavailable; step_runs filtered without strict run_id")

    return signals, latency_rows, coverage_rows, files_read, warnings, scope_info


def _latency_from_step_row(episode: _EpisodeScope, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    duration_ms = _coerce_float(row.get("duration_ms"))
    if duration_ms is None:
        return None
    return {
        "source": "step_runs.jsonl",
        "report_run_id": episode.report_run_id,
        "run_id": _clean_str(row.get("run_id")) or episode.runtime_run_id,
        "episode": episode.video_name or episode.episode,
        "video_id": _clean_str(row.get("video_id")) or episode.video_id,
        "step_name": _clean_str(row.get("step")) or "unknown_step",
        "status": (_clean_str(row.get("status")) or "unknown").lower(),
        "duration_ms": duration_ms,
        "scene_id": _clean_str(row.get("scene_id")),
        "scene_index": row.get("scene_index"),
        "ts": _clean_str(row.get("ts")),
    }


def _coverage_from_step_row(episode: _EpisodeScope, row: Dict[str, Any]) -> Dict[str, Any]:
    step = _clean_str(row.get("step")) or "unknown_step"
    status = (_clean_str(row.get("status")) or "unknown").lower()
    extra = row.get("extra") if isinstance(row.get("extra"), dict) else {}
    reason = _extract_reason(row) or status
    return {
        "source": "step_runs.jsonl",
        "report_run_id": episode.report_run_id,
        "run_id": _clean_str(row.get("run_id")) or episode.runtime_run_id,
        "episode": episode.video_name or episode.episode,
        "video_id": _clean_str(row.get("video_id")) or episode.video_id,
        "step_name": step,
        "status": status,
        "reason": reason,
        "env": _clean_str(row.get("env")),
        "meta_status": _first_nested_status(extra.get("result_meta")),
        "embedding_emitted": extra.get("embedding_emitted") if isinstance(extra.get("embedding_emitted"), bool) else None,
        "optional": bool(extra.get("optional")) or _is_optional_runtime_step(step),
        "scene_id": _clean_str(row.get("scene_id")),
        "scene_index": row.get("scene_index"),
        "ts": _clean_str(row.get("ts")),
    }


def _signal_from_step_row(episode: _EpisodeScope, row: Dict[str, Any]) -> Dict[str, Any]:
    step = _clean_str(row.get("step")) or "unknown_step"
    status = (_clean_str(row.get("status")) or "unknown").lower()
    reason = _extract_reason(row) or status
    error = _clean_str(row.get("error"))
    optional = bool(_nested_get(row, ("extra", "optional")))
    family = _classify_error_family(step=step, status=status, reason=reason, message=error, code=None, row=row)
    return {
        "source": "step_runs.jsonl",
        "run_id": _clean_str(row.get("run_id")) or episode.runtime_run_id,
        "report_run_id": episode.report_run_id,
        "episode": episode.video_name or episode.episode,
        "video_id": _clean_str(row.get("video_id")) or episode.video_id,
        "step_name": step,
        "status": status,
        "reason": reason,
        "error_family": family,
        "scene_id": _clean_str(row.get("scene_id")),
        "scene_index": row.get("scene_index"),
        "recovery_outcome": None,
        "optional": optional or status in _SKIP_STATUSES,
        "message": error,
        "ts": _clean_str(row.get("ts")),
    }


def _signal_from_run_warning(episode: _EpisodeScope, warning: Dict[str, Any]) -> Dict[str, Any]:
    context = warning.get("context")
    if not isinstance(context, dict):
        context = {}
    code = _clean_str(warning.get("code")) or "run_warning"
    step = _clean_str(context.get("step")) or code
    message = _clean_str(warning.get("message"))
    reason = code
    family = _classify_error_family(step=step, status="warning", reason=reason, message=message, code=code, row=context)
    return {
        "source": "run.warnings",
        "run_id": episode.runtime_run_id,
        "report_run_id": episode.report_run_id,
        "episode": episode.video_name or episode.episode,
        "video_id": episode.video_id,
        "step_name": step,
        "status": "warning",
        "reason": reason,
        "error_family": family,
        "scene_id": _clean_str(context.get("scene_id")),
        "scene_index": context.get("scene_index"),
        "return_code": _coerce_int(context.get("return_code")),
        "retry_mode": _clean_str(context.get("native_retry_mode")) or _clean_str(context.get("retry_mode")),
        "recovery_outcome": "recovered_retry" if code == "native_crash_retry" else None,
        "optional": code.startswith("optional_"),
        "message": message,
        "env": _clean_str(context.get("env")),
        "env_fingerprint": _clean_str(context.get("env_fingerprint")),
        "ts": _clean_str(warning.get("ts_utc")),
    }


def _signals_from_scene_statuses(
    episode: _EpisodeScope,
    scene: Dict[str, Any],
    source: str,
) -> List[Dict[str, Any]]:
    signals: List[Dict[str, Any]] = []
    scene_id = _clean_str(scene.get("scene_id"))
    scene_index = scene.get("index")

    for stem in ("diarization", "emotion"):
        status = _clean_str(scene.get(f"{stem}_status"))
        if status and status.lower() not in _OK_STATUSES:
            reason = _clean_str(scene.get(f"{stem}_error")) or _clean_str(scene.get(f"{stem}_note")) or status
            signals.append(
                _scene_signal(
                    episode=episode,
                    source=source,
                    step_name=stem,
                    status=status.lower(),
                    reason=reason,
                    scene_id=scene_id,
                    scene_index=scene_index,
                    optional=True,
                )
            )

    for key, value in scene.items():
        if not isinstance(key, str) or not key.endswith("_meta") or not isinstance(value, dict):
            continue
        status = _clean_str(value.get("status"))
        if not status or status.lower() in _OK_STATUSES:
            continue
        reason = _clean_str(value.get("reason")) or _clean_str(value.get("error")) or _clean_str(value.get("note")) or status
        step_name = key[:-5]
        signals.append(
            _scene_signal(
                episode=episode,
                source=source,
                step_name=step_name,
                status=status.lower(),
                reason=reason,
                scene_id=scene_id,
                scene_index=scene_index,
                optional=True,
            )
        )

    return signals


def _scene_signal(
    *,
    episode: _EpisodeScope,
    source: str,
    step_name: str,
    status: str,
    reason: str,
    scene_id: Optional[str],
    scene_index: Any,
    optional: bool,
) -> Dict[str, Any]:
    family = _classify_error_family(step=step_name, status=status, reason=reason, message=None, code=None, row={})
    return {
        "source": source,
        "run_id": episode.runtime_run_id,
        "report_run_id": episode.report_run_id,
        "episode": episode.video_name or episode.episode,
        "video_id": episode.video_id,
        "step_name": step_name,
        "status": status,
        "reason": reason,
        "error_family": family,
        "scene_id": scene_id,
        "scene_index": scene_index,
        "recovery_outcome": None,
        "optional": optional,
        "message": None,
        "ts": None,
    }


def _episode_health(
    episode: _EpisodeScope,
    result_item: Any,
    manifest: Any,
    temporal: Any,
) -> Dict[str, Any]:
    result = result_item if isinstance(result_item, dict) else {}
    man = manifest if isinstance(manifest, dict) else {}
    temp = temporal if isinstance(temporal, dict) else {}

    phase6_values = [
        result.get("phase6_complete"),
        man.get("phase6_complete"),
        temp.get("phase6_complete"),
    ]
    harmonized_values = [
        man.get("phase6_harmonized"),
        temp.get("phase6_harmonized"),
    ]
    qdrant_values = [
        result.get("qdrant_ok"),
        result.get("phase6_qdrant_ok"),
        _nested_get(man, ("phase6_vector_commit", "qdrant_ok")),
    ]
    scene_counts = [
        _len_list(result.get("scenes")),
        _len_list(man.get("scenes")),
        int(temp.get("total_scenes")) if isinstance(temp.get("total_scenes"), int) else _len_list(temp.get("segments")),
    ]

    phase6_complete = _all_known_true(phase6_values)
    phase6_harmonized = _all_known_true(harmonized_values)
    qdrant_ok = _all_known_true(qdrant_values)
    scene_count = max([v for v in scene_counts if isinstance(v, int)] or [0])
    healthy = bool(phase6_complete and phase6_harmonized and qdrant_ok and scene_count > 0)

    return {
        "report_run_id": episode.report_run_id,
        "run_id": episode.runtime_run_id,
        "episode": episode.video_name or episode.episode,
        "video_id": episode.video_id,
        "phase6_complete": phase6_complete,
        "phase6_harmonized": phase6_harmonized,
        "qdrant_ok": qdrant_ok,
        "scene_count": scene_count,
        "status": "healthy" if healthy else "degraded",
        "healthy": healthy,
        "surfaces": {
            "scene_ingest_results": bool(result),
            "scene_manifest": bool(man),
            "temporal_index": bool(temp),
        },
    }


def _group_signals(signals: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for signal in signals:
        key = (
            signal.get("run_id"),
            signal.get("episode"),
            signal.get("video_id"),
            signal.get("step_name"),
            signal.get("status"),
            signal.get("reason"),
            signal.get("error_family"),
            signal.get("scene_id"),
            signal.get("recovery_outcome"),
        )
        row = grouped.setdefault(
            key,
            {
                "run_id": signal.get("run_id"),
                "report_run_id": signal.get("report_run_id"),
                "episode": signal.get("episode"),
                "video_id": signal.get("video_id"),
                "step_name": signal.get("step_name"),
                "status": signal.get("status"),
                "reason": signal.get("reason"),
                "error_family": signal.get("error_family"),
                "scene_id": signal.get("scene_id"),
                "recovery_outcome": signal.get("recovery_outcome"),
                "count": 0,
                "sources": [],
                "scene_indices": [],
                "optional": bool(signal.get("optional")),
            },
        )
        row["count"] += 1
        for source in _signal_surface_names(signal):
            if source not in row["sources"]:
                row["sources"].append(source)
        if signal.get("scene_index") is not None and signal.get("scene_index") not in row["scene_indices"]:
            row["scene_indices"].append(signal.get("scene_index"))
        row["optional"] = bool(row.get("optional") or signal.get("optional"))

    rows = list(grouped.values())
    rows.sort(key=lambda item: (-int(item.get("count") or 0), str(item.get("error_family")), str(item.get("episode"))))
    return rows


def _top_families(signals: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bucket: Dict[str, Dict[str, Any]] = {}
    for signal in signals:
        family = _clean_str(signal.get("error_family")) or "unknown"
        row = bucket.setdefault(
            family,
            {
                "error_family": family,
                "count": 0,
                "episodes": 0,
                "runs": 0,
                "scenes": 0,
                "step_names": [],
                "statuses": [],
                "sources": [],
                "recovery_outcomes": Counter(),
                "_episode_set": set(),
                "_run_set": set(),
                "_scene_set": set(),
            },
        )
        row["count"] += 1
        if signal.get("episode"):
            row["_episode_set"].add(signal.get("episode"))
        if signal.get("run_id"):
            row["_run_set"].add(signal.get("run_id"))
        if signal.get("scene_id"):
            row["_scene_set"].add(signal.get("scene_id"))
        if signal.get("step_name") and signal.get("step_name") not in row["step_names"]:
            row["step_names"].append(signal.get("step_name"))
        if signal.get("status") and signal.get("status") not in row["statuses"]:
            row["statuses"].append(signal.get("status"))
        for source in _signal_surface_names(signal):
            if source not in row["sources"]:
                row["sources"].append(source)
        row["recovery_outcomes"].update([signal.get("recovery_outcome") or "unknown"])

    rows: List[Dict[str, Any]] = []
    for row in bucket.values():
        rows.append(
            {
                "error_family": row["error_family"],
                "count": row["count"],
                "episodes": len(row["_episode_set"]),
                "runs": len(row["_run_set"]),
                "scenes": len(row["_scene_set"]),
                "step_names": sorted(row["step_names"]),
                "statuses": sorted(row["statuses"]),
                "sources": sorted(row["sources"]),
                "recovery_outcomes": dict(row["recovery_outcomes"]),
            }
        )
    rows.sort(key=lambda item: (-int(item.get("count") or 0), str(item.get("error_family"))))
    return rows


def _optional_enrichment_skips(signals: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    optional = [
        signal
        for signal in signals
        if bool(signal.get("optional")) and str(signal.get("status") or "").lower() in (_SKIP_STATUSES | _ERROR_STATUSES | {"warning"})
    ]
    return _group_signals(optional)


def _optional_enrichment_coverage(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    optional_rows = [row for row in rows if bool(row.get("optional"))]
    if not optional_rows:
        return {
            "mode": "read_only_optional_enrichment_coverage",
            "source": "step_runs.jsonl structured step outcomes",
            "status": "empty",
            "total_rows": 0,
            "step_count": 0,
            "non_ok_rows": 0,
            "steps": [],
            "warnings": ["no_optional_step_rows"],
        }

    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for row in optional_rows:
        step = _clean_step_name(row.get("step_name"))
        buckets.setdefault(step, []).append(row)

    step_rows = [_optional_enrichment_step_coverage(step, items) for step, items in buckets.items()]
    step_rows.sort(key=lambda row: (-int(row.get("non_ok_count") or 0), -int(row.get("total_rows") or 0), str(row.get("step_name"))))
    return {
        "mode": "read_only_optional_enrichment_coverage",
        "source": "step_runs.jsonl structured step outcomes",
        "status": "available",
        "total_rows": len(optional_rows),
        "step_count": len(step_rows),
        "non_ok_rows": sum(int(row.get("non_ok_count") or 0) for row in step_rows),
        "steps": step_rows,
        "warnings": [],
    }


def _optional_enrichment_step_coverage(step: str, rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    status_counts = Counter(str(row.get("status") or "unknown").lower() for row in rows)
    reason_counts = Counter(
        str(row.get("reason") or row.get("status") or "unknown").lower()
        for row in rows
        if str(row.get("status") or "unknown").lower() not in _OK_STATUSES
    )
    meta_status_counts = Counter(
        str(row.get("meta_status") or "unknown").lower()
        for row in rows
        if row.get("meta_status") is not None
    )
    emitted_count = sum(1 for row in rows if row.get("embedding_emitted") is True)
    scene_keys = {
        (row.get("episode"), row.get("scene_id") or row.get("scene_index"))
        for row in rows
        if row.get("scene_id") is not None or row.get("scene_index") is not None
    }
    episodes = sorted({str(row.get("episode")) for row in rows if row.get("episode")})
    non_ok_count = sum(count for status, count in status_counts.items() if status not in _OK_STATUSES)
    return {
        "step_name": step,
        "total_rows": len(rows),
        "ok_count": sum(count for status, count in status_counts.items() if status in _OK_STATUSES),
        "skipped_count": sum(count for status, count in status_counts.items() if status in _SKIP_STATUSES),
        "error_count": sum(count for status, count in status_counts.items() if status in _ERROR_STATUSES),
        "warning_count": int(status_counts.get("warning") or 0),
        "non_ok_count": non_ok_count,
        "status_counts": dict(sorted(status_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "meta_status_counts": dict(sorted(meta_status_counts.items())),
        "embedding_emitted_count": emitted_count,
        "scene_count": len(scene_keys),
        "episodes": episodes,
        "episode_count": len(episodes),
    }


def _environment_summary(step_rows: Sequence[Dict[str, Any]], signals: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    env_counts = Counter(
        _clean_str(row.get("env")) or "unknown"
        for row in step_rows
        if _clean_str(row.get("env"))
    )
    step_envs: Dict[str, Counter[str]] = {}
    for row in step_rows:
        step = _clean_step_name(row.get("step_name"))
        env = _clean_str(row.get("env")) or "unknown"
        if env == "unknown":
            continue
        step_envs.setdefault(step, Counter()).update([env])

    fingerprint_rows: List[Dict[str, Any]] = []
    seen_fingerprints = set()
    for signal in signals:
        raw = _clean_str(signal.get("env_fingerprint"))
        if not raw:
            continue
        parsed = _parse_env_fingerprint(raw)
        key = (
            signal.get("run_id"),
            signal.get("step_name"),
            parsed.get("fingerprint") or raw,
        )
        if key in seen_fingerprints:
            continue
        seen_fingerprints.add(key)
        fingerprint_rows.append(
            {
                "run_id": signal.get("run_id"),
                "episode": signal.get("episode"),
                "video_id": signal.get("video_id"),
                "step_name": signal.get("step_name"),
                "error_family": signal.get("error_family"),
                "fingerprint": parsed.get("fingerprint"),
                "event": parsed.get("event"),
                "env": _sanitized_env_fingerprint_values(parsed.get("env")),
                "raw_available": bool(raw),
            }
        )

    steps = [
        {
            "step_name": step,
            "env_counts": dict(sorted(counter.items())),
            "env_names": sorted(counter),
        }
        for step, counter in sorted(step_envs.items())
    ]
    return {
        "mode": "read_only_environment_observability",
        "source": "step_runs.jsonl env fields and persisted native retry env_fingerprint warnings",
        "status": "available" if env_counts or fingerprint_rows else "empty",
        "step_row_count": len(step_rows),
        "env_counts": dict(sorted(env_counts.items())),
        "step_envs": steps,
        "native_retry_env_fingerprints": fingerprint_rows,
        "warnings": [] if env_counts or fingerprint_rows else ["no_environment_rows"],
    }


def _parse_env_fingerprint(raw: str) -> Dict[str, Any]:
    text = raw.strip()
    if not text:
        return {}
    start = text.find("{")
    if start > 0:
        text = text[start:]
    try:
        payload = json.loads(text)
    except Exception:
        return {"raw": raw}
    return payload if isinstance(payload, dict) else {"raw": raw}


def _sanitized_env_fingerprint_values(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    sanitized: Dict[str, Any] = {}
    for key, item in sorted(value.items()):
        clean_key = _clean_str(key)
        if not clean_key:
            continue
        if isinstance(item, str):
            sanitized[clean_key] = _display_text(item)
        elif item is None or isinstance(item, (bool, int, float)):
            sanitized[clean_key] = item
        else:
            sanitized[clean_key] = _display_text(item)
    return sanitized


def _recovery_counts(signals: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts = Counter()
    for signal in signals:
        outcome = _clean_str(signal.get("recovery_outcome")) or "unknown"
        if outcome.startswith("recovered"):
            counts["recovered"] += 1
        elif outcome.startswith("unrecovered"):
            counts["unrecovered"] += 1
        elif outcome.startswith("skipped"):
            counts["skipped"] += 1
        else:
            counts["unknown"] += 1
    return {
        "recovered": counts.get("recovered", 0),
        "unrecovered": counts.get("unrecovered", 0),
        "skipped": counts.get("skipped", 0),
        "unknown": counts.get("unknown", 0),
    }


def _scenes_affected(signals: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scenes: Dict[Tuple[Any, Any], Dict[str, Any]] = {}
    for signal in signals:
        scene_id = signal.get("scene_id")
        if not scene_id:
            continue
        key = (signal.get("video_id"), scene_id)
        row = scenes.setdefault(
            key,
            {
                "video_id": signal.get("video_id"),
                "episode": signal.get("episode"),
                "scene_id": scene_id,
                "scene_index": signal.get("scene_index"),
                "signal_count": 0,
                "error_families": [],
                "step_names": [],
                "recovery_outcomes": [],
            },
        )
        row["signal_count"] += 1
        for field in ("error_family", "step_name", "recovery_outcome"):
            value = signal.get(field)
            target = "error_families" if field == "error_family" else f"{field}s"
            if value and value not in row[target]:
                row[target].append(value)
        if row.get("scene_index") is None and signal.get("scene_index") is not None:
            row["scene_index"] = signal.get("scene_index")

    rows = list(scenes.values())
    rows.sort(key=lambda item: (-int(item.get("signal_count") or 0), str(item.get("episode")), str(item.get("scene_index"))))
    return rows


def _step_latency_summary(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize persisted step duration rows without changing recurrence signals."""

    valid_rows = [row for row in rows if _coerce_float(row.get("duration_ms")) is not None]
    if not valid_rows:
        return {
            "mode": "read_only_latency_observability",
            "source": "step_runs.jsonl duration_ms",
            "status": "empty",
            "duration_row_count": 0,
            "step_count": 0,
            "timeout_boundary_ms": _DEFAULT_STEP_TIMEOUT_BOUNDARY_MS,
            "slow_outlier_threshold_ms": _SLOW_STEP_OUTLIER_MS,
            "timeout_boundary_exceedance_count": 0,
            "slow_outlier_count": 0,
            "steps": [],
            "wsl_audio_steps": [],
            "warnings": ["no_step_duration_rows"],
        }

    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for row in valid_rows:
        step = _clean_str(row.get("step_name")) or "unknown_step"
        buckets.setdefault(step, []).append(row)

    step_rows = [_summarize_latency_step(step, items) for step, items in buckets.items()]
    step_rows.sort(key=lambda row: (-float(row.get("max_ms") or 0.0), str(row.get("step_name"))))
    wsl_audio_steps = [row for row in step_rows if _is_wsl_audio_step(str(row.get("step_name") or ""))]

    return {
        "mode": "read_only_latency_observability",
        "source": "step_runs.jsonl duration_ms",
        "status": "available",
        "duration_row_count": len(valid_rows),
        "step_count": len(step_rows),
        "timeout_boundary_ms": _DEFAULT_STEP_TIMEOUT_BOUNDARY_MS,
        "slow_outlier_threshold_ms": _SLOW_STEP_OUTLIER_MS,
        "timeout_boundary_exceedance_count": sum(int(row.get("timeout_boundary_exceedance_count") or 0) for row in step_rows),
        "slow_outlier_count": sum(int(row.get("slow_outlier_count") or 0) for row in step_rows),
        "steps": step_rows,
        "wsl_audio_steps": wsl_audio_steps,
        "warnings": [],
    }


def _summarize_latency_step(step: str, rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    durations = sorted(float(row.get("duration_ms") or 0.0) for row in rows)
    statuses = Counter(str(row.get("status") or "unknown").lower() for row in rows)
    ok_count = sum(count for status, count in statuses.items() if status in _OK_STATUSES)
    non_ok_count = len(rows) - ok_count
    top_rows = sorted(rows, key=lambda row: float(row.get("duration_ms") or 0.0), reverse=True)[
        :_TOP_LATENCY_ROWS_PER_STEP
    ]
    return {
        "step_name": step,
        "count": len(rows),
        "ok_count": ok_count,
        "non_ok_count": non_ok_count,
        "status_counts": dict(sorted(statuses.items())),
        "min_ms": _round_ms(durations[0]) if durations else None,
        "p50_ms": _round_ms(_percentile(durations, 50)),
        "p95_ms": _round_ms(_percentile(durations, 95)),
        "max_ms": _round_ms(durations[-1]) if durations else None,
        "avg_ms": _round_ms(sum(durations) / len(durations)) if durations else None,
        "slow_outlier_count": sum(1 for value in durations if value >= _SLOW_STEP_OUTLIER_MS),
        "timeout_boundary_exceedance_count": sum(1 for value in durations if value >= _DEFAULT_STEP_TIMEOUT_BOUNDARY_MS),
        "top_durations": [_latency_row_excerpt(row) for row in top_rows],
    }


def _latency_row_excerpt(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "duration_ms": _round_ms(row.get("duration_ms")),
        "status": row.get("status"),
        "run_id": row.get("run_id"),
        "episode": row.get("episode"),
        "video_id": row.get("video_id"),
        "scene_id": row.get("scene_id"),
        "scene_index": row.get("scene_index"),
        "ts": row.get("ts"),
    }


def _latency_delta(baseline: Any, candidate: Any) -> Dict[str, Any]:
    baseline_summary = baseline if isinstance(baseline, dict) else {}
    candidate_summary = candidate if isinstance(candidate, dict) else {}
    baseline_steps = _latency_steps_by_name(baseline_summary)
    candidate_steps = _latency_steps_by_name(candidate_summary)
    step_rows: List[Dict[str, Any]] = []

    for step in sorted(set(baseline_steps) | set(candidate_steps)):
        base = baseline_steps.get(step, {})
        cand = candidate_steps.get(step, {})
        row = {
            "step_name": step,
            "baseline_count": int(base.get("count") or 0),
            "candidate_count": int(cand.get("count") or 0),
            "baseline_p50_ms": _round_ms(base.get("p50_ms")),
            "candidate_p50_ms": _round_ms(cand.get("p50_ms")),
            "p50_delta_ms": _delta_ms(base.get("p50_ms"), cand.get("p50_ms")),
            "baseline_p95_ms": _round_ms(base.get("p95_ms")),
            "candidate_p95_ms": _round_ms(cand.get("p95_ms")),
            "p95_delta_ms": _delta_ms(base.get("p95_ms"), cand.get("p95_ms")),
            "baseline_max_ms": _round_ms(base.get("max_ms")),
            "candidate_max_ms": _round_ms(cand.get("max_ms")),
            "max_delta_ms": _delta_ms(base.get("max_ms"), cand.get("max_ms")),
            "slow_outlier_delta": int(cand.get("slow_outlier_count") or 0) - int(base.get("slow_outlier_count") or 0),
            "timeout_boundary_exceedance_delta": int(cand.get("timeout_boundary_exceedance_count") or 0)
            - int(base.get("timeout_boundary_exceedance_count") or 0),
        }
        row["trend_status"] = _latency_trend_status(row)
        step_rows.append(row)

    step_rows.sort(
        key=lambda row: (
            -abs(float(row.get("p95_delta_ms") or 0.0)),
            -abs(float(row.get("max_delta_ms") or 0.0)),
            str(row.get("step_name")),
        )
    )
    return {
        "mode": "read_only_latency_delta",
        "status": "available" if step_rows else "empty",
        "baseline_duration_row_count": int(baseline_summary.get("duration_row_count") or 0),
        "candidate_duration_row_count": int(candidate_summary.get("duration_row_count") or 0),
        "timeout_boundary_ms": _DEFAULT_STEP_TIMEOUT_BOUNDARY_MS,
        "slow_outlier_threshold_ms": _SLOW_STEP_OUTLIER_MS,
        "steps": step_rows,
    }


def _optional_enrichment_coverage_delta(baseline: Any, candidate: Any) -> Dict[str, Any]:
    baseline_summary = baseline if isinstance(baseline, dict) else {}
    candidate_summary = candidate if isinstance(candidate, dict) else {}
    baseline_steps = _optional_coverage_steps_by_name(baseline_summary)
    candidate_steps = _optional_coverage_steps_by_name(candidate_summary)
    rows: List[Dict[str, Any]] = []

    for step in sorted(set(baseline_steps) | set(candidate_steps)):
        base = baseline_steps.get(step, {})
        cand = candidate_steps.get(step, {})
        row = {
            "step_name": step,
            "baseline_total_rows": int(base.get("total_rows") or 0),
            "candidate_total_rows": int(cand.get("total_rows") or 0),
            "total_rows_delta": int(cand.get("total_rows") or 0) - int(base.get("total_rows") or 0),
            "baseline_ok_count": int(base.get("ok_count") or 0),
            "candidate_ok_count": int(cand.get("ok_count") or 0),
            "ok_delta": int(cand.get("ok_count") or 0) - int(base.get("ok_count") or 0),
            "baseline_non_ok_count": int(base.get("non_ok_count") or 0),
            "candidate_non_ok_count": int(cand.get("non_ok_count") or 0),
            "non_ok_delta": int(cand.get("non_ok_count") or 0) - int(base.get("non_ok_count") or 0),
            "baseline_embedding_emitted_count": int(base.get("embedding_emitted_count") or 0),
            "candidate_embedding_emitted_count": int(cand.get("embedding_emitted_count") or 0),
            "embedding_emitted_delta": int(cand.get("embedding_emitted_count") or 0)
            - int(base.get("embedding_emitted_count") or 0),
        }
        row["trend_status"] = _coverage_delta_status(row)
        rows.append(row)

    rows.sort(
        key=lambda row: (
            -abs(int(row.get("non_ok_delta") or 0)),
            -abs(int(row.get("total_rows_delta") or 0)),
            str(row.get("step_name")),
        )
    )
    return {
        "mode": "read_only_optional_enrichment_coverage_delta",
        "status": "available" if rows else "empty",
        "baseline_total_rows": int(baseline_summary.get("total_rows") or 0),
        "candidate_total_rows": int(candidate_summary.get("total_rows") or 0),
        "baseline_non_ok_rows": int(baseline_summary.get("non_ok_rows") or 0),
        "candidate_non_ok_rows": int(candidate_summary.get("non_ok_rows") or 0),
        "steps": rows,
    }


def _optional_coverage_steps_by_name(summary: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in summary.get("steps") or []:
        if not isinstance(row, dict):
            continue
        step = _clean_str(row.get("step_name"))
        if step:
            out[step] = row
    return out


def _coverage_delta_status(row: Dict[str, Any]) -> str:
    baseline_total = int(row.get("baseline_total_rows") or 0)
    candidate_total = int(row.get("candidate_total_rows") or 0)
    if baseline_total <= 0 and candidate_total > 0:
        return "new"
    if baseline_total > 0 and candidate_total <= 0:
        return "resolved"
    non_ok_delta = int(row.get("non_ok_delta") or 0)
    if non_ok_delta > 0:
        return "increased"
    if non_ok_delta < 0:
        return "decreased"
    return "stable"


def _latency_steps_by_name(summary: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in summary.get("steps") or []:
        if not isinstance(row, dict):
            continue
        step = _clean_str(row.get("step_name"))
        if step:
            out[step] = row
    return out


def _latency_trend_status(row: Dict[str, Any]) -> str:
    baseline_count = int(row.get("baseline_count") or 0)
    candidate_count = int(row.get("candidate_count") or 0)
    if baseline_count <= 0 and candidate_count > 0:
        return "new"
    if baseline_count > 0 and candidate_count <= 0:
        return "resolved"
    delta = _coerce_float(row.get("p95_delta_ms"))
    if delta is None:
        return "insufficient_data"
    if delta > 0:
        return "increased"
    if delta < 0:
        return "decreased"
    return "stable"


def _is_wsl_audio_step(step_name: str) -> bool:
    step = step_name.lower()
    return "wsl" in step and "audio" in step


def _phase6_health_summary(episodes: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    rows = list(episodes)
    healthy = bool(rows) and all(bool(row.get("healthy")) for row in rows)
    return {
        "healthy": healthy,
        "status": "healthy" if healthy else ("unknown" if not rows else "degraded"),
        "episodes_total": len(rows),
        "episodes_healthy": sum(1 for row in rows if row.get("healthy")),
        "episodes": rows,
    }


def _infer_recovery_outcome(
    signal: Dict[str, Any],
    health_by_episode: Sequence[Dict[str, Any]],
    all_signals: Sequence[Dict[str, Any]],
) -> str:
    status = str(signal.get("status") or "").lower()
    source = signal.get("source")
    code = signal.get("reason")

    if status in _SKIP_STATUSES:
        return "skipped_expected"
    if source == "run.warnings" and code == "native_crash_retry":
        return "recovered_retry"

    episode_health = next(
        (
            row
            for row in health_by_episode
            if row.get("run_id") == signal.get("run_id")
            or (row.get("video_id") and row.get("video_id") == signal.get("video_id"))
        ),
        None,
    )

    if bool(signal.get("optional")):
        if episode_health and episode_health.get("healthy"):
            return "recovered_optional_continued"
        return "unrecovered_optional_truth_degraded"

    if status in _ERROR_STATUSES:
        if _later_ok_step(signal, all_signals):
            return "recovered_later_ok"
        return "unrecovered"

    if status == "warning":
        return "unknown_warning"
    return "unknown"


def _later_ok_step(signal: Dict[str, Any], all_signals: Sequence[Dict[str, Any]]) -> bool:
    # The report keeps only non-ok step rows, so a native retry warning carries the explicit recovered signal.
    return False


def _classify_error_family(
    *,
    step: str,
    status: str,
    reason: Optional[str],
    message: Optional[str],
    code: Optional[str],
    row: Dict[str, Any],
) -> str:
    reason_s = (reason or "").strip().lower()
    message_s = (message or "").strip().lower()
    code_s = (code or "").strip().lower()

    status_code = _normalize_status_code_hex(row.get("status_code_hex")) if isinstance(row, dict) else None
    return_code = _coerce_int(row.get("return_code")) if isinstance(row, dict) else None
    if return_code is None:
        match = re.search(r"returncode=([-]?\d+)", message_s)
        if match:
            return_code = _coerce_int(match.group(1))
    if not status_code and return_code in _NATIVE_CRASH_CODES:
        status_code = _NATIVE_CRASH_CODES[return_code]

    if code_s == "native_crash_retry":
        return f"native_crash_retry:{status_code or return_code or 'unknown'}"
    if status_code:
        return f"native_subprocess_crash:{status_code}"
    if "timed out" in message_s or "timeout" in reason_s:
        return "timeout"
    if "audio_silent" in reason_s or "audio silent" in message_s:
        return "audio_silent"
    if "too_short" in reason_s or "too short" in message_s:
        return "too_short"
    if "no_text" in reason_s or "no text" in message_s:
        return "no_text"
    if "qdrant" in reason_s or "qdrant" in message_s:
        return "qdrant"
    if "embedding" in step.lower() or "embed" in step.lower():
        if status in _ERROR_STATUSES:
            return "embedding_failure"
        if status in _SKIP_STATUSES:
            return f"embedding_skip:{reason_s or status}"
    if code_s:
        return code_s
    if reason_s:
        return reason_s[:96]
    return status or "unknown"


def _extract_reason(row: Dict[str, Any]) -> Optional[str]:
    extra = row.get("extra")
    if isinstance(extra, dict):
        reason = _clean_str(extra.get("reason"))
        if reason:
            return reason
        nested = _first_nested_reason(extra)
        if nested:
            return nested
    error = _clean_str(row.get("error"))
    if error:
        first = error.splitlines()[0].strip()
        return first[:160] if first else "error"
    return None


def _first_nested_reason(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        reason = _clean_str(value.get("reason")) or _clean_str(value.get("status"))
        if reason and reason.lower() not in _OK_STATUSES:
            return reason
        for child in value.values():
            found = _first_nested_reason(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _first_nested_reason(child)
            if found:
                return found
    return None


def _first_nested_status(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        status = _clean_str(value.get("status"))
        if status:
            return status.lower()
        for child in value.values():
            found = _first_nested_status(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _first_nested_status(child)
            if found:
                return found
    return None


def _load_result_items(path: Optional[Path], files_read: List[str], warnings: List[str]) -> List[Dict[str, Any]]:
    if path is None:
        return []
    payload = _load_json(path, files_read, warnings)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            return [item for item in payload["results"] if isinstance(item, dict)]
        if isinstance(payload.get("videos"), list):
            return [item for item in payload["videos"] if isinstance(item, dict)]
        return [payload]
    return []


def _load_json(path: Optional[Path], files_read: List[str], warnings: List[str]) -> Any:
    if path is None:
        return None
    if not path.is_file():
        warnings.append(f"json_missing: {path}")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        files_read.append(str(path))
        return payload
    except Exception as exc:
        warnings.append(f"json_unreadable: {path}: {exc}")
        return None


def _path_from(value: Any) -> Optional[Path]:
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value)


def _derive_manifest_path(temporal_path: Optional[Path]) -> Optional[Path]:
    if temporal_path is None:
        return None
    return temporal_path.parent / "video" / "scene_manifest.json"


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(_REPO_ROOT))
    except Exception:
        raw = str(path)
    return _sanitize_drive_root(raw)


def _display_text(value: Any) -> str:
    text = str(value)
    try:
        repo_raw = str(_REPO_ROOT.resolve())
        text = text.replace(repo_raw, ".")
    except Exception:
        pass
    return _sanitize_drive_root(text)


def _sanitize_drive_root(text: str) -> str:
    sanitized = re.sub(r"\b[A-Za-z]:[\\/]", "<local>/", text)
    return re.sub(r"\\\\" + r"wsl" + r"\$", "<wsl>", sanitized, flags=re.IGNORECASE)


def _unique_episode_map(pairs: Iterable[Tuple[Optional[str], _EpisodeScope]]) -> Dict[str, _EpisodeScope]:
    buckets: Dict[str, List[_EpisodeScope]] = {}
    for key, episode in pairs:
        clean_key = _clean_str(key)
        if not clean_key:
            continue
        buckets.setdefault(clean_key, []).append(episode)
    return {key: values[0] for key, values in buckets.items() if len(values) == 1}


def _replace_episode_step_path(episode: _EpisodeScope, path: Path) -> _EpisodeScope:
    return _EpisodeScope(
        report_run_id=episode.report_run_id,
        episode=episode.episode,
        run_dir=episode.run_dir,
        runtime_run_id=episode.runtime_run_id,
        video_id=episode.video_id,
        video_hash=episode.video_hash,
        video_name=episode.video_name,
        step_runs_path=path,
        output_path=episode.output_path,
        scene_manifest_path=episode.scene_manifest_path,
        temporal_index_path=episode.temporal_index_path,
        resolved_config_path=episode.resolved_config_path,
        episode_log_path=episode.episode_log_path,
        stdout_path=episode.stdout_path,
        stderr_path=episode.stderr_path,
        output_item_index=episode.output_item_index,
    )


def _clean_str(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _coerce_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None


def _coerce_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _round_ms(value: Any) -> Optional[float]:
    numeric = _coerce_float(value)
    if numeric is None:
        return None
    return round(numeric, 3)


def _delta_ms(baseline: Any, candidate: Any) -> Optional[float]:
    base = _coerce_float(baseline)
    cand = _coerce_float(candidate)
    if base is None or cand is None:
        return None
    return _round_ms(cand - base)


def _percentile(values: Sequence[float], percentile: int) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (float(percentile) / 100.0)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _format_ms_text(value: Any) -> str:
    numeric = _round_ms(value)
    return "n/a" if numeric is None else f"{numeric:.3f}"


def _format_ms_cell(value: Any) -> str:
    numeric = _round_ms(value)
    return "n/a" if numeric is None else f"{numeric:.3f}"


def _nested_get(value: Any, path: Sequence[str]) -> Any:
    cur = value
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _all_known_true(values: Sequence[Any]) -> bool:
    known = [v for v in values if v is not None]
    return bool(known) and all(v is True for v in known)


def _len_list(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _dedupe_strings(values: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        if not isinstance(value, str) or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _coalesce_runtime_event_duplicates(signals: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    native_signals = [signal for signal in signals if _is_native_crash_signal(signal)]
    scene_specific: Dict[Tuple[Any, ...], List[Tuple[Any, Any, Any, Any]]] = {}
    for signal in native_signals:
        if not signal.get("scene_id"):
            continue
        scene_specific.setdefault(_native_run_level_key(signal), []).append(
            (
                signal.get("video_id"),
                signal.get("scene_id"),
                signal.get("scene_index"),
                _native_retry_mode(signal),
            )
        )

    groups: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    passthrough: List[Dict[str, Any]] = []
    for signal in signals:
        if not _is_native_crash_signal(signal):
            passthrough.append(signal)
            continue
        groups.setdefault(_native_coalesce_key(signal, scene_specific), []).append(signal)

    out: List[Dict[str, Any]] = []
    for group in groups.values():
        out.append(_merge_native_crash_signals(group))
    out.extend(passthrough)
    return out


def _is_native_crash_signal(signal: Dict[str, Any]) -> bool:
    family = _clean_str(signal.get("error_family")) or ""
    return family.startswith("native_crash_retry:") or family.startswith("native_subprocess_crash:")


def _native_run_level_key(signal: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        signal.get("run_id"),
        signal.get("step_name"),
        _native_family_code(signal),
        _native_recovery_class(signal),
    )


def _native_coalesce_key(
    signal: Dict[str, Any],
    scene_specific: Dict[Tuple[Any, ...], List[Tuple[Any, Any, Any, Any]]],
) -> Tuple[Any, ...]:
    video_id = signal.get("video_id")
    scene_id = signal.get("scene_id")
    scene_index = signal.get("scene_index")
    retry_mode = _native_retry_mode(signal)
    if not scene_id and signal.get("source") in {"run.warnings", "runtime.stderr"}:
        candidates = scene_specific.get(_native_run_level_key(signal), [])
        unique_candidates = list(dict.fromkeys(candidates))
        if len(unique_candidates) == 1:
            video_id, scene_id, scene_index, candidate_retry_mode = unique_candidates[0]
            retry_mode = retry_mode or candidate_retry_mode
    elif scene_id and not retry_mode:
        retry_mode = _native_retry_mode_for_scene(signal, scene_specific)
    return (
        signal.get("run_id"),
        video_id,
        scene_id,
        scene_index,
        signal.get("step_name"),
        _native_family_code(signal),
        _native_recovery_class(signal),
        retry_mode,
    )


def _native_retry_mode(signal: Dict[str, Any]) -> Optional[str]:
    return _clean_str(signal.get("retry_mode")) or None


def _native_retry_mode_for_scene(
    signal: Dict[str, Any],
    scene_specific: Dict[Tuple[Any, ...], List[Tuple[Any, Any, Any, Any]]],
) -> Optional[str]:
    candidates = scene_specific.get(_native_run_level_key(signal), [])
    modes = [
        retry_mode
        for video_id, scene_id, scene_index, retry_mode in candidates
        if retry_mode
        and (not signal.get("video_id") or video_id == signal.get("video_id"))
        and scene_id == signal.get("scene_id")
        and (signal.get("scene_index") is None or scene_index == signal.get("scene_index"))
    ]
    unique_modes = list(dict.fromkeys(modes))
    return unique_modes[0] if len(unique_modes) == 1 else None


def _native_family_code(signal: Dict[str, Any]) -> str:
    family = _clean_str(signal.get("error_family")) or ""
    if ":" in family:
        return family.split(":", 1)[1] or "unknown"
    return "unknown"


def _native_recovery_class(signal: Dict[str, Any]) -> str:
    recovery = _clean_str(signal.get("recovery_outcome")) or ""
    if recovery.startswith("unrecovered"):
        return "unrecovered"
    if recovery.startswith("recovered"):
        return "recovered"
    status = str(signal.get("status") or "").lower()
    if status in _ERROR_STATUSES:
        return "unrecovered"
    if status == "warning":
        return "recovered"
    return recovery or "unknown"


def _merge_native_crash_signals(group: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    ordered = list(group)
    if len(ordered) == 1:
        signal = dict(ordered[0])
        signal["sources"] = _signal_surface_names(signal)
        return signal

    preferred = _preferred_native_signal(ordered)
    merged = dict(preferred)
    sources = _dedupe_strings(source for signal in ordered for source in _signal_surface_names(signal))
    unrecovered = any(_native_recovery_class(signal) == "unrecovered" for signal in ordered)
    code = _native_family_code(preferred)
    if unrecovered:
        merged["error_family"] = f"native_subprocess_crash:{code}"
        merged["status"] = "error"
        merged["recovery_outcome"] = "unrecovered"
    else:
        merged["error_family"] = f"native_crash_retry:{code}"
        merged["status"] = "warning"
        merged["reason"] = "native_crash_retry"
        merged["recovery_outcome"] = _preferred_recovered_outcome(ordered)
    merged["source"] = "coalesced.native_retry"
    merged["sources"] = sources
    merged["source_count"] = len(sources)
    merged["optional"] = any(bool(signal.get("optional")) for signal in ordered)
    merged["provenance"] = {"surfaces": sources}

    for field in (
        "video_id",
        "scene_id",
        "scene_index",
        "run_id",
        "episode",
        "report_run_id",
        "step_name",
        "ts",
        "env",
        "env_fingerprint",
        "return_code",
        "retry_mode",
    ):
        if not merged.get(field):
            merged[field] = next((signal.get(field) for signal in ordered if signal.get(field)), merged.get(field))
    return merged


def _preferred_native_signal(signals: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    source_rank = {
        "step_runs.jsonl": 0,
        "runtime.events": 1,
        "run.warnings": 2,
        "runtime.stderr": 3,
    }
    return sorted(
        signals,
        key=lambda signal: (
            source_rank.get(str(signal.get("source")), 9),
            0 if signal.get("scene_id") else 1,
            str(signal.get("ts") or ""),
        ),
    )[0]


def _preferred_recovered_outcome(signals: Sequence[Dict[str, Any]]) -> str:
    outcomes = [_clean_str(signal.get("recovery_outcome")) for signal in signals]
    if "recovered_retry" in outcomes:
        return "recovered_retry"
    if "recovered_optional_continued" in outcomes:
        return "recovered_optional_continued"
    return next((outcome for outcome in outcomes if outcome and outcome.startswith("recovered")), "recovered_retry")


def _signal_surface_names(signal: Dict[str, Any]) -> List[str]:
    sources = signal.get("sources")
    if isinstance(sources, list):
        return [str(source) for source in sources if str(source).strip()]
    source = _clean_str(signal.get("source"))
    return [source] if source else []


def _is_scene_less_native_retry_signal(signal: Dict[str, Any]) -> bool:
    if signal.get("source") not in {"run.warnings", "runtime.stderr"}:
        return False
    if signal.get("scene_id"):
        return False
    family = _clean_str(signal.get("error_family")) or ""
    return family.startswith("native_crash_retry:") or family.startswith("native_subprocess_crash:")


def _dedupe_paths(values: Iterable[Path]) -> List[Path]:
    seen = set()
    out: List[Path] = []
    for value in values:
        key = os.path.normcase(str(value))
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _dedupe_signals(signals: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for signal in signals:
        video_id = None if _is_scene_less_native_retry_signal(signal) else signal.get("video_id")
        key = (
            signal.get("source"),
            signal.get("run_id"),
            video_id,
            signal.get("step_name"),
            signal.get("status"),
            signal.get("reason"),
            signal.get("scene_id"),
            signal.get("ts"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(signal)
    return out


def _text_row_defaults(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "count": row.get("count", 0),
        "run_id": row.get("run_id") or "unknown",
        "episode": row.get("episode") or "unknown",
        "step_name": row.get("step_name") or "unknown",
        "status": row.get("status") or "unknown",
        "reason": row.get("reason") or "unknown",
        "error_family": row.get("error_family") or "unknown",
        "category": row.get("category") or "unknown",
        "scene_id": row.get("scene_id") or "run-level",
        "recovery_outcome": row.get("recovery_outcome") or "unknown",
    }
