from __future__ import annotations

from dataclasses import FrozenInstanceError
import importlib
import inspect
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys
import threading
import types
from typing import Any

import numpy as np
import pytest
import yaml
from pydantic import ValidationError

from cli import observability_health
from retrieval.multimodal_search import MultimodalSearchEngine
from scripts import config_schema
from steps.common import memory_provenance, memory_stores, retrieval_events
from steps.common import qdrant_client as qdrant_module
from steps.common.qdrant_client import QdrantClient, QdrantConfig


_ENV_KEYS = ("GOODQ_RETRIEVAL_EVENTS", "GOODQ_RETRIEVAL_EVENTS_JSONL")
_SCHEMA_NAMES = {
    "retrieval_events",
    "idx_re_ts",
    "idx_re_embedding",
    "idx_re_scene",
    "idx_re_store",
}


def _clear_policy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ENV_KEYS:
        monkeypatch.delenv(name, raising=False)


def _policy_class():
    cls = getattr(retrieval_events, "RetrievalEventPolicy", None)
    assert cls is not None, "RetrievalEventPolicy must be the sole runtime carrier"
    return cls


def _policy(
    *,
    enabled: bool = True,
    jsonl_fallback: bool = True,
    log_dir: Path | str | None = None,
):
    cls = _policy_class()
    return cls(
        enabled=enabled,
        jsonl_fallback=jsonl_fallback,
        log_dir=str(log_dir) if log_dir is not None else None,
    )


def _event(embedding_id: str = "embedding-1") -> retrieval_events.RetrievalEvent:
    return retrieval_events.RetrievalEvent(
        ts_utc="2026-07-13T12:00:00+00:00",
        store="qdrant",
        retrieval_context="human.ui.search",
        embedding_id=embedding_id,
        scene_id="scene-1",
        modality="text",
        model="model-1",
        score=0.75,
        details={"canary": "secret-query-canary"},
    )


def _seed_database(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE seed_marker(value TEXT NOT NULL)")
        conn.execute("INSERT INTO seed_marker(value) VALUES ('preserve-me')")


def _event_rows(path: Path) -> list[tuple[Any, ...]]:
    with sqlite3.connect(path) as conn:
        return conn.execute(
            "SELECT store, retrieval_context, embedding_id, scene_id, modality, model, score, details_json "
            "FROM retrieval_events ORDER BY id"
        ).fetchall()


def _schema_names(path: Path) -> set[str]:
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE name IN (?,?,?,?,?)",
            tuple(sorted(_SCHEMA_NAMES)),
        ).fetchall()
    return {str(row[0]) for row in rows}


def _emit(path: Path, *, policy=None, embedding_id: str = "embedding-1") -> None:
    retrieval_events.emit_retrieval_events(
        str(path),
        [_event(embedding_id)],
        policy=policy if policy is not None else _policy(),
    )


def test_canonical_observability_models_are_strict_and_frozen() -> None:
    policy_cls = getattr(config_schema, "RetrievalEventsObservabilityConfig", None)
    observability_cls = getattr(config_schema, "ObservabilityConfig", None)
    assert policy_cls is not None
    assert observability_cls is not None

    model = observability_cls.model_validate(
        {
            "retrieval_events": {"enabled": False, "jsonl_fallback": False},
            "summaries_preview": True,
        }
    )
    assert model.retrieval_events.enabled is False
    assert model.retrieval_events.jsonl_fallback is False
    assert model.summaries_preview is True

    with pytest.raises(ValidationError) as nested_error:
        observability_cls.model_validate(
            {
                "retrieval_events": {
                    "enabled": True,
                    "jsonl_fallback": True,
                    "unknown": "forbidden",
                }
            }
        )
    assert any(
        tuple(error["loc"]) == ("retrieval_events", "unknown")
        and error["type"] == "extra_forbidden"
        for error in nested_error.value.errors()
    )

    with pytest.raises(ValidationError):
        observability_cls.model_validate(
            {
                "retrieval_events": {"enabled": True, "jsonl_fallback": True},
                "unknown": "forbidden",
            }
        )
    with pytest.raises(ValidationError):
        model.retrieval_events.enabled = True


