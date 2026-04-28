from __future__ import annotations

import json
import re
from pathlib import Path

from cli.control_recurrence_report import main as recurrence_cli_main
from lib.control_recurrence_report import (
    build_control_recurrence_comparison,
    build_control_recurrence_report,
    render_markdown_report,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, payloads: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(item) for item in payloads) + "\n", encoding="utf-8")


def _episode_artifacts(
    *,
    run_root: Path,
    epoch_root: Path,
    episode_dir_name: str,
    episode_name: str,
    run_id: str,
    video_id: str,
    scene_ids: list[str],
    warnings: list[dict] | None = None,
    phase6_complete: bool = True,
    phase6_harmonized: bool = True,
    qdrant_ok: bool = True,
    speaker_skip_index: int | None = 1,
    speaker_skip_reason: str = "insufficient_diverse_speech",
) -> Path:
    run_dir = run_root / episode_dir_name
    processing_dir = epoch_root / "processing" / episode_name.replace(".mp4", "")
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"
    temporal_index_path = processing_dir / "temporal_index.json"
    output_path = run_dir / "output" / "scene_ingest_results.json"

    scenes = [
        {
            "scene_id": scene_id,
            "index": index,
            "qdrant_ok": qdrant_ok,
            "speaker_voice_signature_meta": (
                {"status": "skipped", "reason": speaker_skip_reason}
                if speaker_skip_index is not None and index == speaker_skip_index
                else {"status": "ok"}
            ),
        }
        for index, scene_id in enumerate(scene_ids)
    ]
    segments = [
        {
            "scene_id": scene_id,
            "index": index,
            "diarization_status": "success",
            "emotion_status": "success",
            "speaker_voice_signature_meta": (
                {"status": "skipped", "reason": speaker_skip_reason}
                if speaker_skip_index is not None and index == speaker_skip_index
                else {"status": "ok"}
            ),
        }
        for index, scene_id in enumerate(scene_ids)
    ]

    _write_json(
        output_path,
        [
            {
                "video_id": video_id,
                "video_hash": video_id,
                "video_name": episode_name,
                "phase6_complete": phase6_complete,
                "qdrant_ok": qdrant_ok,
                "phase6_qdrant_ok": qdrant_ok,
                "scenes": scenes,
                "temporal_index_path": str(temporal_index_path),
            }
        ],
    )
    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase6_complete": phase6_complete,
            "phase6_harmonized": phase6_harmonized,
            "phase6_vector_commit": {"qdrant_ok": qdrant_ok, "vector_points_attempted": len(scene_ids) * 2},
            "scenes": scenes,
        },
    )
    _write_json(
        temporal_index_path,
        {
            "video_id": video_id,
            "phase6_complete": phase6_complete,
            "phase6_harmonized": phase6_harmonized,
            "total_scenes": len(scene_ids),
            "segments": segments,
        },
    )
    _write_json(
        run_dir / "workspace" / "_resolved_config.json",
        {
            "run": {"id": run_id, "pipeline": "scene_ingest_cli", "warnings": warnings or []},
            "paths": {"log_dir": str(epoch_root / "logs")},
        },
    )
    _write_json(
        run_dir / "experiment_log.json",
        {
            "episode": episode_name,
            "status": "passed",
            "metrics": {
                "output_path": str(output_path),
                "temporal_index_path": str(temporal_index_path),
                "scene_manifest_path": str(scene_manifest_path),
                "common": {"phase6_complete": phase6_complete, "qdrant_ok": qdrant_ok, "scene_count": len(scene_ids)},
            },
        },
    )
    return run_dir


def _simple_run_fixture(
    tmp_path: Path,
    run_name: str,
    *,
    episode_name: str = "01x01 - Good News, Bad News.mp4",
    run_id: str = "runtime-simple",
    video_id: str = "video-simple",
) -> tuple[Path, Path]:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    run_root = reports_root / run_name
    epoch_root = tmp_path / "GoodQ_Data" / "epochs" / f"epoch_{run_name}"
    episode_dir = episode_name.replace(".mp4", "_scene_context_llm").replace(" ", "_")
    ep = _episode_artifacts(
        run_root=run_root,
        epoch_root=epoch_root,
        episode_dir_name=episode_dir,
        episode_name=episode_name,
        run_id=run_id,
        video_id=video_id,
        scene_ids=[f"{run_name}-scene"],
        speaker_skip_index=None,
    )
    _write_json(
        run_root / "experiment_log.json",
        {
            "epoch": f"epoch_{run_name}",
            "status": "completed",
            "plan": [{"episode": episode_name, "status": "passed", "run_dir": str(ep)}],
        },
    )
    _append_jsonl(epoch_root / "logs" / "step_runs.jsonl", [])
    return reports_root, run_root


def test_control_recurrence_report_groups_current_truth_surfaces(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    run_root = reports_root / "20260424_182406_season2_fresh_witness"
    epoch_root = tmp_path / "GoodQ_Data" / "epochs" / "epoch_witness"

    ep1 = _episode_artifacts(
        run_root=run_root,
        epoch_root=epoch_root,
        episode_dir_name="02x03_scene_context_llm",
        episode_name="02x03 - The Jacket.mp4",
        run_id="runtime-ep1",
        video_id="video-ep1",
        scene_ids=["scene-a", "scene-b"],
        warnings=[
            {
                "code": "optional_audio_step_failed",
                "message": "Step audio_embed_clap failed (goodq_audio_embed) [returncode=3221226505]",
                "context": {"step": "audio_embed_clap", "scene_id": "scene-b", "scene_index": 1},
                "ts_utc": "2026-04-25T02:13:13+00:00",
            },
            {
                "code": "native_crash_retry",
                "message": "Retrying step after native subprocess crash",
                "context": {"step": "image_embed_dino", "return_code": 3221226505, "attempt": 1},
                "ts_utc": "2026-04-25T02:24:20+00:00",
            },
        ],
    )
    ep2 = _episode_artifacts(
        run_root=run_root,
        epoch_root=epoch_root,
        episode_dir_name="02x04_scene_context_llm",
        episode_name="02x04 - The Phone Message.mp4",
        run_id="runtime-ep2",
        video_id="video-ep2",
        scene_ids=["scene-c"],
    )

    _write_json(
        run_root / "experiment_log.json",
        {
            "epoch": "epoch_witness",
            "status": "completed",
            "plan": [
                {"episode": "02x03 - The Jacket.mp4", "status": "passed", "run_dir": str(ep1)},
                {"episode": "02x04 - The Phone Message.mp4", "status": "passed", "run_dir": str(ep2)},
            ],
        },
    )
    _append_jsonl(
        epoch_root / "logs" / "step_runs.jsonl",
        [
            {
                "ts": "2026-04-25T02:00:00",
                "step": "sentiment",
                "status": "skipped",
                "error": "",
                "run_id": "runtime-ep1",
                "video_id": "video-ep1",
                "scene_id": "scene-a",
                "scene_index": 0,
                "extra": {"reason": "sentiment_no_text", "embedding_emitted": False},
            },
            {
                "ts": "2026-04-25T02:13:13",
                "step": "audio_embed_clap",
                "status": "error",
                "error": "Step audio_embed_clap failed (goodq_audio_embed) [returncode=3221226505]",
                "run_id": "runtime-ep1",
                "video_id": "video-ep1",
                "scene_id": "scene-b",
                "scene_index": 1,
                "extra": {"reason": "optional_step_failed", "optional": True, "embedding_emitted": False},
            },
            {
                "ts": "2026-04-25T03:00:00",
                "step": "image_caption",
                "status": "ok",
                "run_id": "runtime-ep2",
                "video_id": "video-ep2",
            },
        ],
    )

    report = build_control_recurrence_report(run_id=run_root.name, reports_root=reports_root)

    assert report["report"]["control_agent"] == "not_activated"
    assert report["report"]["auto_healing"] == "not_enabled"
    assert report["scope"]["episodes"] == 2
    assert report["phase6_qdrant_truth"]["healthy"] is True

    families = {row["error_family"]: row for row in report["top_repeated_failure_families"]}
    assert "native_subprocess_crash:0xC0000409" in families
    assert "native_crash_retry:0xC0000409" in families
    assert "no_text" in families
    assert "insufficient_diverse_speech" in families
    assert families["native_subprocess_crash:0xC0000409"]["category"] == "actionable"
    assert families["insufficient_diverse_speech"]["category"] == "informational"
    assert report["recurrence_classification"]["highest_category"] == "actionable"

    optional_steps = {row["step_name"] for row in report["optional_enrichment_skips"]}
    assert {"audio_embed_clap", "sentiment", "speaker_voice_signature"}.issubset(optional_steps)
    assert report["recovered_vs_unrecovered_failures"]["recovered"] >= 2
    assert any(row["scene_id"] == "scene-b" for row in report["scenes_affected"])


def test_control_recurrence_report_discovers_direct_run_root_without_experiment_log(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    run_root = reports_root / "direct_control_run"
    epoch_root = tmp_path / "GoodQ_Data" / "epochs" / "epoch_direct"
    processing_dir = epoch_root / "processing" / "01x01 - Direct Control"
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"
    temporal_index_path = processing_dir / "temporal_index.json"
    output_path = run_root / "output" / "scene_ingest_results.json"
    stdout_path = run_root / "ingestion.stdout.log"
    video_id = "video-direct"
    runtime_run_id = "runtime-direct"

    scenes = [
        {
            "scene_id": "scene-a",
            "index": 0,
            "content_state": "signal",
            "speaker_voice_signature_meta": {"status": "skipped", "reason": "insufficient_diverse_speech"},
        }
    ]
    _write_json(
        output_path,
        [
            {
                "video_id": video_id,
                "video_hash": video_id,
                "video_name": "01x01 - Direct Control.mp4",
                "phase6_complete": True,
                "qdrant_ok": True,
                "phase6_qdrant_ok": True,
                "scenes": scenes,
                "temporal_index_path": str(temporal_index_path),
            }
        ],
    )
    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "phase6_harmonized": True,
            "phase6_vector_commit": {"qdrant_ok": True, "vector_points_attempted": 2},
            "scenes": scenes,
        },
    )
    _write_json(
        temporal_index_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "phase6_harmonized": True,
            "total_scenes": 1,
            "segments": scenes,
        },
    )
    _write_json(
        run_root / "workspace" / "_resolved_config.json",
        {
            "run": {"id": runtime_run_id, "pipeline": "scene_ingest_cli", "warnings": []},
            "paths": {"log_dir": str(epoch_root / "logs")},
        },
    )
    _write_json(
        run_root / "operator_run_metadata.json",
        {
            "label": run_root.name,
            "stdout": str(stdout_path),
            "stderr": str(run_root / "ingestion.stderr.log"),
        },
    )
    _append_jsonl(
        epoch_root / "logs" / "step_runs.jsonl",
        [
            {
                "ts": "2026-04-28T05:00:00",
                "step": "sentiment",
                "status": "skipped",
                "error": "",
                "run_id": runtime_run_id,
                "video_id": video_id,
                "scene_id": "scene-a",
                "scene_index": 0,
                "extra": {"reason": "no_text"},
            }
        ],
    )
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-04-28T05:01:00Z",
                        "run_id": runtime_run_id,
                        "event": "step_error",
                        "step": "step.image_caption",
                        "error": "returncode_3221226505",
                        "metadata": {
                            "video_id": video_id,
                            "scene_id": "scene-a",
                            "scene_index": 0,
                            "native_retry_attempt": 0,
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-04-28T05:01:01Z",
                        "run_id": runtime_run_id,
                        "event": "step_start",
                        "step": "step.image_caption",
                        "metadata": {
                            "video_id": video_id,
                            "scene_id": "scene-a",
                            "scene_index": 0,
                            "native_retry_attempt": 1,
                            "native_retry_mode": "gpu_amp_disabled",
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_control_recurrence_report(run_root=run_root)

    assert report["scope"]["episodes"] == 1
    assert report["scope"]["runtime_run_ids"] == [runtime_run_id]
    assert report["phase6_qdrant_truth"]["healthy"] is True
    families = {row["error_family"]: row for row in report["top_repeated_failure_families"]}
    assert families["native_crash_retry:0xC0000409"]["category"] == "actionable"
    assert families["native_crash_retry:0xC0000409"]["count"] == 1
    assert families["no_text"]["category"] == "informational"
    assert "run_root_missing_experiment_log" not in json.dumps(report)
    assert not re.search(r"\b[A-Za-z]:[\\/]", json.dumps(report))


def test_control_recurrence_cli_emits_text(tmp_path: Path, capsys) -> None:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    run_root = reports_root / "run_one"
    epoch_root = tmp_path / "GoodQ_Data" / "epochs" / "epoch_one"
    ep = _episode_artifacts(
        run_root=run_root,
        epoch_root=epoch_root,
        episode_dir_name="01x01_scene_context_llm",
        episode_name="01x01 - Good News, Bad News.mp4",
        run_id="runtime-one",
        video_id="video-one",
        scene_ids=["scene-one"],
    )
    _write_json(
        run_root / "experiment_log.json",
        {
            "epoch": "epoch_one",
            "status": "completed",
            "plan": [{"episode": "01x01 - Good News, Bad News.mp4", "status": "passed", "run_dir": str(ep)}],
        },
    )
    _append_jsonl(epoch_root / "logs" / "step_runs.jsonl", [])

    assert recurrence_cli_main(["--run-id", "run_one", "--reports-root", str(reports_root)]) == 0
    out = capsys.readouterr().out
    assert "GoodQ Control Recurrence Report" in out
    assert "ControlAgent: not activated" in out
    assert "Recommendation" in out
    assert "Operator Hints" in out
    assert "Inspection Targets" in out
    assert "Category Counts" in out
    assert "Final Phase 6 / Qdrant Truth" in out


def test_control_recurrence_classification_informational_only_pass(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    run_root = reports_root / "info_run"
    epoch_root = tmp_path / "GoodQ_Data" / "epochs" / "epoch_info"
    ep = _episode_artifacts(
        run_root=run_root,
        epoch_root=epoch_root,
        episode_dir_name="01x01_scene_context_llm",
        episode_name="01x01 - Good News, Bad News.mp4",
        run_id="info-runtime",
        video_id="info-video",
        scene_ids=["info-scene"],
        speaker_skip_index=None,
    )
    _write_json(
        run_root / "experiment_log.json",
        {
            "epoch": "epoch_info",
            "status": "completed",
            "plan": [{"episode": "01x01 - Good News, Bad News.mp4", "status": "passed", "run_dir": str(ep)}],
        },
    )
    _append_jsonl(
        epoch_root / "logs" / "step_runs.jsonl",
        [
            {
                "ts": "2026-04-24T01:00:00",
                "step": "sentiment",
                "status": "skipped",
                "run_id": "info-runtime",
                "video_id": "info-video",
                "scene_id": "info-scene",
                "scene_index": 0,
                "extra": {"reason": "sentiment_no_text"},
            }
        ],
    )

    report = build_control_recurrence_report(run_id="info_run", reports_root=reports_root)

    families = {row["error_family"]: row for row in report["top_repeated_failure_families"]}
    assert families["no_text"]["category"] == "informational"
    assert families["no_text"]["operator_hints"] == [
        "No action unless count increases sharply or correlates with unhealthy Phase 6/Qdrant output."
    ]
    assert "temporal_index.json segments" in families["no_text"]["inspection_targets"]
    assert report["recurrence_classification"]["category_counts"]["informational"] == 1
    assert report["recurrence_classification"]["highest_category"] == "informational"
    assert report["recommendation"]["status"] == "pass"
    assert report["operator_hints"] == families["no_text"]["operator_hints"]


def test_control_recurrence_classification_watch_only_warn(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    run_root = reports_root / "watch_run"
    epoch_root = tmp_path / "GoodQ_Data" / "epochs" / "epoch_watch"
    ep = _episode_artifacts(
        run_root=run_root,
        epoch_root=epoch_root,
        episode_dir_name="02x01_scene_context_llm",
        episode_name="02x01 - The Ex-Girlfriend.mp4",
        run_id="watch-runtime",
        video_id="watch-video",
        scene_ids=["watch-scene-a", "watch-scene-b"],
        speaker_skip_reason="diarization_unavailable",
    )
    _write_json(
        run_root / "experiment_log.json",
        {
            "epoch": "epoch_watch",
            "status": "completed",
            "plan": [{"episode": "02x01 - The Ex-Girlfriend.mp4", "status": "passed", "run_dir": str(ep)}],
        },
    )
    _append_jsonl(epoch_root / "logs" / "step_runs.jsonl", [])

    report = build_control_recurrence_report(run_id="watch_run", reports_root=reports_root)

    families = {row["error_family"]: row for row in report["top_repeated_failure_families"]}
    assert families["diarization_unavailable"]["category"] == "watch"
    assert families["diarization_unavailable"]["operator_hints"] == [
        "Inspect WSL audio readiness, diarization_status, diarization_error, and whether speaker_count/dominant_speaker_id persisted."
    ]
    assert "diarization_error" in families["diarization_unavailable"]["inspection_targets"]
    assert report["recurrence_classification"]["highest_category"] == "watch"
    assert report["recommendation"]["status"] == "warn"


def test_control_recurrence_classification_actionable_warn(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    run_root = reports_root / "action_run"
    epoch_root = tmp_path / "GoodQ_Data" / "epochs" / "epoch_action"
    ep = _episode_artifacts(
        run_root=run_root,
        epoch_root=epoch_root,
        episode_dir_name="02x03_scene_context_llm",
        episode_name="02x03 - The Jacket.mp4",
        run_id="action-runtime",
        video_id="action-video",
        scene_ids=["action-scene"],
        speaker_skip_index=None,
        warnings=[
            {
                "code": "native_crash_retry",
                "message": "Retrying step after native subprocess crash",
                "context": {"step": "image_embed_dino", "return_code": 3221226505, "attempt": 1},
                "ts_utc": "2026-04-25T02:24:20+00:00",
            }
        ],
    )
    _write_json(
        run_root / "experiment_log.json",
        {
            "epoch": "epoch_action",
            "status": "completed",
            "plan": [{"episode": "02x03 - The Jacket.mp4", "status": "passed", "run_dir": str(ep)}],
        },
    )
    _append_jsonl(epoch_root / "logs" / "step_runs.jsonl", [])

    report = build_control_recurrence_report(run_id="action_run", reports_root=reports_root)

    families = {row["error_family"]: row for row in report["top_repeated_failure_families"]}
    assert families["native_crash_retry:0xC0000409"]["category"] == "actionable"
    assert families["native_crash_retry:0xC0000409"]["operator_hints"] == [
        "Inspect affected step distribution, stderr/error tails, retry/fallback outcome, and whether final scene output survived."
    ]
    assert "run.warnings" in families["native_crash_retry:0xC0000409"]["inspection_targets"]
    assert report["recurrence_classification"]["highest_category"] == "actionable"
    assert report["recommendation"]["status"] == "warn"


def test_control_recurrence_classification_blocking_fail(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    run_root = reports_root / "blocking_run"
    epoch_root = tmp_path / "GoodQ_Data" / "epochs" / "epoch_blocking"
    ep = _episode_artifacts(
        run_root=run_root,
        epoch_root=epoch_root,
        episode_dir_name="02x12_scene_context_llm",
        episode_name="02x12 - The Busboy.mp4",
        run_id="blocking-runtime",
        video_id="blocking-video",
        scene_ids=["blocking-scene"],
        speaker_skip_index=None,
        qdrant_ok=False,
    )
    _write_json(
        run_root / "experiment_log.json",
        {
            "epoch": "epoch_blocking",
            "status": "completed",
            "plan": [{"episode": "02x12 - The Busboy.mp4", "status": "passed", "run_dir": str(ep)}],
        },
    )
    _append_jsonl(epoch_root / "logs" / "step_runs.jsonl", [])

    report = build_control_recurrence_report(run_id="blocking_run", reports_root=reports_root)

    families = {row["error_family"]: row for row in report["top_repeated_failure_families"]}
    assert families["qdrant_unhealthy"]["category"] == "blocking"
    assert families["qdrant_unhealthy"]["operator_hints"] == [
        "Inspect Qdrant service, collection names, and qdrant_ok fields."
    ]
    assert "Qdrant collection names" in families["qdrant_unhealthy"]["inspection_targets"]
    assert report["recurrence_classification"]["highest_category"] == "blocking"
    assert report["recommendation"]["status"] == "fail"


def test_control_recurrence_comparison_reports_deltas_and_recommendation(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    baseline_root = reports_root / "baseline_run"
    candidate_root = reports_root / "candidate_run"
    baseline_epoch = tmp_path / "GoodQ_Data" / "epochs" / "epoch_baseline"
    candidate_epoch = tmp_path / "GoodQ_Data" / "epochs" / "epoch_candidate"

    baseline_ep = _episode_artifacts(
        run_root=baseline_root,
        epoch_root=baseline_epoch,
        episode_dir_name="01x01_scene_context_llm",
        episode_name="01x01 - Good News, Bad News.mp4",
        run_id="baseline-runtime",
        video_id="baseline-video",
        scene_ids=["baseline-scene"],
        speaker_skip_index=None,
    )
    candidate_ep = _episode_artifacts(
        run_root=candidate_root,
        epoch_root=candidate_epoch,
        episode_dir_name="02x01_scene_context_llm",
        episode_name="02x01 - The Ex-Girlfriend.mp4",
        run_id="candidate-runtime",
        video_id="candidate-video",
        scene_ids=["candidate-scene-a", "candidate-scene-b"],
        warnings=[
            {
                "code": "native_crash_retry",
                "message": "Retrying step after native subprocess crash",
                "context": {"step": "image_embed_dino", "return_code": 3221226505, "attempt": 1},
                "ts_utc": "2026-04-25T02:24:20+00:00",
            }
        ],
        qdrant_ok=False,
    )

    _write_json(
        baseline_root / "experiment_log.json",
        {
            "epoch": "epoch_baseline",
            "status": "completed",
            "plan": [{"episode": "01x01 - Good News, Bad News.mp4", "status": "passed", "run_dir": str(baseline_ep)}],
        },
    )
    _write_json(
        candidate_root / "experiment_log.json",
        {
            "epoch": "epoch_candidate",
            "status": "completed",
            "plan": [{"episode": "02x01 - The Ex-Girlfriend.mp4", "status": "passed", "run_dir": str(candidate_ep)}],
        },
    )
    _append_jsonl(
        baseline_epoch / "logs" / "step_runs.jsonl",
        [
            {
                "ts": "2026-04-24T01:00:00",
                "step": "sentiment",
                "status": "skipped",
                "run_id": "baseline-runtime",
                "video_id": "baseline-video",
                "scene_id": "baseline-scene",
                "scene_index": 0,
                "extra": {"reason": "sentiment_too_short"},
            }
        ],
    )
    _append_jsonl(
        candidate_epoch / "logs" / "step_runs.jsonl",
        [
            {
                "ts": "2026-04-25T01:00:00",
                "step": "sentiment",
                "status": "skipped",
                "run_id": "candidate-runtime",
                "video_id": "candidate-video",
                "scene_id": "candidate-scene-a",
                "scene_index": 0,
                "extra": {"reason": "sentiment_no_text"},
            },
            {
                "ts": "2026-04-25T01:03:00",
                "step": "audio_embed_clap",
                "status": "skipped",
                "run_id": "candidate-runtime",
                "video_id": "candidate-video",
                "scene_id": "candidate-scene-b",
                "scene_index": 1,
                "extra": {"reason": "audio_embed_clap_audio_silent"},
            },
        ],
    )

    comparison = build_control_recurrence_comparison(
        baseline_run_id="baseline_run",
        candidate_run_id="candidate_run",
        reports_root=reports_root,
    )

    assert comparison["report"]["control_agent"] == "not_activated"
    assert comparison["baseline"]["run_id"] == "baseline_run"
    assert comparison["candidate"]["run_id"] == "candidate_run"
    assert comparison["delta"]["total_recurrence_signals"]["baseline"] == 1
    assert comparison["delta"]["total_recurrence_signals"]["candidate"] == 5
    assert comparison["delta"]["new_error_families"] == [
        "audio_silent",
        "insufficient_diverse_speech",
        "native_crash_retry:0xC0000409",
        "no_text",
        "qdrant_unhealthy",
    ]
    assert comparison["delta"]["resolved_error_families"] == ["too_short"]
    assert comparison["delta"]["signals_by_error_family"]["audio_silent"]["delta"] == 1
    assert comparison["delta"]["signals_by_error_family"]["qdrant_unhealthy"]["category"] == "blocking"
    assert comparison["delta"]["signals_by_error_family"]["qdrant_unhealthy"]["operator_hints"] == [
        "Inspect Qdrant service, collection names, and qdrant_ok fields."
    ]
    assert "Qdrant service" in comparison["inspection_targets"]
    assert comparison["delta"]["recovery_counts"]["skipped"]["delta"] == 2
    assert any(row["step_name"] == "audio_embed_clap" for row in comparison["delta"]["per_step_changes"])
    assert comparison["delta"]["phase6_health_delta"]["status"] == "unchanged"
    assert comparison["delta"]["qdrant_health_delta"]["status"] == "regressed"
    assert comparison["recommendation"]["status"] == "fail"


def test_control_recurrence_cli_comparison_json_smoke(tmp_path: Path, capsys) -> None:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    baseline_root = reports_root / "baseline_run"
    candidate_root = reports_root / "candidate_run"
    baseline_epoch = tmp_path / "GoodQ_Data" / "epochs" / "epoch_baseline"
    candidate_epoch = tmp_path / "GoodQ_Data" / "epochs" / "epoch_candidate"

    baseline_ep = _episode_artifacts(
        run_root=baseline_root,
        epoch_root=baseline_epoch,
        episode_dir_name="01x01_scene_context_llm",
        episode_name="01x01 - Good News, Bad News.mp4",
        run_id="baseline-runtime",
        video_id="baseline-video",
        scene_ids=["baseline-scene"],
        speaker_skip_index=None,
    )
    candidate_ep = _episode_artifacts(
        run_root=candidate_root,
        epoch_root=candidate_epoch,
        episode_dir_name="01x02_scene_context_llm",
        episode_name="01x02 - The Stakeout.mp4",
        run_id="candidate-runtime",
        video_id="candidate-video",
        scene_ids=["candidate-scene"],
        speaker_skip_index=None,
    )
    _write_json(
        baseline_root / "experiment_log.json",
        {
            "epoch": "epoch_baseline",
            "status": "completed",
            "plan": [{"episode": "01x01 - Good News, Bad News.mp4", "status": "passed", "run_dir": str(baseline_ep)}],
        },
    )
    _write_json(
        candidate_root / "experiment_log.json",
        {
            "epoch": "epoch_candidate",
            "status": "completed",
            "plan": [{"episode": "01x02 - The Stakeout.mp4", "status": "passed", "run_dir": str(candidate_ep)}],
        },
    )
    _append_jsonl(baseline_epoch / "logs" / "step_runs.jsonl", [])
    _append_jsonl(candidate_epoch / "logs" / "step_runs.jsonl", [])

    assert (
        recurrence_cli_main(
            [
                "--baseline-run-id",
                "baseline_run",
                "--candidate-run-id",
                "candidate_run",
                "--reports-root",
                str(reports_root),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["report"]["name"] == "control_recurrence_comparison"
    assert payload["delta"]["total_recurrence_signals"]["delta"] == 0
    assert payload["recommendation"]["status"] == "pass"


def test_control_recurrence_cli_writes_single_run_markdown(tmp_path: Path, capsys) -> None:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    run_root = reports_root / "single_run"
    epoch_root = tmp_path / "GoodQ_Data" / "epochs" / "epoch_single"
    ep = _episode_artifacts(
        run_root=run_root,
        epoch_root=epoch_root,
        episode_dir_name="01x01_scene_context_llm",
        episode_name="01x01 - Good News, Bad News.mp4",
        run_id="single-runtime",
        video_id="single-video",
        scene_ids=["single-scene"],
        speaker_skip_index=None,
    )
    _write_json(
        run_root / "experiment_log.json",
        {
            "epoch": "epoch_single",
            "status": "completed",
            "plan": [{"episode": "01x01 - Good News, Bad News.mp4", "status": "passed", "run_dir": str(ep)}],
        },
    )
    _append_jsonl(epoch_root / "logs" / "step_runs.jsonl", [])

    output_dir = tmp_path / "md"
    assert (
        recurrence_cli_main(
            [
                "--run-id",
                "single_run",
                "--reports-root",
                str(reports_root),
                "--write-md",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    md_path = output_dir / "single_run.md"
    assert md_path.is_file()
    text = md_path.read_text(encoding="utf-8")
    assert "# GoodQ Control Recurrence Report" in text
    assert "## Recommendation" in text
    assert "## Category Counts" in text
    assert "## Recovered / Unrecovered / Skipped Counts" in text
    assert "## Phase 6 Health" in text
    assert "## Qdrant Health" in text
    assert "## Top Recurrence Families" in text
    assert "## Blocking Signals" in text
    assert "## Read-Only Disclaimer" in text
    assert "Markdown written:" in capsys.readouterr().err


def test_markdown_single_report_uses_repo_relative_run_roots() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    run_root = repo_root / "reports" / "fresh_ingest_runs" / "portable_run"
    report = {
        "report": {"generated_at_utc": "2026-04-28T00:00:00+00:00"},
        "scope": {
            "run_roots": [str(run_root)],
            "episodes": 1,
            "signals": 0,
        },
        "recommendation": {"status": "pass", "reasons": []},
        "recurrence_classification": {
            "highest_category": "informational",
            "category_counts": {},
            "blocking_families": [],
        },
        "recovered_vs_unrecovered_failures": {},
        "phase6_qdrant_truth": {
            "status": "healthy",
            "healthy": True,
            "episodes_healthy": 1,
            "episodes_total": 1,
        },
        "top_repeated_failure_families": [],
    }

    text = render_markdown_report(report)

    assert "`reports/fresh_ingest_runs/portable_run`" in text
    assert str(repo_root) not in text


def test_control_recurrence_cli_writes_comparison_markdown(tmp_path: Path, capsys) -> None:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    baseline_root = reports_root / "baseline_run"
    candidate_root = reports_root / "candidate_run"
    baseline_epoch = tmp_path / "GoodQ_Data" / "epochs" / "epoch_baseline"
    candidate_epoch = tmp_path / "GoodQ_Data" / "epochs" / "epoch_candidate"
    baseline_ep = _episode_artifacts(
        run_root=baseline_root,
        epoch_root=baseline_epoch,
        episode_dir_name="01x01_scene_context_llm",
        episode_name="01x01 - Good News, Bad News.mp4",
        run_id="baseline-runtime",
        video_id="baseline-video",
        scene_ids=["baseline-scene"],
        speaker_skip_index=None,
    )
    candidate_ep = _episode_artifacts(
        run_root=candidate_root,
        epoch_root=candidate_epoch,
        episode_dir_name="01x02_scene_context_llm",
        episode_name="01x02 - The Stakeout.mp4",
        run_id="candidate-runtime",
        video_id="candidate-video",
        scene_ids=["candidate-scene"],
        speaker_skip_index=None,
    )
    _write_json(
        baseline_root / "experiment_log.json",
        {
            "epoch": "epoch_baseline",
            "status": "completed",
            "plan": [{"episode": "01x01 - Good News, Bad News.mp4", "status": "passed", "run_dir": str(baseline_ep)}],
        },
    )
    _write_json(
        candidate_root / "experiment_log.json",
        {
            "epoch": "epoch_candidate",
            "status": "completed",
            "plan": [{"episode": "01x02 - The Stakeout.mp4", "status": "passed", "run_dir": str(candidate_ep)}],
        },
    )
    _append_jsonl(baseline_epoch / "logs" / "step_runs.jsonl", [])
    _append_jsonl(candidate_epoch / "logs" / "step_runs.jsonl", [])

    output_dir = tmp_path / "md"
    assert (
        recurrence_cli_main(
            [
                "--baseline-run-id",
                "baseline_run",
                "--candidate-run-id",
                "candidate_run",
                "--reports-root",
                str(reports_root),
                "--write-md",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    md_path = output_dir / "baseline_run__vs__candidate_run.md"
    assert md_path.is_file()
    text = md_path.read_text(encoding="utf-8")
    assert "# GoodQ Control Recurrence Comparison" in text
    assert "Baseline run ID: `baseline_run`" in text
    assert "Candidate run ID: `candidate_run`" in text
    assert "## New / Increased / Resolved Families" in text
    assert "## Blocking Signals" in text
    assert "## Read-Only Disclaimer" in text
    assert "Markdown written:" in capsys.readouterr().err


def test_control_recurrence_cli_writes_single_run_json_file(tmp_path: Path, capsys) -> None:
    reports_root, _ = _simple_run_fixture(tmp_path, "single_run")
    output_dir = tmp_path / "artifacts"

    assert (
        recurrence_cli_main(
            [
                "--run-id",
                "single_run",
                "--reports-root",
                str(reports_root),
                "--write-json-file",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    json_path = output_dir / "single_run.json"
    assert json_path.is_file()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["report"]["name"] == "control_recurrence_report"
    assert payload["scope"]["episodes"] == 1
    assert ":\\\\" not in json_path.read_text(encoding="utf-8")
    err = capsys.readouterr().err
    assert "JSON written:" in err
    assert "Index written:" in err


def test_control_recurrence_cli_writes_comparison_json_file(tmp_path: Path) -> None:
    reports_root, _ = _simple_run_fixture(
        tmp_path,
        "baseline_run",
        episode_name="01x01 - Good News, Bad News.mp4",
        run_id="baseline-runtime",
        video_id="baseline-video",
    )
    _simple_run_fixture(
        tmp_path,
        "candidate_run",
        episode_name="01x02 - The Stakeout.mp4",
        run_id="candidate-runtime",
        video_id="candidate-video",
    )
    output_dir = tmp_path / "artifacts"

    assert (
        recurrence_cli_main(
            [
                "--baseline-run-id",
                "baseline_run",
                "--candidate-run-id",
                "candidate_run",
                "--reports-root",
                str(reports_root),
                "--write-json-file",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    json_path = output_dir / "baseline_run__vs__candidate_run.json"
    assert json_path.is_file()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["report"]["name"] == "control_recurrence_comparison"
    assert payload["baseline"]["run_id"] == "baseline_run"
    assert payload["candidate"]["run_id"] == "candidate_run"


def test_control_recurrence_index_creation_update_and_list_modes(tmp_path: Path, capsys) -> None:
    reports_root, _ = _simple_run_fixture(tmp_path, "single_run")
    _simple_run_fixture(
        tmp_path,
        "candidate_run",
        episode_name="01x02 - The Stakeout.mp4",
        run_id="candidate-runtime",
        video_id="candidate-video",
    )
    output_dir = tmp_path / "artifacts"

    assert (
        recurrence_cli_main(
            [
                "--run-id",
                "single_run",
                "--reports-root",
                str(reports_root),
                "--write-md",
                "--write-json-file",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )
    assert (
        recurrence_cli_main(
            [
                "--baseline-run-id",
                "single_run",
                "--candidate-run-id",
                "candidate_run",
                "--reports-root",
                str(reports_root),
                "--write-json-file",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    index_path = output_dir / "index.json"
    assert index_path.is_file()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    entries = {entry["report_id"]: entry for entry in index["reports"]}
    assert set(entries) == {"single_run", "single_run__vs__candidate_run"}
    assert entries["single_run"]["report_type"] == "single_run"
    assert entries["single_run"]["run_id"] == "single_run"
    assert entries["single_run"]["markdown_path"] == "single_run.md"
    assert entries["single_run"]["json_path"] == "single_run.json"
    assert entries["single_run__vs__candidate_run"]["report_type"] == "comparison"
    assert entries["single_run__vs__candidate_run"]["baseline_run_id"] == "single_run"
    assert entries["single_run__vs__candidate_run"]["candidate_run_id"] == "candidate_run"

    capsys.readouterr()
    assert recurrence_cli_main(["--list-reports", "--output-dir", str(output_dir)]) == 0
    human = capsys.readouterr().out
    assert "GoodQ Control Recurrence Report Index" in human
    assert "single_run" in human
    assert "single_run__vs__candidate_run" in human

    assert recurrence_cli_main(["--list-reports", "--output-dir", str(output_dir), "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert len(listed["reports"]) == 2
    assert {entry["report_id"] for entry in listed["reports"]} == {"single_run", "single_run__vs__candidate_run"}


def test_control_recurrence_json_stdout_stays_valid_with_json_file_write(tmp_path: Path, capsys) -> None:
    reports_root, _ = _simple_run_fixture(tmp_path, "single_run")
    output_dir = tmp_path / "artifacts"

    assert (
        recurrence_cli_main(
            [
                "--run-id",
                "single_run",
                "--reports-root",
                str(reports_root),
                "--json",
                "--write-json-file",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    file_payload = json.loads((output_dir / "single_run.json").read_text(encoding="utf-8"))
    assert stdout_payload["report"]["name"] == "control_recurrence_report"
    assert file_payload["report"]["name"] == "control_recurrence_report"
    assert "JSON written:" in captured.err
    assert "Index written:" in captured.err
