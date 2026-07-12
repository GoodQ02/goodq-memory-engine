from __future__ import annotations

import asyncio
from collections import Counter
from contextlib import asynccontextmanager
import importlib
import re
import sys
import types
from pathlib import Path
from typing import Any, Mapping

import pytest
from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles


EXPECTED_ROUTE_EFFECTS: dict[tuple[str, str], str] = {
    ("GET", "/"): "passive_read",
    ("GET", "/api"): "passive_read",
    ("POST", "/api/search/multimodal"): "automatic_mutation",
    ("GET", "/api/search/text"): "automatic_mutation",
    ("GET", "/api/search/visual"): "automatic_mutation",
    ("POST", "/api/search/temporal"): "passive_read",
    ("POST", "/api/search/temporal/summarize"): "process_execution",
    ("GET", "/api/videos/{video_id}/scenes"): "passive_read",
    ("GET", "/api/videos/{video_id}/scenes/{scene_id}"): "passive_read",
    (
        "GET",
        "/api/videos/{video_id}/scenes/{scene_id}/similar",
    ): "automatic_mutation",
    ("GET", "/api/videos/{video_id}/timeline"): "passive_read",
    ("GET", "/api/videos/{video_id}/timeline/full"): "passive_read",
    (
        "GET",
        "/api/media/video/{video_id}/scene/{scene_id}/frame/{frame_index}",
    ): "passive_read",
    ("GET", "/api/media/audio/{video_id}/{chunk_id}.wav"): "passive_read",
    ("GET", "/api/media/video/{video_id}/frame/{frame_name}"): "passive_read",
    ("GET", "/api/system/status"): "process_execution",
    ("GET", "/api/system/videos"): "passive_read",
    ("POST", "/api/system/ingest"): "passive_read",
    ("POST", "/api/system/reindex"): "passive_read",
    ("POST", "/api/system/reload"): "passive_read",
    ("GET", "/api/system/identity/unstitched"): "automatic_mutation",
    ("POST", "/api/system/identity/stitch/preview"): "automatic_mutation",
    ("POST", "/api/system/identity/stitch"): "curated_mutation",
    ("GET", "/api/system/identity/mappings"): "passive_read",
    ("POST", "/api/system/identity/stitch/revoke"): "curated_mutation",
    ("GET", "/api/summary/dashboard"): "passive_read",
    ("GET", "/api/summary/entity/{entity_id:path}"): "passive_read",
    ("GET", "/api/summary/collections"): "passive_read",
    ("POST", "/api/summary/collections"): "curated_mutation",
    ("DELETE", "/api/summary/collections/{collection_id}"): "curated_mutation",
    ("GET", "/api/summary/capabilities"): "passive_read",
    ("GET", "/api/summary/video/{video_hash}"): "passive_read",
    ("GET", "/api/summary/video/{video_hash}/status"): "passive_read",
    ("POST", "/api/summary/video/{video_hash}/generate"): "process_execution",
    ("POST", "/api/ingest/submit"): "request_staging",
    ("GET", "/api/ingest/status/{request_id}"): "automatic_mutation",
    ("HEAD", "/api/status"): "process_execution",
    ("GET", "/api/status"): "process_execution",
    ("GET", "/api/health/summary"): "passive_read",
    ("GET", "/api/engines"): "passive_read",
    ("GET", "/api/queue"): "passive_read",
    ("GET", "/api/storage/summary"): "passive_read",
    ("GET", "/api/gpu/stats"): "process_execution",
    ("GET", "/api/wsl2-status"): "process_execution",
    ("GET", "/api/models"): "passive_read",
    ("GET", "/api/runs/latest/preview"): "passive_read",
    ("GET", "/api/runs/latest/evidence"): "passive_read",
    ("GET", "/api/runs/audio-proof/latest"): "passive_read",
    ("GET", "/api/memory/stats"): "passive_read",
    ("GET", "/api/read/envelope"): "passive_read",
    ("GET", "/api/control-recurrence/reports"): "passive_read",
    ("GET", "/api/control-recurrence/reports/latest"): "passive_read",
    ("GET", "/api/control-recurrence/reports/trend"): "passive_read",
    ("GET", "/api/control-recurrence/reports/{report_id}"): "passive_read",
    (
        "GET",
        "/api/control-recurrence/reports/{report_id}/recommendations",
    ): "passive_read",
    (
        "GET",
        "/api/control-recurrence/reports/{report_id}/markdown",
    ): "passive_read",
    ("GET", "/api/identity/face-clusters"): "automatic_mutation",
    ("POST", "/api/identity/rebuild-face-clusters"): "process_execution",
    ("POST", "/api/identity/face-clusters/label"): "curated_mutation",
    ("GET", "/api/identity/speaker-clusters"): "automatic_mutation",
    ("POST", "/api/identity/speaker-clusters/confirm"): "curated_mutation",
    ("GET", "/api/identity/name-mentions"): "automatic_mutation",
    ("GET", "/api/identity/roster"): "automatic_mutation",
    ("POST", "/api/identity/roster/save"): "curated_mutation",
    ("POST", "/api/identity/roster/validate"): "process_execution",
    ("POST", "/api/identity/roster/export"): "curated_mutation",
    ("GET", "/docs"): "passive_read",
    ("GET", "/redoc"): "passive_read",
}

