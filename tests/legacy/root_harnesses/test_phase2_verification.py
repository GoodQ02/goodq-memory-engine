"""
Phase 2 Verification Test
Confirms all Phase 2 features are working correctly
"""
import sqlite3
import json
from pathlib import Path

def test_phase2_integration():
    """Verify Phase 2 enhancements in database"""
    
    print("="*80)
    print("PHASE 2 INTEGRATION VERIFICATION")
    print("="*80)
    
    db_path = "L:/_DATA/GoodQ_Data/memory.db"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Test 1: Check scenes have context
    print("\n[TEST 1] Context Analysis")
    c.execute("SELECT meta FROM scenes")
    scenes = [json.loads(row[0]) for row in c.fetchall()]
    
    scenes_with_context = sum(1 for s in scenes if s.get('context_analyzed'))
    print(f"  [SYMBOL] Scenes with context: {scenes_with_context}/{len(scenes)}")
    
    if scenes_with_context > 0:
        sample = next(s for s in scenes if s.get('context_analyzed'))
        ctx = sample.get('context', {})
        print(f"  [SYMBOL] Sample narrative: {ctx.get('narrative_summary', 'N/A')[:60]}...")
        print(f"  [SYMBOL] Sample tags: {ctx.get('context_tags', [])}")
    
    # Test 2: Check intelligent tagging
    print("\n[TEST 2] Intelligent Tagging")
    scenes_with_llm_tags = sum(1 for s in scenes if s.get('llm_tags_applied'))
    llm_used = sum(1 for s in scenes if s.get('tagging_method') == 'llm')
    
    print(f"  [SYMBOL] Scenes with LLM tags: {scenes_with_llm_tags}/{len(scenes)}")
    print(f"  [SYMBOL] LLM tagging used: {llm_used}/{scenes_with_llm_tags}")
    
    if scenes_with_llm_tags > 0:
        sample = next(s for s in scenes if s.get('llm_tags_applied'))
        print(f"  [SYMBOL] Sample tags: {sample.get('tags', [])}")
        print(f"  [SYMBOL] Sample themes: {sample.get('themes', [])}")
    
    # Test 3: Check emotional arc
    print("\n[TEST 3] Emotional Arc Analysis")
    c.execute("SELECT content FROM summaries WHERE category='emotional_arc'")
    arc_row = c.fetchone()
    
    if arc_row:
        arc_data = json.loads(arc_row[0])
        arc = arc_data.get('arc_data', {})
        print(f"  [SYMBOL] Overall arc: {arc.get('overall_arc', 'N/A')}")
        print(f"  [SYMBOL] Dominant emotions: {arc.get('dominant_emotions', [])}")
        print(f"  [SYMBOL] Transitions: {len(arc.get('key_transitions', []))}")
    else:
        print("  [SYMBOL] No emotional arc found")
    
    # Test 4: Check relationship mapping
    print("\n[TEST 4] Relationship Mapping")
    c.execute("SELECT content FROM summaries WHERE category='relationship_map'")
    rel_row = c.fetchone()
    
    if rel_row:
        rel_data = json.loads(rel_row[0])
        rel_map = rel_data.get('relationship_data', {})
        print(f"  [SYMBOL] Total entities: {rel_map.get('total_entities', 0)}")
        print(f"  [SYMBOL] Total interactions: {rel_map.get('total_interactions', 0)}")
        print(f"  [SYMBOL] Interaction types: {list(rel_map.get('interaction_patterns', {}).keys())}")
    else:
        print("  [SYMBOL] No relationship map found")
    
    # Test 5: Verify relationships in context
    print("\n[TEST 5] Scene-Level Relationships")
    scenes_with_rels = sum(1 for s in scenes if s.get('context', {}).get('relationships'))
    total_rels = sum(len(s.get('context', {}).get('relationships', [])) for s in scenes)
    
    print(f"  [SYMBOL] Scenes with relationships: {scenes_with_rels}/{len(scenes)}")
    print(f"  [SYMBOL] Total relationships: {total_rels}")
    
    conn.close()
    
    # Summary
    print("\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    
    all_tests_pass = all([
        scenes_with_context == len(scenes),
        scenes_with_llm_tags == len(scenes),
        llm_used == scenes_with_llm_tags,
        arc_row is not None,
        rel_row is not None,
        total_rels > 0
    ])
    
    if all_tests_pass:
        print("[OK] ALL TESTS PASSED - Phase 2 fully operational")
    else:
        print("[WARN]  Some tests failed - review output above")
    
    return all_tests_pass


if __name__ == "__main__":
    success = test_phase2_integration()
    exit(0 if success else 1)
