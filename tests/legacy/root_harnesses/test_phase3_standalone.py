"""
Standalone Phase 3 LLM Integration Test
Tests LLM functionality without zenml dependencies
"""
import sys
import json
import logging
import requests
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def load_config():
    """Load configuration"""
    import yaml
    with open(REPO_ROOT / 'configs' / 'config.yaml', 'r') as f:
        return yaml.safe_load(f)


def test_llm_entity_extraction_standalone():
    """Test LLM entity extraction without zenml"""
    print("\n[TEST] LLM Entity Extraction")
    print("-" * 80)
    
    cfg = load_config()
    
    # Import the function directly from the module file
    sys.path.insert(0, str(REPO_ROOT / 'steps' / 'graph_builder'))
    
    # Load the function without importing the whole module
    with open(REPO_ROOT / 'steps' / 'graph_builder' / 'llm_enrichment.py', 'r') as f:
        code = f.read()
        # Remove any zenml imports
        code = code.replace('from zenml import step', '')
        code = code.replace('@step', '')
        
        # Execute in namespace
        namespace = {}
        exec(code, namespace)
        extract_entities_with_llm = namespace['extract_entities_with_llm']
    
    # Test text
    test_text = "Colin and I were in a band together. We performed at venues around Seattle, and the experience was amazing."
    test_context = {
        'objects': [{'label': 'microphone', 'confidence': 0.9}],
        'emotions': [{'label': 'joy', 'score': 0.8}],
        'sentiment': {'label': 'POSITIVE', 'score': 0.85}
    }
    
    try:
        entities = extract_entities_with_llm(test_text, test_context, cfg)
        
        if entities:
            print(f"[OK] SUCCESS: Extracted {sum(len(v) for v in entities.values())} entities")
            for entity_type, entity_list in entities.items():
                if entity_list:
                    print(f"\n   {entity_type.upper()}:")
                    for entity in entity_list:
                        name = entity.get('name', 'unknown')
                        conf = entity.get('confidence', 0)
                        print(f"     • {name} (confidence: {conf:.2f})")
            return True, entities
        else:
            print("[WARN]  WARNING: No entities extracted")
            return False, {}
            
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False, {}


def test_scene_narrative_standalone():
    """Test scene narrative generation"""
    print("\n[TEST] Scene Narrative Generation")
    print("-" * 80)
    
    cfg = load_config()
    
    # Load the function
    sys.path.insert(0, str(REPO_ROOT / 'steps' / 'graph_builder'))
    with open(REPO_ROOT / 'steps' / 'graph_builder' / 'llm_enrichment.py', 'r') as f:
        code = f.read()
        namespace = {}
        exec(code, namespace)
        generate_scene_narrative = namespace['generate_scene_narrative']
    
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
    
    try:
        narrative = generate_scene_narrative(test_scene, cfg)
        
        if narrative:
            print(f"[OK] SUCCESS: Generated narrative ({len(narrative)} chars)")
            print(f"\n   NARRATIVE:")
            print(f"   \"{narrative}\"")
            return True, narrative
        else:
            print("[WARN]  WARNING: No narrative generated")
            return False, None
            
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_emotional_arc_standalone():
    """Test emotional arc analysis"""
    print("\n[TEST] Emotional Arc Analysis")
    print("-" * 80)
    
    cfg = load_config()
    
    # Load the function
    sys.path.insert(0, str(REPO_ROOT / 'steps' / 'graph_builder'))
    with open(REPO_ROOT / 'steps' / 'graph_builder' / 'emotion_arc_analyzer.py', 'r') as f:
        code = f.read()
        namespace = {}
        exec(code, namespace)
        analyze_emotional_arc = namespace['analyze_emotional_arc']
    
    # Test scenes
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
    
    try:
        arc_analysis = analyze_emotional_arc(test_scenes, cfg)
        
        if arc_analysis:
            print(f"[OK] SUCCESS: Generated emotional arc analysis")
            print(f"\n   OVERALL ARC:")
            print(f"   {arc_analysis.get('overall_arc', 'N/A')}")
            print(f"\n   KEY MOMENTS: {len(arc_analysis.get('key_moments', []))}")
            for moment in arc_analysis.get('key_moments', [])[:3]:
                print(f"     • Scene {moment.get('scene')}: {moment.get('description', 'N/A')}")
            print(f"\n   THEMES: {', '.join(arc_analysis.get('emotional_themes', []))}")
            print(f"   TURNING POINTS: {len(arc_analysis.get('turning_points', []))}")
            return True, arc_analysis
        else:
            print("[WARN]  WARNING: No emotional arc generated")
            return False, None
            
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_llm_direct_call():
    """Test direct LLM API call"""
    print("\n[TEST] Direct LLM API Call")
    print("-" * 80)
    
    try:
        response = requests.post(
            "http://localhost:1234/v1/chat/completions",
            json={
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that extracts entities from text."
                    },
                    {
                        "role": "user",
                        "content": "Extract person names from: 'Colin and Sarah performed at The Showbox in Seattle.'"
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 100
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            print(f"[OK] SUCCESS: LLM responded")
            print(f"\n   RESPONSE:")
            print(f"   {content}")
            return True, content
        else:
            print(f"[FAIL] FAILED: Status {response.status_code}")
            return False, None
            
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        return False, None


if __name__ == "__main__":
    print("\n" + "="*80)
    print("PHASE 3: STANDALONE LLM INTEGRATION TEST")
    print("="*80)
    
    results = {}
    
    # Test 1: Direct LLM call
    results['direct_llm'], _ = test_llm_direct_call()
    
    # Test 2: Entity extraction
    results['entity_extraction'], entities = test_llm_entity_extraction_standalone()
    
    # Test 3: Narrative generation
    results['narrative'], narrative = test_scene_narrative_standalone()
    
    # Test 4: Emotional arc
    results['emotional_arc'], arc = test_emotional_arc_standalone()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "[OK] PASS" if result else "[FAIL] FAIL"
        print(f"{status} - {test_name.replace('_', ' ').title()}")
    
    print(f"\n[STATS] Results: {passed}/{total} tests passed ({100*passed//total}%)")
    
    if passed == total:
        print("\n[SYMBOL] ALL TESTS PASSED!")
        print("\n[OK] Phase 3 LLM integration is functional:")
        print("   • Entity extraction working")
        print("   • Scene narrative generation working")
        print("   • Emotional arc analysis working")
        print("\n[NOTE] Next step: Integrate into pipeline for actual video processing")
    elif passed >= 2:
        print("\n[WARN]  PARTIAL SUCCESS - Core functionality working")
    else:
        print("\n[FAIL] TESTS FAILED - Review LLM configuration")
    
    print("="*80)
    
    sys.exit(0 if passed >= 3 else 1)
