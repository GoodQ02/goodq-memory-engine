from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest
import yaml

from scripts.identity.promote_identity_layer import _fail_if_plan_errors, promote


def _create_kg(path: Path, scenes: list[tuple[str, list[int]]]) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_type TEXT NOT NULL,
                name TEXT NOT NULL,
                properties TEXT,
                occurrence_count INTEGER DEFAULT 1,
                created_at TEXT,
                UNIQUE(node_type, name)
            );
            CREATE TABLE edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                edge_type TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                properties TEXT,
                created_at TEXT,
                UNIQUE(source_id, target_id, edge_type)
            );
            """
        )
        for name, frame_ids in scenes:
            conn.execute(
                "INSERT INTO nodes (node_type, name, properties) VALUES (?, ?, ?)",
                ("scene", name, json.dumps({"ucf_provenance": frame_ids})),
            )


def _create_memory(
    path: Path,
    segments: list[tuple[str, str, str, str]],
) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE segments (video_hash TEXT, speaker TEXT, meta TEXT)"
        )
        for video_hash, speaker, scene_id, text in segments:
            conn.execute(
                "INSERT INTO segments VALUES (?, ?, ?)",
                (
                    video_hash,
                    speaker,
                    json.dumps({"scene_id": scene_id, "text": text}),
                ),
            )


def _create_identity_data(
    path: Path,
    *,
    face_ids: list[str],
    display_name: str = "Grace",
    aliases: list[str] | None = None,
) -> None:
    path.mkdir()
    roster = {
        "identities": [
            {
                "id": "person-1",
                "display_name": display_name,
                "aliases": aliases or [],
                "face_cluster_ids": ["face_cluster_0"] if face_ids else [],
                "speaker_cluster_ids": [],
                "name_mention_keys": [],
                "role": "family",
                "notes": "",
            }
        ]
    }
    (path / "family_roster.yaml").write_text(
        yaml.safe_dump(roster, sort_keys=False),
        encoding="utf-8",
    )
    face_manifest = {
        "epoch_id": "epoch-test",
        "clusters": [
            {
                "cluster_id": "face_cluster_0",
                "face_ids": face_ids,
                "face_count": len(face_ids),
                "video_hashes": ["content-hash-that-is-not-a-kg-node-name"],
            }
        ],
    }
    (path / "face_clusters.json").write_text(
        json.dumps(face_manifest),
        encoding="utf-8",
    )
    (path / "speaker_clusters.json").write_text(
        json.dumps({"epoch_id": "epoch-test", "clusters": []}),
        encoding="utf-8",
    )
    (path / "name_mentions.json").write_text(
        json.dumps({"epoch_id": "epoch-test", "mentions": []}),
        encoding="utf-8",
    )


def _edge_plan(manifest: dict, edge_type: str) -> list[dict]:
    return [edge for edge in manifest["edges_created"] if edge["edge"] == edge_type]


def test_dry_run_maps_face_detection_only_to_its_provenance_scene(
    tmp_path: Path,
) -> None:
    """Catches regression to linking a face cluster to every scene in its video."""
    kg_path = tmp_path / "kg.db"
    memory_path = tmp_path / "memory.db"
    data_path = tmp_path / "identity"
    _create_kg(kg_path, [("scene-face", [101]), ("scene-other", [102])])
    _create_memory(memory_path, [])
    _create_identity_data(data_path, face_ids=["101_0"])

    manifest = promote("epoch-test", kg_path, data_path, memory_path, dry_run=True)

    assert _edge_plan(manifest, "person_appears_in_scene") == [
        {
            "edge": "person_appears_in_scene",
            "from": "person-1",
            "to": "scene-face",
            "target_node_id": 1,
            "confidence": "candidate",
            "via_face_clusters": ["face_cluster_0"],
            "evidence_face_ids": ["101_0"],
        }
    ]
    assert manifest["errors"] == []


def test_name_mentions_are_word_bounded_and_plan_exact_scenes(
    tmp_path: Path,
) -> None:
    """Catches Jose matching Joseph and summary-only mention plans."""
    kg_path = tmp_path / "kg.db"
    memory_path = tmp_path / "memory.db"
    data_path = tmp_path / "identity"
    _create_kg(kg_path, [("scene-joseph", []), ("scene-jose", [])])
    _create_memory(
        memory_path,
        [
            ("video-a", "speaker-a", "scene-joseph", "Joseph entered the room."),
            ("video-a", "speaker-b", "scene-jose", "Jose entered the room."),
        ],
    )
    _create_identity_data(
        data_path,
        face_ids=[],
        display_name="Jose",
        aliases=["Dad", "Father"],
    )

    manifest = promote("epoch-test", kg_path, data_path, memory_path, dry_run=True)

    mention_edges = _edge_plan(manifest, "person_mentioned_in_scene")
    assert len(mention_edges) == 1
    assert mention_edges[0]["to"] == "scene-jose"
    assert mention_edges[0]["target_node_id"] == 2
    assert mention_edges[0]["matched_terms"] == ["Jose"]
    assert mention_edges[0]["speakers"] == ["speaker-b"]
    assert manifest["errors"] == []


def test_name_mentions_resolve_scene_from_segment_ucf_provenance(
    tmp_path: Path,
) -> None:
    """Catches treating the July segment shape as missing scene authority."""
    kg_path = tmp_path / "kg.db"
    memory_path = tmp_path / "memory.db"
    data_path = tmp_path / "identity"
    _create_kg(kg_path, [("scene-grace", [201, 202])])
    _create_memory(memory_path, [])
    with sqlite3.connect(memory_path) as conn:
        conn.execute(
            "INSERT INTO segments VALUES (?, ?, ?)",
            (
                "video-a",
                "speaker-a",
                json.dumps(
                    {
                        "text": "Grace is here.",
                        "ucf_provenance": [201, 202],
                    }
                ),
            ),
        )
    _create_identity_data(data_path, face_ids=[])

    manifest = promote("epoch-test", kg_path, data_path, memory_path, dry_run=True)

    assert _edge_plan(manifest, "person_mentioned_in_scene") == [
        {
            "edge": "person_mentioned_in_scene",
            "from": "person-1",
            "to": "scene-grace",
            "target_node_id": 1,
            "matched_terms": ["Grace"],
            "speakers": ["speaker-a"],
        }
    ]
    assert manifest["errors"] == []


def test_dry_run_and_confirm_use_the_same_edge_projection(tmp_path: Path) -> None:
    """Catches write-only scene discovery hidden from the dry-run oracle."""
    dry_kg = tmp_path / "dry.db"
    confirm_kg = tmp_path / "confirm.db"
    memory_path = tmp_path / "memory.db"
    data_path = tmp_path / "identity"
    _create_kg(dry_kg, [("scene-face", [101]), ("scene-name", [])])
    shutil.copy2(dry_kg, confirm_kg)
    _create_memory(
        memory_path,
        [("video-a", "speaker-a", "scene-name", "Grace is here.")],
    )
    _create_identity_data(data_path, face_ids=["101_0"])

    dry_manifest = promote(
        "epoch-test", dry_kg, data_path, memory_path, dry_run=True
    )
    confirm_manifest = promote(
        "epoch-test", confirm_kg, data_path, memory_path, dry_run=False
    )

    assert confirm_manifest["nodes_created"] == dry_manifest["nodes_created"]
    assert confirm_manifest["edges_created"] == dry_manifest["edges_created"]
    with sqlite3.connect(confirm_kg) as conn:
        persisted = conn.execute(
            "SELECT e.edge_type, target.name "
            "FROM edges e JOIN nodes target ON target.id = e.target_id "
            "WHERE e.edge_type IN "
            "('person_appears_in_scene', 'person_mentioned_in_scene') "
            "ORDER BY e.edge_type"
        ).fetchall()
    assert persisted == [
        ("person_appears_in_scene", "scene-face"),
        ("person_mentioned_in_scene", "scene-name"),
    ]


@pytest.mark.parametrize(
    ("scenes", "expected_code"),
    [
        ([("unrelated", [999])], "face_detection_scene_missing"),
        (
            [("scene-a", [101]), ("scene-b", [101])],
            "face_detection_scene_ambiguous",
        ),
    ],
)
def test_confirm_blocks_before_writes_when_face_scene_authority_is_invalid(
    tmp_path: Path,
    scenes: list[tuple[str, list[int]]],
    expected_code: str,
) -> None:
    """Catches partial promotion when face evidence cannot resolve uniquely."""
    kg_path = tmp_path / "kg.db"
    memory_path = tmp_path / "memory.db"
    data_path = tmp_path / "identity"
    _create_kg(kg_path, scenes)
    _create_memory(memory_path, [])
    _create_identity_data(data_path, face_ids=["101_0"])

    dry_manifest = promote(
        "epoch-test", kg_path, data_path, memory_path, dry_run=True
    )
    assert [error["code"] for error in dry_manifest["errors"]] == [expected_code]

    with pytest.raises(RuntimeError, match="identity promotion plan has errors"):
        promote("epoch-test", kg_path, data_path, memory_path, dry_run=False)
    with sqlite3.connect(kg_path) as conn:
        person_count = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE node_type = 'Person'"
        ).fetchone()[0]
    assert person_count == 0


def test_confirm_blocks_before_writes_when_mention_scene_authority_is_ambiguous(
    tmp_path: Path,
) -> None:
    """Catches silently connecting one transcript segment to multiple scenes."""
    kg_path = tmp_path / "kg.db"
    memory_path = tmp_path / "memory.db"
    data_path = tmp_path / "identity"
    _create_kg(kg_path, [("scene-a", [201]), ("scene-b", [202])])
    _create_memory(memory_path, [])
    with sqlite3.connect(memory_path) as conn:
        conn.execute(
            "INSERT INTO segments VALUES (?, ?, ?)",
            (
                "video-a",
                "speaker-a",
                json.dumps(
                    {
                        "text": "Grace is here.",
                        "ucf_provenance": [201, 202],
                    }
                ),
            ),
        )
    _create_identity_data(data_path, face_ids=[])

    dry_manifest = promote(
        "epoch-test", kg_path, data_path, memory_path, dry_run=True
    )
    assert [error["code"] for error in dry_manifest["errors"]] == [
        "mention_scene_ambiguous"
    ]

    with pytest.raises(RuntimeError, match="identity promotion plan has errors"):
        promote("epoch-test", kg_path, data_path, memory_path, dry_run=False)
    with sqlite3.connect(kg_path) as conn:
        person_count = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE node_type = 'Person'"
        ).fetchone()[0]
    assert person_count == 0


def test_mention_scene_authorities_must_agree_when_both_are_present(
    tmp_path: Path,
) -> None:
    """Catches an explicit scene ID silently overriding contrary provenance."""
    kg_path = tmp_path / "kg.db"
    memory_path = tmp_path / "memory.db"
    data_path = tmp_path / "identity"
    _create_kg(kg_path, [("scene-explicit", [201]), ("scene-provenance", [202])])
    _create_memory(memory_path, [])
    with sqlite3.connect(memory_path) as conn:
        conn.execute(
            "INSERT INTO segments VALUES (?, ?, ?)",
            (
                "video-a",
                "speaker-a",
                json.dumps(
                    {
                        "scene_id": "scene-explicit",
                        "text": "Grace is here.",
                        "ucf_provenance": [202],
                    }
                ),
            ),
        )
    _create_identity_data(data_path, face_ids=[])

    manifest = promote(
        "epoch-test", kg_path, data_path, memory_path, dry_run=True
    )

    assert [error["code"] for error in manifest["errors"]] == [
        "mention_scene_ambiguous"
    ]
    assert manifest["errors"][0]["scene_ids"] == [
        "scene-explicit",
        "scene-provenance",
    ]


def test_cli_plan_gate_exits_nonzero_when_dry_run_contains_authority_errors() -> None:
    """Catches the CLI announcing a failed dry-run plan as ready to confirm."""
    with pytest.raises(SystemExit) as exc_info:
        _fail_if_plan_errors(
            {
                "errors": [
                    {
                        "code": "face_detection_scene_missing",
                        "face_id": "101_0",
                    }
                ]
            }
        )

    assert exc_info.value.code == 1


def test_promotion_releases_database_handles_before_return(tmp_path: Path) -> None:
    """Catches leaked SQLite readers that prevent backup cleanup on Windows."""
    kg_path = tmp_path / "kg.db"
    memory_path = tmp_path / "memory.db"
    data_path = tmp_path / "identity"
    _create_kg(kg_path, [("scene-face", [101])])
    _create_memory(memory_path, [])
    _create_identity_data(data_path, face_ids=["101_0"])

    promote("epoch-test", kg_path, data_path, memory_path, dry_run=True)

    moved_kg = tmp_path / "moved.db"
    kg_path.rename(moved_kg)
    moved_kg.rename(kg_path)
