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
    assert len(recurring_people["Bill"]["supporting_evidence"]) == 2

    supported_pairs = [
        row for row in ledger["pairs"]
        if row["target_name"] == "Bill" and row["edge_type"] == "identity_supported"
    ]
    assert supported_pairs
    assert len(supported_pairs[0]["supporting_evidence"]) == 2
    assert supported_pairs[0]["supporting_evidence"][0]["transcript_excerpt"] == "Bill is here."


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


def test_identity_ledger_surfaces_speaker_pattern_evidence_across_episodes(tmp_path: Path) -> None:
    processing_root = tmp_path / "processing"
    scene_specs = [
        ("01x01 - Pilot", "scene_0001"),
        ("01x01 - Pilot", "scene_0002"),
        ("01x01 - Pilot", "scene_0003"),
        ("01x02 - Followup", "scene_0001"),
        ("01x02 - Followup", "scene_0002"),
    ]

    grouped: dict[str, list[dict]] = {}
    for episode_name, scene_suffix in scene_specs:
        grouped.setdefault(episode_name, []).append(
            {
                "scene_id": f"{episode_name}_{scene_suffix}",
                "index": len(grouped.get(episode_name, [])) + 1,
                "start": 0.0,
                "end": 4.5,
                "entities": [{"name": "Bill", "type": "PERSON"}],
                "audio": {
                    "speaker_transcript": [
                        {"speaker": "SPEAKER_00", "start": 0.0, "end": 2.2, "text": "Bill is here."},
                        {"speaker": "SPEAKER_00", "start": 2.3, "end": 4.5, "text": "Bill is here."},
                    ],
                    "speaker_voice_signatures": [
                        {
                            "speaker": "SPEAKER_00",
                            "embedding": [1.0, 0.0],
                            "embedding_dim": 2,
                            "voiced_seconds": 4.4,
                            "segment_count": 2,
                            "available_segment_count": 2,
                            "selected_segments": [
                                {"start": 0.0, "end": 2.2, "duration": 2.2},
                                {"start": 2.3, "end": 4.5, "duration": 2.2},
                            ],
                        }
                    ],
                },
            }
        )

    for episode_name, scenes in grouped.items():
        _write_json(
            processing_root / episode_name / "video" / "scene_manifest.json",
            {
                "video_id": episode_name,
                "video_path": f"{episode_name}.mp4",
                "scenes": scenes,
            },
        )

    graph_db_path = tmp_path / "identity_pattern_control.db"
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

    assert ledger["identity_edge_totals"]["identity_evidence"] >= 1

    evidence_pairs = [
        row for row in ledger["pairs"]
        if row["edge_type"] == "identity_evidence"
        and row["target_name"] == "Bill"
        and row["source_type"] == "speaker_pattern"
    ]
    assert len(evidence_pairs) == 1
    assert evidence_pairs[0]["supporting_scene_count"] == 5
    assert len(evidence_pairs[0]["supporting_evidence"]) == 5
    assert evidence_pairs[0]["supporting_evidence"][0]["source_node_type"] == "speaker_pattern"

    recurring_people = {row["person"]: row for row in ledger["recurring_people"]}
    assert recurring_people["Bill"]["episode_count"] == 2
    assert recurring_people["Bill"]["supporting_scene_count"] >= 5
