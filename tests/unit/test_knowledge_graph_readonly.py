from __future__ import annotations

import os
from pathlib import Path
import pytest
from fastapi import HTTPException
from lib.knowledge_graph import KnowledgeGraph
from api.routes import system as system_module

def test_kg_readonly_missing_db_raises_error(tmp_path: Path) -> None:
    db_path = tmp_path / "missing_dir" / "knowledge_graph.db"
    with pytest.raises(FileNotFoundError):
        KnowledgeGraph(str(db_path), read_only=True)
    assert not db_path.exists()
    assert not db_path.parent.exists()

def test_kg_readonly_existing_db(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    with KnowledgeGraph(str(db_path), read_only=False) as kg:
        kg.add_node("person", "Alice")

    with KnowledgeGraph(str(db_path), read_only=True) as kg:
        cur = kg.conn.cursor()
        row = cur.execute("SELECT name FROM nodes WHERE node_type = 'person'").fetchone()
        assert row is not None
        assert row["name"] == "Alice"

def test_kg_readonly_no_sidecars(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    with KnowledgeGraph(str(db_path), read_only=False) as kg:
        kg.add_node("person", "Alice")

    for ext in (".db-wal", ".db-shm", "-wal", "-shm"):
        sidecar = db_path.with_name(db_path.name + ext)
        if sidecar.exists():
            try:
                os.remove(sidecar)
            except OSError:
                pass
        sidecar2 = Path(str(db_path) + ext)
        if sidecar2.exists():
            try:
                os.remove(sidecar2)
            except OSError:
                pass

    with KnowledgeGraph(str(db_path), read_only=True) as kg:
        cur = kg.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM nodes").fetchone()

    for ext in (".db-wal", ".db-shm", "-wal", "-shm"):
        sidecar = db_path.with_name(db_path.name + ext)
        assert not sidecar.exists(), f"Sidecar {sidecar} should not be created in read-only mode"
        sidecar2 = Path(str(db_path) + ext)
        assert not sidecar2.exists(), f"Sidecar {sidecar2} should not be created in read-only mode"

def test_kg_readwrite_default(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge_graph_rw.db"
    assert not db_path.exists()
    with KnowledgeGraph(str(db_path)) as kg:
        kg.add_node("person", "Bob")
    assert db_path.exists()

def test_system_routes_readonly_missing_db(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "missing_dir" / "knowledge_graph.db"
    monkeypatch.setattr(system_module, "_get_kg_db_path", lambda: db_path)

    import asyncio
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(system_module.get_unstitched_patterns())
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "knowledge_graph_not_found"

    req = system_module.StitchPreviewRequest(
        source_node_name="voice_pattern_test_speaker_1",
        target_person_name="Bob"
    )
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(system_module.preview_stitch(req))
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "knowledge_graph_not_found"

    assert not db_path.exists()