EXPECTED_COUNTS = {
    "passive_read": 39,
    "request_staging": 1,
    "automatic_mutation": 11,
    "curated_mutation": 8,
    "process_execution": 9,
}


try:
    AUTHORITY = importlib.import_module("api.route_effects")
except ModuleNotFoundError:
    AUTHORITY = None


requires_authority = pytest.mark.skipif(
    AUTHORITY is None,
    reason="api.route_effects is not implemented yet",
)


def _normalized_effect(value: Any) -> str:
    return str(getattr(value, "value", value))


def _assert_effect_map_matches_expected(candidate: Mapping[tuple[str, str], Any]) -> None:
    normalized = {key: _normalized_effect(value) for key, value in candidate.items()}
    missing = sorted(set(EXPECTED_ROUTE_EFFECTS) - set(normalized))
    extra = sorted(set(normalized) - set(EXPECTED_ROUTE_EFFECTS))
    misclassified = sorted(
        (operation, EXPECTED_ROUTE_EFFECTS[operation], normalized[operation])
        for operation in set(EXPECTED_ROUTE_EFFECTS) & set(normalized)
        if EXPECTED_ROUTE_EFFECTS[operation] != normalized[operation]
    )
    assert not (missing or extra or misclassified), (
        f"route effect mismatch missing={missing} extra={extra} "
        f"misclassified={misclassified}"
    )


def _application_operations(app: FastAPI) -> set[tuple[str, str]]:
    return {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods or set()
    }


def _effect_registry() -> dict[tuple[str, str], Any]:
    assert AUTHORITY is not None
    return {
        operation: AUTHORITY.RouteEffect(effect)
        for operation, effect in EXPECTED_ROUTE_EFFECTS.items()
    }


def _sample_path(template: str) -> str:
    values = {
        "video_id": "video_001",
        "scene_id": "scene_001",
        "frame_index": "1",
        "chunk_id": "chunk_001",
        "frame_name": "frame.jpg",
        "entity_id": "person:operator",
        "collection_id": "collection_001",
        "video_hash": "a" * 32,
        "request_id": "ingest_20260712T000000Z_12345678",
        "report_id": "report_001",
    }

    def replace(match: re.Match[str]) -> str:
        return values[match.group(1)]

    return re.sub(r"\{([^}:]+)(?::path)?\}", replace, template)


def _scope(
    *,
    method: str,
    path: str,
    client: Any,
    headers: list[tuple[bytes, bytes]] | None = None,
) -> dict[str, Any]:
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "scheme": "http",
        "method": method,
        "root_path": "",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": headers or [],
        "client": client,
        "server": ("127.0.0.1", 30000),
        "state": {},
    }


