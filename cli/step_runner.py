from __future__ import annotations
import argparse
import json
import os
import sys
from typing import Any, Dict, List
import time
from pathlib import Path

# Add PARENT of repo root to Python path so "goodq4all.steps" can be imported
REPO_ROOT = Path(__file__).resolve().parents[1]
PARENT_DIR = REPO_ROOT.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

# Ensure per-env site-packages take precedence; ignore user site packages
os.environ.setdefault('PYTHONNOUSERSITE', '0')


def load_cfg(overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    from goodq4all.steps.common.config_loader import load_configs
    return load_configs(overrides or {})


def _save_memory_context(step_name: str, item: Dict[str, Any] | None, results: Dict[str, Any], cfg: Dict[str, Any]) -> None:
    """Save step results to memory database for context enrichment."""
    if not item or not results or not isinstance(results, dict):
        return
    
    try:
        # Import here to avoid circular dependencies
        from goodq4all.steps.common.memory_context_writer import save_step_context
        
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




def run_step(step_name: str, item: Dict[str, Any] | None, cfg: Dict[str, Any]) -> Dict[str, Any]:
    # Map step names to callables and call signatures
    if step_name == "video_scene_detect":
        from goodq4all.steps.video_scene_detect.step import video_scene_detect
        assert item is not None
        return video_scene_detect(item, cfg)

    if step_name == "audio_transcribe":
        from goodq4all.steps.audio_transcribe.step import audio_transcribe
        assert item is not None
        return audio_transcribe(item, cfg)
    if step_name == "image_ocr":
        from goodq4all.steps.image_ocr.step import image_ocr
        assert item is not None
        return image_ocr(item, cfg)
    if step_name == "image_caption":
        from goodq4all.steps.image_caption.step import image_caption
        assert item is not None
        return image_caption(item, cfg)
    if step_name == "object_detect":
        from goodq4all.steps.object_detect.step import object_detect
        assert item is not None
        return object_detect(item, cfg)
    if step_name == "object_track":
        from goodq4all.steps.object_track.step import object_track
        assert item is not None
        return object_track(item, cfg)
    if step_name == "object_track_yolo":
        from goodq4all.steps.object_track_yolo.step import object_track_yolo
        assert item is not None
        return object_track_yolo(item, cfg)
    if step_name == "face_embed":
        from goodq4all.steps.face_embed.step import face_embed
        assert item is not None
        return face_embed(item, cfg)
    if step_name == "text_embed":
        from goodq4all.steps.text_embed.step import text_embed
        assert item is not None
        return text_embed(item, cfg)
    if step_name == "pdf_text":
        from goodq4all.steps.pdf_text.step import pdf_to_text
        assert item is not None
        return pdf_to_text(item, cfg)
    if step_name == "image_exif":
        from goodq4all.steps.image_exif.step import image_exif
        assert item is not None
        return image_exif(item, cfg)
    if step_name == "image_embed_dino":
        from goodq4all.steps.image_embed_dino.step import image_embed_dino
        assert item is not None
        return image_embed_dino(item, cfg)
    if step_name == "image_embed_clip":
        from goodq4all.steps.image_embed_clip.step import image_embed_clip
        assert item is not None
        return image_embed_clip(item, cfg)
    if step_name == "audio_embed_clap":
        from goodq4all.steps.audio_embed_clap.step import audio_embed_clap
        assert item is not None
        return audio_embed_clap(item, cfg)
    if step_name == "emotion_classify":
        from goodq4all.steps.emotion_classify.step import emotion_classify
        assert item is not None
        return emotion_classify(item, cfg)
    if step_name == "sentiment":
        from goodq4all.steps.sentiment.step import sentiment
        assert item is not None
        return sentiment(item, cfg)
    if step_name == "home_assistant_status":
        from goodq4all.steps.home_assistant_status.step import home_assistant_status
        return home_assistant_status(cfg)
    if step_name == "system_metrics":
        from goodq4all.steps.system_metrics.step import system_metrics
        return system_metrics(cfg)
    if step_name == "audio_diarize":
        from goodq4all.steps.audio_diarize.step import audio_diarize
        assert item is not None
        return audio_diarize(item, cfg)
    if step_name == "audio_speaker_merge":
        from goodq4all.steps.audio_speaker_merge.step import audio_speaker_merge
        assert item is not None
        return audio_speaker_merge(item, cfg)
    if step_name == "audio_emotion":
        from goodq4all.steps.audio_emotion.step import audio_emotion
        assert item is not None
        return audio_emotion(item, cfg)
    if step_name == "audio_metadata":
        from goodq4all.steps.audio_metadata.step import audio_metadata
        assert item is not None
        return audio_metadata(item, cfg)
    if step_name == "audio_music_events":
        from goodq4all.steps.audio_music_events.step import audio_music_events
        assert item is not None
        return audio_music_events(item, cfg)
    if step_name == "audio_time_hints":
        from goodq4all.steps.audio_time_hints.step import audio_time_hints
        assert item is not None
        return audio_time_hints(item, cfg)
    if step_name == "tagger":
        from goodq4all.steps.tagger.step import tagger
        assert item is not None
        return tagger(item, cfg)
    if step_name == "video_scene_segmentation":
        from goodq4all.steps.audio.segmentation.phase5_video_scene_integration import process_video_chunks_with_scenes
        assert item is not None
        # Extract required inputs from item
        video_path = item.get('path') or item.get('file_path')
        audio_segments = item.get('audio_segments', [])
        output_dir = item.get('output_dir', cfg.get('processing_dir', 'L:/_DATA/GoodQ_Data/processing'))
        # Call Phase 5 processor
        return process_video_chunks_with_scenes(video_path, audio_segments, output_dir, cfg)
    
    # Phase 6: Scene Visual Embeddings
    if step_name == "scene_visual_embeddings":
        from goodq4all.steps.video.scene_visual_embeddings import run_scene_visual_embeddings
        assert item is not None
        return run_scene_visual_embeddings(item, cfg)
    
    if step_name == "cross_modal_harmonization":
        from goodq4all.steps.video.cross_modal_harmonizer import run_cross_modal_harmonization
        assert item is not None
        return run_cross_modal_harmonization(item, cfg)
    
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
        from goodq4all.common.gpu_manager import initialize_gpu_for_step
        import yaml
        
        # Load GPU config
        gpu_config_path = REPO_ROOT / 'config' / 'gpu_config.yaml'
        if gpu_config_path.exists():
            with open(gpu_config_path, 'r') as f:
                gpu_cfg = yaml.safe_load(f) or {}
        else:
            gpu_cfg = {}
        
        # Get memory fraction for this step
        step_mem_fractions = gpu_cfg.get('step_memory_fractions', {})
        memory_fraction = step_mem_fractions.get(args.step, step_mem_fractions.get('default', 0.5))
        
        # Get determinism setting
        deterministic = gpu_cfg.get('gpu', {}).get('deterministic', False)
        
        # Initialize GPU
        gpu_manager = initialize_gpu_for_step(
            step_name=args.step,
            memory_fraction=memory_fraction,
            enable_determinism=deterministic
        )
        
        # Clear cache if configured
        if gpu_cfg.get('memory', {}).get('clear_cache_before_step', True):
            gpu_manager.clear_cache()
            
    except Exception as e:
        import logging
        logging.warning(f"Could not initialize GPU manager: {e}")
        gpu_manager = None
    
    # Measure and log duration
    from goodq4all.steps.common.step_logger import log_step_run
    start_ns = time.perf_counter_ns()
    try:
        res = run_step(args.step, item, cfg)
    except Exception as exc:
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        log_step_run(cfg, args.step, item, duration_ms, "error", str(exc))
        raise
    else:
        extra: Dict[str, Any] | None = None
        if args.verbose and isinstance(res, dict):
            meta_keys: List[str] = [k for k in res.keys() if k.endswith("_meta") or k.endswith("_meta".upper()) or k in ("embedding_meta", "clap_meta")]
            if meta_keys:
                extra = {"result_meta": {k: res.get(k) for k in meta_keys}}
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        log_step_run(cfg, args.step, item, duration_ms, "ok", extra=extra)
        
        # CRITICAL: Save step results to memory database for context enrichment
        try:
            _save_memory_context(args.step, item, res, cfg)
        except Exception as save_exc:
            import logging
            logging.warning(f"Failed to save context for step {args.step}: {save_exc}")
        
        # Clear GPU cache after step if configured
        if gpu_manager is not None:
            try:
                gpu_cfg_reload = yaml.safe_load(open(REPO_ROOT / 'config' / 'gpu_config.yaml', 'r')) if (REPO_ROOT / 'config' / 'gpu_config.yaml').exists() else {}
                if gpu_cfg_reload.get('memory', {}).get('clear_cache_after_step', True):
                    gpu_manager.clear_cache()
                    
                # Log final memory stats
                if gpu_cfg_reload.get('memory', {}).get('log_memory_stats', True):
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

