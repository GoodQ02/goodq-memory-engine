"""
Pydantic response models for GoodQ4All API.
Provides type-safe, validated response schemas for all endpoints.
"""
from __future__ import annotations
from typing import List, Dict, Any, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field

SceneId = int | str
INGEST_REQUEST_ID_PATTERN = r"^ingest_\d{8}T\d{6}Z_[0-9a-f]{8}$"


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
    video_id: Optional[str] = None
    scene_id: SceneId
    start: float
    end: float
    duration: float
    representative_frame: Optional[str] = None
    representative_frame_available: bool = False
    representative_frame_endpoint: Optional[str] = None
    representative_frame_path_redacted: bool = False
    frame_paths: List[str] = Field(default_factory=list)
    frame_endpoints: List[str] = Field(default_factory=list)
    frame_path_count: int = 0
    frame_paths_redacted: bool = False
    visual_caption: Optional[str] = None
    ocr_text: Optional[str] = None
    ocr_date_candidates: List[str] = Field(default_factory=list)
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
    audio_emotion_scores: Optional[Dict[str, Any]] = None
    audio_emotion_ranking: List[Dict[str, Any]] = Field(default_factory=list)
    audio_emotion_top_candidate: Optional[Dict[str, Any]] = None
    audio_emotion_promotion_threshold: Optional[float] = None
    text_emotion_ranking: List[Dict[str, Any]] = Field(default_factory=list)
    text_emotion_meta: Optional[Dict[str, Any]] = None
    clap_meta: Optional[Dict[str, Any]] = None
    sentiment: Optional[Dict[str, Any]] = None
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    sentiment_meta: Optional[Dict[str, Any]] = None
    time_hints: Optional[Dict[str, Any]] = None
    tags: List[str] = Field(default_factory=list)
    tag_details: List[Dict[str, Any]] = Field(default_factory=list)
    scene_present_entities: List[Dict[str, Any]] = Field(default_factory=list)
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    dialogue_mentioned_entities: List[Dict[str, Any]] = Field(default_factory=list)
    mentioned_people: List[Dict[str, Any]] = Field(default_factory=list)
    visible_people: List[Dict[str, Any]] = Field(default_factory=list)
    scene_context_llm: Optional[Dict[str, Any]] = None
    scene_context_epistemic: Optional[Dict[str, Any]] = None
    scene_context_arbitration: Optional[Dict[str, Any]] = None
    content_state: Optional[str] = None
    candidate_visible_people: List[Dict[str, Any]] = Field(default_factory=list)
    speaker_aligned_mentions: List[Dict[str, Any]] = Field(default_factory=list)
    transcript_entity_disagreements: List[Dict[str, Any]] = Field(default_factory=list)
    normalization_applied: bool = False
    normalization_source: Optional[str] = None
    interaction_dominance: Optional[Dict[str, Any]] = None
    conversation_owner: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    """Search result with score and metadata."""
    score: float
    modality: str
    modalities: List[str] = Field(default_factory=list)
    modality_scores: Dict[str, float] = Field(default_factory=dict)
    video_id: Optional[str] = None
    timeline_video_id: Optional[str] = None
    display_title: Optional[str] = None
    scene_id: Optional[SceneId] = None
    start: Optional[float] = None
    end: Optional[float] = None
    duration: Optional[float] = None
    timestamp: Optional[float] = None
    representative_frame: Optional[str] = None
    representative_frame_available: bool = False
    representative_frame_endpoint: Optional[str] = None
    representative_frame_path_redacted: bool = False
    transcript: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    objects: List[str] = Field(default_factory=list)
    audio_emotion: Optional[str] = None
    audio_emotion_scores: Optional[Dict[str, Any]] = None
    audio_emotion_ranking: List[Dict[str, Any]] = Field(default_factory=list)
    audio_emotion_top_candidate: Optional[Dict[str, Any]] = None
    audio_emotion_promotion_threshold: Optional[float] = None
    text_emotion_ranking: List[Dict[str, Any]] = Field(default_factory=list)
    text_emotion_meta: Optional[Dict[str, Any]] = None
    clap_meta: Optional[Dict[str, Any]] = None
    audio_vector_proof: Optional[Dict[str, Any]] = None
    current_run_qdrant_audio_proven: bool = False
    current_run_audio_vector_proven: bool = False
    audio_qdrant_current_run_proven: bool = False
    scene_present_entities: List[Dict[str, Any]] = Field(default_factory=list)
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    dialogue_mentioned_entities: List[Dict[str, Any]] = Field(default_factory=list)
    mentioned_people: List[Dict[str, Any]] = Field(default_factory=list)
    visible_people: List[Dict[str, Any]] = Field(default_factory=list)
    candidate_visible_people: List[Dict[str, Any]] = Field(default_factory=list)
    speaker_aligned_mentions: List[Dict[str, Any]] = Field(default_factory=list)
    transcript_entity_disagreements: List[Dict[str, Any]] = Field(default_factory=list)
    kg_relationships: List[Dict[str, Any]] = Field(default_factory=list)
    kg_evidence: Optional[Dict[str, Any]] = None
    sentiment: Optional[Dict[str, Any]] = None
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    sentiment_meta: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None
    scene_context_llm: Optional[Dict[str, Any]] = None
    scene_context_epistemic: Optional[Dict[str, Any]] = None
    scene_context_arbitration: Optional[Dict[str, Any]] = None
    provenance: Optional[Dict[str, Any]] = None
    confidence: Dict[str, Any] = Field(default_factory=default_confidence_payload)
    phase6_complete: Optional[bool] = None


