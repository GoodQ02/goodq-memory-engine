"""
Phase 2: Comprehensive Embedding and Knowledge Graph Analysis
Identifies all missing/broken embeddings and knowledge graph links for sample.mp4
"""
import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import os

def analyze_sample_mp4_processing():
    """Analyze the complete processing state of sample.mp4"""
    
    print("="*80)
    print("PHASE 2: EMBEDDING & KNOWLEDGE GRAPH ANALYSIS FOR sample.mp4")
    print("="*80)
    
    # Paths
    data_dir = Path("L:/goodq4all/data")
    memory_db = data_dir / "memory.db"
    kg_db = data_dir / "knowledge_graph.db"
    processing_dir = data_dir / "processing"
    faiss_dir = data_dir / "faiss_indices"
    
    issues = []
    
    # 1. Check scene JSON files
    print("\n1. CHECKING SCENE JSON FILES")
    print("-" * 80)
    
    sample_dirs = list(processing_dir.glob("*sample*"))
    if not sample_dirs:
        issues.append("CRITICAL: No processing directory found for sample.mp4")
        print("ERROR: No sample.mp4 processing directory found!")
    else:
        for sample_dir in sample_dirs:
            print(f"Found: {sample_dir}")
            
            # Check for scene JSONs
            scene_files = list(sample_dir.glob("scene_*.json"))
            print(f"  Scene JSON files: {len(scene_files)}")
            
            if len(scene_files) == 0:
                issues.append(f"No scene JSON files in {sample_dir}")
            else:
                # Analyze a sample scene
                for scene_file in scene_files[:3]:  # Check first 3
                    print(f"\n  Analyzing: {scene_file.name}")
                    try:
                        with open(scene_file) as f:
                            scene_data = json.load(f)
                        
                        # Check for embedding metadata
                        clip_meta = scene_data.get('clip_meta', {})
                        dino_meta = scene_data.get('dino_meta', {})
                        embedding_meta = scene_data.get('embedding_meta', {})
                        clap_meta = scene_data.get('clap_meta', {})
                        
                        print(f"    CLIP: {clip_meta.get('status', 'MISSING')}")
                        print(f"    DINO: {dino_meta.get('status', 'MISSING')}")
                        print(f"    Text Embedding: {embedding_meta.get('status', 'MISSING')}")
                        print(f"    CLAP Audio: {clap_meta.get('status', 'MISSING')}")
                        
                        # Check for data fields
                        has_caption = bool(scene_data.get('caption'))
                        has_ocr = bool(scene_data.get('ocr_text'))
                        has_transcript = bool(scene_data.get('transcript'))
                        has_objects = bool(scene_data.get('objects'))
                        has_sentiment = 'sentiment' in scene_data
                        has_emotions = 'emotions' in scene_data
                        
                        print(f"    Caption: {'✓' if has_caption else '✗'}")
                        print(f"    OCR: {'✓' if has_ocr else '✗'}")
                        print(f"    Transcript: {'✓' if has_transcript else '✗'}")
                        print(f"    Objects: {'✓' if has_objects else '✗'}")
                        print(f"    Sentiment: {'✓' if has_sentiment else '✗'}")
                        print(f"    Emotions: {'✓' if has_emotions else '✗'}")
                        
                        # Check embedding status issues
                        for emb_type, meta in [('CLIP', clip_meta), ('DINO', dino_meta), 
                                                ('TextEmbed', embedding_meta), ('CLAP', clap_meta)]:
                            status = meta.get('status')
                            if status and status != 'ok':
                                issues.append(f"{scene_file.name}: {emb_type} status={status}")
                        
                    except Exception as e:
                        print(f"    ERROR reading {scene_file.name}: {e}")
                        issues.append(f"Failed to read {scene_file.name}: {e}")
    
    # 2. Check FAISS indices
    print(f"\n2. CHECKING FAISS INDICES")
    print("-" * 80)
    
    expected_indices = {
        'text': 'faiss_text_index.bin',
        'clip': 'faiss_clip_index.bin',
        'dino': 'faiss_dino_index.bin',
        'audio': 'faiss_audio_index.bin'
    }
    
    for idx_type, idx_file in expected_indices.items():
        idx_path = faiss_dir / idx_type / idx_file
        if idx_path.exists():
            size_mb = idx_path.stat().st_size / 1024 / 1024
            print(f"  {idx_type:10s}: ✓ ({size_mb:.2f} MB) - {idx_path}")
        else:
            print(f"  {idx_type:10s}: ✗ MISSING - {idx_path}")
            issues.append(f"Missing FAISS index: {idx_path}")
    
    # 3. Check memory.db embeddings
    print(f"\n3. CHECKING MEMORY.DB EMBEDDINGS")
    print("-" * 80)
    
    try:
        conn = sqlite3.connect(str(memory_db))
        cur = conn.cursor()
        
        # Count embeddings by modality
        cur.execute("SELECT modality, COUNT(*) FROM embeddings GROUP BY modality")
        embeddings_by_modality = dict(cur.fetchall())
        
        print("Embeddings by modality:")
        for modality, count in embeddings_by_modality.items():
            print(f"  {modality or 'NULL':15s}: {count}")
        
        # Expected: 16 scenes * 3 (image CLIP, text, audio) = 48+ embeddings minimum
        total = sum(embeddings_by_modality.values())
        print(f"\nTotal embeddings: {total}")
        
        if total < 48:
            issues.append(f"Insufficient embeddings: expected 48+, found {total}")
        
        # Check for scene_id linkage
        cur.execute("SELECT COUNT(*) FROM embeddings WHERE scene_id IS NOT NULL")
        with_scene_id = cur.fetchone()[0]
        print(f"Embeddings with scene_id: {with_scene_id}")
        
        if with_scene_id == 0:
            issues.append("CRITICAL: No embeddings linked to scene_ids")
        
        # Check for sentiment/emotion data
        cur.execute("SELECT COUNT(*) FROM embeddings WHERE sentiment_label IS NOT NULL")
        with_sentiment = cur.fetchone()[0]
        print(f"Embeddings with sentiment: {with_sentiment}")
        
        cur.execute("SELECT COUNT(*) FROM embeddings WHERE emotions_json IS NOT NULL")
        with_emotions = cur.fetchone()[0]
        print(f"Embeddings with emotions: {with_emotions}")
        
        conn.close()
    except Exception as e:
        print(f"ERROR checking memory.db: {e}")
        issues.append(f"Failed to check memory.db: {e}")
    
    # 4. Check knowledge graph
    print(f"\n4. CHECKING KNOWLEDGE GRAPH")
    print("-" * 80)
    
    try:
        conn = sqlite3.connect(str(kg_db))
        cur = conn.cursor()
        
        # Node counts
        cur.execute("SELECT node_type, COUNT(*) FROM nodes GROUP BY node_type")
        nodes_by_type = dict(cur.fetchall())
        
        print("Nodes by type:")
        for node_type, count in nodes_by_type.items():
            print(f"  {node_type:15s}: {count}")
        
        total_nodes = sum(nodes_by_type.values())
        print(f"\nTotal nodes: {total_nodes}")
        
        # Expected: people, objects, concepts, emotions, speakers, etc.
        expected_types = ['person', 'object', 'concept', 'emotion', 'speaker', 'tag']
        missing_types = [t for t in expected_types if t not in nodes_by_type]
        if missing_types:
            issues.append(f"Missing node types in KG: {missing_types}")
        
        # Edge counts
        cur.execute("SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type")
        edges_by_type = dict(cur.fetchall())
        
        print("\nEdges by type:")
        for edge_type, count in edges_by_type.items():
            print(f"  {edge_type:20s}: {count}")
        
        total_edges = sum(edges_by_type.values())
        print(f"\nTotal edges: {total_edges}")
        
        # Check media nodes
        cur.execute("SELECT COUNT(*) FROM media_nodes")
        media_count = cur.fetchone()[0]
        print(f"\nMedia nodes: {media_count}")
        
        if media_count < 16:
            issues.append(f"Insufficient media nodes: expected 16, found {media_count}")
        
        # Check node-media links
        cur.execute("SELECT COUNT(*) FROM node_media")
        node_media_count = cur.fetchone()[0]
        print(f"Node-media links: {node_media_count}")
        
        if node_media_count == 0:
            issues.append("CRITICAL: No node-media links in knowledge graph")
        
        conn.close()
    except Exception as e:
        print(f"ERROR checking knowledge_graph.db: {e}")
        issues.append(f"Failed to check knowledge_graph.db: {e}")
    
    # 5. Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    
    if issues:
        print(f"\nFound {len(issues)} issues:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("\n✓ No issues found!")
    
    return issues

def generate_fix_plan(issues: List[str]) -> Dict[str, Any]:
    """Generate a detailed fix plan based on identified issues"""
    
    plan = {
        'critical_issues': [],
        'embedding_issues': [],
        'kg_issues': [],
        'data_issues': [],
        'actions': []
    }
    
    for issue in issues:
        issue_lower = issue.lower()
        
        if 'critical' in issue_lower:
            plan['critical_issues'].append(issue)
        if 'embedding' in issue_lower or 'faiss' in issue_lower or 'clip' in issue_lower or 'clap' in issue_lower:
            plan['embedding_issues'].append(issue)
        if 'knowledge' in issue_lower or 'node' in issue_lower or 'edge' in issue_lower:
            plan['kg_issues'].append(issue)
        if 'scene' in issue_lower or 'json' in issue_lower:
            plan['data_issues'].append(issue)
    
    # Generate actions
    if plan['critical_issues']:
        plan['actions'].append({
            'priority': 'CRITICAL',
            'action': 'Fix scene_id linkage in embeddings',
            'details': 'Update upsert_embedding calls to include scene_id parameter'
        })
    
    if plan['embedding_issues']:
        plan['actions'].append({
            'priority': 'HIGH',
            'action': 'Regenerate missing embeddings',
            'details': 'Reprocess sample.mp4 with fixed embedding steps'
        })
    
    if plan['kg_issues']:
        plan['actions'].append({
            'priority': 'HIGH',
            'action': 'Rebuild knowledge graph with proper entity extraction',
            'details': 'Fix graph_builder step to extract all entity types'
        })
    
    return plan

if __name__ == "__main__":
    issues = analyze_sample_mp4_processing()
    
    if issues:
        print(f"\n{'='*80}")
        print("GENERATING FIX PLAN")
        print(f"{'='*80}")
        
        plan = generate_fix_plan(issues)
        
        print(f"\nFix Plan:")
        for action in plan['actions']:
            print(f"\n[{action['priority']}] {action['action']}")
            print(f"  → {action['details']}")
