import platform
import subprocess
import shutil
import json
import socket
from datetime import datetime
from pathlib import Path

OUTPUT_PATH = Path("docs/SYSTEM_SNAPSHOT.md")

def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except Exception:
        return "unavailable"

def check_port(host, port, timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return "reachable"
    except Exception:
        return "not reachable"

def main():
    lines = []
    now = datetime.now().isoformat(timespec="seconds")

    lines.append("# System Snapshot")
    lines.append("")
    lines.append(f"_Generated: {now}_")
    lines.append("")
    lines.append("## Host & OS")
    lines.append(f"- Hostname: {platform.node()}")
    lines.append(f"- OS: {platform.system()} {platform.release()} ({platform.version()})")
    lines.append(f"- Architecture: {platform.machine()}")
    lines.append(f"- Timezone: {run('tzutil /g') if platform.system() == 'Windows' else run('date +%Z')}")
    lines.append("")

    lines.append("## CPU / Memory")
    lines.append(f"- CPU: {platform.processor() or 'unavailable'}")
    if platform.system() == "Windows":
    	ram = run('powershell -command "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"')
    	lines.append(f"- RAM: {ram}")
    else:
    	lines.append("- RAM: unavailable")
    lines.append("")

    lines.append("## GPU")
    lines.append(f"- GPU(s): {run('nvidia-smi --query-gpu=name --format=csv,noheader')}")
    lines.append(f"- CUDA: {run('nvidia-smi --query-gpu=driver_version --format=csv,noheader')}")
    lines.append("")

    lines.append("## Storage (Top-Level)")
    for drive in ["C:", "L:"]:
        if Path(drive).exists():
            total, used, free = shutil.disk_usage(drive)
            lines.append(f"- {drive} total={total//(1024**3)}GB free={free//(1024**3)}GB")
    lines.append("")

    lines.append("## Toolchain")
    lines.append(f"- Python: {run('python --version')}")
    lines.append(f"- Conda: {run('conda --version')}")
    lines.append(f"- Git: {run('git --version')}")
    lines.append(f"- Node: {run('node --version')}")
    lines.append(f"- Codex CLI: {run('codex --version')}")
    lines.append("")

    lines.append("## WSL")
    lines.append(f"- WSL enabled: {run('wsl --status')}")
    lines.append(f"- Distros: {run('wsl -l -v')}")
    lines.append("")

    lines.append("## Local Services (Presence Check)")
    lines.append(f"- Qdrant (6333): {check_port('localhost', 6333)}")
    lines.append(f"- Ollama (11434): {check_port('localhost', 11434)}")
    lines.append(f"- LM Studio (1234): {check_port('localhost', 1234)}")
    lines.append("")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] Wrote {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
