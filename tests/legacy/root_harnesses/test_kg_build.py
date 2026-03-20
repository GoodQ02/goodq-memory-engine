#!/usr/bin/env python3
"""
Test knowledge graph building with sample.mp4 data from memory.db
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import json
import sqlite3
from lib.knowledge_graph import KnowledgeGraph

# Load scene data from memory.db
db_path = Path("data/memory.db")
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get all scenes for sample.mp4
scenes = cursor.execute("""
    SELECT * FROM scenes 
    ORDER BY start
""").fetchall()

print(f"Found {len(scenes)} scenes in memory.db\n")

# Build sample result structure
results = []
video_result = {
    'video_path': 'samples/ingestion/sample.mp4',
    'scenes': []
}

for scene in scenes:
    scene_dict = dict(scene)
    meta = json.loads(scene_dict['meta']) if scene_dict['meta'] else {}
    
    scene_entry = {
        'index': meta.get('index', 0),
        'scene_id': scene_dict['id'],
        'start': scene_dict['start'],
        'end': scene_dict['end'],
        'confidence': meta.get('confidence', 0.5)
    }
    
    # Build keyframe dict from nested keyframe + top-level face data
    keyframe_data = meta.get('keyframe', {}).copy() if isinstance(meta.get('keyframe'), dict) else {}
    
    # Add top-level face data to keyframe
    if 'faces' in meta and meta['faces']:
        keyframe_data['faces'] = meta['faces']
    
    # Rename objects to detections for KG processor
    if 'objects' in keyframe_data:
        keyframe_data['detections'] = keyframe_data.pop('objects')
    
    if keyframe_data:
        scene_entry['keyframe'] = keyframe_data
    
    # Build audio dict from nested audio + top-level speaker data
    audio_data = meta.get('audio', {}).copy() if isinstance(meta.get('audio'), dict) else {}
    
    # Add top-level speaker_transcript to audio
    if 'speaker_transcript' in meta and meta['speaker_transcript']:
        audio_data['speaker_transcript'] = meta['speaker_transcript']
    
    # Add top-level speakers if not in audio
    if 'speakers' not in audio_data and 'speakers' in meta:
        audio_data['speakers'] = meta['speakers']
    
    if audio_data:
        scene_entry['audio'] = audio_data
    
    video_result['scenes'].append(scene_entry)

results.append(video_result)
conn.close()

print(f"Prepared {len(results[0]['scenes'])} scenes for knowledge graph building\n")

# Now build knowledge graph
kg_path = Path("data/knowledge_graph.db")
print(f"Building knowledge graph at {kg_path}...")

try:
    from cli.run_ingestion import _build_knowledge_graph_from_results, _process_keyframe_entities, _process_audio_entities, _build_kg_relationships
    
    cfg = {'data_dir': 'data'}
    
    print("\nCalling _build_knowledge_graph_from_results...")
    kg_result = _build_knowledge_graph_from_results(results, cfg)
    
    if kg_result:
        print(f"\nKnowledge Graph Result:")
        print(f"  Status: {kg_result.get('status')}")
        if kg_result.get('statistics'):
            print(f"  Statistics: {json.dumps(kg_result['statistics'], indent=4)}")
        if kg_result.get('error'):
            print(f"  Error: {kg_result['error']}")
    else:
        print("\nNo result returned from knowledge graph building")
        
    # Check what was actually written to the database
    print("\n" + "="*60)
    print("Checking knowledge graph database content...")
    
    conn = sqlite3.connect(str(kg_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    nodes_count = cursor.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    edges_count = cursor.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    media_count = cursor.execute("SELECT COUNT(*) FROM media_nodes").fetchone()[0]
    node_media_count = cursor.execute("SELECT COUNT(*) FROM node_media").fetchone()[0]
    
    print(f"\nDatabase Contents:")
    print(f"  Nodes: {nodes_count}")
    print(f"  Edges: {edges_count}")
    print(f"  Media nodes: {media_count}")
    print(f"  Node-media links: {node_media_count}")
    
    if nodes_count > 0:
        print("\nNode types:")
        node_types = cursor.execute(
            "SELECT node_type, COUNT(*) as count FROM nodes GROUP BY node_type"
        ).fetchall()
        for row in node_types:
            print(f"  {row['node_type']}: {row['count']}")
    
    if nodes_count > 0:
        print("\nSample nodes:")
        sample_nodes = cursor.execute("SELECT * FROM nodes LIMIT 10").fetchall()
        for node in sample_nodes:
            print(f"  {node['node_type']}: {node['name']} (seen {node['occurrence_count']} times)")
    
    conn.close()
    
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
