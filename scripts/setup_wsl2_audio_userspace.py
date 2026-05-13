"""
GoodQ4All - WSL2 Audio Setup (User-Space Only)
Installs everything in user space without venv or sudo
"""

import subprocess
import sys
import os
from pathlib import Path

WSL_AUDIO_TORCH_VERSION = "2.5.1+cu121"
WSL_AUDIO_TORCHVISION_VERSION = "0.20.1+cu121"
WSL_AUDIO_TORCHAUDIO_VERSION = "2.5.1+cu121"
WSL_AUDIO_TORCH_INDEX_URL = "https://download.pytorch.org/whl/cu121"
WSL_AUDIO_BOOTSTRAP_CONSTRAINTS = "requirements-bootstrap-constraints.txt"

class UserSpaceWSL2Setup:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parents[1]
        self.wsl_distro = os.environ.get("GOODQ_WSL_DISTRO", "Ubuntu")
        wsl_user = os.environ.get("GOODQ_WSL_USER", "").strip()
        if not wsl_user:
            result = subprocess.run(
                ["wsl", "-d", self.wsl_distro, "--", "whoami"],
                capture_output=True,
                text=True
            )
            wsl_user = result.stdout.strip()
        if not wsl_user:
            wsl_user = os.environ.get("USERNAME", "user").strip().lower() or "user"
        self.wsl_home = f"/home/{wsl_user}"
        self.workspace = f"{self.wsl_home}/goodq_audio"
        
    def print_header(self, text):
        print("\n" + "="*80)
        print(f"  {text}")
        print("="*80 + "\n")
        
    def wsl_cmd(self, command, timeout=None):
        """Run command in WSL2"""
        try:
            result = subprocess.run(
                ["wsl", "-d", self.wsl_distro, "--", "bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "Timeout", -1

    def stage_constraints_file(self):
        src = self.base_dir / "wsl2_audio" / WSL_AUDIO_BOOTSTRAP_CONSTRAINTS
        if not src.exists():
            print(f"  [SYMBOL] Missing bootstrap constraints file: {src}")
            return False
        content = src.read_text(encoding="utf-8")
        dst = f"{self.workspace}/{WSL_AUDIO_BOOTSTRAP_CONSTRAINTS}"
        out, err, code = self.wsl_cmd(f"cat > {dst} << 'EOF'\n{content}\nEOF")
        if code != 0:
            print(f"  [SYMBOL] Failed to stage bootstrap constraints: {(err or out)[:160]}")
            return False
        return True

    def validate_runtime(self):
        self.print_header("Validating WSL Audio Runtime")
        expected = {
            "torch": WSL_AUDIO_TORCH_VERSION,
            "torchvision": WSL_AUDIO_TORCHVISION_VERSION,
            "torchaudio": WSL_AUDIO_TORCHAUDIO_VERSION,
        }

        print("[1/2] Running pip check...")
        out, err, code = self.wsl_cmd("python3 -m pip check")
        if code != 0:
            print(f"  [SYMBOL] pip check failed: {(out or err)[:200]}")
            return False
        print("  [SYMBOL] pip check passed")

        print("\n[2/2] Verifying torch trio + ABI...")
        verify_script = f"""
import importlib.metadata as md
import torch
import torchaudio
import torchvision
from torchvision.ops import nms

expected = {{
    "torch": "{expected['torch']}",
    "torchvision": "{expected['torchvision']}",
    "torchaudio": "{expected['torchaudio']}",
}}
actual = {{name: md.version(name) for name in expected}}
bad = [f"{{name}}={{actual[name]}} (expected {{version}})" for name, version in expected.items() if actual[name] != version]
if bad:
    raise SystemExit("WSL audio runtime drift detected: " + "; ".join(bad))
print("abi_ready")
""".strip()
        verify_cmd = f"python3 <<'PYEOF'\n{verify_script}\nPYEOF"
        out, err, code = self.wsl_cmd(verify_cmd)
        if code != 0:
            print(f"  [SYMBOL] Runtime validation failed: {(err or out)[:200]}")
            return False
        print("  [SYMBOL] ABI-ready torch lane verified")
        return True
            
    def check_system(self):
        """Check WSL2 system"""
        self.print_header("System Check")
        
        print("[1/3] WSL2...")
        result = subprocess.run(["wsl", "--list", "--verbose"], capture_output=True)
        try:
            output = result.stdout.decode('utf-16le')
        except:
            output = result.stdout.decode('utf-8', errors='ignore')
        if "Ubuntu" in output and "Running" in output:
            print("  [SYMBOL] Running")
        else:
            return False
            
        print("\n[2/3] GPU...")
        out, err, code = self.wsl_cmd("nvidia-smi --query-gpu=name --format=csv,noheader")
        if code == 0:
            print(f"  [SYMBOL] {out.strip()}")
        else:
            print("  [SYMBOL] No GPU (will use CPU)")
            
        print("\n[3/3] Python & pip...")
        out, err, code = self.wsl_cmd("python3 --version && pip3 --version")
        if code == 0:
            for line in out.strip().split('\n'):
                print(f"  [SYMBOL] {line}")
        else:
            return False
            
        return True
        
    def create_workspace(self):
        """Create workspace"""
        self.print_header("Creating Workspace")
        
        dirs = [
            self.workspace,
            f"{self.workspace}/scripts",
            f"{self.workspace}/models",
            f"{self.workspace}/queue_in",
            f"{self.workspace}/queue_out"
        ]
        
        for d in dirs:
            self.wsl_cmd(f"mkdir -p {d}")
        print("  [SYMBOL] Workspace created")
        if not self.stage_constraints_file():
            return False
        print("  [SYMBOL] Bootstrap constraints staged")
        return True
        
    def install_packages(self):
        """Install Python packages in user space"""
        self.print_header("Installing Python Packages")
        
        packages = [
            ("torch", "PyTorch with CUDA"),
            ("faster-whisper", "Fast Whisper transcription"),
            ("openai-whisper", "OpenAI Whisper (fallback)"),
            ("librosa", "Audio processing"),
            ("soundfile", "Audio I/O"),
            ("scipy", "Scientific computing"),
            ("numpy", "Numerical operations")
        ]
        
        print("Installing packages (this may take 10-15 minutes)...")
        print("Using --user flag to install in user space\n")
        constraints_path = f"{self.workspace}/{WSL_AUDIO_BOOTSTRAP_CONSTRAINTS}"
        
        for i, (pkg, desc) in enumerate(packages, 1):
            print(f"[{i}/{len(packages)}] {desc}...")
            
            if pkg == "torch":
                cmd = (
                    "pip3 install --user "
                    f"torch=={WSL_AUDIO_TORCH_VERSION} "
                    f"torchvision=={WSL_AUDIO_TORCHVISION_VERSION} "
                    f"torchaudio=={WSL_AUDIO_TORCHAUDIO_VERSION} "
                    f"--index-url {WSL_AUDIO_TORCH_INDEX_URL}"
                )
            else:
                cmd = f"pip3 install --user --constraint {constraints_path} {pkg}"
                
            out, err, code = self.wsl_cmd(cmd, timeout=600)
            
            if code == 0 or "Requirement already satisfied" in out or "Requirement already satisfied" in err:
                print(f"  [SYMBOL] Installed")
            else:
                print(f"  [SYMBOL] Issue (may still work): {err[:100]}")
                
        print("\nVerifying installations...")
        test_cmd = """python3 -c "
import torch
import whisper
import librosa
print(f'PyTorch: {torch.__version__}')
print(f'CUDA Available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
print(f'Whisper: OK')
print(f'Librosa: {librosa.__version__}')
" 2>&1"""
        
        out, err, code = self.wsl_cmd(test_cmd)
        if code == 0:
            for line in out.strip().split('\n'):
                print(f"  [SYMBOL] {line}")
        else:
            print(f"  [SYMBOL] Verification had issues: {err[:200]}")
            
        return True
        
    def create_scripts(self):
        """Create processing scripts"""
        self.print_header("Creating Processing Scripts")
        
        # Simple processor
        processor = '''#!/usr/bin/env python3
"""Simple Audio Processor for GoodQ"""
import sys
import json
import torch
from pathlib import Path

try:
    from faster_whisper import WhisperModel
    USE_FASTER = True
except:
    import whisper
    USE_FASTER = False

def process_audio(audio_path, output_path):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    print(f"Processing: {Path(audio_path).name}")
    
    if USE_FASTER:
        model = WhisperModel("base", device=device)
        segments, info = model.transcribe(audio_path, beam_size=5, vad_filter=True)
        
        result = {
            "language": info.language,
            "duration": info.duration,
            "segments": [
                {"start": s.start, "end": s.end, "text": s.text}
                for s in segments
            ]
        }
    else:
        model = whisper.load_model("base", device=device)
        result_data = model.transcribe(audio_path)
        result = {
            "language": result_data["language"],
            "duration": None,
            "segments": [
                {"start": s["start"], "end": s["end"], "text": s["text"]}
                for s in result_data["segments"]
            ]
        }
    
    Path(output_path).write_text(json.dumps(result, indent=2))
    print(f"Output: {output_path}")
    print(f"Segments: {len(result['segments'])}")
    return result

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: process.py <input_audio> <output_json>")
        sys.exit(1)
    process_audio(sys.argv[1], sys.argv[2])
'''
        
        script_path = f"{self.workspace}/scripts/process.py"
        # Write via WSL
        safe_script = processor.replace("'", "'\\''")
        cmd = f"cat > {script_path} <<'SCRIPT_END'\n{processor}\nSCRIPT_END"
        self.wsl_cmd(cmd)
        self.wsl_cmd(f"chmod +x {script_path}")
        print(f"  [SYMBOL] Created processing script")
        
        return True
        
    def create_bridge(self):
        """Create Windows bridge"""
        self.print_header("Creating Windows-WSL2 Bridge")
        
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "whoami"],
            capture_output=True,
            text=True
        )
        wsl_user = result.stdout.strip()
        
        bridge_code = f'''"""
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
        self.workspace = "/home/{wsl_user}/goodq_audio"
        self.wsl_user = "{wsl_user}"
        
    def wsl_path(self, windows_path):
        """Convert Windows path to WSL path"""
        p = str(windows_path).replace("\\\\", "/")
        if len(p) > 1 and p[1] == ":":
            drive = p[0].lower()
            rest = p[2:].replace("\\\\", "/")
            return f"/mnt/{{drive}}{{rest}}"
        return p
        
    def windows_path(self, wsl_path):
        """Convert WSL path to Windows path"""
        if wsl_path.startswith("/mnt/"):
            parts = wsl_path[5:].split("/", 1)
            drive = parts[0].upper()
            rest = parts[1] if len(parts) > 1 else ""
            return f"{{drive}}:\\\\{{rest.replace('/', '\\\\')}}"
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
            raise FileNotFoundError(f"Audio file not found: {{audio_file}}")
            
        # Convert to WSL path
        wsl_input = self.wsl_path(audio_path)
        
        # Set output path
        if output_file is None:
            output_file = audio_path.parent / f"{{audio_path.stem}}_transcript.json"
        wsl_output = self.wsl_path(output_file)
        
        # Build command
        cmd = (
            f"python3 {{self.workspace}}/scripts/process.py "
            f"'{{wsl_input}}' '{{wsl_output}}'"
        )
        
        print(f"Processing: {{audio_path.name}}")
        print(f"Output: {{output_file}}")
        
        # Execute in WSL2
        try:
            result = subprocess.run(
                ["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"Processing failed: {{result.stderr}}")
                
            # Read results
            if Path(output_file).exists():
                with open(output_file) as f:
                    return json.load(f)
            else:
                raise RuntimeError("Output file not created")
                
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Processing timeout after {{timeout}}s")
            
    def check_status(self):
        """Check if WSL2 audio is ready"""
        test_cmd = f"test -f {{self.workspace}}/scripts/process.py && python3 -c 'import torch; print(torch.cuda.is_available())'"
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
print(f'Device: {{\"cuda\" if torch.cuda.is_available() else \"cpu\"}}')
if torch.cuda.is_available():
    print(f'GPU: {{torch.cuda.get_device_name(0)}}')
    print(f'VRAM: {{torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}}GB')
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
'''
        
        bridge_path = self.base_dir / "wsl2_audio_bridge.py"
        with open(bridge_path, 'w') as f:
            f.write(bridge_code)
        print(f"  [SYMBOL] Created {bridge_path}")
        
        return True
        
    def run(self):
        """Execute setup"""
        print("="*80)
        print("  GoodQ4All - WSL2 Audio Setup (User-Space)")
        print("="*80)
        print("\nThis will install audio processing in WSL2 user space")
        print("No sudo required - all packages installed with --user flag")
        print("\nFeatures:")
        print("  [SYMBOL] GPU-accelerated Whisper transcription")
        print("  [SYMBOL] Faster-Whisper for speed")
        print("  [SYMBOL] Librosa for audio processing")
        print("  [SYMBOL] Windows-WSL2 bridge for integration")
        print("\nEstimated time: 10-15 minutes")
        print("\nPress ENTER to continue or CTRL+C to cancel...")
        input()
        
        steps = [
            ("System Check", self.check_system),
            ("Workspace", self.create_workspace),
            ("Python Packages", self.install_packages),
            ("Runtime Validation", self.validate_runtime),
            ("Processing Scripts", self.create_scripts),
            ("Windows Bridge", self.create_bridge)
        ]
        
        for name, func in steps:
            try:
                if not func():
                    print(f"\n[SYMBOL] {name} failed!")
                    return False
            except Exception as e:
                print(f"\n[SYMBOL] Exception in {name}: {e}")
                import traceback
                traceback.print_exc()
                return False
                
        self.print_header("Setup Complete!")
        
        print("Test the installation:")
        print("  python wsl2_audio_bridge.py")
        print()
        print("Use in your pipeline:")
        print("  from wsl2_audio_bridge import WSL2AudioBridge")
        print("  bridge = WSL2AudioBridge()")
        print("  result = bridge.process_audio('sample.wav')")
        print("  for seg in result['segments']:")
        print("      print(f\"{seg['start']:.1f}s: {seg['text']}\")")
        print()
        print("Next: Integrate with GoodQ pipeline steps")
        
        return True

if __name__ == "__main__":
    setup = UserSpaceWSL2Setup()
    success = setup.run()
    sys.exit(0 if success else 1)
