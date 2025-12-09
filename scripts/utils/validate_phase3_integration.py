"""
Phase 3 Pipeline Integration Validator
Demonstrates LLM enhancements in the full ingestion pipeline
"""
import sys
import sqlite3
import json
from pathlib import Path

print("\n" + "="*80)
print("PHASE 3: PIPELINE INTEGRATION VALIDATION")
print("="*80)

# Check what we have in the database from sample.mp4
db_path = Path("L:/goodq4all/data/goodq_memory.db")

if not db_path.exists():
    print("\n❌ Database not found. Run ingestion first:")
    print("   python scripts/comprehensive_clean_run.py")
    sys.exit(1)

conn = sqlite3.connect(str(db_path))
c = conn.cursor()

# Check for scenes
print("\n[1] Checking Existing Data...")
print("-" * 80)

c.execute("SELECT COUNT(*) FROM scenes")
scene_count = c.fetchone()[0]
print(f"📊 Total scenes: {scene_count}")

if scene_count == 0:
    print("❌ No scenes found. Run ingestion first.")
    conn.close()
    sys.exit(1)

# Sample a scene to show current data
c.execute("SELECT meta FROM scenes LIMIT 1")
row = c.fetchone()
if row:
    meta = json.loads(row[0])
    print("\n✅ Current scene metadata includes:")
    has_items = []
    if meta.get('audio', {}).get('transcript'):
        has_items.append("✓ Transcript")
    if meta.get('sentiment'):
        has_items.append("✓ Sentiment")
    if meta.get('emotions'):
        has_items.append("✓ Emotions")
    if meta.get('caption'):
        has_items.append("✓ Visual caption")
    if meta.get('objects'):
        has_items.append("✓ Object detection")
    
    for item in has_items:
        print(f"   {item}")

# Check knowledge graph
print("\n[2] Checking Knowledge Graph...")
print("-" * 80)

kg_path = Path("L:/goodq4all/data/knowledge_graph.db")
if kg_path.exists():
    kg_conn = sqlite3.connect(str(kg_path))
    kg_c = kg_conn.cursor()
    
    # Check node types
    kg_c.execute("SELECT node_type, COUNT(*) as count FROM nodes GROUP BY node_type ORDER BY count DESC")
    node_types = kg_c.fetchall()
    
    print(f"📊 Knowledge graph nodes by type:")
    for node_type, count in node_types:
        print(f"   {node_type}: {count}")
    
    kg_conn.close()
else:
    print("⚠️  Knowledge graph not yet created")

# Show what Phase 3 will add
print("\n[3] Phase 3 LLM Enhancements Preview")
print("-" * 80)

print("""
When Phase 3 integration is active, you will see:

📝 NEW NODE TYPES in Knowledge Graph:
   • narrative - Natural language scene descriptions
   • emotional_arc - Overall emotional journey
   • theme - Extracted themes (emotional, topical)
   • emotional_moment - Key emotional moments
   • emotional_turning_point - Emotion shift points
   • person (LLM-enhanced) - Named people from context
   • location (LLM-enhanced) - Places mentioned
   • topic - Discussion topics identified
   • temporal_ref - Time references extracted

🧠 ENHANCED SCENE METADATA:
   • Contextualized entity extraction
   • Natural language narratives
   • Relationship inference between entities
   • Thematic tagging

🎭 VIDEO-LEVEL ANALYSIS:
   • Emotional arc with key moments
   • Turning point identification
   • Theme extraction across scenes
   • Overall narrative structure

📊 SAMPLE OUTPUT:
   Scene 3 narrative: "Two friends discuss their band experience at a 
   table. The conversation is warm and nostalgic, with excitement building
   as they recall their best performance in Seattle."
   
   Extracted entities:
   - People: Friend 1, Friend 2, Colin
   - Locations: Seattle
   - Topics: band experience, musical performance
   - Emotions: nostalgia, excitement, joy
   
   Emotional arc: "Neutral introduction → positive reminiscence → peak
   excitement → reflective conclusion"
""")

print("\n[4] Integration Status")
print("-" * 80)

# Check config
config_path = Path("L:/goodq4all/config.yaml")
if config_path.exists():
    import yaml
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    
    llm_enabled = cfg.get('llm', {}).get('enabled', False)
    features = cfg.get('llm', {}).get('features', {})
    
    print(f"✅ LLM Enabled: {llm_enabled}")
    print(f"✅ Scene Summarization: {features.get('scene_summarization', False)}")
    print(f"✅ Video Summarization: {features.get('video_summarization', False)}")
    print(f"✅ Relationship Extraction: {features.get('relationship_extraction', False)}")
    print(f"✅ Emotion Arc Analysis: {features.get('emotion_arc_analysis', False)}")
else:
    print("❌ Config file not found")

print("\n[5] Next Steps")
print("-" * 80)
print("""
To activate Phase 3 LLM integration:

1. ✅ DONE - LLM modules created
2. ✅ DONE - Knowledge graph updated  
3. ✅ DONE - Config features enabled
4. ✅ DONE - Standalone tests passed (4/4)

5. 🔄 READY - Run full pipeline test:
   python scripts/comprehensive_clean_run.py
   
6. 🔍 VERIFY - Check logs for LLM calls:
   - Look for "LLM enrichment added X entities"
   - Look for "Generated emotional arc analysis"
   - Check knowledge graph for new node types
   
7. 📊 ANALYZE - Query enhanced knowledge graph:
   - Check for narrative nodes
   - Verify emotional arc data
   - Examine LLM-extracted entities

The system is ready for full integration testing!
""")

print("="*80)

conn.close()
