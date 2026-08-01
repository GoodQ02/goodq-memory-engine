from __future__ import annotations

import importlib
import json
import sqlite3
import sys
import types
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pytest

from lib import summary_aggregator
from retrieval.multimodal_search import MultimodalSearchEngine
from steps.common import memory_provenance, memory_stores, quantization, retrieval_events
from steps.common.qdrant_client import QdrantClient, QdrantConfig


_MARKER_TABLE = "forbidden_read_capability_marker"
multimodal_search = importlib.import_module("retrieval.multimodal_search")


def _authority_module():
    return importlib.import_module("steps.common.sqlite_read_authority")


def _seed_memory_database(
    path: Path,
    *,
    include_confidence: bool = True,
    embedding_id: str = "7",
) -> None:
    confidence_column = ", confidence_json TEXT" if include_confidence else ""
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            f"""
            CREATE TABLE scenes (
                id TEXT PRIMARY KEY,
                video_hash TEXT,
                start REAL,
                end REAL,
                meta TEXT
            );
            CREATE TABLE scene_text_fts (
                scene_id TEXT,
                video_hash TEXT,
                content_type TEXT,
                text TEXT
            );
            CREATE TABLE memory_commit_events (
                ts_utc TEXT,
                scene_id TEXT,
                video_id TEXT,
                modality TEXT,
                model TEXT,
                embedding_id TEXT,
                component TEXT,
                attempted INTEGER,
                committed INTEGER,
                reason TEXT,
                targets_json TEXT
                {confidence_column}
            );
            CREATE TABLE embeddings (
                hash TEXT,
                faiss_id INTEGER,
                modality TEXT,
                scene_id TEXT,
                tq_indices BLOB,
                tq_norm REAL,
                tq_qjl_sign BLOB,
                tq_norm_residual REAL
            );
            """
        )
        connection.execute(
            "INSERT INTO scenes (id, video_hash, start, end, meta) VALUES (?, ?, ?, ?, ?)",
            ("scene_0007", "video-alpha", 1.0, 2.0, "{}"),
        )
        connection.execute(
            "INSERT INTO scene_text_fts (scene_id, video_hash, content_type, text) "
            "VALUES (?, ?, ?, ?)",
            ("scene_0007", "video-alpha", "transcript", "Uncle Tony fixture"),
        )
        columns = (
            "ts_utc, scene_id, video_id, modality, model, embedding_id, component, "
            "attempted, committed, reason, targets_json"
        )
        values: tuple[Any, ...] = (
            "2026-07-13T00:00:00+00:00",
            "scene_0007",
            "video-alpha",
            "clip",
            "fixture-model",
            embedding_id,
            "fixture",
            1,
            1,
            "fixture",
            json.dumps({"qdrant": True}),
        )
        if include_confidence:
            columns += ", confidence_json"
            values += (json.dumps({"intrinsic": 0.9, "source": 0.8}),)
        placeholders = ",".join("?" for _ in values)
        connection.execute(
            f"INSERT INTO memory_commit_events ({columns}) VALUES ({placeholders})",
            values,
        )
        connection.execute(
            "INSERT INTO embeddings VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL)",
            (embedding_id, 7, "clip", "scene_0007"),
        )
        connection.commit()
    finally:
        connection.close()


