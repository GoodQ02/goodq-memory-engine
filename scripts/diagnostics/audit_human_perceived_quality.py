"""Read-only audit of scene evidence quality and human-review readiness.

This script deliberately measures evidence availability, explainability, and
projection coherence.  It does not score a person's memories or claim that an
automatic heuristic can replace human review.  Its output is a compact quality
ledger plus a deterministic queue of scene evidence packets for operator review.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from steps.common.config_loader import load_configs


DEFAULT_SEGMENT_OVERSHOOT_SECONDS = 5.0
HUMAN_REVIEW_LIMIT_PER_REASON = 5


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _scene_text(scene: dict[str, Any]) -> str:
    audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
    return str(audio.get("full_text") or audio.get("transcript") or "").strip()


def _signature_meta(scene: dict[str, Any]) -> dict[str, Any]:
    audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
    value = scene.get("speaker_voice_signature_meta") or audio.get(
        "speaker_voice_signature_meta"
    )
    return value if isinstance(value, dict) else {}


def _speaker_ids(scene: dict[str, Any]) -> list[str]:
    """Mirror the harmonizer's scene-payload speaker precedence, read-only."""
    audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
    values: list[Any] = [scene.get("speaker_ids"), audio.get("speakers")]
    values.extend(audio.get(key) for key in ("speaker_transcript", "speaker_segments", "diarization"))
    result: list[str] = []
    for raw_values in values:
        if not isinstance(raw_values, list):
            continue
        for raw in raw_values:
            value = raw if isinstance(raw, str) else raw.get("speaker", raw.get("label")) if isinstance(raw, dict) else None
            if isinstance(value, str) and value.strip() and value.strip() not in result:
                result.append(value.strip())
    return result


def _review_packet(scene: dict[str, Any], video_id: str, reasons: list[str]) -> dict[str, Any]:
    audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
    frame_path = scene.get("representative_frame") or (scene.get("keyframe") or {}).get("path")
    audio_path = audio.get("path")
    return {
        "scene_id": str(scene.get("scene_id") or ""),
        "video_id": video_id,
        "reasons": reasons,
        "duration_seconds": scene.get("duration"),
        "transcript_characters": len(_scene_text(scene)),
        "representative_frame_present": bool(frame_path),
        "representative_frame_available": bool(frame_path and Path(str(frame_path)).exists()),
        "audio_artifact_present": bool(audio_path),
        "audio_artifact_available": bool(audio_path and Path(str(audio_path)).exists()),
    }


def _add_review(
    queue: dict[str, list[dict[str, Any]]],
    reason: str,
    packet: dict[str, Any],
    *,
    full_ledger: dict[str, list[dict[str, Any]]] | None = None,
) -> None:
    if full_ledger is not None:
        full_ledger.setdefault(reason, []).append(packet)
    entries = queue.setdefault(reason, [])
    if len(entries) < HUMAN_REVIEW_LIMIT_PER_REASON:
        entries.append(packet)


def _load_recovered_scene_ids(receipt_path: Path | None) -> set[str]:
    if receipt_path is None:
        return set()
    receipt = _read_json(receipt_path)
    ids = receipt.get("changed_scene_ids")
    if not isinstance(ids, list) or not all(isinstance(value, str) for value in ids):
        raise ValueError("receipt must contain changed_scene_ids as a string list")
    return set(ids)


