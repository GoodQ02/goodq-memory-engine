"""
GoodQ Intelligence Report Generator
Shows detailed analysis of processed video content
"""
import sqlite3
import json
import sys
from pathlib import Path

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

def format_timestamp(seconds):
    """Convert seconds to MM:SS format"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"

def show_intelligence_report():
    """Generate and display intelligence report"""
    
    db_path = Path('L:/goodq4all/data/memory.db')
    
    if not db_path.exists():
        print("\n[!] No intelligence database found yet")
        print(f"[!] Expected: {db_path}")
        print("\n[?] Process a video first using START_WATCHDOG.bat")
        return
    
    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        
        # Get scene statistics
        c.execute('SELECT COUNT(*), MIN(start), MAX(end) FROM scenes')
        result = c.fetchone()
        
        if not result or result[0] == 0:
            print("\n[!] No scenes found in database")
            print("[?] Video may still be processing...")
            conn.close()
            return
            
        scene_cnt, min_start, max_end = result
        
        if min_start is None or max_end is None:
            duration_min = 0
        else:
            duration_min = (max_end - min_start) / 60
        
        print("\n📊 MISSION INTEL\n")
        print(f"  Scenes Analyzed: {scene_cnt}")
        print(f"  Duration: {duration_min:.1f} minutes")
        
        # Get video hash if available
        c.execute("SELECT DISTINCT video_hash FROM scenes WHERE video_hash IS NOT NULL LIMIT 1")
        hash_result = c.fetchone()
        if hash_result:
            print(f"  Video Hash: {hash_result[0][:16]}...")
        
        # Intelligence gathered
        print("\n🎯 INTELLIGENCE GATHERED\n")
        
        c.execute('SELECT COUNT(*) FROM embeddings')
        embedding_count = c.fetchone()[0]
        print(f"  Embeddings Created: {embedding_count}")
        
        c.execute('SELECT COUNT(*) FROM links')
        link_count = c.fetchone()[0]
        print(f"  Knowledge Links: {link_count}")
        
        # By modality
        c.execute('SELECT modality, COUNT(*) FROM embeddings GROUP BY modality')
        modality_results = c.fetchall()
        
        if modality_results:
            print("\n  By Modality:")
            for mod, cnt in modality_results:
                print(f"    {mod}: {cnt}")
        
        # Scene highlights
        print("\n🎬 SCENE HIGHLIGHTS\n")
        c.execute('SELECT start, end, meta FROM scenes WHERE meta IS NOT NULL ORDER BY start LIMIT 15')
        scenes = c.fetchall()
        
        if scenes:
            for i, (start, end, meta) in enumerate(scenes, 1):
                try:
                    meta_dict = json.loads(meta) if meta else {}
                    caption = meta_dict.get('caption', '(processing)')
                    # Truncate long captions
                    if len(caption) > 70:
                        caption = caption[:67] + "..."
                    timestamp = format_timestamp(start)
                    print(f"  {i:2d}. [{timestamp}] {caption}")
                except (json.JSONDecodeError, Exception) as e:
                    timestamp = format_timestamp(start)
                    print(f"  {i:2d}. [{timestamp}] (metadata error)")
        else:
            print("  (No scene metadata available yet)")
        
        # Additional statistics
        print("\n📈 DETAILED STATISTICS\n")
        
        # Count objects detected
        c.execute("SELECT COUNT(*) FROM embeddings WHERE modality = 'object'")
        obj_count = c.fetchone()[0]
        if obj_count > 0:
            print(f"  Objects Detected: {obj_count}")
        
        # Count faces
        c.execute("SELECT COUNT(*) FROM embeddings WHERE modality = 'face'")
        face_count = c.fetchone()[0]
        if face_count > 0:
            print(f"  Faces Identified: {face_count}")
        
        # Count audio transcriptions
        c.execute("SELECT COUNT(*) FROM embeddings WHERE modality = 'audio_transcript'")
        audio_count = c.fetchone()[0]
        if audio_count > 0:
            print(f"  Audio Transcriptions: {audio_count}")
        
        conn.close()
        
        print("\n💾 DATA LOCATION: L:\\goodq4all\\data\\memory.db")
        print("📁 WORKSPACES: L:\\goodq4all\\logs\\watchdog_*\\")
        print("\n✅ Mission Status: INTELLIGENCE SUCCESSFULLY EXTRACTED\n")
        
    except sqlite3.Error as e:
        print(f"\n[ERROR] Database error: {e}")
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    show_intelligence_report()
