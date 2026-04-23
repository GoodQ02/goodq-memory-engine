from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from api.routes import ingest, media, run_index, run_summary, runtime, scenes, search, system, timeline
from goodq_version import GOODQ_VERSION
from steps.common.config_loader import load_configs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GoodQ Retrieval API", version=GOODQ_VERSION)
_CFG = load_configs({})
_API_CFG: Dict[str, Any] = _CFG.get("api", {}) or {}


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
app.include_router(search.router)
app.include_router(scenes.router)
app.include_router(timeline.router)
app.include_router(media.router)
app.include_router(system.router)
app.include_router(ingest.router)
app.include_router(run_summary.router)
app.include_router(run_index.router)
app.include_router(runtime.router)

# Enforce CONFIG_LOADING_CONTRACT: reuse the already-loaded cfg in submodules.
# (api/routes/search.py lazily calls load_configs() otherwise; keep it lazy but non-reloading.)
try:
    search._config = _CFG  # type: ignore[attr-defined]
    search.load_configs = lambda overrides=None: _CFG  # type: ignore[assignment]
except Exception as e:
    logger.debug(f"Search route config injection failed: {e}")

try:
    from api.utils import loaders as api_loaders

    api_loaders.configure_from_cfg(_CFG)
except Exception as e:
    logger.debug(f"DataLoader config injection failed: {e}")


@app.get("/")
def root() -> Dict[str, Any]:
    """Root endpoint (UI is not served from this API process)."""
    return {"status": "ok", "docs": "/docs", "openapi": "/openapi.json"}


@app.get("/api")
def api_root() -> Dict[str, Any]:
    return {
        "status": "ok",
        "endpoints": [
            "/docs",
            "/openapi.json",
            "/api/status",
            "/api/engines",
            "/api/queue",
            "/api/search/multimodal",
            "/api/ingest/submit",
            "/api/videos/{video_id}/scenes",
            "/api/system/status",
        ],
    }


# Legacy UI/log static mounts intentionally disabled.
