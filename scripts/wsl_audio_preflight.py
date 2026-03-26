from __future__ import annotations

import subprocess
from typing import Any, Dict, Optional


_RECOMMENDED_INSTALL_COMMAND = (
    "pip install torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 "
    "--index-url https://download.pytorch.org/whl/cu128"
)


def _run_wsl_probe(distro: str, script: str, *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["wsl", "-d", distro, "--", "bash", "-lc", script],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _probe_package_version(distro: str, workspace: str, package_name: str) -> Optional[str]:
    script = (
        f"source '{workspace}/setup_cuda_env.sh' >/dev/null 2>&1 && "
        f"python3 -c \"import importlib.metadata as md; print(md.version('{package_name}'))\""
    )
    try:
        completed = _run_wsl_probe(distro, script, timeout=10)
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    version_text = (completed.stdout or "").strip()
    return version_text or None


def probe_wsl_audio_runtime(distro: str, workspace: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "distro": str(distro or "").strip() or "Ubuntu",
        "workspace": str(workspace or "").strip().rstrip("/"),
        "workspace_ready": False,
        "runtime_ready": False,
        "abi_ready": False,
        "ready": False,
        "detail": "unresolved",
        "detected_versions": {},
        "recommended_install_command": _RECOMMENDED_INSTALL_COMMAND,
    }
    workspace = result["workspace"]
    distro = result["distro"]

    workspace_script = (
        f"test -f '{workspace}/setup_cuda_env.sh' && "
        f"test -f '{workspace}/process_audio.py' && "
        f"(test -x '{workspace}/venv/bin/python' || test -x '{workspace}/env/bin/python')"
    )
    try:
        workspace_probe = _run_wsl_probe(distro, workspace_script, timeout=10)
    except FileNotFoundError:
        result["detail"] = "wsl unavailable"
        return result
    except Exception as exc:
        result["detail"] = f"workspace probe failed: {exc}"
        return result

    if workspace_probe.returncode != 0:
        result["detail"] = (workspace_probe.stderr or workspace_probe.stdout).strip() or "workspace missing required files"
        return result

    result["workspace_ready"] = True

    runtime_script = (
        f"source '{workspace}/setup_cuda_env.sh' >/dev/null 2>&1 && "
        "python3 -c \"import faster_whisper, torch; print('runtime_ready')\""
    )
    try:
        runtime_probe = _run_wsl_probe(distro, runtime_script, timeout=15)
    except Exception as exc:
        result["detail"] = f"runtime probe failed: {exc}"
        return result

    if runtime_probe.returncode != 0:
        result["detail"] = (runtime_probe.stderr or runtime_probe.stdout).strip() or "python runtime probe failed"
        return result

    result["runtime_ready"] = True

    abi_script = (
        f"source '{workspace}/setup_cuda_env.sh' >/dev/null 2>&1 && "
        "python3 -c \"import torch, torchvision; from torchvision.ops import nms; print('abi_ready')\""
    )
    try:
        abi_probe = _run_wsl_probe(distro, abi_script, timeout=15)
    except Exception as exc:
        result["ready"] = True
        result["detail"] = f"transcription runtime ready; ABI probe failed: {exc}"
        return result

    if abi_probe.returncode == 0:
        result["abi_ready"] = True
        result["ready"] = True
        result["detail"] = "workspace, transcription runtime, and ABI checks are ready"
        return result

    result["ready"] = True
    result["abi_probe_stderr_tail"] = ((abi_probe.stderr or abi_probe.stdout or "").strip())[-600:]
    result["detected_versions"] = {
        "torch": _probe_package_version(distro, workspace, "torch"),
        "torchvision": _probe_package_version(distro, workspace, "torchvision"),
        "torchaudio": _probe_package_version(distro, workspace, "torchaudio"),
    }
    result["detail"] = "transcription runtime ready; torchvision ABI unavailable (diarization may be degraded)"
    return result
