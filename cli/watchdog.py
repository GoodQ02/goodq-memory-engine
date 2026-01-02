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
from threading import Thread, Event, Lock
import json
import os
import uuid

# Add repo root to path for imports
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Setup logging with UTF-8 encoding for file, ASCII for console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('L:/goodq4all/logs/watchdog.log', encoding='utf-8')
    ]
)
# Add console handler with ASCII-safe encoding
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))


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


console_handler.addFilter(ASCIIFilter())
logging.root.addHandler(console_handler)
logger = logging.getLogger(__name__)

# Import Control Agent
try:
    from agents.control_agent import ControlAgent
    CONTROL_AGENT_AVAILABLE = True
except ImportError:
    CONTROL_AGENT_AVAILABLE = False
    logger.warning("Control Agent not available - running without AI orchestration")

# Configuration
WATCH_DIR = Path("L:/goodq4all/import_inbox")
PROCESSING_DIR = Path("L:/_DATA/GoodQ_Data/processing")
PROCESSED_DIR = Path("L:/_DATA/GoodQ_Data/processed")
FAILED_DIR = Path("L:/_DATA/GoodQ_Data/failed")
STATE_FILE = Path("L:/goodq4all/logs/watchdog_state.json")

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
        current_size = self.path.stat().st_size
        current_mtime = self.path.stat().st_mtime
        
        if current_size == self.size and current_mtime == self.mtime:
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
        self.lock = Lock()
        self.processed: Dict[str, Dict] = {}
        self.load()
    
    def load(self):
        """Load processed file registry"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.processed = json.load(f)
                logger.info(f"Loaded {len(self.processed)} processed file records")
            except Exception as e:
                logger.error(f"Failed to load state file: {e}")
                self.processed = {}
    
    def save(self):
        """Save processed file registry"""
        with self.lock:
            try:
                self.state_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.state_file, 'w') as f:
                    json.dump(self.processed, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save state file: {e}")
    
    def is_processed(self, file_hash: str) -> bool:
        """Check if file hash has been processed"""
        with self.lock:
            return file_hash in self.processed
    
    def mark_processed(self, file_hash: str, original_name: str, status: str = 'success'):
        """Mark file as processed"""
        with self.lock:
            self.processed[file_hash] = {
                'original_name': original_name,
                'status': status,
                'timestamp': datetime.now().isoformat()
            }
            self.save()
    
    def mark_failed(self, file_hash: str, original_name: str, error: str):
        """Mark file as failed"""
        with self.lock:
            self.processed[file_hash] = {
                'original_name': original_name,
                'status': 'failed',
                'error': error,
                'timestamp': datetime.now().isoformat()
            }
            self.save()


class WatchdogProcessor:
    """Main watchdog processor"""
    def __init__(self, cfg: Dict[str, Any]):
        self._cfg_base = cfg
        self.watch_dir = Path(cfg["paths"]["import_inbox"])
        self.processing_dir = PROCESSING_DIR
        self.processed_dir = PROCESSED_DIR
        self.failed_dir = FAILED_DIR
        self.registry = ProcessedRegistry(STATE_FILE)
        self.queue = Queue()
        self.shutdown = Event()
        self.file_states: Dict[str, FileState] = {}
        
        # Initialize Control Agent if available
        self.control_agent = None
        if CONTROL_AGENT_AVAILABLE:
            try:
                self.control_agent = ControlAgent()
                logger.info("[BOT] Control Agent initialized - AI orchestration enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize Control Agent: {e}")
        
        # Ensure directories exist
        self.processing_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Watching directory: {self.watch_dir}")
    
    def _build_run_config(self, pipeline_name: str) -> Dict[str, Any]:
        """Load configs and attach a run context for mission logging."""
        import subprocess

        cfg: Dict[str, Any] = dict(self._cfg_base) if isinstance(self._cfg_base, dict) else {}
        run_context: Dict[str, Any] = {
            'id': str(uuid.uuid4()),
            'pipeline': pipeline_name,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'timer_unit': 'ms',
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
                # Check if supported file type
                if self.get_file_type(item):
                    files.append(item)
        return files
    
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
                        
                        if self.registry.is_processed(file_hash):
                            logger.info(f"File already processed (hash: {file_hash[:8]}...), skipping: {file_path.name}")
                            # Optionally mark the file to avoid repeated checks
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
            new_name = f"PROCESSED_{file_path.name}"
            new_path = file_path.parent / new_name
            if not new_path.exists():
                file_path.rename(new_path)
                logger.debug(f"Marked as processed: {new_name}")
        except Exception as e:
            logger.error(f"Failed to rename processed file: {e}")
    
    def process_file(self, file_path: Path, file_hash: str) -> bool:
        """Process a single file with AI Control Agent monitoring"""
        # Import progress tracker
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from steps.common.progress_tracker import start_processing, finish_processing, add_error
        
        file_type = self.get_file_type(file_path)
        logger.info(f"Processing {file_type}: {file_path.name}")
        
        # Notify Control Agent of new file
        if self.control_agent:
            self.control_agent.on_file_detected(file_path.name, file_type, file_path.stat().st_size)
        
        # Start progress tracking
        total_steps = 20  # Estimate for video processing
        start_processing(file_path.name, total_steps)
        
        # Move to processing directory
        processing_path = self.processing_dir / file_path.name
        try:
            shutil.copy2(file_path, processing_path)
            logger.debug(f"Copied to processing: {processing_path}")
        except Exception as e:
            logger.error(f"Failed to copy file: {e}")
            add_error(f"Failed to copy file: {e}", "file_copy")
            finish_processing("failed")
            self.registry.mark_failed(file_hash, file_path.name, str(e))
            
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
                success = self.ingest_video(processing_path)
            elif file_type == 'audio':
                success = self.ingest_audio(processing_path)
            elif file_type == 'image':
                success = self.ingest_image(processing_path)
            elif file_type == 'document':
                success = self.ingest_document(processing_path)
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
            self.registry.mark_processed(file_hash, file_path.name, 'success')
            
            # Notify Control Agent of success
            if self.control_agent:
                self.control_agent.on_processing_complete(file_path.name, success=True)
            
            # Move original to processed
            processed_path = self.processed_dir / f"PROCESSED_{file_path.name}"
            try:
                file_path.rename(processed_path)
                logger.debug(f"Moved to processed: {processed_path}")
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
            self.registry.mark_failed(file_hash, file_path.name, error_msg or 'Unknown error')
            
            # Notify Control Agent of failure
            if self.control_agent:
                self.control_agent.on_processing_complete(file_path.name, success=False, error=error_msg)
            
            # Move to failed
            failed_path = self.failed_dir / f"FAILED_{file_path.name}"
            try:
                file_path.rename(failed_path)
                logger.debug(f"Moved to failed: {failed_path}")
            except Exception as e:
                logger.error(f"Failed to move to failed: {e}")
            
            # Clean up processing copy
            try:
                processing_path.unlink(missing_ok=True)
            except Exception as e:
                logger.error(f"Failed to clean up processing file: {e}")
        
        return success
    
    def ingest_video(self, video_path: Path) -> bool:
        """Ingest video file via CLI"""
        import subprocess
        
        # Create a stable input directory for this specific video
        # Use video hash to ensure uniqueness and avoid cleanup issues
        import hashlib
        video_hash = hashlib.sha256(video_path.name.encode()).hexdigest()[:16]
        temp_input = Path(f"L:/_DATA/GoodQ_Data/processing/video_{video_hash}")
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
            
            # For large files, copy with progress
            if file_size_mb > 100:
                import shutil
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
            cfg = self._build_run_config("watchdog_video_ingest")
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
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"[TIMER]  Mission timeout: Video ingestion exceeded {timeout_seconds}s")
            # Keep temp files for debugging on timeout
            logger.warning(f"Temp files preserved for debugging: {temp_input}")
            return False
        except Exception as e:
            logger.error(f"[FAIL] Mission error: {e}", exc_info=True)
            # Keep temp files for debugging on error
            logger.warning(f"Temp files preserved for debugging: {temp_input}")
            return False
    
    def ingest_audio(self, audio_path: Path) -> bool:
        """Ingest standalone audio file via conda step runner pipeline."""
        from steps.common.conda_runner import run_conda_step, StepExecutionError
        from steps.common.tag_utils import canonicalize_taxonomy

        audio_hash = hashlib.sha256(audio_path.name.encode()).hexdigest()[:16]
        temp_input = Path(f"L:/_DATA/GoodQ_Data/processing/audio_{audio_hash}")
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

        cfg = self._build_run_config("watchdog_audio_ingest")
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

        success = True
        try:
            step_plan = [
                ("goodq_audio_transcribe", "audio_transcribe"),
                ("goodq_audio_embed", "audio_embed_clap"),
                ("goodq_audio_emotion", "audio_emotion"),
                ("goodq_audio_metadata", "audio_metadata"),
                ("goodq_audio_metadata", "audio_time_hints"),
                ("goodq_audio_metadata", "audio_music_events"),
                ("goodq_text_embed", "text_embed"),
                ("goodq_sentiment", "sentiment"),
                ("goodq_emotion_classify", "emotion_classify"),
                ("goodq_emotion_classify", "tagger"),
            ]

            for env_name, step_name in step_plan:
                if not _check_timeout():
                    success = False
                    break
                logger.info(f"[AUDIO] Running step {step_name} in {env_name}")
                result = run_conda_step(env_name, step_name, item, cfg)
                if isinstance(result, dict):
                    item.update(result)

            if success:
                canonicalize_taxonomy(item)
        except StepExecutionError as e:
            logger.error(f"[FAIL] Mission failed during audio pipeline: {e}")
            success = False
        except Exception as e:
            logger.error(f"[FAIL] Mission error during audio pipeline: {e}", exc_info=True)
            success = False
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
    
    def ingest_image(self, image_path: Path) -> bool:
        """Ingest image file via conda step runner pipeline."""
        from steps.common.conda_runner import run_conda_step, StepExecutionError
        from steps.common.tag_utils import canonicalize_taxonomy

        image_hash = hashlib.sha256(image_path.name.encode()).hexdigest()[:16]
        temp_input = Path(f"L:/_DATA/GoodQ_Data/processing/image_{image_hash}")
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

        cfg = self._build_run_config("watchdog_image_ingest")
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
                ("goodq_sentiment", "sentiment"),
                ("goodq_emotion_classify", "emotion_classify"),
                ("goodq_emotion_classify", "tagger"),
            ]

            for env_name, step_name in step_plan:
                if not _check_timeout():
                    success = False
                    break
                logger.info(f"[IMAGE] Running step {step_name} in {env_name}")
                result = run_conda_step(env_name, step_name, item, cfg)
                if isinstance(result, dict):
                    item.update(result)

            if success:
                canonicalize_taxonomy(item)
        except StepExecutionError as e:
            logger.error(f"[FAIL] Mission failed during image pipeline: {e}")
            success = False
        except Exception as e:
            logger.error(f"[FAIL] Mission error during image pipeline: {e}", exc_info=True)
            success = False
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
    
    def ingest_document(self, doc_path: Path) -> bool:
        """Ingest document file (PDF / text) via conda step runner pipeline."""
        from steps.common.conda_runner import run_conda_step, StepExecutionError
        from steps.common.tag_utils import canonicalize_taxonomy

        ext = doc_path.suffix.lower()
        if ext not in {'.pdf', '.txt', '.md'}:
            logger.warning(f"Document ingestion not implemented for extension: {ext}")
            return False

        doc_hash = hashlib.sha256(doc_path.name.encode()).hexdigest()[:16]
        temp_input = Path(f"L:/_DATA/GoodQ_Data/processing/doc_{doc_hash}")
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
        cfg = self._build_run_config("watchdog_document_ingest")
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
                    return False
                item["frame_text"] = text_content

            step_plan = [
                ("goodq_text_embed", "text_embed"),
                ("goodq_sentiment", "sentiment"),
                ("goodq_emotion_classify", "emotion_classify"),
                ("goodq_emotion_classify", "tagger"),
            ]

            for env_name, step_name in step_plan:
                if not _check_timeout():
                    success = False
                    break
                logger.info(f"[DOC] Running step {step_name} in {env_name}")
                result = run_conda_step(env_name, step_name, item, cfg)
                if isinstance(result, dict):
                    item.update(result)

            if success:
                canonicalize_taxonomy(item)
        except StepExecutionError as e:
            logger.error(f"[FAIL] Mission failed during document pipeline: {e}")
            success = False
        except Exception as e:
            logger.error(f"[FAIL] Mission error during document pipeline: {e}", exc_info=True)
            success = False
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


def main():
    """Main entry point with file lock to prevent multiple instances"""
    lockfile = Path('L:/_DATA/GoodQ_Data/.watchdog.lock')
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
                old_pid = int(f.read().strip())
            # Check if process still exists
            import psutil
            if psutil.pid_exists(old_pid):
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
        except Exception as e:
            logger.error(f"Failed to acquire lock: {e}")
            sys.exit(1)
    
    try:
        from steps.common.config_loader import load_configs
        cfg = load_configs({})
        watchdog = WatchdogProcessor(cfg)
        watchdog.run()
    finally:
        # Remove lock on exit
        try:
            lockfile.unlink(missing_ok=True)
        except Exception as e:
            logger.debug(f"Failed to remove lockfile: {e}")


if __name__ == '__main__':
    main()
