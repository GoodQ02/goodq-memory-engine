from __future__ import annotations

import json
from pathlib import Path

from cli.run_ingestion import (
    _detect_scenes,
    _attach_segmentation_shadow_metrics,
    _prepare_segmentation_shadow_audio_overlay,
    _resolve_ingest_orchestration_contract,
    _resolve_scene_backend_contract,
    _run_segmentation_shadow_pipeline,
)
from steps.audio.segmentation.orchestrator import PhasedSegmentationEngine
from steps.audio.segmentation.phase4_audio_processor import Phase4AudioProcessor
from steps.audio.segmentation.phase5_video_scene_integration import process_video_chunks_with_scenes


def test_phase4_accepts_chunk_manifest_alias_and_writes_segments_alias(tmp_path: Path) -> None:
    processor = Phase4AudioProcessor({})
    manifest = {
        "chunks": [
            {
                "id": 0,
                "start": 0.0,
                "end": 1.0,
                "duration": 1.0,
                "vad_speech": False,
                "chunk_path": str(tmp_path / "audio" / "chunk_0000.wav"),
            }
        ]
    }

    enhanced = processor.process_segments(manifest, "video.mp4", tmp_path)

    assert enhanced["segments"] == enhanced["chunks"]
    saved = json.loads((tmp_path / "metadata" / "segmentation_enhanced.json").read_text(encoding="utf-8"))
    assert saved["segments"] == saved["chunks"]


