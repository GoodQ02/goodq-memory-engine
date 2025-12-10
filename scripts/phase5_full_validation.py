#!/usr/bin/env python3
"""
Phase 5: Full System Validation
Comprehensive validation of all pipeline components and data integrity
"""

import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime
import os

# Color codes for terminal
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{msg:^70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")

def print_success(msg):
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")

def print_warning(msg):
    print(f"{Colors.WARNING}⚠ {msg}{Colors.ENDC}")

def print_error(msg):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")

def print_info(msg):
    print(f"{Colors.OKCYAN}→ {msg}{Colors.ENDC}")

def check_file_structure():
    """Validate directory structure"""
    print_header("1. FILE STRUCTURE VALIDATION")
    
    required_dirs = [
        "L:/_DATA/GoodQ_Data",
        "L:/_DATA/GoodQ_Data/databases",
        "L:/_DATA/GoodQ_Data/faiss_indices",
        "L:/_DATA/GoodQ_Data/processing",
        "L:/_DATA/GoodQ_Data/output",
        "L:/goodq4all/logs",
        "L:/goodq4all/import_inbox",
        "L:/goodq4all/steps",
    ]
    
    for dir_path in required_dirs:
        p = Path(dir_path)
        if p.exists():
            print_success(f"{dir_path} exists")
        else:
            print_error(f"{dir_path} MISSING")
    
    # Check critical files
    critical_files = [
        "L:/_DATA/GoodQ_Data/memory.db",
        "L:/_DATA/GoodQ_Data/knowledge_graph.db",
        "L:/goodq4all/configs/paths.yaml",
    ]
    
    for file_path in critical_files:
        p = Path(file_path)
        if p.exists():
            size_mb = p.stat().st_size / 1024 / 1024
            print_success(f"{file_path} ({size_mb:.2f} MB)")
        else:
            print_error(f"{file_path} MISSING")

def check_databases():
    """Validate database integrity"""
    print_header("2. DATABASE INTEGRITY CHECK")
    
    # Check memory.db
    try:
        conn = sqlite3.connect("L:/_DATA/GoodQ_Data/memory.db")
        c = conn.cursor()
        
        # Check tables
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in c.fetchall()]
        print_info(f"memory.db tables: {', '.join(tables)}")
        
        # Get counts
        c.execute("SELECT COUNT(*) FROM scenes")
        scene_count = c.fetchone()[0]
        print_success(f"Scenes: {scene_count}")
        
        c.execute("SELECT COUNT(*) FROM segments")
        segment_count = c.fetchone()[0]
        print_success(f"Segments: {segment_count}")
        
        c.execute("SELECT COUNT(*) FROM embeddings")
        embedding_count = c.fetchone()[0]
        print_success(f"Embeddings: {embedding_count}")
        
        c.execute("SELECT COUNT(*) FROM links")
        link_count = c.fetchone()[0]
        print_success(f"Links: {link_count}")
        
        conn.close()
        
    except Exception as e:
        print_error(f"memory.db error: {e}")
    
    # Check knowledge_graph.db
    try:
        conn = sqlite3.connect("L:/_DATA/GoodQ_Data/knowledge_graph.db")
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM nodes")
        node_count = c.fetchone()[0]
        print_success(f"KG Nodes: {node_count}")
        
        c.execute("SELECT COUNT(*) FROM edges")
        edge_count = c.fetchone()[0]
        print_success(f"KG Edges: {edge_count}")
        
        # Node type distribution
        c.execute("SELECT node_type, COUNT(*) FROM nodes GROUP BY node_type")
        node_dist = c.fetchall()
        print_info("Node distribution:")
        for node_type, count in node_dist:
            print(f"  - {node_type}: {count}")
        
        conn.close()
        
    except Exception as e:
        print_error(f"knowledge_graph.db error: {e}")

def check_faiss_indices():
    """Validate FAISS indices"""
    print_header("3. FAISS INDICES CHECK")
    
    indices = [
        "L:/_DATA/GoodQ_Data/faiss_indices/text/faiss_text.index",
        "L:/_DATA/GoodQ_Data/faiss_indices/audio/faiss_audio.index",
        "L:/_DATA/GoodQ_Data/faiss_indices/clip/faiss_clip.index",
        "L:/_DATA/GoodQ_Data/faiss_indices/dino/faiss_dino.index",
    ]
    
    for idx_path in indices:
        p = Path(idx_path)
        if p.exists():
            size_kb = p.stat().st_size / 1024
            print_success(f"{p.name}: {size_kb:.2f} KB")
        else:
            print_warning(f"{p.name}: NOT FOUND")

