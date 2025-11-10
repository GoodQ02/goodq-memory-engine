"""
Phase 3: LLM Integration Test
Tests metadata enrichment, knowledge graph enhancement, and emotional arc analysis
"""
import sys
import json
import sqlite3
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_llm_availability():
    """Test if LLM is available"""
    import requests
    
    print("\n" + "="*80)
    print("PHASE 3: LLM INTEGRATION TEST")
    print("="*80)
    
    print("\n[1/5] Testing LLM Availability...")
    try:
        response = requests.post(
            "http://localhost:1234/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 10
            },
            timeout=5
        )
        if response.status_code == 200:
            print("✅ LLM is available and responding")
            return True
        else:
            print(f"❌ LLM returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ LLM not available: {e}")
        return False


def test_llm_entity_extraction():
    """Test LLM entity extraction"""
    print("\n[2/5] Testing LLM Entity Extraction...")
    
    try:
        from steps.graph_builder.llm_enrichment import extract_entities_with_llm
        import yaml
        
        # Load config
        with open('config.yaml', 'r') as f:
            cfg = yaml.safe_load(f)
        
        # Test text
        test_text = "Colin and I were in a band together. We performed at venues around Seattle, and the experience was amazing."
        test_context = {
            'objects': [{'label': 'microphone', 'confidence': 0.9}],
            'emotions': [{'label': 'joy', 'score': 0.8}],
            'sentiment': {'label': 'POSITIVE', 'score': 0.85}
        }
        
        entities = extract_entities_with_llm(test_text, test_context, cfg)
        
        if entities:
            print(f"✅ Extracted {sum(len(v) for v in entities.values())} entities")
            for entity_type, entity_list in entities.items():
                if entity_list:
                    print(f"   - {entity_type}: {len(entity_list)} found")
                    for entity in entity_list[:2]:  # Show first 2
                        print(f"     • {entity.get('name', 'unknown')} (confidence: {entity.get('confidence', 0):.2f})")
            return True
        else:
            print("⚠️  No entities extracted (LLM may be processing)")
            return False
            
    except Exception as e:
        print(f"❌ Entity extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_scene_narrative_generation():
    """Test scene narrative generation"""
    print("\n[3/5] Testing Scene Narrative Generation...")
    
    try:
        from steps.graph_builder.llm_enrichment import generate_scene_narrative
        import yaml
        
        # Load config
        with open('config.yaml', 'r') as f:
            cfg = yaml.safe_load(f)
        
        # Test scene data
        test_scene = {
            'start_time': 10.5,
            'end_time': 25.3,
            'objects': [
                {'label': 'person', 'confidence': 0.95},
                {'label': 'microphone', 'confidence': 0.88}
            ],
            'caption': 'Two people sitting at a table having a conversation',
            'audio': {
                'transcript': 'So tell me about your band. What kind of music did you play?',
                'speakers': [{'speaker_id': 'SPEAKER_00'}, {'speaker_id': 'SPEAKER_01'}]
            },
            'sentiment': {'label': 'POSITIVE', 'score': 0.7},
            'emotions': [{'label': 'joy', 'score': 0.6}]
        }
        
        narrative = generate_scene_narrative(test_scene, cfg)
        
        if narrative:
            print(f"✅ Generated narrative ({len(narrative)} chars):")
            print(f"   \"{narrative}\"")
            return True
        else:
            print("⚠️  No narrative generated")
            return False
            
    except Exception as e:
        print(f"❌ Narrative generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_emotional_arc_analysis():
    """Test emotional arc analysis"""
    print("\n[4/5] Testing Emotional Arc Analysis...")
    
    try:
        from steps.graph_builder.emotion_arc_analyzer import analyze_emotional_arc
        import yaml
        
        # Load config
        with open('config.yaml', 'r') as f:
            cfg = yaml.safe_load(f)
        
        # Test scenes with emotional progression
        test_scenes = [
            {
                'start_time': 0, 'end_time': 10,
                'sentiment': {'label': 'NEUTRAL', 'score': 0.5},
                'emotions': [{'label': 'neutral', 'score': 0.6}],
                'audio': {'transcript': 'Welcome to the podcast. Thanks for having us.'}
            },
            {
                'start_time': 10, 'end_time': 20,
                'sentiment': {'label': 'POSITIVE', 'score': 0.7},
                'emotions': [{'label': 'joy', 'score': 0.7}],
                'audio': {'transcript': 'Yeah it was an amazing experience being in the band.'}
            },
            {
                'start_time': 20, 'end_time': 30,
                'sentiment': {'label': 'POSITIVE', 'score': 0.85},
                'emotions': [{'label': 'excitement', 'score': 0.8}],
                'audio': {'transcript': 'The best show we ever played was incredible!'}
            },
            {
                'start_time': 30, 'end_time': 40,
                'sentiment': {'label': 'NEUTRAL', 'score': 0.55},
                'emotions': [{'label': 'neutral', 'score': 0.6}],
                'audio': {'transcript': 'Eventually we all moved on to different things.'}
            }
        ]
        
        arc_analysis = analyze_emotional_arc(test_scenes, cfg)
        
        if arc_analysis:
            print(f"✅ Generated emotional arc analysis:")
            print(f"   Overall Arc: {arc_analysis.get('overall_arc', 'N/A')[:100]}...")
            print(f"   Key Moments: {len(arc_analysis.get('key_moments', []))}")
            print(f"   Themes: {', '.join(arc_analysis.get('emotional_themes', []))}")
            print(f"   Turning Points: {len(arc_analysis.get('turning_points', []))}")
            return True
        else:
            print("⚠️  No emotional arc generated")
            return False
            
    except Exception as e:
        print(f"❌ Emotional arc analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_knowledge_graph_integration():
    """Test integration with knowledge graph"""
    print("\n[5/5] Testing Knowledge Graph Integration...")
    
    try:
        from lib.knowledge_graph import KnowledgeGraph
        from steps.graph_builder.emotion_arc_analyzer import add_emotional_arc_to_kg
        import yaml
        import tempfile
        
        # Load config
        with open('config.yaml', 'r') as f:
            cfg = yaml.safe_load(f)
        
        # Create temporary test database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            test_db_path = tmp.name
        
        # Test emotional arc data
        test_arc = {
            'overall_arc': 'The conversation shows a positive emotional journey from neutral introduction to excited reminiscence.',
            'key_moments': [
                {
                    'scene': 2,
                    'time': '20.0s',
                    'description': 'Peak excitement when discussing best performance',
                    'significance': 'Highlights the passion for music'
                }
            ],
            'emotional_themes': ['nostalgia', 'achievement', 'friendship'],
            'turning_points': [
                {
                    'scene': 2,
                    'from_emotion': 'joy',
                    'to_emotion': 'excitement',
                    'trigger': 'Remembering the best show'
                }
            ],
            'conclusion': 'Overall positive reflection on shared musical experience'
        }
        
        with KnowledgeGraph(test_db_path) as kg:
            # Add test video media node
            video_id = kg.add_media_node(
                media_type='video',
                media_path='test_sample.mp4',
                timestamp_start=0.0,
                timestamp_end=40.0
            )
            
            # Add emotional arc
            add_emotional_arc_to_kg(kg, test_arc, video_id, cfg)
            
            # Verify nodes were added
            cursor = kg.conn.cursor()
            
            # Check for emotional arc node
            cursor.execute("SELECT COUNT(*) FROM nodes WHERE node_type = 'emotional_arc'")
            arc_count = cursor.fetchone()[0]
            
            # Check for theme nodes
            cursor.execute("SELECT COUNT(*) FROM nodes WHERE node_type = 'theme'")
            theme_count = cursor.fetchone()[0]
            
            # Check for key moment nodes
            cursor.execute("SELECT COUNT(*) FROM nodes WHERE node_type = 'emotional_moment'")
            moment_count = cursor.fetchone()[0]
            
            print(f"✅ Knowledge graph integration successful:")
            print(f"   - Emotional arc nodes: {arc_count}")
            print(f"   - Theme nodes: {theme_count}")
            print(f"   - Key moment nodes: {moment_count}")
            
            # Cleanup
            import os
            os.unlink(test_db_path)
            
            return arc_count > 0 and theme_count > 0
            
    except Exception as e:
        print(f"❌ Knowledge graph integration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_sample_database():
    """Check if sample.mp4 has been processed"""
    print("\n" + "="*80)
    print("SAMPLE.MP4 DATABASE CHECK")
    print("="*80)
    
    db_path = Path("L:/goodq4all/data/goodq_memory.db")
    if not db_path.exists():
        print("❌ Memory database not found")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        
        # Check for scenes
        c.execute("SELECT COUNT(*) FROM scenes")
        scene_count = c.fetchone()[0]
        print(f"\n📊 Scenes in database: {scene_count}")
        
        if scene_count > 0:
            # Check if scenes have LLM-enhanced data
            c.execute("""
                SELECT meta FROM scenes LIMIT 1
            """)
            row = c.fetchone()
            if row:
                meta = json.loads(row[0])
                print(f"✅ Sample scene data available")
                
                # Check for various data types
                has_transcript = bool(meta.get('audio', {}).get('transcript'))
                has_sentiment = bool(meta.get('sentiment'))
                has_emotions = bool(meta.get('emotions'))
                has_caption = bool(meta.get('caption'))
                
                print(f"   - Transcript: {'✅' if has_transcript else '❌'}")
                print(f"   - Sentiment: {'✅' if has_sentiment else '❌'}")
                print(f"   - Emotions: {'✅' if has_emotions else '❌'}")
                print(f"   - Caption: {'✅' if has_caption else '❌'}")
        
        conn.close()
        return scene_count > 0
        
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False


if __name__ == "__main__":
    print("\n🚀 Starting Phase 3 LLM Integration Tests\n")
    
    results = {
        'llm_availability': test_llm_availability(),
        'entity_extraction': test_llm_entity_extraction(),
        'narrative_generation': test_scene_narrative_generation(),
        'emotional_arc': test_emotional_arc_analysis(),
        'kg_integration': test_knowledge_graph_integration()
    }
    
    # Check existing data
    has_sample_data = check_sample_database()
    
    # Summary
    print("\n" + "="*80)
    print("PHASE 3 TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name.replace('_', ' ').title()}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if has_sample_data:
        print("\n✅ Sample data available for LLM enhancement")
    else:
        print("\n⚠️  No sample data found - run ingestion first")
    
    print("\n" + "="*80)
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - Phase 3 LLM Integration Complete!")
    elif passed >= total * 0.6:
        print("⚠️  PARTIAL SUCCESS - Some tests passed, review failures above")
    else:
        print("❌ TESTS FAILED - Review errors and ensure LLM is running")
    
    print("="*80)
    
    sys.exit(0 if passed == total else 1)
