from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
import sqlite3
import sys
import traceback
import types
from typing import Any, Callable

import pytest

from cli import observability_rollup
from steps.common import memory_stores, retrieval_events


REPO_ROOT = Path(__file__).resolve().parents[2]
MEMORY_STORES_SOURCE = REPO_ROOT / "steps" / "common" / "memory_stores.py"
PATH_CANARY = "PRIVATE_FAISS_PARENT_CANARY_R05_F1"
RAW_EXCEPTION_CANARY = "PRIVATE_FAISS_EXCEPTION_CANARY_R05_F1"
SAFE_STORE_REF = "text.index"
EVENT_STORE_REF = "events-memory.index"
INSERT_STORE_REF = "insert-memory.index"
STATS_STORE_REF = "stats-memory.index"


class _NullLock:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def __enter__(self) -> "_NullLock":
        return self

    def __exit__(self, *_args: Any) -> bool:
        return False


class _SearchIndex:
    ntotal = 1

    def search(self, _vectors: Any, *, k: int) -> tuple[list[list[float]], list[list[int]]]:
        assert k >= 1
        return [[0.25]], [[7]]


def _index_path(tmp_path: Path, filename: str = SAFE_STORE_REF) -> Path:
    path = tmp_path / PATH_CANARY / "nested" / filename
    path.parent.mkdir(parents=True)
    path.write_bytes(b"fake-faiss-index")
    return path


def _install_fake_faiss(
    monkeypatch: pytest.MonkeyPatch,
    read_index: Callable[[str], Any] | None = None,
) -> types.ModuleType:
    module = types.ModuleType("faiss")
    module.read_index = read_index or (lambda _path: _SearchIndex())
    module.write_index = lambda _index, _path: None
    monkeypatch.setitem(sys.modules, "faiss", module)
    return module


def _install_provenance(
    monkeypatch: pytest.MonkeyPatch,
    attach: Callable[[str | None, list[dict[str, Any]]], None] | None = None,
) -> None:
    module = types.ModuleType("steps.common.memory_provenance")
    module.attach_provenance_to_hits = attach or (lambda _db, _hits: None)
    monkeypatch.setitem(sys.modules, "steps.common.memory_provenance", module)


def _capture_events(
    monkeypatch: pytest.MonkeyPatch,
) -> list[retrieval_events.RetrievalEvent]:
    captured: list[retrieval_events.RetrievalEvent] = []

    def capture(
        _db_path: str | None,
        events: list[retrieval_events.RetrievalEvent],
        **_kwargs: Any,
    ) -> None:
        captured.extend(events)

    monkeypatch.setattr(retrieval_events, "emit_retrieval_events", capture)
    monkeypatch.setattr(memory_stores, "emit_retrieval_events", capture)
    return captured


def _store(path: Path) -> memory_stores.FaissMemory:
    return memory_stores.FaissMemory(
        index_path=str(path),
        dim=2,
        retrieval_event_policy=retrieval_events.RetrievalEventPolicy(
            enabled=True,
            jsonl_fallback=False,
        ),
    )


def _query(store: memory_stores.FaissMemory) -> list[dict[str, Any]]:
    return store.query(
        [0.1, 0.2],
        top_k=1,
        retrieval_context="agent.reasoning",
    )


def _operation_warning(
    caplog: pytest.LogCaptureFixture,
    operation: str,
) -> str:
    matches = [
        record.getMessage()
        for record in caplog.records
        if record.name == memory_stores.__name__
        and record.levelno == logging.WARNING
        and f"operation={operation}" in record.getMessage()
    ]
    assert len(matches) == 1, matches
    return matches[0]


def _assert_safe_warning(
    caplog: pytest.LogCaptureFixture,
    *,
    operation: str,
    store_ref: str = SAFE_STORE_REF,
    exc_type: str | None = None,
    required: tuple[str, ...] = (),
) -> str:
    message = _operation_warning(caplog, operation)
    assert "store=faiss" in message
    assert f"store_ref={store_ref}" in message
    assert "index_path=" not in message
    assert " exc=" not in message
    if exc_type is not None:
        assert f"exc_type={exc_type}" in message
    for item in required:
        assert item in message
    for record in caplog.records:
        if record.name != memory_stores.__name__:
            continue
        surfaces = [
            record.getMessage(),
            repr(record.args),
            record.exc_text or "",
        ]
        if record.exc_info is not None:
            surfaces.append("".join(traceback.format_exception(*record.exc_info)))
        combined = "\n".join(surfaces)
        assert PATH_CANARY not in combined
        assert RAW_EXCEPTION_CANARY not in combined
    return message


