"""
ZenML pipeline that orchestrates multimodal ingestion while delegating each
heavy step to its own Conda environment via the CLI step runner.

Prereqs:
- Prepare envs: `pwsh scripts/prepare_step_envs.ps1`
- Register local ZenML stack: `pwsh scripts/bootstrap_zenml.ps1`

Run (example):
    from steps.pipelines.ingest_multimodal_conda import ingest_multimodal
    ingest_multimodal()
"""
from typing import Any, Dict, List

from zenml import pipeline, step

from goodq4all.steps.common.config_loader import load_configs
from goodq4all.steps.common.conda_runner import run_conda_step
from goodq4all.steps.common.memory import append_long_term_summary, store_short_term_summary
from goodq4all.steps.common.tag_utils import canonicalize_taxonomy
from goodq4all.steps.discover_sources.step import discover_sources
from materializers.json_materializer import JSONMaterializer
from goodq4all.steps.video_ingest.step import video_ingest_and_summarize as _video_ingest_and_summarize
from goodq4all.steps.overview.step import overview as _overview


@step(enable_cache=False, output_materializers=JSONMaterializer)
def load_config_step() -> Dict[str, Any]:
    return load_configs({})


@step(enable_cache=False, output_materializers=JSONMaterializer)
def discover_sources_step(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    return discover_sources(cfg)


@step(enable_cache=False, output_materializers=JSONMaterializer)
def process_items_step(items: List[Dict[str, Any]], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for it in items:
        mod = it.get("modality")
        enriched = dict(it)
        if mod == "audio":
            t = run_conda_step("goodq_audio_transcribe", "audio_transcribe", enriched, cfg)
            enriched.update(t)
            cl = run_conda_step("goodq_audio_embed", "audio_embed_clap", enriched, cfg)
            enriched.update(cl)
            aemo = run_conda_step("goodq_audio_emotion", "audio_emotion", enriched, cfg)
            enriched.update(aemo)
            ameta = run_conda_step("goodq_audio_metadata", "audio_metadata", enriched, cfg)
            enriched.update(ameta)
            # new: time hints and music/event detection
            th = run_conda_step("goodq_audio_metadata", "audio_time_hints", enriched, cfg)
            enriched.update(th)
            me = run_conda_step("goodq_audio_metadata", "audio_music_events", enriched, cfg)
            enriched.update(me)
        if mod == "image":
            o = run_conda_step("goodq_core", "image_ocr", enriched, cfg)
            enriched.update(o)
            c = run_conda_step("goodq_core", "image_caption", enriched, cfg)
            enriched.update(c)
            d = run_conda_step("goodq_core", "object_detect", enriched, cfg)
            enriched.update(d)
            f = run_conda_step("goodq_core", "face_embed", enriched, cfg)
            enriched.update(f)
            ex = run_conda_step("goodq_core", "image_exif", enriched, cfg)
            enriched.update(ex)
            din = run_conda_step("goodq_core", "image_embed_dino", enriched, cfg)
            enriched.update(din)
            cli = run_conda_step("goodq_core", "image_embed_clip", enriched, cfg)
            enriched.update(cli)
        if mod == "video":
            # Phase 5: Video scene detection aligned with audio segmentation
            scene_result = run_conda_step("goodq_core", "video_scene_segmentation", enriched, cfg)
            enriched.update(scene_result)
            
            # Phase 6: Scene visual embeddings & cross-modal harmonization
            phase6_cfg = cfg.get('phase6', {})
            if phase6_cfg.get('enabled', True):
                vis_out = run_conda_step("goodq_core", "scene_visual_embeddings", enriched, cfg)
                enriched.update(vis_out)
                
                harmonized = run_conda_step("goodq_core", "cross_modal_harmonization", enriched, cfg)
                enriched.update(harmonized)
        if mod == "pdf":
            p = run_conda_step("goodq_core", "pdf_text", enriched, cfg)
            enriched.update(p)
        # universal steps
        e = run_conda_step("goodq_core", "text_embed", enriched, cfg)
        enriched.update(e)
        s = run_conda_step("goodq_core", "sentiment", enriched, cfg)
        enriched.update(s)
        m = run_conda_step("goodq_core", "emotion_classify", enriched, cfg)
        enriched.update(m)
        tg = run_conda_step("goodq_core", "tagger", enriched, cfg)
        enriched.update(tg)
        canonicalize_taxonomy(enriched)
        out.append(enriched)
    return out


@step(enable_cache=False, output_materializers=JSONMaterializer)
def summarize_results_step(results: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Dict[str, Any]:
    mods: Dict[str, int] = {}
    frames_total = 0
    tags: Dict[str, int] = {}
    for it in results:
        m = it.get("modality")
        if m:
            mods[m] = mods.get(m, 0) + 1
        if isinstance(it.get("frames"), list):
            frames_total += len(it["frames"])  # type: ignore[index]
        for t in (it.get("tags") or []):
            tags[t] = tags.get(t, 0) + 1
    top_tags = sorted(tags.items(), key=lambda kv: kv[1], reverse=True)[:10]
    summary = {
        "count": len(results),
        "modalities": mods,
        "total_frames": frames_total,
        "top_tags": [{"tag": k, "count": v} for k, v in top_tags],
    }
    try:
        store_short_term_summary(cfg, summary, category="ingest_summary")
        append_long_term_summary(
            cfg,
            summary,
            category="ingest_summary",
            fields=["count", "modalities", "total_frames", "top_tags"],
        )
    except Exception:
        pass
    return summary


@pipeline(enable_cache=False)
def ingest_multimodal():
    cfg = load_config_step()
    items = discover_sources_step(cfg)
    results = process_items_step(items, cfg)
    _ = summarize_results_step(results, cfg)
    vids = video_ingest_and_summarize_step(cfg)
    _ = overview_step(results, vids, cfg)
@step(enable_cache=False, output_materializers=JSONMaterializer)
def video_ingest_and_summarize_step(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return _video_ingest_and_summarize(cfg)


@step(enable_cache=False, output_materializers=JSONMaterializer)
def overview_step(results: List[Dict[str, Any]], video_summary: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    overview = _overview(results, video_summary, cfg)
    try:
        store_short_term_summary(cfg, overview, category="overview")
        append_long_term_summary(
            cfg,
            overview,
            category="overview",
            fields=["db", "faiss", "modalities", "frames_total", "top_tags", "top_entities", "video_advisories", "audio_insights"],
        )
    except Exception:
        pass
    return overview
