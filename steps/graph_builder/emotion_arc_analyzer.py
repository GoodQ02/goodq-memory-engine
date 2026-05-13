"""
Emotional Arc Analysis with LLM
Analyzes emotional journey across video scenes
"""
import json
import logging
import requests
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def analyze_emotional_arc(
    scenes: List[Dict[str, Any]],
    cfg: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Analyze the emotional arc across all scenes using LLM
    
    Args:
        scenes: List of scene dictionaries with emotion data
        cfg: Configuration with LLM settings
        
    Returns:
        Emotional arc analysis with key moments and overall trajectory
    """
    llm_config = cfg.get('llm', {})
    if not llm_config.get('enabled', False):
        return None
    
    if not llm_config.get('features', {}).get('emotion_arc_analysis', False):
        logger.info("Emotion arc analysis not enabled in config")
        return None
    
    if not scenes or len(scenes) < 3:
        logger.warning("Not enough scenes for emotional arc analysis")
        return None
    
    try:
        # Extract emotional data from scenes
        scene_emotions = []
        for idx, scene in enumerate(scenes):
            timestamp = scene.get('start_time', idx * 10)
            
            # Get sentiment
            sentiment = scene.get('sentiment', {})
            sent_label = sentiment.get('label', 'NEUTRAL')
            sent_score = sentiment.get('score', 0.5)
            
            # Get emotions
            emotions = scene.get('emotions', [])
            top_emotions = [e.get('label', '') for e in emotions[:2]]
            
            # Get transcript snippet
            audio = scene.get('audio', {})
            transcript = audio.get('transcript', '')[:100]
            
            scene_emotions.append({
                'scene': idx + 1,
                'time': f"{timestamp:.1f}s",
                'sentiment': f"{sent_label} ({sent_score:.2f})",
                'emotions': ', '.join(top_emotions) if top_emotions else 'neutral',
                'context': transcript if transcript else ''
            })
        
        # Sample scenes for analysis (to avoid token limits)
        if len(scene_emotions) > 15:
            # Take first, last, and sample from middle
            sampled = (
                scene_emotions[:3] +
                scene_emotions[len(scene_emotions)//3:len(scene_emotions)//3+3] +
                scene_emotions[2*len(scene_emotions)//3:2*len(scene_emotions)//3+3] +
                scene_emotions[-3:]
            )
        else:
            sampled = scene_emotions
        
        # Format for prompt
        emotion_timeline = "\n".join([
            f"Scene {e['scene']} ({e['time']}): {e['sentiment']} | Emotions: {e['emotions']}" +
            (f" | \"{e['context']}\"" if e['context'] else "")
            for e in sampled
        ])
        
        total_duration = scenes[-1].get('end_time', 0)
        
        prompt = f"""Analyze the emotional journey in this video:

TOTAL SCENES: {len(scenes)}
DURATION: {total_duration:.1f} seconds

EMOTIONAL TIMELINE:
{emotion_timeline}

Provide analysis in this JSON format:
{{
  "overall_arc": "description of emotional progression",
  "key_moments": [
    {{
      "scene": 1,
      "time": "0.0s",
      "description": "what happens emotionally",
      "significance": "why it matters"
    }}
  ],
  "emotional_themes": ["theme1", "theme2"],
  "turning_points": [
    {{
      "scene": 1,
      "from_emotion": "emotion",
      "to_emotion": "emotion",
      "trigger": "what caused the shift"
    }}
  ],
  "conclusion": "overall emotional takeaway"
}}

Focus on significant emotional shifts and the narrative arc. Be specific and reference actual content."""

        api_url = llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
        timeout = llm_config.get('timeout', 45)  # Longer timeout for analysis
        
        response = requests.post(
            api_url,
            json={
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert in emotional narrative analysis. Identify emotional arcs, key moments, and psychological themes in video content. Return valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.4,
                "max_tokens": 600,
            },
            timeout=timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            
            # Parse JSON response
            arc_data = _parse_llm_json_response(content)
            if arc_data:
                logger.info(f"Generated emotional arc analysis with {len(arc_data.get('key_moments', []))} key moments")
                return arc_data
        else:
            logger.warning(f"LLM emotional arc analysis failed: status {response.status_code}")
            
    except requests.Timeout:
        logger.warning("LLM emotional arc analysis timed out")
    except Exception as e:
        logger.error(f"Emotional arc analysis error: {e}")
    
    return None


def add_emotional_arc_to_kg(
    kg,
    arc_analysis: Dict[str, Any],
    video_media_id: int,
    cfg: Dict[str, Any]
):
    """
    Add emotional arc analysis to knowledge graph
    
    Args:
        kg: Knowledge graph instance
        arc_analysis: Emotional arc analysis from LLM
        video_media_id: Media ID for the overall video
        cfg: Configuration
    """
    try:
        # Add overall arc as a narrative node
        overall_arc = arc_analysis.get('overall_arc', '')
        if overall_arc:
            arc_node_id = kg.add_node(
                node_type='emotional_arc',
                name='video_emotional_journey',
                properties={
                    'description': overall_arc,
                    'llm_generated': True
                },
                timestamp=0.0
            )
            kg.link_node_to_media(arc_node_id, video_media_id, confidence=0.9)
        
        # Add emotional themes
        themes = arc_analysis.get('emotional_themes', [])
        for theme in themes:
            theme_node_id = kg.add_node(
                node_type='theme',
                name=theme,
                properties={'category': 'emotional', 'llm_extracted': True},
                timestamp=0.0
            )
            kg.link_node_to_media(theme_node_id, video_media_id, confidence=0.85)
        
        # Add key moments
        key_moments = arc_analysis.get('key_moments', [])
        for moment in key_moments:
            scene_num = moment.get('scene', 0)
            description = moment.get('description', '')
            
            moment_node_id = kg.add_node(
                node_type='emotional_moment',
                name=f"key_moment_scene_{scene_num}",
                properties={
                    'description': description,
                    'significance': moment.get('significance', ''),
                    'llm_identified': True
                },
                timestamp=float(moment.get('time', '0').replace('s', ''))
            )
            kg.link_node_to_media(moment_node_id, video_media_id, confidence=0.9)
        
        # Add turning points
        turning_points = arc_analysis.get('turning_points', [])
        for tp in turning_points:
            scene_num = tp.get('scene', 0)
            tp_node_id = kg.add_node(
                node_type='emotional_turning_point',
                name=f"turning_point_scene_{scene_num}",
                properties={
                    'from_emotion': tp.get('from_emotion', ''),
                    'to_emotion': tp.get('to_emotion', ''),
                    'trigger': tp.get('trigger', ''),
                    'llm_identified': True
                },
                timestamp=0.0
            )
            kg.link_node_to_media(tp_node_id, video_media_id, confidence=0.85)
        
        logger.info(f"Added emotional arc with {len(key_moments)} key moments and {len(turning_points)} turning points to KG")
        
    except Exception as e:
        logger.error(f"Failed to add emotional arc to knowledge graph: {e}")


def _parse_llm_json_response(content: str) -> Optional[Dict]:
    """Extract and parse JSON from LLM response"""
    try:
        # Try direct parsing first
        return json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        if '```json' in content:
            start = content.find('```json') + 7
            end = content.find('```', start)
            if end > start:
                try:
                    return json.loads(content[start:end].strip())
                except:
                    pass
        
        # Try to find JSON object boundaries
        start = content.find('{')
        end = content.rfind('}') + 1
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end])
            except:
                pass
    
    logger.warning("Failed to parse JSON from emotional arc LLM response")
    return None
