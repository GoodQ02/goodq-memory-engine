from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest


def _receipt_cfg(tmp_path: Path) -> dict:
    return {
        "paths": {"log_dir": str(tmp_path / "logs")},
        "run": {"id": "audio-capability-boundary"},
        "host": {"profile": "PERSONAL_AIR_GAP"},
    }


@pytest.mark.parametrize("raw", ["12/25/87", "december 16, 02"])
def test_time_hint_worker_does_not_invent_century(monkeypatch, tmp_path, raw):
    test_audio_cue_worker_cli_preserves_outcome_in_terminal_receipt(
        monkeypatch, tmp_path, "audio_time_hints", "time_hints",
        "time_hints_meta", "time_hints", "time_hint", True,
        f"The tape says {raw}.", "ok", "ran_with_output",
    )
    output = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert output["time_hints"]["explicit_dates"] == []
    assert output["time_hints"]["ambiguous_dates"] == [raw]

    from steps.video.cross_modal_harmonizer import _resolve_scene_time_hints
    resolved = _resolve_scene_time_hints(output, {})
    assert resolved["ambiguous_dates"] == [raw]


@pytest.mark.parametrize(
    ("step", "config_key", "meta_field", "output_field", "cue_key"),
    [
        ("audio_music_events", "events", "music_events_meta", "music_events", "music_event_cue"),
        ("audio_time_hints", "time_hints", "time_hints_meta", "time_hints", "time_hint"),
    ],
)
@pytest.mark.parametrize(
    ("enabled", "transcript", "expected_status", "expected_closure"),
    [
        (True, "Happy birthday on December 16 2002.", "ok", "ran_with_output"),
        (True, "The blue box is here.", "not_applicable", "ran_content_appropriate_empty"),
        (False, "Happy birthday on December 16 2002.", "skipped", "skipped"),
    ],
)
def test_audio_cue_worker_cli_preserves_outcome_in_terminal_receipt(
    monkeypatch,
    tmp_path: Path,
    step: str,
    config_key: str,
    meta_field: str,
    output_field: str,
    cue_key: str,
    enabled: bool,
    transcript: str,
    expected_status: str,
    expected_closure: str,
) -> None:
    from cli import run_ingestion, step_runner
    from steps.common import step_logger

    cfg = _receipt_cfg(tmp_path)
    cfg["audio"] = {config_key: {"enabled": enabled}}
    cfg["gpu"] = {"clear_cache_before_step": False}
    monkeypatch.setattr(step_runner, "load_step_config", lambda *_: cfg)
    monkeypatch.setattr(step_logger, "MISSION_LOGGER_AVAILABLE", False)
    monkeypatch.setattr(run_ingestion, "_CURRENT_RUN_CONTEXT", cfg["run"])
    gpu_module = types.ModuleType("common.gpu_manager")
    gpu_module.initialize_gpu_for_step = lambda **_: None
    monkeypatch.setitem(sys.modules, "common.gpu_manager", gpu_module)
    source = tmp_path / "input.json"
    result = tmp_path / "result.json"
    source.write_text(
        json.dumps({"scene_id": "scene-1", "transcript": transcript}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["step_runner", "--step", step, "--in", str(source), "--out", str(result)],
    )

    # Exercise the production worker dispatch, non-verbose logger and final writer.
    step_runner.main()
    receipt = run_ingestion._finalize_capability_receipt(
        terminal_status="completed",
        cfg=cfg,
        results=[{"scenes": [{"scene_id": "scene-1"}]}],
        output=tmp_path / "output" / "scene_ingest_results.json",
    )

    worker_output = json.loads(result.read_text(encoding="utf-8"))
    row = json.loads((tmp_path / "logs" / "step_runs.jsonl").read_text(encoding="utf-8"))
    persisted = json.loads(
        (tmp_path / "output" / "capability_receipt.json").read_text(encoding="utf-8")
    )
    capability = persisted["capabilities_by_step"][step]
    assert capability["status"] == expected_status
    assert capability["closure_status"] == expected_closure
    assert capability["status_surface"] == meta_field
    assert row["extra"]["result_meta"][meta_field] == worker_output[meta_field]
    assert output_field in worker_output
    assert receipt == persisted
    assert receipt["outcome"] == ("degraded" if not enabled else "completed")

    if expected_status == "not_applicable":
        for cue_present in (False, True):
            cfg["release_validation"] = {
                "content_truth_by_scene": {
                    "scene-1": {"speech": True, "music": True, cue_key: cue_present}
                }
            }
            release_receipt = run_ingestion._finalize_capability_receipt(
                terminal_status="completed",
                cfg=cfg,
                results=[{"scenes": [{"scene_id": "scene-1"}]}],
                output=tmp_path / f"release-{cue_present}" / "scene_ingest_results.json",
                input_count=1,
                release_validation=True,
            )
            capability = release_receipt["capabilities_by_step"][step]
            assert capability["content_applicability"] == cue_key
            assert capability["closure_status"] == (
                "content_truth_mismatch" if cue_present else "ran_content_appropriate_empty"
            )
            # Presence of speech/music cannot stand in for a labeled transcript cue.
            # Unobserved unrelated stages still prevent whole-profile acceptance.
            assert release_receipt["outcome"] == "failed"
            assert release_receipt["summary"]["missing_expected"] > 0


def test_wsl_acoustic_emotion_receipt_names_the_actual_composite_producer(
    monkeypatch, tmp_path: Path
) -> None:
    from cli import run_ingestion
    from steps.common import step_logger

    cfg = _receipt_cfg(tmp_path)
    monkeypatch.setattr(step_logger, "MISSION_LOGGER_AVAILABLE", False)
    monkeypatch.setattr(run_ingestion, "_CURRENT_RUN_CONTEXT", cfg["run"])
    run_ingestion._log_wsl_capability_outcomes(
        cfg=cfg,
        item={"scene_id": "scene-1"},
        duration_ms=100.0,
        outcomes={
            component: {"status": "ok", "reason": "component_output_present"}
            for component in (
                "transcription", "diarization", "acoustic_emotion", "wav2vec2", "clap_handoff"
            )
        },
    )

    receipt = run_ingestion._finalize_capability_receipt(
        terminal_status="completed",
        cfg=cfg,
        results=[{"scenes": [{"scene_id": "scene-1"}]}],
        output=tmp_path / "output" / "scene_ingest_results.json",
        input_count=1,
        release_validation=True,
    )

    capability = receipt["capabilities_by_step"]["audio_emotion"]
    assert capability["runtime_owner"] == "steps.audio.audio_wsl2_bridge"
    assert capability["implementation"] == "steps.audio.audio_wsl2_bridge.audio_unified_wsl2"
    assert capability["status_surface"] == "wsl_capability_outcomes.acoustic_emotion"
    assert capability["effective_implementation"] == "wsl_unified"
    assert capability["closure_status"] == "ran_with_output"
    # Other stages were deliberately not run: this cannot certify the profile.
    assert receipt["outcome"] == "failed"
    assert receipt["summary"]["missing_expected"] > 0


def test_native_acoustic_emotion_cli_reports_unavailable_not_inference(monkeypatch, tmp_path):
    from cli import run_ingestion, step_runner
    from steps.common import step_logger

    cfg = _receipt_cfg(tmp_path)
    cfg["gpu"] = {"clear_cache_before_step": False}
    monkeypatch.setattr(step_runner, "load_step_config", lambda *_: cfg)
    monkeypatch.setattr(step_logger, "MISSION_LOGGER_AVAILABLE", False)
    monkeypatch.setattr(run_ingestion, "_CURRENT_RUN_CONTEXT", cfg["run"])
    gpu_module = types.ModuleType("common.gpu_manager")
    gpu_module.initialize_gpu_for_step = lambda **_: None
    monkeypatch.setitem(sys.modules, "common.gpu_manager", gpu_module)
    source, result = tmp_path / "input.json", tmp_path / "result.json"
    source.write_text(json.dumps({"scene_id": "scene-1", "source_kind": "audio"}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["step_runner", "--step", "audio_emotion", "--in", str(source), "--out", str(result)])
    step_runner.main()
    output = json.loads(result.read_text(encoding="utf-8"))
    assert output["audio_emotion_meta"]["status"] == "unavailable"
    assert output["audio_emotion_meta"]["reason"] == "native_acoustic_emotion_not_implemented"
    assert output["emotion_status"] == "unavailable"
    assert "audio_emotion" not in output and "audio_emotion_scores" not in output
    row = json.loads((tmp_path / "logs/step_runs.jsonl").read_text(encoding="utf-8"))
    assert row["status"] == "skipped"
    assert row["extra"]["result_meta"]["audio_emotion_meta"] == output["audio_emotion_meta"]
    receipt = run_ingestion._finalize_capability_receipt(
        terminal_status="completed", cfg=cfg, results=[{"scenes": [{"scene_id": "scene-1"}]}],
        output=tmp_path / "output/scene_ingest_results.json", input_count=1, release_validation=True,
    )
    assert receipt["capabilities_by_step"]["audio_emotion"]["closure_status"] == "skipped"
    assert receipt["outcome"] == "failed"
