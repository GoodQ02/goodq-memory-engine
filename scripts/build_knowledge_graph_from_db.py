"""
Build Knowledge Graph from Database
Extracts data from memory.db and populates knowledge_graph.db
"""
import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from steps.common.config_loader import get_runtime_paths, load_configs
from lib.knowledge_graph import KnowledgeGraph

# Import graph builder functions
from steps.graph_builder.graph_builder import (
    _process_objects, _process_faces, _process_text,
    _process_audio, _process_emotions, _process_locations,
    _build_cooccurrence_edges, _build_temporal_edges, _build_semantic_edges
)
from steps.graph_builder.emotion_arc_analyzer import analyze_emotional_arc, add_emotional_arc_to_kg


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


def build_kg_from_scenes(scenes: List[Dict[str, Any]], config: Dict[str, Any]):
    """Build knowledge graph from scene data"""
    
    # Get knowledge graph path
    runtime_paths = get_runtime_paths(config, 'log_dir')
    kg_path = Path(runtime_paths['knowledge_graph_db']).resolve()
    kg_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Building knowledge graph at: {kg_path}")
    
    # Initialize knowledge graph
    kg = KnowledgeGraph(str(kg_path))
    
    # Assume first scene's video_hash represents the video
    video_hash = scenes[0]['video_hash'] if scenes else 'unknown'
    
    # Create a media node for the overall video
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
        
        # Add media node for this scene
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
        
        # Extract and add entities from various sources
        _process_objects(kg, scene, media_id, start_time)
        _process_faces(kg, scene, media_id, start_time)
        _process_text(kg, scene, media_id, start_time, config)
        _process_audio(kg, scene, media_id, start_time)
        _process_emotions(kg, scene, media_id, start_time)
        _process_locations(kg, scene, media_id, start_time)
        
        # Create temporal event for scene
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
    _build_cooccurrence_edges(kg)
    
    logger.info("Building temporal edges...")
    _build_temporal_edges(kg)
    
    logger.info("Building semantic edges...")
    _build_semantic_edges(kg)
    
    # Analyze emotional arc if LLM is enabled
    if config.get('llm', {}).get('enabled', False):
        logger.info("Analyzing emotional arc with LLM...")
        try:
            arc_analysis = analyze_emotional_arc(scenes, config)
            if arc_analysis:
                add_emotional_arc_to_kg(kg, arc_analysis, video_media_id, config)
                logger.info("Emotional arc analysis added to knowledge graph")
        except Exception as e:
            logger.error(f"Failed to analyze emotional arc: {e}")
    
    # Get statistics
    stats = kg.get_statistics()
    
    logger.info("=" * 60)
    logger.info("KNOWLEDGE GRAPH STATISTICS")
    logger.info("=" * 60)
    logger.info(f"Total Nodes: {stats.get('node_count', 0)}")
    logger.info(f"Total Edges: {stats.get('edge_count', 0)}")
    logger.info(f"Media Nodes: {stats.get('media_node_count', 0)}")
    logger.info(f"Temporal Events: {stats.get('temporal_event_count', 0)}")
    
    node_types = stats.get('node_types', {})
    if node_types:
        logger.info("\nNode Types:")
        for node_type, count in sorted(node_types.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {node_type}: {count}")
    
    edge_types = stats.get('edge_types', {})
    if edge_types:
        logger.info("\nEdge Types:")
        for edge_type, count in sorted(edge_types.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {edge_type}: {count}")
    
    logger.info("=" * 60)
    
    # Close knowledge graph
    kg.close()
    
    return stats


def main():
    """Main entry point"""
    logger.info("Starting knowledge graph build from database")
    
    # Load configuration
    config = load_config()
    runtime_paths = get_runtime_paths(config, 'log_dir')
    
    # Get database path
    db_path = runtime_paths['db_path']
    
    # Fetch scenes
    scenes = fetch_scenes_from_db(db_path)
    
    if not scenes:
        logger.error("No scenes found in database!")
        return
    
    # Build knowledge graph
    stats = build_kg_from_scenes(scenes, config)
    
    logger.info("Knowledge graph build complete!")
    
    # Save stats to file
    stats_path = Path(runtime_paths['log_dir']).resolve() / "kg_build_stats.json"
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    logger.info(f"Statistics saved to: {stats_path}")


if __name__ == "__main__":
    main()
