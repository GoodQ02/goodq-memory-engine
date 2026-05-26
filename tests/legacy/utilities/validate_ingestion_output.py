#!/usr/bin/env python3
"""
[SEARCH] Mission Intel: Ingestion Output Validator
Analyzes ingestion results to detect silent failures, missing data, and quality issues.
"""
from __future__ import annotations
import json
import sqlite3
import sys
from pathlib import Path
from typing import Dict, Any, List, Set
from datetime import datetime
from collections import defaultdict

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    INFO = '\033[94m'
    SUCCESS = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def log_section(title: str):
    """Print a formatted section header"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}╔═══ {title} ═══╗{Colors.END}")


def log_success(msg: str):
    print(f"{Colors.SUCCESS}[SYMBOL]{Colors.END} {msg}")


def log_warning(msg: str):
    print(f"{Colors.WARNING}[SYMBOL]{Colors.END} {msg}")


def log_error(msg: str):
    print(f"{Colors.FAIL}[SYMBOL]{Colors.END} {msg}")


def log_info(msg: str):
    print(f"{Colors.INFO}ℹ{Colors.END} {msg}")


def check_memory_db(db_path: Path) -> Dict[str, Any]:
    """Check memory database for scenes and embeddings"""
    log_section("Memory Database Status")
    
    if not db_path.exists():
        log_error(f"Memory database not found: {db_path}")
        return {'status': 'missing', 'scenes': 0, 'embeddings': 0}
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check scenes
        cursor.execute("SELECT COUNT(*) FROM scenes")
        scene_count = cursor.fetchone()[0]
        log_info(f"Total scenes: {scene_count}")
        
        # Check embeddings
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        embedding_count = cursor.fetchone()[0]
        log_info(f"Total embeddings: {embedding_count}")
        
        # Check for scenes with errors
        cursor.execute("""
            SELECT COUNT(*) FROM scenes 
            WHERE meta LIKE '%error%' OR meta LIKE '%Error%' OR meta LIKE '%ERROR%'
        """)
        error_count = cursor.fetchone()[0]
        if error_count > 0:
            log_warning(f"Scenes with errors: {error_count}")
        
        # Check step logs for failures
        cursor.execute("""
            SELECT step_name, COUNT(*) as count
            FROM step_logs
            WHERE status = 'error'
            GROUP BY step_name
            ORDER BY count DESC
        """)
        error_steps = cursor.fetchall()
        if error_steps:
            log_warning("Step failures detected:")
            for step_name, count in error_steps:
                print(f"  - {step_name}: {count} failures")
        
        conn.close()
        
        result = {
            'status': 'ok',
            'scenes': scene_count,
            'embeddings': embedding_count,
            'errors': error_count,
            'error_steps': error_steps
        }
        
        if scene_count == 0:
            log_error("[FAIL] CRITICAL: No scenes found in database!")
            result['status'] = 'empty'
        elif embedding_count == 0:
            log_error("[FAIL] CRITICAL: No embeddings found in database!")
            result['status'] = 'no_embeddings'
        elif error_count > 0 or error_steps:
            log_warning("[WARN]  Database contains errors but has some data")
            result['status'] = 'partial'
        else:
            log_success("[SYMBOL] Database appears healthy")
        
        return result
        
    except Exception as e:
        log_error(f"Failed to query database: {e}")
        return {'status': 'error', 'message': str(e)}


def check_step_logs(log_dir: Path) -> Dict[str, Any]:
    """Analyze step logs for patterns"""
    log_section("Step Log Analysis")
    
    log_files = list(log_dir.glob("*.jsonl"))
    if not log_files:
        log_warning("No step log files found")
        return {'status': 'missing', 'total_steps': 0}
    
    log_info(f"Found {len(log_files)} log file(s)")
    
    step_stats = defaultdict(lambda: {'total': 0, 'ok': 0, 'error': 0, 'skipped': 0, 'timeout': 0})
    
    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        step_name = entry.get('step_name', 'unknown')
                        status = entry.get('status', 'unknown')
                        
                        step_stats[step_name]['total'] += 1
                        step_stats[step_name][status] += 1
                        
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            log_warning(f"Failed to read {log_file.name}: {e}")
    
    # Report on each step
    total_steps = sum(s['total'] for s in step_stats.values())
    total_errors = sum(s['error'] for s in step_stats.values())
    total_skipped = sum(s['skipped'] for s in step_stats.values())
    
    log_info(f"Total step executions: {total_steps}")
    
    if total_errors > 0:
        log_warning(f"Failed steps: {total_errors}")
        print("\n  Steps with failures:")
        for step, stats in sorted(step_stats.items(), key=lambda x: x[1]['error'], reverse=True):
            if stats['error'] > 0:
                error_rate = (stats['error'] / stats['total']) * 100 if stats['total'] > 0 else 0
                print(f"    • {step}: {stats['error']}/{stats['total']} ({error_rate:.1f}%)")
    
    if total_skipped > 0:
        log_info(f"Skipped steps: {total_skipped} (dedupe/cache hits)")
    
    # Check for missing expected steps
    expected_steps = {
        'image_ocr', 'image_caption', 'object_detect', 'face_embed',
        'image_embed_dino', 'image_embed_clip', 'text_embed',
        'audio_metadata', 'audio_diarize', 'audio_transcribe',
        'audio_emotion', 'sentiment', 'emotion_classify', 'tagger',
        'audio_embed_clap'
    }
    
    found_steps = set(step_stats.keys())
    missing_steps = expected_steps - found_steps
    
    if missing_steps:
        log_warning(f"Expected steps not found in logs: {', '.join(missing_steps)}")
    else:
        log_success("All expected pipeline steps found in logs")
    
    return {
        'status': 'partial' if total_errors > 0 else 'ok',
        'total_steps': total_steps,
        'total_errors': total_errors,
        'total_skipped': total_skipped,
        'step_stats': dict(step_stats),
        'missing_steps': list(missing_steps)
    }


def check_knowledge_graph(kg_path: Path) -> Dict[str, Any]:
    """Check knowledge graph database"""
    log_section("Knowledge Graph Status")
    
    if not kg_path.exists():
        log_warning(f"Knowledge graph not found: {kg_path}")
        return {'status': 'missing'}
    
    try:
        conn = sqlite3.connect(str(kg_path))
        cursor = conn.cursor()
        
        # Check nodes
        cursor.execute("SELECT COUNT(*) FROM nodes")
        node_count = cursor.fetchone()[0]
        log_info(f"Total nodes: {node_count}")
        
        # Check edges
        cursor.execute("SELECT COUNT(*) FROM edges")
        edge_count = cursor.fetchone()[0]
        log_info(f"Total edges: {edge_count}")
        
        # Check media nodes
        cursor.execute("SELECT COUNT(*) FROM media_nodes")
        media_count = cursor.fetchone()[0]
        log_info(f"Media nodes: {media_count}")
        
        # Check node types distribution
        cursor.execute("""
            SELECT type, COUNT(*) as count
            FROM nodes
            GROUP BY type
            ORDER BY count DESC
            LIMIT 10
        """)
        node_types = cursor.fetchall()
        if node_types:
            print("\n  Top node types:")
            for node_type, count in node_types:
                print(f"    • {node_type}: {count}")
        
        conn.close()
        
        result = {
            'status': 'ok' if node_count > 0 else 'empty',
            'nodes': node_count,
            'edges': edge_count,
            'media': media_count
        }
        
        if node_count == 0:
            log_warning("Knowledge graph is empty")
        else:
            log_success(f"Knowledge graph populated with {node_count} entities")
        
        return result
        
    except Exception as e:
        log_error(f"Failed to query knowledge graph: {e}")
        return {'status': 'error', 'message': str(e)}


def check_workspace_artifacts(workspace: Path) -> Dict[str, Any]:
    """Check extracted frames and audio files"""
    log_section("Workspace Artifacts")
    
    if not workspace.exists():
        log_warning(f"Workspace not found: {workspace}")
        return {'status': 'missing'}
    
    # Count frames
    frame_files = list(workspace.glob("**/frames/*.jpg")) + list(workspace.glob("**/frames/*.png"))
    log_info(f"Extracted frames: {len(frame_files)}")
    
    # Count audio clips
    audio_files = list(workspace.glob("**/audio/*.wav")) + list(workspace.glob("**/audio/*.mp3"))
    log_info(f"Extracted audio clips: {len(audio_files)}")
    
    # Check for empty directories
    video_dirs = [d for d in workspace.iterdir() if d.is_dir() and d.name not in ('_archive', '__pycache__')]
    
    if video_dirs:
        print(f"\n  Processed videos: {len(video_dirs)}")
        for vid_dir in video_dirs[:5]:  # Show first 5
            frames_in_dir = len(list((vid_dir / 'frames').glob('*.*'))) if (vid_dir / 'frames').exists() else 0
            audio_in_dir = len(list((vid_dir / 'audio').glob('*.*'))) if (vid_dir / 'audio').exists() else 0
            print(f"    • {vid_dir.name}: {frames_in_dir} frames, {audio_in_dir} audio clips")
    
    result = {
        'status': 'ok' if frame_files or audio_files else 'empty',
        'frames': len(frame_files),
        'audio': len(audio_files),
        'video_dirs': len(video_dirs)
    }
    
    if not frame_files and not audio_files:
        log_error("[FAIL] CRITICAL: No extracted artifacts found!")
        result['status'] = 'empty'
    elif len(frame_files) < len(audio_files) * 0.5:
        log_warning("[WARN]  Significantly fewer frames than audio clips")
    else:
        log_success("[SYMBOL] Artifacts extracted successfully")
    
    return result


def main():
    """Run comprehensive validation"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║        [SEARCH] Mission Intel: Ingestion Output Validator          ║")
    print("║        Detecting Silent Failures & Quality Issues            ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(Colors.END)
    
    # Paths
    project_root = Path("L:/goodq4all")
    data_dir = project_root / "data"
    logs_dir = project_root / "logs"
    
    results = {}
    
    # Check memory database
    memory_db = data_dir / "memory.db"
    results['memory_db'] = check_memory_db(memory_db)
    
    # Check step logs
    results['step_logs'] = check_step_logs(logs_dir)
    
    # Check knowledge graph
    kg_db = data_dir / "knowledge_graph.db"
    results['knowledge_graph'] = check_knowledge_graph(kg_db)
    
    # Check workspace artifacts
    workspace = logs_dir / "ingest_full"
    if not workspace.exists():
        # Try alternate locations
        workspace_candidates = list(logs_dir.glob("watchdog_*"))
        if workspace_candidates:
            workspace = workspace_candidates[-1]  # Most recent
    results['artifacts'] = check_workspace_artifacts(workspace)
    
    # Final summary
    log_section("Mission Summary")
    
    all_ok = True
    critical_failures = []
    warnings = []
    
    # Check each component
    if results['memory_db']['status'] in ('missing', 'empty', 'no_embeddings'):
        critical_failures.append("Memory database is empty or missing embeddings")
        all_ok = False
    elif results['memory_db']['status'] == 'partial':
        warnings.append(f"Memory database has {results['memory_db'].get('errors', 0)} errors")
    
    if results['step_logs'].get('total_errors', 0) > 0:
        warnings.append(f"Step logs show {results['step_logs']['total_errors']} failures")
        if results['step_logs']['total_errors'] > results['step_logs'].get('total_steps', 1) * 0.5:
            critical_failures.append("More than 50% of steps failed")
            all_ok = False
    
    if results['step_logs'].get('missing_steps'):
        warnings.append(f"{len(results['step_logs']['missing_steps'])} expected steps not executed")
    
    if results['artifacts']['status'] == 'empty':
        critical_failures.append("No workspace artifacts (frames/audio) found")
        all_ok = False
    
    if results['knowledge_graph']['status'] == 'empty':
        warnings.append("Knowledge graph is empty")
    
    # Print summary
    if critical_failures:
        print(f"\n{Colors.FAIL}{Colors.BOLD}[FAIL] MISSION FAILED - Critical Issues Detected:{Colors.END}")
        for failure in critical_failures:
            print(f"  • {failure}")
    
    if warnings:
        print(f"\n{Colors.WARNING}[WARN]  Warnings:{Colors.END}")
        for warning in warnings:
            print(f"  • {warning}")
    
    if all_ok and not warnings:
        print(f"\n{Colors.SUCCESS}{Colors.BOLD}[SYMBOL] MISSION SUCCESS - All Systems Operational{Colors.END}")
        print(f"  • {results['memory_db']['scenes']} scenes processed")
        print(f"  • {results['memory_db']['embeddings']} embeddings created")
        print(f"  • {results['artifacts']['frames']} frames extracted")
        print(f"  • {results['artifacts']['audio']} audio clips processed")
        print(f"  • {results['knowledge_graph']['nodes']} knowledge graph entities")
    elif all_ok:
        print(f"\n{Colors.SUCCESS}[SYMBOL] MISSION PARTIAL SUCCESS{Colors.END}")
        print("  Pipeline completed with warnings but produced usable output")
    
    # Export detailed report
    report_path = logs_dir / "validation_report.json"
    report_path.write_text(json.dumps(results, indent=2), encoding='utf-8')
    log_info(f"Detailed report saved to: {report_path}")
    
    # Return exit code
    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    main()
