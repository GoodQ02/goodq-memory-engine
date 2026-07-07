from __future__ import annotations
import sys
# Global encoding safeguard for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")

import argparse
import hashlib
import json
import os
import sys
import logging
from typing import Any, Dict, List
import time
from pathlib import Path

# Add repo root to Python path so "steps.*" modules can be imported
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Ensure per-env site-packages take precedence; ignore user site packages
os.environ.setdefault('PYTHONNOUSERSITE', '1')
logger = logging.getLogger(__name__)
_PATH_FALLBACK_WARNED = False

_EXPLICIT_META_STATUS_FIELD_BY_STEP = {
    "audio_embed_clap": "clap_meta",
    "audio_emotion": "audio_emotion_meta",
    "emotion_classify": "emotion_meta",
    "image_caption": "caption_meta",
    "image_embed_clip": "clip_meta",
    "image_embed_dino": "dino_meta",
    "image_ocr": "ocr_meta",
    "sentiment": "sentiment_meta",
}

_META_ERROR_STATUSES = {"error"}
_META_SKIPPED_STATUSES = {
    "dependency_missing",
    "no_file",
    "no_index_path",
    "no_source_path",
    "no_text",
    "skipped",
    "unavailable",
}
_EMBEDDING_EMISSION_BY_STEP = {
    "audio_embed_clap": True,
    "image_embed_clip": True,
    "image_embed_dino": True,
    "sentiment": False,
}
OPENMP_GUARD_STEPS = {
    "audio_embed_clap",
    "image_embed_clip",
    "image_embed_dino",
    "scene_visual_embeddings",
    "text_embed",
}
OPENMP_GUARD_ENV = {
    "KMP_DUPLICATE_LIB_OK": "TRUE",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
}


def apply_step_runtime_guards(step_name: str) -> None:
    if step_name not in OPENMP_GUARD_STEPS:
        return
    for key, value in OPENMP_GUARD_ENV.items():
        os.environ.setdefault(key, value)


def _emit_subprocess_env_fingerprint(step_name: str) -> None:
    if step_name != "tagger":
        return
    env_subset = {
        "OMP_NUM_THREADS": os.getenv("OMP_NUM_THREADS"),
        "MKL_NUM_THREADS": os.getenv("MKL_NUM_THREADS"),
        "NUMEXPR_MAX_THREADS": os.getenv("NUMEXPR_MAX_THREADS"),
        "TOKENIZERS_PARALLELISM": os.getenv("TOKENIZERS_PARALLELISM"),
    }
    payload = {
        "event": "subprocess_env_fingerprint",
        "step": step_name,
        "pid": os.getpid(),
        "env": env_subset,
    }
    payload_raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload["fingerprint"] = hashlib.sha256(payload_raw.encode("utf-8")).hexdigest()[:16]
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr, flush=True)


