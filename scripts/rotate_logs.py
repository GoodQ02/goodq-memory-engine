#!/usr/bin/env python3
"""
Log Rotation Script

Purpose: Archive old watchdog logs and compress them
Author: GoodQ Development Team
Created: 2025-11-07

This script rotates watchdog logs by:
1. Keeping the newest N runs
2. Archiving older logs to configured archive root
3. Compressing archived logs to save space
"""

import logging
import shutil
import zipfile
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
REPO_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = REPO_ROOT / "logs"
_data_root = os.environ.get("GOODQ_DATA_ROOT")
if _data_root:
    ARCHIVE_DIR = Path(_data_root).parent / "_ARCHIVE" / "goodq4all_logs"
else:
    ARCHIVE_DIR = REPO_ROOT / "logs_archive"
KEEP_NEWEST = 10  # Keep the 10 most recent runs
MAX_AGE_DAYS = 30  # Also keep logs from last 30 days
DRY_RUN = False  # Set to True to see what would happen without actually doing it


def get_watchdog_dirs() -> List[Tuple[Path, datetime]]:
    """Get all watchdog log directories with their modification times."""
    dirs = []
    
    if not LOGS_DIR.exists():
        logger.warning(f"Logs directory does not exist: {LOGS_DIR}")
        return dirs
    
    for item in LOGS_DIR.iterdir():
        if item.is_dir() and item.name.startswith("watchdog_"):
            try:
                # Get modification time
                mtime = datetime.fromtimestamp(item.stat().st_mtime)
                dirs.append((item, mtime))
            except Exception as e:
                logger.warning(f"Error reading {item.name}: {e}")
    
    # Sort by modification time, newest first
    dirs.sort(key=lambda x: x[1], reverse=True)
    return dirs


def get_directory_size(path: Path) -> int:
    """Calculate total size of directory in bytes."""
    total = 0
    try:
        for item in path.rglob('*'):
            if item.is_file():
                total += item.stat().st_size
    except Exception as e:
        logger.warning(f"Error calculating size for {path}: {e}")
    return total


def compress_directory(source: Path, dest_zip: Path) -> bool:
    """Compress a directory to a ZIP file."""
    try:
        with zipfile.ZipFile(dest_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in source.rglob('*'):
                if file.is_file():
                    arcname = file.relative_to(source.parent)
                    zf.write(file, arcname)
        return True
    except Exception as e:
        logger.error(f"Error compressing {source}: {e}")
        return False


def rotate_logs():
    """Rotate watchdog logs according to configured policy."""
    
    logger.info("Starting log rotation")
    logger.info(f"Policy: Keep {KEEP_NEWEST} newest runs OR logs from last {MAX_AGE_DAYS} days")
    
    if DRY_RUN:
        logger.info("DRY RUN MODE - No changes will be made")
    
    # Get all watchdog directories
    watchdog_dirs = get_watchdog_dirs()
    
    if not watchdog_dirs:
        logger.info("No watchdog log directories found")
        return
    
    logger.info(f"Found {len(watchdog_dirs)} watchdog log directories")
    
    # Determine cutoff date
    cutoff_date = datetime.now() - timedelta(days=MAX_AGE_DAYS)
    
    # Determine which logs to archive
    to_archive = []
    to_keep = []
    
    for i, (log_dir, mtime) in enumerate(watchdog_dirs):
        age_days = (datetime.now() - mtime).days
        
        # Keep if:
        # 1. Within newest N runs, OR
        # 2. Modified within MAX_AGE_DAYS
        if i < KEEP_NEWEST or mtime > cutoff_date:
            to_keep.append((log_dir, mtime, age_days))
            logger.info(f"Keeping: {log_dir.name} (age: {age_days} days, rank: {i+1})")
        else:
            to_archive.append((log_dir, mtime, age_days))
            logger.info(f"Archiving: {log_dir.name} (age: {age_days} days, rank: {i+1})")
    
    logger.info(f"Will keep: {len(to_keep)} directories")
    logger.info(f"Will archive: {len(to_archive)} directories")
    
    if not to_archive:
        logger.info("No logs to archive")
        return
    
    # Create archive directory
    if not DRY_RUN:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Archive old logs
    total_size = 0
    compressed_size = 0
    archived_count = 0
    
    for log_dir, mtime, age_days in to_archive:
        try:
            # Calculate original size
            original_size = get_directory_size(log_dir)
            size_mb = original_size / (1024 * 1024)
            
            # Create archive filename
            archive_filename = f"{log_dir.name}.zip"
            archive_path = ARCHIVE_DIR / archive_filename
            
            logger.info(f"Archiving {log_dir.name} ({size_mb:.1f} MB)...")
            
            if not DRY_RUN:
                # Compress to archive
                if compress_directory(log_dir, archive_path):
                    # Get compressed size
                    comp_size = archive_path.stat().st_size
                    comp_mb = comp_size / (1024 * 1024)
                    reduction = (1 - comp_size / original_size) * 100 if original_size > 0 else 0
                    
                    logger.info(f"  Compressed to {comp_mb:.1f} MB ({reduction:.1f}% reduction)")
                    
                    # Remove original
                    shutil.rmtree(log_dir)
                    logger.info(f"  [SYMBOL] Archived and removed: {log_dir.name}")
                    
                    archived_count += 1
                    total_size += original_size
                    compressed_size += comp_size
                else:
                    logger.error(f"  [SYMBOL] Failed to compress {log_dir.name}")
            else:
                logger.info(f"  [DRY RUN] Would archive and remove: {log_dir.name}")
                archived_count += 1
                total_size += original_size
                
        except Exception as e:
            logger.error(f"Error archiving {log_dir.name}: {e}")
    
    # Summary
    logger.info("=" * 60)
    logger.info("LOG ROTATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Directories archived: {archived_count}")
    logger.info(f"Original size: {total_size / (1024**3):.2f} GB")
    
    if not DRY_RUN and compressed_size > 0:
        logger.info(f"Compressed size: {compressed_size / (1024**3):.2f} GB")
        reduction = (1 - compressed_size / total_size) * 100 if total_size > 0 else 0
        logger.info(f"Space saved: {reduction:.1f}%")
        logger.info(f"Archive location: {ARCHIVE_DIR}")
    
    if DRY_RUN:
        logger.info("DRY RUN - No files were actually moved or compressed")
    else:
        logger.info("Log rotation completed successfully")


if __name__ == "__main__":
    try:
        rotate_logs()
    except Exception as e:
        logger.error(f"Log rotation failed: {e}")
        raise