class SearchResponse(BaseModel):
    """Multimodal search response."""
    query: str
    total_results: int
    results: List[SearchResult]
    modalities_searched: List[str]
    fusion_weights: Optional[Dict[str, float]] = None
    diagnostics: Optional[Dict[str, Any]] = None
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
    representative_frame_available: bool = False
    representative_frame_endpoint: Optional[str] = None
    representative_frame_path_redacted: bool = False
    frame_endpoints: List[str] = Field(default_factory=list)
    frame_path_count: int = 0
    frame_paths_redacted: bool = False
    visual_caption: Optional[str] = None
    ocr_text: Optional[str] = None
    ocr_date_candidates: List[str] = Field(default_factory=list)
    speaker_count: Optional[int] = None
    dominant_speaker_id: Optional[str] = None
    continuity_key: Optional[str] = None
    diarization_status: Optional[str] = None
    emotion_status: Optional[str] = None
    speaker_voice_signature_count: Optional[int] = None
    speaker_voice_signature_meta: Optional[Dict[str, Any]] = None
    audio_emotion: Optional[str] = None
    audio_emotion_scores: Optional[Dict[str, Any]] = None
    audio_emotion_ranking: List[Dict[str, Any]] = Field(default_factory=list)
    audio_emotion_top_candidate: Optional[Dict[str, Any]] = None
    audio_emotion_promotion_threshold: Optional[float] = None
    text_emotion_ranking: List[Dict[str, Any]] = Field(default_factory=list)
    text_emotion_meta: Optional[Dict[str, Any]] = None
    clap_meta: Optional[Dict[str, Any]] = None
    sentiment: Optional[Dict[str, Any]] = None
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    sentiment_meta: Optional[Dict[str, Any]] = None
    time_hints: Optional[Dict[str, Any]] = None
    tags: List[str] = Field(default_factory=list)
    tag_details: List[Dict[str, Any]] = Field(default_factory=list)
    scene_present_entities: List[Dict[str, Any]] = Field(default_factory=list)
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    dialogue_mentioned_entities: List[Dict[str, Any]] = Field(default_factory=list)
    mentioned_people: List[Dict[str, Any]] = Field(default_factory=list)
    visible_people: List[Dict[str, Any]] = Field(default_factory=list)
    scene_context_llm: Optional[Dict[str, Any]] = None
    scene_context_epistemic: Optional[Dict[str, Any]] = None
    scene_context_arbitration: Optional[Dict[str, Any]] = None
    content_state: Optional[str] = None
    candidate_visible_people: List[Dict[str, Any]] = Field(default_factory=list)
    speaker_aligned_mentions: List[Dict[str, Any]] = Field(default_factory=list)
    transcript_entity_disagreements: List[Dict[str, Any]] = Field(default_factory=list)
    normalization_applied: bool = False
    normalization_source: Optional[str] = None
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
    thumbnail_available: bool = False
    thumbnail_endpoint: Optional[str] = None
    thumbnail_path_redacted: bool = False
    phase6_complete: Optional[bool] = None


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


