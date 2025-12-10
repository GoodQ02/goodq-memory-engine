"""
Build Unified Knowledge Graph - Phase 8
Main orchestration script for constructing the cross-video unified knowledge graph
"""
import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, Any, List
import yaml
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import Phase 8 components
import sys
sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from unified_knowledge_graph import UnifiedKnowledgeGraph
from cross_video_entity_resolver import CrossVideoEntityResolver
from timeline_builder import TimelineBuilder


def load_config():
    """Load configuration"""
    config_path = Path("L:/goodq4all/config.yaml")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Add default unified KG config if not present
    if 'unified_knowledge_graph' not in config:
        config['unified_knowledge_graph'] = {
            'enabled': True,
            'db_path': 'L:/_DATA/GoodQ_Data/unified_goodq.db',
            'entity_resolution': {
                'face_similarity_threshold': 0.85,
                'voice_similarity_threshold': 0.80,
                'name_matching_algorithm': 'fuzzy',
                'use_llm_for_disambiguation': True,
            },
            'timeline': {
                'date_extraction_from_filenames': True,
                'date_format_patterns': [r'(\d{4})_(\d{4})', r'(\d{4})'],
                'infer_missing_dates': True,
            }
        }
    
    return config


def discover_processed_videos(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Discover all processed videos by scanning memory.db and KG databases
    """
    logger.info("Discovering processed videos...")
    
    videos = []
    memory_db_path = Path(config['paths']['db_path'])
    kg_data_dir = Path(config['paths'].get('knowledge_graph_db', '')).parent
    output_dir = Path(config['paths'].get('output', 'L:/goodq4all/output'))
    
    if not memory_db_path.exists():
        logger.warning(f"Memory database not found at {memory_db_path}")
        return videos
    
    try:
        conn = sqlite3.connect(str(memory_db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all unique video hashes
        cursor.execute("""
            SELECT DISTINCT video_hash 
            FROM scenes 
            WHERE video_hash IS NOT NULL
        """)
        
        video_hashes = [row[0] for row in cursor.fetchall()]
        
        for video_hash in video_hashes:
            # Get video metadata from scenes
            cursor.execute("""
                SELECT 
                    video_hash,
                    MIN(start) as first_scene_start,
                    MAX(end) as last_scene_end,
                    COUNT(*) as scene_count
                FROM scenes
                WHERE video_hash = ?
                GROUP BY video_hash
            """, (video_hash,))
            
            row = cursor.fetchone()
            if row:
                duration = (row['last_scene_end'] or 0) - (row['first_scene_start'] or 0)
                
                # Find corresponding KG database
                kg_db_path = kg_data_dir / f"{video_hash}_kg.db"
                if not kg_db_path.exists():
                    # Try default location
                    kg_db_path = kg_data_dir / "knowledge_graph.db"
                
                # Find video file in output
                video_paths = list(output_dir.glob(f"**/{video_hash}*"))
                video_path = str(video_paths[0]) if video_paths else f"unknown_{video_hash}"
                
                # Extract date from filename
                timeline_builder = TimelineBuilder(config)
                year, month, day, inferred = timeline_builder.extract_date_from_filename(video_path)
                
                videos.append({
                    'video_hash': video_hash,
                    'video_path': video_path,
                    'year': year,
                    'month': month,
                    'day': day,
                    'date_inferred': inferred,
                    'duration': duration,
                    'scene_count': row['scene_count'],
                    'kg_db_path': str(kg_db_path) if kg_db_path.exists() else None,
                })
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Failed to discover videos: {e}")
    
    logger.info(f"Discovered {len(videos)} processed videos")
    return videos


def build_unified_knowledge_graph(config: Dict[str, Any], videos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Main function to build unified knowledge graph
    """
    logger.info("=" * 80)
    logger.info("PHASE 8: BUILDING UNIFIED KNOWLEDGE GRAPH")
    logger.info("=" * 80)
    
    # Initialize unified KG
    unified_kg_path = Path(config['unified_knowledge_graph']['db_path'])
    unified_kg_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Initializing unified KG at: {unified_kg_path}")
    unified_kg = UnifiedKnowledgeGraph(str(unified_kg_path))
    
    results = {
        'videos_registered': 0,
        'entities_resolved': {},
        'timeline_built': False,
        'relationships_created': 0,
        'stats': {},
        'errors': []
    }
    
    try:
        # Step 1: Register all videos
        logger.info("\n" + "=" * 80)
        logger.info("STEP 1: REGISTERING VIDEOS")
        logger.info("=" * 80)
        
        for video in videos:
            try:
                unified_kg.register_video(
                    video_hash=video['video_hash'],
                    video_path=video['video_path'],
                    metadata=video
                )
                results['videos_registered'] += 1
                logger.info(f"  ✓ Registered: {video['video_hash']} (year: {video.get('year', 'unknown')})")
            except Exception as e:
                logger.error(f"  ✗ Failed to register {video['video_hash']}: {e}")
                results['errors'].append(str(e))
        
        # Step 2: Resolve entities across videos
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: RESOLVING ENTITIES ACROSS VIDEOS")
        logger.info("=" * 80)
        
        resolver = CrossVideoEntityResolver(config)
        
        video_hashes = [v['video_hash'] for v in videos]
        kg_paths = {v['video_hash']: v['kg_db_path'] for v in videos if v.get('kg_db_path')}
        
        entity_results = resolver.resolve_entities_across_videos(
            video_hashes=video_hashes,
            individual_kg_paths=kg_paths,
            unified_kg=unified_kg
        )
        
        results['entities_resolved'] = entity_results['stats']
        logger.info(f"  ✓ Entity resolution complete: {entity_results['stats']}")
        
        # Step 3: Build temporal timeline
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: BUILDING TEMPORAL TIMELINE")
        logger.info("=" * 80)
        
        timeline_builder = TimelineBuilder(config)
        timeline = timeline_builder.build_timeline(videos, unified_kg)
        
        results['timeline_built'] = True
        results['timeline_stats'] = timeline['stats']
        logger.info(f"  ✓ Timeline built: {timeline['stats']}")
        
        # Step 4: Build cross-video relationships
        logger.info("\n" + "=" * 80)
        logger.info("STEP 4: BUILDING CROSS-VIDEO RELATIONSHIPS")
        logger.info("=" * 80)
        
        relationships_created = build_cross_video_relationships(unified_kg, entity_results)
        results['relationships_created'] = relationships_created
        logger.info(f"  ✓ Created {relationships_created} cross-video relationships")
        
        # Step 5: Extract themes across videos
        logger.info("\n" + "=" * 80)
        logger.info("STEP 5: EXTRACTING CROSS-VIDEO THEMES")
        logger.info("=" * 80)
        
        themes_extracted = extract_cross_video_themes(unified_kg, config)
        results['themes_extracted'] = themes_extracted
        logger.info(f"  ✓ Extracted {themes_extracted} themes")
        
        # Get final statistics
        logger.info("\n" + "=" * 80)
        logger.info("FINAL STATISTICS")
        logger.info("=" * 80)
        
        stats = unified_kg.get_statistics()
        results['stats'] = stats
        
        logger.info(f"  Total Videos: {stats['total_videos']}")
        logger.info(f"  Global Entities: {stats['total_global_entities']}")
        logger.info(f"  Entity Instances: {stats['total_entity_instances']}")
        logger.info(f"  Cross-Video Relationships: {stats['total_relationships']}")
        logger.info(f"  Timeline Events: {stats['total_timeline_events']}")
        logger.info(f"  Themes: {stats['total_themes']}")
        
        if 'year_range' in stats:
            logger.info(f"  Year Range: {stats['year_range']}")
        
        if stats.get('entities_by_type'):
            logger.info("\n  Entities by Type:")
            for entity_type, count in stats['entities_by_type'].items():
                logger.info(f"    - {entity_type}: {count}")
        
        if stats.get('top_entities'):
            logger.info("\n  Top Entities:")
            for entity in stats['top_entities'][:5]:
                logger.info(f"    - {entity['name']} ({entity['type']}): {entity['count']} appearances")
        
    except Exception as e:
        logger.error(f"Failed to build unified KG: {e}", exc_info=True)
        results['errors'].append(str(e))
    
    finally:
        unified_kg.close()
    
    return results


def build_cross_video_relationships(unified_kg, entity_results: Dict) -> int:
    """Build relationships between entities that appear together across videos"""
    count = 0
    
    try:
        cursor = unified_kg.conn.cursor()
        
        # Get all global entities
        entities = cursor.execute("""
            SELECT id, entity_type, canonical_name
            FROM global_entities
        """).fetchall()
        
        # For each pair of entities, check if they co-occur
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i+1:]:
                # Get videos where both appear
                videos1 = set(row[0] for row in cursor.execute("""
                    SELECT DISTINCT video_hash
                    FROM entity_instances
                    WHERE global_entity_id = ?
                """, (entity1[0],)).fetchall())
                
                videos2 = set(row[0] for row in cursor.execute("""
                    SELECT DISTINCT video_hash
                    FROM entity_instances
                    WHERE global_entity_id = ?
                """, (entity2[0],)).fetchall())
                
                common_videos = videos1 & videos2
                
                if common_videos:
                    # They co-occur across videos
                    strength = len(common_videos) / max(len(videos1), len(videos2))
                    
                    unified_kg.add_cross_video_relationship(
                        entity1_id=entity1[0],
                        entity2_id=entity2[0],
                        relationship_type='social',
                        relationship_label='appears_with',
                        strength=strength,
                        evidence={'common_videos': list(common_videos)}
                    )
                    count += 1
        
    except Exception as e:
        logger.error(f"Failed to build relationships: {e}")
    
    return count


