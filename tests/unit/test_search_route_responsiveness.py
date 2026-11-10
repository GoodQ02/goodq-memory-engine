"""Production ASGI search boundaries must not monopolize API responsiveness."""
from __future__ import annotations

import asyncio
import threading

import anyio.to_thread
import httpx
import pytest

from api.main import app
from api.routes import search
from api.utils.response_models import SearchResult


async def _request(client, route, query="first"):
    if route == "multimodal":
        return await client.post(
            "/api/search/multimodal", json={"query": query, "modalities": ["visual"]}
        )
    return await client.get(f"/api/search/{route}", params={"q": query})


@pytest.fixture
def controlled_search(monkeypatch):
    """Replace compute/storage, leaving registration, middleware and handlers real."""
    entered = threading.Event()
    release = threading.Event()
    state = {"block": "search", "calls": [], "constructions": 0, "diagnostics": {},
             "additional_work": threading.Event()}

    def block_at(stage, query="first"):
        if state["block"] == stage and query == "first":
            entered.set()
            if not release.wait(10):
                raise TimeoutError("test did not release controlled search work")

    class Engine:
        weight_text = .5
        weight_visual = .4
        weight_audio = .1

        def __init__(self, cfg):
            state["constructions"] += 1
            if state["constructions"] > 1:
                state["additional_work"].set()
            block_at("initialize")

        def search_multimodal(self, query, **kwargs):
            return self.search_visual(query, **kwargs)

        def search_text(self, query, **kwargs):
            return self.search_visual(query, **kwargs)

        def search_visual(self, query, **kwargs):
            state["calls"].append(query)
            if query == "second":
                state["additional_work"].set()
            if query == "failed":
                raise RuntimeError("controlled retrieval failure")
            state["diagnostics"] = {"visual": {"status": "ready", "reason": query}}
            block_at("search", query)
            return [{"score": .9, "payload": {"scene_id": query}, "query": query}]

        def last_search_diagnostics(self):
            return state["diagnostics"]

        def _reset_search_diagnostics(self):
            state["diagnostics"] = {}

        def rank_visual_captions(self, query, results, captions):
            return results

        def encode_text_query(self, query):
            state["calls"].append("prewarm")
            block_at("prewarm")

        encode_text_for_visual_search = encode_text_query
        encode_text_for_audio_search = encode_text_query

    def project(result, modality=None, timeline_loader=None):
        assert timeline_loader is not None
        block_at("projection", result["query"])
        return SearchResult(
            score=result["score"], modality=modality or "visual",
            scene_id=result["query"], transcript=result["query"],
        )

    monkeypatch.setattr(search, "_config", {"identity_search": {"enabled": False}})
    monkeypatch.setattr(search, "_search_engine", None)
    monkeypatch.setattr(search, "MultimodalSearchEngine", Engine)
    monkeypatch.setattr(search, "_build_search_result", project)
    return state, entered, release


@pytest.mark.parametrize("route", ["multimodal", "text", "visual"])
@pytest.mark.parametrize("stage", ["initialize", "search", "projection"])
def test_health_responds_while_production_search_is_blocked(controlled_search, route, stage):
    state, entered, release = controlled_search
    state["block"] = stage
    # The external timer also releases the original blocking async handler so a
    # failing regression cannot leave this test process stuck on its event loop.
    failsafe = threading.Timer(5, release.set)
    failsafe.start()

    async def exercise():
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            request = asyncio.create_task(_request(client, route))
            try:
                assert await asyncio.to_thread(entered.wait, 3), "search never entered controlled work"
                response = await asyncio.wait_for(client.get("/"), timeout=2)
                assert response.status_code == 200
                assert response.json()["status"] == "ok"
                assert not release.is_set(), "health waited for blocked search work to finish"
                assert not request.done()
            finally:
                release.set()
                result = await request
            assert result.status_code == 200
            assert result.json()["results"][0]["scene_id"] == "first"

    try:
        asyncio.run(exercise())
    finally:
        release.set()
        failsafe.cancel()
        failsafe.join()


@pytest.mark.parametrize("second_route", ["multimodal", "text", "visual"])
@pytest.mark.parametrize("stage", ["initialize", "search", "projection"])
def test_searches_serialize_initialization_and_response_diagnostics(controlled_search, second_route, stage):
    state, entered, release = controlled_search
    state["block"] = stage

    async def exercise():
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = asyncio.create_task(_request(client, "multimodal"))
            second = None
            try:
                assert await asyncio.to_thread(entered.wait, 3)
                second = asyncio.create_task(_request(client, second_route, "second"))
                assert not await asyncio.to_thread(state["additional_work"].wait, .2)
                assert (await asyncio.wait_for(client.get("/"), 2)).status_code == 200
            finally:
                release.set()
                responses = await asyncio.gather(first, *([second] if second else []))
            assert len(responses) == 2
            assert all(response.status_code == 200 for response in responses)
            first_body, second_body = (response.json() for response in responses)
            assert first_body["diagnostics"]["visual"]["reason"] == "first"
            assert second_body["results"][0]["scene_id"] == "second"
            if second_route != "text":
                assert second_body["diagnostics"]["visual"]["reason"] == "second"
            assert state["constructions"] == 1
            assert state["calls"] == ["first", "second"]

    asyncio.run(exercise())


