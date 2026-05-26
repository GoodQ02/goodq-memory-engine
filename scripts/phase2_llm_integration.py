"""
Phase 2: LLM-Enhanced Semantic Analysis Integration

LEGACY / OFF-PATH NOTICE
This script is not part of the canonical scene-centric ingestion runtime.
It is retained only as a historical / experimental harness for the older
Phase 2 LLM workflow and must not be treated as a supported production path.

Use the canonical runtime surfaces instead:
- cli.run_ingestion
- steps.video.cross_modal_harmonizer

Direct execution now requires an explicit acknowledgement flag so this script
cannot be mistaken for a supported operational tool.
"""
import sys
import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from steps.common.config_loader import load_configs
from steps.common.context_analyzer_llm import (
    analyze_scene_context_llm,
    analyze_emotional_progression,
    build_relationship_map
)
from steps.tagger.step_llm_enhanced import tagger_llm_enhanced

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

LEGACY_PHASE2_NOTICE = (
    "LEGACY / OFF-PATH: scripts/phase2_llm_integration.py is not on the canonical "
    "scene-memory ingestion path. Re-run with --allow-legacy-run only if you "
    "explicitly intend to use this historical workflow."
)


def apply_context_analysis_to_scenes(cfg: Dict[str, Any], video_hash: str = None) -> Dict[str, Any]:
    """
    Apply LLM context analysis to all scenes
    
    Args:
        cfg: Configuration dictionary
        video_hash: Optional video hash to process (processes all if None)
        
    Returns:
        Statistics dictionary
    """
    db_path = cfg['paths']['db_path']
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Get scenes to process
    if video_hash:
        c.execute("SELECT id, meta FROM scenes WHERE video_hash=? ORDER BY start", (video_hash,))
    else:
        c.execute("SELECT id, meta FROM scenes ORDER BY start")
    
    scenes = c.fetchall()
    logger.info(f"Processing {len(scenes)} scenes for context analysis")
    
    stats = {
        'total_scenes': len(scenes),
        'analyzed': 0,
        'failed': 0,
        'skipped': 0
    }
    
    for scene_id, meta_json in scenes:
        try:
            scene_meta = json.loads(meta_json)
            
            # Skip if already has context analysis
            if scene_meta.get('context_analyzed'):
                stats['skipped'] += 1
                continue
            
            # Perform LLM context analysis
            logger.info(f"Analyzing scene {scene_id} (index {scene_meta.get('index', '?')})")
            context_data = analyze_scene_context_llm(scene_meta, cfg)
            
            if context_data:
                # Update scene metadata with context
                scene_meta['context'] = context_data
                scene_meta['context_analyzed'] = True
                
                # Update database
                c.execute(
                    "UPDATE scenes SET meta=? WHERE id=?",
                    (json.dumps(scene_meta), scene_id)
                )
                
                stats['analyzed'] += 1
                logger.info(f"  [SYMBOL] Context added: {len(context_data.get('key_moments', []))} key moments, "
                           f"{len(context_data.get('context_tags', []))} tags")
            else:
                stats['failed'] += 1
                logger.warning(f"  [SYMBOL] Context analysis failed for scene {scene_id}")
                
        except Exception as e:
            logger.error(f"Error processing scene {scene_id}: {e}")
            stats['failed'] += 1
    
    conn.commit()
    conn.close()
    
    logger.info(f"\nContext Analysis Complete:")
    logger.info(f"  Analyzed: {stats['analyzed']}/{stats['total_scenes']}")
    logger.info(f"  Skipped: {stats['skipped']}")
    logger.info(f"  Failed: {stats['failed']}")
    
    return stats


