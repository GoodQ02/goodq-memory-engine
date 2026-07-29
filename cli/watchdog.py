#!/usr/bin/env python3
"""
GoodQ Watchdog - Automatic File Ingestion Monitor
Monitors import_inbox for new files and automatically processes them.
Now with AI-powered Control Agent integration for intelligent orchestration.
"""

from __future__ import annotations
import sys
import time
import hashlib
import shutil
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Set, Dict, List, Any
from queue import Queue, Empty
from threading import Thread, Event, RLock
import json
import os
import uuid
import tempfile

# Add repo root to path for imports
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from steps.common.atomic_io import atomic_write_json
from steps.common.config_loader import get_runtime_paths, load_configs
from steps.common.profile_config import require_wsl_audio, wsl_audio_auto_enabled

_LOG_FORMAT = '%(asctime)s [%(levelname)s] %(message)s'
_BOOTSTRAP_LOG_PATH = Path(tempfile.gettempdir()) / "goodq_watchdog_bootstrap.log"
_CONSOLE_HANDLER = logging.StreamHandler(sys.stderr)
_CONSOLE_HANDLER.setFormatter(logging.Formatter(_LOG_FORMAT))
_BOOTSTRAP_FILE_HANDLER = logging.FileHandler(_BOOTSTRAP_LOG_PATH, encoding='utf-8')
_BOOTSTRAP_FILE_HANDLER.setFormatter(logging.Formatter(_LOG_FORMAT))

logging.basicConfig(
    level=logging.INFO,
    format=_LOG_FORMAT,
    handlers=[_CONSOLE_HANDLER, _BOOTSTRAP_FILE_HANDLER],
    force=True,
)


# ASCII filter to replace emojis with text equivalents
class ASCIIFilter(logging.Filter):
    # Map emojis to ASCII equivalents for Windows console
    EMOJI_MAP = {
        '[SYMBOL]': '[CLIPBOARD]',
        '[TIMER]': '[TIMER]',
        '[SYMBOL]': '[VIDEO]',
        '[OK]': '[OK]',
        '[PASS]': '[SUCCESS]',
        '[FAIL]': '[ERROR]',
        '[WARN]': '[WARN]',
        '[SYMBOL]': '[STATS]',
        '[TARGET]': '[TARGET]',
        '[SYMBOL]': '[SAVE]',
        '[SEARCH]': '[SEARCH]',
        '[DIR]': '[FOLDER]',
        '[SYMBOL]': '[CAMERA]',
        '[SYMBOL]': '[MIC]',
        '[SYMBOL]': '[MUSIC]',
        '[SYMBOL]️': '[IMAGE]',
        '[SYMBOL]': '[DOC]',
        '[SYMBOL]': '[AUDIO]',
    }
    
    def filter(self, record):
        if hasattr(record, 'msg'):
            msg = str(record.msg)
            for emoji, replacement in self.EMOJI_MAP.items():
                msg = msg.replace(emoji, replacement)
            record.msg = msg
        return True


_CONSOLE_HANDLER.addFilter(ASCIIFilter())
_BOOTSTRAP_FILE_HANDLER.addFilter(ASCIIFilter())
logger = logging.getLogger(__name__)


def safe_move_file(src: Path, dst: Path) -> Path:
    """
    Safely move a file from src to dst.
    - If dst exists, finds a unique name by appending _1, _2, etc.
    - If cross-device or permission issue with rename, falls back to copy2 + unlink.
    """
    src = Path(src)
    dst = Path(dst)
    
    # 1. Resolve naming collision
    if dst.exists():
        parent = dst.parent
        stem = dst.stem
        suffix = dst.suffix
        counter = 1
        while True:
            candidate = parent / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                dst = candidate
                break
            counter += 1
            if counter > 1000:
                raise RuntimeError(f"Too many file naming collisions (limit 1000) for {dst.name}")

    # 2. Ensure parent directory exists
    dst.parent.mkdir(parents=True, exist_ok=True)

    # 3. Attempt move
    try:
        # Standard fast rename
        src.rename(dst)
        return dst
    except Exception as e:
        # Fallback to copy + delete (robust across partitions/drives)
        logger.warning(f"Rename failed ({e}), falling back to copy+unlink for {src.name}")
        try:
            shutil.copy2(src, dst)
            src.unlink(missing_ok=True)
            return dst
        except Exception as copy_err:
            # Clean up the partial destination file if it was created during failed copy/delete
            if dst.exists():
                try:
                    dst.unlink(missing_ok=True)
                except Exception as cleanup_err:
                    logger.warning(f"Failed to clean up partial file {dst} after copy failure: {cleanup_err}")
            raise OSError(f"Failed to move file from {src} to {dst} via rename or copy/delete fallback: {copy_err}")



def _resolve_watchdog_paths(cfg: Dict[str, Any]) -> Dict[str, Path]:
    runtime_paths = get_runtime_paths(
        cfg,
        "import_inbox",
        "processing",
        "processed",
        "failed",
        "log_dir",
        "watchdog_state_file",
        "watchdog_lock_file",
        require_canonical=False,
    )
    return {
        "watch_dir": Path(runtime_paths["import_inbox"]).resolve(),
        "processing_dir": Path(runtime_paths["processing"]).resolve(),
        "processed_dir": Path(runtime_paths["processed"]).resolve(),
        "failed_dir": Path(runtime_paths["failed"]).resolve(),
        "log_dir": Path(runtime_paths["log_dir"]).resolve(),
        "state_file": Path(runtime_paths["watchdog_state_file"]).resolve(),
        "lock_file": Path(runtime_paths["watchdog_lock_file"]).resolve(),
    }


