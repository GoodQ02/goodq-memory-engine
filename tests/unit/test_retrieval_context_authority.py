from __future__ import annotations

import asyncio
import ast
import inspect
import sys
import threading
import types
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pytest

from api.routes import search as search_routes
from retrieval.multimodal_search import MultimodalSearchEngine, multimodal_search
from steps.common import memory_provenance, memory_stores, retrieval_events
from steps.common.memory_router import MemoryRouter
from steps.common.memory_store import MemoryConfig, MemoryDims, MemoryStore
from steps.common.memory_stores import EphemeralMemory, FaissMemory, QdrantMemory
from steps.common.qdrant_client import QdrantClient, QdrantConfig
from steps.common.retrieval_events import RetrievalEventPolicy


REPO_ROOT = Path(__file__).resolve().parents[2]


def _policy() -> RetrievalEventPolicy:
    return RetrievalEventPolicy(enabled=False, jsonl_fallback=False)


def _read_tree(relative_path: str) -> ast.Module:
    path = REPO_ROOT / relative_path
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _named_receiver_calls(
    relative_path: str,
    *,
    receiver: str,
    method: str,
) -> list[ast.Call]:
    tree = _read_tree(relative_path)
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == method
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == receiver
    ]


def _keyword(call: ast.Call, name: str = "retrieval_context") -> ast.expr | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _reads_environment_key(node: ast.AST, key: str) -> bool:
    if isinstance(node, ast.Subscript):
        return (
            isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "os"
            and node.value.attr == "environ"
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == key
        )
    if not isinstance(node, ast.Call) or not node.args:
        return False
    first_arg = node.args[0]
    if not isinstance(first_arg, ast.Constant) or first_arg.value != key:
        return False
    if (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
        and node.func.attr == "getenv"
    ):
        return True
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and isinstance(node.func.value, ast.Attribute)
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == "os"
        and node.func.value.attr == "environ"
    )