async def _run_boundary(
    *,
    routes: list[Any],
    registry: Mapping[tuple[str, str], Any],
    scope: dict[str, Any],
) -> tuple[list[dict[str, Any]], int, int]:
    assert AUTHORITY is not None
    downstream_calls = 0
    receive_calls = 0
    messages: list[dict[str, Any]] = []

    async def downstream(inner_scope, receive, send):
        nonlocal downstream_calls
        downstream_calls += 1
        await JSONResponse({"ok": True})(inner_scope, receive, send)

    async def receive():
        nonlocal receive_calls
        receive_calls += 1
        raise AssertionError("boundary consumed the request body")

    async def send(message):
        messages.append(message)

    middleware = AUTHORITY.RouteEffectBoundaryMiddleware(
        downstream,
        routes=routes,
        registry=registry,
    )
    await middleware(scope, receive, send)
    return messages, downstream_calls, receive_calls


def _single_route_app(method: str, template: str) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    async def endpoint():
        return {"ok": True}

    app.add_api_route(
        template,
        endpoint,
        methods=[method],
        name=f"test_{method.lower()}_{len(app.routes)}",
    )
    return app


def test_route_effect_authority_module_exists() -> None:
    assert AUTHORITY is not None, "api.route_effects must implement the R-05 authority seam"


def test_live_route_inventory_matches_independent_expected_map() -> None:
    from api.main import app

    assert _application_operations(app) == set(EXPECTED_ROUTE_EFFECTS)
    assert Counter(EXPECTED_ROUTE_EFFECTS.values()) == Counter(EXPECTED_COUNTS)


def test_oracle_rejects_seeded_missing_operation() -> None:
    seeded = dict(EXPECTED_ROUTE_EFFECTS)
    seeded.pop(("GET", "/api/identity/roster"))

    with pytest.raises(AssertionError, match="missing=.*identity/roster"):
        _assert_effect_map_matches_expected(seeded)


def test_oracle_rejects_seeded_extra_operation() -> None:
    seeded = dict(EXPECTED_ROUTE_EFFECTS)
    seeded[("POST", "/api/unregistered")] = "curated_mutation"

    with pytest.raises(AssertionError, match="extra=.*api/unregistered"):
        _assert_effect_map_matches_expected(seeded)


def test_oracle_rejects_seeded_misclassification() -> None:
    seeded = dict(EXPECTED_ROUTE_EFFECTS)
    seeded[("GET", "/api/status")] = "passive_read"

    with pytest.raises(AssertionError, match="misclassified=.*api/status"):
        _assert_effect_map_matches_expected(seeded)


@requires_authority
def test_production_registry_matches_independent_expected_map() -> None:
    assert AUTHORITY is not None
    _assert_effect_map_matches_expected(AUTHORITY.ROUTE_EFFECTS)


@requires_authority
def test_registry_validator_rejects_missing_and_stale_entries() -> None:
    assert AUTHORITY is not None
    from api.main import app

    missing = dict(AUTHORITY.ROUTE_EFFECTS)
    missing.pop(("GET", "/api/identity/roster"))
    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="missing registry entries.*identity/roster",
    ):
        AUTHORITY.validate_route_effect_registry(app.routes, registry=missing)

    stale = dict(AUTHORITY.ROUTE_EFFECTS)
    stale[("POST", "/api/unregistered")] = AUTHORITY.RouteEffect.CURATED_MUTATION
    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="stale registry entries.*api/unregistered",
    ):
        AUTHORITY.validate_route_effect_registry(app.routes, registry=stale)


@requires_authority
def test_registry_validator_rejects_case_normalized_key_collision() -> None:
    assert AUTHORITY is not None
    app = _single_route_app("GET", "/same")

    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="duplicate normalized registry operation.*GET /same",
    ):
        AUTHORITY.validate_route_effect_registry(
            app.routes,
            registry={
                ("get", "/same"): AUTHORITY.RouteEffect.PASSIVE_READ,
                ("GET", "/same"): AUTHORITY.RouteEffect.CURATED_MUTATION,
            },
        )


