"""
Build Knowledge Graph from Database - Standalone Version
Extracts data from memory.db and populates knowledge_graph.db
"""
import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from steps.common.config_loader import get_runtime_paths, load_configs
from lib.knowledge_graph import KnowledgeGraph


def load_config():
    """Load configuration"""
    return load_configs({})


def fetch_scenes_from_db(db_path: str) -> List[Dict[str, Any]]:
    """Fetch all scenes from database"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, video_hash, start, end, meta, created_at
        FROM scenes
        ORDER BY start ASC
    """)
    
    scenes = []
    for row in cursor.fetchall():
        scene_data = {
            'id': row['id'],
            'video_hash': row['video_hash'],
            'start_time': row['start'] if row['start'] else 0.0,
            'end_time': row['end'] if row['end'] else 0.0,
            'created_at': row['created_at']
        }
        
        # Parse meta JSON
        if row['meta']:
            try:
                meta = json.loads(row['meta'])
                scene_data.update(meta)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse meta for scene {row['id']}")
        
        scenes.append(scene_data)
    
    conn.close()
    logger.info(f"Loaded {len(scenes)} scenes from database")
    return scenes


def process_scene_entities(kg: KnowledgeGraph, scene: Dict[str, Any], media_id: int, timestamp: float, config: Dict[str, Any]):
    """Extract and add entities from scene data"""
    
    # Process objects/detections
    detections = scene.get('detections', []) or scene.get('objects', [])
    for det in detections:
        label = det.get('label', 'unknown')
        confidence = det.get('confidence', 0.0)
        bbox = det.get('bbox', [])
        
        node_id = kg.add_node(
            node_type='object',
            name=label,
            properties={'category': det.get('category', 'general')},
            timestamp=timestamp
        )
        
        kg.link_node_to_media(
            node_id=node_id,
            media_id=media_id,
            confidence=confidence,
            context={'bbox': bbox, 'timestamp': timestamp}
        )
    
    # Process faces
    faces = scene.get('faces', [])
    for face_idx, face in enumerate(faces):
        person_name = f"person_{face_idx}"
        
        node_id = kg.add_node(
            node_type='person',
            name=person_name,
            properties={'face_embedding_available': True},
            timestamp=timestamp
        )
        
        kg.link_node_to_media(
            node_id=node_id,
            media_id=media_id,
            confidence=face.get('confidence', 1.0),
            context={'bbox': face.get('bbox', []), 'timestamp': timestamp}
        )
    
    # Process caption/text
    caption = scene.get('caption', '')
    if caption:
        node_id = kg.add_node(
            node_type='caption',
            name='scene_caption',
            properties={'content': caption},
            timestamp=timestamp
        )
        kg.link_node_to_media(node_id, media_id, confidence=0.9)
    
    # Process tags
    tags = scene.get('tags', [])
    for tag in tags:
        node_id = kg.add_node(
            node_type='tag',
            name=tag,
            timestamp=timestamp
        )
        kg.link_node_to_media(node_id, media_id, confidence=0.9)
    
    # Process audio/transcript
    audio = scene.get('audio', {})
    transcript = audio.get('transcript', '')
    if transcript:
        speakers = audio.get('speakers', [])
        for speaker in speakers:
            speaker_id = speaker.get('speaker_id', 'unknown')
            node_id = kg.add_node(
                node_type='speaker',
                name=speaker_id,
                timestamp=timestamp
            )
            kg.link_node_to_media(node_id, media_id, confidence=0.9)
    
    # Process emotions
    sentiment = scene.get('sentiment', {})
    if sentiment:
        score = sentiment.get('score', 0.0)
        label = sentiment.get('label', 'neutral')
        
        node_id = kg.add_node(
            node_type='emotion',
            name=f"sentiment_{label}",
            properties={'score': score},
            timestamp=timestamp
        )
        kg.link_node_to_media(node_id, media_id, confidence=abs(score))
    
    emotions = scene.get('emotions', [])
    for emotion in emotions:
        node_id = kg.add_node(
            node_type='emotion',
            name=emotion.get('label', 'unknown'),
            properties={'score': emotion.get('score', 0.0)},
            timestamp=timestamp
        )
        kg.link_node_to_media(node_id, media_id, confidence=emotion.get('score', 0.5))


