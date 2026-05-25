"""
Summary API routes for GoodQ4All.
Provides dashboard, entity profile aggregation, and custom collections.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException, Path as PathParam, Body

from api.utils.response_models import (
    SummaryDashboardResponse,
    EntityProfileResponse,
    SavedCollectionItem,
    SaveCollectionRequest,
    SaveCollectionResponse
)
from api.utils.loaders import DataLoader
from lib import summary_aggregator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/summary", tags=["summary"])

_data_loader = None


def get_data_loader() -> DataLoader:
    """Lazy-load data loader."""
    global _data_loader
    if _data_loader is None:
        _data_loader = DataLoader()
    return _data_loader


def _get_kg_db_path() -> Path:
    from steps.common.config_loader import load_configs
    cfg = load_configs({})
    return Path(cfg.get("paths", {}).get("knowledge_graph_db", "data/knowledge_graph.db"))


@router.get("/dashboard", response_model=SummaryDashboardResponse)
async def get_dashboard():
    """
    Get consolidated dashboard metrics across all ingested videos/scenes.
    """
    db_path = _get_kg_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Database not found: {db_path}")
        
    try:
        loader = get_data_loader()
        data = summary_aggregator.get_summary_dashboard(db_path, loader)
        return data
    except Exception as e:
        logger.error(f"Failed to compile dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity_id:path}", response_model=EntityProfileResponse)
async def get_entity_profile(
    entity_id: str = PathParam(..., description="Stable entity identifier (e.g. 'person:Joe')")
):
    """
    Get detailed metrics, co-occurrences, and media timelines for a major entity.
    """
    db_path = _get_kg_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Database not found: {db_path}")
        
    try:
        loader = get_data_loader()
        data = summary_aggregator.get_entity_profile(db_path, loader, entity_id)
        return data
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to compile profile for {entity_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections", response_model=List[SavedCollectionItem])
async def list_collections():
    """
    List all active operator-saved collections.
    """
    db_path = _get_kg_db_path()
    try:
        data = summary_aggregator.load_collections(db_path)
        collections = data.get("collections") or []
        # Filter out deleted collections
        active_collections = [col for col in collections if col.get("status") == "active"]
        return active_collections
    except Exception as e:
        logger.error(f"Failed to list collections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collections", response_model=SaveCollectionResponse)
async def create_collection(request: SaveCollectionRequest = Body(...)):
    """
    Create a new manual playlist highlight collection.
    """
    db_path = _get_kg_db_path()
    try:
        req_dict = request.dict()
        new_col = summary_aggregator.add_collection(db_path, req_dict)
        return SaveCollectionResponse(
            success=True,
            message=f"Collection '{request.name}' successfully created.",
            collection=new_col
        )
    except Exception as e:
        logger.error(f"Failed to create collection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collections/{collection_id}", response_model=dict)
async def delete_collection(
    collection_id: str = PathParam(..., description="Unique ID of the collection to soft-delete")
):
    """
    Soft-delete a custom collection.
    """
    db_path = _get_kg_db_path()
    try:
        success = summary_aggregator.soft_delete_collection(db_path, collection_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Active collection not found for ID: {collection_id}")
        return {"success": True, "message": f"Collection '{collection_id}' was soft-deleted."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete collection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
