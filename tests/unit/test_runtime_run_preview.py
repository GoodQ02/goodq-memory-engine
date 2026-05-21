from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path


def _load_runtime_route_module(repo_root: Path):
    module_path = repo_root / "api" / "routes" / "runtime.py"
    spec = importlib.util.spec_from_file_location("tests.runtime_run_preview", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def test_latest_run_preview_uses_read_only_summary_projection(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    fake_config_loader = types.ModuleType("steps.common.config_loader")
    fake_config_loader.load_configs = lambda overrides=None: {
        "paths": {"data_root": "data", "db_path": "data/memory.db"},
        "host": {},
        "memory": {},
        "llm": {},
    }
    monkeypatch.setitem(sys.modules, "steps.common.config_loader", fake_config_loader)

    fake_memory_store = types.ModuleType("steps.common.memory_store")
    fake_memory_store.normalize_memory_tier_list = lambda values: values
    monkeypatch.setitem(sys.modules, "steps.common.memory_store", fake_memory_store)

    fake_ingest_requests = types.ModuleType("api.utils.ingest_requests")
    fake_ingest_requests.is_supported_ingest_path = lambda path: True
    monkeypatch.setitem(sys.modules, "api.utils.ingest_requests", fake_ingest_requests)

    fake_goodq_version = types.ModuleType("goodq_version")
    fake_goodq_version.GOODQ_VERSION = "test"
    monkeypatch.setitem(sys.modules, "goodq_version", fake_goodq_version)

    runtime = _load_runtime_route_module(repo_root)

    monkeypatch.setattr(
        runtime,
        "_scroll_qdrant_audio_payloads",
        lambda runtime_run_id, collection_candidates: {"status": "ok", "collection": "goodq_audio_epoch_test", "payloads": []},
    )
    monkeypatch.setattr(
        runtime,
        "_sample_qdrant_audio_payloads",
        lambda collection_candidates: {"status": "ok", "collection": "goodq_audio_epoch_test", "sample_count": 0},
        raising=False,
    )

    monkeypatch.setattr(
        runtime.run_index,
        "list_runs",
        lambda reports_root=None, limit=None: [
            {
                "run_id": "20260424_182406_season2_fresh_witness",
                "status": "running",
                "epoch": "epoch_2026_04_24_season2_witness",
            }
        ],
    )
    monkeypatch.setattr(
        runtime.run_summary,
        "load_run_summary",
        lambda run_root, reports_root=None: {
            "run_header": {
                "run_id": "20260424_182406_season2_fresh_witness",
                "status": "running",
                "epoch": "epoch_2026_04_24_season2_witness",
                "source_dir": "samples\\ingestion\\Sein_Experiment",
                "start_time": "2026-04-24T23:24:06+00:00",
                "end_time": "unknown",
                "total_duration_seconds": "unknown",
                "trigger_source": "watchdog",
            },
            "file_job_overview": {
                "episodes_total": 12,
                "episodes_completed": 5,
                "episodes_failed": 0,
                "episodes_running": 1,
                "episodes_pending": 6,
                "scenes_processed": 195,
            },
            "outcome_classification": {"status": "running"},
            "latest_episode": {
                "episode": "02x06 - The Statue.mp4",
                "status": "running",
            },
        },
    )

    preview = runtime._latest_run_preview()

    assert preview["available"] is True
    assert preview["run_id"] == "20260424_182406_season2_fresh_witness"
    assert preview["status"] == "running"
    assert preview["episodes_total"] == 12
    assert preview["episodes_completed"] == 5
    assert preview["latest_episode"]["episode"] == "02x06 - The Statue.mp4"


def test_latest_run_preview_redacts_local_paths(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    fake_config_loader = types.ModuleType("steps.common.config_loader")
    fake_config_loader.load_configs = lambda overrides=None: {
        "paths": {"data_root": "data", "db_path": "data/memory.db"},
        "host": {},
        "memory": {},
        "llm": {},
    }
    monkeypatch.setitem(sys.modules, "steps.common.config_loader", fake_config_loader)

    fake_memory_store = types.ModuleType("steps.common.memory_store")
    fake_memory_store.normalize_memory_tier_list = lambda values: values
    monkeypatch.setitem(sys.modules, "steps.common.memory_store", fake_memory_store)

    fake_ingest_requests = types.ModuleType("api.utils.ingest_requests")
    fake_ingest_requests.is_supported_ingest_path = lambda path: True
    monkeypatch.setitem(sys.modules, "api.utils.ingest_requests", fake_ingest_requests)

    fake_goodq_version = types.ModuleType("goodq_version")
    fake_goodq_version.GOODQ_VERSION = "test"
    monkeypatch.setitem(sys.modules, "goodq_version", fake_goodq_version)

    runtime = _load_runtime_route_module(repo_root)

    monkeypatch.setattr(
        runtime.run_index,
        "list_runs",
        lambda reports_root=None, limit=None: [
            {
                "run_id": "20260424_182406_season2_fresh_witness",
                "status": "running",
                "epoch": "epoch_2026_04_24_season2_witness",
                "run_root": r"L:\_DATA\GoodQ_Data\reports\run_001",
            }
        ],
    )
    monkeypatch.setattr(
        runtime.run_summary,
        "load_run_summary",
        lambda run_root, reports_root=None: {
            "run_header": {
                "run_id": "20260424_182406_season2_fresh_witness",
                "status": "running",
                "epoch": "epoch_2026_04_24_season2_witness",
                "source_dir": r"L:\_DATA\GoodQ_Data\import_inbox\home_movies",
            },
            "file_job_overview": {"episodes_total": 1, "scenes_processed": 3},
            "outcome_classification": {"status": "running"},
            "latest_episode": {
                "episode": r"L:\_DATA\GoodQ_Data\import_inbox\home_movies\summer.mp4",
                "status": "running",
                "scene_count": 3,
                "canonical_episode_artifacts": [
                    r"L:\_DATA\GoodQ_Data\epochs\demo\processing\summer\temporal_index.json"
                ],
                "files_read": [
                    r"L:\_DATA\GoodQ_Data\epochs\demo\processing\summer\scene_ingest_results.json"
                ],
            },
        },
    )

    preview = runtime._latest_run_preview()
    serialized = json.dumps(preview)

    assert "L:" not in serialized
    assert "_DATA" not in serialized
    assert preview["source_dir"] == "<local-only>"
    assert preview["source_dir_redacted"] is True
    assert preview["raw_paths"] == "redacted"
    assert preview["latest_episode"]["episode"] == "summer.mp4"
    assert preview["latest_episode"]["artifact_count"] == 2
    assert preview["latest_episode"]["artifact_paths_redacted"] is True
    assert "canonical_episode_artifacts" not in preview["latest_episode"]
    assert "files_read" not in preview["latest_episode"]


def test_storage_summary_redacts_paths_and_reports_bounded_sizes(monkeypatch, tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    data_root = tmp_path / "GoodQ_Data"
    import_inbox = data_root / "import_inbox"
    processing = data_root / "epochs" / "epoch_test" / "processing"
    logs = data_root / "epochs" / "epoch_test" / "logs"
    faiss = data_root / "epochs" / "epoch_test" / "faiss"
    qdrant = tmp_path / "qdrant_storage"
    cache = data_root / "cache"
    reports = data_root / "reports"
    for path in (import_inbox, processing, logs, faiss, qdrant, cache, reports):
        path.mkdir(parents=True)
    (import_inbox / "sample.mp4").write_bytes(b"abc")
    (logs / "step_runs.jsonl").write_text("{}", encoding="utf-8")

    fake_config_loader = types.ModuleType("steps.common.config_loader")
    fake_config_loader.load_configs = lambda overrides=None: {
        "paths": {
            "data_root": str(data_root),
            "db_path": str(data_root / "memory.db"),
            "import_inbox": str(import_inbox),
            "processing": str(processing),
            "log_dir": str(logs),
            "faiss_dir": str(faiss),
            "qdrant_storage": str(qdrant),
            "model_cache": str(cache),
        },
        "host": {},
        "memory": {},
        "llm": {},
    }
    monkeypatch.setitem(sys.modules, "steps.common.config_loader", fake_config_loader)

    fake_memory_store = types.ModuleType("steps.common.memory_store")
    fake_memory_store.normalize_memory_tier_list = lambda values: values
    monkeypatch.setitem(sys.modules, "steps.common.memory_store", fake_memory_store)

    fake_ingest_requests = types.ModuleType("api.utils.ingest_requests")
    fake_ingest_requests.is_supported_ingest_path = lambda path: True
    monkeypatch.setitem(sys.modules, "api.utils.ingest_requests", fake_ingest_requests)

    fake_goodq_version = types.ModuleType("goodq_version")
    fake_goodq_version.GOODQ_VERSION = "test"
    monkeypatch.setitem(sys.modules, "goodq_version", fake_goodq_version)
    monkeypatch.setenv("GOODQ_RUN_REPORTS_ROOT", str(reports))

    runtime = _load_runtime_route_module(repo_root)
    summary = runtime.get_storage_summary()

    assert summary["status"] == "ok"
    assert summary["mode"] == "read_only"
    assert summary["raw_paths"] == "redacted"
    assert summary["disk"]["available"] is True
    assert any(row["name"] == "import_inbox" and row["exists"] for row in summary["roots"])
    serialized = json.dumps(summary)
    assert str(tmp_path) not in serialized
    assert "sample.mp4" not in serialized


def test_latest_run_evidence_summarizes_artifacts_without_paths(monkeypatch, tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    fake_config_loader = types.ModuleType("steps.common.config_loader")
    fake_config_loader.load_configs = lambda overrides=None: {
        "paths": {"data_root": "data", "db_path": "data/memory.db"},
        "host": {},
        "memory": {},
        "llm": {},
    }
    monkeypatch.setitem(sys.modules, "steps.common.config_loader", fake_config_loader)

    fake_memory_store = types.ModuleType("steps.common.memory_store")
    fake_memory_store.normalize_memory_tier_list = lambda values: values
    monkeypatch.setitem(sys.modules, "steps.common.memory_store", fake_memory_store)

    fake_ingest_requests = types.ModuleType("api.utils.ingest_requests")
    fake_ingest_requests.is_supported_ingest_path = lambda path: True
    monkeypatch.setitem(sys.modules, "api.utils.ingest_requests", fake_ingest_requests)

    fake_goodq_version = types.ModuleType("goodq_version")
    fake_goodq_version.GOODQ_VERSION = "test"
    monkeypatch.setitem(sys.modules, "goodq_version", fake_goodq_version)

    runtime = _load_runtime_route_module(repo_root)
    monkeypatch.setattr(
        runtime,
        "_scroll_qdrant_audio_payloads",
        lambda runtime_run_id, collection_candidates: {"status": "ok", "collection": "goodq_audio_epoch_test", "payloads": []},
    )
    monkeypatch.setattr(
        runtime,
        "_sample_qdrant_audio_payloads",
        lambda collection_candidates: {"status": "ok", "collection": "goodq_audio_epoch_test", "sample_count": 0},
    )

    run_dir = tmp_path / "run" / "02x01"
    run_dir.mkdir(parents=True)
    epoch_root = tmp_path / "GoodQ_Data" / "epochs" / "epoch_test"
    temporal_dir = epoch_root / "processing" / "episode-a"
    temporal_dir.mkdir(parents=True)
    (epoch_root / "logs").mkdir(parents=True)
    scene_results_path = run_dir / "output" / "scene_ingest_results.json"
    scene_results_path.parent.mkdir(parents=True)
    temporal_path = temporal_dir / "temporal_index.json"
    step_runs_path = epoch_root / "logs" / "step_runs.jsonl"

    temporal_path.write_text(
        json.dumps(
            {
                "version": "test",
                "total_scenes": 2,
                "total_duration": 61.5,
                "content_summary": "test episode",
                "phase5_complete": True,
                "phase6_complete": True,
                "phase6_harmonized": True,
                "has_audio": True,
                "has_transcripts": True,
                "segments_with_audio_emotion": 2,
                "top_audio_emotions": [{"label": "calm", "count": 2}],
                "segments": [
                    {
                        "scene_id": "scene-a",
                        "audio_emotion": "calm",
                        "sentiment": {"label": "positive", "score": 0.91},
                    },
                    {
                        "scene_id": "scene-b",
                        "audio_emotion": "calm",
                        "sentiment_label": "neutral",
                        "sentiment_score": 0.52,
                        "visual_caption": "projected caption",
                        "clap_meta": {"status": "ok"},
                    },
                    {
                        "scene_id": "scene-c",
                        "audio_emotion": "calm",
                        "sentiment_score": 0.0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    scene_results_path.write_text(
        json.dumps(
            {
                "scene_meta": {"scene_count": 2},
                "qdrant_ok": True,
                "faiss_ok": "not_attempted",
                "knowledge_graph_status": "ok",
                "phase6_complete": True,
                "phase6_qdrant_ok": True,
                "control_agent_status": "observed",
                "modality_status": {"audio": "ok", "vision": "ok"},
                "content_summary": "graph projection ready",
                "scenes": [
                    {
                        "scene_id": "scene-a",
                        "keyframe": {"caption": "source caption"},
                        "audio": {
                            "sentiment": {"label": "positive", "score": 0.91},
                            "clap_meta": {"status": "ok"},
                        },
                    },
                    {
                        "scene_id": "scene-b",
                        "keyframe": {"caption": "projected caption"},
                        "audio": {
                            "sentiment": {"label": "neutral", "score": 0.52},
                            "clap_meta": {"status": "ok"},
                        },
                    },
                    {
                        "scene_id": "scene-c",
                        "sentiment_score": 0.0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    step_runs_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "ts": "2026-04-24T00:00:00",
                        "step": "video_scene_detect",
                        "status": "ok",
                        "duration_ms": 10.5,
                        "source_path": str(tmp_path / "secret.mp4"),
                    }
                ),
                json.dumps(
                    {
                        "ts": "2026-04-24T00:00:01",
                        "step": "image_caption",
                        "status": "ok",
                        "duration_ms": 20.25,
                        "source_path": str(tmp_path / "frame.jpg"),
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        runtime.run_index,
        "list_runs",
        lambda reports_root=None, limit=None: [{"run_id": "run_a", "status": "success", "epoch": "epoch_test"}],
    )
    monkeypatch.setattr(
        runtime.run_summary,
        "load_run_summary",
        lambda run_root, reports_root=None: {
            "run_header": {
                "run_id": "run_a",
                "status": "success",
                "epoch": "epoch_test",
                "run_kind": "standalone_scene_results",
                "scope": "scene_ingest_results",
            },
            "file_job_overview": {"episodes_total": 1, "episodes_completed": 1, "episodes_failed": 0, "scenes_processed": 2},
            "outcome_classification": {"status": "success"},
            "latest_episode": {
                "episode": "episode-a.mp4",
                "status": "passed",
                "run_dir": str(run_dir),
                "scene_count": 2,
                "phase6_complete": True,
                "qdrant_ok": True,
                "files_read": [str(scene_results_path), str(temporal_path)],
                "canonical_episode_artifacts": [str(temporal_path)],
                "errors": [],
                "warnings": [],
            },
        },
    )

    evidence = runtime._latest_run_evidence()

    assert evidence["available"] is True
    assert evidence["run"]["run_kind"] == "standalone_scene_results"
    assert evidence["run"]["scope"] == "scene_ingest_results"
    assert evidence["artifact_presence"]["step_runs_jsonl"] is True
    assert evidence["step_runs"]["row_count"] == 2
    assert evidence["temporal_index"]["total_scenes"] == 2
    assert evidence["sentiment"]["segments_with_audio_emotion"] == 2
    assert evidence["knowledge_graph"]["status"] == "ok"
    assert evidence["knowledge_graph"]["qdrant_ok"] is True
    assert evidence["audio_vector_proof"]["status"] == "no_current_run_evidence"
    assert evidence["audio_vector_proof"]["runtime_run_id_resolved"] is True
    assert evidence["audio_vector_proof"]["runtime_run_id_source"] == "run_header.run_id"
    assert evidence["audio_vector_proof"]["reason"] == "no_qdrant_payloads_matched_run_id"
    projection_gaps = evidence["projection_gaps"]
    assert projection_gaps["status"] == "gap_detected"
    assert projection_gaps["scene_scope_count"] == 3
    assert projection_gaps["fields"]["visual_caption"] == {
        "source_present": 2,
        "temporal_present": 1,
        "missing_from_temporal": 1,
        "status": "gap_detected",
    }
    assert projection_gaps["fields"]["sentiment"] == {
        "source_present": 3,
        "temporal_present": 3,
        "missing_from_temporal": 0,
        "status": "ok",
    }
    assert projection_gaps["fields"]["clap_meta"] == {
        "source_present": 2,
        "temporal_present": 1,
        "missing_from_temporal": 1,
        "status": "gap_detected",
    }
    assert projection_gaps["sample_missing"][0] == {
        "scene_id": "scene-a",
        "fields": ["visual_caption", "clap_meta"],
    }
    serialized = json.dumps(evidence)
    assert str(tmp_path) not in serialized
    assert "source_path" not in serialized
    assert "source caption" not in serialized


def test_audio_vector_proof_resolves_run_header_run_id_without_overclaiming(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    fake_config_loader = types.ModuleType("steps.common.config_loader")
    fake_config_loader.load_configs = lambda overrides=None: {
        "paths": {"data_root": "data", "db_path": "data/memory.db"},
        "host": {},
        "memory": {},
        "llm": {},
        "qdrant": {"enabled": True, "host": "http://127.0.0.1:6333", "collections": {"audio": "goodq_audio_test"}},
    }
    monkeypatch.setitem(sys.modules, "steps.common.config_loader", fake_config_loader)

    fake_memory_store = types.ModuleType("steps.common.memory_store")
    fake_memory_store.normalize_memory_tier_list = lambda values: values
    monkeypatch.setitem(sys.modules, "steps.common.memory_store", fake_memory_store)

    fake_ingest_requests = types.ModuleType("api.utils.ingest_requests")
    fake_ingest_requests.is_supported_ingest_path = lambda path: True
    monkeypatch.setitem(sys.modules, "api.utils.ingest_requests", fake_ingest_requests)

    fake_goodq_version = types.ModuleType("goodq_version")
    fake_goodq_version.GOODQ_VERSION = "test"
    monkeypatch.setitem(sys.modules, "goodq_version", fake_goodq_version)

    runtime = _load_runtime_route_module(repo_root)

    monkeypatch.setattr(
        runtime,
        "_scroll_qdrant_audio_payloads",
        lambda runtime_run_id, collection_candidates: {"status": "ok", "collection": "goodq_audio_epoch_test", "payloads": []},
    )
    monkeypatch.setattr(
        runtime,
        "_sample_qdrant_audio_payloads",
        lambda collection_candidates: {
            "status": "ok",
            "collection": "goodq_audio_epoch_test",
            "sample_count": 2,
            "missing_required_fields": {"run_id": 2, "embedding_id": 2},
        },
        raising=False,
    )

    proof = runtime._summarize_audio_vector_proof(
        header={"epoch": "epoch_test", "run_id": "run-summary-alpha"},
        latest_episode={},
        temporal_payload={"total_scenes": 2, "video_id": "video-a"},
        scene_results_payload={
            "scenes": [
                {"scene_id": "scene-a", "video_id": "video-a", "audio": {"clap_meta": {"status": "ok"}}},
                {"scene_id": "scene-b", "video_id": "video-a", "audio": {"clap_meta": {"status": "ok"}}},
            ]
        },
    )

    assert proof["runtime_run_id_resolved"] is True
    assert proof["runtime_run_id_source"] == "run_header.run_id"
    assert proof["status"] == "no_current_run_evidence"
    assert proof["reason"] == "no_qdrant_payloads_matched_run_id"
    assert proof["current_run_qdrant_proven"] == 0
    assert proof["qdrant_run_matched_points"] == 0
    assert proof["audio_payload_sample"]["sample_count"] == 2
    assert proof["audio_payload_sample"]["missing_required_fields"]["run_id"] == 2


def test_audio_vector_proof_prefers_scene_clap_run_id_over_report_slug(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    fake_config_loader = types.ModuleType("steps.common.config_loader")
    fake_config_loader.load_configs = lambda overrides=None: {
        "paths": {"data_root": "data", "db_path": "data/memory.db"},
        "host": {},
        "memory": {},
        "llm": {},
        "qdrant": {"enabled": True, "host": "http://127.0.0.1:6333", "collections": {"audio": "goodq_audio_test"}},
    }
    monkeypatch.setitem(sys.modules, "steps.common.config_loader", fake_config_loader)

    fake_memory_store = types.ModuleType("steps.common.memory_store")
    fake_memory_store.normalize_memory_tier_list = lambda values: values
    monkeypatch.setitem(sys.modules, "steps.common.memory_store", fake_memory_store)

    fake_ingest_requests = types.ModuleType("api.utils.ingest_requests")
    fake_ingest_requests.is_supported_ingest_path = lambda path: True
    monkeypatch.setitem(sys.modules, "api.utils.ingest_requests", fake_ingest_requests)

    fake_goodq_version = types.ModuleType("goodq_version")
    fake_goodq_version.GOODQ_VERSION = "test"
    monkeypatch.setitem(sys.modules, "goodq_version", fake_goodq_version)

    runtime = _load_runtime_route_module(repo_root)

    def fake_post(url, json=None, timeout=None):
        assert json["filter"]["must"][0]["match"]["value"] == "runtime-run-alpha"
        return _FakeResponse(
            200,
            {
                "result": {
                    "points": [
                        {
                            "payload": {
                                "run_id": "runtime-run-alpha",
                                "scene_id": "scene-a",
                                "video_id": "video-a",
                                "embedding_id": "embed-a",
                                "component": "audio_embed_clap",
                                "step": "audio_embed_clap",
                                "model": "laion/clap-htsat-unfused",
                                "created_at": "2026-05-20T00:00:00Z",
                                "commit_ts_utc": "2026-05-20T00:00:00Z",
                                "modality": "audio",
                            }
                        }
                    ],
                    "next_page_offset": None,
                }
            },
        )

    monkeypatch.setattr(runtime.requests, "post", fake_post)

    proof = runtime._summarize_audio_vector_proof(
        header={"epoch": "epoch_test", "run_id": "standalone_report_folder_slug"},
        latest_episode={},
        temporal_payload={"total_scenes": 1, "video_id": "video-a"},
        scene_results_payload={
            "scenes": [
                {
                    "scene_id": "scene-a",
                    "video_id": "video-a",
                    "audio": {"clap_meta": {"status": "ok", "run_id": "runtime-run-alpha"}},
                }
            ]
        },
    )

    assert proof["runtime_run_id_resolved"] is True
    assert proof["runtime_run_id_source"] == "scene_results.scenes.audio.clap_meta.run_id"
    assert proof["status"] == "current_run_audio_vector_proven"
    assert proof["current_run_qdrant_proven"] == 1


def test_sentiment_summary_uses_scene_results_when_temporal_index_missing(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    fake_config_loader = types.ModuleType("steps.common.config_loader")
    fake_config_loader.load_configs = lambda overrides=None: {
        "paths": {"data_root": "data", "db_path": "data/memory.db"},
        "host": {},
        "memory": {},
        "llm": {},
    }
    monkeypatch.setitem(sys.modules, "steps.common.config_loader", fake_config_loader)

    fake_memory_store = types.ModuleType("steps.common.memory_store")
    fake_memory_store.normalize_memory_tier_list = lambda values: values
    monkeypatch.setitem(sys.modules, "steps.common.memory_store", fake_memory_store)

    fake_ingest_requests = types.ModuleType("api.utils.ingest_requests")
    fake_ingest_requests.is_supported_ingest_path = lambda path: True
    monkeypatch.setitem(sys.modules, "api.utils.ingest_requests", fake_ingest_requests)

    fake_goodq_version = types.ModuleType("goodq_version")
    fake_goodq_version.GOODQ_VERSION = "test"
    monkeypatch.setitem(sys.modules, "goodq_version", fake_goodq_version)

    runtime = _load_runtime_route_module(repo_root)

    summary = runtime._summarize_sentiment(
        None,
        scene_results_payload={
            "scenes": [
                {
                    "audio": {
                        "transcript": "hello from the scene",
                        "audio_emotion": "warm",
                        "sentiment": {"label": "positive", "score": 0.82},
                    }
                },
                {"audio": {"full_text": "second scene", "emotion": "calm"}},
            ]
        },
    )

    assert summary["status"] == "ok"
    assert summary["source"] == "scene_ingest_results"
    assert summary["segments_total"] == 2
    assert summary["segments_with_transcript"] == 2
    assert summary["segments_with_audio_emotion"] == 2
    assert summary["segments_with_sentiment"] == 1
    assert summary["top_audio_emotions"] == [{"label": "warm", "count": 1}, {"label": "calm", "count": 1}]
    assert summary["sentiment_labels"] == [{"label": "positive", "count": 1}]


def test_audio_vector_proof_counts_current_run_qdrant_payloads(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    fake_config_loader = types.ModuleType("steps.common.config_loader")
    fake_config_loader.load_configs = lambda overrides=None: {
        "paths": {"data_root": "data", "db_path": "data/memory.db"},
        "host": {},
        "memory": {},
        "llm": {},
        "qdrant": {"enabled": True, "host": "http://127.0.0.1:6333", "collections": {"audio": "goodq_audio_test"}},
    }
    monkeypatch.setitem(sys.modules, "steps.common.config_loader", fake_config_loader)

    fake_memory_store = types.ModuleType("steps.common.memory_store")
    fake_memory_store.normalize_memory_tier_list = lambda values: values
    monkeypatch.setitem(sys.modules, "steps.common.memory_store", fake_memory_store)

    fake_ingest_requests = types.ModuleType("api.utils.ingest_requests")
    fake_ingest_requests.is_supported_ingest_path = lambda path: True
    monkeypatch.setitem(sys.modules, "api.utils.ingest_requests", fake_ingest_requests)

    fake_goodq_version = types.ModuleType("goodq_version")
    fake_goodq_version.GOODQ_VERSION = "test"
    monkeypatch.setitem(sys.modules, "goodq_version", fake_goodq_version)

    runtime = _load_runtime_route_module(repo_root)

    points = [
        {
            "payload": {
                "run_id": "runtime-run-alpha",
                "scene_id": "scene-a",
                "video_id": "video-a",
                "embedding_id": "embed-a",
                "component": "audio_embed_clap",
                "step": "audio_embed_clap",
                "model": "laion/clap-htsat-unfused",
                "created_at": "2026-05-01T00:00:00Z",
                "commit_ts_utc": "2026-05-01T00:00:00Z",
                "modality": "audio",
            }
        },
        {
            "payload": {
                "run_id": "runtime-run-alpha",
                "scene_id": "scene-b",
                "video_id": "video-a",
                "embedding_id": "embed-b",
                "component": "audio_embed_clap",
                "step": "audio_embed_clap",
                "model": "laion/clap-htsat-unfused",
                "created_at": "2026-05-01T00:00:01Z",
                "commit_ts_utc": "2026-05-01T00:00:01Z",
                "modality": "audio",
            }
        },
    ]

    def fake_post(url, json=None, timeout=None):
        assert "goodq_audio_epoch_test" in url
        assert json["filter"]["must"][0]["match"]["value"] == "runtime-run-alpha"
        return _FakeResponse(200, {"result": {"points": points, "next_page_offset": None}})

    monkeypatch.setattr(runtime.requests, "post", fake_post)

    proof = runtime._summarize_audio_vector_proof(
        header={"epoch": "epoch_test", "runtime_run_id": "runtime-run-alpha"},
        latest_episode={},
        temporal_payload={"total_scenes": 2, "video_id": "video-a"},
        scene_results_payload={
            "scenes": [
                {"scene_id": "scene-a", "video_id": "video-a", "audio": {"clap_meta": {"status": "ok"}}},
                {"scene_id": "scene-b", "video_id": "video-a", "audio": {"clap_meta": {"status": "ok"}}},
            ]
        },
    )

    assert proof["status"] == "current_run_audio_vector_proven"
    assert proof["label"] == "Proven"
    assert proof["clap_ok"] == 2
    assert proof["current_run_qdrant_proven"] == 2
    assert proof["qdrant_run_matched_points"] == 2
    assert proof["missing_required_fields"] == {}
    assert proof["collection"] == "goodq_audio_epoch_test"


def test_audio_vector_proof_rejects_legacy_payloads_without_required_fields(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    fake_config_loader = types.ModuleType("steps.common.config_loader")
    fake_config_loader.load_configs = lambda overrides=None: {
        "paths": {"data_root": "data", "db_path": "data/memory.db"},
        "host": {},
        "memory": {},
        "llm": {},
        "qdrant": {"enabled": True, "host": "http://127.0.0.1:6333", "collections": {"audio": "goodq_audio_test"}},
    }
    monkeypatch.setitem(sys.modules, "steps.common.config_loader", fake_config_loader)

    fake_memory_store = types.ModuleType("steps.common.memory_store")
    fake_memory_store.normalize_memory_tier_list = lambda values: values
    monkeypatch.setitem(sys.modules, "steps.common.memory_store", fake_memory_store)

    fake_ingest_requests = types.ModuleType("api.utils.ingest_requests")
    fake_ingest_requests.is_supported_ingest_path = lambda path: True
    monkeypatch.setitem(sys.modules, "api.utils.ingest_requests", fake_ingest_requests)

    fake_goodq_version = types.ModuleType("goodq_version")
    fake_goodq_version.GOODQ_VERSION = "test"
    monkeypatch.setitem(sys.modules, "goodq_version", fake_goodq_version)

    runtime = _load_runtime_route_module(repo_root)

    def fake_post(url, json=None, timeout=None):
        return _FakeResponse(
            200,
            {
                "result": {
                    "points": [
                        {
                            "payload": {
                                "run_id": "runtime-run-alpha",
                                "scene_id": "scene-a",
                                "modality": "audio",
                                "faiss_id": 7,
                            }
                        }
                    ],
                    "next_page_offset": None,
                }
            },
        )

    monkeypatch.setattr(runtime.requests, "post", fake_post)

    proof = runtime._summarize_audio_vector_proof(
        header={"epoch": "epoch_test", "runtime_run_id": "runtime-run-alpha"},
        latest_episode={},
        temporal_payload={"total_scenes": 1, "video_id": "video-a"},
        scene_results_payload={
            "scenes": [
                {"scene_id": "scene-a", "video_id": "video-a", "audio": {"clap_meta": {"status": "ok"}}},
            ]
        },
    )

    assert proof["status"] == "provenance_unverified_audio_vector_exists"
    assert proof["label"] == "Historical Only"
    assert proof["clap_ok"] == 1
    assert proof["current_run_qdrant_proven"] == 0
    assert proof["qdrant_run_matched_points"] == 1
    assert proof["missing_required_fields"]["embedding_id"] == 1
    assert proof["missing_required_fields"]["component"] == 1


def test_audio_vector_proof_prefers_run_header_collection_over_current_config(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    fake_config_loader = types.ModuleType("steps.common.config_loader")
    fake_config_loader.load_configs = lambda overrides=None: {
        "paths": {"data_root": "data", "db_path": "data/memory.db"},
        "host": {},
        "memory": {},
        "llm": {},
        "qdrant": {"enabled": True, "host": "http://127.0.0.1:6333", "collections": {"audio": "goodq_audio_fresh_epoch"}},
    }
    monkeypatch.setitem(sys.modules, "steps.common.config_loader", fake_config_loader)

    fake_memory_store = types.ModuleType("steps.common.memory_store")
    fake_memory_store.normalize_memory_tier_list = lambda values: values
    monkeypatch.setitem(sys.modules, "steps.common.memory_store", fake_memory_store)

    fake_ingest_requests = types.ModuleType("api.utils.ingest_requests")
    fake_ingest_requests.is_supported_ingest_path = lambda path: True
    monkeypatch.setitem(sys.modules, "api.utils.ingest_requests", fake_ingest_requests)

    fake_goodq_version = types.ModuleType("goodq_version")
    fake_goodq_version.GOODQ_VERSION = "test"
    monkeypatch.setitem(sys.modules, "goodq_version", fake_goodq_version)

    runtime = _load_runtime_route_module(repo_root)

    observed: dict[str, list[str]] = {}

    def fake_scroll(runtime_run_id, collection_candidates):
        observed["collection_candidates"] = list(collection_candidates)
        return {
            "status": "ok",
            "collection": collection_candidates[0],
            "payloads": [
                {
                    "run_id": runtime_run_id,
                    "scene_id": "scene-a",
                    "video_id": "video-a",
                    "embedding_id": "embed-a",
                    "component": "audio_embed_clap",
                    "step": "audio_embed_clap",
                    "model": "laion/clap-htsat-unfused",
                    "created_at": "2026-05-20T00:00:00Z",
                    "commit_ts_utc": "2026-05-20T00:00:00Z",
                }
            ],
        }

    monkeypatch.setattr(runtime, "_scroll_qdrant_audio_payloads", fake_scroll)

    proof = runtime._summarize_audio_vector_proof(
        header={
            "runtime_run_id": "runtime-power-loss",
            "qdrant_collections": {"audio": "goodq_audio_power_loss_epoch"},
        },
        latest_episode={},
        temporal_payload={},
        scene_results_payload={},
    )

    assert observed["collection_candidates"][:2] == [
        "goodq_audio_power_loss_epoch",
        "goodq_audio_fresh_epoch",
    ]
    assert proof["collection"] == "goodq_audio_power_loss_epoch"
    assert proof["status"] == "current_run_audio_vector_proven"
    assert proof["current_run_qdrant_proven"] == 1


def test_audio_provenance_snapshot_lists_run_tagged_qdrant_audio_without_latest_run_claim(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    fake_config_loader = types.ModuleType("steps.common.config_loader")
    fake_config_loader.load_configs = lambda overrides=None: {
        "paths": {"data_root": "data", "db_path": "data/memory.db"},
        "host": {},
        "memory": {},
        "llm": {},
        "qdrant": {"enabled": True, "host": "http://127.0.0.1:6333", "collections": {"audio": "goodq_audio_epoch_test"}},
    }
    monkeypatch.setitem(sys.modules, "steps.common.config_loader", fake_config_loader)

    fake_memory_store = types.ModuleType("steps.common.memory_store")
    fake_memory_store.normalize_memory_tier_list = lambda values: values
    monkeypatch.setitem(sys.modules, "steps.common.memory_store", fake_memory_store)

    fake_ingest_requests = types.ModuleType("api.utils.ingest_requests")
    fake_ingest_requests.is_supported_ingest_path = lambda path: True
    monkeypatch.setitem(sys.modules, "api.utils.ingest_requests", fake_ingest_requests)

    fake_goodq_version = types.ModuleType("goodq_version")
    fake_goodq_version.GOODQ_VERSION = "test"
    monkeypatch.setitem(sys.modules, "goodq_version", fake_goodq_version)

    runtime = _load_runtime_route_module(repo_root)

    def fake_get(url, timeout=None):
        assert url.endswith("/collections")
        return _FakeResponse(
            200,
            {
                "result": {
                    "collections": [
                        {"name": "goodq_text"},
                        {"name": "goodq_audio_legacy"},
                        {"name": "goodq_audio_epoch_test"},
                    ]
                }
            },
        )

    def fake_post(url, json=None, timeout=None):
        assert json["with_payload"] is True
        if "goodq_audio_legacy" in url:
            return _FakeResponse(
                200,
                {"result": {"points": [{"payload": {"faiss_id": 1, "modality": "audio", "source_path": r"L:\secret.wav"}}]}},
            )
        if "goodq_audio_epoch_test" in url:
            return _FakeResponse(
                200,
                {
                    "result": {
                        "points": [
                            {
                                "payload": {
                                    "run_id": "run-old",
                                    "scene_id": "scene-a",
                                    "video_id": "video-a",
                                    "embedding_id": "embed-old",
                                    "component": "audio_embed_clap",
                                    "step": "audio_embed_clap",
                                    "model": "laion/clap-htsat-unfused",
                                    "created_at": "2026-05-01T00:00:00Z",
                                    "commit_ts_utc": "2026-05-01T00:00:00Z",
                                    "modality": "audio",
                                }
                            },
                            {
                                "payload": {
                                    "run_id": "run-new",
                                    "scene_id": "scene-b",
                                    "video_id": "video-b",
                                    "embedding_id": "embed-new",
                                    "component": "audio_embed_clap",
                                    "step": "audio_embed_clap",
                                    "model": "laion/clap-htsat-unfused",
                                    "created_at": "2026-05-02T00:00:00Z",
                                    "commit_ts_utc": "2026-05-02T00:00:00Z",
                                    "modality": "audio",
                                    "source_path": r"L:\private\scene_0001.wav",
                                }
                            },
                            {
                                "payload": {
                                    "run_id": "run-new",
                                    "scene_id": "scene-c",
                                    "video_id": "video-b",
                                    "component": "audio_embed_clap",
                                    "step": "audio_embed_clap",
                                    "model": "laion/clap-htsat-unfused",
                                    "created_at": "2026-05-02T00:01:00Z",
                                    "commit_ts_utc": "2026-05-02T00:01:00Z",
                                    "modality": "audio",
                                }
                            },
                        ],
                        "next_page_offset": None,
                    }
                },
            )
        raise AssertionError(url)

    monkeypatch.setattr(runtime.requests, "get", fake_get)
    monkeypatch.setattr(runtime.requests, "post", fake_post)

    snapshot = runtime._latest_audio_provenance_snapshot(limit=2)

    assert snapshot["status"] == "ok"
    assert snapshot["mode"] == "read_only"
    assert snapshot["latest_run"]["run_id"] == "run-new"
    assert snapshot["latest_run"]["collection"] == "goodq_audio_epoch_test"
    assert snapshot["latest_run"]["run_tagged_points"] == 2
    assert snapshot["latest_run"]["provenance_capable_points"] == 1
    assert snapshot["latest_run"]["missing_required_fields"]["embedding_id"] == 1
    assert snapshot["legacy_audio_points_sampled"] == 1
    assert snapshot["runs"][0]["run_id"] == "run-new"
    assert snapshot["runs"][1]["run_id"] == "run-old"
    serialized = json.dumps(snapshot)
    assert "source_path" not in serialized
    assert "secret.wav" not in serialized
