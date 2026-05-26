from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


FIELDS = ("visual_caption", "sentiment", "clap_meta")
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def repair_projection_gaps(temporal_payload: Dict[str, Any], scene_results_payload: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Project existing scene-result truth into missing temporal-index fields."""

    repaired = copy.deepcopy(temporal_payload)
    segments = repaired.get("segments")
    if not isinstance(segments, list):
        return repaired, _summary("unavailable", "temporal_segments_missing")

    scene_records = _scene_records(scene_results_payload)
    if not scene_records:
        return repaired, _summary("unavailable", "scene_records_missing")

    segments_by_id = _segments_by_id(segments)
    counts = {field: 0 for field in FIELDS}
    sample_updates: List[Dict[str, Any]] = []

    for index, scene in enumerate(scene_records):
        if not isinstance(scene, dict):
            continue
        segment = _matching_segment(scene, index, segments, segments_by_id)
        if not isinstance(segment, dict):
            continue

        changed_fields: List[str] = []
        if not _observed(segment.get("visual_caption")):
            visual_caption = _first_observed(
                scene.get("visual_caption"),
                scene.get("caption"),
                _dict_value(scene.get("keyframe"), "caption"),
            )
            if _observed(visual_caption):
                segment["visual_caption"] = visual_caption
                counts["visual_caption"] += 1
                changed_fields.append("visual_caption")

        sentiment_changed = _project_sentiment(segment, scene)
        if sentiment_changed:
            counts["sentiment"] += 1
            changed_fields.append("sentiment")

        if not _observed(segment.get("clap_meta")):
            clap_meta = _first_observed(scene.get("clap_meta"), _dict_value(scene.get("audio"), "clap_meta"))
            if _observed(clap_meta):
                segment["clap_meta"] = copy.deepcopy(clap_meta)
                counts["clap_meta"] += 1
                changed_fields.append("clap_meta")

        if changed_fields and len(sample_updates) < 8:
            sample_updates.append({"scene_id": _scene_label(scene, index), "fields": changed_fields})

    total_updates = sum(counts.values())
    status = "updated" if total_updates else "no_change"
    return repaired, {
        "status": status,
        "fields": counts,
        "total_updates": total_updates,
        "scene_scope_count": len(scene_records),
        "temporal_scene_count": len(segments),
        "sample_updates": sample_updates,
    }


def apply_projection_repair(*, temporal_index_path: Path, scene_results_path: Path, write: bool = False) -> Dict[str, Any]:
    temporal_payload = _load_json(temporal_index_path)
    scene_results_payload = _load_json(scene_results_path)
    repaired, summary = repair_projection_gaps(temporal_payload, scene_results_payload)

    result: Dict[str, Any] = {
        "mode": "write" if write else "dry_run",
        "status": summary["status"],
        "write_performed": False,
        "backup_path": None,
        "temporal_index_path": _redacted_path_label(temporal_index_path),
        "scene_results_path": _redacted_path_label(scene_results_path),
        "summary": summary,
    }

    if not write or summary["status"] != "updated":
        return result

    backup_path = _backup_path(temporal_index_path)
    shutil.copy2(temporal_index_path, backup_path)
    _atomic_write_json(temporal_index_path, repaired)
    result["write_performed"] = True
    result["backup_path"] = _redacted_path_label(backup_path)
    return result


def latest_run_artifact_paths() -> Tuple[Path, Path]:
    from api.routes import runtime
    from lib import run_index, run_summary

    runs = run_index.list_runs(limit=1)
    if not runs:
        raise FileNotFoundError("No indexed runs found.")
    latest = runs[0]
    summary = run_summary.load_run_summary(run_root=latest.get("run_root") or latest["run_id"])
    latest_episode = summary.get("latest_episode") if isinstance(summary.get("latest_episode"), dict) else {}
    temporal_path = runtime._episode_artifact_path(latest_episode, "temporal_index.json")
    scene_results_path = runtime._episode_artifact_path(latest_episode, "scene_ingest_results.json")
    if temporal_path is None or scene_results_path is None:
        raise FileNotFoundError("Latest run is missing temporal_index.json or scene_ingest_results.json.")
    return temporal_path, scene_results_path


def _project_sentiment(segment: Dict[str, Any], scene: Dict[str, Any]) -> bool:
    if _observed(segment.get("sentiment")) or _observed(segment.get("sentiment_label")) or _observed(segment.get("sentiment_score")):
        return False

    audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
    sentiment = _first_observed(scene.get("sentiment"), audio.get("sentiment"))
    label = _first_observed(
        scene.get("sentiment_label"),
        _dict_value(sentiment, "label"),
        audio.get("sentiment_label"),
    )
    score = _first_observed(
        scene.get("sentiment_score"),
        _dict_value(sentiment, "score"),
        audio.get("sentiment_score"),
    )

    changed = False
    if isinstance(sentiment, dict) and sentiment:
        segment["sentiment"] = copy.deepcopy(sentiment)
        changed = True
    if _observed(label):
        segment["sentiment_label"] = label
        changed = True
    if _observed(score):
        segment["sentiment_score"] = score
        changed = True
    return changed


def _scene_records(payload: Any) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    containers = payload if isinstance(payload, list) else [payload]
    for container in containers:
        if not isinstance(container, dict):
            continue
        scenes = container.get("scenes")
        if isinstance(scenes, list):
            records.extend(scene for scene in scenes if isinstance(scene, dict))
        results = container.get("results")
        if isinstance(results, list):
            records.extend(scene for scene in results if isinstance(scene, dict))
    if records:
        return records
    if isinstance(payload, list):
        return [scene for scene in payload if isinstance(scene, dict)]
    return []


def _segments_by_id(segments: List[Any]) -> Dict[str, Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        for candidate in _id_candidates(segment):
            by_id.setdefault(candidate, segment)
    return by_id


def _matching_segment(scene: Dict[str, Any], index: int, segments: List[Any], segments_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any] | None:
    for candidate in _id_candidates(scene):
        segment = segments_by_id.get(candidate)
        if isinstance(segment, dict):
            return segment
    if 0 <= index < len(segments) and isinstance(segments[index], dict):
        return segments[index]
    return None


def _id_candidates(record: Dict[str, Any]) -> List[str]:
    candidates: List[str] = []
    for key in ("scene_id", "id", "segment_id"):
        value = record.get(key)
        if value is not None and str(value).strip():
            candidates.append(str(value).strip())
    for key in ("index", "scene_index"):
        value = record.get(key)
        if value is None:
            continue
        try:
            candidates.append(f"scene_{int(value):04d}")
        except Exception:
            text = str(value).strip()
            if text:
                candidates.append(text)
    return list(dict.fromkeys(candidates))


def _scene_label(scene: Dict[str, Any], index: int) -> str:
    for key in ("scene_id", "id"):
        value = scene.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return f"scene_{index:04d}"


def _first_observed(*values: Any) -> Any:
    for value in values:
        if _observed(value):
            return value
    return None


def _dict_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return None


def _observed(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list, tuple, set)):
        return bool(value)
    return True


def _load_json(path: Path) -> Any:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Unable to read JSON artifact {path.name}: {exc}") from exc
    if not isinstance(payload, (dict, list)):
        raise ValueError(f"JSON artifact must be an object or list: {path.name}")
    return payload


def _backup_path(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return path.with_name(f"{path.name}.bak-{stamp}")


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _redacted_path_label(path: Path) -> str:
    parent = path.parent.name or "<artifact-root>"
    return f"<redacted>/{parent}/{path.name}"


def _summary(status: str, reason: str) -> Dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "fields": {field: 0 for field in FIELDS},
        "total_updates": 0,
        "scene_scope_count": 0,
        "temporal_scene_count": 0,
        "sample_updates": [],
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Repair missing temporal-index projections from scene_ingest_results source truth.")
    parser.add_argument("--latest-run", action="store_true", help="Use the latest indexed run artifacts.")
    parser.add_argument("--temporal-index", type=Path, help="Path to temporal_index.json.")
    parser.add_argument("--scene-results", type=Path, help="Path to scene_ingest_results.json.")
    parser.add_argument("--write", action="store_true", help="Write repaired temporal_index.json after creating a sibling backup.")
    args = parser.parse_args(argv)

    if args.latest_run:
        temporal_path, scene_results_path = latest_run_artifact_paths()
    else:
        if args.temporal_index is None or args.scene_results is None:
            parser.error("Either --latest-run or both --temporal-index and --scene-results are required.")
        temporal_path = args.temporal_index
        scene_results_path = args.scene_results

    result = apply_projection_repair(
        temporal_index_path=temporal_path,
        scene_results_path=scene_results_path,
        write=bool(args.write),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
