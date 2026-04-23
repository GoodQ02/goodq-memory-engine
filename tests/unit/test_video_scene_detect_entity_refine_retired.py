from __future__ import annotations

from pathlib import Path

from scripts.config_schema import VideoSceneDetectConfig
from steps.video_scene_detect import step as scene_step


def test_scene_detect_config_no_longer_exposes_entity_refine_controls() -> None:
    retired_fields = {
        "entity_refine",
        "entity_sample_rate",
        "entity_min_duration",
        "entity_max_samples",
    }
    assert retired_fields.isdisjoint(VideoSceneDetectConfig.model_fields)


def test_video_scene_detect_ignores_legacy_entity_refine_override(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "video.mp4"
    source.write_bytes(b"v")

    monkeypatch.setattr(
        scene_step,
        "_detect_with_scenedetect",
        lambda *_args, **_kwargs: {
            "scenes": [
                {
                    "index": 0,
                    "start": 0.0,
                    "end": 10.0,
                    "duration": 10.0,
                    "confidence": 0.9,
                }
            ],
            "duration": 10.0,
        },
    )

    assert not hasattr(scene_step, "_refine_scenes_with_entities")

    result = scene_step.video_scene_detect(
        {
            "source_path": str(source),
            "scene_detect": {"entity_refine": True},
        },
        {},
    )

    assert result["scene_meta"]["status"] == "ok"
    assert "entity_refine" not in result["scene_meta"]
    assert len(result["scenes"]) == 1