def _raise_path_error(path: Path) -> None:
    raise RuntimeError(f"{RAW_EXCEPTION_CANARY}::{path}")


def test_faiss_query_emits_only_logical_store_ref_and_preserves_hit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = _index_path(tmp_path, EVENT_STORE_REF)
    _install_fake_faiss(monkeypatch)
    _install_provenance(monkeypatch)
    captured = _capture_events(monkeypatch)

    hits = _query(_store(path))

    assert hits == [{"id": 7, "score": 0.25, "payload": {}}]
    assert len(captured) == 1
    event = captured[0]
    assert event.retrieval_context == "agent.reasoning"
    assert event.score == pytest.approx(0.25)
    assert event.details == {
        "store_type": "faiss",
        "store_ref": EVENT_STORE_REF,
    }
    assert PATH_CANARY not in json.dumps(event.to_dict(), sort_keys=True)
    assert PATH_CANARY not in json.dumps(event.to_row(), sort_keys=True)


def test_retrieval_event_serializers_remain_lossless_for_opaque_details() -> None:
    opaque = {
        "opaque_non_path_marker": "preserve-exactly",
        "nested": {"count": 2},
    }
    event = retrieval_events.RetrievalEvent(
        ts_utc="2026-07-13T12:00:00+00:00",
        store="fixture",
        retrieval_context="system.healthcheck",
        details=opaque,
    )

    assert event.to_dict()["details"] == opaque
    assert json.loads(event.to_row()[-1]) == opaque


def test_faiss_source_has_no_path_bearing_warning_or_event_detail() -> None:
    tree = ast.parse(MEMORY_STORES_SOURCE.read_text(encoding="utf-8"))
    faiss_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "FaissMemory"
    )
    selected_methods = {
        node.name: node
        for node in faiss_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"insert", "query", "stats"}
    }

    path_bearing_warning_lines: list[int] = []
    forbidden_event_detail_lines: list[int] = []
    for method in selected_methods.values():
        for node in ast.walk(method):
            if not isinstance(node, ast.Call):
                continue
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "logger"
                and node.func.attr == "warning"
                and any(
                    isinstance(child, ast.Attribute)
                    and isinstance(child.value, ast.Name)
                    and child.value.id == "self"
                    and child.attr == "index_path"
                    for child in ast.walk(node)
                )
            ):
                path_bearing_warning_lines.append(node.lineno)
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "RetrievalEvent"
            ):
                details = next(
                    (keyword.value for keyword in node.keywords if keyword.arg == "details"),
                    None,
                )
                if isinstance(details, ast.Dict):
                    for key in details.keys:
                        if (
                            isinstance(key, ast.Constant)
                            and key.value == "index_path"
                        ):
                            forbidden_event_detail_lines.append(key.lineno)

    assert path_bearing_warning_lines == []
    assert forbidden_event_detail_lines == []


