from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, Iterable, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = REPO_ROOT / "reports" / "segmentation_shadow_campaign.json"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "technical" / "SEG_P5_PROMOTION_ENVELOPE.md"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _numeric(values: Iterable[Any]) -> List[float]:
    return [float(value) for value in values if isinstance(value, (int, float))]


def _stats(values: Iterable[Any]) -> Dict[str, Optional[float]]:
    nums = _numeric(values)
    if not nums:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None}
    return {
        "count": len(nums),
        "mean": float(mean(nums)),
        "median": float(median(nums)),
        "min": float(min(nums)),
        "max": float(max(nums)),
    }


def _threshold_floor(stats: Dict[str, Optional[float]], *, min_margin: float) -> Optional[float]:
    low = stats.get("min")
    high = stats.get("max")
    if not isinstance(low, float) or not isinstance(high, float):
        return None
    spread = max(0.0, high - low)
    margin = max(min_margin, spread * 0.10)
    return round(max(0.0, low - margin), 3)


def _threshold_ceiling(stats: Dict[str, Optional[float]], *, min_margin: float) -> Optional[float]:
    low = stats.get("min")
    high = stats.get("max")
    if not isinstance(low, float) or not isinstance(high, float):
        return None
    spread = max(0.0, high - low)
    margin = max(min_margin, spread * 0.10)
    return round(high + margin, 3)


def _scene_delta_window(stats: Dict[str, Optional[float]]) -> Optional[Dict[str, int]]:
    low = stats.get("min")
    high = stats.get("max")
    if not isinstance(low, float) or not isinstance(high, float):
        return None
    spread = max(0.0, high - low)
    margin = max(1.0, spread * 0.10)
    return {
        "min": int(round(low - margin)),
        "max": int(round(high + margin)),
    }


def build_envelope(report: Dict[str, Any]) -> Dict[str, Any]:
    episodes = [
        episode
        for episode in report.get("episodes", [])
        if isinstance(episode, dict) and episode.get("status") == "ok"
    ]
    metric_stats = {
        "scene_backend_match_ratio_live": _stats(
            episode.get("scene_backend_match_ratio_live") for episode in episodes
        ),
        "scene_backend_duration_coverage": _stats(
            episode.get("scene_backend_duration_coverage") for episode in episodes
        ),
        "scene_backend_boundary_delta_mean_sec": _stats(
            episode.get("scene_backend_boundary_delta_mean_sec") for episode in episodes
        ),
        "scene_count_delta": _stats(episode.get("scene_count_delta") for episode in episodes),
        "scene_count_live": _stats(episode.get("scene_count_live") for episode in episodes),
        "scene_count_shadow": _stats(episode.get("scene_count_shadow") for episode in episodes),
    }

    thresholds = {
        "scene_backend_match_ratio_live_min": _threshold_floor(
            metric_stats["scene_backend_match_ratio_live"],
            min_margin=0.01,
        ),
        "scene_backend_duration_coverage_min": _threshold_floor(
            metric_stats["scene_backend_duration_coverage"],
            min_margin=0.02,
        ),
        "scene_backend_boundary_delta_mean_sec_max": _threshold_ceiling(
            metric_stats["scene_backend_boundary_delta_mean_sec"],
            min_margin=0.5,
        ),
        "scene_count_delta_expected_window": _scene_delta_window(metric_stats["scene_count_delta"]),
    }

    return {
        "generated_at": _utc_now_iso(),
        "source_report": report.get("report_path"),
        "campaign_id": report.get("campaign_id"),
        "episode_count": len(episodes),
        "metric_stats": metric_stats,
        "thresholds": thresholds,
    }


def render_envelope_markdown(report: Dict[str, Any], envelope: Dict[str, Any]) -> str:
    episodes = [
        episode
        for episode in report.get("episodes", [])
        if isinstance(episode, dict) and episode.get("status") == "ok"
    ]
    thresholds = envelope["thresholds"]
    scene_delta_window = thresholds["scene_count_delta_expected_window"]

    lines: List[str] = [
        "<!-- DOC_BADGE: CANONICAL -->",
        "<!-- DOC_STATUS: AUTHORITATIVE -->",
        f"<!-- DOC_LAST_VERIFIED: {datetime.now().date().isoformat()} -->",
        "",
        "# SEG_P5 Promotion Envelope",
        "",
        f"- Generated: `{envelope['generated_at']}`",
        f"- Source report: `{report.get('report_path')}`",
        f"- Campaign id: `{report.get('campaign_id')}`",
        f"- Successful episodes: `{envelope['episode_count']}`",
        "",
        "## Campaign Witnesses",
        "",
        "| Episode | Live Scenes | Shadow Scenes | Match Ratio | Duration Coverage | Boundary Delta Mean (s) |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    for episode in episodes:
        lines.append(
            "| {episode} | {live} | {shadow} | {match:.3f} | {coverage:.3f} | {delta:.3f} |".format(
                episode=episode.get("episode_name"),
                live=episode.get("scene_count_live"),
                shadow=episode.get("scene_count_shadow"),
                match=float(episode.get("scene_backend_match_ratio_live") or 0.0),
                coverage=float(episode.get("scene_backend_duration_coverage") or 0.0),
                delta=float(episode.get("scene_backend_boundary_delta_mean_sec") or 0.0),
            )
        )

    lines.extend(
        [
            "",
            "## Aggregate Statistics",
            "",
            "| Metric | Mean | Median | Min | Max |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )

    for metric_name, stats in envelope["metric_stats"].items():
        if stats["count"] == 0:
            continue
        lines.append(
            "| {name} | {mean:.3f} | {median:.3f} | {min:.3f} | {max:.3f} |".format(
                name=metric_name,
                mean=float(stats["mean"] or 0.0),
                median=float(stats["median"] or 0.0),
                min=float(stats["min"] or 0.0),
                max=float(stats["max"] or 0.0),
            )
        )

    lines.extend(
        [
            "",
            "## Proposed Manual Promotion Envelope",
            "",
            "These numbers are advisory gates for manual review only. They do not introduce any auto-promotion logic.",
            "",
            f"- `scene_backend_match_ratio_live >= {thresholds['scene_backend_match_ratio_live_min']}`",
            f"- `scene_backend_duration_coverage >= {thresholds['scene_backend_duration_coverage_min']}`",
            f"- `scene_backend_boundary_delta_mean_sec <= {thresholds['scene_backend_boundary_delta_mean_sec_max']}`",
        ]
    )
    if isinstance(scene_delta_window, dict):
        lines.append(
            "- `scene_count_delta expected window = [{min}, {max}]`".format(
                min=scene_delta_window["min"],
                max=scene_delta_window["max"],
            )
        )

    lines.extend(
        [
            "",
            "## Derivation Method",
            "",
            "- Floors are `observed_min - max(fixed_margin, spread * 10%)`.",
            "- Ceilings are `observed_max + max(fixed_margin, spread * 10%)`.",
            "- The scene-count delta window preserves the witnessed range with a small symmetric buffer.",
            "- Promotion remains manual: `OFF`, `SHADOW`, and `AUTHORITATIVE` continue to be orchestration decisions owned by `cli/run_ingestion.py`.",
        ]
    )

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Derive a manual SEG_P5 promotion envelope from the shadow campaign report.")
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    envelope = build_envelope(report)
    output = render_envelope_markdown(report, envelope)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    print(json.dumps({"output": str(args.output), "episode_count": envelope["episode_count"]}, indent=2))


if __name__ == "__main__":
    main()
