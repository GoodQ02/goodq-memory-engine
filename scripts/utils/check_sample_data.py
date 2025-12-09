#!/usr/bin/env python3
"""Check sample.mp4 processing data in the knowledge graph."""

import sqlite3

def main():
    import sqlite3
    db_path = "L:\\goodq4all\\data\\goodq_memory.db"
    
    print("\n=== SAMPLE.MP4 DATABASE CHECK ===\n")
    
    # Connect directly to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Find sample video
    videos = cursor.execute(
        "SELECT video_hash, source_path, duration FROM videos WHERE source_path LIKE '%sample%' LIMIT 5"
    ).fetchall()
    print(f"Videos with 'sample' in path: {len(videos)}")
    for v in videos:
        print(f"  Hash: {v[0]}")
        print(f"  Path: {v[1]}")
        print(f"  Duration: {v[2]}")
        print()
        
        video_hash = v[0]
        
        # Check scenes
        scenes = cursor.execute(
            f"SELECT scene_index, start_time, end_time, duration FROM scenes WHERE video_hash = '{video_hash}' ORDER BY scene_index"
        ).fetchall()
        print(f"  Scenes: {len(scenes)}")
        for i, s in enumerate(scenes[:5]):  # Show first 5
            print(f"    Scene {s[0]}: {s[1]:.2f}s - {s[2]:.2f}s (duration: {s[3]:.2f}s)")
        if len(scenes) > 5:
            print(f"    ... and {len(scenes) - 5} more scenes")
        print()
        
        # Check frames
        frames = cursor.execute(
            f"SELECT COUNT(*) FROM frames WHERE video_hash = '{video_hash}'"
        ).fetchall()
        print(f"  Frames: {frames[0][0] if frames else 0}")
        
        # Check frame details
        frame_details = cursor.execute(
            f"SELECT timestamp, scene_index, caption, ocr_text FROM frames WHERE video_hash = '{video_hash}' ORDER BY timestamp LIMIT 5"
        ).fetchall()
        for fd in frame_details:
            print(f"    @{fd[0]:.2f}s (scene {fd[1]}): caption={bool(fd[2])}, ocr={bool(fd[3])}")
        print()
        
        # Check transcript
        transcript = cursor.execute(
            f"SELECT transcript FROM videos WHERE video_hash = '{video_hash}'"
        ).fetchall()
        if transcript and transcript[0][0]:
            trans_text = transcript[0][0]
            print(f"  Transcript: {len(trans_text)} chars, {len(trans_text.split())} words")
            print(f"  Preview: {trans_text[:200]}...")
        else:
            print(f"  Transcript: NONE")
        print()
        
        # Check segments
        segments = cursor.execute(
            f"SELECT COUNT(*) FROM segments WHERE video_hash = '{video_hash}'"
        ).fetchall()
        print(f"  Transcript Segments: {segments[0][0] if segments else 0}")
        
        seg_details = cursor.execute(
            f"SELECT start_time, end_time, text, speaker FROM segments WHERE video_hash = '{video_hash}' ORDER BY start_time LIMIT 5"
        ).fetchall()
        for sd in seg_details:
            speaker = sd[3] or "Unknown"
            text_preview = sd[2][:60] + "..." if sd[2] and len(sd[2]) > 60 else sd[2]
            print(f"    {sd[0]:.2f}s - {sd[1]:.2f}s [{speaker}]: {text_preview}")
        print()
        
        # Check entities
        entities = cursor.execute(
            f"""SELECT e.entity_text, e.entity_type, COUNT(DISTINCT fe.frame_id)
                FROM entities e
                JOIN frame_entities fe ON e.entity_id = fe.entity_id
                JOIN frames f ON fe.frame_id = f.frame_id
                WHERE f.video_hash = '{video_hash}'
                GROUP BY e.entity_id
                ORDER BY COUNT(DISTINCT fe.frame_id) DESC
                LIMIT 10"""
        ).fetchall()
        print(f"  Entities (from frames): {len(entities)}")
        for ent in entities:
            print(f"    {ent[0]} ({ent[1]}): appears in {ent[2]} frames")
        print()
        
        # Check tags
        tags = cursor.execute(
            f"""SELECT t.tag_name, t.tag_type, COUNT(DISTINCT ft.frame_id)
                FROM tags t
                JOIN frame_tags ft ON t.tag_id = ft.tag_id
                JOIN frames f ON ft.frame_id = f.frame_id
                WHERE f.video_hash = '{video_hash}'
                GROUP BY t.tag_id
                ORDER BY COUNT(DISTINCT ft.frame_id) DESC
                LIMIT 10"""
        ).fetchall()
        print(f"  Tags (from frames): {len(tags)}")
        for tag in tags:
            print(f"    {tag[0]} ({tag[1]}): appears in {tag[2]} frames")
        print()
        
        # Check objects
        objects = cursor.execute(
            f"""SELECT label, COUNT(*) as cnt
                FROM objects
                WHERE video_hash = '{video_hash}'
                GROUP BY label
                ORDER BY cnt DESC
                LIMIT 10"""
        ).fetchall()
        print(f"  Objects detected: {len(objects)} unique types")
        for obj in objects:
            print(f"    {obj[0]}: {obj[1]} detections")
        print()
        
        # Check faces
        faces = cursor.execute(
            f"SELECT COUNT(*) FROM faces WHERE video_hash = '{video_hash}'"
        ).fetchall()
        print(f"  Faces detected: {faces[0][0] if faces else 0}")
        print()
        
        # Check emotions
        emotions = cursor.execute(
            f"SELECT emotion_label, confidence FROM emotions WHERE video_hash = '{video_hash}' LIMIT 5"
        ).fetchall()
        print(f"  Emotions: {len(emotions)}")
        for emo in emotions:
            print(f"    {emo[0]}: {emo[1]:.3f}")
        print()

if __name__ == "__main__":
    main()
