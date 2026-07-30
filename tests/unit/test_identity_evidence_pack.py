import sqlite3

from api.utils.identity_evidence_pack import (
    build_identity_evidence_pack,
    load_identity_scene_evidence,
)


def test_identity_role_is_visible_but_not_converted_to_pairwise_claim() -> None:
    pack = build_identity_evidence_pack(
        [
            {"id": "joe", "display_name": "Joe", "role": "subject"},
            {"id": "maria", "display_name": "Maria", "role": "Cousin"},
        ],
        ["Joe", "Maria"],
    )
    assert pack["claim_status"] == "not_established"
    assert pack["relationships"] == []
    assert {label["value"] for label in pack["identity_labels"]} == {"subject", "Cousin"}


def test_explicit_curated_relationship_is_the_only_established_claim() -> None:
    pack = build_identity_evidence_pack(
        [
            {"id": "joe", "display_name": "Joe", "role": "subject"},
            {
                "id": "maria",
                "display_name": "Maria",
                "role": "Cousin",
                "relationships": [{"target_id": "joe", "type": "cousin"}],
            },
        ],
        ["Joe", "Maria"],
    )
    assert pack["claim_status"] == "established"
    assert pack["relationships"] == [{
        "source_id": "maria",
        "target_id": "joe",
        "type": "cousin",
        "authority": "curated_roster_relationship",
    }]


def test_unrelated_cooccurrence_is_not_a_relationship_input() -> None:
    pack = build_identity_evidence_pack(
        [{"id": "maria", "display_name": "Maria", "role": "Cousin"}],
        ["Maria", "Unknown"],
    )
    assert pack["claim_status"] == "not_established"
    assert len(pack["identities"]) == 1


def test_scene_evidence_preserves_typed_person_scene_edges(tmp_path) -> None:
    kg_path = tmp_path / "knowledge_graph.db"
    with sqlite3.connect(kg_path) as conn:
        conn.executescript(
            """
            CREATE TABLE nodes (id INTEGER PRIMARY KEY, node_type TEXT, name TEXT);
            CREATE TABLE edges (source_id INTEGER, target_id INTEGER, edge_type TEXT);
            INSERT INTO nodes VALUES
                (1, 'Person', 'maria'),
                (2, 'scene', 'scene-a'),
                (3, 'scene', 'scene-b'),
                (4, 'video', 'video-hash-a');
            INSERT INTO edges VALUES
                (1, 2, 'person_appears_in_scene'),
                (1, 2, 'person_mentioned_in_scene'),
                (1, 3, 'person_mentioned_in_scene'),
                (4, 2, 'video_contains_scene'),
                (4, 3, 'video_contains_scene');
            """
        )

    payload = load_identity_scene_evidence(
        [{"id": "maria", "display_name": "Maria"}], kg_path, limit=1
    )

    assert payload == {
        "source": "promoted_knowledge_graph",
        "scene_refs": [{
            "scene_id": "scene-a",
            "video_hash": "video-hash-a",
            "people": [{
                "identity_id": "maria",
                "display_name": "Maria",
                "evidence_types": ["appearance", "mention"],
                "strength": "appearance",
            }],
        }],
    }
