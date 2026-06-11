# GoodQ4All Codebase Guide

Welcome to the developer guide for GoodQ4All. This guide provides a mapped index of active modules, organized by subsystem.

## Table of Subsystems

- [agents](#subsystem-agents)
- [api](#subsystem-api)
- [cli](#subsystem-cli)
- [common](#subsystem-common)
- [configs](#subsystem-configs)
- [lib](#subsystem-lib)
- [pipelines](#subsystem-pipelines)
- [retrieval](#subsystem-retrieval)
- [steps](#subsystem-steps)
- [steps/audio](#subsystem-steps-audio)
- [steps/audio_diarize](#subsystem-steps-audio_diarize)
- [steps/audio_embed_clap](#subsystem-steps-audio_embed_clap)
- [steps/audio_emotion](#subsystem-steps-audio_emotion)
- [steps/audio_ingest_unified](#subsystem-steps-audio_ingest_unified)
- [steps/audio_metadata](#subsystem-steps-audio_metadata)
- [steps/audio_music_events](#subsystem-steps-audio_music_events)
- [steps/audio_speaker_merge](#subsystem-steps-audio_speaker_merge)
- [steps/audio_time_hints](#subsystem-steps-audio_time_hints)
- [steps/audio_transcribe](#subsystem-steps-audio_transcribe)
- [steps/common](#subsystem-steps-common)
- [steps/discover_sources](#subsystem-steps-discover_sources)
- [steps/emotion_classify](#subsystem-steps-emotion_classify)
- [steps/face_embed](#subsystem-steps-face_embed)
- [steps/graph_builder](#subsystem-steps-graph_builder)
- [steps/health_auto_export](#subsystem-steps-health_auto_export)
- [steps/home_assistant_status](#subsystem-steps-home_assistant_status)
- [steps/image_caption](#subsystem-steps-image_caption)
- [steps/image_embed_clip](#subsystem-steps-image_embed_clip)
- [steps/image_embed_dino](#subsystem-steps-image_embed_dino)
- [steps/image_exif](#subsystem-steps-image_exif)
- [steps/image_ocr](#subsystem-steps-image_ocr)
- [steps/llm_chat](#subsystem-steps-llm_chat)
- [steps/object_detect](#subsystem-steps-object_detect)
- [steps/object_track_yolo](#subsystem-steps-object_track_yolo)
- [steps/overview](#subsystem-steps-overview)
- [steps/pdf_text](#subsystem-steps-pdf_text)
- [steps/sentiment](#subsystem-steps-sentiment)
- [steps/system_metrics](#subsystem-steps-system_metrics)
- [steps/tagger](#subsystem-steps-tagger)
- [steps/text_embed](#subsystem-steps-text_embed)
- [steps/tts](#subsystem-steps-tts)
- [steps/video](#subsystem-steps-video)
- [steps/video_ingest](#subsystem-steps-video_ingest)
- [steps/video_scene_detect](#subsystem-steps-video_scene_detect)
- [steps/video_summarizer](#subsystem-steps-video_summarizer)
- [wsl2_audio](#subsystem-wsl2_audio)

## Subsystem: `agents`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/agents/__init__.py)
- **Relative Path**: `agents/__init__.py`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/agents/analysis/__init__.py)
- **Relative Path**: `agents/analysis/__init__.py`

### [base_agent.py](file:///L:/GOODCUBE/projects/goodq4all/agents/base_agent.py)
- **Relative Path**: `agents/base_agent.py`
- **Classes**: `BaseAgent`
- **Imports**: `abc.ABC`, `abc.abstractmethod`, `asyncio`, `configs.python_paths.get_conda_run_command`, `json`, `pathlib.Path`, `subprocess`, `sys`, `typing.Any`, `typing.Dict`, `typing.Optional`

### [config_healer.py](file:///L:/GOODCUBE/projects/goodq4all/agents/config_healer.py)
- **Relative Path**: `agents/config_healer.py`
- **Classes**: `ConfigHealer`
- **Functions**: `main`
- **Imports**: `datetime.datetime`, `json`, `lib.llm_client.LLMClient`, `os`, `pathlib.Path`, `shutil`, `steps.common.config_loader.load_configs`, `steps.common.llm_model_factory.build_llm_models`, `sys`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`, `yaml`

### [control_agent.py](file:///L:/GOODCUBE/projects/goodq4all/agents/control_agent.py)
- **Relative Path**: `agents/control_agent.py`
- **Classes**: `ControlAgent`
- **Functions**: `_resolve_control_agent_data_dir`, `main`
- **Imports**: `agents.config_healer.ConfigHealer`, `agents.recovery_db.RecoveryDatabase`, `agents.recovery_strategies.RecoveryStrategies`, `datetime.datetime`, `json`, `lib.llm_client.LLMClient`, `os`, `pathlib.Path`, `re`, `sqlite3`, `steps.common.config_loader.load_configs`, `steps.common.llm_model_factory.build_llm_models`, `sys`, `time`, `traceback`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/agents/ingestion/__init__.py)
- **Relative Path**: `agents/ingestion/__init__.py`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/agents/knowledge/__init__.py)
- **Relative Path**: `agents/knowledge/__init__.py`

### [llm_agent.py](file:///L:/GOODCUBE/projects/goodq4all/agents/llm_agent.py)
- **Relative Path**: `agents/llm_agent.py`
- **Classes**: `LLMAgent`
- **Imports**: `agents.base_agent.BaseAgent`, `aiohttp`, `asyncio`, `json`, `logging`, `pathlib.Path`, `sys`, `typing.Any`, `typing.Dict`, `typing.List`

### [mini_agent_client.py](file:///L:/GOODCUBE/projects/goodq4all/agents/mini_agent_client.py)
- **Relative Path**: `agents/mini_agent_client.py`
- **Classes**: `MiniAgentClient`
- **Functions**: `_bootstrap_module_layer`
- **Imports**: `__future__.annotations`, `datetime.datetime`, `faiss`, `goodq_mini_agent.paths`, `goodq_mini_agent.stack_runner`, `json`, `lib.llm_client.LLMClient`, `logging`, `numpy`, `os`, `pathlib.Path`, `steps.common.config_loader.load_configs`, `steps.common.faiss_utils.FaissLock`, `steps.common.llm_model_factory.build_llm_models`, `steps.common.qdrant_client.build_qdrant_client`, `subprocess`, `sys`, `tempfile`, `time`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`, `uuid`

### [recovery_db.py](file:///L:/GOODCUBE/projects/goodq4all/agents/recovery_db.py)
- **Relative Path**: `agents/recovery_db.py`
- **Classes**: `RecoveryDatabase`
- **Functions**: `get_recovery_db`
- **Imports**: `datetime.datetime`, `json`, `logging`, `os`, `pathlib.Path`, `sqlite3`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [recovery_strategies.py](file:///L:/GOODCUBE/projects/goodq4all/agents/recovery_strategies.py)
- **Relative Path**: `agents/recovery_strategies.py`
- **Classes**: `RecoveryStrategies`
- **Functions**: `_default_control_memory_path`
- **Imports**: `datetime.datetime`, `json`, `logging`, `os`, `pathlib.Path`, `re`, `sqlite3`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [self_healing_monitor.py](file:///L:/GOODCUBE/projects/goodq4all/agents/self_healing_monitor.py)
- **Relative Path**: `agents/self_healing_monitor.py`
- **Classes**: `SelfHealingMonitor`
- **Functions**: `_default_memory_db_path`, `_default_log_dir`, `run_monitor`
- **Imports**: `agents.config_healer.ConfigHealer`, `agents.llm_agent.LLMAgent`, `asyncio`, `datetime.datetime`, `datetime.timedelta`, `json`, `lib.llm_client.LLMClient`, `logging`, `os`, `pathlib.Path`, `sqlite3`, `steps.common.config_loader.load_configs`, `steps.common.llm_model_factory.build_llm_models`, `time`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

## Subsystem: `api`

### [main.py](file:///L:/GOODCUBE/projects/goodq4all/api/main.py)
- **Relative Path**: `api/main.py`
- **Classes**: `UTF8JSONMiddleware`
- **Functions**: `_resolve_allowed_origins`, `custom_swagger_ui_html`, `custom_redoc_html`
- **Imports**: `__future__.annotations`, `api.routes.control_recurrence`, `api.routes.ingest`, `api.routes.media`, `api.routes.meta`, `api.routes.runtime`, `api.routes.scenes`, `api.routes.search`, `api.routes.summary`, `api.routes.system`, `api.routes.timeline`, `api.utils.loaders`, `fastapi.FastAPI`, `fastapi.middleware.cors.CORSMiddleware`, `fastapi.openapi.docs.get_redoc_html`, `fastapi.openapi.docs.get_swagger_ui_html`, `fastapi.staticfiles.StaticFiles`, `goodq_version.GOODQ_VERSION`, `logging`, `os`, `pathlib.Path`, `starlette.middleware.base.BaseHTTPMiddleware`, `steps.common.config_loader.load_configs`, `typing.Any`, `typing.Dict`, `typing.List`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/api/routes/__init__.py)
- **Relative Path**: `api/routes/__init__.py`
- **Imports**: `api.routes.control_recurrence`, `api.routes.ingest`, `api.routes.media`, `api.routes.meta`, `api.routes.runtime`, `api.routes.scenes`, `api.routes.search`, `api.routes.system`, `api.routes.timeline`

### [control_recurrence.py](file:///L:/GOODCUBE/projects/goodq4all/api/routes/control_recurrence.py)
- **Relative Path**: `api/routes/control_recurrence.py`
- **Functions**: `list_control_recurrence_reports`, `latest_control_recurrence_report`, `get_control_recurrence_reports_trend`, `get_control_recurrence_report`, `get_control_recurrence_report_recommendations`, `get_control_recurrence_report_markdown`
- **Imports**: `__future__.annotations`, `fastapi.APIRouter`, `fastapi.responses.JSONResponse`, `fastapi.responses.PlainTextResponse`, `lib.control_recurrence_index`, `lib.control_recurrence_recommendations.build_recommendation_draft`, `lib.control_recurrence_trend.build_control_recurrence_trend`, `typing.Any`, `typing.Dict`

### [ingest.py](file:///L:/GOODCUBE/projects/goodq4all/api/routes/ingest.py)
- **Relative Path**: `api/routes/ingest.py`
- **Functions**: `get_ingest_runtime_paths`, `get_ingest_request_ledger`, `_ensure_local_supported_file`, `get_allowed_import_roots`, `require_allowed_source`, `_submit_budget_profile`, `generate_confirmation_token`, `submit_ingest`, `get_ingest_status`, `safe_upload_name`, `upload_file`
- **Imports**: `__future__.annotations`, `api.utils.ingest_requests.DEFAULT_PICKUP_ESTIMATE`, `api.utils.ingest_requests.DEFAULT_WATCHDOG_DETECTION_WINDOW_SECONDS`, `api.utils.ingest_requests.IngestRequestLedger`, `api.utils.ingest_requests.compute_file_hash`, `api.utils.ingest_requests.count_supported_inbox_items`, `api.utils.ingest_requests.is_supported_ingest_path`, `api.utils.ingest_requests.load_watchdog_registry`, `api.utils.ingest_requests.resolve_ingest_request_status`, `api.utils.response_models.IngestStatusResponse`, `api.utils.response_models.IngestSubmitRequest`, `api.utils.response_models.IngestSubmitResponse`, `fastapi.APIRouter`, `fastapi.Body`, `fastapi.File`, `fastapi.HTTPException`, `fastapi.UploadFile`, `logging`, `pathlib.Path`, `pathlib.PurePath`, `pathlib.PureWindowsPath`, `secrets`, `shutil`, `steps.common.config_loader.get_runtime_paths`, `steps.common.config_loader.load_configs`, `threading`, `uuid.uuid4`

### [media.py](file:///L:/GOODCUBE/projects/goodq4all/api/routes/media.py)
- **Relative Path**: `api/routes/media.py`
- **Functions**: `get_data_loader`, `get_scene_frame`, `get_audio_chunk`, `get_frame_by_name`
- **Imports**: `__future__.annotations`, `api.utils.loaders.DataLoader`, `fastapi.APIRouter`, `fastapi.HTTPException`, `fastapi.Path`, `fastapi.responses.FileResponse`, `logging`, `pathlib.Path`

### [meta.py](file:///L:/GOODCUBE/projects/goodq4all/api/routes/meta.py)
- **Relative Path**: `api/routes/meta.py`
- **Functions**: `root`, `api_root`
- **Imports**: `__future__.annotations`, `fastapi.APIRouter`, `typing.Any`, `typing.Dict`

### [run_index.py](file:///L:/GOODCUBE/projects/goodq4all/api/routes/run_index.py)
- **Relative Path**: `api/routes/run_index.py`
- **Imports**: `fastapi.APIRouter`

### [run_summary.py](file:///L:/GOODCUBE/projects/goodq4all/api/routes/run_summary.py)
- **Relative Path**: `api/routes/run_summary.py`
- **Imports**: `fastapi.APIRouter`

### [runtime.py](file:///L:/GOODCUBE/projects/goodq4all/api/routes/runtime.py)
- **Relative Path**: `api/routes/runtime.py`
- **Functions**: `_get_ollama_models_url`, `_summarize_llm_health`, `_collect_engine_details`, `_collect_wsl_status`, `_database_status`, `_parse_iso_datetime`, `_collect_cli_progress`, `get_status`, `get_health_summary`, `get_engines`, `get_queue`, `_bytes_to_mb`, `_bytes_to_gb`, `_safe_dir_size`, `_storage_row`, `_safe_name_label`, `_path_redacted_label`, `_timeline_video_id_from_path_value`, `_timeline_video_id_from_episode`, `_latest_episode_preview`, `get_storage_summary`, `get_gpu_stats`, `get_wsl2_status`, `get_models`, `_latest_run_snapshot`, `_latest_run_preview`, `_latest_run_evidence`, `_runtime_visible_runs`, `_load_runtime_visible_run_summary`, `_configured_scene_results_run`, `_configured_scene_results_summary`, `_run_entry_mtime`, `_epoch_name_from_path`, `_first_text_value`, `_empty_run_evidence`, `_run_evidence_safety_boundary`, `_episode_evidence_summary`, `_episode_artifact_path`, `_artifact_path_from_scene_results`, `_find_step_runs_path`, `_find_runtime_log_paths`, `_load_json_any`, `_load_step_run_rows`, `_normalize_step_name`, `_step_scene_index`, `_step_problem_summary`, `_completed_step_keys_from_step_runs`, `_summarize_step_runs`, `_summarize_runtime_step_errors`, `_summarize_temporal_index`, `_count_records_with_list`, `_entity_top_values_from_records`, `_summarize_entity_evidence`, `_audio_emotion_score_buckets_from_records`, `_count_audio_emotion_score_records`, `_text_emotion_buckets_from_records`, `_summarize_sentiment`, `_summarize_knowledge_graph`, `_summarize_projection_gaps`, `_projection_scene_id_candidates`, `_projection_matching_segment`, `_projection_scene_label`, `_projection_source_observed`, `_projection_temporal_observed`, `_first_projection_value`, `_projection_value_observed`, `_summarize_audio_vector_proof`, `_scene_records_from_results`, `_temporal_scene_count`, `_audio_scene_scope`, `_clap_status_counts`, `_resolve_runtime_audio_run_id`, `_first_result_record`, `_audio_qdrant_collection_candidates`, `_qdrant_base_url`, `_scroll_qdrant_audio_payloads`, `_qdrant_audio_collection_names`, `_scroll_qdrant_audio_collection_payloads`, `_latest_audio_provenance_snapshot`, `_sample_qdrant_audio_payloads`, `_missing_required_field_counts`, `_is_safe_payload_shape_key`, `_evaluate_qdrant_audio_payloads`, `_safe_top_values`, `_simple_mapping`, `_safe_float`, `_round_number`, `_duration_summary`, `_percentile`, `_latest_timestamp`, `_tail_log`, `latest_run_preview`, `latest_run_evidence`, `latest_audio_provenance_snapshot`, `_sqlite_table_count`, `_sqlite_embedding_count`, `_positive_count`, `_faiss_count`, `get_memory_stats`, `read_epistemic_envelope`
- **Imports**: `__future__.annotations`, `api.utils.ingest_requests.is_supported_ingest_path`, `collections.Counter`, `collections.deque`, `datetime.datetime`, `faiss`, `fastapi.APIRouter`, `fastapi.HTTPException`, `fastapi.Query`, `goodq_version.GOODQ_VERSION`, `json`, `lib.run_index`, `lib.run_summary`, `logging`, `os`, `pathlib.Path`, `pathlib.PurePosixPath`, `pathlib.PureWindowsPath`, `requests`, `scenedetect.detect`, `shlex`, `shutil`, `sqlite3`, `steps.common.config_loader.load_configs`, `steps.common.memory_store.normalize_memory_tier_list`, `subprocess`, `sys`, `time`, `typing.Any`, `typing.Dict`, `typing.List`, `urllib.parse.urlparse`

### [scenes.py](file:///L:/GOODCUBE/projects/goodq4all/api/routes/scenes.py)
- **Relative Path**: `api/routes/scenes.py`
- **Functions**: `_segment_object_labels`, `_list_dicts`, `_scene_sentiment_payload`, `_find_temporal_segment`, `_build_scene_response`, `get_data_loader`, `get_search_engine`, `list_scenes`, `get_scene`, `find_similar_scenes`
- **Imports**: `__future__.annotations`, `api.utils.loaders.DataLoader`, `api.utils.media_projection.frame_paths_projection`, `api.utils.media_projection.representative_frame_projection`, `api.utils.response_models.SceneResponse`, `fastapi.APIRouter`, `fastapi.HTTPException`, `fastapi.Path`, `fastapi.Query`, `logging`, `retrieval.multimodal_search.MultimodalSearchEngine`, `steps.common.config_loader.load_configs`, `typing.Any`, `typing.Dict`, `typing.List`

### [search.py](file:///L:/GOODCUBE/projects/goodq4all/api/routes/search.py)
- **Relative Path**: `api/routes/search.py`
- **Classes**: `MultimodalSearchRequest`, `TemporalSearchRequest`, `TemporalSearchQueryInfo`, `TemporalEvidence`, `TemporalSearchResult`, `TemporalSearchResponse`, `TemporalSummarizeRequest`, `TemporalSummarizeQueryInfo`, `TemporalSummarizeSegment`, `TemporalSummarizeResponse`
- **Functions**: `configure_search_from_cfg`, `_extract_sentiment_fields`, `_list_strings`, `_list_dicts`, `_segment_object_labels`, `_segment_id_candidates`, `_segment_transcript`, `_segment_representative_frame_reference`, `_kg_evidence`, `_timeline_enrichment_context`, `_lookup_timeline_enrichment`, `_search_audio_vector_proof`, `_merge_dicts`, `_looks_like_local_path`, `_sanitize_local_path_values`, `_sanitize_read_model_mapping`, `_safe_number`, `_safe_modality_scores`, `_safe_modalities`, `_enriched_confidence`, `_build_search_result`, `get_search_engine`, `get_data_loader`, `search_multimodal`, `search_text`, `search_visual`, `search_temporal`, `summarize_temporal`
- **Imports**: `__future__.annotations`, `api.routes.runtime._audio_qdrant_collection_candidates`, `api.routes.runtime._evaluate_qdrant_audio_payloads`, `api.routes.runtime._scroll_qdrant_audio_payloads`, `api.utils.loaders.DataLoader`, `api.utils.media_projection.representative_frame_projection`, `api.utils.response_models.SearchResponse`, `api.utils.response_models.SearchResult`, `api.utils.response_models.default_confidence_payload`, `fastapi.APIRouter`, `fastapi.Body`, `fastapi.HTTPException`, `fastapi.Query`, `logging`, `pydantic.BaseModel`, `retrieval.multimodal_search.MultimodalSearchEngine`, `retrieval.narrative_summarizer.synthesize_narrative`, `retrieval.temporal_reasoning.temporal_search`, `steps.common.config_loader.load_configs`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [summary.py](file:///L:/GOODCUBE/projects/goodq4all/api/routes/summary.py)
- **Relative Path**: `api/routes/summary.py`
- **Functions**: `get_data_loader`, `_get_kg_db_path`, `get_dashboard`, `get_entity_profile`, `list_collections`, `create_collection`, `delete_collection`
- **Imports**: `__future__.annotations`, `api.utils.loaders.DataLoader`, `api.utils.response_models.EntityProfileResponse`, `api.utils.response_models.SaveCollectionRequest`, `api.utils.response_models.SaveCollectionResponse`, `api.utils.response_models.SavedCollectionItem`, `api.utils.response_models.SummaryDashboardResponse`, `fastapi.APIRouter`, `fastapi.Body`, `fastapi.HTTPException`, `fastapi.Path`, `lib.summary_aggregator`, `logging`, `pathlib.Path`, `steps.common.config_loader.load_configs`, `typing.List`

### [system.py](file:///L:/GOODCUBE/projects/goodq4all/api/routes/system.py)
- **Relative Path**: `api/routes/system.py`
- **Functions**: `get_data_loader`, `_build_mutation_response`, `get_system_status`, `list_videos`, `start_ingest`, `rebuild_indexes`, `reload_config`, `_get_kg_db_path`, `get_unstitched_patterns`, `preview_stitch`, `execute_stitch`, `get_manual_mappings`, `revoke_stitch`
- **Imports**: `__future__.annotations`, `api.utils.loaders.DataLoader`, `api.utils.media_projection.thumbnail_projection`, `api.utils.response_models.IngestRequest`, `api.utils.response_models.IngestResponse`, `api.utils.response_models.ManualMappingsResponse`, `api.utils.response_models.MutationPolicy`, `api.utils.response_models.StitchPreviewRequest`, `api.utils.response_models.StitchPreviewResponse`, `api.utils.response_models.StitchRequest`, `api.utils.response_models.StitchResponse`, `api.utils.response_models.StitchRevokeRequest`, `api.utils.response_models.StitchRevokeResponse`, `api.utils.response_models.SystemMutationResponse`, `api.utils.response_models.SystemStatus`, `api.utils.response_models.UnstitchedPattern`, `api.utils.response_models.VideoListItem`, `datetime.datetime`, `fastapi.APIRouter`, `fastapi.Body`, `fastapi.HTTPException`, `json`, `lib.identity_ledger.build_identity_ledger`, `lib.identity_ledger.load_manual_mappings`, `lib.identity_ledger.save_manual_mappings`, `lib.identity_ledger.write_identity_ledger_markdown`, `lib.knowledge_graph.KnowledgeGraph`, `logging`, `os`, `pathlib.Path`, `requests`, `sqlite3`, `steps.common.config_loader.load_configs`, `steps.common.tool_paths.resolve_conda`, `subprocess`, `typing.List`

### [timeline.py](file:///L:/GOODCUBE/projects/goodq4all/api/routes/timeline.py)
- **Relative Path**: `api/routes/timeline.py`
- **Functions**: `_segment_object_labels`, `_build_timeline_segment`, `_build_timeline_metadata`, `get_data_loader`, `get_timeline`, `get_full_timeline`
- **Imports**: `__future__.annotations`, `api.utils.loaders.DataLoader`, `api.utils.media_projection.frame_paths_projection`, `api.utils.media_projection.representative_frame_projection`, `api.utils.response_models.TimelineResponse`, `api.utils.response_models.TimelineSegment`, `fastapi.APIRouter`, `fastapi.HTTPException`, `fastapi.Path`, `logging`

### [server.py](file:///L:/GOODCUBE/projects/goodq4all/api/server.py)
- **Relative Path**: `api/server.py`
- **Functions**: `_resolve_api_bind_defaults`, `_find_available_port`, `main`
- **Imports**: `__future__.annotations`, `api.main.app`, `logging`, `os`, `pathlib`, `re`, `socket`, `steps.common.config_loader.load_configs`, `sys`, `uvicorn.run`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/api/utils/__init__.py)
- **Relative Path**: `api/utils/__init__.py`
- **Imports**: `api.utils.loaders.DataLoader`, `api.utils.response_models.*`

### [ingest_requests.py](file:///L:/GOODCUBE/projects/goodq4all/api/utils/ingest_requests.py)
- **Relative Path**: `api/utils/ingest_requests.py`
- **Classes**: `IngestRequestLedger`
- **Functions**: `utc_now_iso`, `compute_file_hash`, `is_supported_ingest_path`, `count_supported_inbox_items`, `load_watchdog_registry`, `resolve_ingest_request_status`
- **Imports**: `__future__.annotations`, `datetime.datetime`, `datetime.timezone`, `hashlib`, `json`, `pathlib.Path`, `steps.common.atomic_io.atomic_write_json`, `typing.Any`, `typing.Dict`, `typing.Optional`, `uuid`

### [loaders.py](file:///L:/GOODCUBE/projects/goodq4all/api/utils/loaders.py)
- **Relative Path**: `api/utils/loaders.py`
- **Classes**: `DataLoader`
- **Functions**: `_resolve_default_data_root`, `configure_from_cfg`
- **Imports**: `__future__.annotations`, `json`, `logging`, `os`, `pathlib.Path`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [media_projection.py](file:///L:/GOODCUBE/projects/goodq4all/api/utils/media_projection.py)
- **Relative Path**: `api/utils/media_projection.py`
- **Functions**: `frame_name_from_reference`, `is_path_like_reference`, `frame_endpoint`, `representative_frame_projection`, `frame_paths_projection`, `thumbnail_projection`
- **Imports**: `__future__.annotations`, `pathlib.PurePosixPath`, `pathlib.PureWindowsPath`, `urllib.parse.quote`

### [response_models.py](file:///L:/GOODCUBE/projects/goodq4all/api/utils/response_models.py)
- **Relative Path**: `api/utils/response_models.py`
- **Classes**: `SceneResponse`, `SearchResult`, `SearchResponse`, `TimelineSegment`, `TimelineResponse`, `VideoListItem`, `SystemStatus`, `MutationPolicy`, `SystemMutationResponse`, `IngestRequest`, `IngestResponse`, `IngestSubmitRequest`, `IngestSubmitResponse`, `IngestStatusResponse`, `UnstitchedPattern`, `StitchPreviewRequest`, `StitchPreviewResponse`, `StitchRequest`, `StitchResponse`, `StitchRevokeRequest`, `StitchRevokeResponse`, `ManualMappingHistoryEntry`, `ManualMappingEntry`, `ManualMappingsResponse`, `ScopeMetadata`, `OccasionItem`, `EntitySummaryItem`, `BuiltInHighlights`, `SummaryDashboardResponse`, `CoOccurrenceItem`, `SceneRef`, `EntityProfileResponse`, `CollectionHistoryEntry`, `SavedCollectionItem`, `SaveCollectionRequest`, `SaveCollectionResponse`
- **Functions**: `default_confidence_payload`
- **Imports**: `__future__.annotations`, `pydantic.BaseModel`, `pydantic.Field`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

## Subsystem: `cli`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/cli/__init__.py)
- **Relative Path**: `cli/__init__.py`

### [conduits_build.py](file:///L:/GOODCUBE/projects/goodq4all/cli/conduits_build.py)
- **Relative Path**: `cli/conduits_build.py`
- **Functions**: `utc_now_iso`, `_load_configs`, `_cfg_paths`, `_best_effort_wal`, `_set_version`, `main`
- **Imports**: `__future__.annotations`, `argparse`, `cli.conduits_kg`, `cli.conduits_memory`, `cli.conduits_processing`, `cli.conduits_sensitive_sources`, `cli.conduits_store_stats`, `cli.observability_rollup`, `cli.ui_conduits_rollup`, `contextlib`, `datetime.datetime`, `datetime.timezone`, `io`, `os`, `sqlite3`, `steps.common.config_loader.load_configs`, `sys`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.Optional`, `typing.Tuple`

### [conduits_kg.py](file:///L:/GOODCUBE/projects/goodq4all/cli/conduits_kg.py)
- **Relative Path**: `cli/conduits_kg.py`
- **Classes**: `BuildStats`
- **Functions**: `ensure_schema`, `_table_exists`, `build_all`, `_build_entity_index`, `_build_edge_summary`, `_build_entity_timeline`, `_build_entity_scene_mentions`
- **Imports**: `__future__.annotations`, `dataclasses.dataclass`, `json`, `sqlite3`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`

### [conduits_memory.py](file:///L:/GOODCUBE/projects/goodq4all/cli/conduits_memory.py)
- **Relative Path**: `cli/conduits_memory.py`
- **Classes**: `BuildStats`
- **Functions**: `ensure_schema`, `_table_exists`, `_truthy_env`, `summaries_preview_enabled`, `_redact_paths`, `_preview`, `build_all`, `_build_segment_index_public`, `_build_scene_segment_alignment`, `_build_embedding_catalog_public`, `_build_summaries_public`, `_build_link_summary_public`
- **Imports**: `__future__.annotations`, `dataclasses.dataclass`, `hashlib`, `json`, `os`, `re`, `sqlite3`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Sequence`, `typing.Tuple`

### [conduits_processing.py](file:///L:/GOODCUBE/projects/goodq4all/cli/conduits_processing.py)
- **Relative Path**: `cli/conduits_processing.py`
- **Classes**: `BuildStats`
- **Functions**: `ensure_schema`, `_read_json`, `_safe_bool`, `_safe_num`, `_safe_int`, `_safe_str`, `_has_text`, `build_all`, `scene_manifest_public_adapter`, `temporal_index_public_adapter`
- **Imports**: `__future__.annotations`, `dataclasses.dataclass`, `json`, `media_refs.is_video_id_hash`, `media_refs.tokenize_processing_path`, `os`, `sqlite3`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Sequence`, `typing.Tuple`

### [conduits_sensitive_sources.py](file:///L:/GOODCUBE/projects/goodq4all/cli/conduits_sensitive_sources.py)
- **Relative Path**: `cli/conduits_sensitive_sources.py`
- **Functions**: `ensure_schema`
- **Imports**: `__future__.annotations`, `sqlite3`

### [conduits_store_stats.py](file:///L:/GOODCUBE/projects/goodq4all/cli/conduits_store_stats.py)
- **Relative Path**: `cli/conduits_store_stats.py`
- **Classes**: `BuildStats`
- **Functions**: `ensure_schema`, `utc_now_iso`, `build_all`, `_build_qdrant_stats`, `_build_faiss_stats`
- **Imports**: `__future__.annotations`, `dataclasses.dataclass`, `datetime.datetime`, `datetime.timezone`, `faiss`, `os`, `requests`, `sqlite3`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`

### [control_recurrence_report.py](file:///L:/GOODCUBE/projects/goodq4all/cli/control_recurrence_report.py)
- **Relative Path**: `cli/control_recurrence_report.py`
- **Functions**: `main`
- **Imports**: `__future__.annotations`, `argparse`, `json`, `lib.control_recurrence_recommendations.build_recommendation_draft`, `lib.control_recurrence_recommendations.render_recommendation_draft`, `lib.control_recurrence_report.build_control_recurrence_comparison`, `lib.control_recurrence_report.build_control_recurrence_report`, `lib.control_recurrence_report.read_report_index`, `lib.control_recurrence_report.render_report_index`, `lib.control_recurrence_report.render_text_comparison`, `lib.control_recurrence_report.render_text_report`, `lib.control_recurrence_report.report_index_path`, `lib.control_recurrence_report.update_report_index`, `lib.control_recurrence_report.write_json_report_file`, `lib.control_recurrence_report.write_markdown_report`, `lib.control_recurrence_trend.build_control_recurrence_trend`, `lib.control_recurrence_trend.render_text_trend`, `os`, `pathlib.Path`, `sys`, `typing.Iterable`, `typing.Optional`

### [goodq_doctor.py](file:///L:/GOODCUBE/projects/goodq4all/cli/goodq_doctor.py)
- **Relative Path**: `cli/goodq_doctor.py`
- **Classes**: `Item`
- **Functions**: `_label`, `_max_severity`, `_print_section`, `_summarize_paths`, `_read_text`, `_bootstrap_repo_imports`, `_parse_mode`, `_parse_phase6b_status`, `_is_audio_enabled`, `_check_tcp`, `_check_cmd`, `_governance_checks`, `_config_checks`, `_manifest_checks`, `_phase6_checks`, `_service_checks`, `main`
- **Imports**: `__future__.annotations`, `argparse`, `contextlib`, `dataclasses.dataclass`, `datetime.datetime`, `datetime.timezone`, `io`, `os`, `pathlib.Path`, `re`, `scripts.wsl_audio_preflight.probe_wsl_audio_runtime`, `shutil`, `socket`, `steps.common.config_loader.load_configs`, `subprocess`, `sys`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.List`, `typing.Optional`, `typing.Tuple`, `urllib.parse.urlparse`

### [links.py](file:///L:/GOODCUBE/projects/goodq4all/cli/links.py)
- **Relative Path**: `cli/links.py`
- **Functions**: `main`
- **Imports**: `__future__.annotations`, `argparse`, `json`, `steps.common.config_loader.load_configs`, `steps.common.memory.insert_link`, `steps.common.memory.upsert_scene`, `steps.common.memory.upsert_segment`, `typing.Any`, `typing.Dict`

### [list_inbox.py](file:///L:/GOODCUBE/projects/goodq4all/cli/list_inbox.py)
- **Relative Path**: `cli/list_inbox.py`
- **Functions**: `main`
- **Imports**: `__future__.annotations`, `json`, `steps.common.config_loader.load_configs`, `steps.discover_sources.step.discover_sources`, `typing.Any`, `typing.Dict`, `typing.List`

### [media_refs.py](file:///L:/GOODCUBE/projects/goodq4all/cli/media_refs.py)
- **Relative Path**: `cli/media_refs.py`
- **Functions**: `is_video_id_hash`, `_posix`, `_wsl_mount_path`, `tokenize_processing_path`, `_parse_rel`, `_discover_processing_dirs`, `resolve_media_ref`
- **Imports**: `__future__.annotations`, `json`, `os`, `re`, `typing.Any`, `typing.Dict`, `typing.Optional`, `typing.Tuple`

### [memory.py](file:///L:/GOODCUBE/projects/goodq4all/cli/memory.py)
- **Relative Path**: `cli/memory.py`
- **Functions**: `_missing_memory_management`, `health_check`, `backup`, `verify_schema`, `migrate`, `seed_missing_assets`, `_populate_id_map_from_embeddings`, `rebuild_id_maps`, `cleanup_seed_sentinels`, `register_scene_bundle_cmd`, `main`
- **Imports**: `__future__.annotations`, `datetime.datetime`, `faiss`, `json`, `lib.memory_management.diagnostics.check_schema_drift`, `lib.memory_management.diagnostics.run_all_diagnostics`, `lib.memory_management.migrate.migrate_database`, `lib.memory_management.utils.create_memory_backup`, `numpy`, `os`, `pathlib.Path`, `random`, `sqlite3`, `steps.common.config_loader.load_configs`, `steps.common.memory.ensure_scene`, `steps.common.memory.register_scene_bundle`, `sys`, `typer`, `typing.Any`, `typing.Dict`, `typing.Optional`

### [monitor_ingestion.py](file:///L:/GOODCUBE/projects/goodq4all/cli/monitor_ingestion.py)
- **Relative Path**: `cli/monitor_ingestion.py`
- **Functions**: `_resolve_runtime_paths`, `format_time`, `get_latest_log`, `get_processing_videos`, `tail_log`, `monitor`
- **Imports**: `datetime.datetime`, `datetime.timedelta`, `json`, `logging`, `os`, `pathlib.Path`, `steps.common.config_loader.get_runtime_paths`, `steps.common.config_loader.load_configs`, `sys`, `time`

### [nl_query.py](file:///L:/GOODCUBE/projects/goodq4all/cli/nl_query.py)
- **Relative Path**: `cli/nl_query.py`
- **Classes**: `KnowledgeGraphNLQuery`
- **Functions**: `main`
- **Imports**: `json`, `lib.knowledge_graph.KnowledgeGraph`, `logging`, `pathlib.Path`, `requests`, `sqlite3`, `steps.common.config_loader.load_configs`, `sys`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [observability_health.py](file:///L:/GOODCUBE/projects/goodq4all/cli/observability_health.py)
- **Relative Path**: `cli/observability_health.py`
- **Functions**: `_table_exists`, `_count_rows`, `_load_configs`, `_cfg_paths`, `_recent_log_files`, `_tail_contains`, `_scan_sqlite_lock_warnings`, `_provenance_coverage_sample`, `_print_kv`, `main`
- **Imports**: `__future__.annotations`, `argparse`, `contextlib`, `heapq`, `io`, `os`, `pathlib.Path`, `sqlite3`, `steps.common.config_loader.load_configs`, `steps.common.qdrant_client.build_qdrant_client`, `steps.common.retrieval_events.retrieval_events_enabled`, `sys`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.List`, `typing.Optional`, `typing.Tuple`

### [observability_rollup.py](file:///L:/GOODCUBE/projects/goodq4all/cli/observability_rollup.py)
- **Relative Path**: `cli/observability_rollup.py`
- **Classes**: `_Agg`, `_CommitAgg`
- **Functions**: `_load_configs`, `_cfg_paths`, `_best_effort_wal`, `_store_ref`, `_safe_str`, `_parse_targets_json`, `_merge_counts`, `_read_counts_json`, `main`
- **Imports**: `__future__.annotations`, `argparse`, `contextlib`, `dataclasses.dataclass`, `dataclasses.field`, `io`, `json`, `sqlite3`, `steps.common.config_loader.load_configs`, `sys`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.Optional`, `typing.Tuple`

### [persistent_store_alignment_audit.py](file:///L:/GOODCUBE/projects/goodq4all/cli/persistent_store_alignment_audit.py)
- **Relative Path**: `cli/persistent_store_alignment_audit.py`
- **Functions**: `_load_configs`, `_cfg_paths`, `_render_human`, `main`
- **Imports**: `__future__.annotations`, `argparse`, `contextlib`, `io`, `json`, `lib.persistent_store_alignment.build_persistent_store_alignment`, `steps.common.config_loader.load_configs`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.Optional`, `typing.Tuple`

### [print_config.py](file:///L:/GOODCUBE/projects/goodq4all/cli/print_config.py)
- **Relative Path**: `cli/print_config.py`
- **Functions**: `_repo_root`, `_cfg_mapping`, `_derive_data_root`, `main`
- **Imports**: `__future__.annotations`, `argparse`, `contextlib`, `io`, `json`, `pathlib.Path`, `steps.common.config_loader.load_configs`, `steps.common.config_redaction.redact_config`, `sys`, `typing.Any`

### [retrieve.py](file:///L:/GOODCUBE/projects/goodq4all/cli/retrieve.py)
- **Relative Path**: `cli/retrieve.py`
- **Functions**: `_load_cfg`, `_embed_query`, `_search_qdrant`, `_search_faiss`, `_results_from_db`, `_scene_for_frame`, `main`, `search_text_index`
- **Imports**: `__future__.annotations`, `argparse`, `csv`, `faiss`, `hashlib`, `json`, `numpy`, `os`, `sentence_transformers.SentenceTransformer`, `sqlite3`, `steps.common.config_loader.load_configs`, `steps.common.qdrant_client.build_qdrant_client`, `torch`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Tuple`

### [run_ingestion.py](file:///L:/GOODCUBE/projects/goodq4all/cli/run_ingestion.py)
- **Relative Path**: `cli/run_ingestion.py`
- **Functions**: `_is_synthetic_speaker_label`, `_scoped_synthetic_speaker_name`, `_resolve_named_person_identity`, `_resolve_audio_speaker_identity`, `_patch_typer_help_for_click_8_2`, `_deep_merge_dicts`, `_load_runtime_cfg_snapshot`, `_resolve_models_dir`, `_resolve_processing_root`, `_parse_step_result_json`, `_control_agent_runtime_enabled`, `_get_control_agent`, `_resolve_step_timeout_value`, `_merge_prior_phase6_manifest_state`, `_observer`, `run_ingestion`, `_apply_env_overrides`, `_resolve_native_retry_strategy`, `_build_knowledge_graph_from_results`, `_process_keyframe_entities`, `_process_audio_entities`, `_build_kg_relationships`, `_merge_step_output`, `_extract_speaker_ids`, `_promote_metadata_time_hints`, `_time_hints_have_values`, `_merge_time_hint_dicts`, `_resolve_scene_time_hints`, `_build_kg_scene_data`, `_persist_frame_semantic_entities`, `_coerce_optional_float`, `_offset_timestamped_segments`, `_offset_local_audio_result_to_scene`, `_infer_audio_backend_fields`, `_read_audio_backend_marker`, `_record_audio_backend_event`, `_audio_backend_events_since`, `_resolve_audio_backend_attribution`, `_normalize_vector_store_status`, `_aggregate_audio_backend`, `_resolve_audio_runtime_contract`, `_resolve_segmentation_activation`, `_resolve_scene_backend_contract`, `_resolve_scene_backend_dispatch`, `_run_segmentation_authoritative_scene_backend`, `_resolve_phase6_audio_source_contract`, `_resolve_ingest_orchestration_contract`, `_safe_read_json_dict`, `_rehydrate_video_result_scenes_from_manifest`, `_ratio`, `_segment_has_transcript`, `_extract_segment_speaker_ids`, `_compute_scene_coverages`, `_compute_segment_coverages`, `_compute_temporal_index_completeness`, `_compute_shadow_alignment_score`, `_normalize_scene_boundaries`, `_scene_overlap_duration`, `_compute_scene_backend_comparison`, `_compute_shadow_temporal_readiness`, `_build_segmentation_shadow_metrics`, `_attach_segmentation_shadow_metrics`, `_segmentation_shadow_audio_overlay_enabled`, `_prepare_segmentation_shadow_audio_overlay`, `_run_segmentation_shadow_pipeline`, `_merge_modality_state`, `_status_dict_to_modality_state`, `_aggregate_modality_status`, `_coerce_float`, `_resolve_content_empty_duration_threshold`, `_extract_audio_payload`, `_extract_transcript_text`, `_extract_segments`, `_has_meaningful_audio_segments`, `_scene_has_processing_error`, `_tail_text`, `_extract_labeled_output`, `_extract_step_failure_details`, `_classify_scene_content`, `_aggregate_content_summary`, `_coerce_nonnegative_int`, `_resolve_store_status_for_points`, `_aggregate_scene_store_status`, `_merge_store_statuses`, `_compute_sha256`, `_ensure_dir`, `_atomic_write_json`, `_write_cfg_snapshot`, `_normalize_host_profile_name`, `_load_host_runtime_overrides`, `_base_env`, `_persist_healer_retry_metadata`, `_record_run_warning`, `_record_healer_retry`, `_normalize_windows_status_code`, `_is_windows_native_crash`, `_record_native_retry`, `_run_step`, `_make_async_step_envelope`, `_run_step_async`, `_log_skipped_steps`, `_extract_keyframe`, `_extract_audio_chunk`, `_process_frame`, `_process_audio`, `_process_frame_async`, `_process_audio_async`, `_detect_scenes`, `_is_video_phase6_complete`, `run`
- **Imports**: `__future__.annotations`, `agents.control_agent.CONTROL_AGENT_DISABLED_REASON_NO_LLM_CLIENT`, `agents.control_agent.CONTROL_AGENT_STATUS_DISABLED_NO_LLM_CLIENT`, `agents.control_agent.ControlAgent`, `asyncio`, `cli.step_runner._derive_step_log_outcome`, `click`, `common.vram_allocator.STEP_VRAM_FRACTIONS`, `common.vram_allocator.VRAMAllocator`, `configs.python_paths.get_env_python`, `contextlib.contextmanager`, `datetime.datetime`, `datetime.timezone`, `hashlib`, `inspect`, `json`, `lib.kg_realtime_integration._resolve_graph_db_path`, `lib.kg_realtime_integration.build_scene_relationships`, `lib.kg_realtime_integration.update_kg_for_scene`, `lib.knowledge_graph.KnowledgeGraph`, `lib.llm_client.LLMClient`, `lib.observability.observer.PipelineObserver`, `logging`, `os`, `pathlib.Path`, `pipelines.direct_ingestion.run_direct_ingestion`, `re`, `scripts.wsl_audio_preflight.probe_wsl_audio_runtime`, `shutil`, `sqlite3`, `steps.audio.audio_wsl2_bridge.audio_unified_wsl2`, `steps.audio.segmentation.PhasedSegmentationEngine`, `steps.audio_transcribe.step.audio_transcribe`, `steps.common.atomic_io.atomic_write_json`, `steps.common.config_loader.get_runtime_paths`, `steps.common.config_loader.load_configs`, `steps.common.config_redaction.redact_config`, `steps.common.llm_model_factory.build_llm_models`, `steps.common.memory._make_id`, `steps.common.memory.ensure_scene`, `steps.common.memory.get_scene_meta`, `steps.common.memory.list_scenes_for_video`, `steps.common.memory.register_scene_bundle`, `steps.common.memory.scene_has_materialized`, `steps.common.profile_config.is_baseline`, `steps.common.profile_config.require_gpu`, `steps.common.profile_config.require_wsl_audio`, `steps.common.profile_config.wsl_audio_auto_enabled`, `steps.common.progress_tracker.finish_processing`, `steps.common.progress_tracker.get_tracker`, `steps.common.progress_tracker.set_total_steps`, `steps.common.progress_tracker.step_context`, `steps.common.progress_tracker.update_step`, `steps.common.step_logger.log_step_run`, `steps.common.tag_utils.canonicalize_taxonomy`, `steps.common.tag_utils.is_valid_entity_token`, `steps.common.tag_utils.merge_tag_sources`, `steps.common.tag_utils.normalize_entity_token`, `steps.common.tool_paths.resolve_conda`, `steps.common.tool_paths.resolve_ffmpeg`, `steps.video.entity_extractor.extract_entities_from_scene`, `steps.video_summarizer.step.run_step`, `subprocess`, `sys`, `tempfile`, `time`, `typer`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Set`, `uuid`

### [step_runner.py](file:///L:/GOODCUBE/projects/goodq4all/cli/step_runner.py)
- **Relative Path**: `cli/step_runner.py`
- **Functions**: `apply_step_runtime_guards`, `_emit_subprocess_env_fingerprint`, `load_cfg`, `_save_memory_context`, `_derive_step_log_outcome`, `run_step`, `main`
- **Imports**: `__future__.annotations`, `argparse`, `common.gpu_manager.initialize_gpu_for_step`, `hashlib`, `json`, `logging`, `os`, `pathlib.Path`, `steps.audio.segmentation.phase5_video_scene_integration.process_video_chunks_with_scenes`, `steps.audio_diarize.step_wsl2.audio_diarize`, `steps.audio_embed_clap.step.audio_embed_clap`, `steps.audio_emotion.step.audio_emotion`, `steps.audio_metadata.step.audio_metadata`, `steps.audio_music_events.step.audio_music_events`, `steps.audio_speaker_merge.step.audio_speaker_merge`, `steps.audio_time_hints.step.audio_time_hints`, `steps.audio_transcribe.step_wsl2.audio_transcribe`, `steps.common.config_loader.load_configs`, `steps.common.memory_context_writer.save_step_context`, `steps.common.step_logger.log_step_run`, `steps.emotion_classify.step.emotion_classify`, `steps.face_embed.step.face_embed`, `steps.home_assistant_status.step.home_assistant_status`, `steps.image_caption.step.image_caption`, `steps.image_embed_clip.step.image_embed_clip`, `steps.image_embed_dino.step.image_embed_dino`, `steps.image_exif.step.image_exif`, `steps.image_ocr.step.image_ocr`, `steps.object_detect.step.object_detect`, `steps.object_track.step.object_track`, `steps.object_track_yolo.step.object_track_yolo`, `steps.pdf_text.step.pdf_to_text`, `steps.sentiment.step.sentiment`, `steps.system_metrics.step.system_metrics`, `steps.tagger.step.tagger`, `steps.text_embed.step.text_embed`, `steps.video.cross_modal_harmonizer.run_cross_modal_harmonization`, `steps.video.scene_visual_embeddings.run_scene_visual_embeddings`, `steps.video_scene_detect.step.video_scene_detect`, `sys`, `time`, `typing.Any`, `typing.Dict`, `typing.List`

### [system_status.py](file:///L:/GOODCUBE/projects/goodq4all/cli/system_status.py)
- **Relative Path**: `cli/system_status.py`
- **Functions**: `check_environment`, `check_config`, `check_directories`, `check_recent_ingestions`, `main`
- **Imports**: `__future__.annotations`, `json`, `logging`, `os`, `pathlib.Path`, `steps.common.config_loader.get_runtime_paths`, `steps.common.config_loader.load_configs`, `sys`, `typing.Any`, `typing.Dict`

### [test_ingestion.py](file:///L:/GOODCUBE/projects/goodq4all/cli/test_ingestion.py)
- **Relative Path**: `cli/test_ingestion.py`
- **Functions**: `test_config_loading`, `test_step_imports`, `test_sample_ingestion`, `test_artifacts`, `test_temporal_index_structure`, `test_retrieval`, `main`
- **Imports**: `__future__.annotations`, `json`, `pathlib.Path`, `pipelines.direct_ingestion.run_direct_ingestion`, `retrieval.multimodal_search.MultimodalSearchEngine`, `steps.common.config_loader.load_configs`, `sys`, `time`, `traceback`, `typing.Any`, `typing.Dict`

### [ui_conduits_rollup.py](file:///L:/GOODCUBE/projects/goodq4all/cli/ui_conduits_rollup.py)
- **Relative Path**: `cli/ui_conduits_rollup.py`
- **Classes**: `_VideoFlags`
- **Functions**: `_load_configs`, `_cfg_paths`, `_best_effort_wal`, `_ensure_scene_modality_coverage_semantics`, `_posix`, `_wsl_mount_path`, `_tokenize_under_processing_root`, `_read_json`, `_discover_processing_artifacts`, `_update_scene_modality_coverage`, `_update_scene_index_public`, `main`
- **Imports**: `__future__.annotations`, `argparse`, `contextlib`, `dataclasses.dataclass`, `io`, `json`, `media_refs.tokenize_processing_path`, `os`, `re`, `sqlite3`, `steps.common.config_loader.load_configs`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.List`, `typing.Optional`, `typing.Sequence`, `typing.Tuple`

### [watchdog.py](file:///L:/GOODCUBE/projects/goodq4all/cli/watchdog.py)
- **Relative Path**: `cli/watchdog.py`
- **Classes**: `ASCIIFilter`, `FileState`, `ProcessedRegistry`, `WatchdogProcessor`
- **Functions**: `safe_move_file`, `_resolve_watchdog_paths`, `_configure_watchdog_logging`, `_pid_exists`, `_check_system_restart_events`, `main`
- **Imports**: `__future__.annotations`, `agents.control_agent.CONTROL_AGENT_DISABLED_REASON_NO_LLM_CLIENT`, `agents.control_agent.CONTROL_AGENT_STATUS_DISABLED_NO_LLM_CLIENT`, `agents.control_agent.ControlAgent`, `datetime.datetime`, `datetime.timezone`, `hashlib`, `json`, `logging`, `os`, `pathlib.Path`, `pipelines.direct_ingestion.run_direct_ingestion`, `psutil`, `queue.Empty`, `queue.Queue`, `shutil`, `steps.common.atomic_io.atomic_write_json`, `steps.common.conda_runner.StepExecutionError`, `steps.common.conda_runner.run_conda_step`, `steps.common.config_loader.get_runtime_paths`, `steps.common.config_loader.load_configs`, `steps.common.progress_tracker.add_error`, `steps.common.progress_tracker.finish_processing`, `steps.common.progress_tracker.start_processing`, `steps.common.tag_utils.canonicalize_taxonomy`, `subprocess`, `sys`, `tempfile`, `threading.Event`, `threading.RLock`, `threading.Thread`, `time`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Set`, `uuid`

## Subsystem: `common`

### [gpu_manager.py](file:///L:/GOODCUBE/projects/goodq4all/common/gpu_manager.py)
- **Relative Path**: `common/gpu_manager.py`
- **Classes**: `GPUManager`
- **Functions**: `get_gpu_manager`, `initialize_gpu_for_step`
- **Imports**: `logging`, `os`, `pathlib.Path`, `steps.common.device_config.device_config`, `subprocess`, `torch`, `typing.Any`, `typing.Dict`, `typing.Optional`

### [gpu_monitor.py](file:///L:/GOODCUBE/projects/goodq4all/common/gpu_monitor.py)
- **Relative Path**: `common/gpu_monitor.py`
- **Functions**: `get_gpu_processes`, `get_gpu_stats`, `log_gpu_status`, `monitor_gpu`, `get_gpu_availability`
- **Imports**: `argparse`, `datetime.datetime`, `json`, `logging`, `pathlib.Path`, `subprocess`, `time`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [progress_tracker.py](file:///L:/GOODCUBE/projects/goodq4all/common/progress_tracker.py)
- **Relative Path**: `common/progress_tracker.py`
- **Classes**: `ProgressTracker`
- **Functions**: `get_progress_tracker`
- **Imports**: `__future__.annotations`, `configs.paths.LOGS_DIR`, `datetime.datetime`, `json`, `logging`, `pathlib.Path`, `threading.Lock`, `time`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [vram_allocator.py](file:///L:/GOODCUBE/projects/goodq4all/common/vram_allocator.py)
- **Relative Path**: `common/vram_allocator.py`
- **Classes**: `FileLock`, `VRAMAllocator`
- **Functions**: `_get_registry_dir`, `pid_exists`
- **Imports**: `json`, `logging`, `os`, `pathlib.Path`, `psutil`, `steps.common.atomic_io.atomic_write_json`, `subprocess`, `threading`, `time`, `typing.Any`, `typing.Dict`, `typing.Tuple`

## Subsystem: `configs`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/configs/__init__.py)
- **Relative Path**: `configs/__init__.py`
- **Imports**: `python_paths.get_conda_exe`, `python_paths.get_conda_run_command`, `python_paths.get_config`, `python_paths.get_env_python`, `python_paths.initialize_paths`, `python_paths.validate_env`

### [paths.py](file:///L:/GOODCUBE/projects/goodq4all/configs/paths.py)
- **Relative Path**: `configs/paths.py`
- **Functions**: `drive_path`, `ensure_directories`, `get_processing_dir`, `get_completed_dir`, `set_environment_variables`
- **Imports**: `__future__.annotations`, `os`, `pathlib.Path`, `steps.common.config_loader.get_runtime_paths`, `steps.common.config_loader.load_configs`, `steps.common.platform_config.PlatformHelper`

### [python_paths.py](file:///L:/GOODCUBE/projects/goodq4all/configs/python_paths.py)
- **Relative Path**: `configs/python_paths.py`
- **Classes**: `PythonPathConfig`
- **Functions**: `get_config`, `initialize_paths`, `get_conda_exe`, `get_env_python`, `get_conda_run_command`, `validate_env`
- **Imports**: `logging`, `os`, `pathlib.Path`, `platform`, `shutil`, `sys`, `typing.Dict`, `typing.Optional`

## Subsystem: `lib`

### [control_recurrence_hygiene.py](file:///L:/GOODCUBE/projects/goodq4all/lib/control_recurrence_hygiene.py)
- **Relative Path**: `lib/control_recurrence_hygiene.py`
- **Functions**: `audit_control_recurrence_path_hygiene`, `_scan_named_texts`, `_read_text_or_value`, `_contains_local_path_pattern`
- **Imports**: `__future__.annotations`, `pathlib.Path`, `re`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.List`, `typing.Mapping`, `typing.Optional`

### [control_recurrence_index.py](file:///L:/GOODCUBE/projects/goodq4all/lib/control_recurrence_index.py)
- **Relative Path**: `lib/control_recurrence_index.py`
- **Functions**: `list_report_index`, `latest_report_entry`, `load_report_json`, `load_report_markdown`, `_resolve_report_dir`, `_lookup_entry`, `_validate_report_id`, `_resolve_artifact_path`, `_entry_sort_time`, `_parse_datetime`, `_problem`, `_sanitize_payload`, `_sanitize_text`, `_portable_path_text`, `_looks_like_absolute_path`
- **Imports**: `__future__.annotations`, `datetime.datetime`, `datetime.timezone`, `json`, `os`, `pathlib.Path`, `re`, `typing.Any`, `typing.Dict`, `typing.Optional`, `typing.Tuple`

### [control_recurrence_recommendations.py](file:///L:/GOODCUBE/projects/goodq4all/lib/control_recurrence_recommendations.py)
- **Relative Path**: `lib/control_recurrence_recommendations.py`
- **Functions**: `build_recommendation_draft`, `build_recommendation_draft_from_report`, `render_recommendation_draft`, `_report_type`, `_recommendation`, `_classification`, `_health`, `_family_rows`, `_recovery_counts`, `_highest_category`, `_blocking_summary`, `_top_operator_priorities`, `_inspection_plan`, `_defer_mutation_reason`, `_families_at_or_above`, `_family_priority_lines`, `_hint_lines`, `_step_names`, `_family_label`, `_phase6_status`, `_qdrant_status`, `_sum_by_prefix`, `_nested`, `_dedupe`
- **Imports**: `__future__.annotations`, `lib.control_recurrence_index`, `pathlib.Path`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.List`, `typing.Tuple`

### [control_recurrence_report.py](file:///L:/GOODCUBE/projects/goodq4all/lib/control_recurrence_report.py)
- **Relative Path**: `lib/control_recurrence_report.py`
- **Classes**: `_EpisodeScope`
- **Functions**: `build_control_recurrence_report`, `build_control_recurrence_comparison`, `render_text_report`, `render_text_comparison`, `_text_step_latency_summary`, `_text_step_latency_delta`, `_text_environment_summary`, `_text_optional_enrichment_coverage`, `_text_optional_enrichment_coverage_delta`, `write_markdown_report`, `write_json_report_file`, `update_report_index`, `report_index_path`, `read_report_index`, `render_report_index`, `render_markdown_report`, `_render_markdown_single`, `_render_markdown_comparison`, `_markdown_read_only_disclaimer`, `_markdown_recommendation`, `_markdown_category_counts`, `_markdown_recovery_counts`, `_markdown_step_latency_summary`, `_markdown_environment_summary`, `_markdown_optional_enrichment_coverage`, `_markdown_recovery_delta_counts`, `_markdown_step_latency_delta`, `_markdown_optional_enrichment_coverage_delta`, `_markdown_phase6_health`, `_markdown_qdrant_health`, `_markdown_phase6_delta`, `_markdown_qdrant_delta`, `_markdown_top_families`, `_markdown_comparison_family_changes`, `_markdown_blocking_signals`, `_candidate_family_rows_from_comparison`, `_markdown_filename`, `_json_filename`, `_artifact_stem`, `_single_report_run_id`, `_md_filename_part`, `_md_join_code`, `_md_join_code_paths`, `_markdown_bullets`, `_md_cell`, `_md_text`, `_md_path_text`, `_resolve_output_dir`, `_portable_artifact_payload`, `_portable_path_text`, `_looks_like_absolute_path`, `_artifact_path_text`, `_index_entry_from_report`, `_index_entry_from_markdown_path`, `_report_type`, `_report_id`, `_index_highest_category`, `_index_total_signals`, `_index_blocking_signal_count`, `_index_phase6_health_summary`, `_index_qdrant_health_summary`, `_file_mtime_utc`, `_comparison_run_summary`, `_family_counts`, `_merged_family_categories`, `_attach_delta_categories`, `_category_counts_delta`, `_signal_counts_by`, `_episode_video_counts`, `_safe_int_map`, `_count_delta_map`, `_delta_rows`, `_health_delta`, `_episode_dimension_healthy`, `_health_episode_label`, `_attach_family_categories`, `_attach_operator_hints_to_families`, `_operator_hint_bundle`, `_report_operator_guidance`, `_guidance_from_report`, `_category_by_family`, `_attach_row_categories`, `_attach_scene_categories`, `_classification_summary`, `_recommendation_from_classification`, `_classify_family_category`, `_family_category_from_classification`, `_comparison_recommendation`, `_is_informational_family`, `_is_sharp_increase`, `_select_run_roots`, `_load_run_scope`, `_load_direct_run_scope`, `_first_existing_run_path`, `_load_episode_artifact_signals`, `_episode_scene_identity_sets`, `_warning_applies_to_episode`, `_select_episode_result_item`, `_load_runtime_event_signals`, `_runtime_event_applies_to_episode`, `_load_stderr_native_retry_signals`, `_is_optional_runtime_step`, `_parse_native_crash_stderr_line`, `_native_retry_mode_from_text`, `_clean_step_name`, `_return_code_from_error`, `_normalize_status_code_hex`, `_find_runtime_retry_event`, `_artifact_presence_signals`, `_artifact_health_signals`, `_artifact_signal`, `_select_scene_status_surface`, `_load_step_run_signals`, `_latency_from_step_row`, `_coverage_from_step_row`, `_signal_from_step_row`, `_signal_from_run_warning`, `_signals_from_scene_statuses`, `_scene_signal`, `_episode_health`, `_group_signals`, `_top_families`, `_optional_enrichment_skips`, `_optional_enrichment_coverage`, `_optional_enrichment_step_coverage`, `_environment_summary`, `_parse_env_fingerprint`, `_sanitized_env_fingerprint_values`, `_recovery_counts`, `_scenes_affected`, `_step_latency_summary`, `_summarize_latency_step`, `_latency_row_excerpt`, `_latency_delta`, `_optional_enrichment_coverage_delta`, `_optional_coverage_steps_by_name`, `_coverage_delta_status`, `_latency_steps_by_name`, `_latency_trend_status`, `_is_wsl_audio_step`, `_phase6_health_summary`, `_infer_recovery_outcome`, `_later_ok_step`, `_classify_error_family`, `_extract_reason`, `_first_nested_reason`, `_first_nested_status`, `_load_result_items`, `_load_json`, `_path_from`, `_derive_manifest_path`, `_display_path`, `_display_text`, `_sanitize_drive_root`, `_unique_episode_map`, `_replace_episode_step_path`, `_clean_str`, `_coerce_int`, `_coerce_float`, `_round_ms`, `_delta_ms`, `_percentile`, `_format_ms_text`, `_format_ms_cell`, `_nested_get`, `_all_known_true`, `_len_list`, `_dedupe_strings`, `_coalesce_runtime_event_duplicates`, `_is_native_crash_signal`, `_native_run_level_key`, `_native_coalesce_key`, `_native_retry_mode`, `_native_retry_mode_for_scene`, `_native_family_code`, `_native_recovery_class`, `_merge_native_crash_signals`, `_preferred_native_signal`, `_preferred_recovered_outcome`, `_signal_surface_names`, `_is_scene_less_native_retry_signal`, `_dedupe_paths`, `_dedupe_signals`, `_text_row_defaults`
- **Imports**: `__future__.annotations`, `collections.Counter`, `dataclasses.dataclass`, `datetime.datetime`, `datetime.timezone`, `json`, `lib.run_index`, `os`, `pathlib.Path`, `re`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.List`, `typing.Optional`, `typing.Sequence`, `typing.Tuple`

### [control_recurrence_trend.py](file:///L:/GOODCUBE/projects/goodq4all/lib/control_recurrence_trend.py)
- **Relative Path**: `lib/control_recurrence_trend.py`
- **Functions**: `build_control_recurrence_trend`, `render_text_trend`, `_timeline_row_from_entry`, `_derive_scope_signature`, `_comparable_groups`, `_family_trends`, `_category_trends`, `_recovery_trends`, `_health_trends`, `_latency_trends`, `_recommendation_history`, `_report_window`, `_trend_status`, `_family_counts`, `_family_row`, `_family_category`, `_category_counts`, `_recovery_counts`, `_health_count`, `_health_status`, `_latency_timeline_summary`, `_latency_steps`, `_latency_trend_label`, `_trend_label`, `_timeline_sort_key`, `_parse_time`, `_report_type`, `_single_run_id`, `_recommendation`, `_recommendation_status`, `_highest_category`, `_schema_version`, `_list_from_nested`, `_nested`, `_safe_int`, `_safe_float`, `_round_ms`, `_delta_ms`, `_dedupe`
- **Imports**: `__future__.annotations`, `collections.defaultdict`, `datetime.datetime`, `datetime.timezone`, `lib.control_recurrence_index`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.List`, `typing.Optional`, `typing.Tuple`

### [goodq_logger.py](file:///L:/GOODCUBE/projects/goodq4all/lib/goodq_logger.py)
- **Relative Path**: `lib/goodq_logger.py`
- **Classes**: `MissionColors`, `MissionFormatter`, `GoodQLogger`, `QuickMission`
- **Functions**: `get_goodq_logger`, `get_default_logger`
- **Imports**: `__future__.annotations`, `configs.paths.LOGS_DIR`, `contextlib.contextmanager`, `datetime.datetime`, `logging`, `pathlib.Path`, `sys`, `time`, `tqdm.contrib.logging.logging_redirect_tqdm`, `tqdm.tqdm`, `typing.Any`, `typing.Dict`, `typing.Optional`, `typing.Union`

### [identity_ledger.py](file:///L:/GOODCUBE/projects/goodq4all/lib/identity_ledger.py)
- **Relative Path**: `lib/identity_ledger.py`
- **Functions**: `_utc_now_iso`, `_load_json`, `_flatten_scene_payload`, `rebuild_identity_graph_from_manifests`, `_parse_properties`, `_dedupe_supporting_evidence`, `build_identity_ledger`, `write_identity_ledger_markdown`, `load_manual_mappings`, `save_manual_mappings`, `apply_manual_mappings`
- **Imports**: `__future__.annotations`, `collections.Counter`, `collections.defaultdict`, `datetime.datetime`, `datetime.timezone`, `json`, `lib.kg_realtime_integration.update_kg_for_scene`, `lib.knowledge_graph.KnowledgeGraph`, `pathlib.Path`, `sqlite3`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.List`, `typing.Tuple`

### [kg_realtime_integration.py](file:///L:/GOODCUBE/projects/goodq4all/lib/kg_realtime_integration.py)
- **Relative Path**: `lib/kg_realtime_integration.py`
- **Functions**: `_cfg_get`, `_resolve_graph_db_path`, `_iter_str_list`, `normalize_entity_name`, `_is_valid_entity_token`, `_is_likely_character_name`, `_is_weak_identity_promotion_name`, `_scene_text_for_identity`, `_count_identity_name_mentions`, `_contextually_reject_weak_identity_name`, `_weak_identity_candidate_allowed`, `_identity_scene_excerpt`, `_speaker_transcript_excerpt`, `_speaker_duration_share`, `_speaker_name_alignment_excerpt`, `_coerce_embedding`, `_normalize_embedding`, `_cosine_similarity`, `_speaker_voice_signature_map`, `_speaker_pattern_name`, `_upsert_speaker_pattern_node`, `_identity_support_scene_threshold`, `_dedupe_identity_evidence_items`, `_append_identity_candidate_edge`, `_resolve_identity_name`, `_is_meaningful_generic_entity`, `_is_synthetic_speaker_label`, `_scene_scoped_synthetic_speaker_name`, `_parse_edge_properties`, `_has_conflicting_identity_support`, `_accumulate_identity_candidate_support`, `_accumulate_identity_supported_evidence`, `_entity_type_priority`, `_iter_entity_items`, `_collapse_entity_items`, `_extract_location_labels`, `_extract_speaker_ids`, `_preferred_entity_node_type`, `_add_scene_entities`, `build_scene_relationships`, `update_kg_for_scene`
- **Imports**: `__future__.annotations`, `json`, `lib.knowledge_graph.KnowledgeGraph`, `math`, `pathlib.Path`, `re`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.List`, `typing.Optional`

### [knowledge_graph.py](file:///L:/GOODCUBE/projects/goodq4all/lib/knowledge_graph.py)
- **Relative Path**: `lib/knowledge_graph.py`
- **Classes**: `KnowledgeGraph`
- **Functions**: `_utc_now_iso`, `_json_dumps`, `_json_loads`
- **Imports**: `__future__.annotations`, `datetime.datetime`, `datetime.timezone`, `json`, `pathlib.Path`, `sqlite3`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.List`, `typing.Optional`

### [llm_client.py](file:///L:/GOODCUBE/projects/goodq4all/lib/llm_client.py)
- **Relative Path**: `lib/llm_client.py`
- **Classes**: `ModelConfig`, `HealthStatus`, `LLMClient`
- **Functions**: `get_client`, `chat`, `get_status`
- **Imports**: `dataclasses.dataclass`, `dataclasses.field`, `datetime.datetime`, `datetime.timedelta`, `json`, `logging`, `os`, `pathlib.Path`, `requests`, `subprocess`, `sys`, `time`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Literal`, `typing.Optional`

### [mission_components.py](file:///L:/GOODCUBE/projects/goodq4all/lib/mission_components.py)
- **Relative Path**: `lib/mission_components.py`
- **Functions**: `get_component_name`, `get_progress_description`, `format_duration`, `format_file_size`
- **Imports**: `typing.Dict`

### [model_lifecycle.py](file:///L:/GOODCUBE/projects/goodq4all/lib/model_lifecycle.py)
- **Relative Path**: `lib/model_lifecycle.py`
- **Classes**: `ModelLifecycleManager`, `ModelContext`
- **Imports**: `__future__.annotations`, `gc`, `logging`, `os`, `pathlib.Path`, `subprocess`, `sys`, `time`, `torch`, `typing.Any`, `typing.Callable`, `typing.Dict`, `typing.Optional`, `typing.Set`, `yaml`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/lib/observability/__init__.py)
- **Relative Path**: `lib/observability/__init__.py`
- **Imports**: `lib.observability.observer.PipelineObserver`

### [event_types.py](file:///L:/GOODCUBE/projects/goodq4all/lib/observability/event_types.py)
- **Relative Path**: `lib/observability/event_types.py`
- **Imports**: `__future__.annotations`, `typing.Literal`

### [observer.py](file:///L:/GOODCUBE/projects/goodq4all/lib/observability/observer.py)
- **Relative Path**: `lib/observability/observer.py`
- **Classes**: `_StepState`, `PipelineObserver`
- **Functions**: `_env_with_alias`, `_parse_bool_env`, `_parse_float_env`
- **Imports**: `__future__.annotations`, `dataclasses.dataclass`, `json`, `lib.observability.event_types.HEARTBEAT`, `lib.observability.event_types.STEP_END`, `lib.observability.event_types.STEP_ERROR`, `lib.observability.event_types.STEP_PROGRESS`, `lib.observability.event_types.STEP_START`, `os`, `sys`, `threading`, `time`, `tqdm.tqdm`, `typing.Any`, `typing.Callable`, `typing.Dict`, `typing.Optional`

### [persistent_store_alignment.py](file:///L:/GOODCUBE/projects/goodq4all/lib/persistent_store_alignment.py)
- **Relative Path**: `lib/persistent_store_alignment.py`
- **Functions**: `build_persistent_store_alignment`, `_canonical_scene_scope`, `_result_items`, `_canonical_scenes_from_item`, `_memory_alignment`, `_kg_alignment`, `_tables`, `_existing_scene_ids`, `_count_by_scene_ids`, `_counts_by_modality`, `_commit_events_by_modality`, `_count_node_media_links`, `_chunks`, `_read_json`, `_without_internal_scene_ids`, `_clean_str`
- **Imports**: `__future__.annotations`, `json`, `pathlib.Path`, `sqlite3`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.List`, `typing.Optional`, `typing.Sequence`, `typing.Set`, `typing.Tuple`

### [run_index.py](file:///L:/GOODCUBE/projects/goodq4all/lib/run_index.py)
- **Relative Path**: `lib/run_index.py`
- **Functions**: `resolve_reports_root`, `get_run_root`, `list_runs`, `_load_json`, `_load_json_any`, `_build_run_index_entry`, `_build_standalone_scene_results_entry`, `_find_interrupted_config`, `_build_interrupted_ingestion_entry`, `_iter_scene_result_items`, `_count_scene_results`, `_scene_results_video_names`, `_first_text`, `_normalized_collection_map`, `_count_episode_statuses`, `_select_latest_episode`, `_project_plan_item_status`, `_read_episode_record_status`, `_has_active_lane_artifacts`
- **Imports**: `__future__.annotations`, `json`, `logging`, `os`, `pathlib.Path`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.Iterator`, `typing.List`, `typing.Optional`

### [run_narrative.py](file:///L:/GOODCUBE/projects/goodq4all/lib/run_narrative.py)
- **Relative Path**: `lib/run_narrative.py`
- **Functions**: `build_run_narrative`, `render_run_narrative`, `_value_or_unknown`, `_count_or_unknown`, `_format_outcome`
- **Imports**: `__future__.annotations`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [run_summary.py](file:///L:/GOODCUBE/projects/goodq4all/lib/run_summary.py)
- **Relative Path**: `lib/run_summary.py`
- **Functions**: `load_run_summary`, `_load_standalone_scene_results_summary`, `_load_interrupted_ingestion_summary`, `_resolve_run_root`, `_load_json`, `_find_interrupted_config`, `_load_episode_record`, `_classify_outcome`, `_is_newer`, `_duration_seconds`, `_parse_iso`, `_dedupe_preserve_order`
- **Imports**: `__future__.annotations`, `datetime.datetime`, `json`, `lib.run_index`, `logging`, `pathlib.Path`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [summary_aggregator.py](file:///L:/GOODCUBE/projects/goodq4all/lib/summary_aggregator.py)
- **Relative Path**: `lib/summary_aggregator.py`
- **Functions**: `_utc_now_iso`, `_get_stable_entity_id`, `_parse_stable_entity_id`, `_classify_occasion_type`, `get_scope_metadata`, `get_summary_dashboard`, `get_entity_profile`, `load_collections`, `save_collections`, `add_collection`, `soft_delete_collection`
- **Imports**: `__future__.annotations`, `api.utils.loaders.DataLoader`, `datetime.datetime`, `datetime.timezone`, `json`, `logging`, `pathlib.Path`, `sqlite3`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`

## Subsystem: `pipelines`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/pipelines/__init__.py)
- **Relative Path**: `pipelines/__init__.py`

### [direct_ingestion.py](file:///L:/GOODCUBE/projects/goodq4all/pipelines/direct_ingestion.py)
- **Relative Path**: `pipelines/direct_ingestion.py`
- **Functions**: `_resolve_processing_root`, `run_direct_ingestion`
- **Imports**: `__future__.annotations`, `cli.run_ingestion.run`, `configs.paths.LOGS_DIR`, `goodq4all.cli.run_ingestion.run`, `json`, `logging`, `os`, `pathlib.Path`, `shutil`, `steps.common.config_loader.load_configs`, `sys`, `typer`, `typing.Any`, `typing.Dict`

## Subsystem: `retrieval`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/retrieval/__init__.py)
- **Relative Path**: `retrieval/__init__.py`
- **Imports**: `retrieval.multimodal_search.MultimodalSearchEngine`, `retrieval.multimodal_search.multimodal_search`

### [multimodal_search.py](file:///L:/GOODCUBE/projects/goodq4all/retrieval/multimodal_search.py)
- **Relative Path**: `retrieval/multimodal_search.py`
- **Classes**: `MultimodalSearchEngine`
- **Functions**: `_default_data_root`, `_classify_audio_text_encoder_error`, `_configure_clap_text_model_env`, `_resolve_local_clap_model_dir`, `multimodal_search`, `main`
- **Imports**: `__future__.annotations`, `argparse`, `goodq4all.steps.common.config_loader.load_configs`, `json`, `logging`, `numpy`, `os`, `pathlib.Path`, `re`, `sentence_transformers.SentenceTransformer`, `sqlite3`, `steps.common.config_loader.load_configs`, `steps.common.profile_config.gpu_auto_config_enabled`, `steps.common.qdrant_client.QdrantClient`, `steps.common.qdrant_client.QdrantConfig`, `steps.common.retrieval_events.retrieval_events_enabled`, `sys`, `torch`, `transformers.AutoProcessor`, `transformers.CLIPModel`, `transformers.CLIPProcessor`, `transformers.ClapModel`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`, `yaml`

### [narrative_summarizer.py](file:///L:/GOODCUBE/projects/goodq4all/retrieval/narrative_summarizer.py)
- **Relative Path**: `retrieval/narrative_summarizer.py`
- **Functions**: `clean_scene_description`, `parse_narrative_segments`, `synthesize_narrative`
- **Imports**: `__future__.annotations`, `lib.llm_client.LLMClient`, `logging`, `re`, `retrieval.temporal_reasoning.temporal_search`, `steps.common.config_loader.load_configs`, `steps.common.llm_model_factory.build_llm_models`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [temporal_reasoning.py](file:///L:/GOODCUBE/projects/goodq4all/retrieval/temporal_reasoning.py)
- **Relative Path**: `retrieval/temporal_reasoning.py`
- **Functions**: `get_scene_date_range`, `load_scene_to_file_mapping`, `get_scene_vector`, `compute_similarity`, `temporal_search`
- **Imports**: `__future__.annotations`, `json`, `logging`, `numpy`, `os`, `pathlib.Path`, `re`, `requests`, `sqlite3`, `steps.common.config_loader.get_runtime_paths`, `steps.common.config_loader.load_configs`, `steps.common.qdrant_client.QdrantClient`, `steps.common.qdrant_client.QdrantConfig`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

## Subsystem: `steps`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/__init__.py)
- **Relative Path**: `steps/__init__.py`

## Subsystem: `steps/audio`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio/__init__.py)
- **Relative Path**: `steps/audio/__init__.py`

### [audio_wsl2_bridge.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio/audio_wsl2_bridge.py)
- **Relative Path**: `steps/audio/audio_wsl2_bridge.py`
- **Functions**: `audio_diarize_wsl2`, `audio_transcribe_wsl2`, `audio_emotion_wsl2`, `audio_unified_wsl2`
- **Imports**: `logging`, `pathlib.Path`, `sys`, `wsl2_audio_bridge.WSL2AudioBridge`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio/segmentation/__init__.py)
- **Relative Path**: `steps/audio/segmentation/__init__.py`
- **Imports**: `orchestrator.PhasedSegmentationEngine`, `orchestrator.create_default_config`, `phase0_normalization.extract_metadata`, `phase0_normalization.normalize_media`, `phase1_vad_segmentation.segment_with_webrtc_vad`, `phase2_pyannote.enhance_segments_with_pyannote`, `phase2_pyannote.segment_with_pyannote`, `phase3_chunk_builder.run_phase3_chunk_builder`, `phase4_audio_processor.Phase4AudioProcessor`, `phase4_audio_processor.process_segmented_audio`, `phase5_video_scene_integration.align_scenes_with_audio_segments`, `phase5_video_scene_integration.detect_scenes_for_chunk`, `phase5_video_scene_integration.process_video_chunks_with_scenes`, `phase5_video_scene_integration.upgrade_analysis_for_legacy_scene_detect`, `phase6_integration.generate_segmentation_manifest`, `phase6_integration.merge_all_segment_data`, `phase6_integration.validate_manifest`

### [orchestrator.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio/segmentation/orchestrator.py)
- **Relative Path**: `steps/audio/segmentation/orchestrator.py`
- **Classes**: `PhasedSegmentationEngine`
- **Functions**: `create_default_config`
- **Imports**: `__future__.annotations`, `json`, `os`, `pathlib.Path`, `phase0_normalization.extract_metadata`, `phase0_normalization.normalize_media`, `phase1_vad_segmentation.segment_with_webrtc_vad`, `phase2_pyannote.enhance_segments_with_pyannote`, `phase2_pyannote.segment_with_pyannote`, `phase3_chunk_builder.run_phase3_chunk_builder`, `phase4_audio_processor.Phase4AudioProcessor`, `phase4_audio_processor.process_segmented_audio`, `phase5_video_scene_integration.process_video_chunks_with_scenes`, `phase5_video_scene_integration.upgrade_analysis_for_legacy_scene_detect`, `phase6_integration.generate_segmentation_manifest`, `phase6_integration.merge_all_segment_data`, `phase6_integration.validate_manifest`, `time`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [phase0_normalization.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio/segmentation/phase0_normalization.py)
- **Relative Path**: `steps/audio/segmentation/phase0_normalization.py`
- **Functions**: `normalize_media`, `extract_metadata`
- **Imports**: `__future__.annotations`, `json`, `os`, `subprocess`, `typing.Any`, `typing.Dict`, `typing.Optional`

### [phase1_vad_segmentation.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio/segmentation/phase1_vad_segmentation.py)
- **Relative Path**: `steps/audio/segmentation/phase1_vad_segmentation.py`
- **Functions**: `segment_with_webrtc_vad`, `_fill_gaps`, `_fallback_full_segment`
- **Imports**: `__future__.annotations`, `struct`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `wave`, `webrtcvad`

### [phase2_pyannote.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio/segmentation/phase2_pyannote.py)
- **Relative Path**: `steps/audio/segmentation/phase2_pyannote.py`
- **Functions**: `run_pyannote_segmentation`, `merge_vad_and_pyannote`, `segment_with_pyannote`, `enhance_segments_with_pyannote`
- **Imports**: `json`, `logging`, `os`, `pathlib.Path`, `pyannote.audio.Audio`, `pyannote.audio.Model`, `pyannote.audio.pipelines.SpeakerSegmentation`, `sys`, `tempfile`, `torch`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [phase3_chunk_builder.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio/segmentation/phase3_chunk_builder.py)
- **Relative Path**: `steps/audio/segmentation/phase3_chunk_builder.py`
- **Classes**: `ChunkBuilder`
- **Functions**: `run_phase3_chunk_builder`
- **Imports**: `json`, `numpy`, `os`, `pathlib.Path`, `soundfile`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Tuple`, `wave`

### [phase4_audio_processor.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio/segmentation/phase4_audio_processor.py)
- **Relative Path**: `steps/audio/segmentation/phase4_audio_processor.py`
- **Classes**: `Phase4AudioProcessor`
- **Functions**: `process_segmented_audio`
- **Imports**: `__future__.annotations`, `argparse`, `concurrent.futures.ThreadPoolExecutor`, `concurrent.futures.as_completed`, `json`, `logging`, `os`, `pathlib.Path`, `sys`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `wsl2_audio.audio_bridge.transcribe_and_diarize_wsl2`, `wsl2_audio.audio_bridge.transcribe_wsl2`, `yaml`

### [phase5_video_scene_integration.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio/segmentation/phase5_video_scene_integration.py)
- **Relative Path**: `steps/audio/segmentation/phase5_video_scene_integration.py`
- **Functions**: `detect_scenes_for_chunk`, `align_scenes_with_audio_segments`, `process_video_chunks_with_scenes`, `upgrade_analysis_for_legacy_scene_detect`
- **Imports**: `__future__.annotations`, `cv2`, `json`, `numpy`, `os`, `pathlib.Path`, `torch`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [phase6_integration.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio/segmentation/phase6_integration.py)
- **Relative Path**: `steps/audio/segmentation/phase6_integration.py`
- **Functions**: `merge_all_segment_data`, `create_frame_index`, `generate_segmentation_manifest`, `validate_manifest`
- **Imports**: `__future__.annotations`, `datetime.datetime`, `json`, `os`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

## Subsystem: `steps/audio_diarize`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio_diarize/__init__.py)
- **Relative Path**: `steps/audio_diarize/__init__.py`
- **Imports**: `step.audio_diarize`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio_diarize/step.py)
- **Relative Path**: `steps/audio_diarize/step.py`
- **Functions**: `_resolve_device`, `_load_pipeline`, `_get_audio_duration`, `_extract_audio_chunk`, `_merge_speaker_segments`, `_format_segments`, `audio_diarize`
- **Imports**: `__future__.annotations`, `librosa`, `logging`, `math`, `numpy`, `os`, `pathlib.Path`, `pyannote.audio.Pipeline`, `pyannote.audio.pipelines.OverlappedSpeechDetection`, `pyannote.audio.pipelines.Resegmentation`, `soundfile`, `steps.audio_diarize.vad_preprocessor.calculate_time_savings`, `steps.audio_diarize.vad_preprocessor.preprocess_audio_with_vad`, `steps.common.audio_gpu_optimizer.get_audio_gpu_optimizer`, `steps.common.gpu_config.clear_cache`, `steps.common.gpu_config.configure_gpu`, `steps.common.gpu_config.get_device`, `steps.common.gpu_config.print_memory_stats`, `steps.common.progress_tracker.get_tracker`, `steps.common.tool_paths.resolve_ffmpeg`, `subprocess`, `tempfile`, `time`, `torch`, `traceback`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`

### [step_wsl2.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio_diarize/step_wsl2.py)
- **Relative Path**: `steps/audio_diarize/step_wsl2.py`
- **Functions**: `audio_diarize`, `_merge_transcription_diarization`, `_extract_speakers`, `run`
- **Imports**: `__future__.annotations`, `logging`, `os`, `pathlib.Path`, `sys`, `typing.Any`, `typing.Dict`, `typing.List`, `wsl2_audio.audio_bridge.transcribe_and_diarize_wsl2`

### [vad_preprocessor.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio_diarize/vad_preprocessor.py)
- **Relative Path**: `steps/audio_diarize/vad_preprocessor.py`
- **Functions**: `_load_vad_model`, `detect_speech_segments`, `extract_speech_only_audio`, `merge_adjacent_segments`, `preprocess_audio_with_vad`, `calculate_time_savings`
- **Imports**: `__future__.annotations`, `numpy`, `os`, `tempfile`, `torch`, `torchaudio`, `traceback`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`

## Subsystem: `steps/audio_embed_clap`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio_embed_clap/step.py)
- **Relative Path**: `steps/audio_embed_clap/step.py`
- **Functions**: `_normalize_scene_id`, `_resolve_run_id`, `_build_qdrant_audio_payload`, `_torchaudio_preflight`, `_resolve_models_root`, `_configure_model_env`, `_resolve_local_model_dir`, `_preferred_device`, `_should_retry_on_cpu`, `_inspect_audio_input`, `_load`, `_ensure_clap_map`, `audio_embed_clap`
- **Imports**: `__future__.annotations`, `audioop`, `contextlib.nullcontext`, `datetime.datetime`, `datetime.timezone`, `faiss`, `importlib.util`, `librosa`, `logging`, `numpy`, `os`, `pathlib.Path`, `sqlite3`, `steps.common.config_loader.get_runtime_paths`, `steps.common.config_loader.load_configs`, `steps.common.faiss_utils.FaissLock`, `steps.common.faiss_utils.add_with_required_ids`, `steps.common.faiss_utils.create_hnsw_id_index`, `steps.common.gpu_config.clear_cache`, `steps.common.gpu_config.configure_gpu`, `steps.common.gpu_config.get_device`, `steps.common.gpu_config.print_memory_stats`, `steps.common.memory.upsert_embedding`, `steps.common.memory_commit_events.MemoryCommitEvent`, `steps.common.memory_commit_events.emit_memory_commit_event`, `steps.common.memory_commit_events.utc_now_iso`, `steps.common.qdrant_client.build_qdrant_client`, `steps.common.vad_preprocessor.preprocess_audio_with_vad`, `steps.text_embed.step._content_fingerprint`, `torch`, `transformers.AutoFeatureExtractor`, `transformers.ClapModel`, `typing.Any`, `typing.Dict`, `typing.Optional`, `wave`

## Subsystem: `steps/audio_emotion`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio_emotion/step.py)
- **Relative Path**: `steps/audio_emotion/step.py`
- **Functions**: `_resolve_models_root`, `_cache_snapshot_exists`, `_load`, `audio_emotion`
- **Imports**: `__future__.annotations`, `librosa`, `logging`, `os`, `pathlib.Path`, `steps.common.config_loader.get_runtime_paths`, `steps.common.config_loader.load_configs`, `steps.common.gpu_config.clear_cache`, `steps.common.gpu_config.configure_gpu`, `steps.common.gpu_config.get_device`, `steps.common.gpu_config.print_memory_stats`, `steps.common.vad_preprocessor.preprocess_audio_with_vad`, `torch`, `transformers.pipeline`, `typing.Any`, `typing.Dict`, `typing.List`

## Subsystem: `steps/audio_ingest_unified`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio_ingest_unified/__init__.py)
- **Relative Path**: `steps/audio_ingest_unified/__init__.py`

### [step_wsl2.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio_ingest_unified/step_wsl2.py)
- **Relative Path**: `steps/audio_ingest_unified/step_wsl2.py`
- **Functions**: `run`
- **Imports**: `json`, `logging`, `os`, `pathlib.Path`, `scripts.wsl2_audio_bridge.WSL2AudioBridge`, `steps.common.atomic_io.atomic_write_json`

## Subsystem: `steps/audio_metadata`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio_metadata/step.py)
- **Relative Path**: `steps/audio_metadata/step.py`
- **Functions**: `_file_times`, `_mutagen_tags`, `_probe_audio`, `audio_metadata`
- **Imports**: `__future__.annotations`, `datetime`, `librosa`, `mutagen`, `os`, `soundfile`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

## Subsystem: `steps/audio_music_events`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio_music_events/step.py)
- **Relative Path**: `steps/audio_music_events/step.py`
- **Functions**: `_normalize_text`, `audio_music_events`
- **Imports**: `__future__.annotations`, `re`, `typing.Any`, `typing.Dict`, `typing.List`

## Subsystem: `steps/audio_speaker_merge`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio_speaker_merge/step.py)
- **Relative Path**: `steps/audio_speaker_merge/step.py`
- **Functions**: `_overlap`, `audio_speaker_merge`
- **Imports**: `__future__.annotations`, `typing.Any`, `typing.Dict`, `typing.List`

## Subsystem: `steps/audio_time_hints`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio_time_hints/step.py)
- **Relative Path**: `steps/audio_time_hints/step.py`
- **Functions**: `_add_unique`, `_collect_time_hints`, `audio_time_hints`
- **Imports**: `__future__.annotations`, `datetime.datetime`, `re`, `typing.Any`, `typing.Dict`, `typing.List`

## Subsystem: `steps/audio_transcribe`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio_transcribe/__init__.py)
- **Relative Path**: `steps/audio_transcribe/__init__.py`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio_transcribe/step.py)
- **Relative Path**: `steps/audio_transcribe/step.py`
- **Functions**: `_resolve_models_root`, `_detect_transcription_device`, `_load_fw_model`, `_audio_duration`, `_split_range`, `_build_chunks`, `_slice_to_wav`, `_transcribe_chunk_whisper_cli`, `_transcribe_chunk_fw`, `_windows_to_wsl_path`, `_resolve_wsl_python`, `_run_wsl_faster_whisper_venv`, `audio_transcribe`, `_audio_transcribe_impl`
- **Imports**: `__future__.annotations`, `ctranslate2`, `faster_whisper.WhisperModel`, `json`, `lib.model_lifecycle.ModelLifecycleManager`, `librosa`, `logging`, `math`, `os`, `pathlib.Path`, `re`, `soundfile`, `steps.common.audio_gpu_optimizer.get_audio_gpu_optimizer`, `steps.common.config_loader.get_runtime_paths`, `steps.common.config_loader.load_configs`, `steps.common.profile_config.is_baseline`, `steps.common.profile_config.log_runtime_profile_state`, `steps.common.profile_config.require_gpu`, `steps.common.profile_config.require_wsl_audio`, `steps.common.tool_paths.resolve_ffmpeg`, `subprocess`, `tempfile`, `time`, `torch`, `traceback`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`, `wave`, `wsl2_audio_bridge.WSL2AudioBridge`

### [step_wsl2.py](file:///L:/GOODCUBE/projects/goodq4all/steps/audio_transcribe/step_wsl2.py)
- **Relative Path**: `steps/audio_transcribe/step_wsl2.py`
- **Functions**: `audio_transcribe`, `run`
- **Imports**: `__future__.annotations`, `logging`, `os`, `pathlib.Path`, `sys`, `typing.Any`, `typing.Dict`, `wsl2_audio.audio_bridge.transcribe_wsl2`

## Subsystem: `steps/common`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/__init__.py)
- **Relative Path**: `steps/common/__init__.py`

### [atomic_io.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/atomic_io.py)
- **Relative Path**: `steps/common/atomic_io.py`
- **Functions**: `atomic_write_json`
- **Imports**: `__future__.annotations`, `json`, `os`, `pathlib.Path`, `typing.Any`

### [audio_gpu_optimizer.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/audio_gpu_optimizer.py)
- **Relative Path**: `steps/common/audio_gpu_optimizer.py`
- **Classes**: `AudioGPUConfig`, `AudioGPUOptimizer`
- **Functions**: `get_audio_gpu_optimizer`
- **Imports**: `dataclasses.dataclass`, `flash_attn`, `logging`, `os`, `time`, `torch`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [canonical_sensitive_events.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/canonical_sensitive_events.py)
- **Relative Path**: `steps/common/canonical_sensitive_events.py`
- **Classes**: `_CanonicalMessageEventRequired`, `CanonicalMessageEvent`, `_CanonicalHealthEventRequired`, `CanonicalHealthEvent`, `_CanonicalWearableEventRequired`, `CanonicalWearableEvent`
- **Imports**: `__future__.annotations`, `typing.List`, `typing.Literal`, `typing.TypedDict`

### [conda_runner.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/conda_runner.py)
- **Relative Path**: `steps/common/conda_runner.py`
- **Classes**: `StepExecutionError`
- **Functions**: `_resolve_models_root`, `run_conda_step`
- **Imports**: `__future__.annotations`, `json`, `logging`, `os`, `pathlib.Path`, `steps.common.config_loader.get_runtime_paths`, `steps.common.config_loader.load_configs`, `subprocess`, `tempfile`, `tool_paths.resolve_conda`, `typing.Any`, `typing.Dict`

### [config_loader.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/config_loader.py)
- **Relative Path**: `steps/common/config_loader.py`
- **Functions**: `_read_yaml`, `_normalize_win_path`, `_resolve_env_ref`, `_apply_env_aliases`, `_normalize_paths`, `_ensure_runtime_path_defaults`, `_deep_merge`, `get_runtime_paths`, `load_configs`
- **Imports**: `__future__.annotations`, `config_schema.GoodQConfig`, `dotenv.load_dotenv`, `json`, `logging`, `os`, `pathlib.Path`, `re`, `shutil`, `steps.common.platform_config.PlatformHelper`, `steps.common.profile_config.log_runtime_profile_state`, `steps.common.tool_resolver.ToolResolver`, `sys`, `typing.Any`, `typing.Dict`, `yaml`

### [config_redaction.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/config_redaction.py)
- **Relative Path**: `steps/common/config_redaction.py`
- **Functions**: `redact_config`, `is_sensitive_key`, `_redact_value`, `_normalize_key`, `_looks_like_secret_value`, `_display_roots`, `_normalize_path`, `_tokenize_local_path`
- **Imports**: `__future__.annotations`, `math`, `os`, `pathlib.Path`, `re`, `typing.Any`, `typing.Iterable`, `typing.Mapping`

### [context_analyzer_llm.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/context_analyzer_llm.py)
- **Relative Path**: `steps/common/context_analyzer_llm.py`
- **Functions**: `_is_low_value_topic_fragment`, `_resolve_llm_config`, `_speaker_prompt_summary`, `_prompt_evidence_values`, `_caption_is_low_signal`, `_extract_transcript_topic_hints`, `_matches_explicit_transcript_topic_pattern`, `_has_stage_monologue_visual_cue`, `_minimal_scene_context_payload`, `_scene_context_failure_fallback_payload`, `_spoken_monologue_payload`, `_contains_supported_role_in_transcript`, `_derive_setting_hint`, `_is_evidence_grounded_topic_candidate`, `_is_transcript_grounded_topic_candidate`, `_extract_declared_topic_phrase`, `_contains_low_value_declared_topic`, `_derive_topic_hint`, `_rewrite_scene_text`, `_append_unique`, `_classify_context_tags`, `_contains_unsupported_role_text`, `_contains_low_value_visible_focus`, `_contains_mojibake_artifact`, `_looks_like_low_value_visual_key_moment`, `_has_excess_ungrounded_content`, `_normalize_key_moment_identity`, `_content_token_stems`, `_contains_unsupported_activity_text`, `_rewrite_emotional_arc`, `_rewrite_key_moment`, `_normalize_scene_context_payload`, `_build_scene_context_prompts`, `analyze_scene_context_llm`, `analyze_emotional_progression`, `build_relationship_map`
- **Imports**: `json`, `logging`, `re`, `requests`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [device_config.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/device_config.py)
- **Relative Path**: `steps/common/device_config.py`
- **Classes**: `DeviceConfig`
- **Imports**: `logging`, `os`, `sys`, `torch`, `torch.mps`

### [epistemic_diff.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/epistemic_diff.py)
- **Relative Path**: `steps/common/epistemic_diff.py`
- **Classes**: `EnvelopeBundle`, `IdentityBasis`, `DiffKey`, `DiffSide`, `DiffItem`, `CategorySummary`, `EpistemicDiff`
- **Functions**: `_safe_str`, `_sha256_hex`, `_stable_json`, `_presence`, `_is_mapping`, `_iter_candidates`, `_candidate_id`, `_candidate_state`, `_question_text`, `_flatten_evidence`, `_fnv1a32_hex`, `_compute_order_fingerprint`, `_aggregate_limits`, `_dont_know_limits`, `_format_scope`, `_aggregate_next_steps`, `_decision_key`, `_decision_rationale_keys`, `_evidence_key`, `_evidence_meta`, `_match_by_key`, `_identity_basis_eval`, `compute_epistemic_diff`
- **Imports**: `__future__.annotations`, `hashlib`, `json`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.List`, `typing.Literal`, `typing.Mapping`, `typing.Optional`, `typing.Sequence`, `typing.Tuple`, `typing.TypedDict`, `typing.cast`

### [epistemic_formatter.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/epistemic_formatter.py)
- **Relative Path**: `steps/common/epistemic_formatter.py`
- **Classes**: `_CandidateAcc`
- **Functions**: `_safe_str`, `_default_confidence_payload`, `_normalize_question`, `_normalize_retrieval_context`, `_infer_intents`, `_question_time_sensitive`, `_infer_modality_group`, `_vector_debug_enabled`, `_role_override`, `_infer_store_ref`, `_infer_evidence_hit`, `_candidate_key`, `_derive_candidate_state`, `format_epistemic_read`
- **Imports**: `__future__.annotations`, `dataclasses.dataclass`, `os`, `re`, `steps.common.retrieval_events.normalize_retrieval_context`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.List`, `typing.Optional`, `typing.Tuple`

### [faiss_utils.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/faiss_utils.py)
- **Relative Path**: `steps/common/faiss_utils.py`
- **Classes**: `FaissLock`
- **Functions**: `create_hnsw_id_index`, `add_with_required_ids`
- **Imports**: `__future__.annotations`, `errno`, `json`, `os`, `pathlib.Path`, `psutil`, `socket`, `subprocess`, `threading`, `time`, `typing.Any`, `uuid`

### [gpu_config.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/gpu_config.py)
- **Relative Path**: `steps/common/gpu_config.py`
- **Functions**: `_console_print`, `get_step_name`, `configure_gpu`, `get_device`, `clear_cache`, `print_memory_stats`
- **Imports**: `inspect`, `logging`, `os`, `pathlib.Path`, `steps.common.profile_config.is_baseline`, `steps.common.profile_config.log_runtime_profile_state`, `steps.common.profile_config.require_gpu`, `sys`, `torch`

### [gpu_guard.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/gpu_guard.py)
- **Relative Path**: `steps/common/gpu_guard.py`
- **Classes**: `GPUGuard`
- **Imports**: `logging`, `os`, `time`, `torch`

### [lexicon.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/lexicon.py)
- **Relative Path**: `steps/common/lexicon.py`
- **Functions**: `_cfg_get`, `_find_nrc_file`, `load_nrc`, `_tokenize`, `score_nrc_emotions`, `score_nrc_sentiment`
- **Imports**: `__future__.annotations`, `logging`, `os`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`

### [llm_model_factory.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/llm_model_factory.py)
- **Relative Path**: `steps/common/llm_model_factory.py`
- **Functions**: `_split_base_and_port`, `_build_llm_models`
- **Imports**: `lib.llm_client.ModelConfig`, `logging`, `os`, `typing.Any`, `typing.Dict`, `typing.List`, `urllib.parse.urlparse`, `yaml`

### [memory.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/memory.py)
- **Relative Path**: `steps/common/memory.py`
- **Functions**: `_coerce_time`, `to_faiss_id`, `_run_migrations`, `_connect`, `_embeddings_use_modality_key`, `_legacy_collision_hash`, `upsert_embedding`, `update_fields`, `insert_link`, `compute_file_hash`, `ensure_scene`, `upsert_link`, `register_scene_bundle`, `store_short_term_summary`, `append_long_term_summary`, `_make_id`, `upsert_scene`, `upsert_segment`, `get_scene_meta`, `scene_has_materialized`, `list_scenes_for_video`
- **Imports**: `__future__.annotations`, `contextlib`, `datetime.datetime`, `faiss`, `hashlib`, `json`, `logging`, `numpy`, `os`, `pathlib.Path`, `sqlite3`, `steps.common.memory_commit_events.MemoryCommitEvent`, `steps.common.memory_commit_events.emit_memory_commit_event`, `steps.common.memory_commit_events.utc_now_iso`, `steps.common.memory_manager.build_memory_router`, `steps.common.qdrant_client.build_qdrant_client`, `steps.common.quantization.TurboQuantEncoder`, `steps.common.scene_summarizer.generate_scene_summary`, `steps.text_embed.step._load_st`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `uuid`

### [memory_commit_events.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/memory_commit_events.py)
- **Relative Path**: `steps/common/memory_commit_events.py`
- **Classes**: `MemoryCommitEvent`
- **Functions**: `_truthy_env`, `_vector_debug_enabled`, `utc_now_iso`, `default_confidence_payload`, `_normalize_confidence`, `_ensure_schema`, `_cfg_paths`, `_configure_conn`, `emit_memory_commit_event`, `emit_memory_commit_events`
- **Imports**: `__future__.annotations`, `dataclasses.dataclass`, `datetime.datetime`, `datetime.timezone`, `json`, `os`, `sqlite3`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Sequence`, `typing.Tuple`, `typing.Union`

### [memory_context_writer.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/memory_context_writer.py)
- **Relative Path**: `steps/common/memory_context_writer.py`
- **Functions**: `save_step_context`, `save_enriched_scene_bundle`, `ensure_frame_hash_in_embeddings`
- **Imports**: `__future__.annotations`, `json`, `logging`, `steps.common.memory.compute_file_hash`, `steps.common.memory.register_scene_bundle`, `steps.common.memory.update_fields`, `steps.common.memory.upsert_scene`, `typing.Any`, `typing.Dict`, `typing.Optional`

### [memory_manager.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/memory_manager.py)
- **Relative Path**: `steps/common/memory_manager.py`
- **Functions**: `build_memory_router`
- **Imports**: `__future__.annotations`, `steps.common.memory_router.MemoryRouter`, `steps.common.memory_store.MemoryConfig`, `steps.common.memory_store.MemoryDims`, `steps.common.memory_store.normalize_memory_tier_list`, `steps.common.memory_stores.build_text_stores`, `typing.Dict`

### [memory_provenance.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/memory_provenance.py)
- **Relative Path**: `steps/common/memory_provenance.py`
- **Functions**: `_vector_debug_enabled`, `_id_key`, `_normalize_qdrant_point_id`, `_scene_id_candidates`, `_table_exists`, `default_confidence_payload`, `_normalize_confidence`, `_parse_ts_utc`, `_temporal_confidence`, `_row_to_provenance`, `_best_event`, `attach_provenance_to_hits`
- **Imports**: `__future__.annotations`, `datetime.datetime`, `datetime.timezone`, `json`, `math`, `os`, `sqlite3`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.List`, `typing.Optional`, `typing.Sequence`, `typing.Tuple`, `uuid`

### [memory_router.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/memory_router.py)
- **Relative Path**: `steps/common/memory_router.py`
- **Classes**: `MemoryRouter`
- **Imports**: `__future__.annotations`, `logging`, `os`, `steps.common.memory_store.MemoryConfig`, `steps.common.memory_store.MemoryDims`, `steps.common.memory_store.MemoryStore`, `steps.common.memory_store.normalize_memory_tier_list`, `steps.common.memory_store.normalize_memory_tier_name`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [memory_store.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/memory_store.py)
- **Relative Path**: `steps/common/memory_store.py`
- **Classes**: `MemoryStore`, `MemoryDims`, `MemoryConfig`
- **Functions**: `normalize_memory_tier_name`, `normalize_memory_tier_list`
- **Imports**: `__future__.annotations`, `dataclasses.dataclass`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Protocol`, `typing.runtime_checkable`

### [memory_stores.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/memory_stores.py)
- **Relative Path**: `steps/common/memory_stores.py`
- **Classes**: `EphemeralMemory`, `FaissMemory`, `QdrantMemory`
- **Functions**: `build_text_stores`
- **Imports**: `__future__.annotations`, `faiss`, `logging`, `numpy`, `os`, `sqlite3`, `steps.common.faiss_utils.FaissLock`, `steps.common.faiss_utils.add_with_required_ids`, `steps.common.faiss_utils.create_hnsw_id_index`, `steps.common.memory.to_faiss_id`, `steps.common.memory_provenance.attach_provenance_to_hits`, `steps.common.memory_store.MemoryStore`, `steps.common.qdrant_client.QdrantClient`, `steps.common.qdrant_client.build_qdrant_client`, `steps.common.quantization.TurboQuantEncoder`, `steps.common.retrieval_events.RetrievalEvent`, `steps.common.retrieval_events.emit_retrieval_events`, `steps.common.retrieval_events.normalize_retrieval_context`, `steps.common.retrieval_events.retrieval_events_enabled`, `steps.common.retrieval_events.utc_now_iso`, `time`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [memory_writer.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/memory_writer.py)
- **Relative Path**: `steps/common/memory_writer.py`
- **Classes**: `MemoryWriter`
- **Functions**: `get_memory_writer`, `save_step_results`
- **Imports**: `datetime.datetime`, `json`, `logging`, `os`, `pathlib.Path`, `sqlite3`, `steps.common.config_loader.get_runtime_paths`, `steps.common.config_loader.load_configs`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [non_action_contract.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/non_action_contract.py)
- **Relative Path**: `steps/common/non_action_contract.py`
- **Classes**: `NonActionCondition`, `NonActionDecision`, `SensitiveRequestContext`, `IngestRequestContext`, `TrainingRequestContext`, `ActionRequestContext`, `NonActionContext`
- **Functions**: `_is_mapping`, `_safe_bool`, `_iter_candidates`, `_candidate_state`, `_iter_evidence`, `_evidence_role`, `_has_support_evidence`, `_any_conflicted_candidate`, `_conflict_without_next_steps`, `_decision`, `_evaluate_answer`, `_evaluate_ingest`, `_evaluate_train`, `_evaluate_act`, `evaluate_non_action`
- **Imports**: `__future__.annotations`, `enum.Enum`, `typing.Any`, `typing.Dict`, `typing.Iterable`, `typing.List`, `typing.Literal`, `typing.Mapping`, `typing.Optional`, `typing.Sequence`, `typing.TypedDict`, `typing.cast`

### [platform_config.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/platform_config.py)
- **Relative Path**: `steps/common/platform_config.py`
- **Classes**: `PlatformHelper`
- **Imports**: `os`, `pathlib.Path`, `sys`

### [profile_config.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/profile_config.py)
- **Relative Path**: `steps/common/profile_config.py`
- **Functions**: `_normalize_profile`, `_parse_bool_env`, `_parse_optional_bool`, `get_host_profile`, `is_baseline`, `is_gpu_enhanced`, `require_gpu`, `require_wsl_audio`, `gpu_auto_config_enabled`, `wsl_audio_auto_enabled`, `resolve_wsl_gpu_config`, `log_runtime_profile_state`
- **Imports**: `__future__.annotations`, `logging`, `os`, `typing.Any`, `typing.Dict`, `typing.Optional`

### [progress_tracker.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/progress_tracker.py)
- **Relative Path**: `steps/common/progress_tracker.py`
- **Classes**: `ProgressTracker`
- **Functions**: `get_tracker`, `start_processing`, `update_step`, `set_total_steps`, `complete_step`, `add_error`, `add_warning`, `finish_processing`, `get_state`, `step_context`
- **Imports**: `__future__.annotations`, `configs.paths.LOGS_DIR`, `contextlib.contextmanager`, `datetime.datetime`, `pathlib.Path`, `steps.common.atomic_io.atomic_write_json`, `threading`, `time`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [qdrant_client.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/qdrant_client.py)
- **Relative Path**: `steps/common/qdrant_client.py`
- **Classes**: `QdrantConfig`, `QdrantClient`
- **Functions**: `_truncate_http_body`, `build_qdrant_client`
- **Imports**: `__future__.annotations`, `dataclasses.dataclass`, `logging`, `os`, `requests`, `steps.common.memory_provenance.attach_provenance_to_hits`, `steps.common.retrieval_events.RetrievalEvent`, `steps.common.retrieval_events.emit_retrieval_events`, `steps.common.retrieval_events.normalize_retrieval_context`, `steps.common.retrieval_events.retrieval_events_enabled`, `steps.common.retrieval_events.utc_now_iso`, `string`, `time`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `uuid`

### [quantization.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/quantization.py)
- **Relative Path**: `steps/common/quantization.py`
- **Classes**: `TurboQuantEncoder`
- **Imports**: `numpy`, `os`, `typing.Any`, `typing.Dict`, `typing.Optional`, `typing.Tuple`

### [retrieval_events.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/retrieval_events.py)
- **Relative Path**: `steps/common/retrieval_events.py`
- **Classes**: `RetrievalEvent`
- **Functions**: `_truthy_env`, `_vector_debug_enabled`, `utc_now_iso`, `normalize_retrieval_context`, `retrieval_events_jsonl_enabled`, `retrieval_events_enabled`, `_ensure_schema`, `_configure_conn`, `_cfg_paths`, `_is_sqlite_locked_error`, `_fallback_log_dir`, `_emit_jsonl_fallback`, `emit_retrieval_events`
- **Imports**: `__future__.annotations`, `dataclasses.dataclass`, `datetime.datetime`, `datetime.timezone`, `json`, `os`, `re`, `sqlite3`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Sequence`, `typing.Tuple`, `typing.Union`

### [retry.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/retry.py)
- **Relative Path**: `steps/common/retry.py`
- **Functions**: `request_with_retry`
- **Imports**: `__future__.annotations`, `random`, `requests`, `time`, `typing.Callable`, `typing.Tuple`, `typing.TypeVar`

### [safe_access.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/safe_access.py)
- **Relative Path**: `steps/common/safe_access.py`
- **Functions**: `safe_get`, `safe_get_dict`, `safe_get_attr`, `safe_float`, `safe_int`, `safe_str`, `safe_list`, `safe_dict`, `ensure_not_none`, `extract_metadata`, `returns_default_on_error`
- **Imports**: `logging`, `typing.Any`, `typing.Optional`, `typing.Union`

### [scene_summarizer.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/scene_summarizer.py)
- **Relative Path**: `steps/common/scene_summarizer.py`
- **Functions**: `_format_list`, `_format_emotions`, `_format_objects`, `_scene_keyframe`, `_scene_audio`, `_first_non_empty`, `_coerce_numeric`, `_emotion_entries`, `_dominant_emotion`, `_sentiment`, `_semantic_tags`, `_semantic_entities`, `_normalize_speaker_label`, `_speaker_summary`, `generate_scene_summary_template`, `generate_scene_summary_llm`, `generate_scene_summary`
- **Imports**: `__future__.annotations`, `json`, `re`, `requests`, `steps.common.tag_utils.dedupe_tokens`, `steps.common.tag_utils.is_valid_entity_token`, `steps.common.tag_utils.is_valid_tag_token`, `steps.common.tag_utils.normalize_entity_token`, `steps.common.tag_utils.normalize_tag_token`, `typing.Any`, `typing.Dict`, `typing.Optional`

### [sensitive_staging.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/sensitive_staging.py)
- **Relative Path**: `steps/common/sensitive_staging.py`
- **Functions**: `_norm_path`, `_is_under`, `validate_sensitive_staging`
- **Imports**: `__future__.annotations`, `os`, `pathlib.Path`, `typing.Any`, `typing.Mapping`, `typing.Optional`

### [step_logger.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/step_logger.py)
- **Relative Path**: `steps/common/step_logger.py`
- **Functions**: `_fingerprint_item`, `log_step_run`
- **Imports**: `__future__.annotations`, `csv`, `datetime.datetime`, `hashlib`, `json`, `lib.goodq_logger.get_goodq_logger`, `lib.mission_components.format_duration`, `lib.mission_components.get_component_name`, `logging`, `os`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [tag_utils.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/tag_utils.py)
- **Relative Path**: `steps/common/tag_utils.py`
- **Functions**: `_normalize_token`, `_token_key`, `normalize_tag_token`, `normalize_entity_token`, `is_semantic_stopword`, `is_valid_tag_token`, `is_valid_entity_token`, `dedupe_tokens`, `merge_tag_sources`, `canonicalize_taxonomy`
- **Imports**: `__future__.annotations`, `lib.kg_realtime_integration._ENTITY_CONTRACTION_PARTS`, `lib.kg_realtime_integration._ENTITY_STOPWORDS`, `lib.kg_realtime_integration._is_valid_entity_token`, `lib.kg_realtime_integration.normalize_entity_name`, `re`, `typing.Any`, `typing.Callable`, `typing.Iterable`, `typing.List`, `typing.Optional`, `typing.Sequence`

### [tool_paths.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/tool_paths.py)
- **Relative Path**: `steps/common/tool_paths.py`
- **Functions**: `cfg_get`, `resolve_piper`, `resolve_tesseract`, `_normalize_executable_hint`, `resolve_ffmpeg`, `resolve_conda`
- **Imports**: `__future__.annotations`, `configs.python_paths.get_conda_exe`, `imageio_ffmpeg`, `logging`, `os`, `shutil`, `typing.Any`, `typing.Dict`, `typing.Optional`

### [tool_resolver.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/tool_resolver.py)
- **Relative Path**: `steps/common/tool_resolver.py`
- **Classes**: `ToolResolver`
- **Imports**: `os`, `pathlib.Path`, `shutil`, `sys`, `typing.Any`, `typing.Dict`

### [vad_preprocessor.py](file:///L:/GOODCUBE/projects/goodq4all/steps/common/vad_preprocessor.py)
- **Relative Path**: `steps/common/vad_preprocessor.py`
- **Functions**: `get_vad_model`, `preprocess_audio_with_vad`, `calculate_time_savings`
- **Imports**: `pathlib.Path`, `tempfile`, `time`, `torch`, `torchaudio`, `traceback`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`

## Subsystem: `steps/discover_sources`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/discover_sources/__init__.py)
- **Relative Path**: `steps/discover_sources/__init__.py`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/discover_sources/step.py)
- **Relative Path**: `steps/discover_sources/step.py`
- **Functions**: `discover_sources`
- **Imports**: `__future__.annotations`, `os`, `typing.Any`, `typing.Dict`, `typing.List`

## Subsystem: `steps/emotion_classify`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/emotion_classify/__init__.py)
- **Relative Path**: `steps/emotion_classify/__init__.py`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/emotion_classify/step.py)
- **Relative Path**: `steps/emotion_classify/step.py`
- **Functions**: `_load_emotion`, `_gather_text`, `emotion_classify`
- **Imports**: `__future__.annotations`, `gpu_config.GPUManager`, `gpu_config.setup_step_gpu`, `json`, `logging`, `os`, `steps.common.lexicon.score_nrc_emotions`, `steps.common.memory.update_fields`, `steps.text_embed.step._content_fingerprint`, `torch`, `transformers.AutoModelForSequenceClassification`, `transformers.AutoTokenizer`, `typing.Any`, `typing.Dict`, `typing.List`

## Subsystem: `steps/face_embed`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/face_embed/__init__.py)
- **Relative Path**: `steps/face_embed/__init__.py`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/face_embed/step.py)
- **Relative Path**: `steps/face_embed/step.py`
- **Functions**: `_face_recognition_stack_available`, `face_embed`
- **Imports**: `PIL.Image`, `__future__.annotations`, `contextlib`, `face_recognition`, `facenet_pytorch.InceptionResnetV1`, `facenet_pytorch.MTCNN`, `importlib`, `importlib.util`, `io`, `logging`, `os`, `scripts.gpu_config.GPUManager`, `scripts.gpu_config.setup_step_gpu`, `torch`, `torchvision.transforms`, `typing.Any`, `typing.Dict`, `typing.List`, `warnings`

## Subsystem: `steps/graph_builder`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/graph_builder/__init__.py)
- **Relative Path**: `steps/graph_builder/__init__.py`
- **Imports**: `graph_builder.build_knowledge_graph`

### [emotion_arc_analyzer.py](file:///L:/GOODCUBE/projects/goodq4all/steps/graph_builder/emotion_arc_analyzer.py)
- **Relative Path**: `steps/graph_builder/emotion_arc_analyzer.py`
- **Functions**: `analyze_emotional_arc`, `add_emotional_arc_to_kg`, `_parse_llm_json_response`
- **Imports**: `json`, `logging`, `requests`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [graph_builder.py](file:///L:/GOODCUBE/projects/goodq4all/steps/graph_builder/graph_builder.py)
- **Relative Path**: `steps/graph_builder/graph_builder.py`
- **Functions**: `build_knowledge_graph`, `_process_objects`, `_process_faces`, `_process_text`, `_process_audio`, `_process_emotions`, `_process_locations`, `_build_cooccurrence_edges`, `_build_temporal_edges`, `_build_semantic_edges`, `_extract_concepts`, `_extract_mentions`, `_process_llm_entities`, `_analyze_and_add_emotional_arc`
- **Imports**: `emotion_arc_analyzer.add_emotional_arc_to_kg`, `emotion_arc_analyzer.analyze_emotional_arc`, `json`, `lib.knowledge_graph.KnowledgeGraph`, `llm_enrichment.extract_entities_with_llm`, `llm_enrichment.generate_scene_narrative`, `logging`, `pathlib.Path`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [llm_enrichment.py](file:///L:/GOODCUBE/projects/goodq4all/steps/graph_builder/llm_enrichment.py)
- **Relative Path**: `steps/graph_builder/llm_enrichment.py`
- **Functions**: `extract_entities_with_llm`, `infer_relationships_with_llm`, `generate_scene_narrative`, `_build_context_description`, `_parse_llm_json_response`
- **Imports**: `json`, `logging`, `requests`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`

## Subsystem: `steps/health_auto_export`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/health_auto_export/__init__.py)
- **Relative Path**: `steps/health_auto_export/__init__.py`

### [adapter.py](file:///L:/GOODCUBE/projects/goodq4all/steps/health_auto_export/adapter.py)
- **Relative Path**: `steps/health_auto_export/adapter.py`
- **Classes**: `CanonicalHealthEventCHE`, `DryRunSummary`
- **Functions**: `_as_mapping`, `_as_sequence`, `_first_str`, `_normalize_measurement_type`, `_split_sources`, `_to_utc_iso`, `_detect_numeric_keys`, `_sanitize_unknown_fields`, `_infer_category`, `_make_event_id`, `_extract_time_fields`, `_build_metric_events`, `_build_medication_events`, `parse_health_auto_export`, `dry_run_summary`, `print_dry_run_report`, `_load_json`, `_main`
- **Imports**: `__future__.annotations`, `collections.defaultdict`, `dataclasses.dataclass`, `datetime.date`, `datetime.datetime`, `datetime.timezone`, `json`, `pathlib.Path`, `re`, `steps.common.canonical_sensitive_events.CanonicalHealthEvent`, `steps.common.canonical_sensitive_events.HealthCategory`, `steps.common.canonical_sensitive_events.HealthSource`, `typing.Any`, `typing.DefaultDict`, `typing.Iterable`, `typing.Mapping`, `typing.Optional`, `typing.Sequence`, `typing.TypedDict`, `uuid`

### [normalizer.py](file:///L:/GOODCUBE/projects/goodq4all/steps/health_auto_export/normalizer.py)
- **Relative Path**: `steps/health_auto_export/normalizer.py`
- **Classes**: `SchemaFingerprintV1`, `SourceFingerprintV1`, `TimeRangeV1`, `CanonicalHealthEventHIN`, `_Group`, `_Context`
- **Functions**: `normalize_health_payload`, `_hash_sha256`, `_json_size_bytes`, `_shape_signature`, `_fingerprint_schema`, `_to_utc_day`, `_to_utc_datetime`, `_path_template`, `_infer_source`, `_normalize_measurement_type`, `_infer_category`, `_is_safe_label`, `_label_hints_from_mapping`, `_date_range_hint_from_mapping`, `_iter_numeric_values`, `_extract_datetimes`, `_discover_groups`, `_summarize_list`, `_metric_name_from_path`, `_make_event_id`, `_build_event`, `_build_absence_event`
- **Imports**: `__future__.annotations`, `dataclasses.dataclass`, `datetime.date`, `datetime.datetime`, `datetime.timezone`, `hashlib`, `json`, `re`, `steps.common.canonical_sensitive_events.CanonicalHealthEvent`, `steps.common.canonical_sensitive_events.HealthCategory`, `steps.common.canonical_sensitive_events.HealthSource`, `typing.Any`, `typing.Iterable`, `typing.Mapping`, `typing.Optional`, `typing.Sequence`, `typing.TypedDict`, `uuid`

## Subsystem: `steps/home_assistant_status`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/home_assistant_status/__init__.py)
- **Relative Path**: `steps/home_assistant_status/__init__.py`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/home_assistant_status/step.py)
- **Relative Path**: `steps/home_assistant_status/step.py`
- **Functions**: `_summarize_entity`, `home_assistant_status`
- **Imports**: `__future__.annotations`, `os`, `requests`, `steps.common.retry.request_with_retry`, `typing.Any`, `typing.Dict`, `typing.List`

## Subsystem: `steps/image_caption`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/image_caption/__init__.py)
- **Relative Path**: `steps/image_caption/__init__.py`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/image_caption/step.py)
- **Relative Path**: `steps/image_caption/step.py`
- **Functions**: `_resolve_device`, `_amp_enabled`, `_gpu_memory_snapshot`, `_shape_for_log`, `_log_caption_diagnostics`, `_resolve_models_root`, `_load_blip`, `_load_fallback`, `image_caption`
- **Imports**: `PIL.Image`, `__future__.annotations`, `contextlib.nullcontext`, `json`, `logging`, `os`, `pathlib.Path`, `scripts.gpu_config.GPUManager`, `scripts.gpu_config.setup_step_gpu`, `steps.common.config_loader.get_runtime_paths`, `steps.common.config_loader.load_configs`, `sys`, `torch`, `transformers.BlipForConditionalGeneration`, `transformers.BlipProcessor`, `transformers.pipeline`, `typing.Any`, `typing.Dict`, `typing.Optional`

## Subsystem: `steps/image_embed_clip`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/image_embed_clip/step.py)
- **Relative Path**: `steps/image_embed_clip/step.py`
- **Functions**: `_debug_env`, `_load`, `image_embed_clip`
- **Imports**: `PIL.Image`, `__future__.annotations`, `contextlib.nullcontext`, `datetime.datetime`, `faiss`, `logging`, `numpy`, `os`, `pathlib.Path`, `scripts.gpu_config.GPUManager`, `scripts.gpu_config.setup_step_gpu`, `sqlite3`, `steps`, `steps.common.faiss_utils.FaissLock`, `steps.common.faiss_utils.add_with_required_ids`, `steps.common.faiss_utils.create_hnsw_id_index`, `steps.common.memory.upsert_embedding`, `steps.common.qdrant_client.build_qdrant_client`, `steps.text_embed.step._content_fingerprint`, `sys`, `torch`, `transformers.CLIPModel`, `transformers.CLIPProcessor`, `typing.Any`, `typing.Dict`, `yaml`

## Subsystem: `steps/image_embed_dino`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/image_embed_dino/step.py)
- **Relative Path**: `steps/image_embed_dino/step.py`
- **Functions**: `_resolve_device`, `_amp_enabled`, `_gpu_memory_snapshot`, `_shape_for_log`, `_log_dino_diagnostics`, `_load`, `image_embed_dino`
- **Imports**: `PIL.Image`, `__future__.annotations`, `contextlib.nullcontext`, `datetime.datetime`, `faiss`, `json`, `logging`, `numpy`, `os`, `pathlib.Path`, `scripts.gpu_config.GPUManager`, `scripts.gpu_config.setup_step_gpu`, `sqlite3`, `steps.common.faiss_utils.FaissLock`, `steps.common.faiss_utils.add_with_required_ids`, `steps.common.faiss_utils.create_hnsw_id_index`, `steps.common.memory.upsert_embedding`, `steps.common.qdrant_client.build_qdrant_client`, `steps.text_embed.step._content_fingerprint`, `sys`, `torch`, `transformers.AutoModel`, `transformers.AutoProcessor`, `typing.Any`, `typing.Dict`, `typing.Optional`, `yaml`

## Subsystem: `steps/image_exif`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/image_exif/step.py)
- **Relative Path**: `steps/image_exif/step.py`
- **Functions**: `_convert_gps`, `image_exif`
- **Imports**: `PIL.ExifTags`, `PIL.Image`, `__future__.annotations`, `numpy`, `os`, `reverse_geocoder`, `timezonefinder.TimezoneFinder`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`

## Subsystem: `steps/image_ocr`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/image_ocr/__init__.py)
- **Relative Path**: `steps/image_ocr/__init__.py`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/image_ocr/step.py)
- **Relative Path**: `steps/image_ocr/step.py`
- **Functions**: `_sanitize_error_message`, `_meta`, `_clean_ocr_text`, `_dedupe_texts`, `_extract_vhs_date_candidates`, `_select_vhs_ocr_candidate`, `_time_hints_from_vhs_dates`, `_vhs_timestamp_variants`, `_run_vhs_timestamp_fallback`, `image_ocr`
- **Imports**: `PIL.Image`, `PIL.ImageEnhance`, `PIL.ImageFilter`, `PIL.ImageOps`, `__future__.annotations`, `os`, `pytesseract`, `re`, `steps.common.gpu_config.clear_cache`, `steps.common.gpu_config.configure_gpu`, `steps.common.gpu_config.get_device`, `steps.common.gpu_config.print_memory_stats`, `steps.common.tool_paths.resolve_tesseract`, `typing.Any`, `typing.Callable`, `typing.Dict`, `typing.Iterable`, `typing.List`, `typing.Optional`, `typing.Sequence`, `typing.Tuple`

## Subsystem: `steps/llm_chat`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/llm_chat/__init__.py)
- **Relative Path**: `steps/llm_chat/__init__.py`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/llm_chat/step.py)
- **Relative Path**: `steps/llm_chat/step.py`
- **Functions**: `_goodq_persona_prompt`, `_multimodal_context_prompt`, `llm_chat`
- **Imports**: `__future__.annotations`, `json`, `os`, `requests`, `steps.common.gpu_config.clear_cache`, `steps.common.gpu_config.configure_gpu`, `steps.common.gpu_config.get_device`, `steps.common.gpu_config.print_memory_stats`, `steps.common.memory._connect`, `steps.common.retry.request_with_retry`, `typing.Any`, `typing.Dict`, `urllib.parse.urlparse`, `urllib.parse.urlunparse`

## Subsystem: `steps/object_detect`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/object_detect/__init__.py)
- **Relative Path**: `steps/object_detect/__init__.py`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/object_detect/step.py)
- **Relative Path**: `steps/object_detect/step.py`
- **Functions**: `_resolve_device`, `_gpu_memory_snapshot`, `_log_object_detect_diagnostics`, `_resolve_models_root`, `_load_yolo`, `_run_yolo`, `object_detect`
- **Imports**: `PIL.Image`, `__future__.annotations`, `json`, `logging`, `os`, `pathlib.Path`, `scripts.gpu_config.GPUManager`, `scripts.gpu_config.setup_step_gpu`, `steps.common.config_loader.get_runtime_paths`, `steps.common.config_loader.load_configs`, `sys`, `torch`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `ultralytics.YOLO`

## Subsystem: `steps/object_track_yolo`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/object_track_yolo/step.py)
- **Relative Path**: `steps/object_track_yolo/step.py`
- **Functions**: `object_track_yolo`
- **Imports**: `__future__.annotations`, `cv2`, `deep_sort_realtime.deepsort_tracker.DeepSort`, `numpy`, `steps.common.gpu_config.clear_cache`, `steps.common.gpu_config.configure_gpu`, `steps.common.gpu_config.get_device`, `steps.common.gpu_config.print_memory_stats`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Tuple`

## Subsystem: `steps/overview`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/overview/step.py)
- **Relative Path**: `steps/overview/step.py`
- **Functions**: `_tally`, `_safe_int`, `_get_faiss_ntotal`, `_db_counts`, `overview`
- **Imports**: `__future__.annotations`, `json`, `lib.memory_management.diagnostics.run_all_diagnostics`, `os`, `sqlite3`, `steps.common.tag_utils.is_valid_entity_token`, `steps.common.tag_utils.is_valid_tag_token`, `steps.common.tag_utils.normalize_entity_token`, `steps.common.tag_utils.normalize_tag_token`, `steps.common.tool_paths.resolve_conda`, `subprocess`, `time`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

## Subsystem: `steps/pdf_text`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/pdf_text/__init__.py)
- **Relative Path**: `steps/pdf_text/__init__.py`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/pdf_text/step.py)
- **Relative Path**: `steps/pdf_text/step.py`
- **Functions**: `_pdftotext`, `pdf_to_text`
- **Imports**: `__future__.annotations`, `os`, `subprocess`, `typing.Any`, `typing.Dict`, `typing.Optional`

## Subsystem: `steps/sentiment`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/sentiment/step.py)
- **Relative Path**: `steps/sentiment/step.py`
- **Functions**: `_resolve_models_root`, `_configure_model_env`, `_normalize_text`, `_looks_too_short`, `_preferred_device`, `_should_retry_on_cpu`, `_load`, `_gather_text`, `sentiment`
- **Imports**: `__future__.annotations`, `logging`, `os`, `pathlib.Path`, `re`, `steps.common.config_loader.get_runtime_paths`, `steps.common.config_loader.load_configs`, `steps.common.lexicon.score_nrc_sentiment`, `steps.common.memory.update_fields`, `steps.text_embed.step._content_fingerprint`, `torch`, `transformers.AutoModelForSequenceClassification`, `transformers.AutoTokenizer`, `typing.Any`, `typing.Dict`, `typing.Optional`, `unicodedata`

### [step_fixed.py](file:///L:/GOODCUBE/projects/goodq4all/steps/sentiment/step_fixed.py)
- **Relative Path**: `steps/sentiment/step_fixed.py`
- **Functions**: `_resolve_models_root`, `_load`, `_gather_text`, `sentiment`
- **Imports**: `__future__.annotations`, `logging`, `os`, `pathlib.Path`, `steps.common.config_loader.get_runtime_paths`, `steps.common.config_loader.load_configs`, `steps.common.lexicon.score_nrc_sentiment`, `steps.common.memory.update_fields`, `steps.text_embed.step._content_fingerprint`, `threading`, `time`, `torch`, `transformers.AutoModelForSequenceClassification`, `transformers.AutoTokenizer`, `typing.Any`, `typing.Dict`

## Subsystem: `steps/system_metrics`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/system_metrics/__init__.py)
- **Relative Path**: `steps/system_metrics/__init__.py`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/system_metrics/step.py)
- **Relative Path**: `steps/system_metrics/step.py`
- **Functions**: `_read_csv_latest`, `_collect_psutil`, `_collect_nvidia`, `_summarize_row`, `_summarize_live`, `system_metrics`
- **Imports**: `__future__.annotations`, `chardet`, `json`, `os`, `pandas`, `psutil`, `subprocess`, `typing.Any`, `typing.Dict`, `typing.Optional`

## Subsystem: `steps/tagger`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/tagger/__init__.py)
- **Relative Path**: `steps/tagger/__init__.py`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/tagger/step.py)
- **Relative Path**: `steps/tagger/step.py`
- **Functions**: `_get_ner_pipeline`, `_speaker_transcript_text`, `_gather_text`, `_usefulness_score`, `_extract_entities_transformers`, `_fallback_entities`, `_entity_tokens`, `_count_entity_mentions`, `_count_independent_token_mentions`, `_canonicalize_unstable_compound_person_label`, `_is_meaningful_entity_label`, `_contextually_reject_entity`, `_appears_as_entity_span`, `_is_sentence_start_match`, `_filter_ner_entities`, `_filter_entity_labels`, `_coerce_entity_type`, `_add_candidate`, `_sorted_candidates`, `_iter_object_labels`, `_iter_music_labels`, `_iter_time_tokens`, `_iter_caption_tags`, `_rank_entities`, `_rank_tags`, `tagger`
- **Imports**: `__future__.annotations`, `re`, `steps.common.tag_utils.dedupe_tokens`, `steps.common.tag_utils.is_valid_entity_token`, `steps.common.tag_utils.is_valid_tag_token`, `steps.common.tag_utils.normalize_entity_token`, `steps.common.tag_utils.normalize_tag_token`, `transformers.logging`, `transformers.pipeline`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Tuple`

### [step_llm_enhanced.py](file:///L:/GOODCUBE/projects/goodq4all/steps/tagger/step_llm_enhanced.py)
- **Relative Path**: `steps/tagger/step_llm_enhanced.py`
- **Functions**: `_get_ner_pipeline`, `_gather_text`, `_usefulness_score`, `_extract_entities_transformers`, `_fallback_entities`, `_sanitize_llm_values`, `_extract_tags_llm`, `tagger_llm_enhanced`
- **Imports**: `__future__.annotations`, `json`, `logging`, `re`, `requests`, `steps.common.tag_utils.dedupe_tokens`, `steps.common.tag_utils.is_valid_entity_token`, `steps.common.tag_utils.is_valid_tag_token`, `steps.common.tag_utils.normalize_entity_token`, `steps.common.tag_utils.normalize_tag_token`, `transformers.logging`, `transformers.pipeline`, `typing.Any`, `typing.Dict`, `typing.List`

## Subsystem: `steps/text_embed`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/text_embed/__init__.py)
- **Relative Path**: `steps/text_embed/__init__.py`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/text_embed/step.py)
- **Relative Path**: `steps/text_embed/step.py`
- **Functions**: `_load_st`, `_open_faiss`, `_content_fingerprint`, `_coerce_scene_identity`, `_text_embedding_identity`, `_gather_text`, `_coerce_str_list`, `_coerce_semantic_labels`, `_normalize_semantic_label`, `_semantic_tokens`, `_is_meaningful_semantic_label`, `_sanitize_semantic_list`, `_gather_entities`, `_gather_locations`, `_lexical_valence_counts`, `_contains_phrase`, `_count_token_occurrences`, `_gather_artifact_hints`, `_contextually_reject_entity`, `_raw_emotion_label`, `_emotion_score_metrics`, `_gather_emotion`, `_gather_sentiment_label`, `_gather_dialogue_hints`, `_build_semantic_text`, `_preview_focus_phrases`, `_build_text_preview`, `text_embed`
- **Imports**: `__future__.annotations`, `faiss`, `gpu_config.GPUManager`, `gpu_config.setup_step_gpu`, `hashlib`, `json`, `logging`, `os`, `re`, `sentence_transformers.SentenceTransformer`, `steps.common.faiss_utils.create_hnsw_id_index`, `steps.common.memory.upsert_embedding`, `steps.common.memory_commit_events.MemoryCommitEvent`, `steps.common.memory_commit_events.emit_memory_commit_event`, `steps.common.memory_commit_events.utc_now_iso`, `steps.common.memory_router.MemoryRouter`, `steps.common.memory_stores.build_text_stores`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

## Subsystem: `steps/tts`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/tts/__init__.py)
- **Relative Path**: `steps/tts/__init__.py`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/tts/step.py)
- **Relative Path**: `steps/tts/step.py`
- **Functions**: `_resolve_elevenlabs_voice_id`, `_elevenlabs_tts`, `_piper_tts`, `tts_speak`
- **Imports**: `__future__.annotations`, `logging`, `os`, `requests`, `steps.common.tool_paths.resolve_piper`, `subprocess`, `tempfile`, `typing.Any`, `typing.Dict`, `typing.Optional`

## Subsystem: `steps/video`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/video/__init__.py)
- **Relative Path**: `steps/video/__init__.py`

### [cross_modal_harmonizer.py](file:///L:/GOODCUBE/projects/goodq4all/steps/video/cross_modal_harmonizer.py)
- **Relative Path**: `steps/video/cross_modal_harmonizer.py`
- **Functions**: `load_json_safe`, `_normalize_content_state`, `_normalize_entity_rollup_record`, `_normalize_entity_channel_record`, `_normalize_aligned_mention_variant_text`, `_strip_aligned_mention_titles`, `_serialize_entity_count_pairs`, `_normalize_transcript_person_surface`, `_normalize_transcript_person_key`, `_extract_transcript_person_candidates`, `_segment_person_entity_names`, `_segment_person_channel_records`, `_segment_local_person_surfaces`, `_resolve_transcript_entity_exact_pair_normalization`, `_find_partial_surface_match`, `_find_spelling_drift_surface_match`, `_segment_transcript_entity_projection`, `_segment_transcript_entity_disagreements`, `_build_transcript_entity_disagreement_summary`, `_build_speaker_aligned_mention_variant_groups`, `_canonicalize_chain_person_mentions`, `_classify_entity_channel`, `_build_entity_channels`, `_resolve_scene_faces`, `_count_visible_person_objects`, `_resolve_audio_emotion`, `_rank_audio_emotion_scores`, `_rank_text_emotions`, `_resolve_audio_sentiment`, `_resolve_scene_music_events`, `_extract_music_event_labels`, `_time_hints_have_values`, `_merge_time_hint_dicts`, `_resolve_scene_time_hints`, `_resolve_scene_metadata_time_hints`, `_scene_context_llm_enabled`, `_sanitize_scene_context_llm`, `_scene_context_text_blob`, `_collect_entity_texts`, `_text_contains_phrase`, `_collect_scene_identity_names`, `_is_supported_arbitration_topic`, `_extract_scene_object_labels`, `_derive_scene_context_epistemic`, `_derive_scene_context_arbitration`, `_extract_time_hint_tokens`, `_normalize_speaker_id`, `_coerce_float`, `_collect_scene_speaker_records`, `_summarize_speaker_records`, `_has_direct_address`, `_text_mentions_name`, `_has_adjacent_reply_confirmation`, `_derive_candidate_visible_people`, `_segment_mentions_person`, `_resolve_segment_continuity_key`, `_resolve_segment_continuity_members`, `_iter_continuity_chains`, `_apply_interaction_dominance_window`, `_apply_conversation_owner_window`, `_apply_scene_context_llm`, `_persist_harmonized_scene_fields`, `_resolve_segment_content_state`, `_load_required_audio_artifact`, `_load_commit_presence`, `align_audio_to_scenes`, `extract_keywords_from_transcript`, `_resolve_scene_objects`, `run_cross_modal_harmonization`
- **Imports**: `__future__.annotations`, `collections.Counter`, `difflib.SequenceMatcher`, `json`, `logging`, `os`, `pathlib.Path`, `re`, `sqlite3`, `steps.common.atomic_io.atomic_write_json`, `steps.common.config_loader.get_runtime_paths`, `steps.common.context_analyzer_llm._caption_is_low_signal`, `steps.common.context_analyzer_llm._extract_transcript_topic_hints`, `steps.common.context_analyzer_llm._is_low_value_topic_fragment`, `steps.common.context_analyzer_llm.analyze_scene_context_llm`, `steps.common.epistemic_formatter.EPISTEMIC_READ_MODEL_VERSION`, `steps.video.entity_extractor.EntityExtractor`, `steps.video.entity_extractor.extract_entities_from_scene`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [embedding_pooler.py](file:///L:/GOODCUBE/projects/goodq4all/steps/video/embedding_pooler.py)
- **Relative Path**: `steps/video/embedding_pooler.py`
- **Functions**: `pool_embeddings_mean`, `pool_embeddings_max`, `pool_embeddings_concat`, `pool_embeddings_attention`, `pool_scene_embeddings`, `pool_multiple_scenes`
- **Imports**: `__future__.annotations`, `logging`, `numpy`, `typing.Any`, `typing.Dict`, `typing.List`

### [entity_extractor.py](file:///L:/GOODCUBE/projects/goodq4all/steps/video/entity_extractor.py)
- **Relative Path**: `steps/video/entity_extractor.py`
- **Classes**: `ExtractedEntity`, `EntityExtractor`
- **Functions**: `extract_entities_from_scene`
- **Imports**: `dataclasses.asdict`, `dataclasses.dataclass`, `json`, `logging`, `os`, `pathlib.Path`, `re`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Set`

### [scene_embedder.py](file:///L:/GOODCUBE/projects/goodq4all/steps/video/scene_embedder.py)
- **Relative Path**: `steps/video/scene_embedder.py`
- **Functions**: `_resolve_model_device`, `_load_clip_model`, `_load_dino_model`, `embed_frames_clip`, `embed_frames_dino`, `embed_scene_frames`
- **Imports**: `PIL.Image`, `__future__.annotations`, `contextlib.nullcontext`, `logging`, `numpy`, `os`, `pathlib.Path`, `steps.common.gpu_config.configure_gpu`, `torch`, `transformers.AutoImageProcessor`, `transformers.AutoModel`, `transformers.CLIPModel`, `transformers.CLIPProcessor`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`, `yaml`

### [scene_frame_extractor.py](file:///L:/GOODCUBE/projects/goodq4all/steps/video/scene_frame_extractor.py)
- **Relative Path**: `steps/video/scene_frame_extractor.py`
- **Functions**: `_is_reusable_frame`, `extract_frame_at_timestamp`, `extract_frames_uniform`, `extract_frames_middle`, `extract_keyframe_candidates`, `extract_scene_frames`
- **Imports**: `__future__.annotations`, `cv2`, `json`, `logging`, `numpy`, `os`, `pathlib.Path`, `steps.common.config_loader.load_configs`, `steps.common.tool_paths.resolve_ffmpeg`, `subprocess`, `tempfile`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`

### [scene_visual_embeddings.py](file:///L:/GOODCUBE/projects/goodq4all/steps/video/scene_visual_embeddings.py)
- **Relative Path**: `steps/video/scene_visual_embeddings.py`
- **Functions**: `_atomic_write_json`, `_write_scene_manifest`, `_persist_phase6_failure`, `_resolve_processing_root`, `_resolve_qdrant_host`, `_mirror_scene_vector_status`, `_write_scene_faiss_points`, `_stage10_18_debug`, `run_scene_visual_embeddings`
- **Imports**: `__future__.annotations`, `faiss`, `hashlib`, `inspect`, `json`, `logging`, `numpy`, `os`, `pathlib.Path`, `sqlite3`, `steps.common.atomic_io.atomic_write_json`, `steps.common.config_loader.get_runtime_paths`, `steps.common.faiss_utils.FaissLock`, `steps.common.faiss_utils.add_with_required_ids`, `steps.common.faiss_utils.create_hnsw_id_index`, `steps.common.gpu_config.configure_gpu`, `steps.common.memory.to_faiss_id`, `steps.common.memory.upsert_embedding`, `steps.common.memory_commit_events.MemoryCommitEvent`, `steps.common.memory_commit_events.emit_memory_commit_events`, `steps.common.memory_commit_events.utc_now_iso`, `steps.common.qdrant_client.QdrantClient`, `steps.common.qdrant_client.QdrantConfig`, `steps.video.embedding_pooler.pool_multiple_scenes`, `steps.video.scene_embedder`, `steps.video.scene_embedder.embed_scene_frames`, `steps.video.scene_frame_extractor.extract_scene_frames`, `sys`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

## Subsystem: `steps/video_ingest`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/video_ingest/step.py)
- **Relative Path**: `steps/video_ingest/step.py`
- **Functions**: `_default`, `_histogram`, `_summarize_video`, `_sha256`, `_faiss_ntotal_via_env`, `_coerce_float`, `_segment_key`, `_build_segment_id`, `_dedupe_sources`, `_link_frames_audio`, `video_ingest_and_summarize`
- **Imports**: `__future__.annotations`, `hashlib`, `json`, `os`, `sqlite3`, `steps.common.memory.append_long_term_summary`, `steps.common.memory.store_short_term_summary`, `steps.common.tag_utils.canonicalize_taxonomy`, `steps.common.tag_utils.is_valid_entity_token`, `steps.common.tag_utils.is_valid_tag_token`, `steps.common.tag_utils.normalize_entity_token`, `steps.common.tag_utils.normalize_tag_token`, `steps.common.tool_paths.resolve_conda`, `subprocess`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`

## Subsystem: `steps/video_scene_detect`

### [gpu_scene_detect.py](file:///L:/GOODCUBE/projects/goodq4all/steps/video_scene_detect/gpu_scene_detect.py)
- **Relative Path**: `steps/video_scene_detect/gpu_scene_detect.py`
- **Functions**: `detect_scenes_gpu`, `detect_scenes_gpu_advanced`
- **Imports**: `__future__.annotations`, `cv2`, `numpy`, `torch`, `torch.nn.functional`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/video_scene_detect/step.py)
- **Relative Path**: `steps/video_scene_detect/step.py`
- **Functions**: `_probe_video_duration`, `_load_params`, `_fallback_single_scene`, `_detect_with_scenedetect`, `video_scene_detect`
- **Imports**: `__future__.annotations`, `cv2`, `gpu_scene_detect.detect_scenes_gpu`, `imageio_ffmpeg`, `os`, `scenedetect.SceneManager`, `scenedetect.StatsManager`, `scenedetect.detectors.ContentDetector`, `scenedetect.open_video`, `steps.common.progress_tracker.get_tracker`, `torch`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`

## Subsystem: `steps/video_summarizer`

### [__init__.py](file:///L:/GOODCUBE/projects/goodq4all/steps/video_summarizer/__init__.py)
- **Relative Path**: `steps/video_summarizer/__init__.py`
- **Imports**: `step.run_step`

### [step.py](file:///L:/GOODCUBE/projects/goodq4all/steps/video_summarizer/step.py)
- **Relative Path**: `steps/video_summarizer/step.py`
- **Functions**: `generate_video_summary_llm`, `generate_video_summary_template`, `run_step`
- **Imports**: `json`, `logging`, `requests`, `sqlite3`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

## Subsystem: `wsl2_audio`

### [audio_bridge.py](file:///L:/GOODCUBE/projects/goodq4all/wsl2_audio/audio_bridge.py)
- **Relative Path**: `wsl2_audio/audio_bridge.py`
- **Classes**: `WSL2AudioBridge`
- **Functions**: `_attach_run_id`, `_as_error_payload`, `_to_transcribe_payload`, `_to_diarize_payload`, `_to_combined_payload`, `get_bridge`, `transcribe_wsl2`, `diarize_wsl2`, `transcribe_and_diarize_wsl2`
- **Imports**: `__future__.annotations`, `scripts.wsl2_audio_bridge.WSL2AudioBridge`, `typing.Any`, `typing.Dict`, `typing.Optional`

### [audio_service.py](file:///L:/GOODCUBE/projects/goodq4all/wsl2_audio/audio_service.py)
- **Relative Path**: `wsl2_audio/audio_service.py`
- **Classes**: `GPUConfig`, `AudioJob`, `AudioService`
- **Functions**: `_resolve_hf_cache_dir`, `_load_pyannote_pipeline`, `main`
- **Imports**: `dataclasses.dataclass`, `faster_whisper.WhisperModel`, `json`, `librosa`, `logging`, `numpy`, `os`, `pathlib.Path`, `pyannote.audio.Pipeline`, `signal`, `soundfile`, `steps.common.profile_config.log_runtime_profile_state`, `steps.common.profile_config.require_gpu`, `steps.common.profile_config.resolve_wsl_gpu_config`, `sys`, `threading`, `time`, `torch`, `traceback`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [check_cuda.py](file:///L:/GOODCUBE/projects/goodq4all/wsl2_audio/check_cuda.py)
- **Relative Path**: `wsl2_audio/check_cuda.py`
- **Functions**: `print_header`, `check_cuda`, `check_libraries`, `check_environment`, `check_cudnn_libraries`, `main`
- **Imports**: `os`, `sys`, `torch`

### [fw_transcribe.py](file:///L:/GOODCUBE/projects/goodq4all/wsl2_audio/fw_transcribe.py)
- **Relative Path**: `wsl2_audio/fw_transcribe.py`
- **Functions**: `_write_json`, `_build_error_payload`, `main`
- **Imports**: `__future__.annotations`, `faster_whisper.WhisperModel`, `json`, `os`, `sys`, `torch`, `typing.Any`, `typing.Dict`, `typing.List`

### [process_audio.py](file:///L:/GOODCUBE/projects/goodq4all/wsl2_audio/process_audio.py)
- **Relative Path**: `wsl2_audio/process_audio.py`
- **Functions**: `_deep_merge`, `_load_json_dict`, `_normalize_runtime_overlay`, `_load_runtime_config`, `_resolve_secret`, `_resolve_hf_cache_dir`, `_load_pyannote_pipeline`, `clear_gpu_memory`, `get_gpu_memory_info`, `_segment_duration`, `_select_speaker_signature_segments`, `_slice_waveform_segment`, `_normalize_embedding_vector`, `_build_speaker_voice_signatures`, `process_audio`, `main`
- **Imports**: `contextlib.redirect_stdout`, `faster_whisper.WhisperModel`, `gc`, `json`, `logging`, `numpy`, `os`, `pathlib.Path`, `pyannote.audio.Pipeline`, `steps.common.profile_config.log_runtime_profile_state`, `steps.common.profile_config.require_gpu`, `steps.common.profile_config.resolve_wsl_gpu_config`, `sys`, `torch`, `torchaudio`, `traceback`, `transformers.Wav2Vec2FeatureExtractor`, `transformers.Wav2Vec2ForSequenceClassification`, `transformers.Wav2Vec2Model`, `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional`

### [test_bridge.py](file:///L:/GOODCUBE/projects/goodq4all/wsl2_audio/test_bridge.py)
- **Relative Path**: `wsl2_audio/test_bridge.py`
- **Functions**: `main`
- **Imports**: `pathlib.Path`, `sys`, `time`, `wsl2_audio.audio_bridge.WSL2AudioBridge`

### [test_pipeline.py](file:///L:/GOODCUBE/projects/goodq4all/wsl2_audio/test_pipeline.py)
- **Relative Path**: `wsl2_audio/test_pipeline.py`
- **Functions**: `print_section`, `test_audio_processing`, `main`
- **Imports**: `json`, `pathlib.Path`, `subprocess`, `sys`