def build_quality_report(
    processing_root: Path,
    *,
    receipt_path: Path | None = None,
    segment_overshoot_seconds: float = DEFAULT_SEGMENT_OVERSHOOT_SECONDS,
    full_review_ledger: bool = False,
) -> dict[str, Any]:
    """Return a read-only quality ledger for canonical scene manifests."""
    manifests = sorted(processing_root.glob("*/video/scene_manifest.json"))
    recovered_scene_ids = _load_recovered_scene_ids(receipt_path)
    counts: Counter[str] = Counter()
    signature_status: Counter[str] = Counter()
    temporal: Counter[str] = Counter()
    review_queue: dict[str, list[dict[str, Any]]] = {}
    review_ledger: dict[str, list[dict[str, Any]]] | None = {} if full_review_ledger else None

    for manifest_path in manifests:
        manifest = _read_json(manifest_path)
        video_id = str(manifest.get("video_id") or manifest_path.parent.parent.name)
        temporal_path = manifest_path.parent.parent / "temporal_index.json"
        temporal_index = _read_json(temporal_path) if temporal_path.exists() else {}
        temporal_segments = {
            str(segment.get("scene_id")): segment
            for segment in temporal_index.get("segments", [])
            if isinstance(segment, dict) and segment.get("scene_id") is not None
        }
        counts["videos"] += 1
        counts["temporal_indexes_present"] += temporal_path.exists()

        for scene in manifest.get("scenes", []):
            if not isinstance(scene, dict):
                continue
            counts["scenes"] += 1
            scene_id = str(scene.get("scene_id") or "")
            audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
            text = _scene_text(scene)
            packet = _review_packet(scene, video_id, [])

            frame_path = scene.get("representative_frame") or (scene.get("keyframe") or {}).get("path")
            audio_path = audio.get("path")
            counts["representative_frames_present"] += bool(frame_path)
            counts["representative_frames_available"] += bool(
                frame_path and Path(str(frame_path)).exists()
            )
            counts["audio_artifacts_present"] += bool(audio_path)
            counts["audio_artifacts_available"] += bool(
                audio_path and Path(str(audio_path)).exists()
            )
            counts["transcripts_nonempty"] += bool(text)
            if not text:
                counts["transcripts_empty"] += 1
                outcome = str(
                    audio.get("transcript_outcome_reason")
                    or scene.get("transcript_outcome_reason")
                    or ""
                ).strip()
                if not outcome:
                    counts["empty_transcripts_without_outcome"] += 1
                    _add_review(
                        review_queue,
                        "empty_transcript_without_outcome",
                        {**packet, "reasons": ["empty_transcript_without_outcome"]},
                        full_ledger=review_ledger,
                    )

            signature_meta = _signature_meta(scene)
            signature_key = ":".join(
                [
                    str(signature_meta.get("status") or "missing"),
                    str(signature_meta.get("reason") or "missing"),
                ]
            )
            signature_status[signature_key] += 1
            if signature_meta.get("status") == "error":
                counts["speaker_signature_errors"] += 1
                _add_review(
                    review_queue,
                    "speaker_signature_error",
                    {**packet, "reasons": ["speaker_signature_error"]},
                    full_ledger=review_ledger,
                )

            if scene.get("content_state") == "processing_error":
                counts["content_processing_errors"] += 1
                _add_review(
                    review_queue,
                    "content_processing_error",
                    {**packet, "reasons": ["content_processing_error"]},
                    full_ledger=review_ledger,
                )

            audio_diarization = audio.get("diarization_status")
            derived_diarization = scene.get("diarization_status")
            counts["diarization_audio_success"] += audio_diarization == "success"
            counts["diarization_derived_success"] += derived_diarization == "success"
            counts["diarization_audio_completed_no_speakers"] += (
                audio_diarization == "completed_no_speakers"
            )
            counts["diarization_derived_completed_no_speakers"] += (
                derived_diarization == "completed_no_speakers"
            )
            counts["diarization_path_disagreement"] += (
                derived_diarization is not None and derived_diarization != audio_diarization
            )

            segments = [
                segment for segment in audio.get("segments", []) if isinstance(segment, dict)
            ]
            if segments:
                duration = float(scene.get("duration") or 0.0)
                max_end = max(float(segment.get("end") or 0.0) for segment in segments)
                overshoot = max(0.0, max_end - duration)
                if overshoot > segment_overshoot_seconds:
                    counts["transcript_segments_over_boundary"] += 1
                    _add_review(
                        review_queue,
                        "transcript_segment_over_boundary",
                        {
                            **packet,
                            "reasons": ["transcript_segment_over_boundary"],
                            "segment_overshoot_seconds": round(overshoot, 3),
                        },
                        full_ledger=review_ledger,
                    )

            projected = temporal_segments.get(scene_id)
            if projected is None:
                temporal["missing_scene_segment"] += 1
                _add_review(
                    review_queue,
                    "missing_temporal_segment",
                    {**packet, "reasons": ["missing_temporal_segment"]},
                    full_ledger=review_ledger,
                )
                continue
            temporal["segments_present"] += 1
            mismatches: list[str] = []
            if str(projected.get("full_transcript") or "").strip() != text:
                mismatches.append("transcript")
            # The temporal index stores overlap-filtered transcript *rollup*
            # strings, whereas scene.audio.segments stores timestamped
            # speaker-level dictionaries.  Their list counts intentionally do
            # not match, so compare canonical full text and only require that
            # a non-empty transcript has a temporal rollup container.
            temporal_rollup = projected.get("transcript_segments")
            if text and not isinstance(temporal_rollup, list):
                mismatches.append("transcript_rollup_missing")
            if set(projected.get("speaker_ids") or []) != set(_speaker_ids(scene)):
                mismatches.append("speaker_ids")
            for field in mismatches:
                temporal[f"mismatch_{field}"] += 1
            if mismatches:
                category = (
                    "recovery_addendum_temporal_stale"
                    if scene_id in recovered_scene_ids
                    else "preexisting_temporal_mismatch"
                )
                temporal[category] += 1
                _add_review(
                    review_queue,
                    category,
                    {**packet, "reasons": [category, *mismatches]},
                    full_ledger=review_ledger,
                )

    report = {
        "audit_kind": "human_perceived_quality_read_only",
        "field_path_contract": {
            "transcript": "scene.audio.full_text, fallback scene.audio.transcript",
            "transcript_segments": "scene.audio.segments (timestamped speaker payload) versus temporal_index.segments[scene_id].transcript_segments (overlap-filtered rollup strings); list counts are not compared",
            "diarization_runtime": "scene.audio.diarization_status",
            "diarization_derived": "scene.diarization_status",
            "speaker_ids": "scene.speaker_ids, then scene.audio speaker payloads",
            "speaker_signature": "scene.audio.speaker_voice_signature_meta",
            "temporal_projection": "temporal_index.segments[scene_id]",
        },
        "processing_root": "<configured>/processing",
        "receipt_path": f"<receipt>/{receipt_path.name}" if receipt_path else None,
        "recovered_scene_count": len(recovered_scene_ids),
        "counts": dict(sorted(counts.items())),
        "speaker_signature_status": dict(sorted(signature_status.items())),
        "temporal_projection": dict(sorted(temporal.items())),
        "human_review_queue": review_queue,
    }
    if review_ledger is not None:
        report["human_review_ledger"] = review_ledger
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processing-root", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--segment-overshoot-seconds",
        type=float,
        default=DEFAULT_SEGMENT_OVERSHOOT_SECONDS,
    )
    parser.add_argument(
        "--full-review-ledger",
        action="store_true",
        help="Include every non-sensitive review packet instead of only the capped queue samples.",
    )
    args = parser.parse_args()
    cfg = load_configs()
    processing_root = args.processing_root or Path(cfg["paths"]["processing"])
    receipt_path = args.receipt
    if receipt_path is None:
        candidates = sorted(Path(cfg["paths"]["db_dir"]).glob("recovery_addenda/*/receipt.json"))
        receipt_path = candidates[-1] if candidates else None
    report = build_quality_report(
        processing_root,
        receipt_path=receipt_path,
        segment_overshoot_seconds=args.segment_overshoot_seconds,
        full_review_ledger=args.full_review_ledger,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
