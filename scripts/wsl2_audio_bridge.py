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
        self.require_wsl_audio = self._is_truthy(os.environ.get("GOODQ_REQUIRE_WSL_AUDIO", ""))
        self.wsl_user = self._resolve_wsl_user()
        self.workspace = self._resolve_wsl_workspace()
        self.audio_workspace = f"{self.workspace.rstrip('/')}/wsl2_audio"
        self.wsl_distro = os.environ.get("GOODQ_WSL_DISTRO", "Ubuntu")
        self._workspace_checked = False
        self._workspace_warned = False
        self._workspace_ready = False

    @staticmethod
    def _is_truthy(value):
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _resolve_wsl_user(self):
        explicit = os.environ.get("GOODQ_WSL_USER")
        if explicit:
            return explicit
        if self.require_wsl_audio:
            raise RuntimeError(
                "GOODQ_REQUIRE_WSL_AUDIO=1 requires GOODQ_WSL_USER to be set explicitly."
            )
        for candidate in (os.environ.get("USER"), os.environ.get("USERNAME"), os.environ.get("LOGNAME")):
            if candidate:
                return candidate
        return "user"

    def _resolve_wsl_workspace(self):
        explicit = os.environ.get("GOODQ_WSL_WORKSPACE")
        if explicit:
            return explicit
        return f"/home/{self.wsl_user}/projects/goodq4all"

    def _ensure_workspace_ready(self):
        if self._workspace_checked and (self._workspace_ready or not self.require_wsl_audio):
            return self._workspace_ready

        try:
            check = subprocess.run(
                ["wsl", "-d", self.wsl_distro, "--", "test", "-d", self.audio_workspace],
                capture_output=True,
                timeout=5,
            )
            self._workspace_ready = check.returncode == 0
        except Exception as e:
            self._workspace_ready = False
            message = (
                f"WSL workspace preflight failed for distro={self.wsl_distro}, "
                f"workspace={self.audio_workspace}: {e}"
            )
            self._workspace_checked = True
            if self.require_wsl_audio:
                raise RuntimeError(message) from e
            if not self._workspace_warned:
                print(f"[WSL2AudioBridge][WARN] {message}")
                self._workspace_warned = True
            return False

        self._workspace_checked = True
        if not self._workspace_ready:
            message = (
                f"WSL workspace not found for distro={self.wsl_distro}, workspace={self.audio_workspace}. "
                "Set GOODQ_WSL_USER and GOODQ_WSL_WORKSPACE for deterministic host setup."
            )
            if self.require_wsl_audio:
                raise RuntimeError(message)
            if not self._workspace_warned:
                print(f"[WSL2AudioBridge][WARN] {message}")
                self._workspace_warned = True
        return self._workspace_ready
        
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

        self._ensure_workspace_ready()
            
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
        wsl_output = f"{self.audio_workspace}/output"
        
        # Build command - use CUDA environment setup (includes venv + cuDNN paths)
        cmd = f"source {self.audio_workspace}/setup_cuda_env.sh && python3 {self.audio_workspace}/process_audio.py '{wsl_input}' '{wsl_output}'"
        
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
        self._ensure_workspace_ready()
        test_cmd = f"source {self.audio_workspace}/setup_cuda_env.sh && python3 -c 'import torch; print(torch.cuda.is_available())' 2>&1"
        result = subprocess.run(
            ["wsl", "-d", self.wsl_distro, "--", "bash", "-c", test_cmd],
            capture_output=True,
            text=True
        )
        # Check if CUDA environment works
        return result.returncode == 0 and "True" in result.stdout
        
    def get_info(self):
        """Get WSL2 audio system info"""
        self._ensure_workspace_ready()
        info_cmd = f"source {self.audio_workspace}/setup_cuda_env.sh && python3 -c \"import torch; print(f'Device: {{\\\"cuda\\\" if torch.cuda.is_available() else \\\"cpu\\\"}}'); import sys; sys.stdout.flush(); print(f'GPU: {{torch.cuda.get_device_name(0)}}') if torch.cuda.is_available() else None; print(f'VRAM: {{torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}}GB') if torch.cuda.is_available() else None\" 2>&1"
        
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
