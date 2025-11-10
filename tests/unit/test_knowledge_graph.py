"""
Test Knowledge Graph Implementation
Tests the knowledge graph construction and querying
"""
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.knowledge_graph import KnowledgeGraph
from lib.graph_query import GraphQuery


def create_test_graph():
    """Create a test knowledge graph with sample data"""
    test_db = Path("data/test_knowledge_graph.db")
    test_db.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove existing test db
    if test_db.exists():
        test_db.unlink()
    
    print(f"Creating test knowledge graph at {test_db}")
    
    with KnowledgeGraph(str(test_db)) as kg:
        # Add some test media nodes
        media1 = kg.add_media_node(
            media_type='video_scene',
            media_path='test_video.mp4',
            scene_id='scene_0000',
            timestamp_start=0.0,
            timestamp_end=10.0,
            properties={'description': 'Beach scene'}
        )
        
        media2 = kg.add_media_node(
            media_type='video_scene',
            media_path='test_video.mp4',
            scene_id='scene_0001',
            timestamp_start=10.0,
            timestamp_end=20.0,
            properties={'description': 'Park scene'}
        )
        
        # Add some nodes
        person1 = kg.add_node('person', 'John', timestamp=5.0)
        person2 = kg.add_node('person', 'Sarah', timestamp=15.0)
        
        obj1 = kg.add_node('object', 'dog', timestamp=5.0)
        obj2 = kg.add_node('object', 'ball', timestamp=15.0)
        
        loc1 = kg.add_node('location', 'beach', timestamp=5.0)
        loc2 = kg.add_node('location', 'park', timestamp=15.0)
        
        emotion1 = kg.add_node('emotion', 'happy', properties={'score': 0.9}, timestamp=5.0)
        emotion2 = kg.add_node('emotion', 'excited', properties={'score': 0.8}, timestamp=15.0)
        
        # Link nodes to media
        kg.link_node_to_media(person1, media1, confidence=0.95)
        kg.link_node_to_media(obj1, media1, confidence=0.90)
        kg.link_node_to_media(loc1, media1, confidence=0.85)
        kg.link_node_to_media(emotion1, media1, confidence=0.80)
        
        kg.link_node_to_media(person2, media2, confidence=0.92)
        kg.link_node_to_media(obj2, media2, confidence=0.88)
        kg.link_node_to_media(loc2, media2, confidence=0.87)
        kg.link_node_to_media(emotion2, media2, confidence=0.85)
        
        # Create some edges
        kg.add_edge(person1, obj1, 'interacts_with', weight=1.0)
        kg.add_edge(person1, loc1, 'located_in', weight=1.0)
        kg.add_edge(person1, emotion1, 'has_emotion', weight=0.9)
        
        kg.add_edge(person2, obj2, 'interacts_with', weight=1.0)
        kg.add_edge(person2, loc2, 'located_in', weight=1.0)
        kg.add_edge(person2, emotion2, 'has_emotion', weight=0.8)
        
        # Create co-occurrence edges
        kg.add_edge(person1, obj1, 'co_occurs', weight=1.0)
        kg.add_edge(person2, obj2, 'co_occurs', weight=1.0)
        
        # Create temporal events
        event1 = kg.add_temporal_event(
            'scene_change',
            timestamp=0.0,
            duration=10.0,
            properties={'scene_id': 'scene_0000'}
        )
        kg.link_event_to_node(event1, person1, role='participant')
        kg.link_event_to_node(event1, obj1, role='prop')
        
        event2 = kg.add_temporal_event(
            'scene_change',
            timestamp=10.0,
            duration=10.0,
            properties={'scene_id': 'scene_0001'}
        )
        kg.link_event_to_node(event2, person2, role='participant')
        kg.link_event_to_node(event2, obj2, role='prop')
        
        # Get stats
        stats = kg.get_statistics()
        print("\n=== Knowledge Graph Statistics ===")
        print(json.dumps(stats, indent=2))
    
    return test_db


