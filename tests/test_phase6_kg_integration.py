"""
Phase 6 Test: Knowledge Graph Integration Validation
Tests real-time KG updates, entity resolution, and cross-modal linking
"""
import sqlite3
import json
from pathlib import Path
import sys

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from lib.knowledge_graph import KnowledgeGraph
from lib.entity_resolver import EntityResolver, Entity
from lib.kg_realtime_integration import extract_scene_entities, update_kg_for_scene
from steps.common.config_loader import load_configs

def test_entity_extraction():
    """Test entity extraction from scene data"""
    print("\n" + "="*80)
    print("TEST 1: Entity Extraction from Scene Data")
    print("="*80)
    
    # Mock scene data
    scene_data = {
        'index': 0,
        'start': 0.0,
        'end': 10.0,
        'keyframe': {
            'objects': [
                {'class': 'person', 'confidence': 0.95, 'bbox': [100, 100, 200, 300]},
                {'class': 'bottle', 'confidence': 0.87, 'bbox': [50, 200, 80, 280]},
            ],
            'faces': [
                {'name': 'Person_1', 'confidence': 0.92, 'bbox': [110, 110, 190, 250]}
            ],
            'tags': ['interview', 'indoor', 'conversation'],
            'emotion': 'neutral',
            'sentiment': 'positive'
        },
        'audio': {
            'transcript': 'Colin and I were discussing the band and our music journey.',
            'speakers': [
                {'speaker': 'Speaker_1', 'utterances': 3},
                {'speaker': 'Speaker_2', 'utterances': 2}
            ]
        }
    }
    
    entities = extract_scene_entities(
        scene_data,
        scene_id='test_scene_001',
        video_hash='test_video_hash',
        timestamp=5.0
    )
    
    print(f"\nVisual entities extracted: {len(entities['visual'])}")
    for e in entities['visual'][:3]:
        print(f"  - {e.name} ({e.entity_type}) conf={e.confidence:.2f}")
    
    print(f"\nAudio entities extracted: {len(entities['audio'])}")
    for e in entities['audio'][:3]:
        print(f"  - {e.name} ({e.entity_type}) conf={e.confidence:.2f}")
    
    print(f"\nSummary entities extracted: {len(entities['summary'])}")
    for e in entities['summary'][:3]:
        print(f"  - {e.name} ({e.entity_type}) conf={e.confidence:.2f}")
    
    return len(entities['visual']) + len(entities['audio']) + len(entities['summary'])


def test_entity_resolution():
    """Test cross-modal entity resolution"""
    print("\n" + "="*80)
    print("TEST 2: Cross-Modal Entity Resolution")
    print("="*80)
    
    resolver = EntityResolver(confidence_threshold=0.6)
    
    # Create duplicate entities from different sources
    entities = [
        Entity('person', 'John Smith', 0.9, 'visual', 'scene_1', 5.0, {}),
        Entity('person', 'john smith', 0.7, 'audio', 'scene_1', 5.5, {}),
        Entity('person', 'John', 0.6, 'llm_summary', 'scene_1', 6.0, {}),
        Entity('object', 'bottle', 0.85, 'visual', 'scene_1', 5.0, {}),
        Entity('object', 'Bottle', 0.75, 'llm_summary', 'scene_1', 5.5, {}),
    ]
    
    resolved = resolver.resolve_cross_modal_entities(
        visual_entities=[e for e in entities if e.source == 'visual'],
        audio_entities=[e for e in entities if e.source == 'audio'],
        summary_entities=[e for e in entities if e.source == 'llm_summary']
    )
    
    print(f"\nOriginal entities: {len(entities)}")
    print(f"Resolved canonical entities: {len(resolved)}")
    
    for canonical_name, instances in resolved.items():
        sources = [e.source for e in instances]
        print(f"\n  '{canonical_name}': {len(instances)} instances from {set(sources)}")
        for inst in instances:
            print(f"    - {inst.name} ({inst.source}, conf={inst.confidence:.2f})")
    
    return len(resolved)


def test_kg_database_structure():
    """Test knowledge graph database structure"""
    print("\n" + "="*80)
    print("TEST 3: Knowledge Graph Database Structure")
    print("="*80)
    
    kg_path = Path('data/knowledge_graph.db')
    if not kg_path.exists():
        print(f"\n❌ Knowledge graph database not found at {kg_path}")
        return 0
    
    conn = sqlite3.connect(str(kg_path))
    cursor = conn.cursor()
    
    # Check tables
    tables = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    
    print(f"\nDatabase tables: {len(tables)}")
    for table in tables:
        count = cursor.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
        print(f"  - {table[0]}: {count} rows")
    
    # Check recent nodes
    print("\nRecent nodes (last 10):")
    for row in cursor.execute("""
        SELECT node_type, name, occurrence_count 
        FROM nodes 
        ORDER BY id DESC 
        LIMIT 10
    """):
        print(f"  - {row[1]} ({row[0]}) x{row[2]}")
    
    conn.close()
    return len(tables)


