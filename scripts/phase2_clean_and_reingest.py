"""
Phase 2: Clean and Re-Ingest sample.mp4
Cleans previous sample.mp4 data and re-ingests with fixed embedding pipeline
"""
import sqlite3
import shutil
from pathlib import Path
import subprocess
import sys

def clean_sample_data():
    """Remove all previous sample.mp4 processing data"""
    print("="*80)
    print("CLEANING PREVIOUS sample.mp4 DATA")
    print("="*80)
    
    data_dir = Path("L:/goodq4all/data")
    
    # 1. Clean memory.db entries for sample.mp4
    print("\n[1/5] Cleaning memory.db...")
    memory_db = data_dir / "memory.db"
    if memory_db.exists():
        try:
            conn = sqlite3.connect(str(memory_db))
            cur = conn.cursor()
            
            # Find sample.mp4 related entries
            cur.execute("SELECT COUNT(*) FROM embeddings WHERE source_path LIKE '%sample%'")
            emb_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM scenes WHERE id IN (SELECT scene_id FROM embeddings WHERE source_path LIKE '%sample%')")
            scene_count = cur.fetchone()[0]
            
            print(f"  Found {emb_count} embeddings and {scene_count} scenes related to sample.mp4")
            
            if emb_count > 0 or scene_count > 0:
                # Delete embeddings
                cur.execute("DELETE FROM embeddings WHERE source_path LIKE '%sample%'")
                
                # Delete links related to sample scenes
                cur.execute("""
                    DELETE FROM links WHERE parent_hash IN (
                        SELECT hash FROM embeddings WHERE source_path LIKE '%sample%'
                    ) OR child_hash IN (
                        SELECT hash FROM embeddings WHERE source_path LIKE '%sample%'
                    )
                """)
                
                # Delete scenes
                cur.execute("DELETE FROM scenes WHERE id LIKE '%sample%'")
                
                # Delete segments
                cur.execute("DELETE FROM segments WHERE id LIKE '%sample%'")
                
                conn.commit()
                print(f"  ✓ Cleaned memory.db")
            else:
                print("  ✓ No sample.mp4 data found in memory.db")
            
            conn.close()
        except Exception as e:
            print(f"  ✗ Error cleaning memory.db: {e}")
    else:
        print("  ℹ memory.db not found")
    
    # 2. Clean knowledge_graph.db entries
    print("\n[2/5] Cleaning knowledge_graph.db...")
    kg_db = data_dir / "knowledge_graph.db"
    if kg_db.exists():
        try:
            conn = sqlite3.connect(str(kg_db))
            cur = conn.cursor()
            
            # Find sample.mp4 media nodes
            cur.execute("SELECT COUNT(*) FROM media_nodes WHERE media_path LIKE '%sample%'")
            media_count = cur.fetchone()[0]
            
            print(f"  Found {media_count} media nodes related to sample.mp4")
            
            if media_count > 0:
                # Get media IDs
                cur.execute("SELECT id FROM media_nodes WHERE media_path LIKE '%sample%'")
                media_ids = [row[0] for row in cur.fetchall()]
                
                if media_ids:
                    placeholders = ','.join('?' * len(media_ids))
                    
                    # Delete node_media links
                    cur.execute(f"DELETE FROM node_media WHERE media_id IN ({placeholders})", media_ids)
                    
                    # Delete media nodes
                    cur.execute(f"DELETE FROM media_nodes WHERE id IN ({placeholders})", media_ids)
                    
                    # Clean up orphaned nodes (nodes with no media links)
                    cur.execute("""
                        DELETE FROM nodes WHERE id NOT IN (
                            SELECT DISTINCT node_id FROM node_media
                        )
                    """)
                    
                    # Clean up orphaned edges
                    cur.execute("""
                        DELETE FROM edges WHERE source_id NOT IN (
                            SELECT id FROM nodes
                        ) OR target_id NOT IN (
                            SELECT id FROM nodes
                        )
                    """)
                    
                    conn.commit()
                    print(f"  ✓ Cleaned knowledge_graph.db")
            else:
                print("  ✓ No sample.mp4 data found in knowledge_graph.db")
            
            conn.close()
        except Exception as e:
            print(f"  ✗ Error cleaning knowledge_graph.db: {e}")
    else:
        print("  ℹ knowledge_graph.db not found")
    
    # 3. Clean FAISS indices (optional - they auto-update)
    print("\n[3/5] Checking FAISS indices...")
    print("  ℹ FAISS indices will be updated during re-ingestion")
    
    # 4. Clean processing directories
    print("\n[4/5] Cleaning processing directories...")
    processing_dir = data_dir / "processing"
    if processing_dir.exists():
        sample_dirs = list(processing_dir.glob("*sample*"))
        if sample_dirs:
            for sample_dir in sample_dirs:
                try:
                    shutil.rmtree(sample_dir)
                    print(f"  ✓ Removed {sample_dir}")
                except Exception as e:
                    print(f"  ✗ Error removing {sample_dir}: {e}")
        else:
            print("  ℹ No sample processing directories found")
    else:
        print("  ℹ Processing directory not found")
    
    # 5. Clean output directories
    print("\n[5/5] Cleaning output directories...")
    output_dir = data_dir / "output"
    if output_dir.exists():
        sample_outputs = list(output_dir.glob("*sample*"))
        if sample_outputs:
            for sample_output in sample_outputs:
                try:
                    if sample_output.is_dir():
                        shutil.rmtree(sample_output)
                    else:
                        sample_output.unlink()
                    print(f"  ✓ Removed {sample_output}")
                except Exception as e:
                    print(f"  ✗ Error removing {sample_output}: {e}")
        else:
            print("  ℹ No sample output files found")
    else:
        print("  ℹ Output directory not found")
    
    print("\n" + "="*80)
    print("CLEANUP COMPLETE!")
    print("="*80)

def verify_sample_file():
    """Verify sample.mp4 exists in import_inbox"""
    print("\n" + "="*80)
    print("VERIFYING sample.mp4 LOCATION")
    print("="*80)
    
    possible_locations = [
        Path("L:/goodq4all/import_inbox/sample.mp4"),
        Path("L:/goodq4all/data/testing/sample.mp4"),
        Path("L:/goodq4all/sample.mp4"),
    ]
    
    for location in possible_locations:
        if location.exists():
            size_mb = location.stat().st_size / 1024 / 1024
            print(f"✓ Found: {location} ({size_mb:.2f} MB)")
            return location
    
    print("✗ sample.mp4 not found in expected locations:")
    for loc in possible_locations:
        print(f"  - {loc}")
    return None

def main():
    print("\n" + "="*80)
    print("PHASE 2: CLEAN AND RE-INGEST sample.mp4")
    print("="*80)
    
    # Step 1: Clean
    clean_sample_data()
    
    # Step 2: Verify sample.mp4 exists
    sample_file = verify_sample_file()
    
    if not sample_file:
        print("\n✗ Cannot proceed: sample.mp4 not found!")
        print("\nPlease ensure sample.mp4 is in L:/goodq4all/import_inbox/")
        return 1
    
    print("\n" + "="*80)
    print("READY FOR RE-INGESTION")
    print("="*80)
    print("\nNext steps:")
    print("  1. Ensure watchdog_ingest.py is running")
    print("  2. Copy sample.mp4 to import_inbox (if not already there)")
    print("  3. Monitor ingestion with: python scripts/monitor_ingestion_progress.py")
    print("  4. Verify embeddings have scene_id: python check_databases.py")
    print("  5. Verify knowledge graph population")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