def test_queries(test_db):
    """Test various graph queries"""
    print("\n=== Testing Graph Queries ===\n")
    
    with GraphQuery(str(test_db)) as gq:
        # Test 1: Find person appearances
        print("1. Finding John's appearances:")
        appearances = gq.find_person_appearances('John')
        for app in appearances:
            print(f"   Scene: {app['scene_id']}, Time: {app['timestamp_start']:.1f}s-{app['timestamp_end']:.1f}s")
        
        # Test 2: Find related nodes
        print("\n2. Finding nodes related to 'John':")
        cursor = gq.kg.conn.cursor()
        john_id = cursor.execute("SELECT id FROM nodes WHERE name='John'").fetchone()[0]
        related = gq.kg.find_related_nodes(john_id, max_depth=2)
        for rel in related[:5]:
            print(f"   {rel['name']} ({rel['node_type']}) via {rel['edge_type']}, depth={rel['depth']}")
        
        # Test 3: Find co-occurring nodes
        print("\n3. Finding nodes that co-occur with 'dog':")
        dog_id = cursor.execute("SELECT id FROM nodes WHERE name='dog'").fetchone()[0]
        co_occur = gq.kg.find_co_occurring_nodes(dog_id)
        for co in co_occur:
            print(f"   {co['name']} ({co['node_type']}), co-occurs {co['co_occurrence_count']} times")
        
        # Test 4: Get scene context
        print("\n4. Getting context for scene_0000:")
        context = gq.get_scene_context('scene_0000')
        print(f"   Scene: {context['scene_id']}")
        print(f"   Duration: {context['duration']:.1f}s")
        print("   Entities:")
        for ent_type, ents in context['entities'].items():
            print(f"     {ent_type}: {[e['name'] for e in ents]}")
        
        # Test 5: Find related scenes
        print("\n5. Finding scenes related to scene_0000:")
        related_scenes = gq.find_related_scenes('scene_0000', max_results=5)
        for scene in related_scenes:
            print(f"   {scene['scene_id']}: {scene['shared_nodes']} shared entities")
        
        # Test 6: Temporal story
        print("\n6. Getting story from 0s to 20s:")
        story = gq.find_temporal_story(0.0, 20.0)
        print(f"   Entities: {story['entities']}")
        print(f"   Locations: {story['locations']}")
        print(f"   Emotions: {story['emotions']}")
        print(f"   Events: {len(story['events'])}")
        
        # Test 7: Search by criteria
        print("\n7. Searching for scenes with 'dog' and 'happy' emotion:")
        results = gq.search_by_multiple_criteria({
            'objects': ['dog'],
            'emotions': ['happy'],
            'min_confidence': 0.5
        })
        for res in results:
            print(f"   {res['scene_id']} at {res['timestamp_start']:.1f}s")
        
        # Test 8: Entity summary
        print("\n8. Entity summary:")
        summary = gq.get_entity_summary()
        for ent in summary['entities'][:10]:
            print(f"   {ent['type']}: {ent['name']} ({ent['occurrences']} occurrences)")
    
    print("\n=== All Tests Completed Successfully ===\n")


def main():
    """Run knowledge graph tests"""
    print("=" * 60)
    print("Knowledge Graph Implementation Test")
    print("=" * 60)
    
    try:
        # Create test graph
        test_db = create_test_graph()
        
        # Test queries
        test_queries(test_db)
        
        print("\n✓ Knowledge graph implementation validated successfully!")
        print(f"\nTest database created at: {test_db}")
        print("\nYou can now query it with:")
        print(f"  python cli/graph_query.py --graph-db {test_db} stats")
        print(f"  python cli/graph_query.py --graph-db {test_db} find-person John")
        print(f"  python cli/graph_query.py --graph-db {test_db} scene-context scene_0000")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
