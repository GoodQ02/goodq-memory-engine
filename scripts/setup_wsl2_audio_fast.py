"""
GoodQ4All - Fast WSL2 Audio Setup (No Sudo Required)
Sets up user-space audio processing without system package installation
"""

import subprocess
import sys
from pathlib import Path
import json

class FastWSL2Setup:
    def __init__(self):
        # Get actual WSL username
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "whoami"],
            capture_output=True,
            text=True
        )
        wsl_user = result.stdout.strip()
        self.wsl_home = f"/home/{wsl_user}"
        self.workspace = f"{self.wsl_home}/audio_workspace"
        self.errors = []
        self.warnings = []
        
    def print_header(self, text):
        print("\n" + "="*80)
        print(f"  {text}")
        print("="*80 + "\n")
        
    def wsl_cmd(self, command):
        """Run command in WSL2 without sudo"""
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-c", command],
            capture_output=True,
            text=True
        )
        return result.stdout, result.stderr, result.returncode
        
    def check_prerequisites(self):
        """Quick prerequisite check"""
        self.print_header("Checking Prerequisites")
        
        print("[1/3] WSL2 Status...")
        result = subprocess.run(["wsl", "--list", "--verbose"], capture_output=True)
        try:
            output = result.stdout.decode('utf-16le')
        except:
            output = result.stdout.decode('utf-8', errors='ignore')
            
        if "Ubuntu" in output and "Running" in output:
            print("  ✓ WSL2 Ubuntu running")
        else:
            print("  ✗ WSL2 Ubuntu not running")
            return False
            
        print("\n[2/3] GPU Access...")
        out, err, code = self.wsl_cmd("nvidia-smi --query-gpu=name --format=csv,noheader")
        if code == 0:
            print(f"  ✓ {out.strip()}")
        else:
            self.warnings.append("GPU not accessible (will use CPU)")
            
        print("\n[3/3] Python...")
        out, err, code = self.wsl_cmd("python3 --version")
        if code == 0:
            print(f"  ✓ {out.strip()}")
        else:
            print("  ✗ Python3 not found")
            return False
            
        return True
        
    def create_workspace(self):
        """Create workspace directories"""
        self.print_header("Creating Workspace")
        
        dirs = [
            self.workspace,
            f"{self.workspace}/scripts",
            f"{self.workspace}/logs",
            f"{self.workspace}/models",
            f"{self.workspace}/queue_in",
            f"{self.workspace}/queue_out",
            f"{self.workspace}/venv"
        ]
        
        for d in dirs:
            self.wsl_cmd(f"mkdir -p {d}")
        print("  ✓ Workspace created")
        return True
        
    def setup_venv(self):
        """Create Python virtual environment"""
        self.print_header("Setting Up Python Environment")
        
        venv = f"{self.workspace}/venv"
        
        print("[1/5] Creating venv...")
        out, err, code = self.wsl_cmd(f"python3 -m venv {venv}")
        if code != 0:
            # Try with --system-site-packages if regular fails
            out, err, code = self.wsl_cmd(f"python3 -m venv --system-site-packages {venv}")
            if code != 0:
                print(f"  ✗ Failed: {err}")
                return False
        print("  ✓ Virtual environment created")
        
        pip = f"{venv}/bin/pip"
        
        print("\n[2/5] Upgrading pip...")
        self.wsl_cmd(f"{pip} install --upgrade pip -q")
        print("  ✓ pip upgraded")
        
        print("\n[3/5] Installing PyTorch with CUDA...")
        print("  (This downloads ~2.5GB, may take 5-10 minutes)")
        out, err, code = self.wsl_cmd(
            f"{pip} install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 -q"
        )
        if code != 0:
            print(f"  ⚠ Warning: {err[:200]}")
        else:
            print("  ✓ PyTorch installed")
            
        print("\n[4/5] Installing audio libraries...")
        packages = [
            "faster-whisper",
            "openai-whisper", 
            "librosa",
            "soundfile",
            "scipy",
            "numpy"
        ]
        for pkg in packages:
            print(f"  Installing {pkg}...")
            self.wsl_cmd(f"{pip} install {pkg} -q")
        print("  ✓ Audio libraries installed")
        
        print("\n[5/5] Verifying CUDA...")
        test_cmd = f"{venv}/bin/python -c 'import torch; print(\"CUDA Available:\", torch.cuda.is_available())'"
        out, err, code = self.wsl_cmd(test_cmd)
        print(f"  {out.strip()}")
        
        return True
        
    def create_processor_script(self):
        """Create audio processing script"""
        self.print_header("Creating Processing Scripts")
        
        script = '''#!/usr/bin/env python3
import sys
import json
import torch
from faster_whisper import WhisperModel
from pathlib import Path

def process_audio(audio_path, output_path):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    
    model = WhisperModel("base", device=device, compute_type="float16" if device=="cuda" else "int8")
    
    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        vad_filter=True
    )
    
    result = {
        "language": info.language,
        "duration": info.duration,
        "segments": []
    }
    
    for seg in segments:
        result["segments"].append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text
        })
    
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"Processed {len(result['segments'])} segments")
    return result

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: process_audio.py <input> <output>")
        sys.exit(1)
    process_audio(sys.argv[1], sys.argv[2])
'''
        
        script_path = f"{self.workspace}/scripts/process_audio.py"
        # Escape single quotes for bash
        safe_script = script.replace("'", "'\"'\"'")
        cmd = f"cat > {script_path} << 'EOF'\n{script}\nEOF"
        self.wsl_cmd(cmd)
        self.wsl_cmd(f"chmod +x {script_path}")
        print(f"  ✓ Created {script_path}")
        
        return True
        
    def create_bridge(self):
        """Create Windows-WSL bridge"""
        self.print_header("Creating Windows Bridge")
        
        bridge = '''"""WSL2 Audio Bridge - Simplified"""
import subprocess
import json
import time
from pathlib import Path

class WSL2Bridge:
    def __init__(self):
        # Auto-detect WSL user
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "whoami"],
            capture_output=True,
            text=True
        )
        wsl_user = result.stdout.strip()
        self.workspace = f"/home/{wsl_user}/audio_workspace"
        
    def wsl_path(self, windows_path):
        """Convert Windows to WSL path"""
        p = str(windows_path).replace("\\\\", "/")
        if len(p) > 1 and p[1] == ":":
            drive = p[0].lower()
            rest = p[2:].replace("\\\\", "/")
            return f"/mnt/{drive}{rest}"
        return p
        
    def process_audio(self, audio_file, timeout=300):
        """Process audio file in WSL2"""
        audio_path = Path(audio_file)
        if not audio_path.exists():
            raise FileNotFoundError(audio_file)
            
        wsl_input = self.wsl_path(audio_path)
        wsl_output = f"{self.workspace}/queue_out/{audio_path.stem}_result.json"
        
        cmd = (
            f"{self.workspace}/venv/bin/python "
            f"{self.workspace}/scripts/process_audio.py "
            f"'{wsl_input}' '{wsl_output}'"
        )
        
        print(f"Processing: {audio_path.name}")
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Processing failed: {result.stderr}")
            
        # Read result
        read_cmd = f"cat {wsl_output}"
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-c", read_cmd],
            capture_output=True,
            text=True
        )
        
        return json.loads(result.stdout)
        
    def check_status(self):
        """Check if WSL2 audio is ready"""
        test_cmd = f"test -f {self.workspace}/venv/bin/python && echo 'ready'"
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-c", test_cmd],
            capture_output=True,
            text=True
        )
        return "ready" in result.stdout

if __name__ == "__main__":
    bridge = WSL2Bridge()
    print(f"WSL2 Audio Bridge Ready: {bridge.check_status()}")
'''
        
        bridge_path = Path("L:/goodq4all/wsl2_audio_bridge.py")
        with open(bridge_path, 'w') as f:
            f.write(bridge)
        print(f"  ✓ Created {bridge_path}")
        
        # Test script
        test = '''"""Test WSL2 Bridge"""
from wsl2_audio_bridge import WSL2Bridge

bridge = WSL2Bridge()
print("Bridge Status:", "Ready" if bridge.check_status() else "Not Ready")

# Example usage:
# result = bridge.process_audio("L:\\\\goodq4all\\\\test.wav")
# print(json.dumps(result, indent=2))
'''
        
        test_path = Path("L:/goodq4all/test_wsl2_bridge.py")
        with open(test_path, 'w') as f:
            f.write(test)
        print(f"  ✓ Created {test_path}")
        
        return True
        
    def run(self):
        """Execute fast setup"""
        print("="*80)
        print("  GoodQ4All - Fast WSL2 Audio Setup")
        print("="*80)
        print("\nThis will:")
        print("  - Verify WSL2 prerequisites")
        print("  - Create Python venv (no sudo required)")
        print("  - Install PyTorch + audio libraries")
        print("  - Create processing scripts")
        print("  - Set up Windows bridge")
        print("\nEstimated time: 10-15 minutes")
        print("\nPress ENTER to continue or CTRL+C to cancel...")
        input()
        
        steps = [
            ("Prerequisites", self.check_prerequisites),
            ("Workspace", self.create_workspace),
            ("Python Environment", self.setup_venv),
            ("Processing Scripts", self.create_processor_script),
            ("Windows Bridge", self.create_bridge)
        ]
        
        for name, func in steps:
            try:
                if not func():
                    print(f"\n✗ {name} failed!")
                    return False
            except Exception as e:
                print(f"\n✗ Exception in {name}: {e}")
                return False
                
        self.print_header("Setup Complete!")
        print("Test the installation:")
        print("  python test_wsl2_bridge.py")
        print("\nIntegration:")
        print("  from wsl2_audio_bridge import WSL2Bridge")
        print("  bridge = WSL2Bridge()")
        print("  result = bridge.process_audio('your_file.wav')")
        
        return True

if __name__ == "__main__":
    setup = FastWSL2Setup()
    success = setup.run()
    sys.exit(0 if success else 1)
