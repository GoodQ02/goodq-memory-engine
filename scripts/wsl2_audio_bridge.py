"""
GoodQ4All WSL2 Audio Bridge
Simple interface to WSL2 audio processing
"""

import subprocess
import json
import time
import os
from pathlib import Path

class WSL2AudioBridge:
    """Bridge to WSL2 audio processing"""
    
    def __init__(self):
        self.wsl_user = os.environ.get("GOODQ_WSL_USER", "joesdomingo")
        self.workspace = os.environ.get("GOODQ_WSL_WORKSPACE", "/home/joesdomingo/goodq_audio")
        self.wsl_distro = os.environ.get("GOODQ_WSL_DISTRO", "Ubuntu")
        
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
            # Avoid backslashes inside f-string expressions (invalid syntax).
            rest_win = rest.replace("/", "\\")
            return f"{drive}:\\{rest_win}"
        return wsl_path
        
    def process_audio(self, audio_file, output_file=None, timeout=None, audio_duration=None):
        """
        Process audio file using WSL2
        
        Args:
            audio_file: Path to audio file on Windows
            output_file: Optional output path (auto-generated if None)
            timeout: Processing timeout in seconds (auto-calculated if None)
            audio_duration: Audio duration in seconds (for timeout calculation)
            
        Returns:
            dict: Processing results with transcription segments
        """
        audio_path = Path(audio_file)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")
            
        # Calculate dynamic timeout based on audio duration
        # Formula: base_overhead + (duration * processing_factor)
        if timeout is None:
            if audio_duration:
                # 120s base + 4x duration (for transcription + diarization + emotion + embeddings)
                timeout = max(300, int(120 + (audio_duration * 4)))
            else:
                timeout = 1200  # Default 20min fallback
            
        # Convert to WSL path
        wsl_input = self.wsl_path(audio_path)
        
        # Output directory for results
        wsl_output = f"{self.workspace}/output"
        
        # Build command - use CUDA environment setup (includes venv + cuDNN paths)
        cmd = f"source {self.workspace}/setup_cuda_env.sh && python3 {self.workspace}/scripts/process_audio.py '{wsl_input}' '{wsl_output}'"
        
        print(f"Processing: {audio_path.name}")
        
        def _stderr_warnings(stderr: str, max_lines: int = 50, max_chars: int = 300) -> list[str]:
            warnings: list[str] = []
            for line in (stderr or "").splitlines():
                line = line.strip()
                if not line:
                    continue
                if len(line) > max_chars:
                    line = line[:max_chars] + "..."
                warnings.append(line)
                if len(warnings) >= max_lines:
                    break
            return warnings

        def _try_parse_json(text: str) -> dict | None:
            text = (text or "").strip()
            if not text:
                return None
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None

        def _try_read_result_json() -> dict | None:
            # Best-effort: if stdout is empty/invalid, attempt to read the output artifact.
            # The WSL script writes <output_dir>/result.json on both success and error paths.
            try:
                read_cmd = ["wsl", "-d", self.wsl_distro, "--", "cat", f"{wsl_output}/result.json"]
                read_result = subprocess.run(read_cmd, capture_output=True, text=True, timeout=10)
            except Exception:
                return None
            if read_result.returncode != 0:
                return None
            return _try_parse_json(read_result.stdout)

        # Execute in WSL2
        try:
            result = subprocess.run(
                ["wsl", "-d", self.wsl_distro, "--", "bash", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            stderr_warnings = _stderr_warnings(result.stderr)

            output = _try_parse_json(result.stdout)
            if output is None:
                output = _try_read_result_json()

            if output is None:
                # No structured output available; preserve stderr as warnings (non-fatal details).
                return {
                    "status": "error",
                    "error": "No JSON output from WSL audio processor",
                    "returncode": result.returncode,
                    "stderr_warnings": stderr_warnings,
                }

            # Always attach stderr warnings for observability; stderr is not a failure signal on its own.
            if stderr_warnings:
                output.setdefault("stderr_warnings", stderr_warnings)
            output.setdefault("returncode", result.returncode)

            # Success is driven by JSON status + required fields, not stderr noise.
            if output.get("status") == "success":
                return output

            # Preserve structured error details even when the process exits non-zero.
            output.setdefault("status", "error")
            output.setdefault("error", "Unknown error")
            return output

        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "error": f"Processing timeout after {timeout}s",
                "returncode": None,
            }
            
    def check_status(self):
        """Check if WSL2 audio is ready"""
        test_cmd = f"source {self.workspace}/setup_cuda_env.sh && python3 -c 'import torch; print(torch.cuda.is_available())' 2>&1"
        result = subprocess.run(
            ["wsl", "-d", self.wsl_distro, "--", "bash", "-c", test_cmd],
            capture_output=True,
            text=True
        )
        # Check if CUDA environment works
        return result.returncode == 0 and "True" in result.stdout
        
    def get_info(self):
        """Get WSL2 audio system info"""
        info_cmd = f"source {self.workspace}/setup_cuda_env.sh && python3 -c \"import torch; print(f'Device: {{\\\"cuda\\\" if torch.cuda.is_available() else \\\"cpu\\\"}}'); import sys; sys.stdout.flush(); print(f'GPU: {{torch.cuda.get_device_name(0)}}') if torch.cuda.is_available() else None; print(f'VRAM: {{torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}}GB') if torch.cuda.is_available() else None\" 2>&1"
        
        result = subprocess.run(
            ["wsl", "-d", self.wsl_distro, "--", "bash", "-c", info_cmd],
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