def apply_intelligent_tagging(cfg: Dict[str, Any], video_hash: str = None) -> Dict[str, Any]:
    """
    Apply LLM-enhanced intelligent tagging to all scenes
    
    Args:
        cfg: Configuration dictionary
        video_hash: Optional video hash to process
        
    Returns:
        Statistics dictionary
    """
    db_path = cfg['paths']['db_path']
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Get scenes
    if video_hash:
        c.execute("SELECT id, meta FROM scenes WHERE video_hash=? ORDER BY start", (video_hash,))
    else:
        c.execute("SELECT id, meta FROM scenes ORDER BY start")
    
    scenes = c.fetchall()
    logger.info(f"Applying intelligent tagging to {len(scenes)} scenes")
    
    stats = {
        'total_scenes': len(scenes),
        'tagged': 0,
        'failed': 0,
        'skipped': 0,
        'llm_used': 0,
        'fallback_used': 0
    }
    
    for scene_id, meta_json in scenes:
        try:
            scene_meta = json.loads(meta_json)
            
            # Skip if already has LLM tags
            if scene_meta.get('llm_tags_applied'):
                stats['skipped'] += 1
                continue
            
            logger.info(f"Tagging scene {scene_id} (index {scene_meta.get('index', '?')})")
            
            # Apply LLM tagging
            tag_result = tagger_llm_enhanced(scene_meta, cfg)
            
            if tag_result:
                # Merge tags into scene metadata
                scene_meta['tags'] = tag_result.get('tags', [])
                scene_meta['entities'] = tag_result.get('entities', [])
                scene_meta['themes'] = tag_result.get('themes', [])
                scene_meta['keywords'] = tag_result.get('keywords', [])
                scene_meta['usefulness'] = tag_result.get('usefulness', 0.0)
                scene_meta['tagging_method'] = tag_result.get('method', 'unknown')
                scene_meta['llm_tags_applied'] = True
                
                # Update database
                c.execute(
                    "UPDATE scenes SET meta=? WHERE id=?",
                    (json.dumps(scene_meta), scene_id)
                )
                
                stats['tagged'] += 1
                if tag_result.get('method') == 'llm':
                    stats['llm_used'] += 1
                else:
                    stats['fallback_used'] += 1
                
                logger.info(f"  [SYMBOL] Tags: {len(tag_result.get('tags', []))}, "
                           f"Entities: {len(tag_result.get('entities', []))}, "
                           f"Method: {tag_result.get('method')}")
            else:
                stats['failed'] += 1
                logger.warning(f"  [SYMBOL] Tagging failed for scene {scene_id}")
                
        except Exception as e:
            logger.error(f"Error tagging scene {scene_id}: {e}")
            stats['failed'] += 1
    
    conn.commit()
    conn.close()
    
    logger.info(f"\nIntelligent Tagging Complete:")
    logger.info(f"  Tagged: {stats['tagged']}/{stats['total_scenes']}")
    logger.info(f"  LLM used: {stats['llm_used']}")
    logger.info(f"  Fallback used: {stats['fallback_used']}")
    logger.info(f"  Skipped: {stats['skipped']}")
    logger.info(f"  Failed: {stats['failed']}")
    
    return stats