def check_scene_results():
    """Analyze scene ingest results"""
    print_header("4. SCENE PROCESSING ANALYSIS")
    
    results_path = Path("L:/goodq4all/logs/scene_ingest_results.json")
    if not results_path.exists():
        print_warning("No scene_ingest_results.json found")
        return
    
    try:
        with open(results_path) as f:
            results = json.load(f)
        
        if not results:
            print_warning("Empty results")
            return
        
        result = results[0]  # First video
        print_info(f"Video: {Path(result['video_path']).name}")
        print_success(f"Scene count: {result['scene_meta']['scene_count']}")
        print_success(f"Engine: {result['scene_meta']['engine']}")
        print_success(f"Status: {result['scene_meta']['status']}")
        
        # Analyze first scene
        scene = result['scenes'][0]
        print_info("\nFirst scene analysis:")
        print(f"  - Duration: {scene['duration']}s")
        print(f"  - Caption: {scene['keyframe'].get('caption', 'N/A')}")
        print(f"  - Objects detected: {len(scene['keyframe'].get('objects', []))}")
        print(f"  - Transcript: {scene.get('transcript', 'N/A')}")
        
        # Check for critical fields
        critical_fields = ['transcript', 'sentiment', 'tags', 'entities']
        print_info("\nCritical field presence:")
        for field in critical_fields:
            if field in scene:
                value = scene[field]
                if value:
                    print_success(f"{field}: {value}")
                else:
                    print_warning(f"{field}: empty")
            else:
                print_error(f"{field}: MISSING")
        
    except Exception as e:
        print_error(f"Error analyzing results: {e}")

def check_step_logs():
    """Check step execution logs"""
    print_header("5. STEP EXECUTION CHECK")
    
    log_dir = Path("L:/goodq4all/logs")
    if not log_dir.exists():
        print_error("Log directory not found")
        return
    
    # Find all step logs
    step_logs = sorted(log_dir.glob("*.log"))
    
    print_info(f"Found {len(step_logs)} step logs")
    
    for log_file in step_logs:
        try:
            with open(log_file) as f:
                lines = f.readlines()
            
            if not lines:
                print_warning(f"{log_file.name}: empty")
                continue
            
            # Check for errors
            errors = [l for l in lines if 'ERROR' in l or 'FAILED' in l]
            successes = [l for l in lines if 'SUCCESS' in l]
            
            if errors:
                print_error(f"{log_file.name}: {len(errors)} errors")
            elif successes:
                print_success(f"{log_file.name}: {len(successes)} successful runs")
            else:
                print_info(f"{log_file.name}: {len(lines)} lines")
        
        except Exception as e:
            print_warning(f"{log_file.name}: {e}")

def check_processing_state():
    """Check current processing state"""
    print_header("6. PROCESSING STATE")
    
    # Check import_inbox
    inbox = Path("L:/goodq4all/import_inbox")
    if inbox.exists():
        files = list(inbox.glob("*"))
        print_info(f"Import inbox: {len(files)} files")
        for f in files:
            print(f"  - {f.name}")
    
    # Check processing
    processing = Path("L:/_DATA/GoodQ_Data/processing")
    if processing.exists():
        files = list(processing.glob("*"))
        print_info(f"Currently processing: {len(files)} files")
        for f in files:
            print(f"  - {f.name}")
    
    # Check processed
    processed = Path("L:/_DATA/GoodQ_Data/processed")
    if processed.exists():
        files = list(processed.glob("*"))
        print_info(f"Processed: {len(files)} files")

def check_data_linkage():
    """Validate data is properly linked"""
    print_header("7. DATA LINKAGE VALIDATION")
    
    try:
        # Check if scenes have embeddings
        conn = sqlite3.connect("L:/_DATA/GoodQ_Data/memory.db")
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM scenes")
        total_scenes = c.fetchone()[0]
        
        c.execute("""
            SELECT COUNT(DISTINCT scene_id) 
            FROM segments
        """)
        scenes_with_segments = c.fetchone()[0]
        
        if scenes_with_segments == total_scenes:
            print_success(f"All {total_scenes} scenes have segments")
        else:
            print_warning(f"{scenes_with_segments}/{total_scenes} scenes have segments")
        
        c.execute("SELECT COUNT(DISTINCT source_id) FROM embeddings")
        sources_with_embeddings = c.fetchone()[0]
        print_info(f"{sources_with_embeddings} unique sources with embeddings")
        
        conn.close()
        
    except Exception as e:
        print_error(f"Linkage check error: {e}")

def check_config_consistency():
    """Validate config consistency"""
    print_header("8. CONFIGURATION CHECK")
    
    try:
        import yaml
        
        # Load paths config
        with open("L:/goodq4all/configs/paths.yaml") as f:
            paths = yaml.safe_load(f)
        
        print_info("Path configuration:")
        for key, value in paths.items():
            if isinstance(value, str) and ('/' in value or '\\' in value):
                path = Path(value)
                if path.exists():
                    print_success(f"{key}: {value}")
                else:
                    print_warning(f"{key}: {value} (not found)")
        
    except Exception as e:
        print_error(f"Config check error: {e}")

def main():
    print_header("PHASE 5: FULL SYSTEM VALIDATION")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    check_file_structure()
    check_databases()
    check_faiss_indices()
    check_scene_results()
    check_step_logs()
    check_processing_state()
    check_data_linkage()
    check_config_consistency()
    
    print_header("VALIDATION COMPLETE")
    print(f"\n{Colors.OKGREEN}{Colors.BOLD}System validation finished.{Colors.ENDC}\n")

if __name__ == "__main__":
    main()
