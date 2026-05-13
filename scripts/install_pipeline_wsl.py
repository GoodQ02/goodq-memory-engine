"""
WSL pipeline installer/repair script.

Creates or fixes key conda environments, installs requirements, and pins
CUDA 12.1 PyTorch stacks where needed (matching the working GPU scene-detect
setup).

Usage (WSL):
  python scripts/install_pipeline_wsl.py

This script is idempotent and skips steps if files are missing.
"""

from __future__ import annotations

import os
import subprocess
from typing import Dict, List, Set
import tempfile
import time


CONDA_SH = os.path.expanduser("~/miniconda3/etc/profile.d/conda.sh")
AGENT_PREFIX = "[00Q]"


def run(cmd: str, timeout: int = 1200) -> subprocess.CompletedProcess:
    """Run a shell command and return the CompletedProcess."""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)


def run_conda(cmd: str, timeout: int = 1200) -> subprocess.CompletedProcess:
    """Run a conda command with an explicit hook."""
    if os.path.isfile(CONDA_SH):
        full = f"bash -lc 'source \"{CONDA_SH}\" && {cmd}'"
    else:
        full = cmd
    return run(full, timeout=timeout)


def run_in_env(env: str, cmd: str, timeout: int = 1200) -> subprocess.CompletedProcess:
    """Run a command inside a conda env using an explicit conda hook."""
    if os.path.isfile(CONDA_SH):
        full = f'bash -lc "source \\"{CONDA_SH}\\" && conda activate {env} && {cmd}"'
    else:
        full = f"conda activate {env} && {cmd}"
    return run(full, timeout=timeout)


def env_exists(env: str) -> bool:
    result = run_conda("conda env list")
    return result.returncode == 0 and any(f" {env}" in line or line.endswith(f"/{env}") for line in result.stdout.splitlines())


def ensure_env(env: str, py_version: str) -> None:
    if env_exists(env):
        print(f"[OK] Env present: {env}")
        return
    print(f"[SYMBOL]️  Creating env {env} (python={py_version})")
    result = run_conda(f"conda create -y -n {env} python={py_version}")
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create env {env}: {result.stderr.strip()}")