class _StrictIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IngestPrepareRequest(_StrictIngestRequest):
    """Prepare a local file copy for an exact-scope operator decision."""

    action: Literal["prepare"]
    file_path: str
    policy_profile: str


class IngestConfirmRequest(_StrictIngestRequest):
    """Confirm one previously prepared request."""

    action: Literal["confirm"]
    request_id: str = Field(pattern=INGEST_REQUEST_ID_PATTERN)
    confirmation_token: str


class IngestCancelRequest(_StrictIngestRequest):
    """Cancel one previously prepared request."""

    action: Literal["cancel"]
    request_id: str = Field(pattern=INGEST_REQUEST_ID_PATTERN)
    confirmation_token: str


IngestSubmitRequest = Union[
    IngestPrepareRequest,
    IngestConfirmRequest,
    IngestCancelRequest,
]


class IngestSubmitResponse(BaseModel):
    """Truthful ingest facade submit response."""
    request_id: str
    status: str
    original_name: Optional[str] = None
    file_sha256: Optional[str] = None
    size_bytes: Optional[int] = None
    policy_profile: Optional[str] = None
    confirmation_required: bool = False
    confirmation_token: Optional[str] = None
    confirmation_expires_at: Optional[str] = None
    queue_depth_snapshot: Optional[int] = None
    watchdog_detection_window_seconds: Optional[int] = None
    pickup_estimate: Optional[str] = None
    budget_scope: Optional[str] = None
    budget_status: Optional[str] = None
    duplicate_of_run_id: Optional[str] = None


class IngestStatusResponse(BaseModel):
    """Truthful ingest facade status response."""
    request_id: str
    status: str
    original_name: Optional[str] = None
    file_sha256: Optional[str] = None
    size_bytes: Optional[int] = None
    policy_profile: Optional[str] = None
    confirmation_required: bool = False
    queue_depth_snapshot: Optional[int] = None
    watchdog_detection_window_seconds: Optional[int] = None
    pickup_estimate: Optional[str] = None
    budget_scope: Optional[str] = None
    budget_status: Optional[str] = None
    duplicate_of_run_id: Optional[str] = None
    run_id: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    last_observed_at: Optional[str] = None
    completed_at: Optional[str] = None


class UnstitchedPattern(BaseModel):
    """Details of an unstitched speaker pattern."""
    node_id: int
    node_name: str
    occurrence_count: int
    voiced_seconds: float
    segment_count: int
    sample_transcript: Optional[str] = None


class StitchPreviewRequest(BaseModel):
    """Request model for mapping preview."""
    source_node_name: str
    target_person_name: str


class StitchPreviewResponse(BaseModel):
    """Preview response outlining potential changes and conflicts."""
    success: bool
    source_node_name: str
    target_person_name: str
    scenes_affected: int
    episodes_affected: int
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)


class StitchRequest(BaseModel):
    """Request model to persist a mapping."""
    source_node_name: str
    target_person_name: str
    confirm: bool = False
    operator_note: Optional[str] = None


class StitchResponse(BaseModel):
    """Response model for a successful mapping commit."""
    success: bool
    message: str
    mapping_id: str
    edge_id: int


class StitchRevokeRequest(BaseModel):
    """Request model to revoke a mapping."""
    mapping_id: Optional[str] = None
    source_node_name: Optional[str] = None
    operator_note: Optional[str] = None


class StitchRevokeResponse(BaseModel):
    """Response model for mapping revocation."""
    success: bool
    message: str


class ManualMappingHistoryEntry(BaseModel):
    """History entry for manual mappings."""
    status: str
    timestamp_utc: str
    operator_note: Optional[str] = None


class ManualMappingEntry(BaseModel):
    """Single manual mapping entry."""
    mapping_id: str
    source_node_type: str
    source_node_name: str
    target_person_name: str
    status: str
    history: List[ManualMappingHistoryEntry] = Field(default_factory=list)


