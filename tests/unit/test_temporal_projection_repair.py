from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_repair_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "repair_temporal_projection_gaps.py"
    spec = importlib.util.spec_from_file_location("repair_temporal_projection_gaps", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repair_projection_gaps_projects_source_truth_without_overwriting() -> None:
    module = _load_repair_module()
    temporal = {
        "segments": [
            {"scene_id": "scene-a", "sentiment_label": "existing", "sentiment_score": 0.5},
            {"scene_id": "scene-b", "visual_caption": "already projected"},
        ]
    }
    scene_results = {
        "scenes": [
            {
                "scene_id": "scene-a",
                "keyframe": {"caption": "source caption"},
                "audio": {
                    "sentiment": {"label": "negative", "score": 0.0},
                    "clap_meta": {"status": "ok", "faiss_id": 100},
                },
            },
            {
                "scene_id": "scene-b",
                "keyframe": {"caption": "should not overwrite"},
                "audio": {"clap_meta": {"status": "ok", "faiss_id": 101}},
            },
        ]
    }

    repaired, summary = module.repair_projection_gaps(temporal, scene_results)

    assert summary["status"] == "updated"
    assert summary["fields"] == {
        "visual_caption": 1,
        "sentiment": 0,
        "clap_meta": 2,
    }
    assert repaired["segments"][0]["visual_caption"] == "source caption"
    assert repaired["segments"][0]["sentiment_label"] == "existing"
    assert repaired["segments"][0]["sentiment_score"] == 0.5
    assert repaired["segments"][0]["clap_meta"] == {"status": "ok", "faiss_id": 100}
    assert repaired["segments"][1]["visual_caption"] == "already projected"
    assert repaired["segments"][1]["clap_meta"] == {"status": "ok", "faiss_id": 101}


def test_apply_projection_repair_dry_run_preserves_file_and_redacts_paths(tmp_path: Path) -> None:
    module = _load_repair_module()
    temporal_path = tmp_path / "temporal_index.json"
    scene_results_path = tmp_path / "scene_ingest_results.json"
    temporal_path.write_text(json.dumps({"segments": [{"scene_id": "scene-a"}]}), encoding="utf-8")
    scene_results_path.write_text(
        json.dumps([{"scenes": [{"scene_id": "scene-a", "keyframe": {"caption": "source caption"}}]}]),
        encoding="utf-8",
    )
    before = temporal_path.read_text(encoding="utf-8")

    result = module.apply_projection_repair(
        temporal_index_path=temporal_path,
        scene_results_path=scene_results_path,
        write=False,
    )

    assert result["mode"] == "dry_run"
    assert result["status"] == "updated"
    assert result["write_performed"] is False
    assert result["backup_path"] is None
    assert temporal_path.read_text(encoding="utf-8") == before
    assert str(tmp_path) not in json.dumps(result)