def apply_emotional_arc_analysis(cfg: Dict[str, Any], video_hash: str = None) -> Dict[str, Any]:
    """
    Apply emotional arc analysis across video scenes
    
    Args:
        cfg: Configuration dictionary
        video_hash: Optional video hash to process
        
    Returns:
        Statistics and results
    """
    db_path = cfg['paths']['db_path']
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Get all scenes for video
    if video_hash:
        c.execute("SELECT meta FROM scenes WHERE video_hash=? ORDER BY start", (video_hash,))
    else:
        # Get first video's scenes
        c.execute("SELECT DISTINCT video_hash FROM scenes LIMIT 1")
        row = c.fetchone()
        if not row:
            logger.warning("No videos found for emotional arc analysis")
            conn.close()
            return {'error': 'No videos found'}
        video_hash = row[0]
        c.execute("SELECT meta FROM scenes WHERE video_hash=? ORDER BY start", (video_hash,))
    
    scenes = []
    for (meta_json,) in c.fetchall():
        scenes.append(json.loads(meta_json))
    
    logger.info(f"Analyzing emotional arc for {len(scenes)} scenes")
    
    # Perform analysis
    arc_data = analyze_emotional_progression(scenes, cfg)
    
    if arc_data:
        # Store in database
        try:
            c.execute("""
                INSERT OR REPLACE INTO summaries (summary_type, category, content, created_at)
                VALUES ('video', 'emotional_arc', ?, datetime('now'))
            """, (json.dumps({
                'video_hash': video_hash,
                'arc_data': arc_data,
                'scene_count': len(scenes)
            }),))
            conn.commit()
            
            logger.info("\n[SYMBOL] Emotional Arc Analysis Complete:")
            logger.info(f"  Overall Arc: {arc_data.get('overall_arc', 'N/A')}")
            logger.info(f"  Dominant Emotions: {', '.join(arc_data.get('dominant_emotions', []))}")
            logger.info(f"  Key Transitions: {len(arc_data.get('key_transitions', []))}")
            
            conn.close()
            return {
                'success': True,
                'video_hash': video_hash,
                'arc_data': arc_data
            }
        except Exception as e:
            logger.error(f"Failed to store emotional arc: {e}")
            conn.close()
            return {'error': str(e)}
    else:
        logger.warning("Emotional arc analysis failed")
        conn.close()
        return {'error': 'Analysis failed'}


def apply_relationship_mapping(cfg: Dict[str, Any], video_hash: str = None) -> Dict[str, Any]:
    """
    Build relationship map from scene context data
    
    Args:
        cfg: Configuration dictionary
        video_hash: Optional video hash to process
        
    Returns:
        Relationship map data
    """
    db_path = cfg['paths']['db_path']
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Get scenes with context
    if video_hash:
        c.execute("SELECT meta FROM scenes WHERE video_hash=? ORDER BY start", (video_hash,))
    else:
        c.execute("SELECT DISTINCT video_hash FROM scenes LIMIT 1")
        row = c.fetchone()
        if not row:
            conn.close()
            return {'error': 'No videos found'}
        video_hash = row[0]
        c.execute("SELECT meta FROM scenes WHERE video_hash=? ORDER BY start", (video_hash,))
    
    scenes = []
    for (meta_json,) in c.fetchall():
        scenes.append(json.loads(meta_json))
    
    logger.info(f"Building relationship map from {len(scenes)} scenes")
    
    # Build map
    relationship_data = build_relationship_map(scenes, cfg)
    
    if relationship_data:
        # Store in database
        try:
            c.execute("""
                INSERT OR REPLACE INTO summaries (summary_type, category, content, created_at)
                VALUES ('video', 'relationship_map', ?, datetime('now'))
            """, (json.dumps({
                'video_hash': video_hash,
                'relationship_data': relationship_data
            }),))
            conn.commit()
            
            logger.info("\n[SYMBOL] Relationship Map Complete:")
            logger.info(f"  Entities: {relationship_data.get('total_entities', 0)}")
            logger.info(f"  Interactions: {relationship_data.get('total_interactions', 0)}")
            logger.info(f"  Interaction Types: {list(relationship_data.get('interaction_patterns', {}).keys())}")
            
            conn.close()
            return {
                'success': True,
                'video_hash': video_hash,
                'relationship_data': relationship_data
            }
        except Exception as e:
            logger.error(f"Failed to store relationship map: {e}")
            conn.close()
            return {'error': str(e)}
    else:
        logger.warning("Relationship mapping failed")
        conn.close()
        return {'error': 'Mapping failed'}


def run_phase2_integration(video_hash: str = None) -> Dict[str, Any]:
    """
    Run complete Phase 2 LLM integration
    
    Args:
        video_hash: Optional video hash to process (processes all if None)
        
    Returns:
        Complete results dictionary
    """
    logger.info("="*80)
    logger.info("PHASE 2: LLM-Enhanced Semantic Analysis Integration")
    logger.info("="*80)
    
    # Load configuration
    cfg = load_configs()
    
    # Check LLM availability
    logger.info("\n[1/5] Checking LLM availability...")
    try:
        import requests
        llm_url = cfg.get('config', {}).get('llm', {}).get('api_url', 'http://localhost:1234/v1/models')
        response = requests.get(llm_url.replace('/chat/completions', '/models'), timeout=5)
        if response.status_code == 200:
            logger.info("  [SYMBOL] LLM endpoint accessible")
        else:
            logger.warning(f"  [SYMBOL] LLM endpoint returned status {response.status_code}")
    except Exception as e:
        logger.error(f"  [SYMBOL] LLM not accessible: {e}")
        return {'error': 'LLM not available'}
    
    results = {
        'phase': 2,
        'video_hash': video_hash or 'all',
        'timestamp': str(Path(__file__).stat().st_mtime)
    }
    
    # Step 1: Context Analysis
    logger.info("\n[2/5] Applying LLM Context Analysis...")
    context_stats = apply_context_analysis_to_scenes(cfg, video_hash)
    results['context_analysis'] = context_stats
    
    # Step 2: Intelligent Tagging
    logger.info("\n[3/5] Applying LLM Intelligent Tagging...")
    tagging_stats = apply_intelligent_tagging(cfg, video_hash)
    results['intelligent_tagging'] = tagging_stats
    
    # Step 3: Emotional Arc Analysis
    logger.info("\n[4/5] Analyzing Emotional Arc...")
    arc_results = apply_emotional_arc_analysis(cfg, video_hash)
    results['emotional_arc'] = arc_results
    
    # Step 4: Relationship Mapping
    logger.info("\n[5/5] Building Relationship Map...")
    relationship_results = apply_relationship_mapping(cfg, video_hash)
    results['relationship_mapping'] = relationship_results
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("PHASE 2 INTEGRATION COMPLETE")
    logger.info("="*80)
    logger.info(f"Context Analysis: {context_stats.get('analyzed', 0)} scenes")
    logger.info(f"Intelligent Tagging: {tagging_stats.get('tagged', 0)} scenes ({tagging_stats.get('llm_used', 0)} via LLM)")
    logger.info(f"Emotional Arc: {'[SYMBOL]' if arc_results.get('success') else '[SYMBOL]'}")
    logger.info(f"Relationship Map: {relationship_results.get('relationship_data', {}).get('total_entities', 0)} entities, "
                f"{relationship_results.get('relationship_data', {}).get('total_interactions', 0)} interactions")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Phase 2: LLM-Enhanced Semantic Analysis")
    parser.add_argument('--video-hash', help='Process specific video hash only')
    parser.add_argument('--test', action='store_true', help='Run on sample.mp4 only')
    parser.add_argument('--allow-legacy-run', action='store_true', help='Acknowledge that this script is a legacy off-path workflow')
    
    args = parser.parse_args()

    if not args.allow_legacy_run:
        logger.error(LEGACY_PHASE2_NOTICE)
        sys.exit(2)
    
    # If test mode, get sample video hash
    video_hash = args.video_hash
    if args.test:
        cfg = load_configs()
        db_path = cfg['paths']['db_path']
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        # Get any video hash since we can't easily query JSON
        c.execute("SELECT DISTINCT video_hash FROM scenes LIMIT 1")
        row = c.fetchone()
        conn.close()
        if row:
            video_hash = row[0]
            logger.info(f"Test mode: Processing first available video {video_hash}")
        else:
            logger.error("No videos found in database")
            sys.exit(1)
    
    results = run_phase2_integration(video_hash)
    
    # Save results
    results_path = Path(__file__).parent / 'PHASE2_RESULTS.json'
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"\nResults saved to: {results_path}")
