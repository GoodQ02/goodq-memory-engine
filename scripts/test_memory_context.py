#!/usr/bin/env python3
"""
Test Memory Context Enrichment
Verify that scene processing properly saves enriched context to memory database.
"""
import json
import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from steps.steps.common.config_loader import load_configs
from steps.steps.common.memory import list_scenes_for_video, get_scene_meta
from steps.steps.common.memory_context_writer import save_step_context


def check_memory_enrichment(video_hash: str, cfg: dict) -> dict:
    """Check if scenes have enriched context in memory database."""
    scenes_data = list_scenes_for_video(cfg, video_hash)
    scenes = scenes_data.get('scenes', [])
    
    enrichment_stats = {
        'total_scenes': len(scenes),
        'with_caption': 0,
        'with_objects': 0,
        'with_ocr': 0,
        'with_transcript': 0,
        'with_sentiment': 0,
        'with_emotions': 0,
        'with_tags': 0,
        'with_entities': 0,
        'scenes_detail': []
    }
    
    for scene in scenes:
        scene_id = scene.get('id')
        meta = scene.get('meta', {})
        
        detail = {
            'scene_id': scene_id,
            'start': scene.get('start'),
            'end': scene.get('end'),
            'has_caption': bool(meta.get('caption')),
            'has_objects': bool(meta.get('objects')),
            'has_ocr': bool(meta.get('ocr_text')),
            'has_transcript': bool(meta.get('transcript')),
            'has_sentiment': bool(meta.get('sentiment') or meta.get('sentiment_label')),
            'has_emotions': bool(meta.get('emotions')),
            'has_tags': bool(meta.get('tags')),
            'has_entities': bool(meta.get('entities')),
        }
        
        # Count enrichments
        if detail['has_caption']:
            enrichment_stats['with_caption'] += 1
        if detail['has_objects']:
            enrichment_stats['with_objects'] += 1
        if detail['has_ocr']:
            enrichment_stats['with_ocr'] += 1
        if detail['has_transcript']:
            enrichment_stats['with_transcript'] += 1
        if detail['has_sentiment']:
            enrichment_stats['with_sentiment'] += 1
        if detail['has_emotions']:
            enrichment_stats['with_emotions'] += 1
        if detail['has_tags']:
            enrichment_stats['with_tags'] += 1
        if detail['has_entities']:
            enrichment_stats['with_entities'] += 1
        
        enrichment_stats['scenes_detail'].append(detail)
    
    return enrichment_stats


def main():
    print("=" * 70)
    print("MEMORY CONTEXT ENRICHMENT TEST")
    print("=" * 70)
    
    cfg = load_configs({})
    
    # Check if we have any video processing results
    results_path = Path("L:/GoodQ_4_All/logs/video_ingest_results.json")
    
    if not results_path.exists():
        print("\nNo video ingest results found.")
        print("Please run video ingestion first.")
        return 1
    
    with open(results_path) as f:
        results = json.load(f)
    
    if not results:
        print("\nNo videos in results file.")
        return 1
    
    # Get the first video
    video_entry = results[0]
    video_hash = video_entry.get('video_hash')
    video_path = video_entry.get('video')
    
    if not video_hash:
        print("\nNo video hash found in results.")
        return 1
    
    print(f"\nVideo: {video_path}")
    print(f"Hash: {video_hash}")
    
    # Check enrichment
    stats = check_memory_enrichment(video_hash, cfg)
    
    print(f"\n📊 Enrichment Statistics:")
    print(f"   Total Scenes: {stats['total_scenes']}")
    print(f"   With Caption: {stats['with_caption']} ({stats['with_caption']/max(stats['total_scenes'],1)*100:.1f}%)")
    print(f"   With Objects: {stats['with_objects']} ({stats['with_objects']/max(stats['total_scenes'],1)*100:.1f}%)")
    print(f"   With OCR: {stats['with_ocr']} ({stats['with_ocr']/max(stats['total_scenes'],1)*100:.1f}%)")
    print(f"   With Transcript: {stats['with_transcript']} ({stats['with_transcript']/max(stats['total_scenes'],1)*100:.1f}%)")
    print(f"   With Sentiment: {stats['with_sentiment']} ({stats['with_sentiment']/max(stats['total_scenes'],1)*100:.1f}%)")
    print(f"   With Emotions: {stats['with_emotions']} ({stats['with_emotions']/max(stats['total_scenes'],1)*100:.1f}%)")
    print(f"   With Tags: {stats['with_tags']} ({stats['with_tags']/max(stats['total_scenes'],1)*100:.1f}%)")
    print(f"   With Entities: {stats['with_entities']} ({stats['with_entities']/max(stats['total_scenes'],1)*100:.1f}%)")
    
    print(f"\n📝 Scene Details:")
    for detail in stats['scenes_detail'][:5]:  # Show first 5
        print(f"\n   Scene {detail['scene_id']} ({detail['start']:.1f}s - {detail['end']:.1f}s):")
        enrichments = []
        if detail['has_caption']:
            enrichments.append('caption')
        if detail['has_objects']:
            enrichments.append('objects')
        if detail['has_ocr']:
            enrichments.append('ocr')
        if detail['has_transcript']:
            enrichments.append('transcript')
        if detail['has_sentiment']:
            enrichments.append('sentiment')
        if detail['has_emotions']:
            enrichments.append('emotions')
        if detail['has_tags']:
            enrichments.append('tags')
        if detail['has_entities']:
            enrichments.append('entities')
        
        if enrichments:
            print(f"      Enriched with: {', '.join(enrichments)}")
        else:
            print(f"      ⚠️  No enrichment data")
    
    if stats['total_scenes'] > 5:
        print(f"\n   ... and {stats['total_scenes'] - 5} more scenes")
    
    # Overall assessment
    print(f"\n{'='*70}")
    enriched_count = sum(1 for d in stats['scenes_detail'] if any([
        d['has_caption'], d['has_objects'], d['has_ocr'], d['has_transcript'],
        d['has_sentiment'], d['has_emotions'], d['has_tags'], d['has_entities']
    ]))
    
    if enriched_count == 0:
        print("❌ FAILED: No scenes have enriched context")
        print("\nThis indicates the memory context writer is not being called.")
        print("Check that:")
        print("  1. Steps are running successfully")
        print("  2. Step runner is calling save_memory_context()")
        print("  3. Memory database is writable")
        return 1
    elif enriched_count < stats['total_scenes']:
        print(f"⚠️  PARTIAL: {enriched_count}/{stats['total_scenes']} scenes have enrichment")
        print("\nSome scenes are missing context. This may be normal if:")
        print("  - Processing is still ongoing")
        print("  - Some steps failed or were skipped")
        print("  - Not all modalities are present (e.g., no audio)")
        return 0
    else:
        print(f"✅ SUCCESS: All {stats['total_scenes']} scenes have enriched context!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
