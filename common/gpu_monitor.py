"""
GPU Monitoring Utility for GoodQ Pipeline
Real-time monitoring of GPU utilization and memory usage
"""

import subprocess
import json
import time
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def get_gpu_processes() -> List[Dict[str, Any]]:
    """Get list of processes currently using the GPU"""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-compute-apps=pid,process_name,used_memory', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return []
        
        processes = []
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 3:
                processes.append({
                    'pid': int(parts[0]),
                    'name': parts[1],
                    'memory_mb': int(parts[2])
                })
        
        return processes
    except Exception as e:
        logger.error(f"Failed to get GPU processes: {e}")
        return []


def get_gpu_stats() -> Optional[Dict[str, Any]]:
    """Get current GPU statistics"""
    try:
        result = subprocess.run(
            [
                'nvidia-smi',
                '--query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total,memory.free',
                '--format=csv,noheader,nounits'
            ],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return None
        
        line = result.stdout.strip().split('\n')[0]
        parts = [p.strip() for p in line.split(',')]
        
        if len(parts) < 7:
            return None
        
        memory_used = int(parts[4])
        memory_total = int(parts[5])
        memory_free = int(parts[6])
        
        return {
            'gpu_id': int(parts[0]),
            'name': parts[1],
            'temperature_c': int(parts[2]) if parts[2] != 'N/A' else None,
            'utilization_pct': int(parts[3]) if parts[3] != 'N/A' else 0,
            'memory_used_mb': memory_used,
            'memory_total_mb': memory_total,
            'memory_free_mb': memory_free,
            'memory_utilization_pct': round((memory_used / memory_total) * 100, 1),
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get GPU stats: {e}")
        return None


def log_gpu_status(log_file: Optional[Path] = None):
    """Log current GPU status"""
    stats = get_gpu_stats()
    if not stats:
        logger.warning("GPU stats not available")
        return
    
    processes = get_gpu_processes()
    
    status_msg = (
        f"GPU {stats['gpu_id']} ({stats['name']}): "
        f"{stats['utilization_pct']}% utilization, "
        f"{stats['memory_used_mb']}/{stats['memory_total_mb']} MB memory "
        f"({stats['memory_utilization_pct']}%), "
        f"{stats['temperature_c']}°C"
    )
    
    if processes:
        status_msg += f", {len(processes)} process(es) running"
    
    logger.info(status_msg)
    
    # Log to file if specified
    if log_file:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, 'a') as f:
                f.write(f"{datetime.now().isoformat()} | {status_msg}\n")
                if processes:
                    for proc in processes:
                        f.write(f"  - PID {proc['pid']}: {proc['name']} ({proc['memory_mb']} MB)\n")
        except Exception as e:
            logger.error(f"Failed to write to log file: {e}")


def monitor_gpu(interval_seconds: int = 5, duration_seconds: Optional[int] = None, log_file: Optional[Path] = None):
    """
    Monitor GPU usage continuously
    
    Args:
        interval_seconds: How often to check GPU status
        duration_seconds: How long to monitor (None = forever)
        log_file: Optional file to log status to
    """
    logger.info(f"Starting GPU monitoring (interval={interval_seconds}s)")
    
    start_time = time.time()
    try:
        while True:
            log_gpu_status(log_file)
            
            if duration_seconds and (time.time() - start_time) >= duration_seconds:
                break
            
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        logger.info("GPU monitoring stopped by user")


def get_gpu_availability() -> Dict[str, Any]:
    """Check if GPU is available and get basic info"""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=index,name,memory.total', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return {'available': False, 'reason': 'nvidia-smi failed'}
        
        line = result.stdout.strip().split('\n')[0]
        parts = [p.strip() for p in line.split(',')]
        
        return {
            'available': True,
            'gpu_id': int(parts[0]),
            'name': parts[1],
            'memory_total_mb': int(parts[2])
        }
    except FileNotFoundError:
        return {'available': False, 'reason': 'nvidia-smi not found'}
    except Exception as e:
        return {'available': False, 'reason': str(e)}


if __name__ == '__main__':
    # CLI for monitoring
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor GPU usage')
    parser.add_argument('--interval', type=int, default=5, help='Monitoring interval in seconds')
    parser.add_argument('--duration', type=int, default=None, help='Duration to monitor in seconds')
    parser.add_argument('--log-file', type=Path, default=None, help='Log file path')
    parser.add_argument('--check-only', action='store_true', help='Only check GPU availability and exit')
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    if args.check_only:
        avail = get_gpu_availability()
        print(json.dumps(avail, indent=2))
    else:
        monitor_gpu(args.interval, args.duration, args.log_file)
