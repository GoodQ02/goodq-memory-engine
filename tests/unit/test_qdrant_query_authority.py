from __future__ import annotations

import json
from typing import Any

import pytest

from steps.common.qdrant_client import QdrantClient, QdrantConfig
from steps.common.retrieval_events import RetrievalEventPolicy


class _Response:
    def __init__(self, status_code: int, payload: Any = None):
        self.status_code = status_code
        self._payload = {} if payload is None else payload
        self.text = json.dumps(self._payload)

    def json(self) -> Any:
        return self._payload


class _RecordingSession:
    def __init__(
        self,
        *,
        get: list[_Response | Exception] | None = None,
        post: list[_Response | Exception] | None = None,
        put: list[_Response | Exception] | None = None,
    ) -> None:
        self.calls: list[tuple[str, str]] = []
        self._responses = {
            "GET": list(get or []),
            "POST": list(post or []),
            "PUT": list(put or []),
        }

    def _respond(self, method: str, url: str) -> _Response:
        self.calls.append((method, url))
        responses = self._responses[method]
        if not responses:
            raise AssertionError(f"Unexpected {method} request: {url}")
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def get(self, url: str, **_kwargs: Any) -> _Response:
        return self._respond("GET", url)

    def post(self, url: str, **_kwargs: Any) -> _Response:
        return self._respond("POST", url)

    def put(self, url: str, **_kwargs: Any) -> _Response:
        return self._respond("PUT", url)


def _client(session: _RecordingSession) -> QdrantClient:
    client = QdrantClient(
        QdrantConfig(
            host="http://qdrant.invalid",
            collection="goodq_text",
            dim=3,
            retrieval_event_policy=RetrievalEventPolicy(enabled=False),
        )
    )
    client.session = session
    return client


def test_query_does_not_create_a_missing_collection() -> None:
    session = _RecordingSession(
        get=[_Response(404)],
        put=[_Response(200)],
        post=[_Response(200, {"result": []})],
    )

    assert _client(session).query(
        [0.0, 0.0, 0.0],
        top_k=1,
        retrieval_context="system.healthcheck",
    ) == []
    assert session.calls == [
        ("GET", "http://qdrant.invalid/collections/goodq_text"),
    ]


def test_query_retry_does_not_create_a_collection_that_disappeared(monkeypatch) -> None:
    monkeypatch.setattr("steps.common.qdrant_client.time.sleep", lambda _seconds: None)
    session = _RecordingSession(
        get=[_Response(200), _Response(404)],
        put=[_Response(200)],
        post=[_Response(500), _Response(200, {"result": []})],
    )

    assert _client(session).query(
        [0.0, 0.0, 0.0],
        top_k=1,
        retrieval_context="system.healthcheck",
    ) == []
    assert session.calls == [
        ("GET", "http://qdrant.invalid/collections/goodq_text"),
        (
            "POST",
            "http://qdrant.invalid/collections/goodq_text/points/search",
        ),
        ("GET", "http://qdrant.invalid/collections/goodq_text"),
    ]


def test_query_retries_indeterminate_collection_check_with_get_only(monkeypatch) -> None:
    monkeypatch.setattr("steps.common.qdrant_client.time.sleep", lambda _seconds: None)
    session = _RecordingSession(
        get=[ConnectionError("temporary collection check failure"), _Response(200)],
        post=[_Response(200, {"result": []})],
    )

    assert _client(session).query(
        [0.0, 0.0, 0.0],
        top_k=1,
        retrieval_context="system.healthcheck",
    ) == []
    assert session.calls == [
        ("GET", "http://qdrant.invalid/collections/goodq_text"),
        ("GET", "http://qdrant.invalid/collections/goodq_text"),
        (
            "POST",
            "http://qdrant.invalid/collections/goodq_text/points/search",
        ),
    ]


@pytest.mark.parametrize("strict", [False, True])
def test_query_existing_collection_preserves_hit_projection(strict: bool) -> None:
    session = _RecordingSession(
        get=[_Response(200)],
        post=[
            _Response(
                200,
                {
                    "result": [
                        {
                            "id": "point-1",
                            "score": 0.75,
                            "payload": {"scene_id": "scene-1"},
                        }
                    ]
                },
            )
        ],
    )

    assert _client(session).query(
        [0.0, 0.0, 0.0],
        top_k=1,
        retrieval_context="system.healthcheck",
        raise_on_error=strict,
    ) == [
        {
            "id": "point-1",
            "score": 0.75,
            "payload": {"scene_id": "scene-1"},
        }
    ]
    assert all(method != "PUT" for method, _url in session.calls)


def test_upsert_retains_explicit_missing_collection_creation() -> None:
    session = _RecordingSession(
        get=[_Response(404)],
        put=[_Response(200), _Response(200)],
    )

    assert _client(session).upsert(
        [{"id": 1, "vector": [0.0, 0.0, 0.0], "payload": {}}]
    ) is True
    assert session.calls == [
        ("GET", "http://qdrant.invalid/collections/goodq_text"),
        ("PUT", "http://qdrant.invalid/collections/goodq_text"),
        (
            "PUT",
            "http://qdrant.invalid/collections/goodq_text/points?wait=true",
        ),
    ]