def _seed_knowledge_graph(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE nodes (
                id INTEGER PRIMARY KEY,
                name TEXT,
                node_type TEXT
            );
            CREATE TABLE edges (
                source_id INTEGER,
                target_id INTEGER,
                edge_type TEXT,
                properties TEXT
            );
            INSERT INTO nodes VALUES (1, 'Joe', 'person');
            INSERT INTO nodes VALUES (2, 'scene_0007', 'scene');
            INSERT INTO edges VALUES (
                1,
                2,
                'appears_in',
                '{"scene_id":"scene_0007"}'
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def test_turboquant_active_retrieval_requires_sealed_candidate_authority(
    tmp_path: Path,
) -> None:
    """Active candidate retrieval is unavailable outside one sealed witness root."""
    root = tmp_path / "witness"
    database = root / "data" / "memory.db"
    database.parent.mkdir(parents=True)
    database.touch()
    allowed = {
        "ingestion_isolation": True,
        "witness": {
            "promotion_enabled": False,
            "artifact_root": str(root),
            "allow_turboquant_active_retrieval": True,
        },
    }

    assert memory_stores._turboquant_active_allowed(allowed, str(database)) is True

    for key_path, value in (
        (("ingestion_isolation",), False),
        (("witness", "promotion_enabled"), True),
        (("witness", "allow_turboquant_active_retrieval"), False),
    ):
        cfg = json.loads(json.dumps(allowed))
        target: dict[str, Any] = cfg
        for key in key_path[:-1]:
            target = target[key]
        target[key_path[-1]] = value
        assert memory_stores._turboquant_active_allowed(cfg, str(database)) is False

    assert memory_stores._turboquant_active_allowed(
        allowed, str(tmp_path / "canonical" / "memory.db")
    ) is False


def test_turboquant_candidate_query_exactly_reranks_complete_sidecars(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A sealed candidate may use sidecars only to select an exact-rerank pool."""
    root = tmp_path / "witness"
    database = root / "data" / "memory.db"
    index_path = root / "faiss" / "clip.index"
    database.parent.mkdir(parents=True)
    index_path.parent.mkdir(parents=True)
    _seed_memory_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("ALTER TABLE embeddings ADD COLUMN vector BLOB")
        connection.execute(
            "UPDATE embeddings SET vector = ?, tq_indices = ?, tq_norm = ?, tq_qjl_sign = ?, tq_norm_residual = ? WHERE faiss_id = 7",
            (
                np.asarray([0.0, 0.0], dtype=np.float32).tobytes(),
                np.asarray([0, 0], dtype=np.uint8).tobytes(),
                1.0,
                np.asarray([1, 1], dtype=np.int8).tobytes(),
                0.0,
            ),
        )
        connection.execute(
            "INSERT INTO embeddings (hash, faiss_id, modality, scene_id, vector, tq_indices, tq_norm, tq_qjl_sign, tq_norm_residual) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "8",
                8,
                "clip",
                "scene_0008",
                np.asarray([1.0, 0.0], dtype=np.float32).tobytes(),
                np.asarray([1, 1], dtype=np.uint8).tobytes(),
                1.0,
                np.asarray([1, 1], dtype=np.int8).tobytes(),
                0.0,
            ),
        )
        connection.commit()
    index_path.write_bytes(b"fixture")
    _install_fake_faiss(monkeypatch, ids=(8,), scores=(0.81,))
    monkeypatch.setattr(
        quantization.TurboQuantEncoder,
        "estimate_inner_product",
        lambda _self, _q, indices, *_args: float(indices[0]),
    )
    fake_provenance = types.ModuleType("steps.common.memory_provenance")
    fake_provenance.attach_provenance_to_hits = lambda _db, _hits: None
    monkeypatch.setitem(sys.modules, "steps.common.memory_provenance", fake_provenance)

    store = memory_stores.FaissMemory(
        index_path=str(index_path),
        dim=2,
        db_path=str(database),
        cfg={
            "ingestion_isolation": True,
            "witness": {
                "promotion_enabled": False,
                "artifact_root": str(root),
                "allow_turboquant_active_retrieval": True,
            },
        },
        retrieval_event_policy=retrieval_events.RetrievalEventPolicy(enabled=False),
    )

    hits = store.query([0.1, 0.0], top_k=1, retrieval_context="system.healthcheck")

    assert [hit["id"] for hit in hits] == [7]
    assert [hit["score"] for hit in hits] == pytest.approx([0.01])
    assert hits[0]["_retrieval_route"] == "turboquant_candidate_exact_rerank"


def test_turboquant_candidate_query_falls_back_when_a_sidecar_is_incomplete(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An incomplete sidecar must preserve the normal FAISS result."""
    root = tmp_path / "witness"
    database = root / "data" / "memory.db"
    index_path = root / "faiss" / "clip.index"
    database.parent.mkdir(parents=True)
    index_path.parent.mkdir(parents=True)
    _seed_memory_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("ALTER TABLE embeddings ADD COLUMN vector BLOB")
        connection.execute(
            "UPDATE embeddings SET vector = ? WHERE faiss_id = 7",
            (np.asarray([0.0, 0.0], dtype=np.float32).tobytes(),),
        )
        connection.commit()
    index_path.write_bytes(b"fixture")
    _install_fake_faiss(monkeypatch, ids=(7,), scores=(0.1,))
    fake_provenance = types.ModuleType("steps.common.memory_provenance")
    fake_provenance.attach_provenance_to_hits = lambda _db, _hits: None
    monkeypatch.setitem(sys.modules, "steps.common.memory_provenance", fake_provenance)

    store = memory_stores.FaissMemory(
        index_path=str(index_path),
        dim=2,
        db_path=str(database),
        cfg={
            "ingestion_isolation": True,
            "witness": {
                "promotion_enabled": False,
                "artifact_root": str(root),
                "allow_turboquant_active_retrieval": True,
            },
        },
        retrieval_event_policy=retrieval_events.RetrievalEventPolicy(enabled=False),
    )

    hits = store.query([0.1, 0.0], top_k=1, retrieval_context="system.healthcheck")

    assert [hit["id"] for hit in hits] == [7]
    assert hits[0]["score"] == pytest.approx(0.1)
    assert "_retrieval_route" not in hits[0]


def _write_capability_connect(
    real_connect: Callable[..., sqlite3.Connection],
) -> Callable[..., sqlite3.Connection]:
    def connect(path: str | Path, *args: Any, **kwargs: Any) -> sqlite3.Connection:
        connection = real_connect(path, *args, **kwargs)
        connection.execute(f"CREATE TABLE IF NOT EXISTS {_MARKER_TABLE} (value TEXT)")
        connection.commit()
        return connection

    return connect


def _marker_exists(path: Path) -> bool:
    connection = sqlite3.connect(path)
    try:
        return (
            connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
                (_MARKER_TABLE,),
            ).fetchone()[0]
            == 1
        )
    finally:
        connection.close()


class _FakeFaissIndex:
    def __init__(
        self,
        ids: tuple[int, ...] = (7,),
        scores: tuple[float, ...] = (0.9,),
    ) -> None:
        self.ids = ids
        self.scores = scores

    def search(self, _query: np.ndarray, k: int):
        return (
            np.array([self.scores[:k]], dtype=np.float32),
            np.array([self.ids[:k]], dtype=np.int64),
        )


def _install_fake_faiss(
    monkeypatch: pytest.MonkeyPatch,
    *,
    ids: tuple[int, ...] = (7,),
    scores: tuple[float, ...] = (0.9,),
) -> None:
    fake_faiss = types.ModuleType("faiss")
    fake_faiss.read_index = lambda _path: _FakeFaissIndex(ids, scores)
    monkeypatch.setitem(sys.modules, "faiss", fake_faiss)


class _QdrantResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self) -> dict[str, Any]:
        return self._payload


class _QdrantSession:
    def __init__(self, responses: list[_QdrantResponse]) -> None:
        self.responses = list(responses)

    def get(self, _url: str, **_kwargs: Any) -> _QdrantResponse:
        return self.responses.pop(0)

    def post(self, _url: str, **_kwargs: Any) -> _QdrantResponse:
        return self.responses.pop(0)


def test_fts_reader_does_not_retain_direct_write_capable_connect(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "memory.db"
    _seed_memory_database(database)
    real_connect = sqlite3.connect
    monkeypatch.setattr(
        multimodal_search,
        "sqlite3",
        types.SimpleNamespace(
            connect=_write_capability_connect(real_connect),
            OperationalError=sqlite3.OperationalError,
        ),
    )

    engine = MultimodalSearchEngine({"paths": {"db_path": str(database)}})
    assert engine.search_fts("Uncle Tony", top_k=1)[0]["id"] == "scene_0007"
    assert not _marker_exists(database)


def test_kg_reader_does_not_retain_direct_write_capable_connect(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "knowledge_graph.db"
    _seed_knowledge_graph(database)
    real_connect = sqlite3.connect
    monkeypatch.setattr(
        multimodal_search,
        "sqlite3",
        types.SimpleNamespace(
            connect=_write_capability_connect(real_connect),
            OperationalError=sqlite3.OperationalError,
        ),
    )

    engine = MultimodalSearchEngine({"paths": {"knowledge_graph_db": str(database)}})
    assert "scene_0007" in engine._load_kg_scene_context()
    assert not _marker_exists(database)


def test_provenance_reader_does_not_retain_direct_write_capable_connect(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "memory.db"
    _seed_memory_database(database)
    real_connect = sqlite3.connect
    monkeypatch.setattr(
        memory_provenance,
        "sqlite3",
        types.SimpleNamespace(
            connect=_write_capability_connect(real_connect),
            Row=sqlite3.Row,
        ),
    )
    hits = [
        {
            "id": 7,
            "score": 0.9,
            "payload": {"scene_id": "scene_0007", "modality": "clip"},
        }
    ]

    memory_provenance.attach_provenance_to_hits(str(database), hits)

    assert hits[0]["provenance"]["scene_id"] == "scene_0007"
    assert hits[0]["confidence"]["intrinsic"] == 0.9
    assert not _marker_exists(database)


def test_faiss_shadow_reader_does_not_retain_direct_write_capable_connect(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Preload the authority module so a later sys.modules trap can detect only
    # the selected caller's local sqlite3 import, not the common helper.
    try:
        _authority_module()
    except ModuleNotFoundError:
        pass
    database = tmp_path / "memory.db"
    index_path = tmp_path / "memory.index"
    _seed_memory_database(database)
    index_path.write_bytes(b"fixture")
    _install_fake_faiss(monkeypatch)

    fake_provenance = types.ModuleType("steps.common.memory_provenance")
    fake_provenance.attach_provenance_to_hits = lambda _db, _hits: None
    monkeypatch.setitem(sys.modules, "steps.common.memory_provenance", fake_provenance)

    fake_sqlite = types.ModuleType("sqlite3")
    fake_sqlite.connect = _write_capability_connect(sqlite3.connect)
    monkeypatch.setitem(sys.modules, "sqlite3", fake_sqlite)

    store = memory_stores.FaissMemory(
        index_path=str(index_path),
        dim=2,
        db_path=str(database),
        cfg={"memory": {"routing": {"quantization_shadow_mode": True}}},
        retrieval_event_policy=retrieval_events.RetrievalEventPolicy(enabled=False),
    )
    assert len(
        store.query(
            [0.1, 0.2],
            top_k=1,
            retrieval_context="system.healthcheck",
        )
    ) == 1
    assert not _marker_exists(database)


def test_fts_missing_database_does_not_open_or_create(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.db"
    authority = _authority_module()
    monkeypatch.setattr(
        authority,
        "open_sqlite_read_connection",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("missing path must short-circuit before open")
        ),
    )

    engine = MultimodalSearchEngine({"paths": {"db_path": str(missing)}})
    assert engine.search_fts("fixture", top_k=1) == []
    assert not missing.exists()
    assert not missing.with_name(f"{missing.name}-wal").exists()
    assert not missing.with_name(f"{missing.name}-shm").exists()


def test_real_fts5_query_remains_authorized(tmp_path: Path) -> None:
    database = tmp_path / "fts5.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            """
            CREATE TABLE scenes (
                id TEXT PRIMARY KEY,
                video_hash TEXT,
                start REAL,
                end REAL,
                meta TEXT
            );
            CREATE VIRTUAL TABLE scene_text_fts USING fts5(
                scene_id UNINDEXED,
                video_hash UNINDEXED,
                content_type UNINDEXED,
                text
            );
            INSERT INTO scenes VALUES ('scene_0007', 'video-alpha', 1.0, 2.0, '{}');
            INSERT INTO scene_text_fts VALUES (
                'scene_0007',
                'video-alpha',
                'transcript',
                'Uncle Tony fixture'
            );
            """
        )
        connection.commit()
    finally:
        connection.close()

    engine = MultimodalSearchEngine({"paths": {"db_path": str(database)}})
    result = engine.search_fts("Uncle Tony", top_k=1)
    assert result[0]["id"] == "scene_0007"
    assert result[0]["payload"]["text"] == "Uncle Tony fixture"


@pytest.mark.parametrize("include_confidence", [True, False])
def test_provenance_schema_projection_handles_optional_confidence_without_pragma(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    include_confidence: bool,
) -> None:
    database = tmp_path / "memory.db"
    _seed_memory_database(database, include_confidence=include_confidence)
    authority = _authority_module()
    real_open = authority.open_sqlite_read_connection
    statements: list[str] = []

    def traced_open(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        connection = real_open(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(authority, "open_sqlite_read_connection", traced_open)
    hits = [
        {
            "id": 7,
            "score": 0.9,
            "payload": {"scene_id": "scene_0007", "modality": "clip"},
        }
    ]

    memory_provenance.attach_provenance_to_hits(str(database), hits)

    assert hits[0]["provenance"]["scene_id"] == "scene_0007"
    expected_intrinsic = 0.9 if include_confidence else None
    assert hits[0]["confidence"]["intrinsic"] == expected_intrinsic
    normalized = [" ".join(statement.upper().split()) for statement in statements]
    assert "SELECT * FROM MEMORY_COMMIT_EVENTS LIMIT 0" in normalized
    assert not any("PRAGMA TABLE_INFO" in statement for statement in normalized)


def test_qdrant_query_preserves_bounded_provenance_annotation(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    _seed_memory_database(database, embedding_id="point-1")
    client = QdrantClient(
        QdrantConfig(
            host="http://qdrant.invalid",
            collection="goodq_text",
            dim=3,
            db_path=str(database),
            retrieval_event_policy=retrieval_events.RetrievalEventPolicy(enabled=False),
        )
    )
    client.session = _QdrantSession(
        [
            _QdrantResponse(200, {}),
            _QdrantResponse(
                200,
                {
                    "result": [
                        {
                            "id": "point-1",
                            "score": 0.75,
                            "payload": {
                                "scene_id": "scene_0007",
                                "modality": "clip",
                            },
                        }
                    ]
                },
            ),
        ]
    )

    hits = client.query(
        [0.0, 0.0, 0.0],
        top_k=1,
        retrieval_context="system.healthcheck",
    )

    assert hits[0]["provenance"]["scene_id"] == "scene_0007"
    assert hits[0]["confidence"]["intrinsic"] == 0.9


def test_faiss_query_preserves_provenance_shadow_scoring_and_telemetry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "memory.db"
    index_path = tmp_path / "memory.index"
    _seed_memory_database(database, embedding_id="faiss-hash-7")
    index_path.write_bytes(b"fixture")

    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "UPDATE embeddings SET tq_indices=?, tq_norm=?, tq_qjl_sign=?, "
            "tq_norm_residual=? WHERE faiss_id=7",
            (
                np.array([1, 2], dtype=np.uint8).tobytes(),
                1.0,
                np.array([1, -1], dtype=np.int8).tobytes(),
                0.1,
            ),
        )
        connection.execute(
            "INSERT INTO embeddings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "faiss-hash-8",
                8,
                "clip",
                "scene_0008",
                np.array([2, 3], dtype=np.uint8).tobytes(),
                1.1,
                np.array([-1, 1], dtype=np.int8).tobytes(),
                0.2,
            ),
        )
        connection.execute(
            """
            INSERT INTO memory_commit_events (
                ts_utc, scene_id, video_id, modality, model, embedding_id,
                component, attempted, committed, reason, targets_json,
                confidence_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-07-13T00:00:01+00:00",
                "scene_0008",
                "video-alpha",
                "clip",
                "fixture-model",
                "faiss-hash-8",
                "fixture",
                1,
                1,
                "fixture",
                "{}",
                json.dumps({"intrinsic": 0.8}),
            ),
        )
        connection.commit()
    finally:
        connection.close()

    _install_fake_faiss(
        monkeypatch,
        ids=(7, 8),
        scores=(0.1, 0.2),
    )
    estimator_calls: list[tuple[Any, ...]] = []

    class FakeTurboQuantEncoder:
        def estimate_inner_product(self, *args: Any) -> float:
            estimator_calls.append(args)
            return 0.1

    monkeypatch.setattr(quantization, "TurboQuantEncoder", FakeTurboQuantEncoder)
    telemetry_batches: list[list[Any]] = []
    monkeypatch.setattr(
        retrieval_events,
        "emit_retrieval_events",
        lambda _db, events, **_kwargs: telemetry_batches.append(list(events)),
    )

    store = memory_stores.FaissMemory(
        index_path=str(index_path),
        dim=2,
        db_path=str(database),
        cfg={"memory": {"routing": {"quantization_shadow_mode": True}}},
        retrieval_event_policy=retrieval_events.RetrievalEventPolicy(enabled=True),
    )
    hits = store.query(
        [0.1, 0.2],
        top_k=2,
        retrieval_context="system.healthcheck",
    )

    assert [hit["id"] for hit in hits] == [7, 8]
    assert [hit["score"] for hit in hits] == pytest.approx([0.1, 0.2])
    assert [hit["provenance"]["scene_id"] for hit in hits] == [
        "scene_0007",
        "scene_0008",
    ]
    assert len(estimator_calls) == 2
    assert len(telemetry_batches) == 1
    assert len(telemetry_batches[0]) == 2


def test_faiss_shadow_failure_closes_and_preserves_hits_and_telemetry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "memory.db"
    index_path = tmp_path / "memory.index"
    _seed_memory_database(database)
    index_path.write_bytes(b"fixture")
    _install_fake_faiss(monkeypatch)

    fake_provenance = types.ModuleType("steps.common.memory_provenance")
    fake_provenance.attach_provenance_to_hits = lambda _db, _hits: None
    monkeypatch.setitem(sys.modules, "steps.common.memory_provenance", fake_provenance)

    class FailingConnection:
        closed = False

        def execute(self, _statement: str, _parameters: Any = None):
            raise sqlite3.OperationalError("shadow query failed")

        def close(self) -> None:
            self.closed = True

    failing = FailingConnection()
    authority = _authority_module()
    monkeypatch.setattr(
        authority,
        "open_sqlite_read_connection",
        lambda *args, **kwargs: failing,
    )
    telemetry_batches: list[list[Any]] = []
    monkeypatch.setattr(
        retrieval_events,
        "emit_retrieval_events",
        lambda _db, events, **_kwargs: telemetry_batches.append(list(events)),
    )

    store = memory_stores.FaissMemory(
        index_path=str(index_path),
        dim=2,
        db_path=str(database),
        cfg={"memory": {"routing": {"quantization_shadow_mode": True}}},
        retrieval_event_policy=retrieval_events.RetrievalEventPolicy(enabled=True),
    )
    hits = store.query(
        [0.1, 0.2],
        top_k=1,
        retrieval_context="system.healthcheck",
    )

    assert [hit["id"] for hit in hits] == [7]
    assert failing.closed is True
    assert len(telemetry_batches) == 1
    assert len(telemetry_batches[0]) == 1


def test_common_read_authority_rejects_missing_database(tmp_path: Path) -> None:
    missing = tmp_path / "missing.db"
    authority = _authority_module()

    with pytest.raises(FileNotFoundError, match="unavailable"):
        authority.open_sqlite_read_connection(missing)

    assert not missing.exists()
    assert not missing.with_name(f"{missing.name}-wal").exists()
    assert not missing.with_name(f"{missing.name}-shm").exists()


def test_common_read_authority_forwards_read_only_connect_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "connect-contract.db"
    seed = sqlite3.connect(database)
    seed.close()
    authority = _authority_module()
    real_connect = authority.sqlite3.connect
    observed: dict[str, Any] = {}

    def capture_connect(database_arg: str, *args: Any, **kwargs: Any):
        observed["database"] = database_arg
        observed["args"] = args
        observed["kwargs"] = kwargs
        return real_connect(database_arg, *args, **kwargs)

    monkeypatch.setattr(authority.sqlite3, "connect", capture_connect)

    reader = authority.open_sqlite_read_connection(
        database,
        timeout=0.25,
        check_same_thread=False,
    )
    reader.close()

    assert observed == {
        "database": f"{database.resolve().as_uri()}?mode=ro",
        "args": (),
        "kwargs": {
            "uri": True,
            "timeout": 0.25,
            "check_same_thread": False,
        },
    }


def test_common_read_authority_handles_special_character_uri_path(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "space # percent%"
    directory.mkdir()
    database = directory / "memory #100%.db"
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE evidence (value TEXT)")
        connection.execute("INSERT INTO evidence VALUES ('fixture')")
        connection.commit()
    finally:
        connection.close()

    reader = _authority_module().open_sqlite_read_connection(database)
    try:
        assert reader.execute("SELECT value FROM evidence").fetchone() == (
            "fixture",
        )
    finally:
        reader.close()


def test_common_read_authority_sees_live_wal_and_denies_main_mutation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "live-wal.db"
    writer = sqlite3.connect(database)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE evidence (value TEXT)")
        writer.commit()
        writer.execute("INSERT INTO evidence VALUES ('committed-in-wal')")
        writer.commit()
        assert database.with_name(f"{database.name}-wal").exists()

        reader = _authority_module().open_sqlite_read_connection(database)
        try:
            assert reader.execute("SELECT value FROM evidence").fetchone() == (
                "committed-in-wal",
            )
            for statement in (
                "INSERT INTO evidence VALUES ('forbidden')",
                "UPDATE evidence SET value='forbidden'",
                "DELETE FROM evidence",
                "CREATE TABLE forbidden (id INTEGER)",
                "CREATE TEMP TABLE forbidden_temp (id INTEGER)",
                "ALTER TABLE evidence ADD COLUMN forbidden TEXT",
                "DROP TABLE evidence",
            ):
                with pytest.raises(sqlite3.DatabaseError):
                    reader.execute(statement)
            with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
                reader.execute("DETACH DATABASE extra")
        finally:
            reader.close()
    finally:
        writer.close()


@pytest.mark.parametrize(
    "statement",
    [
        "ATTACH DATABASE ? AS extra",
        "VACUUM INTO ?",
    ],
)
def test_common_read_authority_rejects_external_database_creation(
    tmp_path: Path,
    statement: str,
) -> None:
    database = tmp_path / "existing.db"
    external = tmp_path / "must-stay-absent.db"
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE evidence (value TEXT)")
        connection.commit()
    finally:
        connection.close()

    reader = _authority_module().open_sqlite_read_connection(database)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            reader.execute(statement, (str(external),))
    finally:
        reader.close()

    assert not external.exists()


def test_common_read_authority_cannot_disable_query_only(tmp_path: Path) -> None:
    database = tmp_path / "existing.db"
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE evidence (value TEXT)")
        connection.commit()
    finally:
        connection.close()

    reader = _authority_module().open_sqlite_read_connection(database)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            reader.execute("PRAGMA query_only=OFF")
        assert reader.execute("PRAGMA query_only").fetchone() == (1,)
    finally:
        reader.close()


def test_common_read_authority_closes_when_policy_setup_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "existing.db"
    database.write_bytes(b"fixture")
    authority = _authority_module()

    class FailingConnection:
        closed = False

        def execute(self, _statement: str):
            raise sqlite3.OperationalError("policy setup failed")

        def close(self) -> None:
            self.closed = True

    connection = FailingConnection()
    monkeypatch.setattr(authority.sqlite3, "connect", lambda *args, **kwargs: connection)

    with pytest.raises(sqlite3.OperationalError, match="policy setup failed"):
        authority.open_sqlite_read_connection(database)

    assert connection.closed is True


def test_summary_wrapper_delegates_to_common_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "summary.db"
    database.write_bytes(b"fixture")
    authority = _authority_module()
    sentinel = object()
    calls: list[tuple[Path | str, dict[str, Any]]] = []

    def fake_open(path: Path | str, **kwargs: Any):
        calls.append((path, kwargs))
        return sentinel

    monkeypatch.setattr(authority, "open_sqlite_read_connection", fake_open)

    assert summary_aggregator.open_summary_read_connection(database) is sentinel
    assert calls == [
        (
            database,
            {
                "unavailable_message": "Summary database is unavailable",
                "timeout": 5.0,
                "check_same_thread": True,
            },
        )
    ]


def test_fts_open_failure_still_propagates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "memory.db"
    _seed_memory_database(database)
    authority = _authority_module()
    monkeypatch.setattr(
        authority,
        "open_sqlite_read_connection",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            sqlite3.OperationalError("open failed")
        ),
    )

    engine = MultimodalSearchEngine({"paths": {"db_path": str(database)}})
    with pytest.raises(sqlite3.OperationalError, match="open failed"):
        engine.search_fts("fixture", top_k=1)


def test_kg_and_provenance_open_failures_remain_best_effort(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    memory_database = tmp_path / "memory.db"
    graph_database = tmp_path / "knowledge_graph.db"
    _seed_memory_database(memory_database)
    _seed_knowledge_graph(graph_database)
    authority = _authority_module()
    monkeypatch.setattr(
        authority,
        "open_sqlite_read_connection",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            sqlite3.OperationalError("open failed")
        ),
    )

    engine = MultimodalSearchEngine(
        {"paths": {"knowledge_graph_db": str(graph_database)}}
    )
    assert engine._load_kg_scene_context() == {}

    hits = [{"id": 7, "score": 0.9, "payload": {"scene_id": "scene_0007"}}]
    memory_provenance.attach_provenance_to_hits(str(memory_database), hits)
    assert "provenance" not in hits[0]


def test_fts_and_kg_post_open_failures_close_connections(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    memory_database = tmp_path / "memory.db"
    graph_database = tmp_path / "knowledge_graph.db"
    _seed_memory_database(memory_database)
    _seed_knowledge_graph(graph_database)
    authority = _authority_module()

    class FailingConnection:
        def __init__(self) -> None:
            self.closed = False

        def cursor(self):
            return self

        def execute(self, _statement: str, _parameters: Any = None):
            raise sqlite3.OperationalError("post-open query failed")

        def close(self) -> None:
            self.closed = True

    fts_connection = FailingConnection()
    kg_connection = FailingConnection()
    pending = iter([fts_connection, kg_connection])
    monkeypatch.setattr(
        authority,
        "open_sqlite_read_connection",
        lambda *args, **kwargs: next(pending),
    )

    fts_engine = MultimodalSearchEngine(
        {"paths": {"db_path": str(memory_database)}}
    )
    assert fts_engine.search_fts("fixture", top_k=1) == []

    kg_engine = MultimodalSearchEngine(
        {"paths": {"knowledge_graph_db": str(graph_database)}}
    )
    assert kg_engine._load_kg_scene_context() == {}
    assert kg_engine._kg_scene_context_error is True
    assert fts_connection.closed is True
    assert kg_connection.closed is True


def test_selected_readers_use_common_authority_and_close_connections(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    memory_database = tmp_path / "memory.db"
    graph_database = tmp_path / "knowledge_graph.db"
    index_path = tmp_path / "memory.index"
    _seed_memory_database(memory_database)
    _seed_knowledge_graph(graph_database)
    index_path.write_bytes(b"fixture")
    _install_fake_faiss(monkeypatch)

    authority = _authority_module()
    real_open = authority.open_sqlite_read_connection
    opened: list[sqlite3.Connection] = []
    calls: list[tuple[Path, float, bool]] = []

    def tracked_open(
        path: Path | str,
        *,
        unavailable_message: str = "SQLite database is unavailable",
        timeout: float = 5.0,
        check_same_thread: bool = True,
    ) -> sqlite3.Connection:
        connection = real_open(
            path,
            unavailable_message=unavailable_message,
            timeout=timeout,
            check_same_thread=check_same_thread,
        )
        calls.append((Path(path), timeout, check_same_thread))
        opened.append(connection)
        return connection

    monkeypatch.setattr(authority, "open_sqlite_read_connection", tracked_open)

    engine = MultimodalSearchEngine(
        {
            "paths": {
                "db_path": str(memory_database),
                "knowledge_graph_db": str(graph_database),
            }
        }
    )
    assert engine.search_fts("Uncle Tony", top_k=1)
    assert engine._load_kg_scene_context()

    hits = [{"id": 7, "score": 0.9, "payload": {"scene_id": "scene_0007"}}]
    memory_provenance.attach_provenance_to_hits(str(memory_database), hits)
    assert "provenance" in hits[0]

    store = memory_stores.FaissMemory(
        index_path=str(index_path),
        dim=2,
        db_path=str(memory_database),
        cfg={"memory": {"routing": {"quantization_shadow_mode": True}}},
        retrieval_event_policy=retrieval_events.RetrievalEventPolicy(enabled=False),
    )
    assert store.query(
        [0.1, 0.2],
        top_k=1,
        retrieval_context="system.healthcheck",
    )

    assert calls == [
        (memory_database, 5.0, True),
        (graph_database, 5.0, True),
        (memory_database, 0.2, False),
        (memory_database, 0.2, False),
        (memory_database, 5.0, True),
    ]
    for connection in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            connection.execute("SELECT 1")
