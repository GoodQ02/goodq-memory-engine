"""
Search API routes for GoodQ4All.
Provides multimodal search endpoints.
"""
from __future__ import annotations
from typing import List, Optional
import logging
from fastapi import APIRouter, Query, HTTPException, Body
from pydantic import BaseModel

from api.utils.response_models import SearchResponse, SearchResult
from api.utils.loaders import DataLoader
from goodq4all.retrieval.multimodal_search import MultimodalSearchEngine
from goodq4all.steps.common.config_loader import load_configs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])

# Global instances
_search_engine = None
_data_loader = None
_config = None


def get_search_engine():
    """Lazy-load search engine."""
    global _search_engine, _config
    
    if _search_engine is None:
        _config = load_configs({})
        _search_engine = MultimodalSearchEngine(_config)
        logger.info("✅ Search engine initialized")
    
    return _search_engine


def get_data_loader():
    """Lazy-load data loader."""
    global _data_loader
    
    if _data_loader is None:
        _data_loader = DataLoader()
        logger.info("✅ Data loader initialized")
    
    return _data_loader


class MultimodalSearchRequest(BaseModel):
    """Multimodal search request."""
    query: str
    top_k: int = 10
    modalities: Optional[List[str]] = None
    fusion_weights: Optional[dict] = None


@router.post("/multimodal", response_model=SearchResponse)
async def search_multimodal(request: MultimodalSearchRequest = Body(...)):
    """
    Unified multimodal search across text, visual, and audio.
    
    Args:
        request: Search request with query and options
        
    Returns:
        Ranked search results with scores and context
    """
    try:
        engine = get_search_engine()
        
        # Execute search
        results = engine.search_multimodal(
            query=request.query,
            top_k=request.top_k,
            modalities=request.modalities
        )
        
        # Convert to response format
        search_results = []
        for result in results:
            payload = result.get('payload', {})
            
            search_result = SearchResult(
                score=result.get('score', 0.0),
                modality=result.get('modality', 'unknown'),
                video_id=payload.get('video_id'),
                scene_id=payload.get('scene_id'),
                timestamp=payload.get('timestamp'),
                representative_frame=payload.get('representative_frame'),
                transcript=payload.get('transcript'),
                keywords=payload.get('keywords', []),
                objects=payload.get('objects', []),
                context=result.get('scene_context')
            )
            
            search_results.append(search_result)
        
        modalities_searched = request.modalities if request.modalities else ['text', 'visual']
        
        return SearchResponse(
            query=request.query,
            total_results=len(search_results),
            results=search_results,
            modalities_searched=modalities_searched,
            fusion_weights=request.fusion_weights or {
                'text': engine.weight_text,
                'visual': engine.weight_visual,
                'audio': engine.weight_audio
            }
        )
        
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/text", response_model=SearchResponse)
async def search_text(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(10, description="Number of results")
):
    """
    Text-only search across transcripts and captions.
    
    Args:
        q: Search query
        top_k: Number of results to return
        
    Returns:
        Search results from text modality
    """
    try:
        engine = get_search_engine()
        
        results = engine.search_text(q, top_k=top_k)
        
        search_results = []
        for result in results:
            payload = result.get('payload', {})
            
            search_result = SearchResult(
                score=result.get('score', 0.0),
                modality='text',
                video_id=payload.get('video_id'),
                scene_id=payload.get('scene_id'),
                transcript=payload.get('transcript'),
                keywords=payload.get('keywords', [])
            )
            
            search_results.append(search_result)
        
        return SearchResponse(
            query=q,
            total_results=len(search_results),
            results=search_results,
            modalities_searched=['text']
        )
        
    except Exception as e:
        logger.error(f"Text search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Text search failed: {str(e)}")


@router.get("/visual", response_model=SearchResponse)
async def search_visual(
    q: str = Query(..., description="Visual search query (text description)"),
    top_k: int = Query(10, description="Number of results")
):
    """
    Visual search using CLIP text-to-image similarity.
    
    Args:
        q: Text description of visual content
        top_k: Number of results to return
        
    Returns:
        Search results from visual modality
    """
    try:
        engine = get_search_engine()
        
        results = engine.search_visual(q, top_k=top_k)
        
        search_results = []
        for result in results:
            payload = result.get('payload', {})
            
            search_result = SearchResult(
                score=result.get('score', 0.0),
                modality='visual',
                video_id=payload.get('video_id'),
                scene_id=payload.get('scene_id'),
                representative_frame=payload.get('representative_frame'),
                objects=payload.get('objects', []),
                keywords=payload.get('keywords', [])
            )
            
            search_results.append(search_result)
        
        return SearchResponse(
            query=q,
            total_results=len(search_results),
            results=search_results,
            modalities_searched=['visual']
        )
        
    except Exception as e:
        logger.error(f"Visual search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Visual search failed: {str(e)}")
