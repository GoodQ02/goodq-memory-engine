"""
Check status of production ingestion run
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime

# Paths - UNIFIED structure
STEP_RUNS_LOG = Path('L:/goodq4all/logs/steps.jsonl')
MEMORY_DB = Path('L:/goodq4all/data/memory.db')
KNOWLEDGE_GRAPH_DB = Path('L:/goodq4all/L:/goodq4all/data/knowledge_graph.db')
WORKSPACE = Path('L:/goodq4all/logs/production_run')

def count_lines(file_path: Path) -> int:
    """Count lines in a file"""
    if not file_path.exists():
        return 0
    with open(file_path, 'r', encoding='utf-8') as f:
        return sum(1 for _ in f)

def get_last_steps(n=5) -> list:
    """Get last N step entries"""
    if not STEP_RUNS_LOG.exists():
        return []
    
    lines = []
    with open(STEP_RUNS_LOG, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    results = []
    for line in lines[-n:]:
        try:
            entry = json.loads(line)
            results.append(entry)
        except:
            pass
    return results

def check_db_status():
    """Check database status"""
    if not MEMORY_DB.exists():
        return {'scenes': 0, 'embeddings': 0}
    
    conn = sqlite3.connect(str(MEMORY_DB))
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM scenes')
    scene_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM embeddings')
    embedding_count = cursor.fetchone()[0]
    
    conn.close()
    
    return {'scenes': scene_count, 'embeddings': embedding_count}

def check_kg_status():
    """Check knowledge graph status"""
    if not KNOWLEDGE_GRAPH_DB.exists():
        return None
    
    conn = sqlite3.connect(str(KNOWLEDGE_GRAPH_DB))
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM nodes')
    node_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM edges')
    edge_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM media_nodes')
    media_count = cursor.fetchone()[0]
    
    conn.close()
    
    return {'nodes': node_count, 'edges': edge_count, 'media': media_count}

def check_workspace():
    """Check workspace artifacts"""
    if not WORKSPACE.exists():
        return {'frames': 0, 'audio': 0}
    
    video_dir = WORKSPACE / '1987_1988'
    if not video_dir.exists():
        return {'frames': 0, 'audio': 0}
    
    frame_dir = video_dir / 'frames'
    audio_dir = video_dir / 'audio'
    
    frames = len(list(frame_dir.glob('*.jpg'))) if frame_dir.exists() else 0
    audio = len(list(audio_dir.glob('*.wav'))) if audio_dir.exists() else 0
    
    return {'frames': frames, 'audio': audio}

def main():
    print("=" * 70)
    print("PRODUCTION INGESTION STATUS")
    print("=" * 70)
    print(f"Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Step logs
    step_count = count_lines(STEP_RUNS_LOG)
    print(f"📊 Step Runs: {step_count}")
    
    if step_count > 0:
        print("\n   Recent steps:")
        for step in get_last_steps(5):
            step_name = step.get('step', 'unknown')
            status = step.get('status', 'unknown')
            duration = step.get('duration_ms', 0) / 1000
            print(f"     • {step_name}: {status} ({duration:.1f}s)")
    
    # Database status
    print("\n💾 Memory Database:")
    db_status = check_db_status()
    print(f"   Scenes: {db_status['scenes']}")
    print(f"   Embeddings: {db_status['embeddings']}")
    
    # Knowledge graph status
    print("\n🕸️  Knowledge Graph:")
    kg_status = check_kg_status()
    if kg_status:
        print(f"   Nodes: {kg_status['nodes']}")
        print(f"   Edges: {kg_status['edges']}")
        print(f"   Media: {kg_status['media']}")
    else:
        print("   Not created yet")
    
    # Workspace artifacts
    print("\n📁 Workspace Artifacts:")
    workspace_status = check_workspace()
    print(f"   Frames extracted: {workspace_status['frames']}")
    print(f"   Audio clips: {workspace_status['audio']}")
    
    print("\n" + "=" * 70)

if __name__ == '__main__':
    main()
