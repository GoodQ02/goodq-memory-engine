import json
from pathlib import Path

from cli.signature_backfill_plan import build_signature_backfill_plan


def _manifest(scene: dict) -> dict:
    return {"video_id": "video-1", "scenes": [scene]}


def test_plan_separates_eligible_historical_failure_from_missing_evidence(tmp_path: Path) -> None:
    root = tmp_path / "processing"
    manifest_path = root / "video-1" / "video" / "scene_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    audio = tmp_path / "scene.wav"
    audio.write_bytes(b"audio")
    scene = {
        "scene_id": "scene-1",
        "index": 1,
        "audio": {
            "path": str(audio),
            "diarization_status": "success",
            "diarization": [
                {"speaker": "SPEAKER_00", "start": 0.0, "end": 2.1},
                {"speaker": "SPEAKER_00", "start": 3.0, "end": 5.2},
            ],
            "speaker_voice_signature_meta": {"status": "error", "reason": "embedding_step_failed"},
        },
    }
    manifest_path.write_text(json.dumps(_manifest(scene)), encoding="utf-8")

    plan = build_signature_backfill_plan(root)

    assert plan["status"] == "inspect_only"
    assert plan["eligible_count"] == 1
    assert plan["blocked_count"] == 0
    assert plan["execution_policy"]["batch_execution"].startswith("blocked")


def test_plan_blocks_historical_failure_without_existing_audio(tmp_path: Path) -> None:
    root = tmp_path / "processing"
    manifest_path = root / "video-1" / "video" / "scene_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    scene = {
        "scene_id": "scene-1",
        "index": 1,
        "audio": {
            "path": str(tmp_path / "missing.wav"),
            "diarization_status": "success",
            "diarization": [{"speaker": "SPEAKER_00"}],
            "speaker_voice_signature_meta": {"status": "error", "reason": "embedding_step_failed"},
        },
    }
    manifest_path.write_text(json.dumps(_manifest(scene)), encoding="utf-8")

    plan = build_signature_backfill_plan(root)

    assert plan["eligible_count"] == 0
    assert plan["blocked_count"] == 1
    assert plan["blocked"][0]["blocked_reasons"] == ["missing_audio_artifact"]


def test_plan_blocks_nonempty_diarization_that_cannot_emit_a_signature(tmp_path: Path) -> None:
    root = tmp_path / "processing"
    manifest_path = root / "video-1" / "video" / "scene_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    audio = tmp_path / "scene.wav"
    audio.write_bytes(b"audio")
    scene = {
        "scene_id": "scene-1",
        "index": 1,
        "audio": {
            "path": str(audio),
            "diarization_status": "success",
            "diarization": [
                {"speaker": "SPEAKER_00", "start": 0.0, "end": 0.22},
                {"speaker": "SPEAKER_00", "start": 8.8, "end": 9.06},
            ],
            "speaker_voice_signature_meta": {"status": "error", "reason": "embedding_step_failed"},
        },
    }
    manifest_path.write_text(json.dumps(_manifest(scene)), encoding="utf-8")

    plan = build_signature_backfill_plan(root)

    assert plan["eligible_count"] == 0
    assert plan["blocked"][0]["blocked_reasons"] == ["insufficient_diverse_speech"]


def test_planner_thresholds_match_the_signature_worker_contract() -> None:
    worker = Path("wsl2_audio/process_audio.py").read_text(encoding="utf-8")

    assert "_SPEAKER_SIGNATURE_MIN_TOTAL_SECONDS = 4.0" in worker
    assert "_SPEAKER_SIGNATURE_MIN_SEGMENTS = 2" in worker
    assert "_SPEAKER_SIGNATURE_MIN_SEGMENT_SECONDS = 0.75" in worker
    assert "_SPEAKER_SIGNATURE_MAX_SEGMENTS = 4" in worker
