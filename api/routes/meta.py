from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter(tags=["meta"])


@router.get("/")
def root() -> Dict[str, Any]:
    """Root endpoint (UI is not served from this API process)."""
    return {"status": "ok", "docs": "/docs", "openapi": "/openapi.json"}


@router.get("/api")
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
