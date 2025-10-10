from __future__ import annotations
import argparse
import json
import os
import sys
from typing import Any, Dict, List
import time

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
        from goodq4all.steps.common.memory import compute_file_hash
        
        # Extract scene context from item
        video_hash = item.get('video_hash')
        scene_id = item.get('scene_id')
        scene = item.get('scene', {})
        
        # If no scene_id but we have source_path, derive from that
        if not scene_id:
            source_path = item.get('source_path')
            if source_path:
                # For frames/audio clips that belong to scenes
                # Try to construct scene_id from filename pattern
                basename = os.path.basename(source_path)
                if '_scene_' in basename or 'scene_' in basename:
                    # Extract scene identifier
                    parts = basename.split('scene_')
                    if len(parts) > 1:
                        scene_num = parts[1].split('.')[0].split('_')[0]
                        scene_id = f"scene_{scene_num}"
        
        # If we have video context, save enriched metadata
        if video_hash and scene_id:
            save_step_context(cfg, video_hash, scene, scene_id, step_name, results)
        
    except Exception as e:
        # Don't fail the step if context saving fails
        # Just log the error
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to save memory context for {step_name}: {e}")


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
        with open(args.cfg, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    else:
        cfg = load_cfg(overrides)
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
        _save_memory_context(args.step, item, res, cfg)

    out = json.dumps(res, ensure_ascii=False)
    if args.out_path:
        with open(args.out_path, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        sys.stdout.write(out)


if __name__ == "__main__":
    main()

