from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml

from lib.identity_resolver import IdentityResolver


def _seed_identity_authority(tmp_path: Path) -> tuple[Path, Path]:
    identity_root = tmp_path / "identity"
    identity_root.mkdir()
    roster_path = identity_root / "family_roster.yaml"
    roster_path.write_text(
        yaml.safe_dump(
            {
                "identities": [
                    {
                        "id": "person-grace",
                        "display_name": "Grace",
                        "aliases": ["Gracie"],
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    kg_path = tmp_path / "knowledge_graph.db"
    with sqlite3.connect(kg_path) as conn:
        conn.executescript(
            """
            CREATE TABLE nodes (
                id INTEGER PRIMARY KEY,
                node_type TEXT NOT NULL,
                name TEXT NOT NULL,
                properties TEXT
            );
            CREATE TABLE edges (
                id INTEGER PRIMARY KEY,
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                edge_type TEXT NOT NULL
            );
            INSERT INTO nodes VALUES
                (1, 'Person', 'person-grace', '{}'),
                (2, 'scene', 'scene-face', '{}'),
                (3, 'scene', 'scene-mention', '{}');
            INSERT INTO edges VALUES
                (1, 1, 2, 'person_appears_in_scene'),
                (2, 1, 2, 'person_mentioned_in_scene'),
                (3, 1, 3, 'person_mentioned_in_scene');
            """
        )
    return roster_path, kg_path


def test_identity_evidence_preserves_appearance_and_mention_strength(
    tmp_path: Path,
) -> None:
    """Catches collapsing all identity scene links into an untyped set."""
    roster_path, kg_path = _seed_identity_authority(tmp_path)
    resolver = IdentityResolver(
        roster_path=str(roster_path),
        kg_db_path=str(kg_path),
        enabled=True,
    )

    evidence = resolver.get_identity_scene_evidence("show Grace and Gracie")

    assert evidence == {
        "scene-face": [
            {
                "person_id": "person-grace",
                "display_name": "Grace",
                "matched_term": "grace",
                "evidence_types": ["appearance", "mention"],
                "strength": "appearance",
            }
        ],
        "scene-mention": [
            {
                "person_id": "person-grace",
                "display_name": "Grace",
                "matched_term": "grace",
                "evidence_types": ["mention"],
                "strength": "mention",
            }
        ],
    }
    assert resolver.get_scenes_for_person("person-grace") == {
        "scene-face",
        "scene-mention",
    }


def test_roster_path_accepts_the_canonical_roster_file_contract(
    tmp_path: Path,
) -> None:
    """Catches appending family_roster.yaml twice to a configured file path."""
    roster_path, kg_path = _seed_identity_authority(tmp_path)
    resolver = IdentityResolver(
        roster_path=str(roster_path),
        kg_db_path=str(kg_path),
        enabled=True,
    )

    assert resolver.is_enabled() is True
    assert [
        match.person_id
        for match in resolver.resolve_query_entities("Gracie")
    ] == ["person-grace"]