@requires_authority
def test_registry_validator_rejects_new_unclassified_and_duplicate_routes() -> None:
    assert AUTHORITY is not None
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/new")
    async def new_route():
        return {"ok": True}

    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="missing registry entries.*GET /new",
    ):
        AUTHORITY.validate_route_effect_registry(app.routes, registry={})

    app.add_api_route("/new", new_route, methods=["GET"], name="new_route_duplicate")
    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="duplicate mounted operations.*GET /new",
    ):
        AUTHORITY.validate_route_effect_registry(
            app.routes,
            registry={("GET", "/new"): AUTHORITY.RouteEffect.PASSIVE_READ},
        )


@requires_authority
def test_registry_validator_rejects_unexpected_mount_and_websocket(tmp_path: Path) -> None:
    assert AUTHORITY is not None
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/unexpected", StaticFiles(directory=tmp_path), name="unexpected")

    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="unexpected infrastructure routes.*unexpected",
    ):
        AUTHORITY.validate_route_effect_registry(app.routes, registry={})

    websocket_app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @websocket_app.websocket("/socket")
    async def socket_endpoint(websocket):
        await websocket.close()

    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="unexpected infrastructure routes.*socket",
    ):
        AUTHORITY.validate_route_effect_registry(websocket_app.routes, registry={})


@requires_authority
def test_registry_validator_rejects_wrong_kind_at_allowlisted_infrastructure_paths(
    tmp_path: Path,
) -> None:
    assert AUTHORITY is not None

    async def endpoint(_request):
        return JSONResponse({"ok": True})

    wrong_framework_method = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    wrong_framework_method.router.routes.append(
        Route("/openapi.json", endpoint, methods=["POST"], name="openapi")
    )
    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="unexpected infrastructure routes.*openapi.json",
    ):
        AUTHORITY.validate_route_effect_registry(
            wrong_framework_method.routes,
            registry={},
        )

    dynamic_child = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    wrong_mount_app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    wrong_mount_app.mount(
        "/ui/docs_static",
        dynamic_child,
        name="docs_static",
    )
    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="unexpected infrastructure routes.*ui/docs_static",
    ):
        AUTHORITY.validate_route_effect_registry(wrong_mount_app.routes, registry={})

    wrong_mount_name = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    wrong_mount_name.mount(
        "/ui/docs_static",
        StaticFiles(directory=tmp_path),
        name="not_docs_static",
    )
    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="unexpected infrastructure routes.*ui/docs_static",
    ):
        AUTHORITY.validate_route_effect_registry(wrong_mount_name.routes, registry={})


@requires_authority
def test_registry_validator_binds_static_directory_and_framework_endpoint_provenance(
    tmp_path: Path,
) -> None:
    assert AUTHORITY is not None

    wrong_directory = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    wrong_directory.mount(
        "/ui/docs_static",
        StaticFiles(directory=tmp_path),
        name="docs_static",
    )
    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="unexpected infrastructure routes.*ui/docs_static",
    ):
        AUTHORITY.validate_route_effect_registry(wrong_directory.routes, registry={})

    async def replacement_endpoint(_request):
        return JSONResponse({"unexpected": True})

    replacement_endpoint.__name__ = "openapi"
    replaced_framework = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    replaced_framework.router.routes.append(
        Route(
            "/openapi.json",
            replacement_endpoint,
            methods=["GET"],
            name="openapi",
        )
    )
    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="unexpected infrastructure routes.*openapi.json",
    ):
        AUTHORITY.validate_route_effect_registry(replaced_framework.routes, registry={})


@requires_authority
def test_registry_validator_rejects_duplicate_canonical_static_mounts(
    tmp_path: Path,
) -> None:
    assert AUTHORITY is not None
    docs_static = tmp_path / "docs_offline"
    docs_static.mkdir()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    for _ in range(2):
        app.mount(
            "/ui/docs_static",
            StaticFiles(directory=docs_static),
            name="docs_static",
        )

    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="duplicate.*ui/docs_static",
    ):
        AUTHORITY.validate_route_effect_registry(
            app.routes,
            registry={},
            static_root=tmp_path,
        )