class _ScopedCallVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scope: list[str] = []
        self.calls: list[tuple[str, ast.Call]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append((self.scope[-1] if self.scope else "<module>", node))
        self.generic_visit(node)


def _scoped_calls(relative_path: str) -> list[tuple[str, ast.Call]]:
    visitor = _ScopedCallVisitor()
    visitor.visit(_read_tree(relative_path))
    return visitor.calls


SIGNATURE_TARGETS: tuple[tuple[str, Callable[..., Any]], ...] = (
    ("memory_protocol", MemoryStore.query),
    ("memory_router", MemoryRouter.query),
    ("ephemeral", EphemeralMemory.query),
    ("faiss", FaissMemory.query),
    ("qdrant_wrapper", QdrantMemory.query),
    ("qdrant_client", QdrantClient.query),
    ("engine_text", MultimodalSearchEngine.search_text),
    ("engine_visual", MultimodalSearchEngine.search_visual),
    ("engine_audio", MultimodalSearchEngine.search_audio),
    ("engine_multimodal", MultimodalSearchEngine.search_multimodal),
    ("engine_similar_scene", MultimodalSearchEngine.search_similar_scene),
    ("callable_multimodal", multimodal_search),
)


@pytest.mark.parametrize(
    ("_label", "target"),
    SIGNATURE_TARGETS,
    ids=[item[0] for item in SIGNATURE_TARGETS],
)
def test_retrieval_context_is_required_keyword_only(
    _label: str,
    target: Callable[..., Any],
) -> None:
    parameter = inspect.signature(target).parameters.get("retrieval_context")

    assert parameter is not None
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty


FIXED_ORIGIN_CALLS: tuple[tuple[str, str, str, int, str], ...] = (
    ("api/routes/search.py", "engine", "search_multimodal", 1, "human.ui.search"),
    ("api/routes/search.py", "engine", "search_text", 1, "human.ui.search"),
    ("api/routes/search.py", "engine", "search_visual", 1, "human.ui.search"),
    ("api/routes/scenes.py", "engine", "search_similar_scene", 1, "human.ui.search"),
    ("agents/mini_agent_client.py", "q_client", "query", 1, "agent.reasoning"),
    ("cli/retrieve.py", "q_client", "query", 1, "human.cli.retrieve"),
    ("cli/test_ingestion.py", "engine", "search_multimodal", 1, "system.healthcheck"),
    (
        "scripts/ucf/generate_birth_certificate.py",
        "engine",
        "search_text",
        3,
        "system.healthcheck",
    ),
    ("cli/observability_health.py", "client", "query", 1, "system.healthcheck"),
)


@pytest.mark.parametrize(
    ("relative_path", "receiver", "method", "expected_count", "expected_context"),
    FIXED_ORIGIN_CALLS,
)
def test_fixed_origins_supply_literal_context(
    relative_path: str,
    receiver: str,
    method: str,
    expected_count: int,
    expected_context: str,
) -> None:
    calls = _named_receiver_calls(
        relative_path,
        receiver=receiver,
        method=method,
    )

    assert len(calls) == expected_count
    for call in calls:
        value = _keyword(call)
        assert isinstance(value, ast.Constant)
        assert value.value == expected_context


def test_engine_internal_calls_propagate_context_and_cli_origin_is_fixed() -> None:
    calls = _scoped_calls("retrieval/multimodal_search.py")

    client_queries = [
        call
        for _scope, call in calls
        if isinstance(call.func, ast.Attribute)
        and call.func.attr == "query"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "client"
    ]
    assert len(client_queries) == 3
    assert all(
        isinstance(_keyword(call), ast.Name)
        and _keyword(call).id == "retrieval_context"  # type: ignore[union-attr]
        for call in client_queries
    )

    nested = [
        call
        for scope, call in calls
        if scope in {"search_multimodal", "search_similar_scene"}
        and isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "self"
        and call.func.attr
        in {"search_text", "search_visual", "search_audio", "search_multimodal"}
    ]
    assert len(nested) == 4
    assert all(
        isinstance(_keyword(call), ast.Name)
        and _keyword(call).id == "retrieval_context"  # type: ignore[union-attr]
        for call in nested
    )

    public_calls = [
        (scope, call)
        for scope, call in calls
        if isinstance(call.func, ast.Attribute)
        and call.func.attr == "search_multimodal"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "engine"
    ]
    assert {scope for scope, _call in public_calls} == {"multimodal_search", "main"}
    by_scope = {scope: _keyword(call) for scope, call in public_calls}
    assert isinstance(by_scope["multimodal_search"], ast.Name)
    assert by_scope["multimodal_search"].id == "retrieval_context"  # type: ignore[union-attr]
    assert isinstance(by_scope["main"], ast.Constant)
    assert by_scope["main"].value == "human.cli.retrieve"  # type: ignore[union-attr]


def test_ambient_retrieval_context_authority_is_removed() -> None:
    env_lines = (REPO_ROOT / ".env.template").read_text(encoding="utf-8").splitlines()
    active_keys = {
        line.partition("=")[0].strip()
        for line in env_lines
        if line.strip() and not line.lstrip().startswith("#") and "=" in line
    }
    assert "GOODQ_RETRIEVAL_CONTEXT" not in active_keys

    production_roots = ("agents", "api", "cli", "retrieval", "scripts", "steps")
    offenders = sorted(
        f"{path.relative_to(REPO_ROOT).as_posix()}:{node.lineno}"
        for root_name in production_roots
        for path in (REPO_ROOT / root_name).rglob("*.py")
        for node in ast.walk(
            ast.parse(
                path.read_text(encoding="utf-8", errors="replace"),
                filename=str(path),
            )
        )
        if _reads_environment_key(node, "GOODQ_RETRIEVAL_CONTEXT")
    )
    assert offenders == []


def test_api_request_cannot_choose_retrieval_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert "retrieval_context" not in search_routes.MultimodalSearchRequest.model_fields
    request = search_routes.MultimodalSearchRequest.model_validate(
        {
            "query": "needle",
            "top_k": 2,
            "modalities": ["text"],
            "retrieval_context": "agent.reasoning",
        }
    )
    assert "retrieval_context" not in request.model_dump()
    assert not hasattr(request, "retrieval_context")

    calls: list[tuple[str, int, list[str] | None, str]] = []

    class FakeEngine:
        weight_text = 1.0
        weight_visual = 0.0
        weight_audio = 0.0

        def search_multimodal(
            self,
            *,
            query: str,
            top_k: int,
            modalities: list[str] | None,
            retrieval_context: str,
        ) -> list[dict[str, Any]]:
            calls.append((query, top_k, modalities, retrieval_context))
            return []

        @staticmethod
        def last_search_diagnostics() -> dict[str, Any]:
            return {}

    monkeypatch.setattr(search_routes, "get_search_engine", lambda: FakeEngine())

    response = asyncio.run(search_routes.search_multimodal(request))

    assert response.total_results == 0
    assert calls == [("needle", 2, ["text"], "human.ui.search")]


def _capture_events(
    captured: list[tuple[str, str]],
) -> Callable[..., None]:
    lock = threading.Lock()

    def capture(_db_path: str | None, events: Any, *, policy: Any) -> None:
        with lock:
            captured.extend(
                (threading.current_thread().name, event.retrieval_context)
                for event in events
            )

    return capture


def test_ephemeral_explicit_context_ignores_conflicting_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[str, str]] = []
    monkeypatch.setattr(memory_stores, "emit_retrieval_events", _capture_events(captured))
    monkeypatch.setenv("GOODQ_RETRIEVAL_CONTEXT", "agent.reasoning")
    store = EphemeralMemory(dim=2, retrieval_event_policy=_policy())
    assert store.insert(
        [{"id": "point-1", "vector": [1.0, 0.0], "payload": {"scene_id": "s-1"}}]
    )

    hits = store.query(
        [1.0, 0.0],
        top_k=1,
        retrieval_context="human.ui.search",
    )

    assert [hit["id"] for hit in hits] == ["point-1"]
    assert captured == [(threading.current_thread().name, "human.ui.search")]


