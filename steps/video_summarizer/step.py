"""
Video-Level Summarization Step
Generates cohesive narrative from all scene summaries using LLM
"""
import sqlite3
import json
import requests
from typing import Dict, Any, List, Optional
import logging
from contextlib import closing

from lib.llm_client import LLMClient
from steps.common.llm_model_factory import build_llm_models
from lib.summary_aggregator import active_summary_scene_ids

logger = logging.getLogger(__name__)
MAX_SCENE_SUMMARIES_IN_PROMPT = 20
VIDEO_SUMMARY_PROMPT_VERSION = "v1.1.0"


def _scene_summary_records_for_prompt(
    records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return records[:MAX_SCENE_SUMMARIES_IN_PROMPT]


def _filter_target_scene_summary_records(
    db_path: str,
    video_hash: str,
    records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    try:
        target_scene_ids = active_summary_scene_ids(conn, db_path, video_hash)
    finally:
        conn.close()

    filtered_records = []
    for record in records:
        if not isinstance(record, dict):
            continue
        scene_id = record.get('scene_id')
        summary = record.get('summary')
        if (
            scene_id not in target_scene_ids
            or not isinstance(summary, str)
            or not summary.strip()
        ):
            continue
        filtered_records.append(record)
    return filtered_records


def _load_target_scene_summary_records(
    db_path: str,
    video_hash: str,
) -> List[Dict[str, Any]]:
    """Return usable scene-summary rows belonging to the target video."""
    conn = sqlite3.connect(db_path)
    try:
        c = conn.cursor()
        target_scene_ids = active_summary_scene_ids(conn, db_path, video_hash)

        c.execute("""
            SELECT id, content, created_at FROM summaries
            WHERE category='scene_summary'
            ORDER BY id
        """)

        records = []
        for summary_id, content_json, created_at in c.fetchall():
            try:
                content = json.loads(content_json)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse content JSON from summary records: {e}")
                continue

            if not isinstance(content, dict):
                continue
            scene_id = content.get('scene_id')
            summary = content.get('summary')
            if (
                scene_id not in target_scene_ids
                or not isinstance(summary, str)
                or not summary.strip()
            ):
                continue
            records.append({
                "summary_id": summary_id,
                "scene_id": scene_id,
                "summary": summary,
                "created_at": created_at,
            })
        return records
    finally:
        conn.close()


def generate_video_summary_llm(
    cfg: Dict,
    video_hash: str,
    db_path: str,
    scene_summary_records: Optional[List[Dict[str, Any]]] = None,
    *,
    generation_provenance: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Generate video-level summary from all scene summaries using LLM
    
    Args:
        cfg: Configuration dictionary with LLM settings
        video_hash: Video hash to summarize
        db_path: Path to memory database
        
    Returns:
        Video summary string or None if generation fails
    """
    if generation_provenance is None:
        generation_provenance = {}
    try:
        if scene_summary_records is None:
            scene_summary_records = _load_target_scene_summary_records(
                db_path,
                video_hash,
            )
        else:
            scene_summary_records = _filter_target_scene_summary_records(
                db_path,
                video_hash,
                scene_summary_records,
            )
        prompt_records = _scene_summary_records_for_prompt(scene_summary_records)
        scene_summaries = [record["summary"] for record in prompt_records]
        scene_count = len(scene_summary_records)
        
        if not scene_summaries:
            logger.warning(f"No scene summaries found for video {video_hash}")
            generation_provenance["fallback_reason"] = "no_scene_summaries"
            return None

        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Get video metadata from first scene
        c.execute("SELECT meta FROM scenes WHERE video_hash=? LIMIT 1", (video_hash,))
        scene_row = c.fetchone()
        if scene_row:
            scene_meta = json.loads(scene_row[0])
            video_meta = {
                'filename': scene_meta.get('video_path', 'Unknown'),
                'duration': 0
            }
        else:
            video_meta = {'filename': 'Unknown', 'duration': 0}
        
        # Calculate total duration from all scenes
        c.execute("SELECT MAX(end) FROM scenes WHERE video_hash=?", (video_hash,))
        max_end = c.fetchone()[0]
        if max_end:
            video_meta['duration'] = max_end
        
        conn.close()
        
        # Build prompt
        scenes_text = "\n\n".join([
            f"Scene {i+1}: {summary}" 
            for i, summary in enumerate(scene_summaries)
        ])
        
        if len(scene_summary_records) > len(prompt_records):
            scenes_text += (
                f"\n\n[... and {len(scene_summary_records) - len(prompt_records)} more scenes]"
            )
        
        duration = video_meta.get('duration', 0)
        filename = video_meta.get('filename', 'Unknown')
        
        prompt = f"""Write a short, evidence-bound summary of these machine-generated scene records.

VIDEO METADATA:
- File: {filename}
- Duration: {duration:.1f} seconds
- Total Scenes: {scene_count}

SCENE-BY-SCENE BREAKDOWN:
{scenes_text}

Use at most five short sentences, and no more than one sentence per scene.
Describe only observations explicitly present in the supplied records:
- Attribute visual descriptions to the caption and spoken content to the transcript.
- Preserve questions, requests, negation and uncertainty. A requested action is not a completed action.
- Entity names are textual mentions, not identified visible people or speakers. Do not assign names, gender, ownership or relationships to people.
- Object labels do not establish locations, interactions or spatial relationships.
- Emotion and sentiment scores are model estimates, not established feelings. Omit them from this factual summary.
Do not invent events, transitions, motives, an ending or an overall story. Omit unsupported details.

VIDEO SUMMARY:"""
        
        # Use the same configured provider selection as scene context analysis.
        llm_config = cfg.get('llm', {})
        generation_provenance["model_selection_policy"] = "quality_or_reasoning"
        narrative_models = [
            model for model in build_llm_models(cfg)
            if {"quality", "reasoning"}.intersection(model.capabilities)
        ]
        if not narrative_models:
            generation_provenance["fallback_reason"] = "no_quality_capable_model_configured"
            logger.warning("No quality-capable model configured for video narrative")
            return None
        with closing(LLMClient(
            models=narrative_models,
            health_check_interval=int(llm_config.get("health_check_interval", 60)),
            max_retries=int(llm_config.get("max_retries", 3)),
            timeout=int(llm_config.get("timeout", 30)),
            cache_ttl=int(llm_config.get("cache_ttl", 300)),
            enable_health_checks=False,
            allow_auto_activation=False,
            allow_environment_proxies=False,
        )) as client:
            result = client.chat(
                messages=[
                    {
                        "role": "system", 
                        "content": "Summarize supplied evidence conservatively. Preserve its source and uncertainty; do not infer identities or events."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=llm_config.get('temperature', 0.5),
                max_tokens=500,
            )
            summary = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            if summary:
                model = client.last_model_used
                if model is not None:
                    api_url = f"{model.endpoint}/chat/completions"
                    generation_provenance.update({
                        "model_backend": f"{model.model_id} ({api_url})",
                        "model_id": model.model_id,
                        "api_url": api_url,
                        "provider": client.last_provider_used,
                    })
                logger.info(f"Generated video summary ({len(summary)} chars)")
                return summary
            generation_provenance["fallback_reason"] = "empty_model_output"
            
    except requests.Timeout:
        logger.error("LLM request timed out during video summarization")
        generation_provenance["fallback_reason"] = "llm_timeout"
        return None
    except Exception as e:
        logger.error(f"Video summarization failed: {e}")
        generation_provenance["fallback_reason"] = f"llm_error:{type(e).__name__}"
        return None
    
    return None


def generate_video_summary_template(
    cfg: Dict, video_hash: str, db_path: str,
    scene_summary_records: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Generate template-based video summary (fallback)
    
    Args:
        cfg: Configuration dictionary
        video_hash: Video hash to summarize
        db_path: Path to memory database
        
    Returns:
        Template-based video summary
    """
    if scene_summary_records is None:
        scene_summary_records = _load_target_scene_summary_records(db_path, video_hash)
    with closing(sqlite3.connect(db_path)) as conn:
        active_scene_ids = active_summary_scene_ids(conn, db_path, video_hash)
        rows = conn.execute(
            "SELECT id, start, end, meta FROM scenes WHERE video_hash=? ORDER BY start, id",
            (video_hash,),
        ).fetchall()
    rows = [row for row in rows if row[0] in active_scene_ids]
    scene_bounds = {row[0]: (row[1], row[2]) for row in rows}
    records = [record for record in scene_summary_records if record.get("scene_id") in scene_bounds]
    selected = _scene_summary_records_for_prompt(records)
    scene_meta = json.loads(rows[0][3]) if rows and rows[0][3] else {}
    filename = scene_meta.get("video_path") or video_hash
    duration = max((row[2] or 0 for row in rows), default=0)
    parts = [
        f"Machine-generated scene evidence for video '{filename}' "
        f"({len(rows)} active scenes, ending at {duration:.1f} seconds).",
        "The scene summaries below are reproduced verbatim. They are model-generated "
        "observations, not verified identities or events; their uncertainty is retained.",
    ]
    for record in selected:
        start, end = scene_bounds[record["scene_id"]]
        bounds = f"{start:.1f}-{end:.1f} seconds" if start is not None and end is not None else "bounds unavailable"
        parts.append(
            f"Scene {record['scene_id']} [{bounds}] (summary {record['summary_id']}):\n"
            f"{record['summary']}"
        )
    if not selected:
        parts.append("No usable scene summaries are available for this video.")
    omitted = len(records) - len(selected)
    if omitted:
        parts.append(f"{omitted} additional scene summary omitted by the {MAX_SCENE_SUMMARIES_IN_PROMPT}-record limit.")
    return "\n\n".join(parts)


def run_step(cfg: Dict, video_hash: str = None) -> Dict[str, Any]:
    """
    Execute video summarization step
    
    Args:
        cfg: Configuration dictionary
        video_hash: Video hash to summarize (if None, summarizes all videos)
        
    Returns:
        Result dictionary with success status and summary
    """
    db_path = cfg['paths']['db_path']
    
    # If no video_hash provided, get the first one
    if not video_hash:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT DISTINCT video_hash FROM scenes LIMIT 1")
        row = c.fetchone()
        conn.close()
        if not row:
            return {
                'success': False,
                'error': 'No videos found in database'
            }
        video_hash = row[0]
    
    # Check if LLM video summarization is enabled
    use_llm = cfg.get('llm', {}).get('features', {}).get('video_summarization', True)
    
    # Select prompt inputs and provenance from one exact target-video row set.
    scene_summary_records = []
    try:
        scene_summary_records = _load_target_scene_summary_records(
            db_path,
            video_hash,
        )
    except Exception as pe:
        logger.warning(f"Failed to query scene summaries for provenance: {pe}")
    source_artifact_versions = [
        {
            "summary_id": record["summary_id"],
            "scene_id": record["scene_id"],
            "created_at": record["created_at"],
        }
        for record in _scene_summary_records_for_prompt(scene_summary_records)
    ]

    # Generate video summary
    video_summary = None
    generation_method = 'template'
    generation_provenance = {}
    if use_llm:
        video_summary = generate_video_summary_llm(
            cfg,
            video_hash,
            db_path,
            scene_summary_records,
            generation_provenance=generation_provenance,
        )
        if video_summary:
            generation_method = 'llm'
    
    # Fall back to template if LLM failed
    if not video_summary:
        if use_llm:
            logger.warning("LLM video summarization failed, using template fallback")
        video_summary = generate_video_summary_template(
            cfg, video_hash, db_path, scene_summary_records,
        )
    
    # Store in database with full provenance
    from datetime import datetime, timezone
    provenance = {
        "model_backend": "template",
        "prompt_version": VIDEO_SUMMARY_PROMPT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_artifact_versions": source_artifact_versions,
        **generation_provenance,
    }
    
    if not cfg.get("ingestion_isolation", False):
        try:
            payload = json.dumps({
                'video_hash': video_hash,
                'summary': video_summary,
                'method': generation_method,
                'provenance': provenance
            }, ensure_ascii=False)
            
            with closing(sqlite3.connect(db_path)) as conn, conn:
                # Serialize the active-scope check and insert with scene removal.
                conn.execute("BEGIN IMMEDIATE")
                active = active_summary_scene_ids(conn, db_path, video_hash)
                if not active or any(record["scene_id"] not in active for record in scene_summary_records):
                    raise RuntimeError("Video has no active scenes; summary was not stored")
                conn.execute("""
                    INSERT OR REPLACE INTO summaries (summary_type, category, content, created_at)
                    VALUES ('video', 'video_summary', ?, datetime('now'))
                """, (payload,))
            
            logger.info(f"Video summary stored for video {video_hash} with provenance info")
        except Exception as e:
            logger.error(f"Failed to store video summary: {e}")
            return {
                'success': False,
                'error': str(e),
                'video_hash': video_hash
            }

    return {
        'success': True,
        'summary': video_summary,
        'video_hash': video_hash,
        'method': generation_method,
        'provenance': provenance
    }