@requires_authority
def test_installer_validates_wires_one_boundary_and_enforces_both_effect_classes() -> None:
    assert AUTHORITY is not None
    invalid = _single_route_app("POST", "/unclassified")
    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="missing registry entries.*POST /unclassified",
    ):
        AUTHORITY.install_route_effect_authority(invalid, registry={})

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    calls = {"passive": 0, "mutate": 0}

    @app.get("/read")
    async def read_endpoint():
        calls["passive"] += 1
        return {"ok": True}

    @app.post("/mutate")
    async def mutate_endpoint(payload: dict[str, Any]):
        calls["mutate"] += 1
        return payload

    AUTHORITY.install_route_effect_authority(
        app,
        registry={
            ("GET", "/read"): AUTHORITY.RouteEffect.PASSIVE_READ,
            ("POST", "/mutate"): AUTHORITY.RouteEffect.CURATED_MUTATION,
        },
    )

    assert sum(
        middleware.cls is AUTHORITY.RouteEffectBoundaryMiddleware
        for middleware in app.user_middleware
    ) == 1

    with TestClient(app, client=("192.168.1.44", 50000)) as client:
        assert client.get("/read").status_code == 200
        assert client.post("/mutate", json={"secret": "body"}).status_code == 403

    assert calls == {"passive": 1, "mutate": 0}


@requires_authority
def test_installer_rejects_duplicate_authority_installation() -> None:
    assert AUTHORITY is not None
    app = _single_route_app("GET", "/read")
    registry = {("GET", "/read"): AUTHORITY.RouteEffect.PASSIVE_READ}

    AUTHORITY.install_route_effect_authority(app, registry=registry)
    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="route effect authority is already installed",
    ):
        AUTHORITY.install_route_effect_authority(app, registry=registry)

    assert sum(
        middleware.cls is AUTHORITY.RouteEffectBoundaryMiddleware
        for middleware in app.user_middleware
    ) == 1


@requires_authority
def test_installer_revalidates_routes_at_startup_and_fails_closed_after_startup() -> None:
    assert AUTHORITY is not None
    app = _single_route_app("GET", "/ok")
    AUTHORITY.install_route_effect_authority(
        app,
        registry={("GET", "/ok"): AUTHORITY.RouteEffect.PASSIVE_READ},
    )

    @app.post("/late")
    async def late_route():
        return {"unexpected": True}

    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="missing registry entries.*POST /late",
    ):
        with TestClient(app):
            pass

    runtime_app = _single_route_app("GET", "/ok")
    AUTHORITY.install_route_effect_authority(
        runtime_app,
        registry={("GET", "/ok"): AUTHORITY.RouteEffect.PASSIVE_READ},
    )
    runtime_client = TestClient(runtime_app, client=("192.168.1.44", 50000))
    assert runtime_client.get("/ok").status_code == 200

    @runtime_app.post("/late")
    async def runtime_late_route():
        return {"unexpected": True}

    assert runtime_client.post("/late").status_code == 500


@requires_authority
def test_invalid_preexisting_route_prevents_original_lifespan_side_effects() -> None:
    assert AUTHORITY is not None
    events: list[str] = []

    @asynccontextmanager
    async def original_lifespan(_app: FastAPI):
        events.append("enter")
        try:
            yield {"preserved": True}
        finally:
            events.append("exit")

    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=original_lifespan,
    )

    @app.get("/ok")
    async def ok_route():
        return {"ok": True}

    AUTHORITY.install_route_effect_authority(
        app,
        registry={("GET", "/ok"): AUTHORITY.RouteEffect.PASSIVE_READ},
    )

    @app.post("/late")
    async def late_route():
        return {"unexpected": True}

    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="missing registry entries.*POST /late",
    ):
        with TestClient(app):
            pass

    assert events == []