def build_cooccurrence_edges(kg: KnowledgeGraph):
    """Build edges between entities that co-occur in media"""
    logger.info("Building co-occurrence edges")
    
    cursor = kg.conn.cursor()
    media_nodes = cursor.execute("SELECT id FROM media_nodes").fetchall()
    
    for (media_id,) in media_nodes:
        nodes = cursor.execute("""
            SELECT node_id FROM node_media WHERE media_id = ?
        """, (media_id,)).fetchall()
        
        node_ids = [n[0] for n in nodes]
        
        for i, node1 in enumerate(node_ids):
            for node2 in node_ids[i+1:]:
                kg.add_edge(
                    source_id=node1,
                    target_id=node2,
                    edge_type='co_occurs',
                    weight=1.0
                )


def build_temporal_edges(kg: KnowledgeGraph):
    """Build edges between temporally adjacent entities"""
    logger.info("Building temporal edges")
    
    cursor = kg.conn.cursor()
    
    media_nodes = cursor.execute("""
        SELECT id, timestamp_start, timestamp_end
        FROM media_nodes
        WHERE scene_id IS NOT NULL
        ORDER BY timestamp_start ASC
    """).fetchall()
    
    for i in range(len(media_nodes) - 1):
        media1_id, start1, end1 = media_nodes[i]
        media2_id, start2, end2 = media_nodes[i + 1]
        
        nodes1 = [n[0] for n in cursor.execute(
            "SELECT node_id FROM node_media WHERE media_id = ?", (media1_id,)
        ).fetchall()]
        
        nodes2 = [n[0] for n in cursor.execute(
            "SELECT node_id FROM node_media WHERE media_id = ?", (media2_id,)
        ).fetchall()]
        
        for node1 in nodes1:
            for node2 in nodes2:
                kg.add_edge(
                    source_id=node1,
                    target_id=node2,
                    edge_type='temporal_next',
                    weight=0.5
                )