def test_phase5_writes_scene_manifest_artifact(tmp_path: Path, monkeypatch) -> None:
    from steps.audio.segmentation import phase5_video_scene_integration as phase5_module

    monkeypatch.setattr(
        phase5_module,
        "detect_scenes_for_chunk",
        lambda *_args, **_kwargs: [
            {"start": 0.0, "end": 1.0, "duration": 1.0, "confidence": 0.9, "strategy": "gpu_chunk_detect"}
        ],
    )

    result = process_video_chunks_with_scenes(
        "video.mp4",
        [{"id": 0, "start": 0.0, "end": 1.0, "duration": 1.0}],
        str(tmp_path),
        {},
    )

    manifest = json.loads(Path(result["scene_manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["phase5_complete"] is True
    assert manifest["scenes"][0]["scene_id"] == "scene_0000"
    assert manifest["scenes"][0]["index"] == 0


def test_orchestrator_uses_live_phase_entrypoints(tmp_path: Path, monkeypatch) -> None:
    from steps.audio.segmentation import orchestrator as orchestrator_module

    calls: dict[str, object] = {}

    monkeypatch.setattr(orchestrator_module, "normalize_media", lambda *_args, **_kwargs: str(tmp_path / "audio.wav"))
    monkeypatch.setattr(orchestrator_module, "extract_metadata", lambda *_args, **_kwargs: {"duration": 1.0, "fps": 30.0})
    monkeypatch.setattr(orchestrator_module, "segment_with_webrtc_vad", lambda *_args, **_kwargs: [{"start": 0.0, "end": 1.0, "vad_speech": True}])
    monkeypatch.setattr(orchestrator_module, "segment_with_pyannote", lambda *_args, **_kwargs: [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}])
    monkeypatch.setattr(orchestrator_module, "enhance_segments_with_pyannote", lambda vad, _pyannote: list(vad))

    def fake_phase3(phase2_output, audio_path, output_dir, config):
        calls["phase3_output_dir"] = output_dir
        calls["phase3_config"] = dict(config)
        return {
            "chunks": [{"id": 0, "start": 0.0, "end": 1.0, "vad_speech": True}],
            "manifest_path": str(Path(output_dir) / "segmentation.json"),
        }

    def fake_phase4(manifest_path, _video_path, _output_dir, _cfg):
        calls["phase4_manifest_path"] = manifest_path
        return {
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 1.0,
                    "transcript": "hello",
                    "transcript_segments": [{"start": 0.0, "end": 1.0, "text": "hello", "words": []}],
                    "diarization": [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00", "duration": 1.0}],
                }
            ]
        }

    monkeypatch.setattr(orchestrator_module, "run_phase3_chunk_builder", fake_phase3)
    monkeypatch.setattr(orchestrator_module, "process_segmented_audio", fake_phase4)
    monkeypatch.setattr(
        orchestrator_module,
        "process_video_chunks_with_scenes",
        lambda *_args, **_kwargs: {"video_scenes": [{"start": 0.0, "end": 1.0}], "total_scenes": 1},
    )
    monkeypatch.setattr(orchestrator_module, "merge_all_segment_data", lambda *args, **_kwargs: [{"id": 0, "start": 0.0, "end": 1.0}])
    monkeypatch.setattr(orchestrator_module, "generate_segmentation_manifest", lambda *_args, **_kwargs: str(tmp_path / "metadata" / "segmentation.json"))
    monkeypatch.setattr(orchestrator_module, "validate_manifest", lambda *_args, **_kwargs: {"valid": True})

    engine = PhasedSegmentationEngine(
        {
            "segmentation": {
                "phase2": {"enabled": False},
                "phase3": {"chunk_padding_ms": 250, "chunk_overlap_ms": 500, "merge_threshold": 2.0},
            }
        }
    )

    result = engine.run_full_pipeline("video.mp4", str(tmp_path / "shadow"))

    assert str(calls["phase3_output_dir"]).endswith("audio")
    assert str(calls["phase4_manifest_path"]).endswith("audio\\segmentation.json") or str(calls["phase4_manifest_path"]).endswith("audio/segmentation.json")
    assert result["phase_results"]["phase6"]["manifest_path"].endswith("segmentation.json")


def test_segmentation_shadow_pipeline_is_default_off_and_partial_when_wsl_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    off_result = _run_segmentation_shadow_pipeline(
        tmp_path / "video.mp4",
        tmp_path / "processing",
        {"segmentation": {"enabled": True, "activation": "off"}},
        audio_runtime_contract={"selected": "wsl"},
    )
    assert off_result["status"] == "off"

    import steps.audio.segmentation as segmentation_module

    class DummyEngine:
        def __init__(self, cfg):
            self.cfg = cfg

        def run_full_pipeline(self, video_path, output_base_dir, skip_phases=None):
            output_dir = Path(output_base_dir) / Path(video_path).stem
            output_dir.mkdir(parents=True, exist_ok=True)
            return {
                "output_dir": str(output_dir),
                "timings": {"phase0": 0.1},
                "phase_results": {
                    "phase3": {"audio_manifest_path": str(output_dir / "audio" / "segmentation.json")},
                    "phase5": {
                        "scene_manifest_path": str(output_dir / "video" / "scene_manifest.json"),
                        "video_scenes_path": str(output_dir / "video" / "video_scenes.json"),
                    },
                },
            }

    monkeypatch.setattr(segmentation_module, "PhasedSegmentationEngine", DummyEngine)

    shadow_result = _run_segmentation_shadow_pipeline(
        tmp_path / "video.mp4",
        tmp_path / "processing",
        {"segmentation": {"enabled": True, "activation": "shadow"}},
        audio_runtime_contract={"selected": "windows"},
    )

    assert shadow_result["status"] == "partial"
    assert shadow_result["skip_phases"] == ["phase4", "phase6"]
    assert Path(shadow_result["summary_path"]).exists()


def test_scene_backend_contract_is_explicit_across_activation_modes() -> None:
    off_contract = _resolve_scene_backend_contract({"segmentation": {"enabled": True, "activation": "off"}})
    assert off_contract["scene_backend_selected"] == "legacy_scene_detect"
    assert off_contract["scene_backend_effective"] == "legacy_scene_detect"
    assert off_contract["scene_backend_effective_reason"] == "legacy_scene_detect_default"

    shadow_contract = _resolve_scene_backend_contract({"segmentation": {"enabled": True, "activation": "shadow"}})
    assert shadow_contract["scene_backend_selected"] == "segmentation_phase5_shadow_compare"
    assert shadow_contract["scene_backend_effective"] == "legacy_scene_detect"
    assert shadow_contract["scene_backend_effective_reason"] == "segmentation_shadow_compare_legacy_authority"

    authoritative_contract = _resolve_scene_backend_contract(
        {"segmentation": {"enabled": True, "activation": "authoritative"}}
    )
    assert authoritative_contract["scene_backend_selected"] == "segmentation_phase5"
    assert authoritative_contract["scene_backend_effective"] == "legacy_scene_detect"
    assert authoritative_contract["scene_backend_effective_reason"] == "segmentation_authoritative_not_enabled"


def test_ingest_orchestration_contract_tracks_overlay_selection_and_effective_source() -> None:
    overlay_pending = _resolve_ingest_orchestration_contract(
        {"segmentation": {"enabled": True, "activation": "shadow", "shadow_audio_overlay": True}},
        audio_runtime_contract={"selected": "wsl"},
        segmentation_shadow={"status": "complete", "reason": "segmentation_shadow_complete"},
        segmentation_shadow_overlay={"enabled": False, "reason": "segmentation_shadow_audio_overlay_requires_complete_shadow_run"},
    )
    assert overlay_pending["scene_backend_selected"] == "segmentation_phase5_shadow_compare"
    assert overlay_pending["scene_backend_effective"] == "legacy_scene_detect"
    assert overlay_pending["phase6_audio_source_selected"] == "segmentation_shadow_audio_overlay"
    assert overlay_pending["phase6_audio_source_effective"] == "live_audio_artifacts"
    assert (
        overlay_pending["phase6_audio_source_effective_reason"]
        == "segmentation_shadow_audio_overlay_requires_complete_shadow_run"
    )
    assert overlay_pending["audio_runtime_backend"] == "wsl"

    overlay_ready = _resolve_ingest_orchestration_contract(
        {"segmentation": {"enabled": True, "activation": "shadow", "shadow_audio_overlay": True}},
        segmentation_shadow_overlay={"enabled": True, "reason": "segmentation_shadow_audio_overlay_ready"},
    )
    assert overlay_ready["phase6_audio_source_effective"] == "segmentation_shadow_audio_overlay"
    assert overlay_ready["phase6_audio_source_effective_reason"] == "segmentation_shadow_audio_overlay_ready"


def test_detect_scenes_routes_through_resolved_scene_backend_and_records_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: dict[str, str] = {}

    def fake_run_step(env_name, step_name, payload, cfg_json):
        calls["env_name"] = env_name
        calls["step_name"] = step_name
        calls["video_id"] = payload.get("video_id")
        return {
            "scenes": [{"index": 0, "start": 0.0, "end": 1.25}],
            "scene_meta": {"detected": True},
        }

    monkeypatch.setattr("cli.run_ingestion._run_step", fake_run_step)

    contract = _resolve_scene_backend_contract(
        {"segmentation": {"enabled": True, "activation": "authoritative"}}
    )
    result = _detect_scenes(
        tmp_path / "cfg.json",
        tmp_path / "video.mp4",
        {},
        video_id="video-123",
        scene_backend_contract=contract,
    )

    assert calls["env_name"] == "goodq_video_scene_detect"
    assert calls["step_name"] == "video_scene_detect"
    assert calls["video_id"] == "video-123"
    assert result["scenes"][0]["duration"] == 1.25
    assert result["meta"]["orchestration"]["scene_backend_selected"] == "segmentation_phase5"
    assert result["meta"]["orchestration"]["scene_backend_effective"] == "legacy_scene_detect"
    assert result["meta"]["orchestration"]["step_env"] == "goodq_video_scene_detect"


def test_segmentation_shadow_metrics_written_when_enabled(tmp_path: Path) -> None:
    shadow_root = tmp_path / "processing" / "_segmentation_shadow"
    shadow_root.mkdir(parents=True, exist_ok=True)
    summary_path = shadow_root / "shadow_summary.json"
    summary_path.write_text("{}", encoding="utf-8")

    scene_manifest_path = shadow_root / "scene_manifest.json"
    scene_manifest_path.write_text(
        json.dumps(
            {
                "total_scenes": 2,
                "scenes": [
                    {"scene_id": "scene_0000", "index": 0, "start": 0.0, "end": 1.0},
                    {"scene_id": "scene_0001", "index": 1, "start": 1.0, "end": 2.0},
                ],
                "aligned_segments": [
                    {"scene_aligned": True, "scene_count": 1},
                    {"scene_aligned": False, "scene_count": 0},
                ],
            }
        ),
        encoding="utf-8",
    )

    segmentation_manifest_path = shadow_root / "segmentation.json"
    segmentation_manifest_path.write_text(
        json.dumps(
            {
                "segments": [
                    {"id": 0, "transcript": "hello", "speakers": ["SPEAKER_00"]},
                    {"id": 1, "transcript": "", "speakers": []},
                ],
                "frame_index": [],
                "summary": {},
                "processing": {},
                "source": {},
            }
        ),
        encoding="utf-8",
    )

    shadow_result = {
        "activation": "shadow",
        "status": "complete",
        "summary_path": str(summary_path),
        "scene_manifest_path": str(scene_manifest_path),
        "segmentation_manifest_path": str(segmentation_manifest_path),
        "validation": {
            "stats": {
                "total_segments": 2,
                "transcript_coverage": 0.5,
                "speaker_coverage": 0.5,
            }
        },
    }
    scene_outputs = [
        {"audio": {"transcript": "hello", "speakers": ["SPEAKER_00"]}},
        {"audio": {}},
    ]
    temporal_index = {
        "segments": [],
        "total_scenes": 2,
        "has_audio": True,
        "has_transcripts": True,
        "phase5_complete": True,
        "phase6_complete": True,
        "phase6_harmonized": True,
    }

    updated = _attach_segmentation_shadow_metrics(
        {"segmentation": {"metrics_output": True}},
        scene_outputs,
        temporal_index,
        shadow_result,
    )

    metrics_path = Path(updated["metrics_path"])
    assert metrics_path.exists()
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["scene_count_delta"] == 0
    assert metrics["transcript_coverage_delta"] == 0.0
    assert metrics["speaker_coverage_delta"] == 0.0
    assert metrics["alignment_score"] == 0.5
    assert metrics["temporal_index_completeness_current"] == 1.0
    assert metrics["temporal_index_completeness_shadow"] == 1.0


def test_segmentation_shadow_metrics_respect_metrics_output_flag(tmp_path: Path) -> None:
    shadow_root = tmp_path / "processing" / "_segmentation_shadow"
    shadow_root.mkdir(parents=True, exist_ok=True)
    summary_path = shadow_root / "shadow_summary.json"
    summary_path.write_text("{}", encoding="utf-8")

    shadow_result = {
        "activation": "shadow",
        "status": "partial",
        "summary_path": str(summary_path),
    }

    updated = _attach_segmentation_shadow_metrics(
        {"segmentation": {"metrics_output": False}},
        [],
        None,
        shadow_result,
    )

    assert "metrics_path" not in updated
    assert not (shadow_root / "shadow_metrics.json").exists()


def test_segmentation_shadow_audio_overlay_disabled_by_default(tmp_path: Path) -> None:
    shadow_root = tmp_path / "processing" / "_segmentation_shadow"
    shadow_root.mkdir(parents=True, exist_ok=True)
    summary_path = shadow_root / "shadow_summary.json"
    summary_path.write_text("{}", encoding="utf-8")

    shadow_result = {
        "activation": "shadow",
        "status": "complete",
        "summary_path": str(summary_path),
        "phase4_manifest_path": str(shadow_root / "segmentation_enhanced.json"),
    }

    overlay = _prepare_segmentation_shadow_audio_overlay(
        {"segmentation": {"activation": "shadow", "shadow_audio_overlay": False}},
        shadow_result,
    )

    assert overlay["enabled"] is False
    assert overlay["reason"] == "segmentation_shadow_audio_overlay_disabled"


def test_segmentation_shadow_audio_overlay_builds_phase6_artifacts(tmp_path: Path) -> None:
    shadow_root = tmp_path / "processing" / "_segmentation_shadow"
    metadata_dir = shadow_root / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    summary_path = shadow_root / "shadow_summary.json"
    summary_path.write_text("{}", encoding="utf-8")

    phase4_manifest_path = metadata_dir / "segmentation_enhanced.json"
    phase4_manifest_path.write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 1.0,
                        "transcript": "hello",
                        "transcript_segments": [{"start": 0.0, "end": 1.0, "text": "hello", "words": []}],
                        "language": "en",
                        "diarization": [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00", "duration": 1.0}],
                        "speakers": [{"speaker_id": "SPEAKER_00", "total_duration": 1.0, "segment_count": 1}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    shadow_result = {
        "activation": "shadow",
        "status": "complete",
        "summary_path": str(summary_path),
        "phase4_manifest_path": str(phase4_manifest_path),
    }

    overlay = _prepare_segmentation_shadow_audio_overlay(
        {"segmentation": {"activation": "shadow", "shadow_audio_overlay": True}},
        shadow_result,
    )

    assert overlay["enabled"] is True
    overlay_dir = Path(overlay["audio_artifact_dir"])
    transcript_json = json.loads((overlay_dir / "transcript.json").read_text(encoding="utf-8"))
    diarization_json = json.loads((overlay_dir / "diarization.json").read_text(encoding="utf-8"))
    segmentation_json = json.loads((overlay_dir / "segmentation.json").read_text(encoding="utf-8"))

    assert transcript_json["full_text"] == "hello"
    assert transcript_json["segments"][0]["text"] == "hello"
    assert diarization_json["segments"][0]["speaker"] == "SPEAKER_00"
    assert diarization_json["speakers"][0]["speaker_id"] == "SPEAKER_00"
    assert segmentation_json["segments"][0]["id"] == 0