@requires_authority
def test_valid_original_lifespan_state_and_teardown_are_preserved() -> None:
    assert AUTHORITY is not None
    events: list[str] = []

    @asynccontextmanager
    async def original_lifespan(_app: FastAPI):
        events.append("enter")
        try:
            yield {"preserved": True}
        finally:
            events.append("exit")

    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=original_lifespan,
    )

    @app.get("/read")
    async def read_route(request: Request):
        return {"preserved": request.state.preserved}

    AUTHORITY.install_route_effect_authority(
        app,
        registry={("GET", "/read"): AUTHORITY.RouteEffect.PASSIVE_READ},
    )

    with TestClient(app, client=("192.168.1.44", 50000)) as client:
        assert events == ["enter"]
        assert client.get("/read").json() == {"preserved": True}

    assert events == ["enter", "exit"]


@requires_authority
def test_route_added_by_original_lifespan_is_revalidated_before_serving() -> None:
    assert AUTHORITY is not None
    events: list[str] = []

    async def added_route():
        return {"unexpected": True}

    @asynccontextmanager
    async def original_lifespan(app: FastAPI):
        events.append("enter")
        app.add_api_route("/added", added_route, methods=["POST"], name="added")
        try:
            yield
        finally:
            events.append("exit")

    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=original_lifespan,
    )

    @app.get("/ok")
    async def ok_route():
        return {"ok": True}

    AUTHORITY.install_route_effect_authority(
        app,
        registry={("GET", "/ok"): AUTHORITY.RouteEffect.PASSIVE_READ},
    )

    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="missing registry entries.*POST /added",
    ):
        with TestClient(app):
            pass

    assert events == ["enter", "exit"]


@requires_authority
def test_original_lifespan_cannot_replace_endpoint_at_authorized_operation() -> None:
    assert AUTHORITY is not None
    events: list[str] = []

    async def replacement_route():
        return {"unexpected": True}

    @asynccontextmanager
    async def original_lifespan(app: FastAPI):
        events.append("enter")
        app.router.routes.remove(original_api_route)
        app.add_api_route(
            "/read",
            replacement_route,
            methods=["GET"],
            name=original_api_route.name,
        )
        try:
            yield
        finally:
            events.append("exit")

    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=original_lifespan,
    )

    @app.get("/read")
    async def original_route():
        return {"ok": True}

    original_api_route = next(
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == "/read"
    )
    AUTHORITY.install_route_effect_authority(
        app,
        registry={("GET", "/read"): AUTHORITY.RouteEffect.PASSIVE_READ},
    )

    with pytest.raises(
        AUTHORITY.RouteEffectConfigurationError,
        match="route graph changed.*GET /read",
    ):
        with TestClient(app):
            pass

    assert events == ["enter", "exit"]


@requires_authority
def test_openapi_projects_every_effect_and_preserves_ingest_schema() -> None:
    assert AUTHORITY is not None
    from api.main import app

    schema = app.openapi()
    operations: list[dict[str, Any]] = []
    for path_item in schema["paths"].values():
        for method, operation in path_item.items():
            if method.lower() in {"get", "post", "put", "patch", "delete", "head", "options"}:
                operations.append(operation)

    assert len(operations) == 66
    assert all(operation.get("x-goodq-effect") in EXPECTED_COUNTS for operation in operations)

    submit_operation = schema["paths"]["/api/ingest/submit"]["post"]
    assert submit_operation["x-goodq-effect"] == "request_staging"
    assert "requestBody" in submit_operation
    assert "application/json" in submit_operation["requestBody"]["content"]


NONPASSIVE_OPERATIONS = sorted(
    operation
    for operation, effect in EXPECTED_ROUTE_EFFECTS.items()
    if effect != "passive_read"
)


@requires_authority
@pytest.mark.parametrize(("method", "template"), NONPASSIVE_OPERATIONS)
def test_remote_client_denied_before_body_or_downstream(
    method: str,
    template: str,
) -> None:
    app = _single_route_app(method, template)
    messages, downstream_calls, receive_calls = asyncio.run(
        _run_boundary(
            routes=app.routes,
            registry={
                (method, template): _effect_registry()[(method, template)],
            },
            scope=_scope(
                method=method,
                path=_sample_path(template),
                client=("192.168.1.44", 50000),
            ),
        )
    )

    start = next(message for message in messages if message["type"] == "http.response.start")
    assert start["status"] == 403
    assert downstream_calls == 0
    assert receive_calls == 0