def _configure_watchdog_logging(log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "watchdog.log"
    root_logger = logging.getLogger()
    formatter = logging.Formatter(_LOG_FORMAT)

    for handler in root_logger.handlers:
        handler.setFormatter(formatter)

    has_file_handler = False
    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            try:
                if Path(handler.baseFilename).resolve() == log_file.resolve():
                    has_file_handler = True
                    break
            except Exception:
                continue

    if not has_file_handler:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    if _BOOTSTRAP_FILE_HANDLER in root_logger.handlers:
        root_logger.removeHandler(_BOOTSTRAP_FILE_HANDLER)
        _BOOTSTRAP_FILE_HANDLER.close()

    return log_file

# Import Control Agent
try:
    from agents.control_agent import (
        ControlAgent,
        CONTROL_AGENT_STATUS_DISABLED_NO_LLM_CLIENT,
        CONTROL_AGENT_DISABLED_REASON_NO_LLM_CLIENT,
    )
    CONTROL_AGENT_AVAILABLE = True
except ImportError:
    CONTROL_AGENT_AVAILABLE = False
    CONTROL_AGENT_STATUS_DISABLED_NO_LLM_CLIENT = "disabled_no_llm_client"
    CONTROL_AGENT_DISABLED_REASON_NO_LLM_CLIENT = "Control Agent module unavailable"
    logger.warning("Control Agent not available - running without AI orchestration")

# File type configuration
SUPPORTED_VIDEO = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
SUPPORTED_AUDIO = {'.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.wma'}
SUPPORTED_IMAGE = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
SUPPORTED_DOCUMENT = {'.pdf', '.txt', '.md', '.doc', '.docx'}

# Processing configuration
POLL_INTERVAL = 2.0  # seconds
STABILITY_WAIT = 3.0  # wait for file to stop changing
MAX_WORKERS = 1  # process one at a time for now
REPROCESS_ON_START = False  # don't reprocess files already marked as processed


class FileState:
    """Track file processing state"""
    def __init__(self, path: Path):
        self.path = path
        self.size = path.stat().st_size if path.exists() else 0
        self.mtime = path.stat().st_mtime if path.exists() else 0
        self.hash: Optional[str] = None
        self.last_check = time.time()
        self.stable = False
        
    def is_stable(self) -> bool:
        """Check if file has stopped changing"""
        if not self.path.exists():
            return False
            
        # Guard: 0-byte files are not ready or valid for ingestion
        current_size = self.path.stat().st_size
        if current_size == 0:
            return False
            
        current_mtime = self.path.stat().st_mtime
        
        if current_size == self.size and current_mtime == self.mtime:
            # Check if locked by another writing process (Windows-specific check)
            if os.name == 'nt':
                try:
                    with open(self.path, 'ab'):
                        pass
                except PermissionError as e:
                    # WinError 32: Sharing violation, WinError 33: Lock violation
                    if getattr(e, 'winerror', None) in (32, 33):
                        logger.debug(f"File {self.path.name} is locked by another process (WinError {e.winerror}), waiting...")
                        return False
            
            elapsed = time.time() - self.last_check
            return elapsed >= STABILITY_WAIT
        
        # File changed, reset
        self.size = current_size
        self.mtime = current_mtime
        self.last_check = time.time()
        return False
    
    def compute_hash(self) -> str:
        """Compute SHA256 hash of file"""
        if self.hash:
            return self.hash
        sha256 = hashlib.sha256()
        with open(self.path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        self.hash = sha256.hexdigest()
        return self.hash


class ProcessedRegistry:
    """Track which files have been processed"""
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.processed: Dict[str, Dict] = {}
        self.load()
    
    def load(self):
        """Load processed file registry"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self.processed = json.load(f)
                logger.info(f"Loaded {len(self.processed)} processed file records")
            except Exception as e:
                logger.error(f"Failed to load state file: {e}")
                self.processed = {}
    
    def save(self):
        """Save processed file registry"""
        with self.lock:
            try:
                atomic_write_json(self.state_file, self.processed)
            except Exception as e:
                logger.error(f"Failed to save state file: {e}")
    
    def is_processed(self, file_hash: str) -> bool:
        """Check if file hash has been processed successfully"""
        with self.lock:
            if file_hash not in self.processed:
                return False
            record = self.processed[file_hash]
            return record.get('status') == 'success'

    def coverage_decision(
        self,
        file_hash: str,
        requested_stages: Dict[str, Any],
    ) -> str:
        """Return the single Watchdog authority decision for a requested stage set.

        A successful content hash alone is deliberately insufficient for a
        recovery request: every requested stage must have a successful record
        with matching provenance.  Legacy success-only records remain readable
        but are not evidence that a newly requested stage is complete.
        """
        with self.lock:
            record = self.processed.get(file_hash)
            if not isinstance(record, dict):
                return "recover"
            if record.get("status") != "success":
                return "recover"
            coverage = record.get("stage_coverage")
            if not isinstance(coverage, dict):
                return "recover"
            for stage, provenance in requested_stages.items():
                entry = coverage.get(stage)
                if not isinstance(entry, dict) or entry.get("status") != "success":
                    return "recover"
                if entry.get("provenance") != provenance:
                    return "recover"
            return "skip"
    
    def mark_processed(
        self,
        file_hash: str,
        original_name: str,
        status: str = 'success',
        run_id: Optional[str] = None,
        stage_coverage: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        """Mark file as processed"""
        with self.lock:
            record: Dict[str, Any] = {
                'original_name': original_name,
                'status': status,
                'run_id': run_id,
                'timestamp': datetime.now().isoformat()
            }
            if stage_coverage is not None:
                record['stage_coverage'] = stage_coverage
            self.processed[file_hash] = record
            self.save()

    def mark_failed(
        self,
        file_hash: str,
        original_name: str,
        error: str,
        run_id: Optional[str] = None,
    ):
        """Mark file as failed"""
        with self.lock:
            self.processed[file_hash] = {
                'original_name': original_name,
                'status': 'failed',
                'error': error,
                'run_id': run_id,
                'timestamp': datetime.now().isoformat()
            }
            self.save()


class WatchdogProcessor:
    """Main watchdog processor"""
    def __init__(self, cfg: Dict[str, Any], resolved_paths: Optional[Dict[str, Path]] = None):
        self._cfg_base = cfg
        runtime_paths = resolved_paths or _resolve_watchdog_paths(cfg)
        self.watch_dir = runtime_paths["watch_dir"]
        self.processing_dir = runtime_paths["processing_dir"]
        self.processed_dir = runtime_paths["processed_dir"]
        self.failed_dir = runtime_paths["failed_dir"]
        self.log_dir = runtime_paths["log_dir"]
        self.state_file = runtime_paths["state_file"]
        self.lock_file = runtime_paths["lock_file"]
        self.registry = ProcessedRegistry(self.state_file)
        self.queue = Queue()
        self.shutdown = Event()
        self.file_states: Dict[str, FileState] = {}
        
        # Initialize Control Agent if available
        self.control_agent = None
        self.control_agent_status = "import_unavailable"
        self.control_agent_reason: Optional[str] = None
        if CONTROL_AGENT_AVAILABLE:
            self.control_agent_status = CONTROL_AGENT_STATUS_DISABLED_NO_LLM_CLIENT
            self.control_agent_reason = CONTROL_AGENT_DISABLED_REASON_NO_LLM_CLIENT
            logger.info("[BOT] Control Agent disabled: no llm_client injection")
        
        # Ensure directories exist
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self.processing_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Watching directory: {self.watch_dir}")

    def cleanup_stale_processing_files(self):
        """Clean up leftover temp files or folders in the processing directory from previous runs."""
        logger.info("Checking for stale temporary files in processing directory...")
        if not self.processing_dir.exists():
            return
        
        cleaned_count = 0
        try:
            for item in self.processing_dir.iterdir():
                if item.name.startswith('.'):
                    continue
                
                # Check if it's a temp/processing folder or file
                is_stale = False
                if item.is_dir():
                    # Temporary folders start with prefixes or match standard subdirs
                    if (item.name.startswith("video_") or 
                        item.name.startswith("audio_") or 
                        item.name.startswith("image_") or 
                        item.name.startswith("doc_") or
                        item.name in ("chunks", "audio", "video", "metadata")):
                        is_stale = True
                elif item.is_file():
                    # Direct ingestion leaves files directly in processing dir
                    ext = item.suffix.lower()
                    if ext in SUPPORTED_VIDEO.union(SUPPORTED_AUDIO) or ext == ".tmp":
                        is_stale = True
                
                if is_stale:
                    try:
                        logger.info(f"Removing stale processing item: {item.name}")
                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()
                        cleaned_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to remove stale item {item.name}: {e}")
        except Exception as e:
            logger.error(f"Error scanning processing directory: {e}")
            
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} stale items from the processing directory.")
        else:
            logger.info("Processing directory is clean.")
    
    def _build_run_config(self, pipeline_name: str, run_id: Optional[str] = None) -> Dict[str, Any]:
        """Load configs and attach a run context for mission logging."""
        import subprocess

        cfg: Dict[str, Any] = dict(self._cfg_base) if isinstance(self._cfg_base, dict) else {}
        run_context: Dict[str, Any] = {
            'id': run_id or str(uuid.uuid4()),
            'pipeline': pipeline_name,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'timer_unit': 'ms',
            'control_agent_status': self.control_agent_status,
            'control_agent_reason': self.control_agent_reason,
        }

        try:
            git_proc = subprocess.run(
                ['git', '-C', str(REPO_ROOT), 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                check=False,
            )
            if git_proc.returncode == 0 and git_proc.stdout.strip():
                run_context['git_sha'] = git_proc.stdout.strip()
        except Exception as e:
            logger.debug(f"Failed to get git SHA: {e}")

        existing_run = cfg.get('run') if isinstance(cfg, dict) else None
        if isinstance(existing_run, dict):
            run_copy = dict(existing_run)
            run_copy.update(run_context)
            cfg['run'] = run_copy
        else:
            cfg['run'] = run_context
        return cfg
    
    def get_file_type(self, path: Path) -> Optional[str]:
        """Determine file type"""
        ext = path.suffix.lower()
        if ext in SUPPORTED_VIDEO:
            return 'video'
        elif ext in SUPPORTED_AUDIO:
            return 'audio'
        elif ext in SUPPORTED_IMAGE:
            return 'image'
        elif ext in SUPPORTED_DOCUMENT:
            return 'document'
        return None
    
    def scan_directory(self) -> List[Path]:
        """Scan watch directory for new files"""
        if not self.watch_dir.exists():
            logger.warning(f"Watch directory does not exist: {self.watch_dir}")
            return []
        
        files = []
        for item in self.watch_dir.iterdir():
            if item.is_file() and not item.name.startswith('.'):
                # Ignore already-handled marker prefixes to prevent requeue/rename churn.
                if item.name.startswith('PROCESSED_') or item.name.startswith('FAILED_'):
                    continue
                # Check if supported file type
                if self.get_file_type(item):
                    files.append(item)
        return files
    
    def check_video_completion_on_disk(self, file_path: Path, file_hash: str) -> bool:
        """Check if the video has a complete temporal_index indicating phase 6 completion."""
        try:
            # Check potential processing paths (both stem and hash based)
            candidates = [
                self.processing_dir / file_path.stem / 'video' / 'temporal_index.json',
                self.processing_dir / file_path.stem / 'temporal_index.json',
                self.processing_dir / file_hash / 'video' / 'temporal_index.json',
                self.processing_dir / file_hash / 'temporal_index.json'
            ]
            for candidate in candidates:
                if candidate.exists():
                    try:
                        with open(candidate, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if isinstance(data, dict) and data.get('phase6_complete') is True:
                            # Verify that it is not a progressive/partial run
                            db_dir_val = self._cfg_base.get('paths', {}).get('db_dir')
                            if db_dir_val:
                                db_path = Path(db_dir_val) / "ucf_ledger.db"
                                if db_path.exists():
                                    import sqlite3
                                    conn = sqlite3.connect(db_path)
                                    cursor = conn.cursor()
                                    cursor.execute(
                                        "SELECT count(*) FROM context_frames WHERE video_hash = ? AND worker_name = 'video_scene_detect'",
                                        (file_hash,)
                                    )
                                    db_scenes = cursor.fetchone()[0]
                                    conn.close()
                                    
                                    idx_scenes = data.get('total_scenes', 0)
                                    if db_scenes > 0 and idx_scenes < db_scenes:
                                        logger.warning(
                                            f"Temporal index has {idx_scenes} scenes, but ucf_ledger.db has {db_scenes} detected scenes. "
                                            "Skipping progressive index to force full resumption."
                                        )
                                        continue
                            
                            logger.debug(f"Found completed phase6 index at {candidate}")
                            return True
                    except Exception as e:
                        logger.debug(f"Failed to read/parse candidate {candidate}: {e}")
        except Exception as e:
            logger.warning(f"Error checking video completion on disk for {file_path.name}: {e}")
        return False

    def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Starting file monitor...")
        
        while not self.shutdown.is_set():
            try:
                # Scan for files
                files = self.scan_directory()
                
                # Update file states
                current_paths = {str(f) for f in files}
                
                # Remove states for files that no longer exist
                to_remove = [p for p in self.file_states.keys() if p not in current_paths]
                for p in to_remove:
                    del self.file_states[p]
                
                # Check each file
                for file_path in files:
                    path_str = str(file_path)
                    
                    # Create or update file state
                    if path_str not in self.file_states:
                        self.file_states[path_str] = FileState(file_path)
                        logger.info(f"New file detected: {file_path.name}")
                    
                    state = self.file_states[path_str]
                    
                    # Check if file is stable
                    if state.is_stable() and not state.stable:
                        state.stable = True
                        logger.info(f"File stable: {file_path.name} ({state.size} bytes)")
                        
                        # Compute hash and check if already processed
                        file_hash = state.compute_hash()
                        
                        # Check registry first, then perform structural disk check for completion
                        already_processed = self.registry.is_processed(file_hash)
                        if not already_processed:
                            already_processed = self.check_video_completion_on_disk(file_path, file_hash)
                            if already_processed:
                                logger.info(f"Detected previous completed ingestion for {file_path.name} (hash: {file_hash[:8]}...) on disk. Syncing registry.")
                                self.registry.mark_processed(file_hash, file_path.name, 'success', run_id='pre-existing-on-disk')
                        
                        if already_processed:
                            logger.info(f"File already processed (hash: {file_hash[:8]}...), skipping: {file_path.name}")
                            # Update progress tracker so the UI reflects success
                            try:
                                from steps.common.progress_tracker import start_processing, update_step, finish_processing
                                start_processing(file_path.name, total_steps=1, run_id='pre-existing-on-disk')
                                update_step("completed", 1)
                                finish_processing("completed")
                            except Exception as pe:
                                logger.error(f"Failed to update progress tracker for pre-processed file: {pe}")
                            
                            # Move the file to the processed directory
                            processed_path = self.processed_dir / f"PROCESSED_{file_path.name}"
                            try:
                                actual_processed_path = safe_move_file(file_path, processed_path)
                                logger.info(f"Moved pre-processed file to processed directory: {actual_processed_path.name}")
                            except Exception as me:
                                logger.error(f"Failed to move pre-processed file to processed directory: {me}")
                                # Fallback to renaming in inbox
                                self.mark_file_processed(file_path)
                        else:
                            # Add to processing queue
                            self.queue.put((file_path, file_hash))
                            logger.info(f"Queued for processing: {file_path.name}")
                
                time.sleep(POLL_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                time.sleep(POLL_INTERVAL)
    
    def mark_file_processed(self, file_path: Path):
        """Mark file as processed by renaming"""
        try:
            # Idempotency guard: avoid repeated prefix expansion on already marked files.
            if file_path.name.startswith('PROCESSED_'):
                logger.debug(f"Already marked processed, skipping rename: {file_path.name}")
                return
            new_name = f"PROCESSED_{file_path.name}"
            new_path = file_path.parent / new_name
            actual_path = safe_move_file(file_path, new_path)
            logger.debug(f"Marked as processed: {actual_path.name}")
        except Exception as e:
            logger.error(f"Failed to rename processed file: {e}")
    
    def process_file(self, file_path: Path, file_hash: str) -> bool:
        """Process a single file with AI Control Agent monitoring"""
        # Import progress tracker
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from steps.common.progress_tracker import start_processing, finish_processing, add_error

        file_type = self.get_file_type(file_path)
        logger.info(f"Processing {file_type}: {file_path.name}")
        run_id = str(uuid.uuid4())
        logger.info(f"[RUN] run_id={run_id} file={file_path.name}")

        # Notify Control Agent of new file
        if self.control_agent:
            self.control_agent.on_file_detected(file_path.name, file_type, file_path.stat().st_size)
        
        # Start progress tracking
        total_steps = 20  # Estimate for video processing
        start_processing(file_path.name, total_steps, run_id=run_id)
        
        # Move to processing directory
        processing_path = self.processing_dir / file_path.name
        try:
            shutil.copy2(file_path, processing_path)
            logger.debug(f"Copied to processing: {processing_path}")
        except Exception as e:
            logger.error(f"Failed to copy file: {e}")
            add_error(f"Failed to copy file: {e}", "file_copy")
            finish_processing("failed")
            self.registry.mark_failed(file_hash, file_path.name, str(e), run_id=run_id)
            
            # Let Control Agent analyze the failure
            if self.control_agent:
                diagnosis = self.control_agent.analyze_error(
                    error=str(e),
                    context={'step': 'file_copy', 'file': file_path.name}
                )
                logger.info(f"[BOT] AI Diagnosis: {diagnosis.get('diagnosis', 'No diagnosis available')}")
            
            return False
        
        # Call ingestion pipeline
        success = False
        error_msg = None
        
        try:
            # Notify Control Agent that processing is starting
            if self.control_agent:
                self.control_agent.on_processing_start(file_path.name, file_type)

            if file_type == 'video':
                success = self.ingest_video(processing_path, run_id)
            elif file_type == 'audio':
                success = self.ingest_audio(processing_path, run_id)
            elif file_type == 'image':
                success = self.ingest_image(processing_path, run_id)
            elif file_type == 'document':
                success = self.ingest_document(processing_path, run_id)
            else:
                error_msg = f"Unsupported file type: {file_type}"
                logger.error(error_msg)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Processing failed: {e}", exc_info=True)
            
            # Let Control Agent analyze the failure
            if self.control_agent:
                diagnosis = self.control_agent.analyze_error(
                    error=str(e),
                    context={'step': 'ingestion', 'file': file_path.name, 'file_type': file_type}
                )
                logger.info(f"[BOT] AI Diagnosis: {diagnosis.get('diagnosis', 'Processing error')}")
                
                # Check if Control Agent recommends a retry strategy
                if diagnosis.get('recommended_action') == 'retry_with_changes':
                    logger.info(f"[BOT] AI Recommendation: {diagnosis.get('changes', 'No specific changes suggested')}")
        
        # Handle result
        if success:
            logger.info(f"[OK] Successfully processed: {file_path.name}")
            finish_processing("completed")
            self.registry.mark_processed(file_hash, file_path.name, 'success', run_id=run_id)
            
            # Notify Control Agent of success
            if self.control_agent:
                self.control_agent.on_processing_complete(file_path.name, success=True)
            
            # Move original to processed
            processed_path = self.processed_dir / f"PROCESSED_{file_path.name}"
            try:
                actual_processed_path = safe_move_file(file_path, processed_path)
                logger.debug(f"Moved to processed: {actual_processed_path}")
            except Exception as e:
                logger.error(f"Failed to move to processed: {e}")
            
            # Clean up processing copy
            try:
                processing_path.unlink(missing_ok=True)
            except Exception as e:
                logger.error(f"Failed to clean up processing file: {e}")
                
        else:
            logger.error(f"[FAIL] Failed to process: {file_path.name}")
            add_error(error_msg or 'Unknown error', "processing")
            finish_processing("failed")
            self.registry.mark_failed(file_hash, file_path.name, error_msg or 'Unknown error', run_id=run_id)
            
            # Notify Control Agent of failure
            if self.control_agent:
                self.control_agent.on_processing_complete(file_path.name, success=False, error=error_msg)
            
            # Move to failed
            failed_path = self.failed_dir / f"FAILED_{file_path.name}"
            try:
                actual_failed_path = safe_move_file(file_path, failed_path)
                logger.debug(f"Moved to failed: {actual_failed_path}")
            except Exception as e:
                logger.error(f"Failed to move to failed: {e}")
            
            # Clean up processing copy
            try:
                processing_path.unlink(missing_ok=True)
            except Exception as e:
                logger.error(f"Failed to clean up processing file: {e}")
        
        return success
    
    def ingest_video(self, video_path: Path, run_id: str) -> bool:
        """Ingest video file via CLI"""
        import subprocess
        
        # Create a stable input directory for this specific video
        # Use video hash to ensure uniqueness and avoid cleanup issues
        import hashlib
        video_hash = hashlib.sha256(video_path.name.encode()).hexdigest()[:16]
        temp_input = self.processing_dir / f"video_{video_hash}"
        temp_input.mkdir(parents=True, exist_ok=True)
        
        # Copy video to temp location (must stay there for entire ingestion)
        temp_video = temp_input / video_path.name
        try:
            if temp_video.exists():
                logger.debug(f"Temp video already exists, removing: {temp_video}")
                temp_video.unlink()
            
            file_size_mb = video_path.stat().st_size / (1024**2)
            logger.info(f"[COPY] Copying {file_size_mb:.1f}MB to processing area: {video_path.name}")
            logger.info(f"[COPY] From: {video_path}")
            logger.info(f"[COPY] To: {temp_video}")
            
            if file_size_mb > 100:
                with open(video_path, 'rb') as fsrc:
                    with open(temp_video, 'wb') as fdst:
                        copied = 0
                        chunk_size = 1024 * 1024 * 10  # 10MB chunks
                        while True:
                            chunk = fsrc.read(chunk_size)
                            if not chunk:
                                break
                            fdst.write(chunk)
                            copied += len(chunk)
                            progress_pct = (copied / video_path.stat().st_size) * 100
                            if copied % (chunk_size * 10) == 0:  # Log every 100MB
                                logger.info(f"[COPY] Progress: {progress_pct:.1f}% ({copied/(1024**2):.1f}MB)")
            else:
                shutil.copy2(video_path, temp_video)
            
            logger.info(f"[OK] Copy complete: {temp_video}")
        except Exception as e:
            logger.error(f"Failed to copy video to temp dir: {e}")
            return False
        
        # Use direct Python function call (no subprocess, better output visibility)
        from pipelines.direct_ingestion import run_direct_ingestion
        
        # Dynamic timeout based on file size (3 hours per GB, min 8 hours for thorough processing)
        file_size_gb = video_path.stat().st_size / (1024**3)
        timeout_seconds = max(28800, int(file_size_gb * 10800))  # At least 8 hours, +3hrs per GB
        logger.info(f"[TIMER]  Mission timeout: {timeout_seconds}s ({timeout_seconds/3600:.1f}h) for {file_size_gb:.2f}GB asset")
        logger.info(f"[SYMBOL] Asset: {video_path.name}")
        
        try:
            cfg = self._build_run_config("watchdog_video_ingest", run_id=run_id)
            result_dict = run_direct_ingestion(str(temp_video), cfg)
            
            # Simulate subprocess result for compatibility
            class Result:
                def __init__(self, success):
                    self.returncode = 0 if success else 1
                    self.stdout = ""
                    self.stderr = ""
            
            success = result_dict.get('status') == 'success'
            result = Result(success)
            
            if result.returncode == 0:
                logger.info("[PASS] Mission complete: Video ingestion successful")
                # Clean up temp directory ONLY on success
                try:
                    logger.debug(f"Cleaning up temp files: {temp_input}")
                    temp_video.unlink(missing_ok=True)
                    # Remove any other files that might have been created
                    for f in temp_input.iterdir():
                        if f.is_file():
                            f.unlink()
                    temp_input.rmdir()
                    logger.debug("[OK] Cleanup complete")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp directory: {e}")
                return True
            else:
                logger.error(f"[FAIL] Mission failed: Video ingestion returned code {result.returncode}")
                if result.stdout:
                    logger.error(f"STDOUT: {result.stdout}")
                if result.stderr:
                    logger.error(f"STDERR: {result.stderr}")
                # Keep temp files for debugging on failure
                logger.warning(f"Temp files preserved for debugging: {temp_input}")
                from steps.common.progress_tracker import add_error
                add_error(f"Video ingestion failed with code {result.returncode}", "ingestion")
                raise RuntimeError(f"Video ingestion failed: code {result.returncode}")
                
        except subprocess.TimeoutExpired as e:
            logger.error(f"[TIMER]  Mission timeout: Video ingestion exceeded {timeout_seconds}s")
            # Keep temp files for debugging on timeout
            logger.warning(f"Temp files preserved for debugging: {temp_input}")
            from steps.common.progress_tracker import add_error
            add_error(f"Video ingestion exceeded timeout of {timeout_seconds}s", "ingestion")
            raise e
        except Exception as e:
            logger.error(f"[FAIL] Mission error: {e}", exc_info=True)
            # Keep temp files for debugging on error
            logger.warning(f"Temp files preserved for debugging: {temp_input}")
            from steps.common.progress_tracker import add_error
            add_error(str(e), "ingestion")
            raise e
    
    def ingest_audio(self, audio_path: Path, run_id: str) -> bool:
        """Ingest standalone audio, preferring WSL unified audio when requested."""
        from steps.common.conda_runner import run_conda_step, StepExecutionError
        from steps.common.tag_utils import canonicalize_taxonomy

        audio_hash = hashlib.sha256(audio_path.name.encode()).hexdigest()[:16]
        temp_input = self.processing_dir / f"audio_{audio_hash}"
        temp_input.mkdir(parents=True, exist_ok=True)

        temp_audio = temp_input / audio_path.name
        try:
            if temp_audio.exists():
                logger.debug(f"Temp audio already exists, removing: {temp_audio}")
                temp_audio.unlink()
            logger.info(f"[SYMBOL] Copying asset to processing area: {audio_path.name}")
            shutil.copy2(audio_path, temp_audio)
            logger.debug(f"[OK] Copy complete: {temp_audio}")
        except Exception as e:
            logger.error(f"Failed to copy audio to temp dir: {e}")
            return False

        file_size_gb = audio_path.stat().st_size / (1024**3)
        timeout_seconds = max(28800, int(file_size_gb * 10800))
        logger.info(f"[TIMER]  Mission timeout: {timeout_seconds}s ({timeout_seconds/3600:.1f}h) for {file_size_gb:.2f}GB asset")
        logger.info(f"[SYMBOL] Asset: {audio_path.name}")
        start_time = time.time()

        # Per-step timeout for conda runner (10 minutes)
        os.environ["GOODQ_STEP_TIMEOUT_MS"] = str(600_000)

        cfg = self._build_run_config("watchdog_audio_ingest", run_id=run_id)
        item: Dict[str, Any] = {
            "modality": "audio",
            "source_path": str(temp_audio),
            "filename": audio_path.name,
        }

        def _check_timeout() -> bool:
            if time.time() - start_time > timeout_seconds:
                logger.error(f"[TIMER]  Mission timeout: Audio ingestion exceeded {timeout_seconds}s")
                return False
            return True

        def _write_audio_result_sidecar() -> None:
            self.processed_dir.mkdir(parents=True, exist_ok=True)
            sidecar_path = self.processed_dir / f"{audio_path.stem}.{audio_hash}.audio_result.json"
            payload = dict(item)
            payload.update(
                {
                    "source_file": audio_path.name,
                    "run_id": run_id,
                    "audio_hash": audio_hash,
                    "saved_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            atomic_write_json(sidecar_path, payload)
            logger.info(f"[AUDIO] Wrote standalone audio result sidecar: {sidecar_path}")

        def _try_wsl_unified_audio() -> bool:
            if not bool(wsl_audio_auto_enabled() or require_wsl_audio()):
                return False

            if shutil.which("wsl") is None:
                message = "WSL unified audio requested but wsl command is unavailable"
                if require_wsl_audio():
                    raise RuntimeError(message)
                logger.warning(f"[AUDIO] {message}; falling back to Conda audio step runner")
                return False

            from steps.audio.audio_wsl2_bridge import audio_unified_wsl2

            try:
                from steps.common.progress_tracker import get_tracker
                tracker = get_tracker()
                tracker.update_step(
                    "Analyzing standalone audio (WSL2)",
                    1,
                    {
                        "stage": "audio_unified_wsl2",
                        "run_id": run_id,
                        "file": audio_path.name,
                    },
                )
            except Exception as progress_error:
                logger.warning(f"[AUDIO] Failed to update WSL audio progress: {progress_error}")

            logger.info(f"[AUDIO] Running standalone audio through WSL2 unified backend: {audio_path.name}")
            result = audio_unified_wsl2(str(temp_audio), scene_id=audio_hash, duration=None)

            if not isinstance(result, dict):
                message = f"WSL unified audio returned unexpected payload: {type(result).__name__}"
            elif str(result.get("status", "")).strip().lower() == "error":
                message = str(
                    result.get("error")
                    or result.get("bridge_error_reason")
                    or "WSL unified audio error"
                ).strip()
            else:
                item.update(result)
                item["audio_backend_selected"] = "wsl"
                item["audio_backend_reason"] = "watchdog_audio_wsl_requested"
                item["audio_backend_effective"] = "wsl"
                item["audio_backend_effective_reason"] = "wsl_unified_success"
                canonicalize_taxonomy(item)
                _write_audio_result_sidecar()
                return True

            if require_wsl_audio():
                raise RuntimeError(message)
            logger.warning(f"[AUDIO] {message}; falling back to Conda audio step runner")
            return False

        success = True
        try:
            if _try_wsl_unified_audio():
                return True

            step_plan = [
                ("goodq_audio_transcribe", "audio_transcribe"),
                ("goodq_audio_embed", "audio_embed_clap"),
                ("goodq_audio_emotion", "audio_emotion"),
                ("goodq_audio_metadata", "audio_metadata"),
                ("goodq_audio_metadata", "audio_time_hints"),
                ("goodq_audio_metadata", "audio_music_events"),
                ("goodq_text_embed", "text_embed"),
                ("goodq_core", "sentiment"),
                ("goodq_core", "emotion_classify"),
                ("goodq_core", "tagger"),
            ]

            for env_name, step_name in step_plan:
                if not _check_timeout():
                    raise TimeoutError(f"Audio ingestion exceeded timeout of {timeout_seconds}s")
                logger.info(f"[AUDIO] Running step {step_name} in {env_name}")
                result = run_conda_step(env_name, step_name, item, cfg)
                if isinstance(result, dict):
                    item.update(result)

            if success:
                canonicalize_taxonomy(item)
        except StepExecutionError as e:
            logger.error(f"[FAIL] Mission failed during audio pipeline: {e}")
            from steps.common.progress_tracker import add_error
            add_error(f"Audio pipeline step failed: {e}", "ingestion")
            raise e
        except Exception as e:
            logger.error(f"[FAIL] Mission error during audio pipeline: {e}", exc_info=True)
            from steps.common.progress_tracker import add_error
            add_error(f"Audio pipeline error: {e}", "ingestion")
            raise e
        finally:
            if success:
                try:
                    logger.debug(f"Cleaning up temp files: {temp_input}")
                    temp_audio.unlink(missing_ok=True)
                    for f in temp_input.iterdir():
                        if f.is_file():
                            f.unlink()
                    temp_input.rmdir()
                    logger.debug("[OK] Cleanup complete")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp directory: {e}")
            else:
                logger.warning(f"Temp files preserved for debugging: {temp_input}")

        return success
    
    def ingest_image(self, image_path: Path, run_id: str) -> bool:
        """Ingest image file via conda step runner pipeline."""
        from steps.common.conda_runner import run_conda_step, StepExecutionError
        from steps.common.tag_utils import canonicalize_taxonomy

        image_hash = hashlib.sha256(image_path.name.encode()).hexdigest()[:16]
        temp_input = self.processing_dir / f"image_{image_hash}"
        temp_input.mkdir(parents=True, exist_ok=True)

        temp_image = temp_input / image_path.name
        try:
            if temp_image.exists():
                logger.debug(f"Temp image already exists, removing: {temp_image}")
                temp_image.unlink()
            logger.info(f"[SYMBOL] Copying asset to processing area: {image_path.name}")
            shutil.copy2(image_path, temp_image)
            logger.debug(f"[OK] Copy complete: {temp_image}")
        except Exception as e:
            logger.error(f"Failed to copy image to temp dir: {e}")
            return False

        file_size_gb = image_path.stat().st_size / (1024**3)
        timeout_seconds = max(28800, int(file_size_gb * 10800))
        logger.info(f"[TIMER]  Mission timeout: {timeout_seconds}s ({timeout_seconds/3600:.1f}h) for {file_size_gb:.2f}GB asset")
        logger.info(f"[SYMBOL]️ Asset: {image_path.name}")
        start_time = time.time()

        os.environ["GOODQ_STEP_TIMEOUT_MS"] = str(600_000)

        cfg = self._build_run_config("watchdog_image_ingest", run_id=run_id)
        item: Dict[str, Any] = {
            "modality": "image",
            "source_path": str(temp_image),
            "filename": image_path.name,
        }

        def _check_timeout() -> bool:
            if time.time() - start_time > timeout_seconds:
                logger.error(f"[TIMER]  Mission timeout: Image ingestion exceeded {timeout_seconds}s")
                return False
            return True

        success = True
        try:
            step_plan = [
                ("goodq_image_caption", "image_ocr"),
                ("goodq_image_caption", "image_caption"),
                ("goodq_object_detect", "object_detect"),
                ("goodq_face_embed", "face_embed"),
                ("goodq_image_caption", "image_exif"),
                ("goodq_image_caption", "image_embed_dino"),
                ("goodq_image_caption", "image_embed_clip"),
                ("goodq_text_embed", "text_embed"),
                ("goodq_core", "sentiment"),
                ("goodq_core", "emotion_classify"),
                ("goodq_core", "tagger"),
            ]

            for env_name, step_name in step_plan:
                if not _check_timeout():
                    raise TimeoutError(f"Image ingestion exceeded timeout of {timeout_seconds}s")
                logger.info(f"[IMAGE] Running step {step_name} in {env_name}")
                result = run_conda_step(env_name, step_name, item, cfg)
                if isinstance(result, dict):
                    item.update(result)

            if success:
                canonicalize_taxonomy(item)
        except StepExecutionError as e:
            logger.error(f"[FAIL] Mission failed during image pipeline: {e}")
            from steps.common.progress_tracker import add_error
            add_error(f"Image pipeline step failed: {e}", "ingestion")
            raise e
        except Exception as e:
            logger.error(f"[FAIL] Mission error during image pipeline: {e}", exc_info=True)
            from steps.common.progress_tracker import add_error
            add_error(f"Image pipeline error: {e}", "ingestion")
            raise e
        finally:
            if success:
                try:
                    logger.debug(f"Cleaning up temp files: {temp_input}")
                    temp_image.unlink(missing_ok=True)
                    for f in temp_input.iterdir():
                        if f.is_file():
                            f.unlink()
                    temp_input.rmdir()
                    logger.debug("[OK] Cleanup complete")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp directory: {e}")
            else:
                logger.warning(f"Temp files preserved for debugging: {temp_input}")

        return success
    
    def ingest_document(self, doc_path: Path, run_id: str) -> bool:
        """Ingest document file (PDF / text) via conda step runner pipeline."""
        from steps.common.conda_runner import run_conda_step, StepExecutionError
        from steps.common.tag_utils import canonicalize_taxonomy

        ext = doc_path.suffix.lower()
        if ext not in {'.pdf', '.txt', '.md'}:
            logger.warning(f"Document ingestion skipped for unsupported extension: {ext}")
            return False

        doc_hash = hashlib.sha256(doc_path.name.encode()).hexdigest()[:16]
        temp_input = self.processing_dir / f"doc_{doc_hash}"
        temp_input.mkdir(parents=True, exist_ok=True)

        temp_doc = temp_input / doc_path.name
        try:
            if temp_doc.exists():
                logger.debug(f"Temp document already exists, removing: {temp_doc}")
                temp_doc.unlink()
            logger.info(f"[SYMBOL] Copying asset to processing area: {doc_path.name}")
            shutil.copy2(doc_path, temp_doc)
            logger.debug(f"[OK] Copy complete: {temp_doc}")
        except Exception as e:
            logger.error(f"Failed to copy document to temp dir: {e}")
            return False

        file_size_gb = doc_path.stat().st_size / (1024**3)
        timeout_seconds = max(28800, int(file_size_gb * 10800))
        logger.info(f"[TIMER]  Mission timeout: {timeout_seconds}s ({timeout_seconds/3600:.1f}h) for {file_size_gb:.2f}GB asset")
        logger.info(f"[SYMBOL] Asset: {doc_path.name}")
        start_time = time.time()

        os.environ["GOODQ_STEP_TIMEOUT_MS"] = str(600_000)

        modality = 'pdf' if ext == '.pdf' else 'text'
        cfg = self._build_run_config("watchdog_document_ingest", run_id=run_id)
        item: Dict[str, Any] = {
            "modality": modality,
            "source_path": str(temp_doc),
            "filename": doc_path.name,
        }

        def _check_timeout() -> bool:
            if time.time() - start_time > timeout_seconds:
                logger.error(f"[TIMER]  Mission timeout: Document ingestion exceeded {timeout_seconds}s")
                return False
            return True

        success = True
        try:
            # For PDFs, first extract text via pdf_text
            if ext == '.pdf':
                logger.info("[DOC] Running step pdf_text in goodq_text_embed")
                pdf_result = run_conda_step("goodq_text_embed", "pdf_text", item, cfg)
                if isinstance(pdf_result, dict):
                    item.update(pdf_result)
                    pdf_text = pdf_result.get("pdf_text")
                    if isinstance(pdf_text, str) and pdf_text.strip():
                        item["frame_text"] = pdf_text
            else:
                # For plain text / markdown, read content directly
                try:
                    text_content = temp_doc.read_text(encoding="utf-8", errors="ignore")
                except Exception as e:
                    logger.error(f"Failed to read document text: {e}")
                    from steps.common.progress_tracker import add_error
                    add_error(f"Failed to read document text: {e}", "ingestion")
                    raise e
                item["frame_text"] = text_content

            step_plan = [
                ("goodq_text_embed", "text_embed"),
                ("goodq_core", "sentiment"),
                ("goodq_core", "emotion_classify"),
                ("goodq_core", "tagger"),
            ]

            for env_name, step_name in step_plan:
                if not _check_timeout():
                    raise TimeoutError(f"Document ingestion exceeded timeout of {timeout_seconds}s")
                logger.info(f"[DOC] Running step {step_name} in {env_name}")
                result = run_conda_step(env_name, step_name, item, cfg)
                if isinstance(result, dict):
                    item.update(result)

            if success:
                canonicalize_taxonomy(item)
        except StepExecutionError as e:
            logger.error(f"[FAIL] Mission failed during document pipeline: {e}")
            from steps.common.progress_tracker import add_error
            add_error(f"Document pipeline step failed: {e}", "ingestion")
            raise e
        except Exception as e:
            logger.error(f"[FAIL] Mission error during document pipeline: {e}", exc_info=True)
            from steps.common.progress_tracker import add_error
            add_error(f"Document pipeline error: {e}", "ingestion")
            raise e
        finally:
            if success:
                try:
                    logger.debug(f"Cleaning up temp files: {temp_input}")
                    temp_doc.unlink(missing_ok=True)
                    for f in temp_input.iterdir():
                        if f.is_file():
                            f.unlink()
                    temp_input.rmdir()
                    logger.debug("[OK] Cleanup complete")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp directory: {e}")
            else:
                logger.warning(f"Temp files preserved for debugging: {temp_input}")

        return success
    
    def worker_loop(self):
        """Worker thread to process queued files"""
        logger.info("Starting worker thread...")
        
        while not self.shutdown.is_set():
            try:
                # Get next file from queue (with timeout)
                try:
                    file_path, file_hash = self.queue.get(timeout=1.0)
                except Empty:
                    continue
                
                # Process the file
                self.process_file(file_path, file_hash)
                
                # Mark task as done
                self.queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in worker loop: {e}", exc_info=True)
    
    def run(self):
        """Start the watchdog"""
        logger.info("=" * 60)
        logger.info("GoodQ Watchdog Starting")
        logger.info("=" * 60)
        logger.info(f"Watch directory: {self.watch_dir}")
        logger.info(f"Poll interval: {POLL_INTERVAL}s")
        logger.info(f"Stability wait: {STABILITY_WAIT}s")
        logger.info(f"Workers: {MAX_WORKERS}")
        logger.info("=" * 60)
        
        # Start worker threads
        workers = []
        for i in range(MAX_WORKERS):
            worker = Thread(target=self.worker_loop, name=f"Worker-{i}", daemon=True)
            worker.start()
            workers.append(worker)
        
        # Start monitor thread
        monitor = Thread(target=self.monitor_loop, name="Monitor", daemon=True)
        monitor.start()
        
        # Main thread waits
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\nShutdown requested...")
            self.shutdown.set()
            
            # Wait for queue to empty
            logger.info("Waiting for queue to empty...")
            self.queue.join()
            
            # Wait for threads
            logger.info("Waiting for threads to finish...")
            monitor.join(timeout=5)
            for worker in workers:
                worker.join(timeout=5)
            
            logger.info("Watchdog stopped")


def _pid_exists(pid: int) -> bool:
    """Check if a process ID exists on the system."""
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        # Fallback for when psutil is not available
        if os.name == 'nt':
            import subprocess
            try:
                proc = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                return str(pid) in proc.stdout and "INFO:" not in proc.stdout
            except Exception:
                pass
        else:
            # POSIX standard fallback
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False
        return False


def _check_system_restart_events():
    """Query Windows Event Log to check for recent shutdown or restart events."""
    if os.name != 'nt':
        return
    try:
        import subprocess
        # Get the latest shutdown event (1074 or 6008)
        ps_command = (
            "Get-WinEvent -FilterHashtable @{LogName='System'; Id=1074,6008} -MaxEvents 1 | "
            "Select-Object TimeCreated, Id, Message | ConvertTo-Json"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            check=False
        )
        if proc.returncode == 0 and proc.stdout.strip():
            import json
            try:
                event = json.loads(proc.stdout.strip())
                if isinstance(event, list):
                    event = event[0] if event else {}
                
                time_str = event.get("TimeCreated")
                event_id = event.get("Id")
                message = event.get("Message", "")
                
                if time_str and "Date(" in time_str:
                    try:
                        ms = int(time_str.split("Date(")[1].split(")")[0])
                        dt = datetime.fromtimestamp(ms / 1000.0, timezone.utc)
                        time_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                    except Exception:
                        pass
                
                logger.info(
                    "[RESTART_DETECTOR] Detected last system shutdown/restart event ID %s at %s. Details: %s",
                    event_id, time_str, message.strip().replace('\r', '').replace('\n', ' ')
                )
            except Exception as e:
                logger.debug("Failed to parse Event Log JSON: %s", e)
        else:
            logger.debug("No recent shutdown events found in Event Log.")
    except Exception as e:
        logger.debug("Failed to query Event Log for system restarts: %s", e)


def main():
    """Main entry point with file lock to prevent multiple instances"""
    try:
        cfg = load_configs({})
        runtime_paths = _resolve_watchdog_paths(cfg)
        log_file = _configure_watchdog_logging(runtime_paths["log_dir"])
    except Exception:
        logger.exception(
            "Watchdog bootstrap failed before canonical log binding. bootstrap_log=%s",
            _BOOTSTRAP_LOG_PATH,
        )
        raise
    lockfile = runtime_paths["lock_file"]
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    
    # Try to create lock file exclusively
    try:
        # On Windows, open with exclusive access
        lock_handle = os.open(str(lockfile), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(lock_handle, str(os.getpid()).encode())
        os.close(lock_handle)
    except FileExistsError:
        # Check if existing lock is from a dead process
        try:
            with open(lockfile, 'r') as f:
                content = f.read().strip()
            if not content:
                raise ValueError("Lockfile is empty")
            old_pid = int(content)
            # Check if process still exists
            if _pid_exists(old_pid):
                logger.error(f"Watchdog already running (PID {old_pid}). Exiting.")
                sys.exit(1)
            else:
                # Dead process, remove stale lock
                logger.warning(f"Removing stale lock from dead process {old_pid}")
                lockfile.unlink()
                # Try again
                lock_handle = os.open(str(lockfile), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(lock_handle, str(os.getpid()).encode())
                os.close(lock_handle)
        except (ValueError, OSError) as e:
            # Stale, malformed, or unreadable lock file
            logger.warning(f"Lockfile exists but is invalid, empty, or unreadable ({e}). Overwriting stale lock.")
            try:
                lockfile.unlink(missing_ok=True)
                lock_handle = os.open(str(lockfile), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(lock_handle, str(os.getpid()).encode())
                os.close(lock_handle)
            except Exception as force_err:
                logger.error(f"Failed to force-acquire lock: {force_err}")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to acquire lock: {e}")
            sys.exit(1)
    
    try:
        logger.info("Runtime authority: configs/config.yaml")
        logger.info(f"Import inbox (resolved): {cfg['paths']['import_inbox']}")
        logger.info(f"Active epoch: {Path(cfg['paths']['db_dir']).name}")
        logger.info(f"Watchdog log file: {log_file}")
        
        # Check system events for recent restarts
        _check_system_restart_events()
        
        watchdog = WatchdogProcessor(cfg, resolved_paths=runtime_paths)
        
        # Clean up any leftover temporary files from interrupted runs
        watchdog.cleanup_stale_processing_files()
        
        watchdog.run()
    finally:
        # Remove lock on exit
        try:
            lockfile.unlink(missing_ok=True)
        except Exception as e:
            logger.debug(f"Failed to remove lockfile: {e}")


if __name__ == '__main__':
    main()