def test_competing_memory_policy_is_targeted_without_tightening_legacy_memory() -> None:
    with pytest.raises(ValidationError) as exc_info:
        config_schema.GoodQConfig.model_validate(
            {
                "memory": {
                    "routing": {},
                    "retrieval_events": {"enabled": False},
                }
            }
        )
    assert any(
        tuple(error["loc"]) == ("memory",)
        and "memory.retrieval_events" in error["msg"]
        for error in exc_info.value.errors()
    )

    legacy_projection = config_schema.MemoryConfigSection.model_validate(
        {
            "routing": {},
            "ttl_seconds": 123,
            "max_ephemeral_items": 456,
            "dims": {"text": 384},
        }
    ).model_dump()
    assert legacy_projection == {
        "routing": {
            "quantization_enabled": False,
            "quantization_shadow_mode": True,
        }
    }


def test_config_yaml_declares_canonical_retrieval_event_defaults() -> None:
    config_path = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    assert cfg["observability"]["retrieval_events"] == {
        "enabled": True,
        "jsonl_fallback": True,
    }


def test_policy_resolution_is_canonical_frozen_and_ignores_legacy_memory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_policy_env(monkeypatch)
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    cfg = {
        "paths": {"log_dir": str(log_dir)},
        "observability": {
            "retrieval_events": {"enabled": False, "jsonl_fallback": False}
        },
        "memory": {
            "retrieval_events": {"enabled": True, "jsonl_fallback": True}
        },
    }

    policy = retrieval_events.resolve_retrieval_event_policy(cfg)

    assert policy.enabled is False
    assert policy.jsonl_fallback is False
    assert Path(policy.log_dir) == log_dir.resolve()
    with pytest.raises(FrozenInstanceError):
        policy.enabled = True

    raw_legacy_only = {
        "paths": {"log_dir": str(log_dir)},
        "memory": {
            "retrieval_events": {"enabled": False, "jsonl_fallback": False}
        },
    }
    ignored = retrieval_events.resolve_retrieval_event_policy(raw_legacy_only)
    assert ignored.enabled is True
    assert ignored.jsonl_fallback is True


def test_policy_environment_precedence_and_raw_boolean_parsing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    cfg = {
        "paths": {"log_dir": str(log_dir)},
        "observability": {
            "retrieval_events": {"enabled": False, "jsonl_fallback": True}
        },
    }
    monkeypatch.setenv("GOODQ_RETRIEVAL_EVENTS", "yes")
    monkeypatch.setenv("GOODQ_RETRIEVAL_EVENTS_JSONL", "0")
    policy = retrieval_events.resolve_retrieval_event_policy(cfg)
    assert policy.enabled is True
    assert policy.jsonl_fallback is False

    _clear_policy_env(monkeypatch)
    raw = {
        "observability": {
            "retrieval_events": {
                "enabled": "false",
                "jsonl_fallback": "malformed",
            }
        }
    }
    parsed = retrieval_events.resolve_retrieval_event_policy(raw)
    assert parsed.enabled is False
    assert parsed.jsonl_fallback is True


def test_resolved_policy_does_not_reparse_mutated_config_or_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_policy_env(monkeypatch)
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    cfg = {
        "paths": {"log_dir": str(log_dir)},
        "observability": {
            "retrieval_events": {"enabled": False, "jsonl_fallback": False}
        },
    }
    policy = retrieval_events.resolve_retrieval_event_policy(cfg)

    cfg["observability"]["retrieval_events"] = {
        "enabled": True,
        "jsonl_fallback": True,
    }
    monkeypatch.setenv("GOODQ_RETRIEVAL_EVENTS", "1")
    monkeypatch.setenv("GOODQ_RETRIEVAL_EVENTS_JSONL", "1")
    log_dir.rmdir()

    assert policy.enabled is False
    assert policy.jsonl_fallback is False
    assert Path(policy.log_dir) == log_dir.resolve()