@requires_authority
@pytest.mark.parametrize(
    ("operation", "client"),
    [
        (("POST", "/api/ingest/submit"), ("127.0.0.1", 50000)),
        (("POST", "/api/ingest/submit"), ("::1", 50000)),
        (("POST", "/api/ingest/submit"), ("::ffff:127.0.0.1", 50000)),
    ],
)
def test_loopback_client_variants_allow_effectful_operation(
    operation: tuple[str, str],
    client: tuple[str, int],
) -> None:
    method, template = operation
    app = _single_route_app(method, template)
    messages, downstream_calls, receive_calls = asyncio.run(
        _run_boundary(
            routes=app.routes,
            registry={operation: _effect_registry()[operation]},
            scope=_scope(method=method, path=_sample_path(template), client=client),
        )
    )

    start = next(message for message in messages if message["type"] == "http.response.start")
    assert start["status"] == 200
    assert downstream_calls == 1
    assert receive_calls == 0


@requires_authority
@pytest.mark.parametrize(
    "client",
    [
        None,
        (),
        ("127.0.0.1",),
        ["::1"],
        ("127.0.0.1", 50000, "extra"),
        ("", 50000),
        ("localhost", 50000),
        ("0.0.0.0", 50000),
        ("::", 50000),
        ("127.0.0.1", "50000"),
        ("127.0.0.1", True),
        ("127.0.0.1", -1),
        ("127.0.0.1", 65536),
    ],
)
def test_missing_or_malformed_client_is_nonlocal_for_effectful_operation(client: Any) -> None:
    operation = ("POST", "/api/ingest/submit")
    app = _single_route_app(*operation)
    messages, downstream_calls, receive_calls = asyncio.run(
        _run_boundary(
            routes=app.routes,
            registry={operation: _effect_registry()[operation]},
            scope=_scope(method=operation[0], path=operation[1], client=client),
        )
    )

    start = next(message for message in messages if message["type"] == "http.response.start")
    assert start["status"] == 403
    assert downstream_calls == 0
    assert receive_calls == 0


@requires_authority
@pytest.mark.parametrize(
    "operation",
    [
        ("GET", "/api/health/summary"),
        ("POST", "/api/search/temporal"),
    ],
)
def test_remote_client_can_reach_passive_get_and_post(operation: tuple[str, str]) -> None:
    method, template = operation
    app = _single_route_app(method, template)
    messages, downstream_calls, receive_calls = asyncio.run(
        _run_boundary(
            routes=app.routes,
            registry={operation: _effect_registry()[operation]},
            scope=_scope(
                method=method,
                path=_sample_path(template),
                client=("203.0.113.7", 50000),
            ),
        )
    )

    start = next(message for message in messages if message["type"] == "http.response.start")
    assert start["status"] == 200
    assert downstream_calls == 1
    assert receive_calls == 0


@requires_authority
def test_forwarded_headers_cannot_spoof_remote_client() -> None:
    operation = ("POST", "/api/ingest/submit")
    app = _single_route_app(*operation)
    messages, downstream_calls, receive_calls = asyncio.run(
        _run_boundary(
            routes=app.routes,
            registry={operation: _effect_registry()[operation]},
            scope=_scope(
                method=operation[0],
                path=operation[1],
                client=("192.168.1.44", 50000),
                headers=[
                    (b"host", b"127.0.0.1:30000"),
                    (b"origin", b"http://127.0.0.1:30000"),
                    (b"referer", b"http://127.0.0.1:30000/docs"),
                    (b"forwarded", b"for=127.0.0.1"),
                    (b"x-forwarded-for", b"127.0.0.1"),
                ],
            ),
        )
    )

    start = next(message for message in messages if message["type"] == "http.response.start")
    assert start["status"] == 403
    assert downstream_calls == 0
    assert receive_calls == 0