def test_kg_stats():
    """Test knowledge graph statistics"""
    print("\n" + "="*80)
    print("TEST 4: Knowledge Graph Statistics")
    print("="*80)
    
    kg_path = Path('data/knowledge_graph.db')
    if not kg_path.exists():
        print(f"\n❌ Knowledge graph not found")
        return 0
    
    with KnowledgeGraph(str(kg_path)) as kg:
        stats = kg.get_statistics()
        
        print(f"\nTotal Nodes: {stats.get('total_nodes', 0)}")
        print(f"Total Edges: {stats.get('total_edges', 0)}")
        print(f"Total Media: {stats.get('total_media', 0)}")
        print(f"Total Events: {stats.get('total_events', 0)}")
        
        print("\nNodes by Type:")
        for node_type, count in stats.get('nodes_by_type', {}).items():
            print(f"  - {node_type}: {count}")
        
        print("\nEdges by Type:")
        for edge_type, count in stats.get('edges_by_type', {}).items():
            print(f"  - {edge_type}: {count}")
        
        print("\nMedia by Type:")
        for media_type, count in stats.get('media_by_type', {}).items():
            print(f"  - {media_type}: {count}")
    
    return stats.get('total_nodes', 0)


def test_llm_extracted_entities():
    """Test if LLM-extracted entities are in KG"""
    print("\n" + "="*80)
    print("TEST 5: LLM-Extracted Entities in Knowledge Graph")
    print("="*80)
    
    kg_path = Path('data/knowledge_graph.db')
    if not kg_path.exists():
        print(f"\n❌ Knowledge graph not found")
        return 0
    
    conn = sqlite3.connect(str(kg_path))
    cursor = conn.cursor()
    
    # Check for concept nodes (themes, topics)
    concepts = cursor.execute("""
        SELECT name, node_type, occurrence_count, properties
        FROM nodes
        WHERE node_type IN ('concept', 'theme', 'emotional_arc')
        ORDER BY occurrence_count DESC
    """).fetchall()
    
    print(f"\nConcept nodes (LLM-generated): {len(concepts)}")
    for row in concepts[:10]:
        props = json.loads(row[3]) if row[3] else {}
        print(f"  - {row[0]} ({row[1]}) x{row[2]}")
        if 'description' in props:
            print(f"    Description: {props['description'][:80]}...")
    
    conn.close()
    return len(concepts)


def test_cross_modal_linking():
    """Test if entities are linked across modalities"""
    print("\n" + "="*80)
    print("TEST 6: Cross-Modal Entity Linking")
    print("="*80)
    
    kg_path = Path('data/knowledge_graph.db')
    if not kg_path.exists():
        print(f"\n❌ Knowledge graph not found")
        return 0
    
    conn = sqlite3.connect(str(kg_path))
    cursor = conn.cursor()
    
    # Find entities that appear in multiple scenes (cross-modal validation)
    multi_scene_entities = cursor.execute("""
        SELECT n.name, n.node_type, COUNT(DISTINCT nm.media_id) as scene_count
        FROM nodes n
        JOIN node_media nm ON n.id = nm.node_id
        GROUP BY n.id
        HAVING scene_count > 1
        ORDER BY scene_count DESC
        LIMIT 10
    """).fetchall()
    
    print(f"\nEntities appearing in multiple scenes: {len(multi_scene_entities)}")
    for row in multi_scene_entities:
        print(f"  - {row[0]} ({row[1]}): {row[2]} scenes")
    
    conn.close()
    return len(multi_scene_entities)


def main():
    print("\n" + "="*80)
    print("PHASE 6: KNOWLEDGE GRAPH INTEGRATION - VALIDATION TEST")
    print("="*80)
    
    results = {}
    
    try:
        results['entity_extraction'] = test_entity_extraction()
    except Exception as e:
        print(f"\n❌ Entity extraction test failed: {e}")
        results['entity_extraction'] = 0
    
    try:
        results['entity_resolution'] = test_entity_resolution()
    except Exception as e:
        print(f"\n❌ Entity resolution test failed: {e}")
        results['entity_resolution'] = 0
    
    try:
        results['db_structure'] = test_kg_database_structure()
    except Exception as e:
        print(f"\n❌ Database structure test failed: {e}")
        results['db_structure'] = 0
    
    try:
        results['kg_stats'] = test_kg_stats()
    except Exception as e:
        print(f"\n❌ KG stats test failed: {e}")
        results['kg_stats'] = 0
    
    try:
        results['llm_entities'] = test_llm_extracted_entities()
    except Exception as e:
        print(f"\n❌ LLM entities test failed: {e}")
        results['llm_entities'] = 0
    
    try:
        results['cross_modal'] = test_cross_modal_linking()
    except Exception as e:
        print(f"\n❌ Cross-modal linking test failed: {e}")
        results['cross_modal'] = 0
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v > 0)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result > 0 else "❌ FAIL"
        print(f"{status} - {test_name}: {result}")
    
    print(f"\nTests Passed: {passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("\n🎉 All Phase 6 tests passed!")
        print("\nNext Steps:")
        print("  1. Run full ingestion on sample.mp4 with KG integration")
        print("  2. Verify real-time entity extraction during processing")
        print("  3. Test natural language queries against KG")
        print("  4. Implement relationship inference with LLM")
    else:
        print("\n⚠️ Some tests failed - review errors above")
    
    return passed_tests == total_tests


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
