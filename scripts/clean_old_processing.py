#!/usr/bin/env python3
"""
Clean Old Processing Files

Purpose: Automatically clean processing directory of stale files
Author: GoodQ Development Team
Created: 2025-11-07

This script removes processing files older than 48 hours that are
no longer actively being processed.
"""

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PROCESSING_DIR = Path("L:/_DATA/GoodQ_Data/processing")
MAX_AGE_HOURS = 48
DRY_RUN = False  # Set to True to see what would be deleted without actually deleting


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


def is_safe_to_delete(path: Path, max_age_hours: int) -> bool:
    """Check if directory is safe to delete (no recent activity)."""
    cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
    
    try:
        # Check all files in directory
        for item in path.rglob('*'):
            if item.is_file():
                # Check both modification and access time
                if item.stat().st_mtime > cutoff_time.timestamp():
                    return False
    except Exception as e:
        logger.error(f"Error checking {path}: {e}")
        return False
    
    return True


def clean_old_processing():
    """Clean processing files older than MAX_AGE_HOURS."""
    
    if not PROCESSING_DIR.exists():
        logger.info(f"Processing directory does not exist: {PROCESSING_DIR}")
        return
    
    logger.info(f"Scanning processing directory: {PROCESSING_DIR}")
    logger.info(f"Max age: {MAX_AGE_HOURS} hours")
    
    if DRY_RUN:
        logger.info("DRY RUN MODE - No files will be deleted")
    
    total_cleaned = 0
    total_size = 0
    items_cleaned = 0
    
    # Get all subdirectories in processing
    items = [d for d in PROCESSING_DIR.iterdir() if d.is_dir()]
    
    if not items:
        logger.info("Processing directory is empty")
        return
    
    logger.info(f"Found {len(items)} items to check")
    
    for item in items:
        age = datetime.now() - datetime.fromtimestamp(item.stat().st_mtime)
        age_hours = age.total_seconds() / 3600
        
        logger.info(f"Checking: {item.name} (age: {age_hours:.1f} hours)")
        
        if is_safe_to_delete(item, MAX_AGE_HOURS):
            size = get_directory_size(item)
            size_mb = size / (1024 * 1024)
            
            logger.info(f"  → Safe to delete: {item.name} ({size_mb:.1f} MB)")
            
            if not DRY_RUN:
                try:
                    shutil.rmtree(item)
                    items_cleaned += 1
                    total_size += size
                    logger.info(f"  [SYMBOL] Deleted: {item.name}")
                except Exception as e:
                    logger.error(f"  [SYMBOL] Failed to delete {item.name}: {e}")
            else:
                items_cleaned += 1
                total_size += size
                logger.info(f"  [DRY RUN] Would delete: {item.name}")
        else:
            logger.info(f"  → Skipping (recent activity): {item.name}")
    
    # Summary
    total_size_gb = total_size / (1024 * 1024 * 1024)
    
    logger.info("=" * 60)
    logger.info("CLEANUP SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Items cleaned: {items_cleaned}")
    logger.info(f"Space recovered: {total_size_gb:.2f} GB")
    
    if DRY_RUN:
        logger.info("DRY RUN - No files were actually deleted")
    else:
        logger.info("Cleanup completed successfully")


if __name__ == "__main__":
    try:
        clean_old_processing()
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise
