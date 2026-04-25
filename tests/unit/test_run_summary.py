from __future__ import annotations

import json
from pathlib import Path

from lib.run_summary import load_run_summary


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_load_run_summary_normalizes_current_artifacts_without_reviving_legacy_fields(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    run_root = reports_root / "20260424_182406_season2_fresh_witness"

    temporal_index = tmp_path / "epochs" / "epoch_2026_04_24_season2_witness" / "processing" / "02x01 - The Ex-Girlfriend" / "temporal_index.json"
    scene_manifest = tmp_path / "epochs" / "epoch_2026_04_24_season2_witness" / "processing" / "02x01 - The Ex-Girlfriend" / "video" / "scene_manifest.json"
    _write_json(temporal_index, {"segments": [{}, {}], "phase6_complete": True})
    _write_json(scene_manifest, {"scenes": [{}, {}]})

    _write_json(
        run_root / "experiment_log.json",
        {
            "ts_utc": "2026-04-24T23:24:06+00:00",
            "epoch": "epoch_2026_04_24_season2_witness",
            "source_dir": "samples\\ingestion\\Sein_Experiment",
            "status": "completed",
            "plan": [
                {
                    "episode": "02x01 - The Ex-Girlfriend.mp4",
                    "status": "passed",
                    "run_dir": str(run_root / "02x01_scene_context_llm"),
                },
                {
                    "episode": "02x02 - The Pony Remark.mp4",
                    "status": "failed",
                    "run_dir": str(run_root / "02x02_scene_context_llm"),
                },
            ],
        },
    )
    _write_json(
        run_root / "02x01_scene_context_llm" / "experiment_log.json",
        {
            "episode": "02x01 - The Ex-Girlfriend.mp4",
            "status": "passed",
            "ts_utc": "2026-04-25T00:44:33+00:00",
            "metrics": {
                "common": {"scene_count": 40, "phase6_complete": True, "qdrant_ok": True},
                "output_path": str(run_root / "02x01_scene_context_llm" / "output" / "scene_ingest_results.json"),
                "temporal_index_path": str(temporal_index),
                "scene_manifest_path": str(scene_manifest),
            },
            "notes": ["http://127.0.0.1:38005/v1/models -> 200"],
        },
    )

    summary = load_run_summary(run_root=run_root)

    assert summary["run_header"]["run_id"] == "20260424_182406_season2_fresh_witness"
    assert summary["run_header"]["status"] == "completed"
    assert summary["file_job_overview"]["episodes_total"] == 2
    assert summary["file_job_overview"]["episodes_completed"] == 1
    assert summary["file_job_overview"]["episodes_failed"] == 1
    assert summary["file_job_overview"]["scenes_processed"] == 40
    assert summary["file_job_overview"]["steps_executed"] == "unknown"
    assert summary["audio_wsl2_summary"]["notes"] == "not observed"
    assert summary["outcome_classification"]["status"] == "partial_success"
    assert str(run_root / "experiment_log.json") in summary["evidence"]["files_read"]
    assert str(temporal_index) in summary["evidence"]["canonical_episode_artifacts"]


def test_load_run_summary_projects_active_pending_lane_as_running_without_episode_record(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    run_root = reports_root / "20260424_182406_season2_fresh_witness"
    active_run_dir = run_root / "02x02_scene_context_llm"

    _write_json(
        run_root / "experiment_log.json",
        {
            "ts_utc": "2026-04-24T23:24:06+00:00",
            "epoch": "epoch_2026_04_24_season2_witness",
            "source_dir": "samples\\ingestion\\Sein_Experiment",
            "status": "running",
            "plan": [
                {
                    "episode": "02x01 - The Ex-Girlfriend.mp4",
                    "status": "passed",
                    "run_dir": str(run_root / "02x01_scene_context_llm"),
                },
                {
                    "episode": "02x02 - The Pony Remark.mp4",
                    "status": "pending",
                    "run_dir": str(active_run_dir),
                },
            ],
        },
    )
    (active_run_dir / "workspace").mkdir(parents=True, exist_ok=True)
    (active_run_dir / "workspace" / "_resolved_config.json").write_text("{}", encoding="utf-8")
    (active_run_dir / "ingest.stdout.log").write_text("[STEP 03/16] object_detect\n", encoding="utf-8")

    summary = load_run_summary(run_root=run_root)

    assert summary["run_header"]["status"] == "running"
    assert summary["file_job_overview"]["episodes_total"] == 2
    assert summary["file_job_overview"]["episodes_completed"] == 1
    assert summary["file_job_overview"]["episodes_running"] == 1
    assert summary["file_job_overview"]["episodes_pending"] == 0
    assert summary["outcome_classification"]["status"] == "running"
    assert summary["latest_episode"]["episode"] == "02x02 - The Pony Remark.mp4"
    assert summary["latest_episode"]["status"] == "running"