def test_prewarm_and_search_share_model_initialization_ownership(controlled_search):
    state, entered, release = controlled_search
    state["block"] = "prewarm"

    async def exercise():
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            warmup = asyncio.create_task(asyncio.to_thread(search.prewarm_search_engine))
            request = None
            try:
                assert await asyncio.to_thread(entered.wait, 3)
                request = asyncio.create_task(_request(client, "multimodal", "second"))
                assert not await asyncio.to_thread(state["additional_work"].wait, .2)
                assert (await asyncio.wait_for(client.get("/"), 2)).status_code == 200
            finally:
                release.set()
                results = await asyncio.gather(warmup, *([request] if request else []))
            assert results[0] == {"text": True, "visual": True, "audio": True}
            assert results[1].status_code == 200
            assert state["constructions"] == 1
            assert state["calls"] == ["prewarm", "prewarm", "prewarm", "second"]

    asyncio.run(exercise())


def test_failed_search_releases_ownership_for_next_request(controlled_search):
    state, _, _ = controlled_search
    state["block"] = None

    async def exercise():
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            failed = await _request(client, "multimodal", "failed")
            assert failed.status_code == 500
            response = await asyncio.wait_for(_request(client, "visual", "second"), 2)
            assert response.status_code == 200
            assert response.json()["diagnostics"]["visual"]["reason"] == "second"

    asyncio.run(exercise())


def test_queued_searches_leave_shared_api_worker_capacity_available(controlled_search):
    state, entered, release = controlled_search

    async def exercise():
        limiter = anyio.to_thread.current_default_thread_limiter()
        previous_tokens = limiter.total_tokens
        # A bounded capacity makes shared-pool starvation deterministic without
        # launching dozens of threads. Search must own its separate capacity.
        limiter.total_tokens = 1
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
        tasks = []
        try:
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                tasks.append(asyncio.create_task(_request(client, "multimodal")))
                try:
                    assert await asyncio.to_thread(entered.wait, 3)
                    for route in ("multimodal", "text", "visual"):
                        tasks.append(asyncio.create_task(_request(client, route, "second")))
                    health = await asyncio.wait_for(client.get("/"), 1)
                    assert health.status_code == 200
                    assert state["calls"] == ["first"]
                finally:
                    release.set()
                    responses = await asyncio.gather(*tasks)
                assert all(response.status_code == 200 for response in responses)
        finally:
            limiter.total_tokens = previous_tokens

    asyncio.run(exercise())


@pytest.mark.parametrize("ranking_status", ["fallback", "limited"])
def test_text_route_exposes_current_passage_ranking_diagnostics(monkeypatch, ranking_status):
    from tests.unit.test_hybrid_search_rrf import _passage_engine, _passage_hit

    hits = [_passage_hit(index, f"retained passage {index}")
            for index in range(33 if ranking_status == "limited" else 2)]
    engine, _ = _passage_engine(monkeypatch, hits, "raise" if ranking_status == "fallback" else None)
    engine._set_search_diagnostic("visual", status="unavailable", label="previous query", reason="previous")
    # Use the real search implementation and registered GET route. Only model,
    # vector transport and unrelated persisted-result hydration are replaced.
    monkeypatch.setattr(search, "get_search_engine", lambda: engine)
    monkeypatch.setattr(search, "get_data_loader", lambda: object())
    monkeypatch.setattr(search, "_build_search_result", lambda result, **kwargs: SearchResult(
        score=result["score"], modality="text", scene_id=result["payload"]["scene_id"],
    ))

    async def exercise():
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/search/text", params={"q": "unreported persistence"})
            assert response.status_code == 200
            body = response.json()
            assert body["results"][0]["scene_id"] == "scene-a"
            assert "visual" not in (body.get("diagnostics") or {})
            diagnostic = (body.get("diagnostics") or {}).get("text_passages")
            assert diagnostic is not None, "Supported text route dropped passage-ranking diagnostics"
            assert diagnostic["status"] == ranking_status
            assert diagnostic["reason"] == (
                "candidate_limit" if ranking_status == "limited" else "passage_encoding_failed"
            )
            hits[:] = [{"id": "scalar", "score": .9, "payload": {
                "scene_id": "scalar-scene", "text": "unchanged scalar transcript"}}]
            response = await client.get("/api/search/text", params={"q": "another query"})
            assert response.status_code == 200
            assert response.json()["results"][0]["scene_id"] == "scalar-scene"
            assert "text_passages" not in (response.json().get("diagnostics") or {})

    asyncio.run(exercise())