def test_faiss_insert_missing_ids_logs_logical_ref_and_preserves_rejection(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    path = _index_path(tmp_path, INSERT_STORE_REF)
    store = _store(path)
    fake_index = types.SimpleNamespace()
    fake_faiss = types.SimpleNamespace(write_index=lambda _index, _path: None)
    monkeypatch.setattr(memory_stores, "FaissLock", _NullLock)
    monkeypatch.setattr(store, "_load_index", lambda: (fake_index, fake_faiss))
    caplog.set_level(logging.WARNING, logger=memory_stores.__name__)

    result = store.insert([{"vector": [0.1, 0.2]}])

    assert result is False
    _assert_safe_warning(
        caplog,
        operation="insert",
        store_ref=INSERT_STORE_REF,
        required=(
            "reason=explicit_ids_required",
            "vector_count=1",
            "id_count=0",
            "missing_id_count=1",
        ),
    )


def test_faiss_insert_exception_logs_only_exception_type_and_preserves_false(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    store_ref = "insert-error.index"
    path = _index_path(tmp_path, store_ref)

    class FailingLock:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def __enter__(self) -> None:
            _raise_path_error(path)

        def __exit__(self, *_args: Any) -> bool:
            return False

    monkeypatch.setattr(memory_stores, "FaissLock", FailingLock)
    caplog.set_level(logging.WARNING, logger=memory_stores.__name__)

    result = _store(path).insert([{"id": 7, "vector": [0.1, 0.2]}])

    assert result is False
    _assert_safe_warning(
        caplog,
        operation="insert",
        store_ref=store_ref,
        exc_type="RuntimeError",
    )


def test_faiss_provenance_exception_preserves_hit_and_logs_logical_ref(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    store_ref = "provenance-error.index"
    path = _index_path(tmp_path, store_ref)
    _install_fake_faiss(monkeypatch)
    _install_provenance(monkeypatch, lambda _db, _hits: _raise_path_error(path))
    _capture_events(monkeypatch)
    caplog.set_level(logging.WARNING, logger=memory_stores.__name__)

    hits = _query(_store(path))

    assert hits == [{"id": 7, "score": 0.25, "payload": {}}]
    _assert_safe_warning(
        caplog,
        operation="attach_provenance",
        store_ref=store_ref,
        exc_type="RuntimeError",
    )


def test_faiss_score_parse_exception_preserves_hit_and_nulls_event_score(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    store_ref = "score-error.index"
    path = _index_path(tmp_path, store_ref)
    _install_fake_faiss(monkeypatch)

    class BadScore:
        def __float__(self) -> float:
            _raise_path_error(path)
            raise AssertionError("unreachable")

    bad_score = BadScore()

    def replace_score(_db: str | None, hits: list[dict[str, Any]]) -> None:
        hits[0]["score"] = bad_score

    _install_provenance(monkeypatch, replace_score)
    captured = _capture_events(monkeypatch)
    caplog.set_level(logging.WARNING, logger=memory_stores.__name__)

    hits = _query(_store(path))

    assert hits[0]["id"] == 7
    assert hits[0]["score"] is bad_score
    assert captured[0].score is None
    _assert_safe_warning(
        caplog,
        operation="query.score_parse",
        store_ref=store_ref,
        exc_type="RuntimeError",
    )


def test_faiss_event_emission_exception_preserves_hit_and_logs_logical_ref(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    store_ref = "emission-error.index"
    path = _index_path(tmp_path, store_ref)
    _install_fake_faiss(monkeypatch)
    _install_provenance(monkeypatch)

    def fail_emit(*_args: Any, **_kwargs: Any) -> None:
        _raise_path_error(path)

    monkeypatch.setattr(retrieval_events, "emit_retrieval_events", fail_emit)
    monkeypatch.setattr(memory_stores, "emit_retrieval_events", fail_emit)
    caplog.set_level(logging.WARNING, logger=memory_stores.__name__)

    hits = _query(_store(path))

    assert hits == [{"id": 7, "score": 0.25, "payload": {}}]
    _assert_safe_warning(
        caplog,
        operation="emit_retrieval_events",
        store_ref=store_ref,
        exc_type="RuntimeError",
    )


def test_faiss_query_exception_preserves_empty_result_and_logs_logical_ref(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    store_ref = "query-error.index"
    path = _index_path(tmp_path, store_ref)
    _install_fake_faiss(monkeypatch, lambda _path: _raise_path_error(path))
    caplog.set_level(logging.WARNING, logger=memory_stores.__name__)

    hits = _query(_store(path))

    assert hits == []
    _assert_safe_warning(
        caplog,
        operation="query",
        store_ref=store_ref,
        exc_type="RuntimeError",
    )


def test_faiss_stats_exception_preserves_unavailable_result_and_logs_logical_ref(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    path = _index_path(tmp_path, STATS_STORE_REF)
    _install_fake_faiss(monkeypatch, lambda _path: _raise_path_error(path))
    caplog.set_level(logging.WARNING, logger=memory_stores.__name__)

    result = _store(path).stats()

    assert result == {"available": False, "vectors": 0, "dim": 2}
    _assert_safe_warning(
        caplog,
        operation="stats",
        store_ref=STATS_STORE_REF,
        exc_type="RuntimeError",
    )


def _seed_rollup_database(
    database: Path,
    legacy_path: str,
    logical_ref: str,
) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
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
        rows = [
            (
                "2026-07-13T12:00:00+00:00",
                "faiss",
                "agent.reasoning",
                "embedding-modern",
                "scene-modern",
                "text",
                "fixture-model",
                0.25,
                json.dumps(
                    {
                        "store_ref": logical_ref,
                        "index_path": legacy_path,
                    }
                ),
            ),
            (
                "2026-07-13T12:01:00+00:00",
                "faiss",
                "agent.reasoning",
                "embedding-legacy",
                "scene-legacy",
                "text",
                "fixture-model",
                0.75,
                json.dumps({"index_path": legacy_path}),
            ),
        ]
        connection.executemany(
            """
            INSERT INTO retrieval_events(
              ts_utc, store, retrieval_context, embedding_id, scene_id,
              modality, model, score, details_json
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )


@pytest.mark.parametrize(
    "legacy_path, logical_ref",
    [
        (
            rf"C:\{PATH_CANARY}\nested\windows-memory.index",
            "windows-memory.index",
        ),
        (
            f"/srv/{PATH_CANARY}/nested/posix-memory.index",
            "posix-memory.index",
        ),
    ],
    ids=["windows", "posix"],
)
def test_rollup_normalizes_legacy_faiss_path_and_remains_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    legacy_path: str,
    logical_ref: str,
) -> None:
    database = tmp_path / "rollup.db"
    _seed_rollup_database(database, legacy_path, logical_ref)
    monkeypatch.setattr(
        observability_rollup,
        "_load_configs",
        lambda: ({"paths": {"db_path": str(database)}}, None),
    )

    assert observability_rollup.main([]) == 0
    with sqlite3.connect(database) as connection:
        derived = connection.execute(
            """
            SELECT store_ref, hits, score_count, score_sum, score_min, score_max,
                   last_event_id, last_ts_utc
            FROM retrieval_events_daily
            """
        ).fetchall()
        state = connection.execute(
            "SELECT last_event_id FROM observability_rollup_state WHERE key = ?",
            ("retrieval_events_daily",),
        ).fetchone()
        raw_details = [
            json.loads(row[0])
            for row in connection.execute(
                "SELECT details_json FROM retrieval_events ORDER BY id"
            ).fetchall()
        ]

    assert derived == [
        (
            logical_ref,
            2,
            2,
            pytest.approx(1.0),
            pytest.approx(0.25),
            pytest.approx(0.75),
            2,
            "2026-07-13T12:01:00+00:00",
        )
    ]
    assert state == (2,)
    assert raw_details[0]["index_path"] == legacy_path
    assert raw_details[1]["index_path"] == legacy_path

    assert observability_rollup.main([]) == 0
    with sqlite3.connect(database) as connection:
        after_second_run = connection.execute(
            """
            SELECT store_ref, hits, score_count, score_sum, score_min, score_max,
                   last_event_id, last_ts_utc
            FROM retrieval_events_daily
            """
        ).fetchall()
    assert after_second_run == derived


def test_rollup_limit_advances_state_and_then_merges_legacy_faiss_ref(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    logical_ref = "limited-memory.index"
    legacy_path = rf"C:\{PATH_CANARY}\limited\{logical_ref}"
    database = tmp_path / "limited-rollup.db"
    _seed_rollup_database(database, legacy_path, logical_ref)
    monkeypatch.setattr(
        observability_rollup,
        "_load_configs",
        lambda: ({"paths": {"db_path": str(database)}}, None),
    )

    assert observability_rollup.main(["--limit", "1"]) == 0
    with sqlite3.connect(database) as connection:
        first = connection.execute(
            "SELECT store_ref, hits, score_count, score_sum, last_event_id "
            "FROM retrieval_events_daily"
        ).fetchall()
        first_state = connection.execute(
            "SELECT last_event_id FROM observability_rollup_state WHERE key = ?",
            ("retrieval_events_daily",),
        ).fetchone()
    assert first == [(logical_ref, 1, 1, pytest.approx(0.25), 1)]
    assert first_state == (1,)

    assert observability_rollup.main(["--limit", "1"]) == 0
    with sqlite3.connect(database) as connection:
        completed = connection.execute(
            "SELECT store_ref, hits, score_count, score_sum, last_event_id "
            "FROM retrieval_events_daily"
        ).fetchall()
        completed_state = connection.execute(
            "SELECT last_event_id FROM observability_rollup_state WHERE key = ?",
            ("retrieval_events_daily",),
        ).fetchone()
    assert completed == [(logical_ref, 2, 2, pytest.approx(1.0), 2)]
    assert completed_state == (2,)


@pytest.mark.parametrize(
    "store, details, expected",
    [
        ("qdrant", {"collection": " collection-a "}, "collection-a"),
        (
            "qdrant",
            {"store_ref": " explicit-qdrant ", "collection": "ignored"},
            "explicit-qdrant",
        ),
        ("faiss", {"store_ref": " explicit-ref ", "index_path": "ignored"}, "explicit-ref"),
        ("faiss", {}, None),
        ("other", {"index_path": rf"C:\{PATH_CANARY}\ignored.index"}, None),
        ("faiss", None, None),
    ],
)
def test_store_ref_precedence_for_nonlegacy_inputs_is_preserved(
    store: str,
    details: Any,
    expected: str | None,
) -> None:
    assert observability_rollup._store_ref(store, details) == expected
