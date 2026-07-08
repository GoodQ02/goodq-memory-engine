#!/usr/bin/env python3
# ==============================================================================
# INGESTION UCF LEDGER HEALER UTILITY
# ==============================================================================
# File: scripts/ucf/maintenance/heal_ucf_ledger.py
# Description: Maintenance script to heal temporal bounds, fix missing Whisper
#              transcripts/diarization turns, and resolve container-boundary
#              timestamp anomalies on UCF ledger.
# Safety Notes:
# - Run ONLY during repair/recovery operations when inconsistencies are detected.
# - Always makes a backup ('ucf_ledger.db.backup_before_heal') before altering.
# ==============================================================================
import sqlite3
import json
import os
import hashlib
from pathlib import Path

# Paths
db_path = Path("L:/_DATA/GoodQ_Data/epochs/epoch_2026_07_05_home_memory_clean_01/ucf/ucf_ledger.db")
processing_root = Path("L:/_DATA/GoodQ_Data/epochs/epoch_2026_07_05_home_memory_clean_01/processing")

def make_scene_hash(video_hash: str, start: float, end: float) -> str:
    h = hashlib.sha256()
    h.update("scene".encode("utf-8"))
    for p in [video_hash, f"{start:.3f}", f"{end:.3f}"]:
        h.update(str(p).encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()

def backup_db():
    import shutil
    backup_path = db_path.with_name("ucf_ledger.db.backup_before_heal")
    if not backup_path.exists():
        shutil.copy2(db_path, backup_path)
        print(f"Backed up database to {backup_path}")

def heal_temporal_bounds(conn):
    print("--- Healing Temporal Bounds ---")
    cursor = conn.cursor()
    cursor.execute("SELECT video_hash, duration FROM media_sources")
    durations = dict(cursor.fetchall())
    
    cursor.execute("SELECT frame_id, video_hash, t_end FROM context_frames WHERE promotion_status = 'staged'")
    updated = 0
    for fid, vh, t_end in cursor.fetchall():
        dur = durations.get(vh)
        if dur and t_end > dur + 0.05:
            new_end = dur
            cursor.execute("UPDATE context_frames SET t_end = ? WHERE frame_id = ?", (new_end, fid))
            updated += 1
            print(f"  Frame {fid} t_end {t_end:.3f} clamped to video duration {dur:.3f}")
    conn.commit()
    print(f"Clamped {updated} frames to video durations.")

def heal_absolute_timestamps(conn):
    print("--- Healing Absolute Timestamps Containment ---")
    cursor = conn.cursor()
    
    cursor.execute("SELECT video_hash, source_artifact_id, t_start, t_end FROM context_frames WHERE worker_name = 'video_scene_detect'")
    scene_bounds = {}
    for vh, sa_id, t1, t2 in cursor.fetchall():
        scene_bounds[(vh, sa_id)] = (t1, t2)
        
    cursor.execute("SELECT frame_id, video_hash, source_artifact_id, worker_name, t_start, t_end FROM context_frames WHERE worker_name IN ('audio_transcribe', 'speaker_merge') AND promotion_status = 'staged'")
    child_frames = cursor.fetchall()
    
    clamped = 0
    deleted = 0
    for fid, vh, sa_id, w, t1, t2 in child_frames:
        bounds = scene_bounds.get((vh, sa_id))
        if not bounds:
            continue
            
        s_start, s_end = bounds
        new_start = t1
        new_end = t2
        changed = False
        
        if t1 < s_start:
            new_start = s_start
            changed = True
        if t2 > s_end:
            new_end = s_end
            changed = True
            
        if changed:
            if new_start >= new_end:
                cursor.execute("DELETE FROM context_frames WHERE frame_id = ?", (fid,))
                deleted += 1
            else:
                cursor.execute("UPDATE context_frames SET t_start = ?, t_end = ? WHERE frame_id = ?", (new_start, new_end, fid))
                clamped += 1
                
    conn.commit()
    print(f"Clamped {clamped} child frames. Deleted {deleted} invalid frames.")

def heal_missing_scene_transcripts(conn):
    print("--- Healing Missing Scene Transcripts ---")
    cursor = conn.cursor()
    
    cursor.execute("SELECT video_hash, file_path FROM media_sources")
    videos = cursor.fetchall()
    
    for vh, file_path in videos:
        video_stem = Path(file_path).stem
        
        cursor.execute("SELECT source_artifact_id, t_start, t_end, payload FROM context_frames WHERE video_hash = ? AND worker_name = 'video_scene_detect'", (vh,))
        scenes = cursor.fetchall()
        
        for sa_id, t_start, t_end, payload_str in scenes:
            scene_hash = make_scene_hash(vh, t_start, t_end)
            
            cursor.execute("SELECT COUNT(*) FROM context_frames WHERE source_artifact_id = ? AND worker_name = 'audio_transcribe'", (scene_hash,))
            cnt_trans = cursor.fetchone()[0]
            
            t_path = processing_root / video_stem / 'audio' / f"{scene_hash}_raw_transcript.json"
            if t_path.exists():
                with open(t_path, 'r', encoding='utf-8') as rf:
                    raw_segments = json.load(rf)
                
                if len(raw_segments) > 0 and cnt_trans == 0:
                    print(f"  Populating missing transcripts for scene {sa_id} of video {video_stem} (hash {scene_hash[:8]})")
                    
                    for i, segment in enumerate(raw_segments):
                        start_time = segment.get('start', 0.0)
                        end_time = segment.get('end', 0.0)
                        
                        if start_time < (t_start - 0.01):
                            tf_start = start_time + t_start
                            tf_end = end_time + t_start
                        else:
                            tf_start = start_time
                            tf_end = end_time
                            
                        tf_start = max(tf_start, t_start)
                        tf_end = min(tf_end, t_end)
                        if tf_start >= tf_end:
                            tf_end = tf_start + 0.1
                            
                        word_count = len(segment.get('text', '').strip().split())
                        confidence_val = segment.get('logprob') if segment.get('logprob') is not None else 1.0
                        
                        payload = {
                            'text': segment.get('text', ''),
                            'language': segment.get('language') or 'en',
                            'segment_index': i,
                            'word_count': word_count,
                            'confidence': confidence_val,
                            'identity_status': 'unresolved'
                        }
                        
                        epoch_id = "epoch_2026_07_05_home_memory_clean_01"
                        run_id = os.getenv("GOODQ_RUN_ID") or "unknown_run"
                        
                        temp_end = tf_end
                        while True:
                            cursor.execute(
                                "SELECT COUNT(*) FROM context_frames WHERE video_hash=? AND epoch_id=? AND modality='text' AND worker_name='audio_transcribe' AND t_start=? AND t_end=?",
                                (vh, epoch_id, tf_start, temp_end)
                            )
                            if cursor.fetchone()[0] == 0:
                                break
                            temp_end += 0.0001
                            
                        cursor.execute(
                            "INSERT INTO context_frames ("
                            "  video_hash, ucf_schema_version, epoch_id, run_id, t_start, t_end,"
                            "  modality, worker_name, model_tag, confidence, payload, payload_hash, promotion_status, source_artifact_id, raw_ref"
                            ") VALUES (?, 'ucf.v0.1', ?, ?, ?, ?, 'text', 'audio_transcribe', 'faster_whisper', 1.0, ?, ?, 'staged', ?, ?)",
                            (
                                vh, epoch_id, run_id, tf_start, temp_end,
                                json.dumps(payload), hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest(),
                                scene_hash, str(t_path.resolve())
                            )
                        )
                        
            cursor.execute("SELECT COUNT(*) FROM context_frames WHERE source_artifact_id = ? AND worker_name = 'speaker_merge'", (scene_hash,))
            cnt_diar = cursor.fetchone()[0]
            
            d_path = processing_root / video_stem / 'audio' / f"{scene_hash}_raw_diarization.json"
            if d_path.exists():
                with open(d_path, 'r', encoding='utf-8') as rf:
                    raw_turns = json.load(rf)
                    
                if len(raw_turns) > cnt_diar:
                    print(f"  Resolving missing diarization turns for scene {sa_id} of video {video_stem} (hash {scene_hash[:8]}): raw={len(raw_turns)} db={cnt_diar}")
                    for i, segment in enumerate(raw_turns):
                        start_time = segment.get('start', 0.0)
                        end_time = segment.get('end', 0.0)
                        
                        if start_time < (t_start - 0.01):
                            tf_start = start_time + t_start
                            tf_end = end_time + t_start
                        else:
                            tf_start = start_time
                            tf_end = end_time
                            
                        tf_start = max(tf_start, t_start)
                        tf_end = min(tf_end, t_end)
                        if tf_start >= tf_end:
                            tf_end = tf_start + 0.1
                            
                        speaker_id = segment.get('speaker') or segment.get('speaker_id', 'unknown')
                        payload = {
                            'speaker_id': speaker_id,
                            'speaker_label': None,
                            'speaker_confidence': 1.0,
                            'turn_index': i,
                            'source': 'pyannote',
                            'identity_status': 'unresolved'
                        }
                        
                        epoch_id = "epoch_2026_07_05_home_memory_clean_01"
                        run_id = os.getenv("GOODQ_RUN_ID") or "unknown_run"
                        
                        temp_end = tf_end
                        while True:
                            cursor.execute(
                                "SELECT COUNT(*) FROM context_frames WHERE video_hash=? AND epoch_id=? AND modality='audio' AND worker_name='speaker_merge' AND t_start=? AND t_end=?",
                                (vh, epoch_id, tf_start, temp_end)
                            )
                            if cursor.fetchone()[0] == 0:
                                break
                            temp_end += 0.0001
                            
                        cursor.execute(
                            "INSERT OR REPLACE INTO context_frames ("
                            "  video_hash, ucf_schema_version, epoch_id, run_id, t_start, t_end,"
                            "  modality, worker_name, model_tag, confidence, payload, payload_hash, promotion_status, source_artifact_id, raw_ref"
                            ") VALUES (?, 'ucf.v0.1', ?, ?, ?, ?, 'audio', 'speaker_merge', 'pyannote', 1.0, ?, ?, 'staged', ?, ?)",
                            (
                                vh, epoch_id, run_id, tf_start, temp_end,
                                json.dumps(payload), hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest(),
                                scene_hash, str(d_path.resolve())
                            )
                        )
    conn.commit()
    print("Missing transcripts and diarization turns repopulated successfully.")

def main():
    print(f"Opening database: {db_path}")
    if not db_path.exists():
        print("Database not found!")
        return
        
    backup_db()
    
    conn = sqlite3.connect(str(db_path))
    try:
        heal_temporal_bounds(conn)
        heal_missing_scene_transcripts(conn)
        heal_absolute_timestamps(conn)
        print("Database healing completed successfully!")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
