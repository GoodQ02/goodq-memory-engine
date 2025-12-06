"""
Pydantic response models for GoodQ4All API.
Provides type-safe, validated response schemas for all endpoints.
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SceneResponse(BaseModel):
    """Scene metadata response."""
    scene_id: int
    start: float
    end: float
    duration: float
    representative_frame: Optional[str] = None
    frame_paths: List[str] = Field(default_factory=list)
    clip_id: Optional[str] = None
    dino_id: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    objects: List[str] = Field(default_factory=list)
    transcript: Optional[str] = None
    speakers: List[str] = Field(default_factory=list)
    audio_chunks: List[int] = Field(default_factory=list)


class SearchResult(BaseModel):
    """Search result with score and metadata."""
    score: float
    modality: str
    video_id: Optional[str] = None
    scene_id: Optional[int] = None
    timestamp: Optional[float] = None
    representative_frame: Optional[str] = None
    transcript: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    objects: List[str] = Field(default_factory=list)
    context: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModel):
    """Multimodal search response."""
    query: str
    total_results: int
    results: List[SearchResult]
    modalities_searched: List[str]
    fusion_weights: Optional[Dict[str, float]] = None


class TimelineSegment(BaseModel):
    """Timeline segment with all modalities."""
    segment_id: int
    start: float
    end: float
    scene_id: Optional[int] = None
    audio_chunks: List[int] = Field(default_factory=list)
    speaker_ids: List[str] = Field(default_factory=list)
    transcript: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    objects: List[str] = Field(default_factory=list)
    clip_id: Optional[str] = None
    dino_id: Optional[str] = None
    representative_frame: Optional[str] = None


class TimelineResponse(BaseModel):
    """Complete timeline for a video."""
    video_id: str
    duration: float
    total_scenes: int
    total_segments: int
    segments: List[TimelineSegment]
    metadata: Optional[Dict[str, Any]] = None


class VideoListItem(BaseModel):
    """Video list item with basic metadata."""
    video_id: str
    title: Optional[str] = None
    duration: Optional[float] = None
    total_scenes: Optional[int] = None
    processed_date: Optional[str] = None
    thumbnail: Optional[str] = None


class SystemStatus(BaseModel):
    """System status response."""
    status: str
    goodq_core_available: bool
    qdrant_available: bool
    total_videos_processed: int
    total_scenes_indexed: int
    indexes: Dict[str, Any] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    """Ingest job request."""
    file_path: str
    priority: Optional[int] = 0
    options: Optional[Dict[str, Any]] = None


class IngestResponse(BaseModel):
    """Ingest job response."""
    job_id: str
    status: str
    message: str
