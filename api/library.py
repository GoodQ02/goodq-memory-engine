"""Combine saved collections at the API boundary without moving their evidence.

The outer route-effect authority still governs every request. Backends must be
explicit loopback sources and attest the configured epoch on every response.
Combined catalogue/appearance reads may omit unreachable or attested 5xx sources;
the JSON x-goodq-unavailable-sources header lists their configured id/name pairs
(empty on a complete read). Payload shapes stay unchanged. Evidence conflicts
and explicitly selected source requests still fail; no fallback or writes occur.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlsplit

import httpx
from fastapi.routing import APIRoute
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Match

from scripts.config_schema import LibrarySourceConfig

SOURCE = "library_source"
EPOCH_HEADER = "x-goodq-source-epoch"
UNAVAILABLE_HEADER = "x-goodq-unavailable-sources"
RESPONSE_HEADERS = {
    "content-type", "content-length", "content-range", "accept-ranges",
    "etag", "last-modified", "cache-control", "retry-after", EPOCH_HEADER,
}


def merge_appearances(parts):
    result = copy.deepcopy(parts[0][1])
    result.update(epoch_id=None, scope="combined_saved_library", library_epochs=[], appearances=[])
    people = {}
    for source, data in parts:
        epoch = data["epoch_id"]
        result["library_epochs"].append(epoch)
        for person in data["people"]:
            people.setdefault(person["id"], {**person, "scene_count": 0, "observation_count": 0})
        for appearance in data["appearances"]:
            row = {**appearance, "epoch_id": epoch, SOURCE: source}
            result["appearances"].append(row)
            person = people[row["person_id"]]
            person["scene_count"] += 1
            person["observation_count"] += len(row.get("evidence") or [])
    result["people"] = list(people.values())
    result["summary"] = {
        "people": len(people), "appearances": len(result["appearances"]),
        "scenes": len({(r["epoch_id"], r["scene_id"]) for r in result["appearances"]}),
    }
    return result


class SavedLibraryMiddleware:
    def __init__(self, app, *, cfg, routes):
        self.app, self.routes = app, routes
        self.epoch = str(cfg.get("epoch_id") or Path(cfg["paths"]["db_path"]).parent.name)
        ui = cfg.get("ui") or {}
        self.port = ui.get("library_port", 30000)
        self.sources = {
            row.id: row for row in (
                LibrarySourceConfig.model_validate(item) for item in ui.get("library_sources", [])
            )
        }

    def known_route(self, scope):
        return any(isinstance(route, APIRoute) and route.matches(scope)[0] == Match.FULL
                   for route in self.routes())

    @staticmethod
    def check_epoch(response, source):
        if response.headers.get(EPOCH_HEADER) != source.epoch_id:
            raise ValueError(f"Saved collection {source.name} has a different or unavailable epoch")
        if 300 <= response.status_code < 400:
            raise ValueError(f"Saved collection {source.name} attempted a redirect")

    async def read_source(self, source, path, query):
        async with httpx.AsyncClient(timeout=30, trust_env=False, follow_redirects=False) as client:
            response = await client.get(source.api_origin + path, params=query,
                                        headers={"x-goodq-library-forwarded": "1"})
            self.check_epoch(response, source)
            response.raise_for_status()
            return response.json()

    async def aggregate(self, scope, receive, send, query):
        messages = []

        async def collect(message):
            messages.append(message)

        await self.app(scope, receive, collect)
        start = next(message for message in messages if message["type"] == "http.response.start")
        if start["status"] != 200:
            for message in messages:
                await send(message)
            return
        body = json.loads(b"".join(m.get("body", b"") for m in messages))
        path = scope["path"]
        parts = [("local", body)]
        unavailable = []
        for source in self.sources.values():
            try:
                data = await self.read_source(source, path, query)
            except httpx.RequestError:
                unavailable.append({"id": source.id, "name": source.name})
                continue
            except httpx.HTTPStatusError as error:
                if error.response.status_code < 500:
                    raise
                unavailable.append({"id": source.id, "name": source.name})
                continue
            if path.endswith("/appearances/saved") and data.get("epoch_id") != source.epoch_id:
                raise ValueError(f"Saved collection {source.name} returned mismatched appearance evidence")
            parts.append((source.id, data))
        if path == "/api/system/videos":
            result, seen = [], set()
            for source_id, videos in parts:
                source = self.sources.get(source_id)
                if source and {v["video_id"] for v in videos} != set(source.video_ids):
                    raise ValueError(f"Saved collection {source.name} changed its movie catalog")
                for video in videos:
                    if video["video_id"] in seen:
                        raise ValueError("Saved collections contain duplicate movie identifiers")
                    seen.add(video["video_id"])
                    result.append({**video, SOURCE: source_id,
                                   "epoch_id": source.epoch_id if source else self.epoch,
                                   "review_report_id": source.review_report_id if source else None})
        else:
            result = merge_appearances(parts)
        # Keep existing list/object payloads compatible. Partial results must be
        # explicit and never cached as a complete catalogue. Evidence conflicts
        # still raise above; only transport/attested server failures are omitted.
        await JSONResponse(result, headers={
            EPOCH_HEADER: "combined", UNAVAILABLE_HEADER: json.dumps(unavailable),
            "cache-control": "no-store",
        })(scope, receive, send)

    async def proxy(self, scope, receive, send, source, query):
        request = Request(scope, receive)
        if request.headers.get("x-goodq-library-forwarded"):
            raise ValueError("Nested saved-library forwarding is not allowed")
        origin = request.headers.get("origin")
        headers = {key: request.headers[key] for key in
                   ("content-type", "range", "if-range", "if-none-match", "if-modified-since")
                   if key in request.headers}
        if origin:
            supplied, current = urlsplit(origin), urlsplit(str(request.base_url))
            if (supplied.scheme, supplied.netloc) != (current.scheme, current.netloc):
                await JSONResponse({"detail": "Saved-library requests require the current origin"},
                                   status_code=403)(scope, receive, send)
                return
            headers["origin"] = source.api_origin
        headers.update({"x-goodq-library-forwarded": "1", "accept-encoding": "identity"})
        body = await request.body()
        if len(body) > 2 * 1024 * 1024:
            raise ValueError("Saved-library request exceeds the bounded review payload size")
        raw_path = (
            scope["raw_path"].decode("ascii").split("?", 1)[0]
            if scope.get("raw_path")
            else quote(scope["path"], safe="/")
        )
        async with httpx.AsyncClient(timeout=60, trust_env=False, follow_redirects=False) as client:
            async with client.stream(scope["method"], source.api_origin + raw_path,
                                     params=query, content=body, headers=headers) as response:
                self.check_epoch(response, source)
                await send({"type": "http.response.start", "status": response.status_code,
                            "headers": [(k.encode(), v.encode()) for k, v in response.headers.items()
                                        if k.lower() in RESPONSE_HEADERS]})
                async for chunk in response.aiter_bytes():
                    await send({"type": "http.response.body", "body": chunk, "more_body": True})
                await send({"type": "http.response.body", "body": b"", "more_body": False})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def local_send(message):
            if message["type"] == "http.response.start":
                message = dict(message)
                message["headers"] = list(message.get("headers", [])) + [
                    (EPOCH_HEADER.encode(), self.epoch.encode())]
            await send(message)

        enabled = scope.get("server", (None, None))[1] == self.port and self.sources
        if not enabled or not self.known_route(scope) or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, local_send)
            return
        query = parse_qsl(scope.get("query_string", b"").decode("utf-8"), keep_blank_values=True)
        selections = [v for k, v in query if k == SOURCE]
        query = [(k, v) for k, v in query if k != SOURCE]
        selected = selections[0] if len(selections) == 1 else None
        started = False

        async def tracked_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            if len(selections) > 1 or (selections and selected not in {"local", *self.sources}):
                raise ValueError("Unknown saved-library collection")
            path = scope["path"]
            video = None
            for prefix in ("/api/videos/", "/api/media/video/", "/api/media/audio/"):
                if path.startswith(prefix):
                    video = unquote(path[len(prefix):].split("/", 1)[0])
                    break
            owners = [s.id for s in self.sources.values() if video in s.video_ids] if video else []
            if len(owners) > 1 or (owners and selected and selected != owners[0]):
                raise ValueError("Movie and saved-library collection do not match")
            selected = selected or (owners[0] if owners else None)
            if selected and selected != "local":
                if path.startswith("/api/ingest/"):
                    raise ValueError("Ingestion is not a saved-library browsing action")
                await self.proxy(scope, receive, tracked_send, self.sources[selected], query)
            elif not selected and scope["method"] == "GET" and path in {
                "/api/system/videos", "/api/identity/appearances/saved"
            }:
                await self.aggregate(scope, receive, tracked_send, query)
            else:
                await self.app(scope, receive, local_send)
        except (ValueError, httpx.HTTPError) as error:
            if started:
                raise
            await JSONResponse({"detail": f"Combined library unavailable: {error}"},
                               status_code=409 if isinstance(error, ValueError) else 503)(scope, receive, send)
