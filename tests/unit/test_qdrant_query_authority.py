from __future__ import annotations

import json
from typing import Any

from steps.common.qdrant_client import QdrantClient, QdrantConfig


class _Response:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = json.dumps(self._payload)

    def json(self) -> dict[str, Any]:
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
            log_retrieval_events=False,
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

    assert _client(session).query([0.0, 0.0, 0.0], top_k=1) == []
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

    assert _client(session).query([0.0, 0.0, 0.0], top_k=1) == []
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

    assert _client(session).query([0.0, 0.0, 0.0], top_k=1) == []
    assert session.calls == [
        ("GET", "http://qdrant.invalid/collections/goodq_text"),
        ("GET", "http://qdrant.invalid/collections/goodq_text"),
        (
            "POST",
            "http://qdrant.invalid/collections/goodq_text/points/search",
        ),
    ]


def test_query_existing_collection_preserves_hit_projection() -> None:
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

    assert _client(session).query([0.0, 0.0, 0.0], top_k=1) == [
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
