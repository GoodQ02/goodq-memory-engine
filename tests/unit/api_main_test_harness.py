from __future__ import annotations

import ast
import sys
import types
from collections.abc import Mapping, Sequence
from pathlib import Path

from fastapi import APIRouter


API_MAIN_ROUTER_NAMES = (
    "control_recurrence",
    "identity",
    "ingest",
    "media",
    "meta",
    "runtime",
    "scenes",
    "search",
    "system",
    "timeline",
    "summary",
)
API_MAIN_ROUTE_MODULE_NAMES = (
    "api.routes",
    *(f"api.routes.{name}" for name in API_MAIN_ROUTER_NAMES),
)


def _required_api_main_router_names(repo_root: Path) -> tuple[str, ...]:
    module_path = repo_root / "api" / "main.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    names = tuple(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "api.routes"
        for alias in node.names
    )
    if not names:
        raise AssertionError("api.main has no 'from api.routes import ...' router inventory")
    return names


def assert_api_main_router_inventory(
    repo_root: Path,
    synthetic_router_names: Sequence[str] = API_MAIN_ROUTER_NAMES,
) -> None:
    required = set(_required_api_main_router_names(repo_root))
    synthetic = set(synthetic_router_names)
    missing = sorted(required - synthetic)
    stale = sorted(synthetic - required)
    if missing or stale:
        details = []
        if missing:
            details.append(f"missing synthetic routers: {missing}")
        if stale:
            details.append(f"stale synthetic routers: {stale}")
        raise AssertionError("api.main router harness truth mismatch: " + "; ".join(details))


def install_api_main_router_stubs(
    repo_root: Path,
    *,
    real_router_modules: Mapping[str, types.ModuleType] | None = None,
    synthetic_router_names: Sequence[str] = API_MAIN_ROUTER_NAMES,
) -> None:
    assert_api_main_router_inventory(repo_root, synthetic_router_names)

    real_router_modules = real_router_modules or {}
    routes_package = types.ModuleType("api.routes")
    route_modules: dict[str, types.ModuleType] = {}
    for name in synthetic_router_names:
        module = real_router_modules.get(name)
        if module is None:
            module = types.ModuleType(f"api.routes.{name}")
            module.router = APIRouter()
        if name == "search" and not hasattr(module, "configure_search_from_cfg"):
            module.configure_search_from_cfg = lambda cfg: None
        setattr(routes_package, name, module)
        route_modules[name] = module

    for name, module in route_modules.items():
        sys.modules[f"api.routes.{name}"] = module
    sys.modules["api.routes"] = routes_package
