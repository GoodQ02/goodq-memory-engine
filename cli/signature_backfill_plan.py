"""Read-only planner for historical Wav2Vec speaker-signature repairs."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from steps.common.config_loader import load_configs


TARGET_STATUS = "error"
TARGET_REASON = "embedding_step_failed"


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _signature_meta(scene: dict[str, Any]) -> dict[str, Any]:
    audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
    value = audio.get("speaker_voice_signature_meta") or scene.get(
        "speaker_voice_signature_meta"
    )
    return value if isinstance(value, dict) else {}


def _scene_record(scene: dict[str, Any], manifest_path: Path, video_id: str) -> dict[str, Any]:
    audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
    return {
        "scene_id": str(scene.get("scene_id") or ""),
        "video_id": video_id,
        "scene_index": scene.get("index"),
        "manifest_path": str(manifest_path),
        "audio_path": str(audio.get("path") or ""),
        "diarization_status": audio.get("diarization_status"),
        "diarization_segment_count": len(audio.get("diarization") or [])
        if isinstance(audio.get("diarization"), list)
        else 0,
    }


def build_signature_backfill_plan(processing_root: Path) -> dict[str, Any]:
    """Classify existing scene evidence without reading media or changing state."""
    status_counts: Counter[str] = Counter()
    eligible: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    manifests = sorted(processing_root.glob("*/video/scene_manifest.json"))
    for manifest_path in manifests:
        manifest = _read_json(manifest_path)
        video_id = str(manifest.get("video_id") or manifest_path.parent.parent.name)
        for scene in manifest.get("scenes", []):
            if not isinstance(scene, dict):
                continue
            meta = _signature_meta(scene)
            status = str(meta.get("status") or "missing")
            reason = str(meta.get("reason") or "missing")
            status_counts[f"{status}:{reason}"] += 1
            if (status, reason) != (TARGET_STATUS, TARGET_REASON):
                continue

            record = _scene_record(scene, manifest_path, video_id)
            missing: list[str] = []
            if not record["scene_id"]:
                missing.append("missing_scene_id")
            if not record["audio_path"] or not Path(record["audio_path"]).is_file():
                missing.append("missing_audio_artifact")
            if record["diarization_status"] != "success":
                missing.append("diarization_not_success")
            if not record["diarization_segment_count"]:
                missing.append("missing_diarization_segments")
            if missing:
                blocked.append({**record, "blocked_reasons": missing})
            else:
                eligible.append(record)

    eligible.sort(key=lambda item: (item["video_id"], int(item["scene_index"] or -1), item["scene_id"]))
    blocked.sort(key=lambda item: (item["video_id"], int(item["scene_index"] or -1), item["scene_id"]))
    canonical = json.dumps(eligible, sort_keys=True, separators=(",", ":"))
    return {
        "status": "inspect_only",
        "kind": "signature_only_historical_backfill",
        "processing_root": str(processing_root),
        "target_status": {"status": TARGET_STATUS, "reason": TARGET_REASON},
        "manifest_count": len(manifests),
        "historical_failure_count": len(eligible) + len(blocked),
        "eligible_count": len(eligible),
        "blocked_count": len(blocked),
        "eligible_scene_ids_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "signature_status_counts": dict(sorted(status_counts.items())),
        "eligible": eligible,
        "blocked": blocked,
        "execution_policy": {
            "mode": "signature_only",
            "requires_fresh_scene_proof": True,
            "preserves": ["transcript", "diarization", "clap", "temporal", "visual"],
            "batch_execution": "blocked_until_scene_proof_and_scoped_confirmation",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processing-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cfg = load_configs()
    plan = build_signature_backfill_plan(args.processing_root or Path(cfg["paths"]["processing"]))
    rendered = json.dumps(plan, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
