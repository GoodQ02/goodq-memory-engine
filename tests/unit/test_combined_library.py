from __future__ import annotations

import json

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.responses import Response

from api.library import EPOCH_HEADER, SavedLibraryMiddleware, merge_appearances
from api.route_effects import ROUTE_EFFECTS, install_route_effect_authority
from scripts.config_schema import UIConfig


@pytest.fixture
def library(monkeypatch):
    source = dict(id="two", name="Movie two", api_origin="http://127.0.0.1:30041",
                  epoch_id="epoch_two", video_ids=["Two"])
    ui = UIConfig(serve_from="ui", library_sources=[source]).model_dump()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/api/system/videos")
    def videos():
        return [{"video_id": "One", "total_scenes": 141}]

    @app.get("/api/identity/appearances/saved")
    def appearances():
        return {"epoch_id": "epoch_one", "people": [{"id": "jose"}],
                "appearances": [{"person_id": "jose", "scene_id": "s1", "evidence": [{}]}]}

    @app.get("/api/videos/{video_id}/scenes")
    def scenes(video_id: str):
        return {"local": video_id, "scenes": [{"scene_id": "s1", "id": "s1",
                "start": 0, "end": 5, "summary": "Local saved scene", "entities": []}]}

    @app.get("/api/media/video/{video_id}/source")
    def media(video_id: str):
        return Response(b"local")

    @app.post("/api/search/multimodal")
    async def search(request: Request):
        return await request.json()

    @app.post("/api/media/desktop-player/play")
    def play():
        return {"local": True}

    requests = []
    behavior = {"epoch": "epoch_two", "offline": False, "status": 200}

    def respond(request):
        requests.append(request)
        if behavior["offline"]:
            raise httpx.ConnectError("source offline", request=request)
        headers = {EPOCH_HEADER: behavior["epoch"]}
        if behavior.get("timeout"):
            raise httpx.ReadTimeout("source timed out", request=request)
        if behavior["status"] != 200:
            return httpx.Response(behavior["status"], headers=headers, json={"detail": "failed"})
        if request.url.path == "/api/system/videos":
            return httpx.Response(200, headers=headers, json=[{"video_id": behavior.get("video", "Two"), "total_scenes": 129}])
        if request.url.path == "/api/identity/appearances/saved":
            return httpx.Response(200, headers=headers, json={
                "epoch_id": behavior.get("body_epoch", "epoch_two"), "people": [{"id": "jose"}],
                "appearances": [{"person_id": "jose", "scene_id": "s2", "evidence": [{}]}]})
        if request.url.path.endswith("/source"):
            headers.update({"content-type": "video/mp4", "content-range": "bytes 0-3/99"})
            return httpx.Response(206, headers=headers, stream=httpx.ByteStream(b"film"))
        return httpx.Response(200, headers=headers, json={"remote": True, "path": request.url.path})

    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    app.add_middleware(SavedLibraryMiddleware,
                       cfg={"paths": {"db_path": "/data/epoch_one/memory.db"}, "ui": ui},
                       routes=lambda: app.routes)
    operations = {(method, route.path) for route in app.routes for method in route.methods}
    install_route_effect_authority(app, registry={key: ROUTE_EFFECTS[key] for key in operations})
    return TestClient(app, base_url="http://127.0.0.1:30000"), requests, behavior


def test_one_catalog_contains_both_movies_and_preserves_epoch(library):
    client, requests, _ = library
    response = client.get("/api/system/videos")
    assert response.status_code == 200
    assert [(v["video_id"], v["epoch_id"], v["library_source"]) for v in response.json()] == [
        ("One", "epoch_one", "local"), ("Two", "epoch_two", "two")]
    assert len(requests) == 1


def test_video_route_uses_its_owner_and_range_is_streamed(library):
    client, requests, _ = library
    assert client.get("/api/videos/Two/scenes").json()["remote"]
    response = client.get("/api/media/video/Two/source", headers={"Range": "bytes=0-3"})
    assert response.status_code == 206 and response.content == b"film"
    assert response.headers["content-range"] == "bytes 0-3/99"
    assert requests[-1].headers["range"] == "bytes=0-3"


def test_search_payload_is_forwarded_without_ranking_or_query_changes(library):
    client, requests, _ = library
    payload = {"query": "fixed question", "modalities": ["text", "visual"], "top_k": 5}
    response = client.post("/api/search/multimodal?library_source=two", json=payload)
    assert response.status_code == 200
    assert json.loads(requests[-1].content) == payload
    assert not requests[-1].url.query


@pytest.mark.parametrize("path", ["/api/system/videos", "/api/videos/Two/scenes"])
def test_changed_epoch_never_falls_back_to_another_movie(library, path):
    client, _, behavior = library
    behavior["epoch"] = "wrong"
    assert client.get(path).status_code == 409


