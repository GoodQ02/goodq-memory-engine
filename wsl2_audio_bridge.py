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
        
        # Set output path
        if output_file is None:
            output_file = audio_path.parent / f"{audio_path.stem}_transcript.json"
        wsl_output = self.wsl_path(output_file)
        
        # Build command
        cmd = (
            f"python3 {self.workspace}/scripts/process.py "
            f"'{wsl_input}' '{wsl_output}'"
        )
        
        print(f"Processing: {audio_path.name}")
        print(f"Output: {output_file}")
        
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
                
            # Read results
            if Path(output_file).exists():
                with open(output_file) as f:
                    return json.load(f)
            else:
                raise RuntimeError("Output file not created")
                
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Processing timeout after {timeout}s")
            
    def check_status(self):
        """Check if WSL2 audio is ready"""
        test_cmd = f"test -f {self.workspace}/scripts/process.py && python3 -c 'import torch; print(torch.cuda.is_available())'"
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-c", test_cmd],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
        
    def get_info(self):
        """Get WSL2 audio system info"""
        info_cmd = """python3 -c "
import torch
print(f'Device: {"cuda" if torch.cuda.is_available() else "cpu"}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print(f'VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB')
" 2>&1"""
        
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
