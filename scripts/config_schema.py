"""
GoodQ4All Canonical Configuration Schema
Pydantic v2 validation layer for the unified config.yaml
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any


# ============================================================================
# USER & MODEL IDENTITY
# ============================================================================
class UserConfig(BaseModel):
    name: str
    nickname: str
    pronouns: str
    personality_traits: str
    values: str
    background: str
    music_style: str
    role_nursing: str
    nursing_philosophy: str
    role_personal: str


class ModelConfig(BaseModel):
    identity: str
    personality_traits: str
    values: str
    humor_style: str
    tech_sidekick_persona: str
    zone_1: str
    zone_1_desc: str
    zone_2: str
    zone_2_desc: str
    zone_3: str
    zone_3_desc: str
    main_hardware: str
    main_hardware_codename: str
    mission_name: str
    assigned_zone: str
    workplace: str


# ============================================================================
# HOST IDENTITY (PORTABILITY LAYER)
# ============================================================================
class HostConfig(BaseModel):
    profile: Optional[str] = None
    data_root: Optional[str] = None
    wsl_distro: Optional[str] = None
    wsl_user: Optional[str] = None
    wsl_workspace: Optional[str] = None
    conda_env: Optional[str] = None
    require_gpu: Optional[bool] = None
    require_wsl_audio: Optional[bool] = None

    class Config:
        extra = "forbid"


# ============================================================================
# PATHS
# ============================================================================
class PathsConfig(BaseModel):
    log_dir: str
    output_directory: str
    db_dir: str
    db_path: str
    knowledge_graph_db: str
    faiss_dir: str
    faiss_audio_path: Optional[str] = None
    qdrant_storage: Optional[str] = None
    watchdog_state_file: Optional[str] = None
    watchdog_lock_file: Optional[str] = None
    config_dir: str
    data_root: str
    import_inbox: str
    processing: str
    processed: Optional[str] = None
    failed: Optional[str] = None
    models_cache: str
    chunk_subdir: str
    audio_subdir: str
    video_subdir: str
    metadata_subdir: str
    csv_path: str
    nas_path: str


# ============================================================================
# LLM & TTS
# ============================================================================
class ToolsConfig(BaseModel):
    ffmpeg_exe: str = "ffmpeg"
    tesseract_exe: str = "tesseract"
    poppler_bin: str = ""


class RuntimeConfigSection(BaseModel):
    tools: ToolsConfig


class LLMConfig(BaseModel):
    api_url: str
    model_id: str


class TTSConfig(BaseModel):
    elevenlabs_voice_id: str
    piper_voice: str
    last_used_voice: str
    piper_exe: str | None = None
    voice_path: str | None = None
    out_dir: str | None = None


# ============================================================================
# HOME ASSISTANT
# ============================================================================
class HomeAssistantConfig(BaseModel):
    url: str
    token: str


# ============================================================================
# SYSTEM HARDWARE
# ============================================================================
class SystemConfig(BaseModel):
    cpu: str
    gpu: str
    ram1: str
    ram2: str
    ssd1: str
    ssd2: str
    network: str
    storage: str


# ============================================================================
# GPU CONFIGURATION
# ============================================================================
class GPUConfig(BaseModel):
    enabled: bool = True
    cuda_version: str = "12.1"
    torch_version: str = "2.5.1+cu121"
    primary_env: str = "goodq_core"
    memory_fraction: float = 0.85
    allow_growth: bool = True


# ============================================================================
# ENVIRONMENT ROUTING
# ============================================================================
class EnvsConfig(BaseModel):
    core: str = "goodq_core"
    audio_transcribe: str = "goodq_audio_transcribe"
    audio_embed: str = "goodq_audio_embed"
    audio_emotion: str = "goodq_audio_emotion"
    audio_metadata: str = "goodq_audio_metadata"
    video_scene_detect: str = "goodq_video_scene_detect"


# ============================================================================
# QDRANT VECTOR DATABASE
# ============================================================================
class QdrantCollectionsConfig(BaseModel):
    clip: str = "goodq_clip"
    dino: str = "goodq_dino"
    text: str = "goodq_text"
    audio: str = "goodq_audio"


class QdrantEmbeddingDims(BaseModel):
    clip: int = 512
    dino: int = 768
    text: int = 384
    audio: int = 512


class QdrantConfig(BaseModel):
    enabled: bool = True
    host: str = "http://localhost:6333"
    collections: QdrantCollectionsConfig
    embedding_dims: QdrantEmbeddingDims


# ============================================================================
# SEGMENTATION PHASES
# ============================================================================
class Phase0Config(BaseModel):
    target_sample_rate: int = 16000
    channels: int = 1
    bit_depth: int = 16
    codec: str = "pcm_s16le"


class Phase1Config(BaseModel):
    aggressiveness: int = 3
    frame_duration_ms: int = 30
    min_speech_duration: float = 0.3
    min_silence_duration: float = 0.5
    padding_duration: float = 0.1


class Phase2Config(BaseModel):
    enabled: bool = False
    min_duration_off: float = 0.0
    min_duration_on: float = 0.0
    model: str = "pyannote/segmentation-3.0"
    device: str = "cuda"
    use_auth_token: Optional[str] = None


class Phase3Config(BaseModel):
    min_chunk_duration: float = 1.0
    max_chunk_duration: float = 40.0
    target_chunk_duration: float = 20.0
    chunk_padding_ms: int = 250
    chunk_overlap_ms: int = 500
    merge_threshold: float = 2.0


class Phase4Config(BaseModel):
    enable_transcription: bool = True
    enable_diarization: bool = True
    enable_embeddings: bool = True
    enable_emotion: bool = True
    enable_music_detection: bool = True
    whisper_model: str = "medium"
    language: Optional[str] = None
    beam_size: int = 5
    best_of: int = 5
    temperature: float = 0.0
    min_speakers: Optional[int] = None
    max_speakers: Optional[int] = None
    diarize_timeout: int = 7200
    chunk_timeout: int = 600
    max_parallel_chunks: int = 2
    clap_model: str = "laion/clap-htsat-fused"
    emotion_model: str = "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"


class Phase5Config(BaseModel):
    enabled: bool = True
    scene_threshold: float = 30.0
    min_scene_len_sec: float = 2.0
    use_gpu: bool = True
    batch_size: int = 32
    alignment_tolerance: float = 0.5


class SegmentationConfig(BaseModel):
    enabled: bool = True
    activation: str = "off"
    metrics_output: bool = True
    shadow_audio_overlay: bool = False
    mode: str = "phased"
    phase0: Phase0Config
    phase1: Phase1Config
    phase2: Phase2Config
    phase3: Phase3Config
    phase4: Phase4Config
    phase5: Phase5Config


# ============================================================================
# VIDEO PROCESSING
# ============================================================================
class VideoSceneDetectConfig(BaseModel):
    threshold: float = 30.0
    min_scene_len_sec: float = 300.0
    max_scenes: int = 0
    entity_refine: bool = False
    entity_sample_rate: float = 0.5
    entity_min_duration: float = 300.0
    entity_max_samples: int = 300


class VideoConfig(BaseModel):
    scene_detect: VideoSceneDetectConfig


# ============================================================================
# PHASE 6: VISUAL EMBEDDINGS & CROSS-MODAL FUSION
# ============================================================================
class Phase6RetrievalConfig(BaseModel):
    enable: bool = True
    fusion_weights: Dict[str, float] = {
        "text": 0.5,
        "visual": 0.4,
        "audio": 0.1
    }


class Phase6Config(BaseModel):
    enabled: bool = True
    frame_sampling_strategy: str = "uniform"
    frames_per_scene: int = 3
    max_gpu_batch_size: int = 8
    clip_collection: str = "goodq_clip"
    dino_collection: str = "goodq_dino"
    retrieval: Phase6RetrievalConfig


# ============================================================================
# API CONFIGURATION
# ============================================================================
class APIConfig(BaseModel):
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 30000
    reload: bool = True
    cors_enabled: bool = False
    max_upload_size: int = 5368709120


# ============================================================================
# UI CONFIGURATION
# ============================================================================
class UIConfig(BaseModel):
    enabled: bool = True
    serve_from: str
    theme: str = "dark"


# ============================================================================
# PIPELINE SETTINGS
# ============================================================================
class PipelineConfig(BaseModel):
    parallel_processing: bool = False
    max_workers: int = 4
    save_intermediate: bool = True
    cleanup_temp_files: bool = False
    retry_on_failure: bool = True
    max_retries: int = 3


# ============================================================================
# OUTPUT SETTINGS
# ============================================================================
class OutputConfig(BaseModel):
    save_chunks: bool = True
    save_manifests: bool = True
    save_embeddings: bool = True
    compression: bool = False


# ============================================================================
# LOGGING
# ============================================================================
class LoggingConfig(BaseModel):
    level: str = "INFO"
    save_logs: bool = True
    verbose: bool = True
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


# ============================================================================
# ROOT CONFIG
# ============================================================================
class GoodQConfig(BaseModel):
    """
    The canonical GoodQ4All configuration schema.
    All config keys are validated against this schema.
    """
    user: UserConfig
    model: ModelConfig
    host: Optional[HostConfig] = None
    paths: PathsConfig
    config: Optional[RuntimeConfigSection] = None
    llm: LLMConfig
    tts: TTSConfig
    home_assistant: HomeAssistantConfig
    system: SystemConfig
    gpu: GPUConfig
    envs: EnvsConfig
    qdrant: QdrantConfig
    segmentation: SegmentationConfig
    video: VideoConfig
    phase6: Phase6Config
    api: APIConfig
    ui: UIConfig
    pipeline: PipelineConfig
    output: OutputConfig
    logging: LoggingConfig

    class Config:
        extra = "forbid"  # Reject unknown keys
        validate_assignment = True