@pytest.mark.parametrize("strict", [False, True])
def test_query_empty_success_is_not_a_backend_failure(strict: bool) -> None:
    session = _RecordingSession(
        get=[_Response(200)], post=[_Response(200, {"result": []})]
    )

    assert _client(session).query(
        [1.0, 0.0, 0.0],
        retrieval_context="human.ui.search",
        raise_on_error=strict,
    ) == []
    assert [method for method, _url in session.calls] == ["GET", "POST"]


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("disabled", "qdrant_disabled"),
        ("missing", "collection_unavailable"),
        ("collection_http_failure", "collection_unavailable"),
        ("collection_connection_failure", "collection_unavailable"),
        ("disappeared_on_retry", "collection_unavailable"),
        ("query_http_failure", "qdrant_query_failed"),
        ("query_connection_failure", "qdrant_query_failed"),
    ],
)
def test_query_strict_errors_preserve_legacy_empty_results(monkeypatch, strict, case, reason) -> None:
    monkeypatch.setattr("steps.common.qdrant_client.time.sleep", lambda _seconds: None)
    get_responses = [_Response(200), _Response(200)]
    post_responses = [_Response(500), _Response(500)]
    expected_methods = ["GET", "POST", "GET", "POST"]
    if case == "disabled":
        expected_methods = []
    elif case == "missing":
        get_responses = [_Response(404)]
        expected_methods = ["GET"]
    elif case == "collection_http_failure":
        get_responses = [_Response(503), _Response(503)]
        expected_methods = ["GET", "GET"]
    elif case == "collection_connection_failure":
        get_responses = [ConnectionError("offline"), ConnectionError("offline")]
        expected_methods = ["GET", "GET"]
    elif case == "disappeared_on_retry":
        get_responses = [_Response(200), _Response(404)]
        expected_methods = ["GET", "POST", "GET"]
    elif case == "query_connection_failure":
        post_responses = [ConnectionError("offline"), ConnectionError("offline")]
    session = _RecordingSession(get=get_responses, post=post_responses)
    client = _client(session)
    client.cfg.enabled = case != "disabled"

    if strict:
        with pytest.raises(RuntimeError, match=reason) as raised:
            client.query(
                [1.0, 0.0, 0.0],
                retrieval_context="human.ui.search",
                raise_on_error=True,
            )
        from steps.common.qdrant_client import QdrantQueryError

        assert isinstance(raised.value, QdrantQueryError)
        assert raised.value.reason == reason
    else:
        assert client.query(
            [1.0, 0.0, 0.0], retrieval_context="human.ui.search"
        ) == []
    assert [method for method, _url in session.calls] == expected_methods


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"result": None},
        {"result": {}},
        {"result": [None]},
        {"result": [{}]},
        {"result": [{"id": "point-1", "score": "invalid", "payload": {}}]},
        {"result": [{"id": "point-1", "score": float("nan"), "payload": {}}]},
        {"result": [{"id": "point-1", "score": 0.75, "payload": []}]},
    ],
)
def test_query_strict_rejects_malformed_success(payload) -> None:
    session = _RecordingSession(get=[_Response(200)], post=[_Response(200, payload)])

    with pytest.raises(RuntimeError, match="qdrant_response_invalid") as raised:
        _client(session).query(
            [1.0, 0.0, 0.0],
            retrieval_context="human.ui.search",
            raise_on_error=True,
        )
    from steps.common.qdrant_client import QdrantQueryError

    assert isinstance(raised.value, QdrantQueryError)
    assert raised.value.reason == "qdrant_response_invalid"
    assert [method for method, _url in session.calls] == ["GET", "POST"]


def test_query_strict_rejects_invalid_json() -> None:
    class InvalidJsonResponse(_Response):
        def json(self):
            raise ValueError("invalid JSON")

    session = _RecordingSession(
        get=[_Response(200)], post=[InvalidJsonResponse(200)]
    )

    with pytest.raises(RuntimeError, match="qdrant_response_invalid"):
        _client(session).query(
            [1.0, 0.0, 0.0],
            retrieval_context="human.ui.search",
            raise_on_error=True,
        )
    assert [method for method, _url in session.calls] == ["GET", "POST"]


def test_query_strict_recovers_through_existing_retry(monkeypatch) -> None:
    monkeypatch.setattr("steps.common.qdrant_client.time.sleep", lambda _seconds: None)
    session = _RecordingSession(
        get=[_Response(200), _Response(200)],
        post=[_Response(503), _Response(200, {"result": []})],
    )

    assert _client(session).query(
        [1.0, 0.0, 0.0],
        retrieval_context="human.ui.search",
        raise_on_error=True,
    ) == []
    assert [method for method, _url in session.calls] == ["GET", "POST", "GET", "POST"]
