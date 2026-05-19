from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path


def _load_route_module(module_name: str):
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    module_path = repo_root / "api" / "routes" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"tests.{module_name}_route_policy", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


system_module = _load_route_module("system")


class _FakeVideoLoader:
    def list_processed_videos(self):
        return ["video_001"]

    def get_video_metadata(self, video_id: str):
        assert video_id == "video_001"
        return {
            "title": "Example Memory",
            "duration": 12.5,
            "total_scenes": 1,
            "processed_date": 1_700_000_000,
        }

    def load_temporal_index(self, video_id: str):
        assert video_id == "video_001"
        return {
            "segments": [
                {
                    "representative_frame": (
                        r"L:\_DATA\GoodQ_Data\processing\video_001\video\frames"
                        r"\scene_0000_frame_01.jpg"
                    )
                }
            ]
        }


def _model_payload(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def test_videos_route_projects_thumbnail_without_exposing_local_paths(monkeypatch) -> None:
    monkeypatch.setattr(system_module, "get_data_loader", lambda: _FakeVideoLoader())

    response = asyncio.run(system_module.list_videos())

    assert len(response) == 1
    video = response[0]
    payload = _model_payload(video)
    serialized = json.dumps(payload)
    assert "L:" not in serialized
    assert "C:" not in serialized
    assert "_DATA" not in serialized
    assert getattr(video, "thumbnail_available", None) is True
    assert getattr(video, "thumbnail_endpoint", None) == (
        "/api/media/video/video_001/frame/scene_0000_frame_01.jpg"
    )
    assert getattr(video, "thumbnail_path_redacted", None) is True
    assert video.thumbnail == "/api/media/video/video_001/frame/scene_0000_frame_01.jpg"


def test_ingest_route_declares_guarded_future_facade() -> None:
    request = system_module.IngestRequest(file_path="C:/tmp/example.mp4")

    response = asyncio.run(system_module.start_ingest(request))

    assert response.status == "disabled"
    assert response.allowed is False
    assert response.route == "/api/system/ingest"
    assert response.mode == "future_controlled_facade"
    assert response.job_id == "disabled"
    assert response.policy.confirmation_gated is True
    assert response.policy.policy_driven is True
    assert response.policy.budgeted is True
    assert response.policy.checkpointed is True
    assert response.policy.auditable is True
    assert "cli.watchdog" in response.canonical_runtime_path
    assert any("cli.watchdog" in item for item in response.operator_surfaces)
    assert any("cli.run_ingestion" in item for item in response.operator_surfaces)
    assert any("import_inbox" in item for item in response.operator_surfaces)
    assert any("confirmation token" in item for item in response.required_capabilities)
    assert any("checkpointed" in item for item in response.required_capabilities)


def test_reindex_route_declares_operator_only_policy() -> None:
    response = asyncio.run(system_module.rebuild_indexes())

    assert response.status == "disabled"
    assert response.allowed is False
    assert response.route == "/api/system/reindex"
    assert response.mode == "operator_only"
    assert "operator-only" in response.message
    assert "No supported public API facade exists" in response.canonical_runtime_path
    assert response.policy.explicit is True
    assert response.policy.confirmation_gated is True
    assert response.policy.policy_driven is True
    assert any("maintenance workflow" in item for item in response.operator_surfaces)
    assert any("maintenance" in item for item in response.required_capabilities)


def test_reload_route_declares_operator_only_policy() -> None:
    response = asyncio.run(system_module.reload_config())

    assert response.status == "disabled"
    assert response.allowed is False
    assert response.route == "/api/system/reload"
    assert response.mode == "operator_only"
    assert "operator-only" in response.message
    assert "No supported public API facade exists" in response.canonical_runtime_path
    assert response.policy.explicit is True
    assert response.policy.auditable is True
    assert any("maintenance workflow" in item for item in response.operator_surfaces)
    assert any("maintenance" in item for item in response.required_capabilities)
