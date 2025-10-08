#!/usr/bin/env python3
"""
GoodQ File Watchdog
Monitors import_inbox folder and triggers ingestion pipeline for new files
"""

import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Setup paths
PROJECT_ROOT = Path(__file__).parent.parent
IMPORT_INBOX = PROJECT_ROOT / "import_inbox"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
LOGS_DIR = PROJECT_ROOT / "logs"

# Setup logging
log_file = LOGS_DIR / f"watchdog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# File type mappings
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.wma', '.aac'}
DOCUMENT_EXTENSIONS = {'.pdf', '.txt', '.doc', '.docx', '.rtf'}
DATA_EXTENSIONS = {'.json', '.csv', '.xml', '.yaml', '.yml'}

# Ignore patterns
IGNORE_PATTERNS = {'.tmp', '.part', '.download', '.crdownload'}


class GoodQFileHandler(FileSystemEventHandler):
    """Handler for file system events in import_inbox"""
    
    def __init__(self):
        super().__init__()
        self.processing = set()
        self.debounce_time = 2  # seconds to wait for file to stabilize
        
    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        
        # Ignore temporary files
        if any(pattern in file_path.name for pattern in IGNORE_PATTERNS):
            return
            
        logger.info(f"Detected new file: {file_path.name}")
        
        # Wait for file to finish writing
        time.sleep(self.debounce_time)
        
        # Check if file is still growing
        if not self._is_file_stable(file_path):
            logger.info(f"File still being written, waiting: {file_path.name}")
            time.sleep(5)
            
        self.process_file(file_path)
    
    def on_modified(self, event):
        """Handle file modification events (for copy operations)"""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        
        # Only process if not already processing
        if file_path in self.processing:
            return
            
        # Check if file is complete
        if self._is_file_stable(file_path):
            self.process_file(file_path)
    
    def _is_file_stable(self, file_path):
        """Check if file has finished being written"""
        try:
            size1 = file_path.stat().st_size
            time.sleep(1)
            size2 = file_path.stat().st_size
            return size1 == size2 and size1 > 0
        except:
            return False
    
    def process_file(self, file_path):
        """Route file to appropriate processing pipeline"""
        if file_path in self.processing:
            return
            
        self.processing.add(file_path)
        
        try:
            ext = file_path.suffix.lower()
            file_type = self._classify_file(ext)
            
            logger.info(f"Processing {file_type}: {file_path.name} ({self._format_size(file_path.stat().st_size)})")
            
            if file_type == "video":
                self._process_video(file_path)
            elif file_type == "image":
                self._process_image(file_path)
            elif file_type == "audio":
                self._process_audio(file_path)
            elif file_type == "document":
                self._process_document(file_path)
            elif file_type == "data":
                self._process_data(file_path)
            else:
                logger.warning(f"Unknown file type: {ext} - {file_path.name}")
                
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}", exc_info=True)
        finally:
            self.processing.discard(file_path)
    
    def _classify_file(self, ext):
        """Classify file by extension"""
        if ext in VIDEO_EXTENSIONS:
            return "video"
        elif ext in IMAGE_EXTENSIONS:
            return "image"
        elif ext in AUDIO_EXTENSIONS:
            return "audio"
        elif ext in DOCUMENT_EXTENSIONS:
            return "document"
        elif ext in DATA_EXTENSIONS:
            return "data"
        else:
            return "unknown"
    
    def _format_size(self, size_bytes):
        """Format file size for display"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def _process_video(self, file_path):
        """Process video file through GoodQ pipeline"""
        logger.info(f"→ Triggering video ingestion pipeline for: {file_path.name}")
        
        # Run the ingestion pipeline
        cmd = [
            "conda", "run", "-n", "goodq_zenml", "--no-capture-output",
            "python", "-m", "pipelines.ingest_pipeline",
            str(file_path)
        ]
        
        import subprocess
        try:
            result = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode == 0:
                logger.info(f"✓ Successfully processed: {file_path.name}")
                logger.info(result.stdout)
            else:
                logger.error(f"✗ Pipeline failed for: {file_path.name}")
                logger.error(result.stderr)
                
        except subprocess.TimeoutExpired:
            logger.error(f"✗ Pipeline timeout for: {file_path.name}")
        except Exception as e:
            logger.error(f"✗ Pipeline error for {file_path.name}: {e}")
    
    def _process_image(self, file_path):
        """Process image file"""
        logger.info(f"→ Processing image: {file_path.name}")
        # TODO: Implement image-only pipeline
        logger.info("Image processing not yet implemented")
    
    def _process_audio(self, file_path):
        """Process audio file"""
        logger.info(f"→ Processing audio: {file_path.name}")
        # TODO: Implement audio-only pipeline
        logger.info("Audio processing not yet implemented")
    
    def _process_document(self, file_path):
        """Process document file"""
        logger.info(f"→ Processing document: {file_path.name}")
        # TODO: Implement document processing
        logger.info("Document processing not yet implemented")
    
    def _process_data(self, file_path):
        """Process data file (JSON, CSV, etc)"""
        logger.info(f"→ Processing data file: {file_path.name}")
        # TODO: Implement data file processing
        logger.info("Data file processing not yet implemented")


def main():
    """Main watchdog loop"""
    logger.info("=" * 70)
    logger.info("GoodQ File Watchdog Starting")
    logger.info("=" * 70)
    logger.info(f"Monitoring: {IMPORT_INBOX}")
    logger.info(f"Log file: {log_file}")
    logger.info("")
    logger.info("Supported file types:")
    logger.info(f"  • Videos: {', '.join(sorted(VIDEO_EXTENSIONS))}")
    logger.info(f"  • Images: {', '.join(sorted(IMAGE_EXTENSIONS))}")
    logger.info(f"  • Audio: {', '.join(sorted(AUDIO_EXTENSIONS))}")
    logger.info(f"  • Documents: {', '.join(sorted(DOCUMENT_EXTENSIONS))}")
    logger.info(f"  • Data: {', '.join(sorted(DATA_EXTENSIONS))}")
    logger.info("")
    logger.info("Drop files into import_inbox to begin processing...")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 70)
    logger.info("")
    
    # Ensure directories exist
    IMPORT_INBOX.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    
    # Setup watchdog
    event_handler = GoodQFileHandler()
    observer = Observer()
    observer.schedule(event_handler, str(IMPORT_INBOX), recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("")
        logger.info("Stopping watchdog...")
        observer.stop()
    
    observer.join()
    logger.info("Watchdog stopped")


if __name__ == "__main__":
    main()