@pytest.mark.parametrize("store_kind", ["ephemeral", "qdrant", "faiss"])
def test_invalid_explicit_context_retains_unknown_normalization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    store_kind: str,
) -> None:
    captured: list[tuple[str, str]] = []
    monkeypatch.setattr(memory_stores, "emit_retrieval_events", _capture_events(captured))
    monkeypatch.setattr(retrieval_events, "emit_retrieval_events", _capture_events(captured))
    monkeypatch.setattr(memory_provenance, "attach_provenance_to_hits", lambda *_args: None)
    monkeypatch.setenv("GOODQ_RETRIEVAL_CONTEXT", "agent.reasoning")

    if store_kind == "ephemeral":
        store: Any = EphemeralMemory(dim=2, retrieval_event_policy=_policy())
        assert store.insert(
            [
                {
                    "id": "point-1",
                    "vector": [1.0, 0.0],
                    "payload": {"scene_id": "s-1"},
                }
            ]
        )
    elif store_kind == "qdrant":
        store = QdrantClient(
            QdrantConfig(
                host="http://qdrant.invalid",
                collection="goodq_text",
                dim=2,
                retrieval_event_policy=_policy(),
            )
        )
        store._collection_ready = True

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

        store.session = types.SimpleNamespace(post=lambda *_args, **_kwargs: Response())
    else:
        index_path = tmp_path / "invalid-context.index"
        index_path.write_bytes(b"fake-index")

        class FakeIndex:
            @staticmethod
            def search(_query: Any, k: int):
                return (
                    np.array([[0.25]], dtype="float32"),
                    np.array([[7]], dtype="int64"),
                )

        monkeypatch.setitem(
            sys.modules,
            "faiss",
            types.SimpleNamespace(read_index=lambda _path: FakeIndex()),
        )
        store = FaissMemory(
            str(index_path),
            dim=2,
            retrieval_event_policy=_policy(),
        )

    store.query([1.0, 0.0], top_k=1, retrieval_context="not a valid context")

    assert captured == [(threading.current_thread().name, "unknown")]


