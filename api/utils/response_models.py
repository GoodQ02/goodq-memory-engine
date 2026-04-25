"""
Pydantic response models for GoodQ4All API.
Provides type-safe, validated response schemas for all endpoints.
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

SceneId = int | str


def default_confidence_payload() -> Dict[str, Any]:
    return {
        "intrinsic": None,
        "source": None,
        "temporal": None,
        "consistency": None,
        "overall": None,
    }


class SceneResponse(BaseModel):
    """Scene metadata response."""
    scene_id: SceneId
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
    speaker_count: Optional[int] = None
    dominant_speaker_id: Optional[str] = None
    continuity_key: Optional[str] = None
    diarization_status: Optional[str] = None
    emotion_status: Optional[str] = None
    speaker_voice_signature_count: Optional[int] = None
    speaker_voice_signature_meta: Optional[Dict[str, Any]] = None
    audio_emotion: Optional[str] = None
    sentiment: Optional[Dict[str, Any]] = None
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    time_hints: Optional[Dict[str, Any]] = None
    content_state: Optional[str] = None
    candidate_visible_people: List[Dict[str, Any]] = Field(default_factory=list)
    speaker_aligned_mentions: List[Dict[str, Any]] = Field(default_factory=list)
    transcript_entity_disagreements: List[Dict[str, Any]] = Field(default_factory=list)
    interaction_dominance: Optional[Dict[str, Any]] = None
    conversation_owner: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    """Search result with score and metadata."""
    score: float
    modality: str
    video_id: Optional[str] = None
    scene_id: Optional[SceneId] = None
    timestamp: Optional[float] = None
    representative_frame: Optional[str] = None
    transcript: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    objects: List[str] = Field(default_factory=list)
    sentiment: Optional[Dict[str, Any]] = None
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    context: Optional[Dict[str, Any]] = None
    provenance: Optional[Dict[str, Any]] = None
    confidence: Dict[str, Any] = Field(default_factory=default_confidence_payload)


class SearchResponse(BaseModel):
    """Multimodal search response."""
    query: str
    total_results: int
    results: List[SearchResult]
    modalities_searched: List[str]
    fusion_weights: Optional[Dict[str, float]] = None
    confidence: Dict[str, Any] = Field(default_factory=default_confidence_payload)


class TimelineSegment(BaseModel):
    """Timeline segment with all modalities."""
    segment_id: int
    start: float
    end: float
    scene_id: Optional[SceneId] = None
    audio_chunks: List[int] = Field(default_factory=list)
    speaker_ids: List[str] = Field(default_factory=list)
    transcript: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    objects: List[str] = Field(default_factory=list)
    clip_id: Optional[str] = None
    dino_id: Optional[str] = None
    representative_frame: Optional[str] = None
    speaker_count: Optional[int] = None
    dominant_speaker_id: Optional[str] = None
    continuity_key: Optional[str] = None
    diarization_status: Optional[str] = None
    emotion_status: Optional[str] = None
    speaker_voice_signature_count: Optional[int] = None
    speaker_voice_signature_meta: Optional[Dict[str, Any]] = None
    audio_emotion: Optional[str] = None
    sentiment: Optional[Dict[str, Any]] = None
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    time_hints: Optional[Dict[str, Any]] = None
    content_state: Optional[str] = None
    candidate_visible_people: List[Dict[str, Any]] = Field(default_factory=list)
    speaker_aligned_mentions: List[Dict[str, Any]] = Field(default_factory=list)
    transcript_entity_disagreements: List[Dict[str, Any]] = Field(default_factory=list)
    interaction_dominance: Optional[Dict[str, Any]] = None
    conversation_owner: Optional[Dict[str, Any]] = None


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


class MutationPolicy(BaseModel):
    """Declared policy requirements for write/control surfaces."""
    explicit: bool = True
    confirmation_gated: bool = True
    policy_driven: bool = True
    budgeted: bool = True
    checkpointed: bool = True
    auditable: bool = True


class SystemMutationResponse(BaseModel):
    """Read model for intentionally disabled or operator-only mutation routes."""
    status: str
    allowed: bool
    route: str
    mode: str
    message: str
    canonical_runtime_path: Optional[str] = None
    operator_surfaces: List[str] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)
    next_step: Optional[str] = None
    policy: MutationPolicy = Field(default_factory=MutationPolicy)


class IngestRequest(BaseModel):
    """Ingest job request."""
    file_path: str
    priority: Optional[int] = 0
    options: Optional[Dict[str, Any]] = None


class IngestResponse(SystemMutationResponse):
    """Ingest job response."""
    job_id: Optional[str] = None


class IngestSubmitRequest(BaseModel):
    """Truthful ingest facade submit request."""
    file_path: str
    confirmation_token: str
    policy_profile: str
    priority: int = 0
    options: Dict[str, Any] = Field(default_factory=dict)


class IngestSubmitResponse(BaseModel):
    """Truthful ingest facade submit response."""
    request_id: str
    status: str
    source_path: str
    original_name: str
    staged_path: Optional[str] = None
    policy_profile: str
    queue_depth_snapshot: int
    watchdog_detection_window_seconds: int
    pickup_estimate: str
    budget_scope: str
    budget_status: str
    duplicate_of_run_id: Optional[str] = None


class IngestStatusResponse(BaseModel):
    """Truthful ingest facade status response."""
    request_id: str
    status: str
    source_path: str
    original_name: str
    staged_path: Optional[str] = None
    policy_profile: str
    queue_depth_snapshot: int
    watchdog_detection_window_seconds: int
    pickup_estimate: str
    budget_scope: str
    budget_status: str
    duplicate_of_run_id: Optional[str] = None
    run_id: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    last_observed_at: Optional[str] = None
    completed_at: Optional[str] = None