def load_cfg(overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    from steps.common.config_loader import load_configs
    return load_configs(overrides or {})


def _save_memory_context(step_name: str, item: Dict[str, Any] | None, results: Dict[str, Any], cfg: Dict[str, Any]) -> None:
    """Save step results to memory database for context enrichment."""
    if not item or not results or not isinstance(results, dict):
        return
    
    try:
        # Import here to avoid circular dependencies
        from steps.common.memory_context_writer import save_step_context
        
        # Extract scene context from item
        video_hash = item.get('video_hash')
        scene_id = item.get('scene_id')
        scene = item.get('scene', {})
        
        # Validate we have required context
        if not video_hash or not scene_id or not scene:
            return
        
        # Ensure scene has timing info
        if 'start' not in scene or 'end' not in scene:
            return
        
        # Save enriched metadata to database
        save_step_context(cfg, video_hash, scene, scene_id, step_name, results)
        
    except Exception as e:
        # Don't fail the step if context saving fails
        # Just log the error
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to save memory context for {step_name}: {e}", exc_info=True)


def _derive_step_log_outcome(
    step_name: str,
    result: Dict[str, Any] | None,
    *,
    verbose: bool,
) -> tuple[str, str | None, Dict[str, Any] | None]:
    extra: Dict[str, Any] | None = None
    meta_field = _EXPLICIT_META_STATUS_FIELD_BY_STEP.get(step_name)
    if meta_field and isinstance(result, dict):
        result_meta = result.get(meta_field)
        if isinstance(result_meta, dict):
            meta_status = str(result_meta.get("status") or "").strip().lower()
            extra = {
                "result_meta": {meta_field: result_meta},
                "embedding_emitted": bool(_EMBEDDING_EMISSION_BY_STEP.get(step_name, False) and meta_status == "ok"),
            }
            if meta_status in _META_ERROR_STATUSES:
                error_text = str(result_meta.get("error") or "").strip() or f"{step_name} failed"
                error_reason = str(result_meta.get("reason") or meta_status).strip().lower() or meta_status
                extra["reason"] = f"{step_name}_{error_reason}"
                return "error", error_text, extra
            if meta_status in _META_SKIPPED_STATUSES:
                skip_reason = str(result_meta.get("reason") or meta_status).strip().lower() or meta_status
                extra["reason"] = f"{step_name}_{skip_reason}"
                return "skipped", None, extra
            return "ok", None, extra

    if verbose and isinstance(result, dict):
        meta_keys: List[str] = [
            k
            for k in result.keys()
            if k.endswith("_meta") or k.endswith("_meta".upper()) or k in ("embedding_meta", "clap_meta")
        ]
        if meta_keys:
            extra = {"result_meta": {k: result.get(k) for k in meta_keys}}
    return "ok", None, extra




def run_step(step_name: str, item: Dict[str, Any] | None, cfg: Dict[str, Any]) -> Dict[str, Any]:
    global _PATH_FALLBACK_WARNED
    # Map step names to callables and call signatures
    if step_name == "video_scene_detect":
        from steps.video_scene_detect.step import video_scene_detect
        assert item is not None
        return video_scene_detect(item, cfg)

    if step_name == "audio_transcribe":
        from steps.audio.audio_wsl2_bridge import audio_transcribe_wsl2
        assert item is not None
        audio_path = item.get("audio_path") or item.get("path")
        if not audio_path:
            return {"transcript": "", "transcript_segments": []}
        audio_cfg = cfg.get("audio", {})
        transcribe_cfg = audio_cfg.get("transcribe", {})
        timeout = transcribe_cfg.get("timeout", 3600)
        return audio_transcribe_wsl2(str(audio_path), timeout=timeout)
    if step_name == "audio_transcribe_local":
        from steps.audio_transcribe.step import audio_transcribe
        assert item is not None
        return audio_transcribe(item, cfg)
    if step_name == "image_ocr":
        from steps.image_ocr.step import image_ocr
        assert item is not None
        return image_ocr(item, cfg)
    if step_name == "image_caption":
        from steps.image_caption.step import image_caption
        assert item is not None
        return image_caption(item, cfg)
    if step_name == "object_detect":
        from steps.object_detect.step import object_detect
        assert item is not None
        return object_detect(item, cfg)
    if step_name == "object_track":
        from steps.object_track_yolo.step import object_track_yolo
        assert item is not None
        return object_track_yolo(item, cfg)
    if step_name == "object_track_yolo":
        from steps.object_track_yolo.step import object_track_yolo
        assert item is not None
        return object_track_yolo(item, cfg)
    if step_name == "face_embed":
        from steps.face_embed.step import face_embed
        assert item is not None
        return face_embed(item, cfg)
    if step_name == "text_embed":
        from steps.text_embed.step import text_embed
        assert item is not None
        return text_embed(item, cfg)
    if step_name == "pdf_text":
        from steps.pdf_text.step import pdf_to_text
        assert item is not None
        return pdf_to_text(item, cfg)
    if step_name == "image_exif":
        from steps.image_exif.step import image_exif
        assert item is not None
        return image_exif(item, cfg)
    if step_name == "image_embed_dino":
        from steps.image_embed_dino.step import image_embed_dino
        assert item is not None
        return image_embed_dino(item, cfg)
    if step_name == "image_embed_clip":
        from steps.image_embed_clip.step import image_embed_clip
        assert item is not None
        return image_embed_clip(item, cfg)
    if step_name == "audio_embed_clap":
        from steps.audio_embed_clap.step import audio_embed_clap
        assert item is not None
        return audio_embed_clap(item, cfg)
    if step_name == "emotion_classify":
        from steps.emotion_classify.step import emotion_classify
        assert item is not None
        return emotion_classify(item, cfg)
    if step_name == "sentiment":
        from steps.sentiment.step import sentiment
        assert item is not None
        return sentiment(item, cfg)
    if step_name == "home_assistant_status":
        from steps.home_assistant_status.step import home_assistant_status
        return home_assistant_status(cfg)
    if step_name == "system_metrics":
        from steps.system_metrics.step import system_metrics
        return system_metrics(cfg)
    if step_name == "audio_diarize":
        from steps.audio.audio_wsl2_bridge import audio_diarize_wsl2
        assert item is not None
        audio_path = item.get("audio_path") or item.get("path")
        if not audio_path:
            return {"speakers": [], "speaker_segments": []}
        audio_cfg = cfg.get("audio", {})
        diarize_cfg = audio_cfg.get("diarize", {})
        timeout = diarize_cfg.get("timeout", 3600)
        return audio_diarize_wsl2(str(audio_path), timeout=timeout)
    if step_name == "audio_unified_wsl2":
        from steps.audio.audio_wsl2_bridge import audio_unified_wsl2
        assert item is not None
        audio_path = item.get("audio_path") or item.get("path")
        if not audio_path:
            return {"status": "error", "error": "No audio path provided"}
        return audio_unified_wsl2(str(audio_path), scene_id=item.get("scene_id"), duration=item.get("duration"))
    if step_name == "audio_speaker_merge":
        from steps.audio_speaker_merge.step import audio_speaker_merge
        assert item is not None
        return audio_speaker_merge(item, cfg)
    if step_name == "audio_emotion":
        from steps.audio_emotion.step import audio_emotion
        assert item is not None
        return audio_emotion(item, cfg)
    if step_name == "audio_metadata":
        from steps.audio_metadata.step import audio_metadata
        assert item is not None
        return audio_metadata(item, cfg)
    if step_name == "audio_music_events":
        from steps.audio_music_events.step import audio_music_events
        assert item is not None
        return audio_music_events(item, cfg)
    if step_name == "audio_time_hints":
        from steps.audio_time_hints.step import audio_time_hints
        assert item is not None
        return audio_time_hints(item, cfg)
    if step_name == "tagger":
        from steps.tagger.step import tagger
        assert item is not None
        return tagger(item, cfg)
    if step_name == "video_scene_segmentation":
        from steps.audio.segmentation.phase5_video_scene_integration import process_video_chunks_with_scenes
        assert item is not None
        # Extract required inputs from item
        video_path = item.get('path') or item.get('file_path')
        audio_segments = item.get('audio_segments', [])
        output_dir = item.get('output_dir')
        if not output_dir:
            paths_cfg = cfg.get('paths', {}) if isinstance(cfg, dict) else {}
            output_dir = (
                paths_cfg.get('processing')
                or cfg.get('processing_dir')
                or (str(Path(paths_cfg.get('data_root')) / 'processing') if paths_cfg.get('data_root') else None)
            )
        if not output_dir:
            if not _PATH_FALLBACK_WARNED:
                logger.warning(
                    "step_runner path fallback used path_key=%s derived_from=%s",
                    "output_dir",
                    "cwd",
                )
                _PATH_FALLBACK_WARNED = True
            output_dir = str(Path.cwd() / "processing")
        # Call Phase 5 processor
        return process_video_chunks_with_scenes(video_path, audio_segments, output_dir, cfg)
    
    # Phase 6: Scene Visual Embeddings
    if step_name == "scene_visual_embeddings":
        from steps.video.scene_visual_embeddings import run_scene_visual_embeddings
        assert item is not None
        return run_scene_visual_embeddings(item, cfg)
    
    if step_name == "cross_modal_harmonization":
        from steps.video.cross_modal_harmonizer import run_cross_modal_harmonization
        assert item is not None
        return run_cross_modal_harmonization(item, cfg)
    
    if step_name == "video_summarizer":
        from steps.video_summarizer.step import run_step as run_video_summarizer
        if not item:
            raise ValueError("Input item dictionary is required for video_summarizer step")
        video_hash = item.get("video_hash")
        if not isinstance(video_hash, str) or not video_hash.strip():
            raise ValueError("A non-empty string 'video_hash' is required for video_summarizer step")
        return run_video_summarizer(cfg, video_hash.strip())
    
    raise SystemExit(f"Unknown step: {step_name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", required=True)
    ap.add_argument("--in", dest="in_path", help="Path to item JSON", required=False)
    ap.add_argument("--out", dest="out_path", help="Path to write result JSON", required=False)
    ap.add_argument("--overrides", help="Path to config overrides JSON", required=False)
    ap.add_argument("--cfg", help="Path to full resolved config JSON", required=False)
    ap.add_argument("--verbose", action="store_true", help="Enable verbose logging of step metadata")
    args = ap.parse_args()

    apply_step_runtime_guards(args.step)

    item = None
    if args.in_path:
        with open(args.in_path, "r", encoding="utf-8") as f:
            item = json.load(f)

    overrides = None
    if args.overrides and os.path.isfile(args.overrides):
        with open(args.overrides, "r", encoding="utf-8") as f:
            overrides = json.load(f)

    if args.cfg and os.path.isfile(args.cfg):
        # Try JSON first, fallback to YAML loading
        try:
            with open(args.cfg, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except json.JSONDecodeError:
            # Not JSON, load using config_loader which handles YAML
            cfg = load_cfg(overrides)
    else:
        cfg = load_cfg(overrides)
    
    # Initialize GPU management for this step
    try:
        from common.gpu_manager import initialize_gpu_for_step
        
        # Load GPU config from master config
        gpu_cfg = cfg.get('gpu', {})
        
        # Get memory fraction for this step from step_memory_fractions, step_memory, or the global memory_fraction
        step_mem_fractions = gpu_cfg.get('step_memory_fractions') or gpu_cfg.get('step_memory') or {}
        memory_fraction = step_mem_fractions.get(args.step, gpu_cfg.get('memory_fraction', 0.5))
        
        # Get determinism setting
        deterministic = gpu_cfg.get('deterministic', False)
        
        # Initialize GPU
        gpu_manager = initialize_gpu_for_step(
            step_name=args.step,
            memory_fraction=memory_fraction,
            enable_determinism=deterministic
        )
        
        # Clear cache if configured
        if gpu_cfg.get('clear_cache_before_step', True):
            gpu_manager.clear_cache()
            
    except Exception as e:
        import logging
        logging.warning(f"Could not initialize GPU manager: {e}")
        gpu_manager = None
    
    # Measure and log duration
    from steps.common.step_logger import log_step_run
    start_ns = time.perf_counter_ns()
    _emit_subprocess_env_fingerprint(args.step)
    try:
        res = run_step(args.step, item, cfg)
    except Exception as exc:
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        log_step_run(cfg, args.step, item, duration_ms, "error", str(exc))
        raise
    else:
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        log_status, log_error, extra = _derive_step_log_outcome(args.step, res, verbose=args.verbose)
        log_step_run(cfg, args.step, item, duration_ms, log_status, log_error, extra=extra)
 
        # CRITICAL: Save step results to memory database for context enrichment
        try:
            _save_memory_context(args.step, item, res, cfg)
        except Exception as save_exc:
            import logging
            logging.warning(f"Failed to save context for step {args.step}: {save_exc}")
        
        # Clear GPU cache after step if configured
        if gpu_manager is not None:
            try:
                gpu_cfg = cfg.get('gpu', {})
                if gpu_cfg.get('clear_cache_after_step', True):
                    gpu_manager.clear_cache()
                    
                # Log final memory stats
                if gpu_cfg.get('log_memory_stats', True):
                    stats = gpu_manager.get_memory_stats()
                    if stats.get('cuda_available'):
                        import logging
                        logging.info(f"[{args.step}] Final GPU Memory: {stats['allocated_gb']}/{stats['total_gb']} GB ({stats['utilization_pct']}%)")
            except Exception as e:
                pass

    out = json.dumps(res, ensure_ascii=False)
    if args.out_path:
        with open(args.out_path, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        sys.stdout.write(out)


if __name__ == "__main__":
    main()
