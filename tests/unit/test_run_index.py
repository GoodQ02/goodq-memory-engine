from __future__ import annotations

import json
from pathlib import Path

from lib.run_index import list_runs


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_list_runs_prefers_newest_root_and_tracks_progress(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"

    completed_root = reports_root / "20260424_003250_season1_recompare_witness"
    _write_json(
        completed_root / "experiment_log.json",
        {
            "ts_utc": "2026-04-24T00:32:50+00:00",
            "epoch": "epoch_2026_04_24_season1_recompare_witness",
            "source_dir": "samples\\ingestion\\Sein_Experiment",
            "status": "completed",
            "plan": [
                {"episode": "01x01 - Good News, Bad News.mp4", "status": "passed"},
            ],
        },
    )

    running_root = reports_root / "20260424_182406_season2_fresh_witness"
    _write_json(
        running_root / "experiment_log.json",
        {
            "ts_utc": "2026-04-24T23:24:06+00:00",
            "epoch": "epoch_2026_04_24_season2_witness",
            "source_dir": "samples\\ingestion\\Sein_Experiment",
            "status": "running",
            "plan": [
                {"episode": "02x01 - The Ex-Girlfriend.mp4", "status": "passed"},
                {"episode": "02x02 - The Pony Remark.mp4", "status": "pending"},
            ],
        },
    )

    runs = list_runs(reports_root=reports_root)

    assert [run["run_id"] for run in runs] == [
        "20260424_182406_season2_fresh_witness",
        "20260424_003250_season1_recompare_witness",
    ]
    assert runs[0]["status"] == "running"
    assert runs[0]["episodes_total"] == 2
    assert runs[0]["episodes_completed"] == 1
    assert runs[0]["episodes_pending"] == 1
    assert runs[0]["latest_episode"]["episode"] == "02x02 - The Pony Remark.mp4"
    assert runs[1]["status"] == "completed"
    assert runs[1]["episodes_completed"] == 1


def test_list_runs_projects_pending_lane_as_running_when_activity_files_exist(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    running_root = reports_root / "20260424_182406_season2_fresh_witness"
    active_run_dir = running_root / "02x02_scene_context_llm"

    _write_json(
        running_root / "experiment_log.json",
        {
            "ts_utc": "2026-04-24T23:24:06+00:00",
            "epoch": "epoch_2026_04_24_season2_witness",
            "source_dir": "samples\\ingestion\\Sein_Experiment",
            "status": "running",
            "plan": [
                {"episode": "02x01 - The Ex-Girlfriend.mp4", "status": "passed"},
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

    runs = list_runs(reports_root=reports_root)

    assert runs[0]["episodes_completed"] == 1
    assert runs[0]["episodes_running"] == 1
    assert runs[0]["episodes_pending"] == 0
    assert runs[0]["latest_episode"]["episode"] == "02x02 - The Pony Remark.mp4"
    assert runs[0]["latest_episode"]["status"] == "running"


def test_list_runs_indexes_standalone_scene_results_without_experiment_log(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    run_root = reports_root / "20260519_home_memory_scene_probe"

    _write_json(
        run_root / "output" / "scene_ingest_results.json",
        {
            "scenes": [
                {"scene_id": "scene-a", "video_id": "home-video"},
                {"scene_id": "scene-b", "video_id": "home-video"},
            ],
        },
    )

    runs = list_runs(reports_root=reports_root)

    assert len(runs) == 1
    assert runs[0]["run_id"] == "20260519_home_memory_scene_probe"
    assert runs[0]["run_kind"] == "standalone_scene_results"
    assert runs[0]["scope"] == "scene_ingest_results"
    assert runs[0]["status"] == "completed"
    assert runs[0]["episodes_total"] == 1
    assert runs[0]["episodes_completed"] == 1
    assert runs[0]["scenes_processed"] == 2
    assert runs[0]["latest_episode"]["scene_count"] == 2
    assert runs[0]["latest_episode"]["run_dir"] == str(run_root)


def test_list_runs_indexes_resolved_config_only_root_as_interrupted(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    run_root = reports_root / "20260520_power_loss_interrupted"

    _write_json(
        run_root / "_resolved_config.json",
        {
            "run": {"id": "runtime-power-loss"},
            "qdrant": {"collections": {"audio": "goodq_audio_epoch_power_loss"}},
            "paths": {"data_root": "GoodQ_Data/epochs/epoch_home_clean"},
        },
    )
    (run_root / "output").mkdir(parents=True, exist_ok=True)

    runs = list_runs(reports_root=reports_root)

    assert len(runs) == 1
    assert runs[0]["run_id"] == "20260520_power_loss_interrupted"
    assert runs[0]["run_kind"] == "interrupted_ingestion"
    assert runs[0]["scope"] == "resolved_config_only"
    assert runs[0]["status"] == "interrupted"
    assert runs[0]["runtime_run_id"] == "runtime-power-loss"
    assert runs[0]["qdrant_collections"]["audio"] == "goodq_audio_epoch_power_loss"
    assert runs[0]["episodes_total"] == 1
    assert runs[0]["episodes_completed"] == 0
    assert runs[0]["episodes_failed"] == 0
    assert runs[0]["episodes_running"] == 0
    assert runs[0]["episodes_pending"] == 0
    assert runs[0]["scenes_processed"] == 0
    assert runs[0]["latest_episode"]["status"] == "interrupted"
    assert runs[0]["latest_episode"]["scene_count"] == 0
    assert str(run_root / "_resolved_config.json") in runs[0]["latest_episode"]["files_read"]
