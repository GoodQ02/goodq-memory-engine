"""Bound historical transcript timestamps to their canonical scene audio."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from steps.common.atomic_io import atomic_write_json_for_concurrent_readers
from steps.common.config_loader import load_configs


OVERSHOOT_SECONDS = 5.0
TIMESTAMPED_FIELDS = ("segments", "word_timestamps", "speaker_transcript")


class TranscriptTimestampReconciliationError(RuntimeError):
    """A historical timestamp repair cannot be applied safely."""


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TranscriptTimestampReconciliationError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TranscriptTimestampReconciliationError(f"expected JSON object: {path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _scene_id(value: dict[str, Any]) -> str:
    return str(value.get("scene_id") or value.get("id") or "")


def _timed_items(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _max_end(items: list[dict[str, Any]]) -> float:
    values: list[float] = []
    for item in items:
        try:
            end = float(item.get("end"))
        except (TypeError, ValueError):
            continue
        if math.isfinite(end):
            values.append(end)
    return max(values, default=0.0)


def _target_details(scene: dict[str, Any]) -> dict[str, Any] | None:
    audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
    try:
        duration = float(scene.get("duration"))
    except (TypeError, ValueError):
        return None
    segments = _timed_items(audio.get("segments"))
    max_end = _max_end(segments)
    if not _scene_id(scene) or duration <= 0 or max_end <= duration + OVERSHOOT_SECONDS:
        return None
    return {
        "duration_seconds": duration,
        "original_max_segment_end": max_end,
        "overshoot_seconds": max_end - duration,
    }


def _bounded_items(items: list[dict[str, Any]], duration: float) -> tuple[list[dict[str, Any]], int, int]:
    bounded: list[dict[str, Any]] = []
    clipped = 0
    dropped = 0
    for item in items:
        try:
            start = float(item.get("start"))
            end = float(item.get("end"))
        except (TypeError, ValueError):
            dropped += 1
            continue
        if not (math.isfinite(start) and math.isfinite(end)):
            dropped += 1
            continue
        new_start = min(duration, max(0.0, start))
        new_end = min(duration, max(0.0, end))
        if new_end <= new_start:
            dropped += 1
            continue
        updated = dict(item)
        updated["start"] = new_start
        updated["end"] = new_end
        if new_start != start or new_end != end:
            clipped += 1
        bounded.append(updated)
    return bounded, clipped, dropped


def _projection(scene: dict[str, Any]) -> dict[str, Any]:
    audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
    segments = _timed_items(audio.get("segments"))
    text_parts = [str(item.get("text") or "").strip() for item in segments]
    full_text = " ".join(part for part in text_parts if part)
    return {
        "full_transcript": full_text,
        "transcript_segments": [part for part in text_parts if part],
        "has_transcript": bool(full_text),
    }


def _entry(scene: dict[str, Any], manifest_path: Path, temporal_path: Path) -> dict[str, Any]:
    details = _target_details(scene)
    if details is None:
        raise TranscriptTimestampReconciliationError(f"scene is not a timestamp target: {_scene_id(scene)}")
    return {
        "scene_id": _scene_id(scene),
        "manifest_path": str(manifest_path),
        "temporal_path": str(temporal_path),
        **details,
        "scene_digest": _digest(scene),
    }


def build_plan(processing_root: Path, scene_ids: set[str] | None = None) -> dict[str, Any]:
    """Inspect timestamp overshoots; no mutation occurs here."""
    requested = set(scene_ids or ())
    found: set[str] = set()
    files: dict[Path, dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    for manifest_path in sorted(processing_root.glob("*/video/scene_manifest.json")):
        temporal_path = manifest_path.parent.parent / "temporal_index.json"
        if not temporal_path.is_file():
            continue
        manifest, temporal = _read(manifest_path), _read(temporal_path)
        temporal_ids = {_scene_id(item) for item in temporal.get("segments", []) if isinstance(item, dict)}
        for scene in manifest.get("scenes", []):
            if not isinstance(scene, dict):
                continue
            scene_id = _scene_id(scene)
            if requested and scene_id not in requested:
                continue
            if _target_details(scene) is None:
                continue
            if scene_id not in temporal_ids:
                raise TranscriptTimestampReconciliationError(f"temporal segment missing: {scene_id}")
            files.setdefault(manifest_path, {
                "manifest_path": str(manifest_path),
                "temporal_path": str(temporal_path),
                "manifest_sha256": _sha(manifest_path),
                "temporal_sha256": _sha(temporal_path),
            })
            entries.append(_entry(scene, manifest_path, temporal_path))
            found.add(scene_id)
    if requested - found:
        raise TranscriptTimestampReconciliationError(
            f"requested scenes are not timestamp targets: {sorted(requested - found)}"
        )
    if not entries:
        raise TranscriptTimestampReconciliationError("no historical timestamp overshoots found")
    return {
        "status": "ready",
        "kind": "historical_transcript_timestamp_reconciliation",
        "processing_root": str(processing_root),
        "scene_count": len(entries),
        "file_count": len(files),
        "overshoot_threshold_seconds": OVERSHOOT_SECONDS,
        "files": [files[path] for path in sorted(files)],
        "scenes": sorted(entries, key=lambda item: item["scene_id"]),
        "write_scope": [
            "scene.audio.segments", "scene.audio.word_timestamps", "scene.audio.speaker_transcript",
            "scene.audio.full_text", "scene.audio.transcript", "scene.audio.transcription_timing",
            "temporal_index.segments[scene_id].full_transcript",
            "temporal_index.segments[scene_id].transcript_segments",
            "temporal_index.segments[scene_id].has_transcript",
        ],
        "non_effects": [
            "no_wsl", "no_media_processing", "no_transcription", "no_diarization", "no_embeddings",
            "no_vectors", "no_sqlite", "no_graph", "no_reingestion",
        ],
    }


def plan_digest(plan: dict[str, Any]) -> str:
    return _digest({key: value for key, value in plan.items() if key != "status"})


def _apply(scene: dict[str, Any]) -> dict[str, Any]:
    audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else None
    details = _target_details(scene)
    if not isinstance(audio, dict) or details is None:
        raise TranscriptTimestampReconciliationError(f"scene authority changed: {_scene_id(scene)}")
    duration = float(details["duration_seconds"])
    clipped = dropped = 0
    for field in TIMESTAMPED_FIELDS:
        if field not in audio:
            continue
        bounded, field_clipped, field_dropped = _bounded_items(_timed_items(audio.get(field)), duration)
        audio[field] = bounded
        clipped += field_clipped
        dropped += field_dropped
    projection = _projection(scene)
    for field in ("full_text", "transcript"):
        if field in audio:
            audio[field] = projection["full_transcript"]
    audio["transcription_timing"] = {
        "status": "reconciled_to_audio_bounds",
        "input_duration_seconds": duration,
        "original_max_segment_end": details["original_max_segment_end"],
        "clipped_segment_count": clipped,
        "dropped_segment_count": dropped,
        "provenance": "historical_metadata_reconciliation",
    }
    return projection


def execute_plan(plan: dict[str, Any], confirmation_token: str) -> dict[str, Any]:
    if plan.get("status") != "ready" or confirmation_token != plan_digest(plan):
        raise TranscriptTimestampReconciliationError("confirmation token does not match inspected plan")
    files = plan.get("files")
    entries = plan.get("scenes")
    if not isinstance(files, list) or not isinstance(entries, list) or not entries:
        raise TranscriptTimestampReconciliationError("plan is structurally incomplete")
    epoch_root = Path(str(plan["processing_root"])).resolve().parent
    operation_id = (
        "transcript_timestamp_reconciliation_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{confirmation_token[:12]}"
    )
    receipt_root = epoch_root / "transcript_timestamp_reconciliations" / operation_id
    backup_root = receipt_root / "backup"
    backup_root.mkdir(parents=True, exist_ok=False)
    originals: dict[Path, bytes] = {}
    payloads: dict[Path, dict[str, Any]] = {}
    try:
        for index, detail in enumerate(files):
            for label in ("manifest", "temporal"):
                path = Path(str(detail[f"{label}_path"])).resolve()
                if _sha(path) != detail[f"{label}_sha256"]:
                    raise TranscriptTimestampReconciliationError("authority changed after planning")
                originals[path] = path.read_bytes()
                (backup_root / f"{index:02d}_{label}.json").write_bytes(originals[path])
                payloads[path] = _read(path)
        for entry in entries:
            manifest = payloads[Path(str(entry["manifest_path"])).resolve()]
            temporal = payloads[Path(str(entry["temporal_path"])).resolve()]
            scenes = [item for item in manifest.get("scenes", []) if isinstance(item, dict) and _scene_id(item) == entry["scene_id"]]
            segments = [item for item in temporal.get("segments", []) if isinstance(item, dict) and _scene_id(item) == entry["scene_id"]]
            if len(scenes) != 1 or len(segments) != 1 or _digest(scenes[0]) != entry["scene_digest"]:
                raise TranscriptTimestampReconciliationError(f"scene authority changed: {entry['scene_id']}")
            projection = _apply(scenes[0])
            segments[0].update(projection)
        for path, payload in payloads.items():
            atomic_write_json_for_concurrent_readers(path, payload)
    except Exception as exc:
        for path, raw in originals.items():
            path.write_bytes(raw)
        raise TranscriptTimestampReconciliationError(f"reconciliation rolled back: {exc}") from exc
    receipt = {
        "status": "transcript_timestamp_reconciliation_committed",
        "operation_id": operation_id,
        "plan_digest": confirmation_token,
        "scene_count": len(entries),
        "file_count": len(files),
        "backup_root": str(backup_root),
        "changed_scene_ids": [item["scene_id"] for item in entries],
        "write_scope": plan["write_scope"],
        "non_effects": plan["non_effects"],
    }
    atomic_write_json_for_concurrent_readers(receipt_root / "receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processing-root", type=Path)
    parser.add_argument("--scene-id", action="append", default=[])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation-token")
    args = parser.parse_args()
    root = args.processing_root or Path(load_configs()["paths"]["processing"])
    try:
        plan = build_plan(root, set(args.scene_id) if args.scene_id else None)
        token = plan_digest(plan)
        print(json.dumps(execute_plan(plan, args.confirmation_token) if args.execute else {"plan": plan, "confirmation_token": token}, indent=2))
        return 0
    except TranscriptTimestampReconciliationError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