class ManualMappingsResponse(BaseModel):
    """Full manual mappings response."""
    version: int
    mappings: List[ManualMappingEntry] = Field(default_factory=list)


class ScopeMetadata(BaseModel):
    """Execution scope metadata for all summary operations."""
    epoch: str
    db_path: str
    video_count: int
    scene_count: int
    temporal_index_count: int
    generated_at_utc: str
    source_surfaces_used: List[str] = Field(default_factory=list)


class OccasionItem(BaseModel):
    """Read model for Occasions (replaces Holidays)."""
    entity_id: str
    name: str
    occurrence_count: int
    occasion_type: str
    source: str
    confidence: float


class EntitySummaryItem(BaseModel):
    """Summary metrics for major entities (people, places)."""
    entity_id: str
    name: str
    occurrence_count: int
    first_seen: Optional[float] = None
    last_seen: Optional[float] = None


class BuiltInHighlights(BaseModel):
    """Predefined static/deterministic highlight collections."""
    positive_moments: List[Dict[str, Any]] = Field(default_factory=list)
    negative_moments: List[Dict[str, Any]] = Field(default_factory=list)
    multi_person_gatherings: List[Dict[str, Any]] = Field(default_factory=list)


class SummaryDashboardResponse(BaseModel):
    """Response model for cumulative dashboard metrics."""
    scope_metadata: ScopeMetadata
    people: List[EntitySummaryItem] = Field(default_factory=list)
    places: List[EntitySummaryItem] = Field(default_factory=list)
    occasions: List[OccasionItem] = Field(default_factory=list)
    sentiment_distribution: Dict[str, int] = Field(default_factory=dict)
    top_emotions: List[Dict[str, Any]] = Field(default_factory=list)
    built_in_highlights: BuiltInHighlights


class CoOccurrenceItem(BaseModel):
    """Represents an entity that co-occurs with the target entity."""
    entity_id: str
    node_type: str
    name: str
    co_occurrence_count: int


class SceneRef(BaseModel):
    """Reference to a scene segment featuring the entity."""
    video_id: str
    scene_id: str
    start: float
    end: float
    representative_frame: Optional[str] = None
    transcript: Optional[str] = None


class EntityProfileResponse(BaseModel):
    """Full detail profile response for a major entity."""
    scope_metadata: ScopeMetadata
    entity_id: str
    node_type: str
    name: str
    occurrence_count: int
    first_seen: Optional[float] = None
    last_seen: Optional[float] = None
    co_occurrences: List[CoOccurrenceItem] = Field(default_factory=list)
    scenes: List[SceneRef] = Field(default_factory=list)
    sentiment_distribution: Dict[str, int] = Field(default_factory=dict)
    top_emotions: List[Dict[str, Any]] = Field(default_factory=list)


class CollectionHistoryEntry(BaseModel):
    """Change log history entry for custom collections."""
    action: str
    timestamp_utc: str
    operator_note: Optional[str] = None


class SavedCollectionItem(BaseModel):
    """Custom manual playlist/collection persisted object."""
    collection_id: str
    name: str
    description: Optional[str] = None
    status: str
    collection_type: str
    query_params: Dict[str, Any] = Field(default_factory=dict)
    scene_refs: List[Dict[str, Any]] = Field(default_factory=list)
    source_epoch: str
    created_at_utc: str
    created_by: str
    updated_at_utc: str
    deleted_at_utc: Optional[str] = None
    history: List[CollectionHistoryEntry] = Field(default_factory=list)


class SaveCollectionRequest(BaseModel):
    """Request payload to create/update custom collections."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=256)
    description: Optional[str] = Field(default=None, max_length=4096)
    collection_type: str = Field(default="manual_playlist", min_length=1, max_length=64)
    query_params: Dict[str, Any] = Field(default_factory=dict)
    scene_refs: List[Dict[str, Any]] = Field(default_factory=list)
    operator_note: Optional[str] = Field(default=None, max_length=2048)


class SaveCollectionResponse(BaseModel):
    """API response model after saving a custom collection."""
    success: bool
    message: str
    collection: SavedCollectionItem


