#!/usr/bin/env python3
"""
GoodQ Watchdog - Automatic File Ingestion Monitor
Monitors import_inbox for new files and automatically processes them.
"""

from __future__ import annotations
import sys
import time
import hashlib
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Set, Dict, List
from queue import Queue, Empty
from threading import Thread, Event, Lock
import json

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
        '📋': '[CLIPBOARD]',
        '⏱️': '[TIMER]',
        '🎬': '[VIDEO]',
        '✓': '[OK]',
        '✅': '[SUCCESS]',
        '❌': '[ERROR]',
        '⚠️': '[WARN]',
        '📊': '[STATS]',
        '🎯': '[TARGET]',
        '💾': '[SAVE]',
        '🔍': '[SEARCH]',
        '📁': '[FOLDER]',
        '🎥': '[CAMERA]',
        '🎤': '[MIC]',
        '🎵': '[MUSIC]',
        '🖼️': '[IMAGE]',
        '📄': '[DOC]',
        '🔊': '[AUDIO]',
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

# Configuration
WATCH_DIR = Path("L:/goodq4all/import_inbox")
PROCESSING_DIR = Path("L:/goodq4all/data/processing")
PROCESSED_DIR = Path("L:/goodq4all/data/processed")
FAILED_DIR = Path("L:/goodq4all/data/failed")
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
    def __init__(self):
        self.watch_dir = WATCH_DIR
        self.processing_dir = PROCESSING_DIR
        self.processed_dir = PROCESSED_DIR
        self.failed_dir = FAILED_DIR
        self.registry = ProcessedRegistry(STATE_FILE)
        self.queue = Queue()
        self.shutdown = Event()
        self.file_states: Dict[str, FileState] = {}
        
        # Ensure directories exist
        self.processing_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Watching directory: {self.watch_dir}")
    
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
        """Process a single file"""
        # Import progress tracker
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from steps.common.progress_tracker import start_processing, finish_processing, add_error
        
        file_type = self.get_file_type(file_path)
        logger.info(f"Processing {file_type}: {file_path.name}")
        
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
            return False
        
        # Call ingestion pipeline
        success = False
        error_msg = None
        
        try:
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
        
        # Handle result
        if success:
            logger.info(f"[OK] Successfully processed: {file_path.name}")
            finish_processing("completed")
            self.registry.mark_processed(file_hash, file_path.name, 'success')
            
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
        temp_input = Path(f"L:/goodq4all/data/processing/video_{video_hash}")
        temp_input.mkdir(parents=True, exist_ok=True)
        
        # Copy video to temp location (must stay there for entire ingestion)
        temp_video = temp_input / video_path.name
        try:
            if temp_video.exists():
                logger.debug(f"Temp video already exists, removing: {temp_video}")
                temp_video.unlink()
            logger.info(f"📋 Copying asset to processing area: {video_path.name}")
            shutil.copy2(video_path, temp_video)
            logger.debug(f"✓ Copy complete: {temp_video}")
        except Exception as e:
            logger.error(f"Failed to copy video to temp dir: {e}")
            return False
        
        # Use direct Python call (already running in correct environment)
        import sys
        python_exe = sys.executable
        cmd = [
            python_exe, '-m', 'cli.run_ingestion',
            '--input-dir', str(temp_input),
            '--workspace', f'L:/goodq4all/logs/watchdog_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            '--output', f'L:/goodq4all/logs/watchdog_{datetime.now().strftime("%Y%m%d_%H%M%S")}_results.json',
            '--force',  # Force reprocessing to ensure complete AI analysis
            '--verbose'
        ]
        
        # Dynamic timeout based on file size (3 hours per GB, min 8 hours for thorough processing)
        file_size_gb = video_path.stat().st_size / (1024**3)
        timeout_seconds = max(28800, int(file_size_gb * 10800))  # At least 8 hours, +3hrs per GB
        logger.info(f"⏱️  Mission timeout: {timeout_seconds}s ({timeout_seconds/3600:.1f}h) for {file_size_gb:.2f}GB asset")
        logger.info(f"🎬 Asset: {video_path.name}")
        
        logger.debug(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd='L:/goodq4all'
            )
            
            if result.returncode == 0:
                logger.info("✅ Mission complete: Video ingestion successful")
                # Clean up temp directory ONLY on success
                try:
                    logger.debug(f"Cleaning up temp files: {temp_input}")
                    temp_video.unlink(missing_ok=True)
                    # Remove any other files that might have been created
                    for f in temp_input.iterdir():
                        if f.is_file():
                            f.unlink()
                    temp_input.rmdir()
                    logger.debug("✓ Cleanup complete")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp directory: {e}")
                return True
            else:
                logger.error(f"❌ Mission failed: Video ingestion returned code {result.returncode}")
                if result.stdout:
                    logger.error(f"STDOUT: {result.stdout}")
                if result.stderr:
                    logger.error(f"STDERR: {result.stderr}")
                # Keep temp files for debugging on failure
                logger.warning(f"Temp files preserved for debugging: {temp_input}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"⏱️  Mission timeout: Video ingestion exceeded {timeout_seconds}s")
            # Keep temp files for debugging on timeout
            logger.warning(f"Temp files preserved for debugging: {temp_input}")
            return False
        except Exception as e:
            logger.error(f"❌ Mission error: {e}", exc_info=True)
            # Keep temp files for debugging on error
            logger.warning(f"Temp files preserved for debugging: {temp_input}")
            return False
    
    def ingest_audio(self, audio_path: Path) -> bool:
        """Ingest audio file"""
        # TODO: Implement audio ingestion
        logger.warning("Audio ingestion not yet implemented")
        return False
    
    def ingest_image(self, image_path: Path) -> bool:
        """Ingest image file"""
        # TODO: Implement image ingestion
        logger.warning("Image ingestion not yet implemented")
        return False
    
    def ingest_document(self, doc_path: Path) -> bool:
        """Ingest document file"""
        # TODO: Implement document ingestion
        logger.warning("Document ingestion not yet implemented")
        return False
    
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
    """Main entry point"""
    watchdog = WatchdogProcessor()
    watchdog.run()


if __name__ == '__main__':
    main()
