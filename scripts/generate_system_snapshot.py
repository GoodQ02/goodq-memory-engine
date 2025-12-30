import platform
import subprocess
import shutil
import json
import socket
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

OUTPUT_PATH = Path("docs/SYSTEM_SNAPSHOT.md")

def run(cmd):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
    except Exception:
        return "unavailable"

def check_port(host, port, timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return "reachable"
    except Exception:
        return "not reachable"

def get_ollama_target():
    try:
        repo_root = Path(__file__).resolve().parents[1]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from steps.common.config_loader import load_configs
        cfg = load_configs({})
        ollama_url = (cfg.get("llm", {}) or {}).get("ollama_url")
        if not ollama_url:
            return None, None
        parsed = urlparse(str(ollama_url))
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return host, port
    except Exception:
        return None, None

def main():
    lines = []
    now = datetime.now().isoformat(timespec="seconds")

    try:
        from configs.python_paths import get_conda_exe
        conda_exe = get_conda_exe()
        conda_cmd = str(conda_exe) if conda_exe else "conda"
    except Exception:
        conda_cmd = "conda"

    lines.append("# System Snapshot")
    lines.append("")
    lines.append(f"_Generated: {now}_")
    lines.append("")
    lines.append("## Host & OS")
    lines.append(f"- Hostname: {platform.node()}")
    lines.append(f"- OS: {platform.system()} {platform.release()} ({platform.version()})")
    lines.append(f"- Architecture: {platform.machine()}")
    lines.append(f"- Timezone: {run(['tzutil', '/g']) if platform.system() == 'Windows' else run(['date', '+%Z'])}")
    lines.append("")

    lines.append("## CPU / Memory")
    lines.append(f"- CPU: {platform.processor() or 'unavailable'}")
    if platform.system() == "Windows":
        ram = run(['powershell', '-command', '(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory'])
        lines.append(f"- RAM: {ram}")
    else:
        lines.append("- RAM: unavailable")
    lines.append("")

    lines.append("## GPU")
    lines.append(f"- GPU(s): {run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'])}")
    lines.append(f"- CUDA: {run(['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader'])}")
    lines.append("")

    lines.append("## Storage (Top-Level)")
    for drive in ["C:", "L:"]:
        if Path(drive).exists():
            total, used, free = shutil.disk_usage(drive)
            lines.append(f"- {drive} total={total//(1024**3)}GB free={free//(1024**3)}GB")
    lines.append("")

    lines.append("## Toolchain")
    lines.append(f"- Python: {run([sys.executable, '--version'])}")
    lines.append(f"- Conda: {run([conda_cmd, '--version'])}")
    lines.append(f"- Git: {run(['git', '--version'])}")
    lines.append(f"- Node: {run(['node', '--version'])}")
    lines.append(f"- Codex CLI: {run(['codex', '--version'])}")
    lines.append("")

    lines.append("## WSL")
    lines.append(f"- WSL enabled: {run(['wsl', '--status'])}")
    lines.append(f"- Distros: {run(['wsl', '-l', '-v'])}")
    lines.append("")

    lines.append("## Local Services (Presence Check)")
    lines.append(f"- Qdrant (6333): {check_port('localhost', 6333)}")
    ollama_host, ollama_port = get_ollama_target()
    if ollama_port:
        lines.append(f"- Ollama ({ollama_port}): {check_port(ollama_host, ollama_port)}")
    else:
        lines.append("- Ollama (unknown): unavailable")
    lines.append(f"- LM Studio (1234): {check_port('localhost', 1234)}")        
    lines.append("")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] Wrote {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
