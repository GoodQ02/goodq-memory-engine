import json
from pathlib import Path

from lib.identity_ledger import (
    _flatten_scene_payload,
    build_identity_ledger,
    rebuild_identity_graph_from_manifests,
)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_identity_ledger_rebuilds_control_graph_and_summarizes_support(tmp_path: Path) -> None:
    processing_root = tmp_path / "processing"

    for episode_name in ("01x01 - Pilot", "01x02 - Followup"):
        _write_json(
            processing_root / episode_name / "video" / "scene_manifest.json",
            {
                "video_id": episode_name,
                "video_path": f"{episode_name}.mp4",
                "scenes": [
                    {
                        "scene_id": f"{episode_name}_scene_0001",
                        "index": 1,
                        "start": 0.0,
                        "end": 4.0,
                        "audio": {
                            "speaker_transcript": [
                                {"speaker": "SPEAKER_00", "start": 0.0, "end": 4.0, "text": "Bill is here."},
                            ],
                        },
                        "entities": [{"name": "Bill", "type": "PERSON"}],
                    }
                ],
            },
        )

    graph_db_path = tmp_path / "identity_control.db"
    rebuild = rebuild_identity_graph_from_manifests(
        processing_root=processing_root,
        graph_db_path=graph_db_path,
        episode_prefix="01x",
    )
    ledger = build_identity_ledger(
        graph_db_path=graph_db_path,
        scene_episode_map=rebuild["scene_episode_map"],
        episodes=rebuild["episodes"],
    )

    assert rebuild["episode_count"] == 2
    assert rebuild["scene_count"] == 2
    assert ledger["identity_edge_totals"]["identity_candidate"] == 2
    assert ledger["identity_edge_totals"]["identity_supported"] == 2

    recurring_people = {row["person"]: row for row in ledger["recurring_people"]}
    assert "Bill" in recurring_people
    assert recurring_people["Bill"]["episode_count"] == 2
    assert recurring_people["Bill"]["supporting_scene_count"] == 2


def test_identity_ledger_flatten_prefers_nested_audio_entities_when_top_level_is_empty() -> None:
    payload = _flatten_scene_payload(
        {
            "entities": [],
            "keyframe": {"entities": []},
            "audio": {
                "entities": ["Bill"],
                "ner_entities": [{"name": "Bill", "type": "PER"}],
                "speaker_transcript": [{"speaker": "SPEAKER_00", "text": "Bill is here."}],
            },
        }
    )

    assert payload["entities"][0] == "Bill"
    assert {"name": "Bill", "type": "PER"} in payload["entities"]
    assert payload["ner_entities"] == [{"name": "Bill", "type": "PER"}]
    assert len(payload["speaker_transcript"]) == 1
