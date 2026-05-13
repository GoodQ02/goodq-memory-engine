"""
LLM-Powered Knowledge Graph Enrichment
Adds semantic understanding to extracted entities and relationships
"""
import json
import logging
import requests
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


def extract_entities_with_llm(
    text: str,
    context: Dict[str, Any],
    cfg: Dict[str, Any]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Use LLM to extract structured entities from text with context
    
    Args:
        text: Text to analyze (transcript, caption, OCR)
        context: Scene context (objects, emotions, etc.)
        cfg: Configuration with LLM settings
        
    Returns:
        Dictionary with entity categories and extracted entities
    """
    if not text or len(text) < 10:
        return {}
    
    llm_config = cfg.get('llm', {})
    if not llm_config.get('enabled', False):
        return {}
    
    try:
        # Build contextual prompt
        context_desc = _build_context_description(context)
        
        prompt = f"""Analyze this content and extract key entities with their types and relationships.

VISUAL CONTEXT:
{context_desc}

TEXT CONTENT:
{text[:1000]}

Extract entities in this JSON format:
{{
  "people": [{{"name": "...", "role": "...", "confidence": 0.0-1.0}}],
  "locations": [{{"name": "...", "type": "...", "confidence": 0.0-1.0}}],
  "objects": [{{"name": "...", "significance": "...", "confidence": 0.0-1.0}}],
  "events": [{{"description": "...", "type": "...", "confidence": 0.0-1.0}}],
  "topics": [{{"name": "...", "relevance": "...", "confidence": 0.0-1.0}}],
  "temporal_references": [{{"reference": "...", "approximate_time": "...", "confidence": 0.0-1.0}}]
}}

Only include entities explicitly mentioned or clearly visible. Be precise and conservative."""

        api_url = llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
        timeout = llm_config.get('timeout', 30)
        
        response = requests.post(
            api_url,
            json={
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a precise entity extraction system. Extract only clear, confident entities from multimodal content. Return valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.2,  # Low temperature for consistency
                "max_tokens": 500,
            },
            timeout=timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            
            # Extract JSON from response
            entities = _parse_llm_json_response(content)
            if entities:
                logger.info(f"Extracted entities: {sum(len(v) for v in entities.values())} total")
                return entities
        else:
            logger.warning(f"LLM entity extraction failed: status {response.status_code}")
            
    except requests.Timeout:
        logger.warning("LLM entity extraction timed out")
    except Exception as e:
        logger.error(f"LLM entity extraction error: {e}")
    
    return {}


def infer_relationships_with_llm(
    entities: List[Dict[str, Any]],
    context: Dict[str, Any],
    cfg: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Use LLM to infer semantic relationships between entities
    
    Args:
        entities: List of entity dictionaries with names and types
        context: Scene context for relationship inference
        cfg: Configuration with LLM settings
        
    Returns:
        List of relationship dictionaries
    """
    if not entities or len(entities) < 2:
        return []
    
    llm_config = cfg.get('llm', {})
    if not llm_config.get('enabled', False):
        return {}
    
    # Check if relationship extraction is enabled
    if not llm_config.get('features', {}).get('relationship_extraction', False):
        return []
    
    try:
        # Format entities for prompt
        entity_list = "\n".join([
            f"- {e.get('name', 'unknown')} ({e.get('type', 'entity')})"
            for e in entities[:20]  # Limit to avoid token overflow
        ])
        
        context_desc = _build_context_description(context)
        
        prompt = f"""Given these entities extracted from a video scene, infer meaningful relationships:

ENTITIES:
{entity_list}

SCENE CONTEXT:
{context_desc}

Identify relationships in this JSON format:
{{
  "relationships": [
    {{
      "source": "entity_name",
      "target": "entity_name",
      "relationship_type": "type",
      "confidence": 0.0-1.0,
      "context": "brief explanation"
    }}
  ]
}}

Relationship types: family_member, colleague, friend, located_in, part_of, associated_with, discusses, interacts_with

Only include high-confidence relationships (>0.7). Return valid JSON."""

        api_url = llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
        timeout = llm_config.get('timeout', 30)
        
        response = requests.post(
            api_url,
            json={
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a relationship inference system. Identify only clear, confident relationships from context. Return valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 400,
            },
            timeout=timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            
            # Extract JSON from response
            data = _parse_llm_json_response(content)
            if data and 'relationships' in data:
                relationships = data['relationships']
                logger.info(f"Inferred {len(relationships)} relationships")
                return relationships
        else:
            logger.warning(f"LLM relationship inference failed: status {response.status_code}")
            
    except requests.Timeout:
        logger.warning("LLM relationship inference timed out")
    except Exception as e:
        logger.error(f"LLM relationship inference error: {e}")
    
    return []


def generate_scene_narrative(
    scene_data: Dict[str, Any],
    cfg: Dict[str, Any]
) -> Optional[str]:
    """
    Generate a narrative description of the scene using LLM
    
    Args:
        scene_data: Complete scene metadata
        cfg: Configuration with LLM settings
        
    Returns:
        Narrative description string or None
    """
    llm_config = cfg.get('llm', {})
    if not llm_config.get('enabled', False):
        return None
    
    try:
        # Build comprehensive scene description
        components = []
        
        # Visual elements
        if scene_data.get('objects'):
            obj_list = [o.get('label', 'object') for o in scene_data['objects'][:10]]
            components.append(f"Visual: {', '.join(obj_list)}")
        
        if scene_data.get('caption'):
            components.append(f"Scene: {scene_data['caption']}")
        
        # Audio elements
        audio = scene_data.get('audio', {})
        if audio.get('transcript'):
            components.append(f"Speech: {audio['transcript'][:200]}")
        
        if audio.get('speakers'):
            speaker_count = len(audio['speakers'])
            components.append(f"Speakers: {speaker_count} detected")
        
        # Emotional context
        sentiment = scene_data.get('sentiment', {})
        if sentiment:
            components.append(f"Tone: {sentiment.get('label', 'neutral')}")
        
        emotions = scene_data.get('emotions', [])
        if emotions:
            top_emotion = emotions[0].get('label', 'neutral')
            components.append(f"Emotion: {top_emotion}")
        
        if not components:
            return None
        
        scene_desc = "\n".join(components)
        start_time = scene_data.get('start_time', 0)
        duration = scene_data.get('end_time', 0) - start_time
        
        prompt = f"""Create a concise 2-3 sentence narrative description of this video scene:

TIME: {start_time:.1f}s (duration: {duration:.1f}s)

SCENE DATA:
{scene_desc}

Generate a natural, flowing description that captures what's happening, who's involved, and the emotional context."""

        api_url = llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
        timeout = llm_config.get('timeout', 30)
        
        response = requests.post(
            api_url,
            json={
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a video content narrator. Create vivid, accurate scene descriptions that capture the essence of what's happening."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.4,
                "max_tokens": 150,
            },
            timeout=timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            narrative = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            if narrative:
                logger.info(f"Generated scene narrative ({len(narrative)} chars)")
                return narrative
        else:
            logger.warning(f"LLM narrative generation failed: status {response.status_code}")
            
    except requests.Timeout:
        logger.warning("LLM narrative generation timed out")
    except Exception as e:
        logger.error(f"LLM narrative generation error: {e}")
    
    return None


def _build_context_description(context: Dict[str, Any]) -> str:
    """Build a textual description of scene context"""
    parts = []
    
    if context.get('objects'):
        obj_labels = [o.get('label', '') for o in context['objects'][:5]]
        parts.append(f"Visible objects: {', '.join(obj_labels)}")
    
    if context.get('emotions'):
        emotions = [e.get('label', '') for e in context['emotions'][:3]]
        parts.append(f"Detected emotions: {', '.join(emotions)}")
    
    if context.get('sentiment'):
        sent = context['sentiment']
        parts.append(f"Sentiment: {sent.get('label', 'neutral')} ({sent.get('score', 0):.2f})")
    
    if context.get('audio', {}).get('speakers'):
        speaker_count = len(context['audio']['speakers'])
        parts.append(f"Speakers: {speaker_count}")
    
    return "\n".join(parts) if parts else "No additional context"


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
    
    logger.warning("Failed to parse JSON from LLM response")
    return None
