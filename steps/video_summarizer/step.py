"""
Video-Level Summarization Step
Generates cohesive narrative from all scene summaries using LLM
"""
import sqlite3
import json
import requests
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def generate_video_summary_llm(cfg: Dict, video_hash: str, db_path: str) -> Optional[str]:
    """
    Generate video-level summary from all scene summaries using LLM
    
    Args:
        cfg: Configuration dictionary with LLM settings
        video_hash: Video hash to summarize
        db_path: Path to memory database
        
    Returns:
        Video summary string or None if generation fails
    """
    try:
        # Fetch all scene summaries for this video
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Get scene summaries
        c.execute("""
            SELECT content FROM summaries 
            WHERE category='scene_summary' 
            ORDER BY id
        """)
        
        scene_summaries = []
        scene_count = 0
        for (content_json,) in c.fetchall():
            try:
                content = json.loads(content_json)
                summary = content.get('summary', '')
                if summary:
                    scene_summaries.append(summary)
                    scene_count += 1
            except:
                continue
        
        if not scene_summaries:
            logger.warning(f"No scene summaries found for video {video_hash}")
            conn.close()
            return None
        
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
            for i, summary in enumerate(scene_summaries[:20])  # Limit to first 20 scenes
        ])
        
        if len(scene_summaries) > 20:
            scenes_text += f"\n\n[... and {len(scene_summaries) - 20} more scenes]"
        
        duration = video_meta.get('duration', 0)
        filename = video_meta.get('filename', 'Unknown')
        
        prompt = f"""Analyze this video and generate a cohesive 2-3 paragraph summary:

VIDEO METADATA:
- File: {filename}
- Duration: {duration:.1f} seconds
- Total Scenes: {scene_count}

SCENE-BY-SCENE BREAKDOWN:
{scenes_text}

Generate a natural, flowing summary that:
1. Captures the overall narrative or purpose of the video
2. Highlights key moments and transitions between scenes
3. Identifies main themes, subjects, or topics discussed
4. Describes the emotional tone and arc

VIDEO SUMMARY:"""
        
        # Call LLM
        llm_config = cfg.get('llm', {})
        api_url = llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
        timeout = llm_config.get('timeout', 30)
        
        response = requests.post(
            api_url,
            json={
                "messages": [
                    {
                        "role": "system", 
                        "content": "You are a video content analyst. Create coherent, informative video summaries that capture the essence and flow of the content."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "temperature": llm_config.get('temperature', 0.5),
                "max_tokens": 500,
            },
            timeout=timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            summary = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            if summary:
                logger.info(f"Generated video summary ({len(summary)} chars)")
                return summary
        else:
            logger.error(f"LLM API returned status {response.status_code}")
            return None
            
    except requests.Timeout:
        logger.error("LLM request timed out during video summarization")
        return None
    except Exception as e:
        logger.error(f"Video summarization failed: {e}")
        return None
    
    return None


def generate_video_summary_template(cfg: Dict, video_hash: str, db_path: str) -> str:
    """
    Generate template-based video summary (fallback)
    
    Args:
        cfg: Configuration dictionary
        video_hash: Video hash to summarize
        db_path: Path to memory database
        
    Returns:
        Template-based video summary
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Get video metadata from scenes
    c.execute("SELECT meta FROM scenes WHERE video_hash=? LIMIT 1", (video_hash,))
    scene_row = c.fetchone()
    if scene_row:
        scene_meta = json.loads(scene_row[0])
        filename = scene_meta.get('video_path', 'Unknown')
    else:
        filename = 'Unknown'
    
    # Count scenes
    c.execute("SELECT COUNT(*) FROM scenes WHERE video_hash=?", (video_hash,))
    scene_count = c.fetchone()[0]
    
    # Get duration
    c.execute("SELECT MAX(end) FROM scenes WHERE video_hash=?", (video_hash,))
    duration = c.fetchone()[0] or 0
    
    conn.close()
    
    return f"Video '{filename}' contains {scene_count} scenes spanning {duration:.1f} seconds. The content has been processed and indexed for semantic search."


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
    
    # Collect source artifact versions for provenance tracking
    source_artifact_versions = []
    try:
        conn_prov = sqlite3.connect(db_path)
        c_prov = conn_prov.cursor()
        c_prov.execute("""
            SELECT id, content, created_at FROM summaries 
            WHERE category='scene_summary' 
            ORDER BY id
        """)
        for rid, content_json, created_at in c_prov.fetchall():
            try:
                content = json.loads(content_json)
                scene_id = content.get('scene_id', 'unknown')
                source_artifact_versions.append({
                    "summary_id": rid,
                    "scene_id": scene_id,
                    "created_at": created_at
                })
            except Exception:
                continue
        conn_prov.close()
    except Exception as pe:
        logger.warning(f"Failed to query scene summaries for provenance: {pe}")

    # Generate video summary
    video_summary = None
    if use_llm:
        video_summary = generate_video_summary_llm(cfg, video_hash, db_path)
    
    # Fall back to template if LLM failed
    if not video_summary:
        if use_llm:
            logger.warning("LLM video summarization failed, using template fallback")
        video_summary = generate_video_summary_template(cfg, video_hash, db_path)
    
    # Store in database with full provenance
    from datetime import datetime, timezone
    llm_config = cfg.get('llm', {})
    api_url = llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
    model_name = llm_config.get('model', 'default_model')
    
    provenance = {
        "model_backend": f"{model_name} ({api_url})",
        "prompt_version": "v1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_artifact_versions": source_artifact_versions
    }
    
    if not cfg.get("ingestion_isolation", False):
        try:
            conn = sqlite3.connect(db_path)
            
            payload = json.dumps({
                'video_hash': video_hash,
                'summary': video_summary,
                'method': 'llm' if use_llm and video_summary else 'template',
                'provenance': provenance
            }, ensure_ascii=False)
            
            conn.execute("""
                INSERT OR REPLACE INTO summaries (summary_type, category, content, created_at)
                VALUES ('video', 'video_summary', ?, datetime('now'))
            """, (payload,))
            conn.commit()
            conn.close()
            
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
        'method': 'llm' if use_llm and video_summary else 'template',
        'provenance': provenance
    }
