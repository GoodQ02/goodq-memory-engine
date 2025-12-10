"""
Watchdog Integration with Agent Orchestrator
Connects file watcher to agent-based pipeline
"""

import asyncio
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from agents.pipeline_integration import process_video_with_agents
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VideoFileHandler(FileSystemEventHandler):
    """Handler for new video files."""
    
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.processing = set()
        self.video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.m4v', '.webm'}
    
    def on_created(self, event):
        """Handle new file creation."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        
        if path.suffix.lower() in self.video_extensions:
            logger.info(f"New video detected: {path}")
            
            # Add to processing queue
            asyncio.run_coroutine_threadsafe(
                self.queue.put(str(path)),
                asyncio.get_event_loop()
            )


async def process_queue(queue: asyncio.Queue):
    """Process videos from queue."""
    
    while True:
        try:
            video_path = await queue.get()
            
            if video_path in processed_videos:
                logger.info(f"Skipping already processed: {video_path}")
                continue
            
            logger.info(f"Processing: {video_path}")
            
            # Wait for file to finish writing
            await asyncio.sleep(2)
            
            # Verify file exists and is accessible
            path = Path(video_path)
            if not path.exists():
                logger.warning(f"File disappeared: {video_path}")
                continue
            
            # Process with agent orchestrator
            result = await process_video_with_agents(video_path)
            
            if result['status'] == 'complete':
                logger.info(f"[SYMBOL] Successfully processed: {path.name}")
                processed_videos.add(video_path)
                
                # Move to completed
                completed_dir = Path("L:/goodq4all/import_inbox/_completed")
                completed_dir.mkdir(exist_ok=True)
                
                new_path = completed_dir / path.name
                if not new_path.exists():
                    path.rename(new_path)
                    logger.info(f"Moved to completed: {new_path}")
            
            elif result['status'] == 'failed':
                logger.error(f"[SYMBOL] Processing failed: {path.name}")
                
                # Move to failed
                failed_dir = Path("L:/goodq4all/import_inbox/_failed")
                failed_dir.mkdir(exist_ok=True)
                
                new_path = failed_dir / path.name
                if not new_path.exists():
                    path.rename(new_path)
                    logger.info(f"Moved to failed: {new_path}")
            
            queue.task_done()
            
        except Exception as e:
            logger.error(f"Queue processing error: {str(e)}", exc_info=True)
            await asyncio.sleep(5)


processed_videos = set()


async def run_watchdog_with_agents():
    """Run watchdog with agent-based processing."""
    
    inbox_path = Path("L:/goodq4all/import_inbox")
    inbox_path.mkdir(exist_ok=True)
    
    logger.info(f"Watching: {inbox_path}")
    
    # Create processing queue
    queue = asyncio.Queue()
    
    # Start file watcher
    event_handler = VideoFileHandler(queue)
    observer = Observer()
    observer.schedule(event_handler, str(inbox_path), recursive=False)
    observer.start()
    
    logger.info("Watchdog started with agent orchestrator")
    
    try:
        # Process existing files
        for video in inbox_path.glob("*"):
            if video.is_file() and video.suffix.lower() in event_handler.video_extensions:
                if video.name.startswith('_'):
                    continue  # Skip hidden/processed folders
                logger.info(f"Queueing existing file: {video}")
                await queue.put(str(video))
        
        # Start queue processor
        await process_queue(queue)
        
    except KeyboardInterrupt:
        logger.info("Stopping watchdog...")
        observer.stop()
    
    observer.join()


if __name__ == "__main__":
    asyncio.run(run_watchdog_with_agents())