def analyze_emotional_arc_simple(scenes: List[Dict[str, Any]], config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Simple emotional arc analysis with LLM"""
    llm_config = config.get('llm', {})
    if not llm_config.get('enabled', False):
        return None
    
    if not scenes or len(scenes) < 3:
        return None
    
    try:
        # Extract emotional data
        scene_emotions = []
        for idx, scene in enumerate(scenes):
            timestamp = scene.get('start_time', idx * 10)
            sentiment = scene.get('sentiment', {})
            sent_label = sentiment.get('label', 'NEUTRAL')
            sent_score = sentiment.get('score', 0.5)
            
            emotions = scene.get('emotions', [])
            top_emotions = [e.get('label', '') for e in emotions[:2]]
            
            audio = scene.get('audio', {})
            transcript = audio.get('transcript', '')[:100]
            
            scene_emotions.append({
                'scene': idx + 1,
                'time': f"{timestamp:.1f}s",
                'sentiment': f"{sent_label} ({sent_score:.2f})",
                'emotions': ', '.join(top_emotions) if top_emotions else 'neutral',
                'context': transcript if transcript else ''
            })
        
        # Sample for prompt
        if len(scene_emotions) > 15:
            sampled = (
                scene_emotions[:3] +
                scene_emotions[len(scene_emotions)//3:len(scene_emotions)//3+3] +
                scene_emotions[2*len(scene_emotions)//3:2*len(scene_emotions)//3+3] +
                scene_emotions[-3:]
            )
        else:
            sampled = scene_emotions
        
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

Provide a brief analysis in this JSON format:
{{
  "overall_arc": "description of emotional progression",
  "key_moments": [
    {{
      "scene": 1,
      "description": "what happens emotionally"
    }}
  ],
  "emotional_themes": ["theme1", "theme2"]
}}

Return valid JSON only."""

        api_url = llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
        
        response = requests.post(
            api_url,
            json={
                "messages": [
                    {"role": "system", "content": "You are an emotional narrative analyst. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.4,
                "max_tokens": 500,
            },
            timeout=45
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            
            # Try to parse JSON
            try:
                return json.loads(content)
            except:
                # Try to extract JSON from markdown
                if '```json' in content:
                    start = content.find('```json') + 7
                    end = content.find('```', start)
                    if end > start:
                        try:
                            return json.loads(content[start:end].strip())
                        except:
                            pass
                
                # Try to find JSON boundaries
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    try:
                        return json.loads(content[start:end])
                    except:
                        pass
        
    except Exception as e:
        logger.error(f"Emotional arc analysis error: {e}")
    
    return None


def build_kg_from_scenes(scenes: List[Dict[str, Any]], config: Dict[str, Any]):
    """Build knowledge graph from scene data"""
    
    runtime_paths = get_runtime_paths(config, 'log_dir')
    kg_path = Path(runtime_paths['knowledge_graph_db']).resolve()
    kg_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Building knowledge graph at: {kg_path}")
    
    kg = KnowledgeGraph(str(kg_path))
    
    video_hash = scenes[0]['video_hash'] if scenes else 'unknown'
    
    # Create video media node
    video_media_id = kg.add_media_node(
        media_type='video',
        media_path=f"video_{video_hash}",
        scene_id=None,
        timestamp_start=0.0,
        timestamp_end=scenes[-1]['end_time'] if scenes else 0.0,
        properties={'video_hash': video_hash}
    )
    
    logger.info(f"Created video media node: {video_media_id}")
    
    # Process each scene
    for idx, scene in enumerate(scenes):
        scene_id = f"scene_{idx:04d}"
        start_time = scene.get('start_time', 0.0)
        end_time = scene.get('end_time', 0.0)
        
        media_id = kg.add_media_node(
            media_type='video_scene',
            media_path=f"video_{video_hash}",
            scene_id=scene_id,
            timestamp_start=start_time,
            timestamp_end=end_time,
            properties={
                'duration': end_time - start_time,
                'scene_index': idx
            }
        )
        
        logger.debug(f"Processing scene {idx}: {start_time:.2f}s - {end_time:.2f}s")
        
        # Extract entities
        process_scene_entities(kg, scene, media_id, start_time, config)
        
        # Create temporal event
        event_id = kg.add_temporal_event(
            event_type='scene_change',
            timestamp=start_time,
            duration=end_time - start_time,
            properties={
                'scene_id': scene_id,
                'scene_index': idx
            }
        )
        
        if (idx + 1) % 5 == 0:
            logger.info(f"Processed {idx + 1}/{len(scenes)} scenes")
    
    logger.info(f"Processed all {len(scenes)} scenes")
    
    # Build relationships
    logger.info("Building co-occurrence edges...")
    build_cooccurrence_edges(kg)
    
    logger.info("Building temporal edges...")
    build_temporal_edges(kg)
    
    # Analyze emotional arc
    if config.get('llm', {}).get('enabled', False):
        logger.info("Analyzing emotional arc with LLM...")
        try:
            arc_analysis = analyze_emotional_arc_simple(scenes, config)
            if arc_analysis:
                # Add emotional arc nodes
                overall_arc = arc_analysis.get('overall_arc', '')
                if overall_arc:
                    arc_node_id = kg.add_node(
                        node_type='emotional_arc',
                        name='video_emotional_journey',
                        properties={'description': overall_arc, 'llm_generated': True},
                        timestamp=0.0
                    )
                    kg.link_node_to_media(arc_node_id, video_media_id, confidence=0.9)
                
                for theme in arc_analysis.get('emotional_themes', []):
                    theme_node_id = kg.add_node(
                        node_type='theme',
                        name=theme,
                        properties={'category': 'emotional', 'llm_extracted': True},
                        timestamp=0.0
                    )
                    kg.link_node_to_media(theme_node_id, video_media_id, confidence=0.85)
                
                logger.info("Emotional arc analysis added to knowledge graph")
        except Exception as e:
            logger.error(f"Failed to analyze emotional arc: {e}")
    
    # Get statistics
    stats = kg.get_statistics()
    
    logger.info("=" * 60)
    logger.info("KNOWLEDGE GRAPH STATISTICS")
    logger.info("=" * 60)
    logger.info(f"Total Nodes: {stats.get('total_nodes', 0)}")
    logger.info(f"Total Edges: {stats.get('total_edges', 0)}")
    logger.info(f"Media Nodes: {stats.get('total_media', 0)}")
    logger.info(f"Temporal Events: {stats.get('total_events', 0)}")
    
    node_types = stats.get('nodes_by_type', {})
    if node_types:
        logger.info("\nNode Types:")
        for node_type, count in sorted(node_types.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {node_type}: {count}")
    
    edge_types = stats.get('edges_by_type', {})
    if edge_types:
        logger.info("\nEdge Types:")
        for edge_type, count in sorted(edge_types.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {edge_type}: {count}")
    
    logger.info("=" * 60)
    
    kg.close()
    
    return stats


def main():
    """Main entry point"""
    logger.info("Starting knowledge graph build from database")
    
    config = load_config()
    runtime_paths = get_runtime_paths(config, 'log_dir')
    db_path = runtime_paths['db_path']
    
    scenes = fetch_scenes_from_db(db_path)
    
    if not scenes:
        logger.error("No scenes found in database!")
        return
    
    stats = build_kg_from_scenes(scenes, config)
    
    logger.info("Knowledge graph build complete!")
    
    stats_path = Path(runtime_paths['log_dir']).resolve() / "kg_build_stats.json"
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    logger.info(f"Statistics saved to: {stats_path}")


if __name__ == "__main__":
    main()
