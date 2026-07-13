from __future__ import annotations

import ast
import importlib
import logging
from pathlib import Path
import sys
import types
from typing import Any, Iterator

import numpy as np
import pytest

from api import server as api_server
from retrieval.multimodal_search import MultimodalSearchEngine


REPO_ROOT = Path(__file__).resolve().parents[2]
SEARCH_SOURCE = REPO_ROOT / "retrieval" / "multimodal_search.py"
QUERY_CANARY = "PRIVATE_QUERY_CANARY_R05_F1_7D3A"
SELECTED_METHODS = {
    "search_text",
    "search_visual",
    "search_audio",
    "search_multimodal",
}


def _search_module():
    return importlib.import_module("retrieval.multimodal_search")


def _messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "retrieval.multimodal_search"
    ]


def _assert_safe_operation_log(
    caplog: pytest.LogCaptureFixture,
    *,
    operation: str,
    top_k: int,
) -> None:
    messages = _messages(caplog)
    rendered = "\n".join(messages)
    assert QUERY_CANARY not in rendered
    assert any(
        "retrieval_search" in message
        and f"operation={operation}" in message
        and f"top_k={top_k}" in message
        for message in messages
    )


def _selected_method_nodes(tree: ast.AST) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    selected: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in SELECTED_METHODS:
            selected[node.name] = node
    return selected


def test_selected_search_loggers_do_not_reference_query_parameter() -> None:
    source = SEARCH_SOURCE.read_text(encoding="utf-8")
    selected = _selected_method_nodes(ast.parse(source))
    assert set(selected) == SELECTED_METHODS

    violations: list[tuple[str, int]] = []
    for method_name, method in selected.items():
        for node in ast.walk(method):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != "logger":
                continue
            if node.func.attr not in {"debug", "info", "warning", "error", "exception", "critical"}:
                continue
            if any(isinstance(child, ast.Name) and child.id == "query" for child in ast.walk(node)):
                violations.append((method_name, node.lineno))

    assert violations == []


def test_text_search_preserves_encoder_and_fts_query_without_logging_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = object.__new__(MultimodalSearchEngine)
    calls: list[tuple[str, str, int | None]] = []

    def encode(query: str) -> np.ndarray:
        calls.append(("encoder", query, None))
        return np.zeros(1, dtype=np.float32)

    def search_fts(query: str, top_k: int = 5) -> list[dict[str, Any]]:
        calls.append(("fts", query, top_k))
        return []

    engine.encode_text_query = encode  # type: ignore[method-assign]
    engine.search_fts = search_fts  # type: ignore[method-assign]
    caplog.set_level(logging.INFO, logger="retrieval.multimodal_search")

    result = MultimodalSearchEngine.search_text(
        engine,
        QUERY_CANARY,
        top_k=2,
        retrieval_context="human.ui.search",
    )

    assert result == []
    assert calls == [
        ("encoder", QUERY_CANARY, None),
        ("fts", QUERY_CANARY, 20),
    ]
    _assert_safe_operation_log(caplog, operation="text", top_k=2)


def test_visual_search_preserves_encoder_query_without_logging_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = object.__new__(MultimodalSearchEngine)
    calls: list[str] = []

    def encode(query: str) -> np.ndarray:
        calls.append(query)
        return np.zeros(1, dtype=np.float32)

    engine.encode_text_for_visual_search = encode  # type: ignore[method-assign]
    caplog.set_level(logging.INFO, logger="retrieval.multimodal_search")

    result = MultimodalSearchEngine.search_visual(
        engine,
        QUERY_CANARY,
        top_k=3,
        retrieval_context="human.ui.search",
    )

    assert result == []
    assert calls == [QUERY_CANARY]
    _assert_safe_operation_log(caplog, operation="visual", top_k=3)


def test_audio_search_preserves_encoder_query_without_logging_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = object.__new__(MultimodalSearchEngine)
    calls: list[str] = []

    def encode(query: str) -> np.ndarray:
        calls.append(query)
        return np.zeros(1, dtype=np.float32)

    engine.encode_text_for_audio_search = encode  # type: ignore[method-assign]
    engine._set_search_diagnostic = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
    engine._audio_text_model_error_reason = None
    caplog.set_level(logging.INFO, logger="retrieval.multimodal_search")

    result = MultimodalSearchEngine.search_audio(
        engine,
        QUERY_CANARY,
        top_k=4,
        retrieval_context="human.ui.search",
    )

    assert result == []
    assert calls == [QUERY_CANARY]
    _assert_safe_operation_log(caplog, operation="audio", top_k=4)


