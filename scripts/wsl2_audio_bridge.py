"""
GoodQ4All WSL2 Audio Bridge
Simple interface to WSL2 audio processing
"""

import subprocess
import json
import time
from pathlib import Path

class WSL2AudioBridge:
    """Bridge to WSL2 audio processing"""
    
    def __init__(self):
        self.workspace = "/home/joesdomingo/goodq_audio"
        self.wsl_user = "joesdomingo"
        
    def wsl_path(self, windows_path):
        """Convert Windows path to WSL path"""
        p = str(windows_path).replace("\\", "/")
        if len(p) > 1 and p[1] == ":":
            drive = p[0].lower()
            rest = p[2:].replace("\\", "/")
            return f"/mnt/{drive}{rest}"
        return p
        
    def windows_path(self, wsl_path):
        """Convert WSL path to Windows path"""
        if wsl_path.startswith("/mnt/"):
            parts = wsl_path[5:].split("/", 1)
            drive = parts[0].upper()
            rest = parts[1] if len(parts) > 1 else ""
            return f"{drive}:\\{rest.replace('/', '\\')}"
        return wsl_path
        
    def process_audio(self, audio_file, output_file=None, timeout=600):
        """
        Process audio file using WSL2
        
        Args:
            audio_file: Path to audio file on Windows
            output_file: Optional output path (auto-generated if None)
            timeout: Processing timeout in seconds
            
        Returns:
            dict: Processing results with transcription segments
        """
        audio_path = Path(audio_file)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")
            
        # Convert to WSL path
        wsl_input = self.wsl_path(audio_path)
        
        # Build command - use the process.sh wrapper (handles cuDNN paths)
        cmd = f"{self.workspace}/scripts/process.sh '{wsl_input}'"
        
        print(f"Processing: {audio_path.name}")
        
        # Execute in WSL2
        try:
            result = subprocess.run(
                ["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"Processing failed: {result.stderr}")
                
            # Parse JSON output from process.py
            output = json.loads(result.stdout)
            
            if output.get("status") != "success":
                raise RuntimeError(f"Processing error: {output.get('error', 'Unknown error')}")
            
            return output
                
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Processing timeout after {timeout}s")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON output: {e}\nOutput: {result.stdout}")
            
    def check_status(self):
        """Check if WSL2 audio is ready"""
        test_cmd = f"test -x {self.workspace}/scripts/process.sh && {self.workspace}/venv/bin/python3 -c 'import torch; print(torch.cuda.is_available())' 2>&1"
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-c", test_cmd],
            capture_output=True,
            text=True
        )
        # Check if process.sh exists and CUDA is available
        return result.returncode == 0 and "True" in result.stdout
        
    def get_info(self):
        """Get WSL2 audio system info"""
        info_cmd = f"{self.workspace}/venv/bin/python3 -c \"import torch; print(f'Device: {{\\\"cuda\\\" if torch.cuda.is_available() else \\\"cpu\\\"}}'); import sys; sys.stdout.flush(); print(f'GPU: {{torch.cuda.get_device_name(0)}}') if torch.cuda.is_available() else None; print(f'VRAM: {{torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}}GB') if torch.cuda.is_available() else None\" 2>&1"
        
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-c", info_cmd],
            capture_output=True,
            text=True
        )
        return result.stdout if result.returncode == 0 else "Not available"

# Example usage
if __name__ == "__main__":
    bridge = WSL2AudioBridge()
    
    print("="*60)
    print("  GoodQ4All WSL2 Audio Bridge")
    print("="*60)
    print()
    print("Status:", "Ready" if bridge.check_status() else "Not Ready")
    print()
    print("System Info:")
    print(bridge.get_info())
    print()
    print("="*60)
    print()
    print("Usage:")
    print("  from wsl2_audio_bridge import WSL2AudioBridge")
    print("  bridge = WSL2AudioBridge()")
    print("  result = bridge.process_audio('path/to/audio.wav')")
    print("  print(result['segments'])")
