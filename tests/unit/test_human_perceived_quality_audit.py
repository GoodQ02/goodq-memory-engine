from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).parents[2] / "scripts" / "diagnostics" / "audit_human_perceived_quality.py"
SPEC = importlib.util.spec_from_file_location("human_quality_audit", MODULE_PATH)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_quality_audit_classifies_readiness_without_mutating_inputs(tmp_path: Path) -> None:
    processing = tmp_path / "processing"
    video = processing / "video-a"
    frame = tmp_path / "frame.jpg"
    audio = tmp_path / "audio.wav"
    frame.write_bytes(b"frame")
    audio.write_bytes(b"audio")
    recovered_id = "scene-recovered"
    manifest_path = video / "video" / "scene_manifest.json"
    manifest = {
        "video_id": "video-a",
        "scenes": [
            {
                "scene_id": recovered_id,
                "duration": 10.0,
                "representative_frame": str(frame),
                "audio": {
                    "path": str(audio),
                    "diarization_status": "completed_no_speakers",
                    "full_text": "Recovered speech",
                    "segments": [{"start": 0.0, "end": 16.0}],
                    "speaker_voice_signature_meta": {
                        "status": "error",
                        "reason": "embedding_step_failed",
                    },
                },
                "diarization_status": "completed_no_speakers",
                "content_state": "processing_error",
            },
            {
                "scene_id": "scene-empty",
                "duration": 5.0,
                "representative_frame": str(frame),
                "audio": {"path": str(audio), "segments": []},
            },
        ],
    }
    _write(manifest_path, manifest)
    _write(
        video / "temporal_index.json",
        {"segments": [{"scene_id": recovered_id, "full_transcript": "", "transcript_segments": [], "speaker_ids": []}, {"scene_id": "scene-empty", "full_transcript": "", "transcript_segments": [], "speaker_ids": []}]},
    )
    receipt_path = tmp_path / "receipt.json"
    _write(receipt_path, {"changed_scene_ids": [recovered_id]})
    before = manifest_path.read_bytes()

    report = audit.build_quality_report(processing, receipt_path=receipt_path)

    assert report["counts"]["scenes"] == 2
    assert report["counts"]["speaker_signature_errors"] == 1
    assert report["counts"]["diarization_audio_success"] == 0
    assert report["counts"]["diarization_audio_completed_no_speakers"] == 1
    assert report["counts"]["diarization_derived_completed_no_speakers"] == 1
    assert report["field_path_contract"]["diarization_runtime"] == "scene.audio.diarization_status"
    assert report["counts"]["empty_transcripts_without_outcome"] == 1
    assert report["counts"]["transcript_segments_over_boundary"] == 1
    assert report["temporal_projection"]["recovery_addendum_temporal_stale"] == 1
    assert report["human_review_queue"]["recovery_addendum_temporal_stale"][0]["scene_id"] == recovered_id
    assert "human_review_ledger" not in report
    assert manifest_path.read_bytes() == before


def test_quality_audit_full_review_ledger_is_complete_and_non_mutating(tmp_path: Path) -> None:
    processing = tmp_path / "processing"
    video = processing / "video-a"
    manifest_path = video / "video" / "scene_manifest.json"
    _write(
        manifest_path,
        {
            "video_id": "video-a",
            "scenes": [
                {"scene_id": f"scene-{index}", "audio": {"full_text": "canonical", "segments": []}}
                for index in range(audit.HUMAN_REVIEW_LIMIT_PER_REASON + 2)
            ],
        },
    )
    _write(
        video / "temporal_index.json",
        {
            "segments": [
                {"scene_id": f"scene-{index}", "full_transcript": "stale", "transcript_segments": [], "speaker_ids": []}
                for index in range(audit.HUMAN_REVIEW_LIMIT_PER_REASON + 2)
            ]
        },
    )
    before = manifest_path.read_bytes()

    report = audit.build_quality_report(processing, full_review_ledger=True)

    assert len(report["human_review_queue"]["preexisting_temporal_mismatch"]) == audit.HUMAN_REVIEW_LIMIT_PER_REASON
    ledger = report["human_review_ledger"]["preexisting_temporal_mismatch"]
    assert [item["scene_id"] for item in ledger] == [f"scene-{index}" for index in range(7)]
    assert all("full_text" not in item for item in ledger)
    assert manifest_path.read_bytes() == before