@requires_authority
def test_full_method_match_wins_after_partial_same_path_match() -> None:
    assert AUTHORITY is not None
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    async def endpoint():
        return {"ok": True}

    app.add_api_route("/same", endpoint, methods=["GET"], name="same_get")
    app.add_api_route("/same", endpoint, methods=["POST"], name="same_post")
    registry = {
        ("GET", "/same"): AUTHORITY.RouteEffect.PASSIVE_READ,
        ("POST", "/same"): AUTHORITY.RouteEffect.CURATED_MUTATION,
    }

    messages, downstream_calls, receive_calls = asyncio.run(
        _run_boundary(
            routes=app.routes,
            registry=registry,
            scope=_scope(method="POST", path="/same", client=("192.168.1.44", 50000)),
        )
    )

    start = next(message for message in messages if message["type"] == "http.response.start")
    assert start["status"] == 403
    assert downstream_calls == 0
    assert receive_calls == 0


@requires_authority
def test_explicit_effectful_options_route_is_not_confused_with_cors_preflight() -> None:
    assert AUTHORITY is not None
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    endpoint_calls = 0

    @app.options("/mutate")
    async def explicit_options():
        nonlocal endpoint_calls
        endpoint_calls += 1
        return {"unexpected": True}

    AUTHORITY.install_route_effect_authority(
        app,
        registry={("OPTIONS", "/mutate"): AUTHORITY.RouteEffect.CURATED_MUTATION},
    )

    with TestClient(app, client=("192.168.1.44", 50000)) as client:
        response = client.options("/mutate")

    assert response.status_code == 403
    assert endpoint_calls == 0


@requires_authority
def test_framework_404_405_redirect_and_cors_preflight_are_preserved() -> None:
    assert AUTHORITY is not None
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/items/")
    async def items():
        return {"ok": True}

    @app.post("/mutate")
    async def mutate():
        return {"ok": True}

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://example.test"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    AUTHORITY.install_route_effect_authority(
        app,
        registry={
            ("GET", "/items/"): AUTHORITY.RouteEffect.PASSIVE_READ,
            ("POST", "/mutate"): AUTHORITY.RouteEffect.CURATED_MUTATION,
        },
    )
    client = TestClient(app, client=("192.168.1.44", 50000))

    assert client.get("/missing").status_code == 404
    assert client.post("/items/").status_code == 405
    assert client.get("/items", follow_redirects=False).status_code == 307
    preflight = client.options(
        "/mutate",
        headers={
            "Origin": "http://example.test",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://example.test"


@requires_authority
def test_production_docs_openapi_and_static_mount_work_for_remote_client() -> None:
    from api.main import app

    with TestClient(app, client=("192.168.1.44", 50000)) as client:
        docs = client.get("/docs")
        redoc = client.get("/redoc")
        schema = client.get("/openapi.json")
        static = client.get("/ui/docs_static/swagger-ui.css")

    assert docs.status_code == 200
    assert "text/html" in docs.headers["content-type"]
    assert redoc.status_code == 200
    assert "text/html" in redoc.headers["content-type"]
    assert schema.status_code == 200
    assert schema.json()["info"]["title"] == "GoodQ Retrieval API"
    assert static.status_code == 200
    assert "text/css" in static.headers["content-type"]


def test_api_server_disables_proxy_header_rewriting_even_with_permissive_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.server as server

    captured: dict[str, Any] = {}
    fake_uvicorn = types.ModuleType("uvicorn")

    def fake_run(app, **kwargs):
        captured["app"] = app
        captured.update(kwargs)

    fake_uvicorn.run = fake_run
    fake_main = types.ModuleType("api.main")
    fake_main.app = object()

    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    monkeypatch.setitem(sys.modules, "api.main", fake_main)
    monkeypatch.setattr(server, "_resolve_api_bind_defaults", lambda: ("127.0.0.1", 30000))
    monkeypatch.setattr(server, "_find_available_port", lambda host, port: port)
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "*")

    server.main()

    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 30000
    assert captured["proxy_headers"] is False


def test_ingest_route_has_no_duplicate_client_locality_authority() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "api" / "routes" / "ingest.py").read_text(encoding="utf-8")

    assert "_require_loopback_client" not in source
