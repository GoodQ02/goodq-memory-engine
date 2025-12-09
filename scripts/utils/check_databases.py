import sqlite3
from pathlib import Path

# Check memory.db
print("=== Checking memory.db ===")
try:
    conn = sqlite3.connect('L:/goodq4all/data/memory.db')
    cur = conn.cursor()
    
    # List tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"Tables: {tables}")
    
    # Check embeddings
    if 'embeddings' in tables:
        cur.execute("SELECT COUNT(*) FROM embeddings")
        print(f"Total embeddings: {cur.fetchone()[0]}")
        
        cur.execute("SELECT modality, COUNT(*) FROM embeddings GROUP BY modality")
        print("\nEmbeddings by modality:")
        for row in cur.fetchall():
            print(f"  {row[0] or 'NULL'}: {row[1]}")
        
        # Sample some entries
        cur.execute("SELECT hash, source_path, modality, scene_id FROM embeddings LIMIT 5")
        print("\nSample embeddings:")
        for row in cur.fetchall():
            print(f"  Hash: {row[0][:16]}... Path: {Path(row[1]).name if row[1] else 'N/A'}, Modality: {row[2]}, Scene: {row[3]}")
    
    # Check links
    if 'links' in tables:
        cur.execute("SELECT COUNT(*) FROM links")
        print(f"\nTotal links: {cur.fetchone()[0]}")
        
        cur.execute("SELECT relation, COUNT(*) FROM links GROUP BY relation")
        print("\nLinks by relation:")
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")
    
    # Check scenes
    if 'scenes' in tables:
        cur.execute("SELECT COUNT(*) FROM scenes")
        print(f"\nTotal scenes: {cur.fetchone()[0]}")
    
    # Check segments
    if 'segments' in tables:
        cur.execute("SELECT COUNT(*) FROM segments")
        print(f"\nTotal segments: {cur.fetchone()[0]}")
    
    conn.close()
except Exception as e:
    print(f"Error checking memory.db: {e}")

print("\n=== Checking knowledge_graph.db ===")
try:
    conn = sqlite3.connect('L:/goodq4all/data/knowledge_graph.db')
    cur = conn.cursor()
    
    # List tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"Tables: {tables}")
    
    # Check nodes
    if 'nodes' in tables:
        cur.execute("SELECT COUNT(*) FROM nodes")
        print(f"Total nodes: {cur.fetchone()[0]}")
        
        cur.execute("SELECT node_type, COUNT(*) FROM nodes GROUP BY node_type")
        print("\nNodes by type:")
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")
    
    # Check edges
    if 'edges' in tables:
        cur.execute("SELECT COUNT(*) FROM edges")
        print(f"\nTotal edges: {cur.fetchone()[0]}")
        
        cur.execute("SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type")
        print("\nEdges by type:")
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")
    
    # Check media_nodes
    if 'media_nodes' in tables:
        cur.execute("SELECT COUNT(*) FROM media_nodes")
        print(f"\nTotal media_nodes: {cur.fetchone()[0]}")
    
    # Check node_media links
    if 'node_media' in tables:
        cur.execute("SELECT COUNT(*) FROM node_media")
        print(f"\nTotal node_media links: {cur.fetchone()[0]}")
    
    conn.close()
except Exception as e:
    print(f"Error checking knowledge_graph.db: {e}")
