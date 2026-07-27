from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import yaml

from api.routes import search as search_module
from lib import identity_resolver as resolver_module


class _IdentityRankingEngine:
    weight_text = 0.5
    weight_visual = 0.4
    weight_audio = 0.1

    def __init__(self) -> None:
        self.requested_top_k: list[int] = []

    def search_multimodal(self, query, top_k, modalities=None, **_kwargs):
        self.requested_top_k.append(top_k)
        return [
            {
                "score": 0.85,
                "modality": "text",
                "payload": {"scene_id": "scene-mention", "video_id": "video-a"},
            },
            {
                "score": 0.80,
                "modality": "visual",
                "payload": {"scene_id": "scene-face", "video_id": "video-a"},
            },
            {
                "score": 0.95,
                "modality": "visual",
                "payload": {"scene_id": "scene-generic", "video_id": "video-a"},
            },
        ]


class _IdentityOmittingEngine(_IdentityRankingEngine):
    def search_multimodal(self, query, top_k, modalities=None, **_kwargs):
        self.requested_top_k.append(top_k)
        return [
            {
                "score": 0.85,
                "modality": "text",
                "payload": {"scene_id": "scene-mention", "video_id": "video-a"},
            },
            {
                "score": 0.75,
                "modality": "visual",
                "payload": {"scene_id": "scene-generic", "video_id": "video-a"},
            },
        ]


class _NoopLoader:
    def get_video_metadata(self, _video_id):
        return {}

    def list_processed_videos(self):
        return []


def _seed_identity_config(tmp_path: Path, *, enabled: bool) -> dict:
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
                (2, 1, 3, 'person_mentioned_in_scene');
            """
        )
    return {
        "identity_search": {
            "enabled": enabled,
            "roster_path": str(roster_path),
            "kg_db_path": str(kg_path),
            "appearance_score_boost": 0.20,
            "mention_score_boost": 0.05,
            "candidate_pool_multiplier": 5,
        },
        "paths": {"knowledge_graph_db": str(kg_path)},
    }


def test_identity_query_ranks_appearance_above_mention_and_labels_both(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Catches mention-only scenes being treated as equal visual identity hits."""
    engine = _IdentityRankingEngine()
    config = _seed_identity_config(tmp_path, enabled=True)
    resolver_module._resolver = None
    monkeypatch.setattr(search_module, "_config", config)
    monkeypatch.setattr(search_module, "get_search_engine", lambda: engine)
    monkeypatch.setattr(search_module, "get_data_loader", lambda: _NoopLoader())

    response = asyncio.run(
        search_module.search_multimodal(
            search_module.MultimodalSearchRequest(query="Grace", top_k=3)
        )
    )

    assert engine.requested_top_k == [15]
    assert [result.scene_id for result in response.results] == [
        "scene-face",
        "scene-generic",
        "scene-mention",
    ]
    appearance, generic, mention = response.results
    assert appearance.vector_score == 0.80
    assert appearance.score == 1.00
    assert appearance.identity_boost == 0.20
    assert appearance.identity_match == "appearance"
    assert appearance.identity_evidence[0]["evidence_types"] == ["appearance"]
    assert generic.vector_score == 0.95
    assert generic.identity_boost == 0.0
    assert generic.identity_match is None
    assert mention.vector_score == 0.85
    assert mention.score == 0.90
    assert mention.identity_boost == 0.05
    assert mention.identity_match == "mention"
    assert mention.identity_evidence[0]["evidence_types"] == ["mention"]


def test_non_identity_query_keeps_candidate_window_and_scores_unchanged(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Catches identity augmentation perturbing ordinary retrieval."""
    engine = _IdentityRankingEngine()
    config = _seed_identity_config(tmp_path, enabled=True)
    resolver_module._resolver = None
    monkeypatch.setattr(search_module, "_config", config)
    monkeypatch.setattr(search_module, "get_search_engine", lambda: engine)
    monkeypatch.setattr(search_module, "get_data_loader", lambda: _NoopLoader())

    response = asyncio.run(
        search_module.search_multimodal(
            search_module.MultimodalSearchRequest(query="mountain bike", top_k=2)
        )
    )

    assert engine.requested_top_k == [2]
    assert [result.score for result in response.results] == [0.85, 0.80, 0.95]
    assert all(result.vector_score is None for result in response.results)
    assert all(result.identity_boost == 0.0 for result in response.results)


def test_identity_query_reserves_one_exact_appearance_when_vectors_omit_it(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Catches sparse face evidence disappearing outside the vector candidate set."""
    engine = _IdentityOmittingEngine()
    config = _seed_identity_config(tmp_path, enabled=True)
    config["identity_search"]["appearance_injection_limit"] = 1
    resolver_module._resolver = None
    monkeypatch.setattr(search_module, "_config", config)
    monkeypatch.setattr(search_module, "get_search_engine", lambda: engine)
    monkeypatch.setattr(search_module, "get_data_loader", lambda: _NoopLoader())

    response = asyncio.run(
        search_module.search_multimodal(
            search_module.MultimodalSearchRequest(query="Grace", top_k=2)
        )
    )

    assert len(response.results) == 2
    injected = next(
        result for result in response.results
        if result.scene_id == "scene-face"
    )
    assert injected.modality == "identity"
    assert injected.identity_only is True
    assert injected.vector_score is None
    assert injected.score == 0.20
    assert injected.identity_boost == 0.20
    assert injected.identity_match == "appearance"
    assert injected.identity_evidence[0]["strength"] == "appearance"
    assert all(
        result.scene_id != "scene-mention"
        or result.identity_match == "mention"
        for result in response.results
    )
