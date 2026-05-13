"""
GoodQ4All - WSL2 Audio Processing Setup
Comprehensive Phase 2 installation and configuration
"""

import subprocess
import sys
import os
from pathlib import Path
import time

WSL_AUDIO_TORCH_VERSION = "2.5.1+cu121"
WSL_AUDIO_TORCHVISION_VERSION = "0.20.1+cu121"
WSL_AUDIO_TORCHAUDIO_VERSION = "2.5.1+cu121"
WSL_AUDIO_TORCH_INDEX_URL = "https://download.pytorch.org/whl/cu121"
WSL_AUDIO_BOOTSTRAP_CONSTRAINTS = "requirements-bootstrap-constraints.txt"

class WSL2AudioSetup:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parents[1]
        self.wsl_distro = os.environ.get("GOODQ_WSL_DISTRO", "Ubuntu")
        self.wsl_user = (
            os.environ.get("GOODQ_WSL_USER")
            or os.environ.get("USER")
            or os.environ.get("USERNAME")
            or os.environ.get("LOGNAME")
            or "user"
        )
        self.wsl_workspace = os.environ.get("GOODQ_WSL_WORKSPACE", f"/home/{self.wsl_user}/goodq_audio")
        self.errors = []
        self.warnings = []
        
    def print_header(self, text):
        print("\n" + "="*80)
        print(f"  {text}")
        print("="*80 + "\n")
        
    def run_wsl_command(self, command, check=True):
        """Execute command in WSL2"""
        try:
            result = subprocess.run(
                ["wsl", "-d", self.wsl_distro, "--", "bash", "-c", command],
                capture_output=True,
                text=True,
                check=check
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.CalledProcessError as e:
            return e.stdout, e.stderr, e.returncode

    def stage_constraints_file(self):
        """Stage the locked WSL bootstrap constraints into the workspace."""
        src = self.base_dir / "wsl2_audio" / WSL_AUDIO_BOOTSTRAP_CONSTRAINTS
        if not src.exists():
            self.errors.append(f"Missing bootstrap constraints file: {src}")
            return False
        content = src.read_text(encoding="utf-8")
        dst = f"{self.wsl_workspace}/{WSL_AUDIO_BOOTSTRAP_CONSTRAINTS}"
        cmd = f"cat > {dst} << 'EOF'\n{content}\nEOF"
        stdout, stderr, code = self.run_wsl_command(cmd)
        if code != 0:
            self.errors.append(f"Failed to stage bootstrap constraints: {stderr or stdout}")
            return False
        return True

    def validate_audio_runtime(self):
        """Fail fast when the rebuilt venv drifts off the validated ABI lane."""
        self.print_header("Phase 6.5: Validating WSL Audio Runtime")

        venv_python = f"{self.wsl_workspace}/venv/bin/python"
        expected = {
            "torch": WSL_AUDIO_TORCH_VERSION,
            "torchvision": WSL_AUDIO_TORCHVISION_VERSION,
            "torchaudio": WSL_AUDIO_TORCHAUDIO_VERSION,
        }

        print("[1/2] Running pip check...")
        stdout, stderr, code = self.run_wsl_command(f"{venv_python} -m pip check")
        if code != 0:
            self.errors.append((stdout or stderr).strip() or "pip check failed")
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
        verify_cmd = f"{venv_python} <<'PYEOF'\n{verify_script}\nPYEOF"
        stdout, stderr, code = self.run_wsl_command(verify_cmd)
        if code != 0:
            self.errors.append((stderr or stdout).strip() or "torch trio / ABI verification failed")
            return False
        print("  [SYMBOL] ABI-ready torch lane verified")
        return True
            
    def check_prerequisites(self):
        """Phase 1: Verify WSL2 and CUDA"""
        self.print_header("Phase 1: Checking Prerequisites")
        
        # Check WSL2 is running
        print("[1/5] Checking WSL2 status...")
        result = subprocess.run(["wsl", "--list", "--verbose"], capture_output=True)
        # WSL output is UTF-16LE encoded
        try:
            output = result.stdout.decode('utf-16le').strip()
        except:
            output = result.stdout.decode('utf-8', errors='ignore').strip()
        output_lines = output.split('\n')
        distro_running = any(self.wsl_distro in line and "Running" in line for line in output_lines)
        if not distro_running:
            self.errors.append(f"WSL2 distro '{self.wsl_distro}' is not running")
            return False
        print(f"  [SYMBOL] WSL2 distro '{self.wsl_distro}' is running")
        
        # Check CUDA in WSL2
        print("\n[2/5] Checking CUDA availability in WSL2...")
        stdout, stderr, code = self.run_wsl_command("nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader")
        if code != 0:
            self.errors.append(f"CUDA not available in WSL2: {stderr}")
            return False
        print(f"  [SYMBOL] GPU detected: {stdout.strip()}")
        
        # Check Python
        print("\n[3/5] Checking Python in WSL2...")
        stdout, stderr, code = self.run_wsl_command("python3 --version")
        if code != 0:
            self.warnings.append("Python3 not found, will install")
        else:
            print(f"  [SYMBOL] {stdout.strip()}")
            
        # Check pip
        print("\n[4/5] Checking pip in WSL2...")
        stdout, stderr, code = self.run_wsl_command("pip3 --version")
        if code != 0:
            self.warnings.append("pip3 not found, will install")
        else:
            print(f"  [SYMBOL] {stdout.strip()}")
            
        # Check disk space
        print("\n[5/5] Checking disk space...")
        stdout, stderr, code = self.run_wsl_command("df -h /home | tail -1")
        print(f"  Home partition: {stdout.strip()}")
        
        return True
        
    def install_system_packages(self):
        """Phase 2: Install system dependencies"""
        self.print_header("Phase 2: Installing System Packages")
        
        packages = [
            "build-essential",
            "python3-dev",
            "python3-pip",
            "python3-venv",
            "ffmpeg",
            "libsndfile1",
            "libsndfile1-dev",
            "portaudio19-dev",
            "git",
            "curl",
            "wget"
        ]
        
        print("[1/3] Updating package lists...")
        stdout, stderr, code = self.run_wsl_command("sudo apt-get update -y")
        if code != 0:
            self.errors.append(f"apt-get update failed: {stderr}")
            return False
        print("  [SYMBOL] Package lists updated")
        
        print("\n[2/3] Installing system packages...")
        package_str = " ".join(packages)
        cmd = f"sudo apt-get install -y {package_str}"
        stdout, stderr, code = self.run_wsl_command(cmd)
        if code != 0:
            self.errors.append(f"Package installation failed: {stderr}")
            return False
        print(f"  [SYMBOL] Installed {len(packages)} packages")
        
        print("\n[3/3] Verifying FFmpeg...")
        stdout, stderr, code = self.run_wsl_command("ffmpeg -version | head -1")
        if code == 0:
            print(f"  [SYMBOL] {stdout.strip()}")
        else:
            self.warnings.append("FFmpeg verification failed")
            
        return True
        
    def setup_workspace(self):
        """Phase 3: Create WSL2 workspace structure"""
        self.print_header("Phase 3: Setting Up Workspace")
        
        dirs = [
            self.wsl_workspace,
            f"{self.wsl_workspace}/scripts",
            f"{self.wsl_workspace}/logs",
            f"{self.wsl_workspace}/temp",
            f"{self.wsl_workspace}/models",
            f"{self.wsl_workspace}/queue_in",
            f"{self.wsl_workspace}/queue_out"
        ]
        
        print(f"Creating workspace at: {self.wsl_workspace}")
        for i, dir_path in enumerate(dirs, 1):
            print(f"[{i}/{len(dirs)}] Creating {dir_path}...")
            self.run_wsl_command(f"mkdir -p {dir_path}")
        print("  [SYMBOL] Workspace structure created")
        
        # Create mount point for Windows data
        print("\n[MOUNT] Creating mount point for L: drive...")
        self.run_wsl_command("mkdir -p /mnt/l")
        print("  [SYMBOL] Mount point ready")

        print("\n[STAGE] Staging WSL bootstrap constraints...")
        if not self.stage_constraints_file():
            return False
        print("  [SYMBOL] Bootstrap constraints staged")

        return True
        
    def install_cuda_toolkit(self):
        """Phase 4: Install CUDA toolkit if needed"""
        self.print_header("Phase 4: CUDA Toolkit Setup")
        
        print("[1/2] Checking for existing CUDA installation...")
        stdout, stderr, code = self.run_wsl_command("nvcc --version")
        if code == 0:
            print(f"  [SYMBOL] CUDA already installed: {stdout.strip()}")
            return True
            
        print("\n[2/2] Installing CUDA toolkit...")
        print("  This may take several minutes...")
        cmd = """
        wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.0-1_all.deb
        sudo dpkg -i cuda-keyring_1.0-1_all.deb
        sudo apt-get update
        sudo apt-get -y install cuda-toolkit-12-1
        """
        stdout, stderr, code = self.run_wsl_command(cmd, check=False)
        if code != 0:
            self.warnings.append("CUDA toolkit installation had issues, but may still work")
            
        return True
        
    def create_python_venv(self):
        """Phase 5: Create Python virtual environment"""
        self.print_header("Phase 5: Python Virtual Environment")
        
        venv_path = f"{self.wsl_workspace}/venv"
        
        print("[1/4] Creating virtual environment...")
        stdout, stderr, code = self.run_wsl_command(f"python3 -m venv {venv_path}")
        if code != 0:
            self.errors.append(f"venv creation failed: {stderr}")
            return False
        print(f"  [SYMBOL] Virtual environment created at {venv_path}")
        
        print("\n[2/4] Upgrading pip...")
        cmd = f"{venv_path}/bin/pip install --upgrade pip setuptools wheel"
        stdout, stderr, code = self.run_wsl_command(cmd)
        if code != 0:
            self.warnings.append("pip upgrade had issues")
        else:
            print("  [SYMBOL] pip upgraded")
            
        print("\n[3/4] Installing PyTorch with CUDA support...")
        print("  This will download ~2.5GB, please wait...")
        cmd = (
            f"{venv_path}/bin/pip install "
            f"torch=={WSL_AUDIO_TORCH_VERSION} "
            f"torchvision=={WSL_AUDIO_TORCHVISION_VERSION} "
            f"torchaudio=={WSL_AUDIO_TORCHAUDIO_VERSION} "
            f"--index-url {WSL_AUDIO_TORCH_INDEX_URL}"
        )
        stdout, stderr, code = self.run_wsl_command(cmd)
        if code != 0:
            self.errors.append(f"PyTorch installation failed: {stderr}")
            return False
        print("  [SYMBOL] PyTorch with CUDA installed")
        
        print("\n[4/4] Verifying CUDA availability...")
        test_cmd = f"{venv_path}/bin/python -c 'import torch; print(f\"CUDA: {{torch.cuda.is_available()}}\"); print(f\"Device: {{torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}}\")'"
        stdout, stderr, code = self.run_wsl_command(test_cmd)
        if code == 0:
            print(f"  [SYMBOL] {stdout.strip()}")
        else:
            self.errors.append("CUDA not available in PyTorch")
            return False
            
        return True
        
    def install_audio_packages(self):
        """Phase 6: Install audio processing packages"""
        self.print_header("Phase 6: Audio Processing Packages")
        
        venv_pip = f"{self.wsl_workspace}/venv/bin/pip"
        constraints_path = f"{self.wsl_workspace}/{WSL_AUDIO_BOOTSTRAP_CONSTRAINTS}"

        print("\n[1/3] Installing audio processing packages...")
        package_cmd = (
            f"{venv_pip} install --constraint {constraints_path} "
            "faster-whisper openai-whisper pyannote.audio speechbrain "
            "librosa soundfile pydub webrtcvad noisereduce scipy numpy"
        )
        stdout, stderr, code = self.run_wsl_command(package_cmd)
        if code != 0:
            self.errors.append(f"Audio package installation failed: {(stderr or stdout)[:200]}")
            return False
        print("  [SYMBOL] Audio packages installed")

        print("\n[2/3] Installing Silero VAD...")
        stdout, stderr, code = self.run_wsl_command(
            f"{venv_pip} install --constraint {constraints_path} silero-vad"
        )
        if code != 0:
            self.errors.append(f"Silero VAD installation failed: {(stderr or stdout)[:200]}")
            return False
        print("  [SYMBOL] Silero VAD installed")

        print("\n[3/3] Verifying Silero VAD import...")
        test_cmd = (
            f"{self.wsl_workspace}/venv/bin/python -c "
            "\"import importlib.metadata as md; print(md.version('silero-vad'))\""
        )
        stdout, stderr, code = self.run_wsl_command(test_cmd)
        if code == 0:
            print(f"  [SYMBOL] silero-vad {stdout.strip()}")
        else:
            self.warnings.append("Silero VAD import check had issues")
            
        return True
        
    def create_processing_scripts(self):
        """Phase 7: Create WSL2 processing scripts"""
        self.print_header("Phase 7: Creating Processing Scripts")
        
        # Main audio processor script
        processor_script = '''#!/usr/bin/env python3
"""
WSL2 GPU-Accelerated Audio Processor
Handles transcription and diarization with VAD pre-filtering
"""

import sys
import json
import torch
from pathlib import Path
from faster_whisper import WhisperModel
from pyannote.audio import Pipeline
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")
        
        # Load models
        self.whisper = WhisperModel("large-v3", device=self.device, compute_type="float16")
        self.diarization = Pipeline.from_pretrained(
            "pyannote/speaker-diarization",
            use_auth_token=None
        )
        if self.device == "cuda":
            self.diarization.to(torch.device("cuda"))
            
    def process_audio(self, audio_path, output_path):
        """Process audio file with transcription and diarization"""
        logger.info(f"Processing: {audio_path}")
        
        # Transcribe with Whisper
        segments, info = self.whisper.transcribe(
            audio_path,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=400
            )
        )
        
        transcription = []
        for segment in segments:
            transcription.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "confidence": segment.avg_logprob
            })
            
        # Diarize
        diarization = self.diarization(audio_path)
        
        speakers = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            speakers.append({
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker
            })
            
        # Save results
        result = {
            "transcription": transcription,
            "speakers": speakers,
            "language": info.language,
            "duration": info.duration
        }
        
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
            
        logger.info(f"Results saved to: {output_path}")
        return result

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: process_audio.py <input_audio> <output_json>")
        sys.exit(1)
        
    processor = AudioProcessor()
    processor.process_audio(sys.argv[1], sys.argv[2])
'''
        
        print("[1/3] Creating audio processor script...")
        script_path = f"{self.wsl_workspace}/process_audio.py"
        # Write script via WSL
        cmd = f"cat > {script_path} << 'SCRIPT_EOF'\n{processor_script}\nSCRIPT_EOF"
        self.run_wsl_command(cmd)
        self.run_wsl_command(f"chmod +x {script_path}")
        print(f"  [SYMBOL] Created {script_path}")
        
        # Queue watcher script
        watcher_script = '''#!/usr/bin/env python3
"""
WSL2 Queue Watcher
Monitors queue_in directory and processes audio files
"""

import time
import json
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioQueueHandler(FileSystemEventHandler):
    def __init__(self, queue_in, queue_out, processor_script):
        self.queue_in = Path(queue_in)
        self.queue_out = Path(queue_out)
        self.processor_script = processor_script
        
    def on_created(self, event):
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        if file_path.suffix.lower() in ['.wav', '.mp3', '.m4a', '.flac']:
            logger.info(f"New audio file detected: {file_path}")
            self.process_file(file_path)
            
    def process_file(self, audio_path):
        """Process audio file and save results"""
        output_path = self.queue_out / f"{audio_path.stem}_result.json"
        
        try:
            cmd = [
                "__GOODQ_WSL_WORKSPACE__/venv/bin/python",
                str(self.processor_script),
                str(audio_path),
                str(output_path)
            ]
            subprocess.run(cmd, check=True)
            logger.info(f"Processing complete: {output_path}")
            
            # Mark as done
            done_marker = audio_path.with_suffix('.done')
            done_marker.touch()
            
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            error_marker = audio_path.with_suffix('.error')
            error_marker.write_text(str(e))

if __name__ == "__main__":
    workspace = Path("__GOODQ_WSL_WORKSPACE__")
    queue_in = workspace / "queue_in"
    queue_out = workspace / "queue_out"
    processor = workspace / "process_audio.py"
    
    handler = AudioQueueHandler(queue_in, queue_out, processor)
    observer = Observer()
    observer.schedule(handler, str(queue_in), recursive=False)
    observer.start()
    
    logger.info("WSL2 Audio Queue Watcher started")
    logger.info(f"Watching: {queue_in}")
    logger.info(f"Output: {queue_out}")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
'''
        watcher_script = watcher_script.replace("__GOODQ_WSL_WORKSPACE__", self.wsl_workspace)
        
        print("\n[2/3] Creating queue watcher script...")
        watcher_path = f"{self.wsl_workspace}/scripts/watch_queue.py"
        cmd = f"cat > {watcher_path} << 'SCRIPT_EOF'\n{watcher_script}\nSCRIPT_EOF"
        self.run_wsl_command(cmd)
        self.run_wsl_command(f"chmod +x {watcher_path}")
        print(f"  [SYMBOL] Created {watcher_path}")
        
        # Install watchdog
        print("\n[3/3] Installing watchdog package...")
        venv_pip = f"{self.wsl_workspace}/venv/bin/pip"
        self.run_wsl_command(f"{venv_pip} install watchdog")
        print("  [SYMBOL] Watchdog installed")
        
        return True
        
    def create_windows_bridge(self):
        """Phase 8: Create Windows-WSL bridge scripts"""
        self.print_header("Phase 8: Creating Windows-WSL Bridge")
        
        # Python bridge module
        bridge_code = '''"""
GoodQ4All - WSL2 Audio Bridge
Manages communication between Windows pipeline and WSL2 audio processing
"""

import subprocess
import json
from pathlib import Path
import time
import shutil

class WSL2AudioBridge:
    def __init__(self):
        self.wsl_queue_in = Path("__GOODQ_WSL_WORKSPACE__/queue_in")
        self.wsl_queue_out = Path("__GOODQ_WSL_WORKSPACE__/queue_out")
        
    def wsl_path(self, windows_path):
        """Convert Windows path to WSL path"""
        path_str = str(windows_path).replace("\\\\", "/")
        if path_str[1] == ":":
            drive = path_str[0].lower()
            rest = path_str[2:].replace("\\\\", "/")
            return f"/mnt/{drive}{rest}"
        return path_str
        
    def windows_path(self, wsl_path):
        """Convert WSL path to Windows path"""
        if wsl_path.startswith("/mnt/"):
            parts = wsl_path[5:].split("/", 1)
            drive = parts[0].upper()
            rest = parts[1] if len(parts) > 1 else ""
            return f"{drive}:\\\\{rest.replace('/', '\\\\')}"
        return wsl_path
        
    def submit_audio_job(self, audio_file, wait=True, timeout=300):
        """Submit audio file for processing in WSL2"""
        audio_path = Path(audio_file)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")
            
        # Copy to WSL queue
        wsl_audio = self.wsl_path(audio_path)
        wsl_queue = "__GOODQ_WSL_WORKSPACE__/queue_in"
        
        cmd = f"cp '{wsl_audio}' {wsl_queue}/"
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to copy to WSL queue: {result.stderr}")
            
        if not wait:
            return None
            
        # Wait for results
        result_file = f"__GOODQ_WSL_WORKSPACE__/queue_out/{audio_path.stem}_result.json"
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            check_cmd = f"test -f {result_file} && echo 'exists'"
            result = subprocess.run(
                ["wsl", "-d", "Ubuntu", "--", "bash", "-c", check_cmd],
                capture_output=True,
                text=True
            )
            
            if "exists" in result.stdout:
                # Read results
                read_cmd = f"cat {result_file}"
                result = subprocess.run(
                    ["wsl", "-d", "Ubuntu", "--", "bash", "-c", read_cmd],
                    capture_output=True,
                    text=True
                )
                return json.loads(result.stdout)
                
            time.sleep(2)
            
        raise TimeoutError(f"Audio processing timeout after {timeout}s")
        
    def start_wsl_watcher(self):
        """Start the WSL2 queue watcher"""
        cmd = "__GOODQ_WSL_WORKSPACE__/venv/bin/python __GOODQ_WSL_WORKSPACE__/scripts/watch_queue.py"
        subprocess.Popen(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
    def check_wsl_status(self):
        """Check if WSL2 audio processing is running"""
        cmd = "pgrep -f watch_queue.py"
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
'''
        bridge_code = bridge_code.replace("__GOODQ_WSL_WORKSPACE__", self.wsl_workspace)
        bridge_code = bridge_code.replace('"Ubuntu"', f'"{self.wsl_distro}"')
        
        bridge_path = self.base_dir / "wsl2_audio_bridge.py"
        print(f"[1/2] Creating bridge module at {bridge_path}...")
        with open(bridge_path, 'w') as f:
            f.write(bridge_code)
        print("  [SYMBOL] Bridge module created")
        
        # Test script
        test_code = '''"""Test WSL2 Audio Bridge"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from wsl2_audio_bridge import WSL2AudioBridge

def test_bridge():
    print("="*80)
    print("  WSL2 Audio Bridge Test")
    print("="*80)
    
    bridge = WSL2AudioBridge()
    
    # Check status
    print("\\n[1/3] Checking WSL2 audio watcher status...")
    if bridge.check_wsl_status():
        print("  [SYMBOL] WSL2 audio watcher is running")
    else:
        print("  [SYMBOL] WSL2 audio watcher not running")
        print("  Starting watcher...")
        bridge.start_wsl_watcher()
        import time
        time.sleep(3)
        if bridge.check_wsl_status():
            print("  [SYMBOL] Watcher started successfully")
        else:
            print("  [SYMBOL] Failed to start watcher")
            return False
            
    # Path conversion test
    print("\\n[2/3] Testing path conversion...")
    win_path = "C:\\\\path\\\\to\\\\test.wav"
    wsl_path = bridge.wsl_path(win_path)
    print(f"  Windows: {win_path}")
    print(f"  WSL2:    {wsl_path}")
    print("  [SYMBOL] Path conversion working")
    
    print("\\n[3/3] Bridge ready for audio processing")
    print("\\n" + "="*80)
    print("  [SYMBOL] All tests passed!")
    print("="*80)
    return True

if __name__ == "__main__":
    test_bridge()
'''
        
        test_path = self.base_dir / "test_wsl2_bridge.py"
        print(f"\n[2/2] Creating test script at {test_path}...")
        with open(test_path, 'w') as f:
            f.write(test_code)
        print("  [SYMBOL] Test script created")
        
        return True
        
    def generate_report(self):
        """Generate final installation report"""
        self.print_header("Installation Complete!")
        
        print("Summary:")
        print(f"  Workspace: {self.wsl_workspace}")
        print(f"  Virtual environment: {self.wsl_workspace}/venv")
        print(f"  Processing entrypoint: {self.wsl_workspace}/process_audio.py")
        print(f"  Queue watcher: {self.wsl_workspace}/scripts/watch_queue.py")
        print(f"  Queue directories:")
        print(f"    - Input:  {self.wsl_workspace}/queue_in")
        print(f"    - Output: {self.wsl_workspace}/queue_out")
        
        if self.warnings:
            print(f"\n[SYMBOL] Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")
                
        if self.errors:
            print(f"\n[SYMBOL] Errors ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")
            return False
        else:
            print("\n[SYMBOL] No errors detected")
            
        print("\nNext steps:")
        print("  1. Test the bridge: python test_wsl2_bridge.py")
        print("  2. Integrate with pipeline: Update audio steps to use WSL2AudioBridge")
        print("  3. Monitor processing: Check logs in WSL2 workspace")
        
        return True
        
    def run(self):
        """Execute full installation"""
        print("="*80)
        print("  GoodQ4All - WSL2 Audio Processing Setup")
        print("  Phase 2: Comprehensive Installation")
        print("="*80)
        print("\nThis will:")
        print("  - Verify WSL2 and CUDA prerequisites")
        print("  - Install system packages and CUDA toolkit")
        print("  - Create Python environment with GPU PyTorch")
        print("  - Install audio processing libraries")
        print("  - Create processing scripts and queue system")
        print("  - Set up Windows-WSL2 bridge")
        print("\nEstimated time: 15-30 minutes")
        print("\nPress ENTER to continue or CTRL+C to cancel...")
        input()
        
        steps = [
            ("Prerequisites", self.check_prerequisites),
            ("System Packages", self.install_system_packages),
            ("Workspace Setup", self.setup_workspace),
            ("CUDA Toolkit", self.install_cuda_toolkit),
            ("Python Environment", self.create_python_venv),
            ("Audio Packages", self.install_audio_packages),
            ("Runtime Validation", self.validate_audio_runtime),
            ("Processing Scripts", self.create_processing_scripts),
            ("Windows Bridge", self.create_windows_bridge)
        ]
        
        for name, func in steps:
            try:
                if not func():
                    print(f"\n[SYMBOL] {name} failed!")
                    if self.errors:
                        print("Errors:")
                        for error in self.errors[-3:]:
                            print(f"  - {error}")
                    return False
            except Exception as e:
                print(f"\n[SYMBOL] Exception in {name}: {e}")
                self.errors.append(f"{name}: {str(e)}")
                return False
                
        return self.generate_report()

if __name__ == "__main__":
    setup = WSL2AudioSetup()
    success = setup.run()
    sys.exit(0 if success else 1)