def test_multimodal_search_preserves_every_selected_nested_query_without_logging_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = object.__new__(MultimodalSearchEngine)
    engine.weight_text = 1.0
    engine.weight_visual = 1.0
    engine.weight_audio = 1.0
    engine._reset_search_diagnostics = lambda: None  # type: ignore[method-assign]
    engine._fuse_scene_results = lambda _query, _results, top_k: []  # type: ignore[method-assign]
    calls: list[tuple[str, str, int, str]] = []

    def nested(operation: str):
        def search(
            query: str,
            top_k: int,
            *,
            retrieval_context: str,
        ) -> list[dict[str, Any]]:
            calls.append((operation, query, top_k, retrieval_context))
            return []

        return search

    engine.search_text = nested("text")  # type: ignore[method-assign]
    engine.search_visual = nested("visual")  # type: ignore[method-assign]
    engine.search_audio = nested("audio")  # type: ignore[method-assign]
    caplog.set_level(logging.INFO, logger="retrieval.multimodal_search")

    result = MultimodalSearchEngine.search_multimodal(
        engine,
        QUERY_CANARY,
        top_k=5,
        modalities=["text", "visual", "audio"],
        retrieval_context="agent.reasoning",
    )

    assert result == []
    assert calls == [
        ("text", QUERY_CANARY, 10, "agent.reasoning"),
        ("visual", QUERY_CANARY, 10, "agent.reasoning"),
        ("audio", QUERY_CANARY, 10, "agent.reasoning"),
    ]
    _assert_safe_operation_log(caplog, operation="multimodal", top_k=5)
    multimodal_messages = [
        message for message in _messages(caplog) if "operation=multimodal" in message
    ]
    assert len(multimodal_messages) == 1
    assert all(modality in multimodal_messages[0] for modality in ("text", "visual", "audio"))


@pytest.fixture
def installed_access_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[list[logging.Filter], dict[str, Any]]]:
    logger_names = ("uvicorn.access", "uvicorn", "uvicorn.error")
    original_filters = {
        name: list(logging.getLogger(name).filters)
        for name in logger_names
    }
    captured: dict[str, Any] = {}
    fake_uvicorn = types.ModuleType("uvicorn")

    def fake_run(app: Any, **kwargs: Any) -> None:
        captured["app"] = app
        captured.update(kwargs)

    fake_uvicorn.run = fake_run  # type: ignore[attr-defined]
    fake_main = types.ModuleType("api.main")
    fake_main.app = object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    monkeypatch.setitem(sys.modules, "api.main", fake_main)
    monkeypatch.setattr(api_server, "_resolve_api_bind_defaults", lambda: ("127.0.0.1", 30000))
    monkeypatch.setattr(api_server, "_find_available_port", lambda host, port: port)

    try:
        api_server.main()
        access_logger = logging.getLogger("uvicorn.access")
        added = [
            filter_obj
            for filter_obj in access_logger.filters
            if filter_obj not in original_filters["uvicorn.access"]
        ]
        assert len(added) == 1
        yield added, captured
    finally:
        for name, filters in original_filters.items():
            logging.getLogger(name).filters[:] = filters


def _render_access_record(filters: list[logging.Filter], target: str) -> str:
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:12345", "GET", target, "1.1", 200),
        None,
    )
    for filter_obj in filters:
        assert filter_obj.filter(record) is not False
    return record.getMessage()


@pytest.mark.parametrize(
    ("target", "forbidden", "expected_route", "expected_top_k", "secret_keys"),
    [
        (
            (
                f"/api/search/text?q={QUERY_CANARY}&top_k=2"
                "&token=token-value"
                "&session_token=session-value"
                "&api_key=api-key-value"
                "&auth_token=auth-value"
                "&password=password-value"
                "&secret=secret-value"
            ),
            (
                QUERY_CANARY,
                "token-value",
                "session-value",
                "api-key-value",
                "auth-value",
                "password-value",
                "secret-value",
            ),
            "/api/search/text",
            2,
            ("token", "session_token", "api_key", "auth_token", "password", "secret"),
        ),
        (
            "/api/search/visual?top_k=3&q=PRIVATE%20QUERY%20CANARY%20R05",
            ("PRIVATE%20QUERY%20CANARY%20R05", "PRIVATE QUERY CANARY R05"),
            "/api/search/visual",
            3,
            (),
        ),
        (
            "/api/search/text?q=FIRST_QUERY_CANARY&q=SECOND_QUERY_CANARY&top_k=4",
            ("FIRST_QUERY_CANARY", "SECOND_QUERY_CANARY"),
            "/api/search/text",
            4,
            (),
        ),
        (
            "/api/search/visual?Q=MIXED_CASE_QUERY_CANARY&top_k=5",
            ("MIXED_CASE_QUERY_CANARY",),
            "/api/search/visual",
            5,
            (),
        ),
    ],
)
def test_uvicorn_access_filter_redacts_every_query_value_and_preserves_audit_fields(
    installed_access_filters: tuple[list[logging.Filter], dict[str, Any]],
    target: str,
    forbidden: tuple[str, ...],
    expected_route: str,
    expected_top_k: int,
    secret_keys: tuple[str, ...],
) -> None:
    filters, captured = installed_access_filters
    rendered = _render_access_record(filters, target)

    assert all(value not in rendered for value in forbidden)
    assert "127.0.0.1:12345" in rendered
    assert f'"GET {expected_route}?' in rendered
    assert "HTTP/1.1" in rendered
    assert rendered.endswith('" 200')
    assert f"top_k={expected_top_k}" in rendered
    assert "q=redacted" in rendered.lower()
    for secret_key in secret_keys:
        assert f"{secret_key}=REDACTED" in rendered
    assert captured.get("access_log", True) is not False
    assert captured["proxy_headers"] is False