@pytest.mark.parametrize("failure", ["offline", "timeout", "server"])
def test_unavailable_collection_keeps_local_catalog_and_people_with_explicit_warning(library, failure):
    client, _, behavior = library
    behavior.update({"offline": failure == "offline", "timeout": failure == "timeout",
                     "status": 503 if failure == "server" else 200})
    for path in ("/api/system/videos", "/api/identity/appearances/saved"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers[EPOCH_HEADER] == "combined"
        assert json.loads(response.headers["x-goodq-unavailable-sources"]) == [
            {"id": "two", "name": "Movie two"}]
        assert response.headers["cache-control"] == "no-store"
        if path.endswith("/videos"):
            assert [(v["video_id"], v["library_source"], v["epoch_id"]) for v in response.json()] == [
                ("One", "local", "epoch_one")]
        else:
            assert response.json()["summary"] == {"people": 1, "appearances": 1, "scenes": 1}
            assert response.json()["library_epochs"] == ["epoch_one"]
    assert client.get("/api/videos/One/scenes?library_source=local").json()["local"] == "One"
    assert client.get("/api/media/video/One/source").content == b"local"
    assert client.post("/api/search/multimodal?library_source=local", json={"query": "local"}).json() == {"query": "local"}


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/videos/Two/scenes"),
    ("GET", "/api/media/video/Two/source"),
    ("GET", "/api/identity/appearances/saved?library_source=two"),
    ("POST", "/api/search/multimodal?library_source=two"),
    ("POST", "/api/media/desktop-player/play?library_source=two"),
])
def test_unavailable_explicit_source_never_uses_local_caller(library, method, path):
    client, requests, behavior = library
    behavior["offline"] = True
    response = client.request(method, path)
    assert response.status_code == 503
    assert len(requests) == 1 and requests[0].url.port == 30041


@pytest.mark.parametrize("change,path", [
    ({"epoch": "wrong"}, "/api/identity/appearances/saved"),
    ({"body_epoch": "wrong"}, "/api/identity/appearances/saved"),
    ({"video": "unexpected"}, "/api/system/videos"),
    ({"epoch": "wrong", "status": 503}, "/api/system/videos"),
])
def test_evidence_conflicts_are_not_downgraded_to_partial_success(library, change, path):
    client, _, behavior = library
    behavior.update(change)
    assert client.get(path).status_code == 409


def test_recovered_collection_returns_complete_results_and_clears_warning(library):
    client, _, behavior = library
    behavior["offline"] = True
    assert client.get("/api/system/videos").status_code == 200
    behavior["offline"] = False
    for path in ("/api/system/videos", "/api/identity/appearances/saved"):
        response = client.get(path)
        assert response.status_code == 200
        assert json.loads(response.headers["x-goodq-unavailable-sources"]) == []
        if path.endswith("/videos"):
            assert len(response.json()) == 2
        else:
            assert response.json()["summary"]["appearances"] == 2


@pytest.mark.parametrize("path", ["/api/videos/Two/scenes?library_source=local",
    "/api/videos/Two/scenes?library_source=missing",
    "/api/videos/Two/scenes?library_source=two&library_source=local"])
def test_bad_collection_selection_is_refused_without_forwarding(library, path):
    client, requests, _ = library
    assert client.get(path).status_code == 409
    assert not requests


def test_unknown_routes_cannot_be_used_as_an_open_proxy(library):
    client, requests, _ = library
    assert client.get("/api/unknown?library_source=two").status_code == 404
    assert not requests


def test_same_origin_desktop_intent_and_cross_origin_refusal(library):
    client, requests, _ = library
    url = "/api/media/desktop-player/play?library_source=two"
    assert client.post(url, json={}, headers={"Origin": "https://other.test"}).status_code == 403
    assert not requests
    assert client.post(url, json={}, headers={"Origin": "http://127.0.0.1:30000"}).status_code == 200
    assert requests[-1].headers["origin"] == "http://127.0.0.1:30041"


def test_combined_people_keep_exact_source_provenance():
    def saved(epoch, count):
        return {"epoch_id": epoch, "people": [{"id": "jose", "display_name": "Jose"}],
                "appearances": [{"person_id": "jose", "scene_id": str(i), "evidence": [{}]}
                                for i in range(count)]}
    result = merge_appearances([("local", saved("one", 4)), ("two", saved("two", 3))])
    assert result["people"][0]["scene_count"] == 7
    assert result["summary"] == {"people": 1, "appearances": 7, "scenes": 7}
    assert result["epoch_id"] is None
    assert result["appearances"][-1]["epoch_id"] == "two"
    assert result["appearances"][-1]["library_source"] == "two"


@pytest.mark.parametrize("origin", ["https://example.com", "http://127.0.0.1:30000",
                                   "http://127.0.0.1:30041/path", "http://user@127.0.0.1:30041"])
def test_only_explicit_nonrecursive_local_sources_are_allowed(origin):
    with pytest.raises(ValidationError):
        UIConfig(serve_from="ui", library_sources=[dict(id="two", name="Two", api_origin=origin,
                                                       epoch_id="two", video_ids=["Two"])])
