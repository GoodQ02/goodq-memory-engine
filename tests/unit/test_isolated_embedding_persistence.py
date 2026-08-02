from __future__ import annotations

import sqlite3
from pathlib import Path

from steps.common import memory


def _candidate_cfg(root: Path, *, allow: bool = True, promotion_enabled: bool = False) -> dict:
    return {
        "ingestion_isolation": True,
        "witness": {
            "ingestion_isolation": True,
            "promotion_enabled": promotion_enabled,
            "artifact_root": str(root),
            "allow_sqlite_embeddings": allow,
        },
        "paths": {"db_path": str(root / "data" / "epochs" / "candidate" / "memory.db")},
        "memory": {"routing": {"quantization_enabled": True}},
    }


def test_isolated_candidate_allows_embedding_sidecars_only_with_explicit_contained_opt_in(
    tmp_path: Path,
) -> None:
    root = tmp_path / "witness"
    cfg = _candidate_cfg(root)

    assert memory.embedding_persistence_allowed(cfg) is True

    memory.upsert_embedding(
        cfg,
        "candidate-embedding",
        1,
        "fixture.mp4",
        "clip",
        scene_id="scene_0000",
        vector=[0.25] * 384,
    )

    with sqlite3.connect(cfg["paths"]["db_path"]) as conn:
        row = conn.execute(
            "SELECT vector, tq_indices, tq_norm, tq_qjl_sign, tq_norm_residual "
            "FROM embeddings WHERE hash=? AND modality=?",
            ("candidate-embedding", "clip"),
        ).fetchone()

    assert row is not None
    assert all(value is not None for value in row)


def test_isolated_embedding_persistence_fails_closed_without_opt_in_or_containment(
    tmp_path: Path,
) -> None:
    root = tmp_path / "witness"

    assert memory.embedding_persistence_allowed(_candidate_cfg(root, allow=False)) is False
    assert memory.embedding_persistence_allowed(_candidate_cfg(root, promotion_enabled=True)) is False

    escaped = _candidate_cfg(root)
    escaped["paths"]["db_path"] = str(tmp_path / "canonical" / "memory.db")
    assert memory.embedding_persistence_allowed(escaped) is False
