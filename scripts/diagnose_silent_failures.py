#!/usr/bin/env python3
"""
Mission: Diagnose Silent Failures
Objective: Find all processing steps that are failing silently
Agent: Q
"""

import sqlite3
import json
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OK = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}╔═══ {msg} ═══╗{Colors.END}")

def success(msg):
    print(f"{Colors.OK}✓{Colors.END} {msg}")

def warning(msg):
    print(f"{Colors.WARNING}⚠{Colors.END} {msg}")

def error(msg):
    print(f"{Colors.FAIL}✗{Colors.END} {msg}")

def info(msg):
    print(f"  {msg}")

def main():
    print(f"{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}MISSION BRIEFING: Silent Failure Analysis{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"Agent Q reporting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check database
    db_path = Path("L:/goodq4all/data/memory.db")
    if not db_path.exists():
        error(f"Database not found at {db_path}")
        return 1
    
    db = sqlite3.connect(str(db_path))
    cursor = db.cursor()
    
    # Get counts
    header("INTEL: Database Population")
    cursor.execute("SELECT COUNT(*) FROM scenes")
    scene_count = cursor.fetchone()[0]
    success(f"Scenes processed: {scene_count:,}")
    
    cursor.execute("SELECT COUNT(*) FROM embeddings")
    embed_count = cursor.fetchone()[0]
    if embed_count == 0:
        error(f"Embeddings created: {embed_count} - CRITICAL FAILURE")
    elif embed_count < scene_count * 2:  # Expect at least 2 embeddings per scene (text + image)
        warning(f"Embeddings created: {embed_count:,} - Expected ~{scene_count*2:,}")
    else:
        success(f"Embeddings created: {embed_count:,}")
    
    cursor.execute("SELECT COUNT(*) FROM segments")
    segment_count = cursor.fetchone()[0]
    info(f"Audio segments: {segment_count:,}")
    
    cursor.execute("SELECT COUNT(*) FROM links")
    link_count = cursor.fetchone()[0]
    info(f"Entity links: {link_count:,}")
    
    # Analyze embeddings by modality
    header("ANALYSIS: Embedding Coverage by Type")
    cursor.execute("SELECT modality, COUNT(*) FROM embeddings GROUP BY modality")
    embed_types = dict(cursor.fetchall())
    
    if not embed_types:
        error("No embeddings found by modality - all embedding steps failed silently!")
    else:
        for modality, count in sorted(embed_types.items()):
            if count == 0:
                error(f"{modality}: {count} - FAILED")
            elif count < scene_count * 0.5:  # Less than 50% coverage
                warning(f"{modality}: {count:,} ({count/scene_count*100:.1f}% of scenes)")
            else:
                success(f"{modality}: {count:,} ({count/scene_count*100:.1f}% of scenes)")
    
    # Check for scenes without embeddings
    header("ASSESSMENT: Processing Gaps")
    cursor.execute("""
        SELECT COUNT(DISTINCT s.id)
        FROM scenes s
        LEFT JOIN embeddings e ON e.scene_id = s.id
        WHERE e.hash IS NULL
    """)
    scenes_no_embeds = cursor.fetchone()[0]
    
    if scenes_no_embeds > 0:
        error(f"{scenes_no_embeds:,} scenes have NO embeddings - silent failure in embedding pipeline")
        
        # Sample some scenes without embeddings
        cursor.execute("""
            SELECT s.id, s.start, s.end, s.meta
            FROM scenes s
            LEFT JOIN embeddings e ON e.scene_id = s.id
            WHERE e.hash IS NULL
            LIMIT 5
        """)
        warning("Sample scenes missing embeddings:")
        for row in cursor.fetchall():
            scene_id, start, end, meta = row
            info(f"  Scene {scene_id[:16]}... @ {start:.1f}-{end:.1f}s")
    else:
        success("All scenes have at least one embedding")
    
    # Check step logs for failures
    header("INVESTIGATION: Step Log Analysis")
    step_log = Path("L:/goodq4all/logs/steps.jsonl")
    
    if not step_log.exists():
        error(f"Step log not found at {step_log} - logging completely failed!")
        warning("This means ALL steps are running blind without logging")
    else:
        # Parse step log
        step_stats = defaultdict(Counter)
        errors = []
        
        with open(step_log, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    entry = json.loads(line.strip())
                    step_name = entry.get('step_name', 'unknown')
                    status = entry.get('status', 'unknown')
                    step_stats[step_name][status] += 1
                    
                    if status in ['error', 'failed', 'skipped'] and entry.get('error_msg'):
                        errors.append({
                            'line': line_num,
                            'step': step_name,
                            'status': status,
                            'error': entry['error_msg']
                        })
                except json.JSONDecodeError:
                    pass
        
        # Report step statistics
        success(f"Step log found with {sum(sum(c.values()) for c in step_stats.values()):,} total entries")
        
        warning("\nStep Success Rates:")
        for step_name in sorted(step_stats.keys()):
            counts = step_stats[step_name]
            total = sum(counts.values())
            ok_count = counts.get('ok', 0)
            skip_count = counts.get('skipped', 0)
            error_count = counts.get('error', 0) + counts.get('failed', 0)
            
            if error_count > 0:
                error(f"  {step_name}: {ok_count}/{total} OK, {error_count} FAILED, {skip_count} SKIPPED")
            elif skip_count > total * 0.5:
                warning(f"  {step_name}: {ok_count}/{total} OK, {skip_count} SKIPPED")
            else:
                success(f"  {step_name}: {ok_count}/{total} OK")
        
        # Show recent errors
        if errors:
            header("EVIDENCE: Recent Errors")
            for err in errors[-10:]:
                error(f"Line {err['line']}: {err['step']} - {err['status']}")
                info(f"  {err['error'][:100]}")
    
    # Check for workspace artifacts
    header("FORENSICS: Workspace Artifacts")
    logs_dir = Path("L:/goodq4all/logs")
    
    workspace_dirs = [d for d in logs_dir.glob("watchdog_*") if d.is_dir()]
    if not workspace_dirs:
        warning("No watchdog workspaces found")
    else:
        success(f"Found {len(workspace_dirs)} watchdog workspaces")
        
        # Check latest workspace
        latest = max(workspace_dirs, key=lambda p: p.stat().st_mtime)
        info(f"Latest: {latest.name}")
        
        # Count artifacts in latest workspace
        video_folders = [d for d in latest.iterdir() if d.is_dir()]
        for vf in video_folders[:3]:
            info(f"\n  Video: {vf.name}")
            
            frames_dir = vf / "frames"
            if frames_dir.exists():
                frame_count = len(list(frames_dir.glob("*.jpg")))
                if frame_count == 0:
                    error(f"    Frames: 0 - extraction failed")
                else:
                    success(f"    Frames: {frame_count}")
            else:
                error(f"    Frames: missing directory")
            
            audio_dir = vf / "audio"
            if audio_dir.exists():
                audio_count = len(list(audio_dir.glob("*.wav")))
                if audio_count == 0:
                    error(f"    Audio: 0 - extraction failed")
                else:
                    success(f"    Audio: {audio_count}")
            else:
                error(f"    Audio: missing directory")
            
            metadata_file = vf / "metadata.json"
            if metadata_file.exists():
                success(f"    Metadata: present")
            else:
                error(f"    Metadata: missing")
    
    # Final assessment
    header("MISSION DEBRIEFING")
    
    critical_failures = []
    warnings_list = []
    
    if embed_count == 0:
        critical_failures.append("NO embeddings created - complete pipeline failure")
    elif embed_count < scene_count:
        warnings_list.append(f"Low embedding count ({embed_count}/{scene_count})")
    
    if scenes_no_embeds > scene_count * 0.1:
        critical_failures.append(f"{scenes_no_embeds} scenes missing embeddings")
    
    if not step_log.exists():
        critical_failures.append("Step logging completely failed")
    
    if critical_failures:
        print(f"\n{Colors.FAIL}{Colors.BOLD}CRITICAL FAILURES DETECTED:{Colors.END}")
        for failure in critical_failures:
            error(failure)
        print(f"\n{Colors.FAIL}Mission Status: COMPROMISED{Colors.END}")
        return 1
    elif warnings_list:
        print(f"\n{Colors.WARNING}{Colors.BOLD}WARNINGS:{Colors.END}")
        for warn in warnings_list:
            warning(warn)
        print(f"\n{Colors.WARNING}Mission Status: PARTIAL SUCCESS{Colors.END}")
        return 0
    else:
        print(f"\n{Colors.OK}{Colors.BOLD}✓ All systems operational{Colors.END}")
        print(f"{Colors.OK}Mission Status: SUCCESS{Colors.END}")
        return 0
    
    db.close()

if __name__ == '__main__':
    exit(main())