def extract_cross_video_themes(unified_kg, config: Dict[str, Any]) -> int:
    """Extract themes that appear across multiple videos"""
    count = 0
    
    try:
        cursor = unified_kg.conn.cursor()
        
        # Get concept/tag nodes from all videos and aggregate
        theme_counts = {}
        
        entities = cursor.execute("""
            SELECT canonical_name, entity_type
            FROM global_entities
            WHERE entity_type IN ('concept', 'tag', 'theme')
        """).fetchall()
        
        for entity in entities:
            name = entity[0]
            
            # Count appearances
            appearances = cursor.execute("""
                SELECT COUNT(DISTINCT video_hash)
                FROM entity_instances
                WHERE global_entity_id IN (
                    SELECT id FROM global_entities WHERE canonical_name = ?
                )
            """, (name,)).fetchone()[0]
            
            if appearances >= 2:  # Theme appears in at least 2 videos
                theme_id = unified_kg.add_theme(
                    theme_name=name,
                    category='content',
                    description=f"Appears in {appearances} videos"
                )
                
                # Link theme instances
                instances = cursor.execute("""
                    SELECT video_hash, timestamp_start, timestamp_end
                    FROM entity_instances
                    WHERE global_entity_id IN (
                        SELECT id FROM global_entities WHERE canonical_name = ?
                    )
                """, (name,)).fetchall()
                
                for instance in instances:
                    unified_kg.link_theme_instance(
                        theme_id=theme_id,
                        video_hash=instance[0],
                        timestamp_start=instance[1],
                        timestamp_end=instance[2],
                        relevance_score=1.0
                    )
                
                count += 1
        
    except Exception as e:
        logger.error(f"Failed to extract themes: {e}")
    
    return count


def main():
    """Main entry point"""
    logger.info("Starting unified knowledge graph construction...")
    
    # Load config
    config = load_config()
    
    # Discover processed videos
    videos = discover_processed_videos(config)
    
    if not videos:
        logger.error("No processed videos found!")
        return
    
    logger.info(f"Found {len(videos)} processed videos")
    for v in videos:
        logger.info(f"  - {v['video_hash']}: {v.get('year', 'unknown')} ({v['scene_count']} scenes)")
    
    # Build unified KG
    results = build_unified_knowledge_graph(config, videos)
    
    # Save results
    results_path = Path("L:/goodq4all/logs/unified_kg_build_results.json")
    results_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"\nResults saved to: {results_path}")
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ PHASE 8: UNIFIED KNOWLEDGE GRAPH COMPLETE")
    logger.info("=" * 80)
    
    if results.get('errors'):
        logger.warning(f"\n⚠️  Completed with {len(results['errors'])} errors")
        for error in results['errors']:
            logger.warning(f"  - {error}")
    else:
        logger.info("\n🎉 No errors encountered!")


if __name__ == "__main__":
    main()