@pytest.mark.parametrize("destination_kind", ["missing", "file"])
def test_policy_marks_unavailable_log_destination_explicitly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    destination_kind: str,
) -> None:
    _clear_policy_env(monkeypatch)
    destination = tmp_path / "not-a-log-directory"
    if destination_kind == "file":
        destination.write_text("not a directory", encoding="utf-8")

    policy = retrieval_events.resolve_retrieval_event_policy(
        {
            "paths": {"log_dir": str(destination)},
            "observability": {
                "retrieval_events": {"enabled": True, "jsonl_fallback": True}
            },
        }
    )

    assert policy.log_dir is None
    assert destination.exists() is (destination_kind == "file")


def test_emitter_signature_has_one_resolved_policy_authority() -> None:
    parameters = inspect.signature(retrieval_events.emit_retrieval_events).parameters
    assert "policy" in parameters
    assert "cfg" not in parameters
    assert "enabled" not in parameters
    assert "log_dir" not in parameters


def test_generic_qdrant_builder_accepts_exact_policy_object(tmp_path: Path) -> None:
    policy = _policy(enabled=False, jsonl_fallback=False)
    cfg = {
        "qdrant": {
            "enabled": True,
            "host": "http://qdrant.invalid",
            "collections": {"text": "goodq_text"},
        },
        "paths": {"db_path": str(tmp_path / "missing.db")},
    }
    client = qdrant_module.build_qdrant_client(
        cfg,
        dim=3,
        key="text",
        retrieval_event_policy=policy,
    )
    assert client is not None
    assert client.cfg.retrieval_event_policy is policy


def test_shared_text_builder_propagates_one_policy_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    policy = _policy(enabled=False, jsonl_fallback=False)
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        memory_stores,
        "resolve_retrieval_event_policy",
        lambda _cfg: policy,
        raising=False,
    )

    def fake_build_qdrant_client(
        _cfg: dict[str, Any],
        dim: int,
        key: str,
        *,
        retrieval_event_policy=None,
    ):
        captured["policy"] = retrieval_event_policy
        return types.SimpleNamespace(
            cfg=types.SimpleNamespace(dim=dim, collection=f"goodq_{key}")
        )

    monkeypatch.setattr(memory_stores, "build_qdrant_client", fake_build_qdrant_client)
    cfg = {
        "paths": {
            "db_path": str(tmp_path / "missing.db"),
            "faiss_index_path": str(tmp_path / "text.index"),
        },
        "memory": {"routing": {}, "dims": {"text": 3}},
    }
    stores = memory_stores.build_text_stores(cfg)

    assert stores["ephemeral"].retrieval_event_policy is policy
    assert stores["faiss"].retrieval_event_policy is policy
    assert captured["policy"] is policy


def test_engine_freezes_policy_at_construction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_policy_env(monkeypatch)
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    cfg = {
        "qdrant": {
            "host": "http://qdrant.invalid",
            "collections": {"text": "goodq_text"},
            "embedding_dims": {"text": 3},
        },
        "paths": {
            "db_path": str(tmp_path / "missing.db"),
            "log_dir": str(log_dir),
            "data_root": str(tmp_path / "data"),
        },
        "phase6": {"retrieval": {"fusion_weights": {}}},
        "observability": {
            "retrieval_events": {"enabled": False, "jsonl_fallback": False}
        },
    }
    engine = MultimodalSearchEngine(cfg)
    cfg["observability"]["retrieval_events"] = {
        "enabled": True,
        "jsonl_fallback": True,
    }
    monkeypatch.setenv("GOODQ_RETRIEVAL_EVENTS", "1")
    text_client = engine._get_qdrant_client("goodq_text")
    audio_client = engine._get_qdrant_client("goodq_audio")

    assert text_client.cfg.retrieval_event_policy.enabled is False
    assert text_client.cfg.retrieval_event_policy.jsonl_fallback is False
    assert Path(text_client.cfg.retrieval_event_policy.log_dir) == log_dir.resolve()
    assert audio_client.cfg.retrieval_event_policy is text_client.cfg.retrieval_event_policy


