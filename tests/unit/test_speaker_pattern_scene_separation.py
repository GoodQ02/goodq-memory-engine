import sqlite3

import pytest

from lib.kg_realtime_integration import update_kg_for_scene


def _scene(labels):
    return {
        "speaker_ids": labels,
        "speaker_voice_signatures": [
            {"speaker": label, "embedding": [1.0, 0.0], "voiced_seconds": 4.0,
             "segment_count": 2}
            for label in labels
        ],
    }


@pytest.mark.parametrize("reload_between", [False, True])
def test_distinct_scene_speakers_stay_separate_through_caller(tmp_path, reload_between):
    db = tmp_path / "kg.db"
    cfg = {"paths": {"knowledge_graph_db": str(db)}}
    groups = [["SPEAKER_01"], ["SPEAKER_02"]] if reload_between else [["SPEAKER_01", "SPEAKER_02"]]
    for labels in groups:
        update_kg_for_scene(_scene(labels), "scene_a", "video", "sample.mp4", cfg)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(DISTINCT target_id) FROM edges WHERE edge_type='voice_pattern_match'").fetchone()[0] == 2
    # Reload/replay of the same label must keep its own pattern, not create a third.
    update_kg_for_scene(_scene(["SPEAKER_02"]), "scene_a", "video", "sample.mp4", cfg)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM nodes WHERE node_type='speaker_pattern'").fetchone()[0] == 2


def test_scene_separation_does_not_disable_cross_scene_pattern_matching(tmp_path):
    db = tmp_path / "kg.db"
    cfg = {"paths": {"knowledge_graph_db": str(db)}}
    for scene, speaker in [("scene_a", "SPEAKER_01"), ("scene_b", "SPEAKER_02")]:
        update_kg_for_scene(_scene([speaker]), scene, "video", "sample.mp4", cfg)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(DISTINCT source_id), count(DISTINCT target_id) FROM edges WHERE edge_type='voice_pattern_match'").fetchone() == (2, 1)