def test_interleaved_shared_store_calls_keep_distinct_contexts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parameter = inspect.signature(EphemeralMemory.query).parameters.get(
        "retrieval_context"
    )
    if parameter is None:
        pytest.fail("explicit retrieval_context interface is absent")

    captured: list[tuple[str, str]] = []
    monkeypatch.setattr(memory_stores, "emit_retrieval_events", _capture_events(captured))
    monkeypatch.setenv("GOODQ_RETRIEVAL_CONTEXT", "system.healthcheck")
    store = EphemeralMemory(dim=2, retrieval_event_policy=_policy())
    assert store.insert(
        [{"id": "point-1", "vector": [1.0, 0.0], "payload": {"scene_id": "s-1"}}]
    )
    a_inside_query = threading.Event()
    release_a = threading.Event()
    errors: list[BaseException] = []
    original_purge_expired = store._purge_expired

    def gated_purge_expired() -> None:
        if threading.current_thread().name == "request-a":
            a_inside_query.set()
            assert release_a.wait(timeout=5)
        original_purge_expired()

    monkeypatch.setattr(store, "_purge_expired", gated_purge_expired)

    def request_a() -> None:
        try:
            store.query(
                [1.0, 0.0],
                top_k=1,
                retrieval_context="human.ui.search",
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    def request_b() -> None:
        try:
            store.query(
                [1.0, 0.0],
                top_k=1,
                retrieval_context="agent.reasoning",
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    thread_a = threading.Thread(name="request-a", target=request_a)
    thread_b = threading.Thread(name="request-b", target=request_b)
    thread_a.start()
    assert a_inside_query.wait(timeout=5)
    thread_b.start()
    thread_b.join(timeout=10)
    release_a.set()
    thread_a.join(timeout=10)

    assert not thread_a.is_alive()
    assert not thread_b.is_alive()
    assert errors == []
    assert sorted(captured) == [
        ("request-a", "human.ui.search"),
        ("request-b", "agent.reasoning"),
    ]


def test_qdrant_event_uses_explicit_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[str, str]] = []
    monkeypatch.setattr(retrieval_events, "emit_retrieval_events", _capture_events(captured))
    monkeypatch.setattr(memory_provenance, "attach_provenance_to_hits", lambda *_args: None)
    monkeypatch.setenv("GOODQ_RETRIEVAL_CONTEXT", "agent.reasoning")
    client = QdrantClient(
        QdrantConfig(
            host="http://qdrant.invalid",
            collection="goodq_text",
            dim=2,
            retrieval_event_policy=_policy(),
        )
    )
    client._collection_ready = True

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

    client.session = types.SimpleNamespace(post=lambda *_args, **_kwargs: Response())

    hits = client.query(
        [0.1, 0.2],
        top_k=1,
        retrieval_context="human.ui.search",
    )

    assert [hit["id"] for hit in hits] == ["q-1"]
    assert captured == [(threading.current_thread().name, "human.ui.search")]


def test_faiss_event_uses_explicit_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: list[tuple[str, str]] = []
    monkeypatch.setattr(retrieval_events, "emit_retrieval_events", _capture_events(captured))
    monkeypatch.setattr(memory_provenance, "attach_provenance_to_hits", lambda *_args: None)
    monkeypatch.setenv("GOODQ_RETRIEVAL_CONTEXT", "agent.reasoning")
    index_path = tmp_path / "text.index"
    index_path.write_bytes(b"fake-index")

    class FakeIndex:
        @staticmethod
        def search(_query: Any, k: int):
            return (
                np.array([[0.25]], dtype="float32"),
                np.array([[7]], dtype="int64"),
            )

    monkeypatch.setitem(
        sys.modules,
        "faiss",
        types.SimpleNamespace(read_index=lambda _path: FakeIndex()),
    )
    store = FaissMemory(
        str(index_path),
        dim=2,
        retrieval_event_policy=_policy(),
    )

    hits = store.query(
        [0.1, 0.2],
        top_k=1,
        retrieval_context="human.ui.search",
    )

    assert [hit["id"] for hit in hits] == [7]
    assert captured == [(threading.current_thread().name, "human.ui.search")]


def test_qdrant_wrapper_forwards_exact_context() -> None:
    class FakeClient:
        cfg = types.SimpleNamespace(dim=2, collection="goodq_text")

        def __init__(self) -> None:
            self.calls: list[
                tuple[list[float], int, dict[str, Any] | None, str]
            ] = []

        def query(
            self,
            vector: list[float],
            top_k: int = 5,
            payload_filter: dict[str, Any] | None = None,
            *,
            retrieval_context: str,
        ) -> list[dict[str, Any]]:
            self.calls.append((vector, top_k, payload_filter, retrieval_context))
            return [{"id": "q-1", "score": 0.9, "payload": {}}]

    client = FakeClient()
    store = QdrantMemory(client)  # type: ignore[arg-type]

    payload_filter = {"episode_id": "e-1"}
    hits = store.query(
        [0.1, 0.2],
        top_k=7,
        filter=payload_filter,
        retrieval_context="agent.reasoning",
    )

    assert [hit["id"] for hit in hits] == ["q-1"]
    assert client.calls == [([0.1, 0.2], 7, payload_filter, "agent.reasoning")]


def test_memory_router_forwards_exact_context() -> None:
    class FakeStore:
        dim = 2

        def __init__(self, name: str, hits: list[dict[str, Any]]) -> None:
            self.name = name
            self.hits = hits
            self.calls: list[
                tuple[list[float], int, dict[str, Any] | None, str]
            ] = []

        def query(
            self,
            vector: list[float],
            top_k: int = 5,
            filter: dict[str, Any] | None = None,
            *,
            retrieval_context: str,
        ) -> list[dict[str, Any]]:
            self.calls.append((vector, top_k, filter, retrieval_context))
            return self.hits

        def insert(self, _vectors: list[dict[str, Any]]) -> bool:
            return True

    stores = {
        "ephemeral": FakeStore("ephemeral", []),
        "faiss": FakeStore("faiss", []),
        "qdrant": FakeStore(
            "qdrant", [{"id": "q-1", "score": 0.9, "payload": {}}]
        ),
    }
    router = MemoryRouter(
        stores,  # type: ignore[arg-type]
        config=MemoryConfig(
            read_priority=["ephemeral", "faiss", "qdrant"],
            write_targets=[],
            dims=MemoryDims(text=2, image=2, audio=2),
        ),
    )

    payload_filter = {"episode_id": "e-1"}
    hits = router.query(
        [0.1, 0.2],
        top_k=7,
        filter=payload_filter,
        retrieval_context="agent.reasoning",
    )

    assert [hit["id"] for hit in hits] == ["q-1"]
    expected_call = ([0.1, 0.2], 7, payload_filter, "agent.reasoning")
    assert [store.calls for store in stores.values()] == [
        [expected_call],
        [expected_call],
        [expected_call],
    ]


def test_multimodal_fanout_forwards_one_exact_context() -> None:
    engine = object.__new__(MultimodalSearchEngine)
    engine.weight_text = 1.0
    engine.weight_visual = 1.0
    engine.weight_audio = 1.0
    engine._reset_search_diagnostics = lambda: None
    engine._fuse_scene_results = lambda _query, results, top_k: results[:top_k]
    engine._metadata_bonus = lambda _query, _payload: 0.0
    calls: list[tuple[str, str]] = []

    def fake_search(
        modality: str,
    ) -> Callable[..., list[dict[str, Any]]]:
        def search(
            _query: str,
            top_k: int,
            *,
            retrieval_context: str,
        ) -> list[dict[str, Any]]:
            calls.append((modality, retrieval_context))
            return [{"id": modality, "score": 1.0, "payload": {}}]

        return search

    engine.search_text = fake_search("text")  # type: ignore[method-assign]
    engine.search_visual = fake_search("visual")  # type: ignore[method-assign]
    engine.search_audio = fake_search("audio")  # type: ignore[method-assign]

    results = MultimodalSearchEngine.search_multimodal(
        engine,
        "query",
        top_k=3,
        modalities=["text", "visual", "audio"],
        retrieval_context="agent.reasoning",
    )

    assert len(results) == 3
    assert calls == [
        ("text", "agent.reasoning"),
        ("visual", "agent.reasoning"),
        ("audio", "agent.reasoning"),
    ]