def test_health_sample_injects_disabled_policy_without_mutating_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setenv("GOODQ_RETRIEVAL_EVENTS", "1")

    class FakeClient:
        def query(self, *_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
            captured["query_env"] = os.environ.get("GOODQ_RETRIEVAL_EVENTS")
            return [{"id": "point-1", "provenance": {"scene_id": "scene-1"}}]

    def fake_build(
        _cfg: dict[str, Any],
        _dim: int,
        _key: str,
        *,
        retrieval_event_policy=None,
    ) -> FakeClient:
        captured["policy"] = retrieval_event_policy
        return FakeClient()

    monkeypatch.setattr(qdrant_module, "build_qdrant_client", fake_build)
    coverage, error = observability_health._provenance_coverage_sample(
        {"memory": {"dims": {"clip": 3}}},
        top_k=1,
    )

    assert error is None
    assert coverage == 1.0
    assert captured["policy"].enabled is False
    assert captured["policy"].jsonl_fallback is False
    assert captured["query_env"] == "1"
    assert os.environ["GOODQ_RETRIEVAL_EVENTS"] == "1"


def test_qdrant_ephemeral_and_faiss_emit_exact_policy_without_changing_hits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    policy = _policy(enabled=False, jsonl_fallback=False)
    captured: list[Any] = []

    def capture(_db_path: str | None, _events: Any, *, policy=None) -> None:
        captured.append(policy)
        raise RuntimeError("forced telemetry sink failure")

    monkeypatch.setattr(retrieval_events, "emit_retrieval_events", capture)
    monkeypatch.setattr(memory_stores, "emit_retrieval_events", capture)
    monkeypatch.setattr(memory_provenance, "attach_provenance_to_hits", lambda *_args: None)

    qdrant = QdrantClient(
        QdrantConfig(
            host="http://qdrant.invalid",
            collection="goodq_text",
            dim=2,
            retrieval_event_policy=policy,
        )
    )
    qdrant._collection_ready = True

    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json() -> dict[str, Any]:
            return {
                "result": [
                    {"id": "q-1", "score": 0.9, "payload": {"scene_id": "s-1"}}
                ]
            }

    qdrant.session = types.SimpleNamespace(post=lambda *_args, **_kwargs: Response())
    qdrant_hits = qdrant.query([0.1, 0.2], top_k=1)

    ephemeral = memory_stores.EphemeralMemory(
        dim=2,
        retrieval_event_policy=policy,
    )
    assert ephemeral.insert(
        [{"id": "e-1", "vector": [1.0, 0.0], "payload": {"scene_id": "s-2"}}]
    )
    ephemeral_hits = ephemeral.query([1.0, 0.0], top_k=1)

    index_path = tmp_path / "text.index"
    index_path.write_bytes(b"fake-index")

    class FakeIndex:
        @staticmethod
        def search(_query: Any, k: int):
            return (
                np.array([[0.25]], dtype="float32"),
                np.array([[7]], dtype="int64"),
            )

    fake_faiss = types.SimpleNamespace(read_index=lambda _path: FakeIndex())
    monkeypatch.setitem(sys.modules, "faiss", fake_faiss)
    faiss = memory_stores.FaissMemory(
        str(index_path),
        dim=2,
        retrieval_event_policy=policy,
    )
    faiss_hits = faiss.query([0.1, 0.2], top_k=1)

    assert [hit["id"] for hit in qdrant_hits] == ["q-1"]
    assert [hit["id"] for hit in ephemeral_hits] == ["e-1"]
    assert [hit["id"] for hit in faiss_hits] == [7]
    assert captured == [policy, policy, policy]


def test_disabled_policy_is_a_true_no_op(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    database = tmp_path / "memory.db"
    _seed_database(database)
    before = database.read_bytes()
    caplog.set_level(logging.WARNING, logger=retrieval_events.__name__)

    _emit(database, policy=_policy(enabled=False, jsonl_fallback=True, log_dir=tmp_path))

    assert database.read_bytes() == before
    assert _schema_names(database) == set()
    assert not Path(f"{database}-wal").exists()
    assert not Path(f"{database}-shm").exists()
    assert not (tmp_path / "retrieval_events.jsonl").exists()
    assert caplog.messages == []


def test_disabled_policy_does_not_create_missing_primary(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    database = tmp_path / "missing.db"
    caplog.set_level(logging.WARNING, logger=retrieval_events.__name__)

    _emit(database, policy=_policy(enabled=False, log_dir=tmp_path))

    assert not database.exists()
    assert not Path(f"{database}-wal").exists()
    assert not Path(f"{database}-shm").exists()
    assert not (tmp_path / "retrieval_events.jsonl").exists()
    assert caplog.messages == []


def test_missing_primary_database_is_not_created_or_redirected(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    database = tmp_path / "secret-primary-name.db"
    logs = tmp_path / "logs"
    logs.mkdir()
    caplog.set_level(logging.WARNING, logger=retrieval_events.__name__)

    _emit(database, policy=_policy(log_dir=logs))

    assert not database.exists()
    assert not Path(f"{database}-wal").exists()
    assert not Path(f"{database}-shm").exists()
    assert not (logs / "retrieval_events.jsonl").exists()
    assert any("reason=missing_database" in message for message in caplog.messages)
    warning_text = "\n".join(caplog.messages)
    assert str(database.resolve()) not in warning_text
    assert "secret-primary-name" not in warning_text
    assert "secret-query-canary" not in warning_text


def test_non_file_primary_is_refused_without_fallback(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    database = tmp_path / "database-directory"
    database.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    caplog.set_level(logging.WARNING, logger=retrieval_events.__name__)

    _emit(database, policy=_policy(log_dir=logs))

    assert database.is_dir()
    assert not (logs / "retrieval_events.jsonl").exists()
    assert any("reason=missing_database" in message for message in caplog.messages)


def test_primary_disappearing_before_connect_is_not_recreated(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "memory.db"
    _seed_database(database)
    real_connect = sqlite3.connect

    def remove_before_connect(*args: Any, **kwargs: Any):
        database.unlink()
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(retrieval_events.sqlite3, "connect", remove_before_connect)
    _emit(database, policy=_policy())

    assert not database.exists()
    assert not Path(f"{database}-wal").exists()
    assert not Path(f"{database}-shm").exists()


def test_existing_database_receives_stable_schema_row_and_rw_uri(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "memory.db"
    _seed_database(database)
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    real_connect = sqlite3.connect

    def capture_connect(*args: Any, **kwargs: Any):
        calls.append((args, dict(kwargs)))
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(retrieval_events.sqlite3, "connect", capture_connect)
    _emit(database, policy=_policy())

    assert _schema_names(database) == _SCHEMA_NAMES
    rows = _event_rows(database)
    assert len(rows) == 1
    assert rows[0][0:7] == (
        "qdrant",
        "human.ui.search",
        "embedding-1",
        "scene-1",
        "text",
        "model-1",
        0.75,
    )
    assert json.loads(rows[0][7]) == {"canary": "secret-query-canary"}
    writer_call = calls[0]
    assert str(writer_call[0][0]).endswith("?mode=rw")
    assert writer_call[1]["uri"] is True
    assert writer_call[1]["timeout"] == pytest.approx(0.05)
    assert writer_call[1]["check_same_thread"] is False


def test_same_path_database_replacement_reestablishes_schema(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    _seed_database(database)
    _emit(database, policy=_policy(), embedding_id="before-replacement")
    assert [row[2] for row in _event_rows(database)] == ["before-replacement"]

    replacement = tmp_path / "replacement.db"
    _seed_database(replacement)
    os.replace(replacement, database)
    _emit(database, policy=_policy(), embedding_id="after-replacement")

    assert _schema_names(database) == _SCHEMA_NAMES
    assert [row[2] for row in _event_rows(database)] == ["after-replacement"]


def test_partial_schema_is_repaired_before_event_write(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    with sqlite3.connect(database) as conn:
        conn.execute(
            """
            CREATE TABLE retrieval_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts_utc TEXT NOT NULL,
              store TEXT NOT NULL,
              retrieval_context TEXT,
              embedding_id TEXT,
              scene_id TEXT,
              modality TEXT,
              model TEXT,
              score REAL,
              details_json TEXT
            )
            """
        )

    _emit(database, policy=_policy())

    assert _schema_names(database) == _SCHEMA_NAMES
    assert len(_event_rows(database)) == 1


@pytest.mark.parametrize("lock_message", ["database is locked", "database is busy"])
@pytest.mark.parametrize("jsonl_fallback", [False, True])
def test_locked_database_fallback_obeys_exact_frozen_policy(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    jsonl_fallback: bool,
    lock_message: str,
) -> None:
    database = tmp_path / "memory.db"
    _seed_database(database)
    logs = tmp_path / "exact-logs"
    logs.mkdir()
    caplog.set_level(logging.WARNING, logger=retrieval_events.__name__)

    def locked_connect(*_args: Any, **_kwargs: Any):
        raise sqlite3.OperationalError(lock_message)

    monkeypatch.setattr(retrieval_events.sqlite3, "connect", locked_connect)
    _emit(
        database,
        policy=_policy(jsonl_fallback=jsonl_fallback, log_dir=logs),
    )

    fallback = logs / "retrieval_events.jsonl"
    assert fallback.exists() is jsonl_fallback
    assert not (tmp_path / "retrieval_events.jsonl").exists()
    if jsonl_fallback:
        payload = json.loads(fallback.read_text(encoding="utf-8").strip())
        assert payload["embedding_id"] == "embedding-1"
    else:
        assert any("reason=sqlite_locked" in message for message in caplog.messages)
    warning_text = "\n".join(caplog.messages)
    assert str(database.resolve()) not in warning_text
    assert str(logs.resolve()) not in warning_text
    assert "secret-query-canary" not in warning_text


def test_missing_fallback_directory_is_not_created_or_relocated(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    database = tmp_path / "memory.db"
    _seed_database(database)
    missing_logs = tmp_path / "missing" / "logs"
    caplog.set_level(logging.WARNING, logger=retrieval_events.__name__)

    monkeypatch.setattr(
        retrieval_events.sqlite3,
        "connect",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            sqlite3.OperationalError("database is busy")
        ),
    )
    _emit(database, policy=_policy(log_dir=missing_logs))

    assert not missing_logs.exists()
    assert not (tmp_path / "retrieval_events.jsonl").exists()
    assert any("reason=fallback_unavailable" in message for message in caplog.messages)


def test_deleted_resolved_log_directory_is_rechecked_without_recreation(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    database = tmp_path / "memory.db"
    _seed_database(database)
    logs = tmp_path / "logs"
    logs.mkdir()
    policy = retrieval_events.resolve_retrieval_event_policy(
        {
            "paths": {"log_dir": str(logs)},
            "observability": {
                "retrieval_events": {"enabled": True, "jsonl_fallback": True}
            },
        }
    )
    logs.rmdir()
    caplog.set_level(logging.WARNING, logger=retrieval_events.__name__)
    monkeypatch.setattr(
        retrieval_events.sqlite3,
        "connect",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            sqlite3.OperationalError("database is locked")
        ),
    )

    _emit(database, policy=policy)

    assert not logs.exists()
    assert not (tmp_path / "retrieval_events.jsonl").exists()
    assert any("reason=fallback_unavailable" in message for message in caplog.messages)


def test_non_lock_sqlite_failure_never_uses_jsonl_and_warns_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    database = tmp_path / "private-memory.db"
    _seed_database(database)
    logs = tmp_path / "private-logs"
    logs.mkdir()
    caplog.set_level(logging.WARNING, logger=retrieval_events.__name__)

    def failed_connect(*_args: Any, **_kwargs: Any):
        raise sqlite3.OperationalError(
            f"disk I/O error at {database.resolve()} secret-query-canary"
        )

    monkeypatch.setattr(retrieval_events.sqlite3, "connect", failed_connect)
    _emit(database, policy=_policy(log_dir=logs))

    assert not (logs / "retrieval_events.jsonl").exists()
    assert any("reason=sqlite_error" in message for message in caplog.messages)
    warning_text = "\n".join(caplog.messages)
    assert str(database.resolve()) not in warning_text
    assert str(logs.resolve()) not in warning_text
    assert "secret-query-canary" not in warning_text


def test_non_sqlite_busy_exception_is_not_misclassified_as_lock(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    database = tmp_path / "memory.db"
    _seed_database(database)
    logs = tmp_path / "logs"
    logs.mkdir()
    caplog.set_level(logging.WARNING, logger=retrieval_events.__name__)

    def failed_connect(*_args: Any, **_kwargs: Any):
        raise OSError("resource busy secret-query-canary")

    monkeypatch.setattr(retrieval_events.sqlite3, "connect", failed_connect)
    _emit(database, policy=_policy(log_dir=logs))

    assert not (logs / "retrieval_events.jsonl").exists()
    assert any("reason=sqlite_error" in message for message in caplog.messages)
    warning_text = "\n".join(caplog.messages)
    assert "secret-query-canary" not in warning_text


def test_unrelated_sqlite_operational_error_text_is_not_misclassified_as_lock(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    database = tmp_path / "memory.db"
    _seed_database(database)
    logs = tmp_path / "logs"
    logs.mkdir()
    caplog.set_level(logging.WARNING, logger=retrieval_events.__name__)

    def failed_connect(*_args: Any, **_kwargs: Any):
        raise sqlite3.OperationalError(
            "busywork subsystem could not open locked-file-label secret-query-canary"
        )

    monkeypatch.setattr(retrieval_events.sqlite3, "connect", failed_connect)
    _emit(database, policy=_policy(log_dir=logs))

    assert not (logs / "retrieval_events.jsonl").exists()
    assert any("reason=sqlite_error" in message for message in caplog.messages)
    warning_text = "\n".join(caplog.messages)
    assert "secret-query-canary" not in warning_text


def test_concurrent_first_writers_preserve_every_event(
    tmp_path: Path,
) -> None:
    database = tmp_path / "memory.db"
    _seed_database(database)
    logs = tmp_path / "logs"
    logs.mkdir()
    policy = _policy(log_dir=logs)
    count = 8
    barrier = threading.Barrier(count)
    raised: list[BaseException] = []

    def worker(index: int) -> None:
        try:
            barrier.wait(timeout=5)
            _emit(database, policy=policy, embedding_id=f"thread-{index}")
        except BaseException as exc:  # pragma: no cover - asserted below
            raised.append(exc)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not raised
    assert all(not thread.is_alive() for thread in threads)
    persisted = {str(row[2]) for row in _event_rows(database)}
    fallback_path = logs / "retrieval_events.jsonl"
    fallback = set()
    if fallback_path.exists():
        fallback = {
            str(json.loads(line)["embedding_id"])
            for line in fallback_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    assert persisted | fallback == {f"thread-{index}" for index in range(count)}
    assert persisted.isdisjoint(fallback)


def test_empty_batch_is_a_silent_no_op(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.db"
    caplog.set_level(logging.WARNING, logger=retrieval_events.__name__)

    retrieval_events.emit_retrieval_events(
        str(missing),
        [],
        policy=_policy(),
    )

    assert not missing.exists()
    assert caplog.messages == []
