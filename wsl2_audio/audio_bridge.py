"""
GoodQ4All - Windows to WSL2 Audio Bridge

This module provides a bridge between the Windows-based pipeline
and the WSL2 audio processing service.
"""

import json
import os
import time
import uuid
import shutil
import logging
from pathlib import Path
from typing import Dict, Optional, Any
import subprocess

logger = logging.getLogger(__name__)


class WSL2AudioBridge:
    """Bridge for offloading audio processing to WSL2"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the bridge
        
        Args:
            config_path: Optional path to config file (default: wsl2_audio/bridge_config.json)
        """
        if config_path is None:
            base_dir = Path(__file__).parent.parent
            config_path = base_dir / "wsl2_audio" / "bridge_config.json"
        
        self.config = self._load_config(config_path)
        
        # Windows paths
        self.windows_queue = Path(self.config['windows_queue_dir'])
        self.windows_output = Path(self.config['windows_output_dir'])
        
        # WSL2 paths (from Windows perspective)
        wsl_home = self.config['wsl_home_dir']
        self.wsl_queue = f"{wsl_home}/queue"
        self.wsl_output = f"{wsl_home}/output"
        
        # Ensure Windows directories exist
        self.windows_queue.mkdir(parents=True, exist_ok=True)
        self.windows_output.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"WSL2 Audio Bridge initialized")
        logger.info(f"  Windows Queue: {self.windows_queue}")
        logger.info(f"  Windows Output: {self.windows_output}")
        logger.info(f"  WSL2 Queue: {self.wsl_queue}")
    
    def _load_config(self, config_path: Path) -> Dict:
        """Load configuration"""
        if not config_path.exists():
            # Create default config
            default_config = {
                "windows_queue_dir": "L:\\goodq4all\\wsl2_audio\\queue",
                "windows_output_dir": "L:\\goodq4all\\wsl2_audio\\output",
                "wsl_home_dir": "/home/$USER/goodq_audio",
                "timeout_seconds": 3600,
                "poll_interval": 1.0
            }
            
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            
            logger.info(f"Created default config: {config_path}")
            return default_config
        
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def _is_wsl_service_running(self) -> bool:
        """Check if WSL2 audio service is running"""
        try:
            result = subprocess.run(
                ["wsl", "pgrep", "-f", "audio_service.py"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"Failed to check WSL2 service status: {e}")
            return False
    
    def transcribe(
        self, 
        audio_path: str,
        language: Optional[str] = None,
        task: str = "transcribe",
        beam_size: int = 5,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio using WSL2 Whisper
        
        Args:
            audio_path: Path to audio file
            language: Optional language code (e.g., 'en')
            task: 'transcribe' or 'translate'
            beam_size: Beam size for decoding
            timeout: Timeout in seconds
            
        Returns:
            Dictionary with transcription results
        """
        job_id = str(uuid.uuid4())
        
        # Convert Windows path to WSL2 path if needed
        if audio_path.startswith("L:\\"):
            wsl_audio_path = audio_path.replace("L:\\", "/mnt/l/").replace("\\", "/")
        else:
            wsl_audio_path = audio_path
        
        # Create job
        job = {
            "job_id": job_id,
            "audio_path": wsl_audio_path,
            "output_path": f"{self.wsl_output}/{job_id}_result.json",
            "task": "transcribe",
            "params": {
                "language": language,
                "task": task,
                "beam_size": beam_size
            }
        }
        
        return self._submit_job(job, timeout)
    
    def diarize(
        self,
        audio_path: str,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform speaker diarization using WSL2 PyAnnote
        
        Args:
            audio_path: Path to audio file
            timeout: Timeout in seconds
            
        Returns:
            Dictionary with diarization results
        """
        job_id = str(uuid.uuid4())
        
        # Convert Windows path to WSL2 path if needed
        if audio_path.startswith("L:\\"):
            wsl_audio_path = audio_path.replace("L:\\", "/mnt/l/").replace("\\", "/")
        else:
            wsl_audio_path = audio_path
        
        # Create job
        job = {
            "job_id": job_id,
            "audio_path": wsl_audio_path,
            "output_path": f"{self.wsl_output}/{job_id}_result.json",
            "task": "diarize",
            "params": {}
        }
        
        return self._submit_job(job, timeout)
    
    def transcribe_and_diarize(
        self,
        audio_path: str,
        language: Optional[str] = None,
        task: str = "transcribe",
        beam_size: int = 5,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform both transcription and diarization
        
        Args:
            audio_path: Path to audio file
            language: Optional language code
            task: 'transcribe' or 'translate'
            beam_size: Beam size for decoding
            timeout: Timeout in seconds
            
        Returns:
            Dictionary with both transcription and diarization results
        """
        job_id = str(uuid.uuid4())
        
        # Convert Windows path to WSL2 path if needed
        if audio_path.startswith("L:\\"):
            wsl_audio_path = audio_path.replace("L:\\", "/mnt/l/").replace("\\", "/")
        else:
            wsl_audio_path = audio_path
        
        # Create job
        job = {
            "job_id": job_id,
            "audio_path": wsl_audio_path,
            "output_path": f"{self.wsl_output}/{job_id}_result.json",
            "task": "both",
            "params": {
                "language": language,
                "task": task,
                "beam_size": beam_size
            }
        }
        
        return self._submit_job(job, timeout)
    
    def _submit_job(self, job: Dict, timeout: Optional[int] = None) -> Dict[str, Any]:
        """Submit a job to WSL2 and wait for results"""
        job_id = job['job_id']
        
        if timeout is None:
            timeout = self.config['timeout_seconds']
        
        logger.info(f"Submitting job {job_id} to WSL2 audio service")
        
        # Check if service is running
        if not self._is_wsl_service_running():
            logger.warning("WSL2 audio service does not appear to be running")
            logger.warning("Start it with: wsl bash -c 'cd ~/goodq_audio && source venv/bin/activate && python3 /mnt/l/goodq4all/wsl2_audio/audio_service.py'")
        
        try:
            # Write job file to Windows queue
            job_file = self.windows_queue / f"{job_id}.json"
            with open(job_file, 'w') as f:
                json.dump(job, f, indent=2)
            
            # Copy to WSL2 queue using wsl command
            wsl_pending = f"{self.wsl_queue}/pending/{job_id}.json"
            subprocess.run(
                ["wsl", "cp", 
                 str(job_file).replace("\\", "/").replace("L:/", "/mnt/l/"),
                 wsl_pending],
                check=True,
                timeout=10
            )
            
            logger.info(f"Job {job_id} queued in WSL2")
            
            # Wait for result
            start_time = time.time()
            poll_interval = self.config['poll_interval']
            
            while time.time() - start_time < timeout:
                # Check for result file in Windows output
                result_file = self.windows_output / f"{job_id}_result.json"
                error_file = self.windows_output / f"{job_id}_error.json"
                
                # Try to copy result from WSL2
                try:
                    wsl_result = f"{self.wsl_output}/{job_id}_result.json"
                    wsl_error = f"{self.wsl_output}/{job_id}_error.json"
                    
                    # Try result file
                    subprocess.run(
                        ["wsl", "cp", wsl_result, 
                         str(result_file).replace("\\", "/").replace("L:/", "/mnt/l/")],
                        capture_output=True,
                        timeout=5
                    )
                    
                    if result_file.exists():
                        with open(result_file, 'r') as f:
                            result = json.load(f)
                        logger.info(f"Job {job_id} completed successfully")
                        return result
                    
                    # Try error file
                    subprocess.run(
                        ["wsl", "cp", wsl_error,
                         str(error_file).replace("\\", "/").replace("L:/", "/mnt/l/")],
                        capture_output=True,
                        timeout=5
                    )
                    
                    if error_file.exists():
                        with open(error_file, 'r') as f:
                            error = json.load(f)
                        logger.error(f"Job {job_id} failed: {error.get('error')}")
                        return error
                
                except subprocess.TimeoutExpired:
                    pass
                except Exception:
                    pass
                
                time.sleep(poll_interval)
            
            # Timeout
            logger.error(f"Job {job_id} timed out after {timeout}s")
            return {
                "job_id": job_id,
                "status": "timeout",
                "error": f"Job did not complete within {timeout} seconds"
            }
        
        except Exception as e:
            logger.error(f"Job {job_id} submission failed: {e}")
            return {
                "job_id": job_id,
                "status": "error",
                "error": str(e)
            }


# Convenience functions for easy integration
_bridge = None

def get_bridge() -> WSL2AudioBridge:
    """Get or create the global bridge instance"""
    global _bridge
    if _bridge is None:
        _bridge = WSL2AudioBridge()
    return _bridge


def transcribe_wsl2(audio_path: str, **kwargs) -> Dict[str, Any]:
    """Transcribe audio using WSL2"""
    bridge = get_bridge()
    return bridge.transcribe(audio_path, **kwargs)


def diarize_wsl2(audio_path: str, **kwargs) -> Dict[str, Any]:
    """Diarize audio using WSL2"""
    bridge = get_bridge()
    return bridge.diarize(audio_path, **kwargs)


def transcribe_and_diarize_wsl2(audio_path: str, **kwargs) -> Dict[str, Any]:
    """Transcribe and diarize audio using WSL2"""
    bridge = get_bridge()
    return bridge.transcribe_and_diarize(audio_path, **kwargs)
