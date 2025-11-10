"""
Analyze Unified Knowledge Graph - Phase 8
Query and explore the cross-video unified knowledge graph
"""
import json
import sqlite3
import logging
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def analyze_unified_kg(db_path: str):
    """Comprehensive analysis of the unified knowledge graph"""
    
    print("=" * 80)
    print("UNIFIED KNOWLEDGE GRAPH ANALYSIS")
    print("=" * 80)
    print()
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Video Registry
    print("📹 VIDEO REGISTRY")
    print("-" * 80)
    videos = cursor.execute("""
        SELECT video_hash, video_path, year, month, day, duration, scene_count
        FROM video_registry
        ORDER BY year, month, day
    """).fetchall()
    
    for video in videos:
        year_str = f"{video['year']}" if video['year'] else "Unknown"
        if video['month']:
            year_str += f"-{video['month']:02d}"
        if video['day']:
            year_str += f"-{video['day']:02d}"
        
        print(f"  📼 {Path(video['video_path']).name}")
        print(f"     Date: {year_str}")
        print(f"     Duration: {video['duration']:.1f}s | Scenes: {video['scene_count']}")
        print()
    
    # 2. Global Entities
    print("🌐 GLOBAL ENTITIES")
    print("-" * 80)
    entity_stats = cursor.execute("""
        SELECT entity_type, COUNT(*) as count
        FROM global_entities
        GROUP BY entity_type
        ORDER BY count DESC
    """).fetchall()
    
    for stat in entity_stats:
        print(f"  {stat['entity_type']}: {stat['count']}")
    print()
    
    # 3. Top Entities
    print("⭐ TOP ENTITIES (by appearance count)")
    print("-" * 80)
    top_entities = cursor.execute("""
        SELECT canonical_name, entity_type, appearance_count
        FROM global_entities
        ORDER BY appearance_count DESC
        LIMIT 15
    """).fetchall()
    
    for entity in top_entities:
        print(f"  {entity['canonical_name']} ({entity['entity_type']}): {entity['appearance_count']} appearances")
    print()
    
    # 4. Cross-Video Relationships
    print("🔗 CROSS-VIDEO RELATIONSHIPS")
    print("-" * 80)
    
    total_rels = cursor.execute("SELECT COUNT(*) FROM cross_video_relationships").fetchone()[0]
    print(f"  Total Relationships: {total_rels}")
    
    rel_types = cursor.execute("""
        SELECT relationship_type, COUNT(*) as count
        FROM cross_video_relationships
        GROUP BY relationship_type
        ORDER BY count DESC
    """).fetchall()
    
    for rel in rel_types:
        print(f"  {rel['relationship_type']}: {rel['count']}")
    print()
    
    # 5. Strongest Relationships
    print("💪 STRONGEST RELATIONSHIPS (top 10)")
    print("-" * 80)
    
    strong_rels = cursor.execute("""
        SELECT 
            e1.canonical_name as entity1,
            e2.canonical_name as entity2,
            r.relationship_label,
            r.strength,
            r.evidence_count
        FROM cross_video_relationships r
        JOIN global_entities e1 ON r.entity1_id = e1.id
        JOIN global_entities e2 ON r.entity2_id = e2.id
        ORDER BY r.strength DESC
        LIMIT 10
    """).fetchall()
    
    for rel in strong_rels:
        print(f"  {rel['entity1']} --[{rel['relationship_label']}]--> {rel['entity2']}")
        print(f"    Strength: {rel['strength']:.2f} | Evidence: {rel['evidence_count']}")
    print()
    
    # 6. Timeline Events
    print("📅 TIMELINE")
    print("-" * 80)
    
    timeline_count = cursor.execute("SELECT COUNT(*) FROM temporal_timeline").fetchone()[0]
    print(f"  Total Events: {timeline_count}")
    
    event_types = cursor.execute("""
        SELECT event_type, COUNT(*) as count
        FROM temporal_timeline
        GROUP BY event_type
        ORDER BY count DESC
    """).fetchall()
    
    print("\n  Events by Type:")
    for event in event_types:
        print(f"    {event['event_type']}: {event['count']}")
    print()
    
    # 7. Year Coverage
    print("📆 YEAR COVERAGE")
    print("-" * 80)
    
    year_stats = cursor.execute("""
        SELECT 
            year,
            COUNT(DISTINCT video_hash) as video_count,
            COUNT(*) as event_count
        FROM temporal_timeline
        WHERE year IS NOT NULL
        GROUP BY year
        ORDER BY year
    """).fetchall()
    
    for year_stat in year_stats:
        print(f"  {year_stat['year']}: {year_stat['video_count']} videos, {year_stat['event_count']} events")
    print()
    
    # 8. Themes (if any)
    theme_count = cursor.execute("SELECT COUNT(*) FROM thematic_index").fetchone()[0]
    if theme_count > 0:
        print("🎨 THEMES")
        print("-" * 80)
        
        themes = cursor.execute("""
            SELECT theme_name, theme_category, video_count, scene_count
            FROM thematic_index
            ORDER BY scene_count DESC
        """).fetchall()
        
        for theme in themes:
            print(f"  {theme['theme_name']} ({theme['theme_category']})")
            print(f"    Videos: {theme['video_count']} | Scenes: {theme['scene_count']}")
        print()
    
    # 9. Sample Queries
    print("🔍 SAMPLE QUERIES")
    print("-" * 80)
    
    # Query 1: Find all people
    people = cursor.execute("""
        SELECT canonical_name, appearance_count
        FROM global_entities
        WHERE entity_type = 'person'
        ORDER BY appearance_count DESC
    """).fetchall()
    
    print("\n  Q1: Who appears in the videos?")
    if people:
        for person in people:
            print(f"    - {person['canonical_name']} ({person['appearance_count']} appearances)")
    else:
        print("    No named people detected")
    
    # Query 2: Find all objects
    print("\n  Q2: What objects are present?")
    objects = cursor.execute("""
        SELECT canonical_name, appearance_count
        FROM global_entities
        WHERE entity_type = 'object'
        ORDER BY appearance_count DESC
        LIMIT 10
    """).fetchall()
    
    for obj in objects:
        print(f"    - {obj['canonical_name']} ({obj['appearance_count']} times)")
    
    # Query 3: Find emotional content
    print("\n  Q3: What emotions are detected?")
    emotions = cursor.execute("""
        SELECT canonical_name, appearance_count
        FROM global_entities
        WHERE entity_type = 'emotion'
        ORDER BY appearance_count DESC
    """).fetchall()
    
    for emotion in emotions:
        print(f"    - {emotion['canonical_name']} ({emotion['appearance_count']} times)")
    
    print()
    print("=" * 80)
    print("Analysis complete!")
    print("=" * 80)
    
    conn.close()


def main():
    """Main entry point"""
    db_path = Path("L:/goodq4all/data/unified_goodq.db")
    
    if not db_path.exists():
        print(f"❌ Unified KG database not found at {db_path}")
        print("Run build_unified_kg.py first!")
        return
    
    analyze_unified_kg(str(db_path))


if __name__ == "__main__":
    main()
