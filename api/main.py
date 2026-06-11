from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

from api.routes import control_recurrence, ingest, media, meta, runtime, scenes, search, system, timeline, summary
from goodq_version import GOODQ_VERSION
from steps.common.config_loader import load_configs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GoodQ Retrieval API",
    version=GOODQ_VERSION,
    docs_url=None,
    redoc_url=None,
)
_CFG = load_configs({})
_API_CFG: Dict[str, Any] = _CFG.get("api", {}) or {}
_REPO_ROOT = Path(__file__).resolve().parents[1]
_UI_SUBDIR = _CFG.get("ui", {}).get("serve_from", "ui")
_OPERATOR_CONSOLE_DIR = _REPO_ROOT / _UI_SUBDIR / "operator_console_v1"
_RETRO_CONSOLE_DIR = _REPO_ROOT / _UI_SUBDIR / "retro_console_v1"
_STITCHING_WORKBENCH_DIR = _REPO_ROOT / _UI_SUBDIR / "stitching_workbench"
_SUMMARY_CONSOLE_DIR = _REPO_ROOT / _UI_SUBDIR / "summary_console"
_JUSTIFICATION_DIR = _REPO_ROOT / _UI_SUBDIR / "justification_v1"


def _resolve_allowed_origins() -> List[str]:
    override = str(os.environ.get("GOODQ_API_ALLOWED_ORIGINS") or "").strip()
    if override:
        origins = [item.strip() for item in override.split(",") if item.strip()]
        if origins:
            return origins
    return [
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:30000",
        "http://127.0.0.1:30000",
    ]


class UTF8JSONMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if response.headers.get("content-type", "").startswith("application/json"):
            response.headers["content-type"] = "application/json; charset=utf-8"
        return response


app.add_middleware(UTF8JSONMiddleware)

if bool(_API_CFG.get("cors_enabled", False)):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_resolve_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Mount canonical router-backed API surfaces.
app.include_router(meta.router)
app.include_router(search.router)
app.include_router(scenes.router)
app.include_router(timeline.router)
app.include_router(media.router)
app.include_router(system.router)
app.include_router(summary.router)
app.include_router(ingest.router)
app.include_router(runtime.router)
app.include_router(control_recurrence.router)

if _OPERATOR_CONSOLE_DIR.exists():
    app.mount(
        "/ui/operator_console_v1",
        StaticFiles(directory=str(_OPERATOR_CONSOLE_DIR), html=True),
        name="operator_console_v1",
    )

if _RETRO_CONSOLE_DIR.exists():
    app.mount(
        "/ui/retro_console_v1",
        StaticFiles(directory=str(_RETRO_CONSOLE_DIR), html=True),
        name="retro_console_v1",
    )

if _STITCHING_WORKBENCH_DIR.exists():
    app.mount(
        "/ui/stitching_workbench",
        StaticFiles(directory=str(_STITCHING_WORKBENCH_DIR), html=True),
        name="stitching_workbench",
    )

if _SUMMARY_CONSOLE_DIR.exists():
    app.mount(
        "/ui/summary_console",
        StaticFiles(directory=str(_SUMMARY_CONSOLE_DIR), html=True),
        name="summary_console",
    )

if _JUSTIFICATION_DIR.exists():
    app.mount(
        "/ui/justification_v1",
        StaticFiles(directory=str(_JUSTIFICATION_DIR), html=True),
        name="justification_v1",
    )

_DOCS_OFFLINE_DIR = _REPO_ROOT / _UI_SUBDIR / "docs_offline"
if _DOCS_OFFLINE_DIR.exists():
    app.mount(
        "/ui/docs_static",
        StaticFiles(directory=str(_DOCS_OFFLINE_DIR)),
        name="docs_static",
    )

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    if _DOCS_OFFLINE_DIR.exists():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url or "/openapi.json",
            title=app.title + " - Swagger UI",
            swagger_js_url="/ui/docs_static/swagger-ui-bundle.js",
            swagger_css_url="/ui/docs_static/swagger-ui.css",
            swagger_favicon_url="/ui/docs_static/favicon.ico",
        )
    return get_swagger_ui_html(
        openapi_url=app.openapi_url or "/openapi.json",
        title=app.title + " - Swagger UI",
    )

@app.get("/redoc", include_in_schema=False)
async def custom_redoc_html():
    if _DOCS_OFFLINE_DIR.exists():
        return get_redoc_html(
            openapi_url=app.openapi_url or "/openapi.json",
            title=app.title + " - ReDoc",
            redoc_js_url="/ui/docs_static/redoc.standalone.js",
            redoc_favicon_url="/ui/docs_static/favicon.ico",
        )
    return get_redoc_html(
        openapi_url=app.openapi_url or "/openapi.json",
        title=app.title + " - ReDoc",
    )

# Enforce CONFIG_LOADING_CONTRACT: reuse the already-loaded cfg in submodules.
# (api/routes/search.py lazily calls load_configs() otherwise; keep it lazy but non-reloading.)
try:
    search._config = _CFG  # type: ignore[attr-defined]
    search.load_configs = lambda overrides=None: _CFG  # type: ignore[assignment]
except Exception as e:
    logger.warning(f"Search route config injection failed: {e}")

try:
    from api.utils import loaders as api_loaders

    api_loaders.configure_from_cfg(_CFG)
except Exception as e:
    logger.warning(f"DataLoader config injection failed: {e}")


# Legacy UI/log static mounts intentionally disabled.
