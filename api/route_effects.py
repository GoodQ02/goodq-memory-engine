from __future__ import annotations

from collections import Counter
from contextlib import asynccontextmanager
from enum import Enum
import ipaddress
import logging
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.responses import JSONResponse
from starlette.routing import Match, Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send


logger = logging.getLogger(__name__)


class RouteEffect(str, Enum):
    PASSIVE_READ = "passive_read"
    REQUEST_STAGING = "request_staging"
    AUTOMATIC_MUTATION = "automatic_mutation"
    CURATED_MUTATION = "curated_mutation"
    PROCESS_EXECUTION = "process_execution"


RouteOperation = tuple[str, str]
RouteGraphEntry = tuple[Any, type[Any], str, Any, tuple[str, ...], Any]


ROUTE_EFFECTS: dict[RouteOperation, RouteEffect] = {
    ("GET", "/"): RouteEffect.PASSIVE_READ,
    ("GET", "/api"): RouteEffect.PASSIVE_READ,
    ("POST", "/api/search/multimodal"): RouteEffect.AUTOMATIC_MUTATION,
    ("GET", "/api/search/text"): RouteEffect.AUTOMATIC_MUTATION,
    ("GET", "/api/search/visual"): RouteEffect.AUTOMATIC_MUTATION,
    ("POST", "/api/search/temporal"): RouteEffect.PASSIVE_READ,
    ("POST", "/api/search/temporal/summarize"): RouteEffect.PROCESS_EXECUTION,
    (
        "GET",
        "/api/search/temporal/summarize/{job_id}",
    ): RouteEffect.PASSIVE_READ,
    ("GET", "/api/videos/{video_id}/scenes"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/videos/{video_id}/scenes/{scene_id}"): RouteEffect.PASSIVE_READ,
    (
        "GET",
        "/api/videos/{video_id}/scenes/{scene_id}/similar",
    ): RouteEffect.AUTOMATIC_MUTATION,
    ("GET", "/api/videos/{video_id}/timeline"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/videos/{video_id}/timeline/full"): RouteEffect.PASSIVE_READ,
    (
        "GET",
        "/api/media/video/{video_id}/scene/{scene_id}/frame/{frame_index}",
    ): RouteEffect.PASSIVE_READ,
    ("GET", "/api/media/audio/{video_id}/{chunk_id}.wav"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/media/video/{video_id}/frame/{frame_name}"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/system/status"): RouteEffect.PROCESS_EXECUTION,
    ("GET", "/api/system/videos"): RouteEffect.PASSIVE_READ,
    ("POST", "/api/system/ingest"): RouteEffect.PASSIVE_READ,
    ("POST", "/api/system/reindex"): RouteEffect.PASSIVE_READ,
    ("POST", "/api/system/reload"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/system/identity/unstitched"): RouteEffect.AUTOMATIC_MUTATION,
    (
        "POST",
        "/api/system/identity/stitch/preview",
    ): RouteEffect.AUTOMATIC_MUTATION,
    ("POST", "/api/system/identity/stitch"): RouteEffect.CURATED_MUTATION,
    ("GET", "/api/system/identity/mappings"): RouteEffect.PASSIVE_READ,
    (
        "POST",
        "/api/system/identity/stitch/revoke",
    ): RouteEffect.CURATED_MUTATION,
    ("GET", "/api/summary/dashboard"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/summary/entity/{entity_id:path}"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/summary/collections"): RouteEffect.PASSIVE_READ,
    ("POST", "/api/summary/collections"): RouteEffect.CURATED_MUTATION,
    (
        "DELETE",
        "/api/summary/collections/{collection_id}",
    ): RouteEffect.CURATED_MUTATION,
    ("GET", "/api/summary/capabilities"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/summary/video/{video_hash}"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/summary/video/{video_hash}/status"): RouteEffect.PASSIVE_READ,
    (
        "POST",
        "/api/summary/video/{video_hash}/generate",
    ): RouteEffect.PROCESS_EXECUTION,
    ("POST", "/api/ingest/submit"): RouteEffect.REQUEST_STAGING,
    ("GET", "/api/ingest/status/{request_id}"): RouteEffect.PASSIVE_READ,
    ("HEAD", "/api/status"): RouteEffect.PROCESS_EXECUTION,
    ("GET", "/api/status"): RouteEffect.PROCESS_EXECUTION,
    ("GET", "/api/health/summary"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/engines"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/queue"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/storage/summary"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/gpu/stats"): RouteEffect.PROCESS_EXECUTION,
    ("GET", "/api/wsl2-status"): RouteEffect.PROCESS_EXECUTION,
    ("GET", "/api/models"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/runs/latest/preview"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/runs/latest/evidence"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/runs/audio-proof/latest"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/memory/stats"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/read/envelope"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/control-recurrence/reports"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/control-recurrence/reports/latest"): RouteEffect.PASSIVE_READ,
    ("GET", "/api/control-recurrence/reports/trend"): RouteEffect.PASSIVE_READ,
    (
        "GET",
        "/api/control-recurrence/reports/{report_id}",
    ): RouteEffect.PASSIVE_READ,
    (
        "GET",
        "/api/control-recurrence/reports/{report_id}/recommendations",
    ): RouteEffect.PASSIVE_READ,
    (
        "GET",
        "/api/control-recurrence/reports/{report_id}/markdown",
    ): RouteEffect.PASSIVE_READ,
    ("GET", "/api/identity/face-clusters"): RouteEffect.AUTOMATIC_MUTATION,
    (
        "POST",
        "/api/identity/rebuild-face-clusters",
    ): RouteEffect.PROCESS_EXECUTION,
    (
        "GET",
        "/api/identity/process-jobs/{job_id}",
    ): RouteEffect.PASSIVE_READ,
    (
        "POST",
        "/api/identity/face-clusters/label",
    ): RouteEffect.CURATED_MUTATION,
    ("GET", "/api/identity/speaker-clusters"): RouteEffect.AUTOMATIC_MUTATION,
    (
        "POST",
        "/api/identity/speaker-clusters/confirm",
    ): RouteEffect.CURATED_MUTATION,
    ("GET", "/api/identity/name-mentions"): RouteEffect.AUTOMATIC_MUTATION,
    ("GET", "/api/identity/roster"): RouteEffect.AUTOMATIC_MUTATION,
    ("POST", "/api/identity/roster/save"): RouteEffect.CURATED_MUTATION,
    ("POST", "/api/identity/roster/validate"): RouteEffect.PROCESS_EXECUTION,
    ("POST", "/api/identity/roster/export"): RouteEffect.CURATED_MUTATION,
    ("GET", "/docs"): RouteEffect.PASSIVE_READ,
    ("GET", "/redoc"): RouteEffect.PASSIVE_READ,
}


_STATIC_MOUNT_LAYOUT: dict[str, tuple[str, str]] = {
    "/ui/operator_console_v1": ("operator_console_v1", "operator_console_v1"),
    "/ui/retro_console_v1": ("retro_console_v1", "retro_console_v1"),
    "/ui/stitching_workbench": ("stitching_workbench", "stitching_workbench"),
    "/ui/identity_workbench": ("identity_workbench", "identity_workbench"),
    "/ui/summary_console": ("summary_console", "summary_console"),
    "/ui/justification_v1": ("justification_v1", "justification_v1"),
    "/ui/docs_static": ("docs_static", "docs_offline"),
}
_DEFAULT_UI_ROOT = Path(__file__).resolve().parents[1] / "ui"


def _expected_static_mounts_for_root(
    static_root: str | Path,
) -> dict[str, tuple[str, Path]]:
    resolved_root = Path(static_root).resolve()
    return {
        path: (name, (resolved_root / relative_directory).resolve())
        for path, (name, relative_directory) in _STATIC_MOUNT_LAYOUT.items()
    }


EXPECTED_STATIC_MOUNTS = _expected_static_mounts_for_root(_DEFAULT_UI_ROOT)
EXPECTED_FRAMEWORK_ROUTE_SIGNATURES: dict[
    str,
    tuple[str, frozenset[str], str],
] = {
    "/openapi.json": ("openapi", frozenset({"GET", "HEAD"}), "openapi"),
    "/docs": ("swagger_ui_html", frozenset({"GET", "HEAD"}), "swagger_ui_html"),
    "/docs/oauth2-redirect": (
        "swagger_ui_redirect",
        frozenset({"GET", "HEAD"}),
        "swagger_ui_redirect",
    ),
    "/redoc": ("redoc_html", frozenset({"GET", "HEAD"}), "redoc_html"),
}


def _framework_endpoint_codes() -> dict[str, Any]:
    reference_app = FastAPI()
    return {
        route.path: getattr(route.endpoint, "__code__", None)
        for route in reference_app.routes
        if type(route) is Route and route.path in EXPECTED_FRAMEWORK_ROUTE_SIGNATURES
    }


EXPECTED_FRAMEWORK_ENDPOINT_CODES = _framework_endpoint_codes()
_INSTALL_SENTINEL = "_goodq_route_effect_authority_installed"


class RouteEffectConfigurationError(RuntimeError):
    pass


def _normalize_registry(
    registry: Mapping[RouteOperation, RouteEffect | str],
) -> dict[RouteOperation, RouteEffect]:
    normalized: dict[RouteOperation, RouteEffect] = {}
    errors: list[str] = []
    for operation, raw_effect in registry.items():
        if (
            not isinstance(operation, tuple)
            or len(operation) != 2
            or not all(isinstance(value, str) and value for value in operation)
        ):
            errors.append(f"invalid operation key {operation!r}")
            continue
        method, path = operation
        key = (method.upper(), path)
        if key in normalized:
            errors.append(
                f"duplicate normalized registry operation {key[0]} {key[1]}"
            )
            continue
        try:
            normalized[key] = RouteEffect(raw_effect)
        except ValueError:
            errors.append(f"invalid effect for {method.upper()} {path}: {raw_effect!r}")
    if errors:
        raise RouteEffectConfigurationError("; ".join(errors))
    return normalized


def _format_operations(operations: Sequence[RouteOperation]) -> str:
    return ", ".join(f"{method} {path}" for method, path in operations)


def _route_graph_snapshot(routes: Sequence[Any]) -> tuple[RouteGraphEntry, ...]:
    snapshot: list[RouteGraphEntry] = []
    for route in routes:
        provenance = getattr(route, "endpoint", None)
        if provenance is None:
            provenance = getattr(route, "app", None)
        snapshot.append(
            (
                route,
                type(route),
                str(getattr(route, "path", "<unknown>")),
                getattr(route, "name", None),
                tuple(
                    sorted(
                        str(method).upper()
                        for method in getattr(route, "methods", None) or set()
                    )
                ),
                provenance,
            )
        )
    return tuple(snapshot)


def _route_graph_entry_label(entry: RouteGraphEntry) -> str:
    _route, route_type, path, _name, methods, _provenance = entry
    if methods:
        return _format_operations([(method, path) for method in methods])
    return f"{route_type.__name__} {path}"


def _validate_route_graph_unchanged(
    routes: Sequence[Any],
    *,
    expected: tuple[RouteGraphEntry, ...],
) -> None:
    current = _route_graph_snapshot(routes)
    changed: set[str] = set()
    for expected_entry, current_entry in zip(expected, current):
        if (
            expected_entry[0] is current_entry[0]
            and expected_entry[1] is current_entry[1]
            and expected_entry[2:5] == current_entry[2:5]
            and expected_entry[5] is current_entry[5]
        ):
            continue
        changed.add(_route_graph_entry_label(expected_entry))
        changed.add(_route_graph_entry_label(current_entry))
    for extra_entry in expected[len(current) :] + current[len(expected) :]:
        changed.add(_route_graph_entry_label(extra_entry))
    if changed:
        raise RouteEffectConfigurationError(
            "route graph changed from authorized installation: "
            + ", ".join(sorted(changed))
        )


def _infrastructure_route_error(
    route: Any,
    *,
    expected_static_mounts: Mapping[str, tuple[str, Path]],
) -> str | None:
    path = getattr(route, "path", "<unknown>")
    if isinstance(route, Mount):
        expected_mount = expected_static_mounts.get(path)
        actual_directory = None
        if type(route.app) is StaticFiles:
            actual_directory = Path(route.app.directory).resolve()
        if (
            type(route) is not Mount
            or expected_mount is None
            or route.name != expected_mount[0]
            or type(route.app) is not StaticFiles
            or actual_directory != expected_mount[1]
        ):
            return (
                f"Mount {path} has type={type(route).__name__} name={route.name!r} "
                f"app={type(route.app).__name__} directory={actual_directory!s}; "
                "expected the named canonical StaticFiles mount"
            )
        return None

    if isinstance(route, Route):
        expected = EXPECTED_FRAMEWORK_ROUTE_SIGNATURES.get(path)
        actual_methods = frozenset(method.upper() for method in route.methods or set())
        endpoint_name = getattr(route.endpoint, "__name__", None)
        endpoint_code = getattr(route.endpoint, "__code__", None)
        if (
            type(route) is not Route
            or expected is None
            or (route.name, actual_methods, endpoint_name) != expected
            or endpoint_code is not EXPECTED_FRAMEWORK_ENDPOINT_CODES.get(path)
        ):
            return (
                f"Route {path} has type={type(route).__name__} name={route.name!r} "
                f"methods={sorted(actual_methods)!r} endpoint={endpoint_name!r}; "
                "framework signature or endpoint provenance is not allowlisted"
            )
        return None

    return f"{type(route).__name__} {path}"


def validate_route_effect_registry(
    routes: Sequence[Any],
    *,
    registry: Mapping[RouteOperation, RouteEffect | str] = ROUTE_EFFECTS,
    static_root: str | Path = _DEFAULT_UI_ROOT,
) -> dict[RouteOperation, RouteEffect]:
    normalized = _normalize_registry(registry)
    expected_static_mounts = _expected_static_mounts_for_root(static_root)
    mounted: list[RouteOperation] = []
    infrastructure_routes: list[tuple[str, str]] = []
    unexpected_infrastructure: list[str] = []

    for route in routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or set()):
                mounted.append((method.upper(), route.path))
            continue
        infrastructure_routes.append(
            (type(route).__name__, str(getattr(route, "path", "<unknown>")))
        )
        infrastructure_error = _infrastructure_route_error(
            route,
            expected_static_mounts=expected_static_mounts,
        )
        if infrastructure_error is not None:
            unexpected_infrastructure.append(infrastructure_error)

    duplicate_operations = sorted(
        operation for operation, count in Counter(mounted).items() if count > 1
    )
    duplicate_infrastructure_routes = sorted(
        route_signature
        for route_signature, count in Counter(infrastructure_routes).items()
        if count > 1
    )
    mounted_set = set(mounted)
    missing = sorted(mounted_set - set(normalized))
    stale = sorted(set(normalized) - mounted_set)

    findings: list[str] = []
    if missing:
        findings.append(f"missing registry entries: {_format_operations(missing)}")
    if stale:
        findings.append(f"stale registry entries: {_format_operations(stale)}")
    if duplicate_operations:
        findings.append(
            "duplicate mounted operations: " + _format_operations(duplicate_operations)
        )
    if duplicate_infrastructure_routes:
        findings.append(
            "duplicate infrastructure routes: "
            + ", ".join(
                f"{route_type} {path}"
                for route_type, path in duplicate_infrastructure_routes
            )
        )
    if unexpected_infrastructure:
        findings.append(
            "unexpected infrastructure routes: "
            + ", ".join(sorted(unexpected_infrastructure))
        )
    if findings:
        raise RouteEffectConfigurationError("; ".join(findings))
    return normalized


def apply_route_effect_openapi(
    app: FastAPI,
    *,
    registry: Mapping[RouteOperation, RouteEffect | str] = ROUTE_EFFECTS,
) -> None:
    normalized = _normalize_registry(registry)
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.include_in_schema:
            continue
        effects = {
            normalized[(method.upper(), route.path)]
            for method in route.methods or set()
        }
        if len(effects) != 1:
            operations = sorted((method.upper(), route.path) for method in route.methods or set())
            raise RouteEffectConfigurationError(
                "one OpenAPI route object has multiple effects: "
                + _format_operations(operations)
            )
        effect = next(iter(effects))
        openapi_extra = dict(route.openapi_extra or {})
        existing = openapi_extra.get("x-goodq-effect")
        if existing is not None and existing != effect.value:
            raise RouteEffectConfigurationError(
                f"conflicting x-goodq-effect for {route.path}: {existing!r}"
            )
        openapi_extra["x-goodq-effect"] = effect.value
        route.openapi_extra = openapi_extra
    app.openapi_schema = None


def is_loopback_client(client: Any) -> bool:
    if not isinstance(client, (tuple, list)) or len(client) != 2:
        return False
    host, port = client
    if not isinstance(host, str) or not host.strip():
        return False
    if type(port) is not int or not 0 <= port <= 65535:
        return False
    try:
        address = ipaddress.ip_address(host.strip())
    except ValueError:
        return False
    if address.is_loopback:
        return True
    mapped = getattr(address, "ipv4_mapped", None)
    return bool(mapped and mapped.is_loopback)


class RouteEffectBoundaryMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        routes: Sequence[Any] | Callable[[], Sequence[Any]],
        registry: Mapping[RouteOperation, RouteEffect | str],
        static_root: str | Path = _DEFAULT_UI_ROOT,
    ) -> None:
        self.app = app
        if callable(routes):
            self._route_provider = routes
        else:
            self._route_provider = lambda: routes
        self.registry = _normalize_registry(registry)
        self.expected_static_mounts = _expected_static_mounts_for_root(static_root)

    def _match_operation(self, scope: Scope) -> tuple[RouteOperation | None, str | None]:
        method = str(scope.get("method") or "").upper()
        for route in self._route_provider():
            match, _child_scope = route.matches(scope)
            if match != Match.FULL:
                continue
            if isinstance(route, APIRoute):
                return (method, route.path), None
            infrastructure_error = _infrastructure_route_error(
                route,
                expected_static_mounts=self.expected_static_mounts,
            )
            return None, infrastructure_error
        return None, None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        operation, infrastructure_error = self._match_operation(scope)
        if infrastructure_error is not None:
            logger.error("API infrastructure route validation failed: %s", infrastructure_error)
            response = JSONResponse(
                {"detail": "API route infrastructure configuration is invalid"},
                status_code=500,
            )
            await response(scope, receive, send)
            return
        if operation is None:
            await self.app(scope, receive, send)
            return

        effect = self.registry.get(operation)
        if effect is None:
            logger.error(
                "API route effect configuration is incomplete for %s %s",
                operation[0],
                operation[1],
            )
            response = JSONResponse(
                {"detail": "API route effect configuration is incomplete"},
                status_code=500,
            )
            await response(scope, receive, send)
            return

        if effect != RouteEffect.PASSIVE_READ and not is_loopback_client(scope.get("client")):
            response = JSONResponse(
                {"detail": "Non-passive API operations are restricted to the local operator"},
                status_code=403,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


def install_route_effect_authority(
    app: FastAPI,
    *,
    registry: Mapping[RouteOperation, RouteEffect | str] = ROUTE_EFFECTS,
    static_root: str | Path = _DEFAULT_UI_ROOT,
) -> None:
    if getattr(app.state, _INSTALL_SENTINEL, False):
        raise RouteEffectConfigurationError("route effect authority is already installed")

    normalized = validate_route_effect_registry(
        app.routes,
        registry=registry,
        static_root=static_root,
    )
    apply_route_effect_openapi(app, registry=normalized)
    authorized_route_graph = _route_graph_snapshot(app.routes)

    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def route_effect_lifespan(app_instance: FastAPI):
        validate_route_effect_registry(
            app.routes,
            registry=normalized,
            static_root=static_root,
        )
        _validate_route_graph_unchanged(
            app.routes,
            expected=authorized_route_graph,
        )
        async with original_lifespan(app_instance) as state:
            validate_route_effect_registry(
                app.routes,
                registry=normalized,
                static_root=static_root,
            )
            _validate_route_graph_unchanged(
                app.routes,
                expected=authorized_route_graph,
            )
            yield state

    app.router.lifespan_context = route_effect_lifespan
    app.add_middleware(
        RouteEffectBoundaryMiddleware,
        routes=lambda: app.routes,
        registry=normalized,
        static_root=static_root,
    )
    setattr(app.state, _INSTALL_SENTINEL, True)
