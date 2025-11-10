"""
LLM-Enhanced Context Analyzer
Provides deeper semantic understanding of scenes and relationships
"""
from typing import Dict, Any, List, Optional
import logging
import requests
import json

logger = logging.getLogger(__name__)


def analyze_scene_context_llm(scene_meta: Dict[str, Any], cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Use LLM to analyze scene context and extract deeper semantic meaning
    
    Args:
        scene_meta: Scene metadata with visual, audio, and temporal info
        cfg: Configuration with LLM settings
        
    Returns:
        {
            'narrative_summary': str,
            'key_moments': List[str],
            'emotional_arc': str,
            'context_tags': List[str],
            'relationships': List[Dict],  # Detected relationships between entities
            'activity_description': str
        }
    """
    try:
        llm_config = cfg.get('config', {}).get('llm', {})
        api_url = llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
        timeout = llm_config.get('timeout', 20)
        
        # Extract key information
        index = scene_meta.get('index', 0)
        start = scene_meta.get('start', 0.0)
        end = scene_meta.get('end', 0.0)
        caption = scene_meta.get('caption', '')
        transcript = scene_meta.get('transcript', '')
        objects = scene_meta.get('objects', [])
        face_count = scene_meta.get('face_count', 0)
        emotions = scene_meta.get('emotions', [])
        speakers = scene_meta.get('speakers', [])
        
        # Format data
        objects_str = ', '.join([str(obj.get('label', obj)) if isinstance(obj, dict) else str(obj) for obj in objects[:10]]) if objects else 'none'
        emotions_str = ', '.join([f"{e.get('label', 'unknown')} ({e.get('score', 0):.0%})" if isinstance(e, dict) else str(e) for e in emotions[:3]]) if emotions else 'neutral'
        speakers_str = ', '.join([str(s) for s in speakers]) if speakers else 'unknown'
        
        prompt = f"""Analyze this video scene and extract semantic context:

SCENE METADATA:
- Scene {index}: {start:.1f}s - {end:.1f}s
- Visual: {caption or 'No description'}
- Objects: {objects_str}
- Faces: {face_count}
- Transcript: {transcript[:200] if transcript else 'No audio'}
- Speakers: {speakers_str}
- Emotions: {emotions_str}

Analyze and return ONLY a JSON object with:
- narrative_summary: Brief narrative description (1-2 sentences)
- key_moments: List of 1-3 key moments or actions
- emotional_arc: Overall emotional progression (e.g., "joyful throughout", "nervous to excited")
- context_tags: 3-5 semantic tags (e.g., "social gathering", "outdoor activity")
- relationships: List of detected relationships (e.g., {{"entities": ["person1", "person2"], "type": "interacting"}})
- activity_description: What's happening (1 sentence)

Example:
{{
  "narrative_summary": "A family gathering where children play while adults converse in the background",
  "key_moments": ["children playing with toys", "adults laughing together"],
  "emotional_arc": "joyful and relaxed throughout",
  "context_tags": ["family time", "indoor gathering", "childhood play"],
  "relationships": [{{"entities": ["speaker_00", "speaker_01"], "type": "conversation"}}],
  "activity_description": "Informal family interaction with playful atmosphere"
}}

JSON:"""
        
        response = requests.post(
            api_url,
            json={
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a video scene analyst. Extract semantic context and relationships as structured JSON. Be concise and accurate."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 300,
            },
            timeout=timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            
            # Clean and parse JSON
            content = content.replace('```json', '').replace('```', '').strip()
            
            try:
                parsed = json.loads(content)
                logger.info(f"Scene {index} context analyzed via LLM")
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM context JSON: {content[:100]}")
                return None
        else:
            logger.warning(f"LLM API returned status {response.status_code}")
            return None
            
    except requests.Timeout:
        logger.warning("LLM context analysis timed out")
        return None
    except Exception as e:
        logger.warning(f"LLM context analysis failed: {e}")
        return None


def analyze_emotional_progression(scenes: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Analyze emotional progression across multiple scenes
    
    Args:
        scenes: List of scene metadata dictionaries
        cfg: Configuration with LLM settings
        
    Returns:
        {
            'overall_arc': str,
            'key_transitions': List[Dict],
            'dominant_emotions': List[str],
            'emotional_journey': str
        }
    """
    try:
        llm_config = cfg.get('config', {}).get('llm', {})
        api_url = llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
        timeout = llm_config.get('timeout', 25)
        
        # Build scene emotion summary
        scene_emotions = []
        for i, scene in enumerate(scenes[:20]):  # Limit to first 20 scenes
            emotions = scene.get('emotions', [])
            if emotions:
                emotion_label = emotions[0].get('label', 'neutral') if isinstance(emotions[0], dict) else str(emotions[0])
            else:
                emotion_label = 'neutral'
            scene_emotions.append(f"Scene {i}: {emotion_label}")
        
        scenes_text = "\n".join(scene_emotions)
        
        prompt = f"""Analyze the emotional progression across this video:

SCENE EMOTIONS:
{scenes_text}

Analyze and return ONLY a JSON object with:
- overall_arc: Overall emotional trajectory (e.g., "gradual build from calm to excitement")
- key_transitions: List of significant emotional shifts with scene numbers
- dominant_emotions: Top 3-5 emotions throughout
- emotional_journey: 2-3 sentence description of the emotional narrative

Example:
{{
  "overall_arc": "Starts calm, builds to joyful climax",
  "key_transitions": [
    {{"from_scene": 0, "to_scene": 5, "shift": "calm to excited"}},
    {{"from_scene": 10, "to_scene": 15, "shift": "excited to contemplative"}}
  ],
  "dominant_emotions": ["joy", "excitement", "calm"],
  "emotional_journey": "The video begins in a relaxed atmosphere, gradually building excitement as activities intensify, before settling into a warm, reflective conclusion"
}}

JSON:"""
        
        response = requests.post(
            api_url,
            json={
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an emotional arc analyst. Extract structured emotional progression data as JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.4,
                "max_tokens": 350,
            },
            timeout=timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            
            content = content.replace('```json', '').replace('```', '').strip()
            
            try:
                parsed = json.loads(content)
                logger.info("Emotional progression analyzed via LLM")
                return parsed
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse emotional arc JSON: {content[:100]}")
                return None
        else:
            return None
            
    except Exception as e:
        logger.warning(f"Emotional progression analysis failed: {e}")
        return None


def build_relationship_map(scenes: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Build relationship map from scene context
    
    Args:
        scenes: List of scene metadata with context analysis
        cfg: Configuration
        
    Returns:
        {
            'entities': List[str],
            'relationships': List[Dict],
            'interaction_patterns': Dict
        }
    """
    try:
        # Collect all entities and relationships from scenes
        all_entities = set()
        all_relationships = []
        
        for scene in scenes:
            context = scene.get('context', {})
            if not context:
                continue
                
            # Extract relationships
            relationships = context.get('relationships', [])
            for rel in relationships:
                all_relationships.append({
                    'scene': scene.get('index', 0),
                    'entities': rel.get('entities', []),
                    'type': rel.get('type', 'unknown'),
                    'timestamp': scene.get('start', 0.0)
                })
                
                # Add entities
                for entity in rel.get('entities', []):
                    all_entities.add(entity)
        
        # Build interaction patterns
        interaction_patterns = {}
        for rel in all_relationships:
            rel_type = rel['type']
            interaction_patterns[rel_type] = interaction_patterns.get(rel_type, 0) + 1
        
        return {
            'entities': sorted(list(all_entities)),
            'relationships': all_relationships,
            'interaction_patterns': interaction_patterns,
            'total_entities': len(all_entities),
            'total_interactions': len(all_relationships)
        }
        
    except Exception as e:
        logger.error(f"Relationship mapping failed: {e}")
        return None