def install_requirements(env: str, req_path: str, skip_pkgs: Set[str] | None = None) -> None:
    if not os.path.isfile(req_path):
        print(f"[WARN]  Skip requirements (missing): {req_path}")
        return
    skip_pkgs = skip_pkgs or set()
    print(f"[SYMBOL]️  Installing requirements for {env} from {req_path}")

    # Filter out problematic pins (e.g., faiss* incompatible with py3.12) into a temp file
    with open(req_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    filtered: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            filtered.append(line)
            continue
        name = stripped.split("==")[0].split(">=")[0].split(" ")[0]
        if any(name.lower().startswith(pfx) for pfx in skip_pkgs):
            print(f"   [WARN]  Skipping pinned package in {env}: {stripped}")
            continue
        filtered.append(line)

    with tempfile.NamedTemporaryFile("w+", delete=False) as tmp:
        tmp.writelines(filtered)
        tmp_path = tmp.name

    try:
        # Avoid resolver conflicts with pinned torch/numpy; install sans deps.
        res = run_in_env(env, f"pip install --no-cache-dir --no-deps -r {tmp_path}")
        if res.returncode != 0:
            raise RuntimeError(f"Reqs failed for {env}: {res.stderr.strip()}")
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def install_torch(env: str) -> None:
    print(f"[SYMBOL]️  Installing CUDA 12.1 torch stack for {env}")
    cmds = [
        "pip uninstall -y torch torchvision torchaudio",
        (
            "pip install --no-cache-dir "
            "torch==2.3.1+cu121 torchvision==0.18.1+cu121 torchaudio==2.3.1 "
            "--extra-index-url https://download.pytorch.org/whl/cu121"
        ),
        # Align numpy/pillow with the working stack to avoid resolver conflicts
        "pip install --no-cache-dir numpy==2.2.6 pillow==12.0.0",
        (
            "python - <<'PY'\n"
            "import torch\n"
            "print('torch', torch.__version__, 'cuda?', torch.cuda.is_available())\n"
            "PY"
        ),
    ]
    for cmd in cmds:
        res = run_in_env(env, cmd)
        if res.returncode != 0:
            raise RuntimeError(f"Torch step failed for {env}: {res.stderr.strip()}")
    print(f"[OK] Torch stack OK for {env}")


ENV_CONFIG: List[Dict[str, str]] = [
    # Vision / video
    {"name": "goodq_video_scene_detect", "python": "3.12", "req": "envs/video_scene_detect/requirements.txt", "torch": "cu121"},
    {"name": "goodq_face_embed", "python": "3.12", "req": "envs/face_embed/requirements.txt", "torch": "cu121"},
    {"name": "goodq_image_caption", "python": "3.12", "req": "envs/image_caption/requirements.txt", "torch": "cu121"},
    {"name": "goodq_object_detect", "python": "3.12", "req": "envs/object_detect/requirements.txt", "torch": "cu121"},
    {"name": "goodq_object_track", "python": "3.12", "req": "envs/object_track_yolo/requirements.txt", "torch": "cu121"},

    # Audio
    {"name": "goodq_audio_diarize", "python": "3.12", "req": "envs/audio_diarize/requirements.txt", "torch": "cu121"},
    {"name": "goodq_audio_transcribe", "python": "3.12", "req": "envs/audio_transcribe/requirements.txt", "torch": "cu121"},
    {"name": "goodq_audio_emotion", "python": "3.12", "req": "envs/audio_emotion/requirements.txt", "torch": "cu121"},
    {"name": "goodq_audio_embed", "python": "3.12", "req": "envs/audio_embed/requirements.txt", "torch": "cu121"},
    {"name": "goodq_audio_metadata", "python": "3.12", "req": "envs/audio_metadata/requirements.txt", "torch": ""},

    # NLP / embeddings / tagging
    {"name": "goodq_text_embed", "python": "3.12", "req": "envs/text_embed/requirements.txt", "torch": "cu121"},
    {"name": "goodq_tagger", "python": "3.12", "req": "envs/tagger/requirements.txt", "torch": "cu121"},
    {"name": "goodq_sentiment", "python": "3.12", "req": "envs/sentiment/requirements.txt", "torch": "cu121"},
    {"name": "goodq_emotion_classify", "python": "3.12", "req": "envs/emotion_classify/requirements.txt", "torch": "cu121"},

    # Other pipeline pieces (no torch needed)
    {"name": "goodq_llm_chat", "python": "3.12", "req": "envs/llm_chat/requirements.txt", "torch": ""},
    {"name": "goodq_tts", "python": "3.12", "req": "envs/tts/requirements.txt", "torch": ""},
    {"name": "goodq_ocr", "python": "3.12", "req": "envs/ocr/requirements.txt", "torch": ""},
    {"name": "goodq_pdf_text", "python": "3.12", "req": "envs/pdf_text/requirements.txt", "torch": ""},
    {"name": "goodq_system_metrics", "python": "3.12", "req": "envs/system_metrics/requirements.txt", "torch": ""},
    {"name": "goodq_home_assistant_status", "python": "3.12", "req": "envs/home_assistant_status/requirements.txt", "torch": ""},
]

FAISS_ENV_NAMES = {
    "goodq_image_caption",
    "goodq_audio_embed",
    "goodq_text_embed",
}
TORCH_ENV_NAMES = {cfg["name"] for cfg in [
    {"name": "goodq_video_scene_detect"}, {"name": "goodq_face_embed"}, {"name": "goodq_image_caption"},
    {"name": "goodq_object_detect"}, {"name": "goodq_object_track"}, {"name": "goodq_audio_diarize"},
    {"name": "goodq_audio_transcribe"}, {"name": "goodq_audio_emotion"}, {"name": "goodq_audio_embed"},
    {"name": "goodq_text_embed"}, {"name": "goodq_tagger"}, {"name": "goodq_sentiment"},
    {"name": "goodq_emotion_classify"},
] }


def agent_log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"{AGENT_PREFIX} [{ts}] {msg}")


def smoke_test(env: str) -> None:
    tests = []
    if env in TORCH_ENV_NAMES:
        tests.append(
            "python - <<'PY'\n"
            "import torch\n"
            "print('torch', torch.__version__, 'cuda?', torch.cuda.is_available())\n"
            "PY"
        )
    if env in FAISS_ENV_NAMES:
        tests.append(
            "python - <<'PY'\n"
            "import faiss, numpy as np\n"
            "print('faiss', faiss.__version__, 'numpy', np.__version__)\n"
            "PY"
        )
    if not tests:
        return
    agent_log(f"Running smoke tests for {env}")
    for cmd in tests:
        res = run_in_env(env, cmd)
        if res.returncode != 0:
            raise RuntimeError(f"Smoke test failed for {env}: {res.stderr.strip()}")
    agent_log(f"Smoke tests passed for {env}")


def main() -> int:
    print("=== GoodQ4All WSL Pipeline Installer ===")
    for cfg in ENV_CONFIG:
        name = cfg["name"]
        py = cfg.get("python", "3.12")
        req = cfg.get("req", "")
        needs_torch = bool(cfg.get("torch"))

        try:
            agent_log(f"Ensuring env {name}")
            ensure_env(name, py)
            if req:
                skip = {"faiss"} if name in FAISS_ENV_NAMES else set()
                install_requirements(name, req, skip_pkgs=skip)
                # Install a compatible faiss for py3.12 (CPU build)
                if name in FAISS_ENV_NAMES:
                    res = run_in_env(name, "pip install --no-cache-dir faiss-cpu==1.9.0")
                    if res.returncode != 0:
                        raise RuntimeError(f"faiss install failed for {name}: {res.stderr.strip()}")
            if needs_torch:
                install_torch(name)
            smoke_test(name)
        except Exception as exc:  # noqa: BLE001
            agent_log(f"[FAIL] {name}: {exc}")
            continue
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
