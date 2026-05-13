from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


_RECOMMENDED_INSTALL_COMMAND = (
    "pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 "
    "--index-url https://download.pytorch.org/whl/cu121"
)
WSL_DIARIZATION_MODEL_REPOS = (
    "pyannote/speaker-diarization-3.1",
    "pyannote/segmentation-3.0",
    "pyannote/wespeaker-voxceleb-resnet34-LM",
)
_DIARIZATION_REPOS = WSL_DIARIZATION_MODEL_REPOS
WSL_AUDIO_REQUIRED_CACHE_REPOS = (
    "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition",
    "facebook/wav2vec2-base-960h",
    *WSL_DIARIZATION_MODEL_REPOS,
)


def _load_pinned_model_revisions() -> Dict[str, str]:
    registry_path = Path(__file__).resolve().parents[1] / "configs" / "model_registry.yaml"
    if not registry_path.exists():
        return {}
    try:
        import yaml  # type: ignore
    except Exception:
        return {}
    try:
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    models = registry.get("huggingface_models") if isinstance(registry, dict) else {}
    if not isinstance(models, dict):
        return {}
    revisions: Dict[str, str] = {}
    for model_info in models.values():
        if not isinstance(model_info, dict):
            continue
        repo_id = str(model_info.get("repo_id") or "").strip()
        revision = str(model_info.get("revision") or "").strip()
        if repo_id and revision:
            revisions[repo_id] = revision
    return revisions


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


def _python_path_literal(path_value: str) -> str:
    return path_value.replace("\\", "\\\\").replace("'", "\\'")


def _build_diarization_probe_script(workspace: str) -> str:
    repo_list = ", ".join(repr(repo) for repo in WSL_AUDIO_REQUIRED_CACHE_REPOS)
    pinned_revisions = {
        repo_id: revision
        for repo_id, revision in _load_pinned_model_revisions().items()
        if repo_id in WSL_AUDIO_REQUIRED_CACHE_REPOS
    }
    revision_map = json.dumps(pinned_revisions, sort_keys=True)
    return (
        f"source '{workspace}/setup_cuda_env.sh' >/dev/null 2>&1 && "
        "python3 - <<'PY'\n"
        "import os\n"
        "from huggingface_hub import snapshot_download\n"
        "token = os.getenv('PYANNOTE_TOKEN') or os.getenv('HUGGINGFACE_TOKEN') or os.getenv('HF_TOKEN')\n"
        "cache_dir = os.getenv('HUGGINGFACE_HUB_CACHE') or os.getenv('HF_HUB_CACHE') or None\n"
        "if not token:\n"
        "    print('diarization_token_missing')\n"
        "    raise SystemExit(0)\n"
        f"required_repos = [{repo_list}]\n"
        f"pinned_revisions = {revision_map}\n"
        "missing = []\n"
        "for repo_id in required_repos:\n"
        "    try:\n"
        "        kwargs = {'repo_id': repo_id, 'local_files_only': True}\n"
        "        if pinned_revisions.get(repo_id):\n"
        "            kwargs['revision'] = pinned_revisions[repo_id]\n"
        "        snapshot_download(**kwargs)\n"
        "    except Exception as exc:\n"
        "        missing.append(f'{repo_id}: {type(exc).__name__}: {exc}')\n"
        "if missing:\n"
        "    print('diarization_cache_missing')\n"
        "    print(' || '.join(missing))\n"
        "    raise SystemExit(0)\n"
        "try:\n"
        "    from pyannote.audio import Pipeline\n"
        "    try:\n"
        "        Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', use_auth_token=token, cache_dir=cache_dir)\n"
        "    except TypeError as auth_exc:\n"
        "        auth_message = str(auth_exc)\n"
        "        if 'use_auth_token' not in auth_message or 'unexpected keyword' not in auth_message:\n"
        "            raise\n"
        "        Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', token=token, cache_dir=cache_dir)\n"
        "except Exception as exc:\n"
        "    print('diarization_runtime_unavailable')\n"
        "    print(f'{type(exc).__name__}: {exc}')\n"
        "else:\n"
        "    print('diarization_ready')\n"
        "PY"
    )


def _build_wav2vec_enrichment_probe_script(workspace: str) -> str:
    return (
        f"source '{workspace}/setup_cuda_env.sh' >/dev/null 2>&1 && "
        "python3 - <<'PY'\n"
        "import os\n"
        "try:\n"
        "    from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForSequenceClassification, Wav2Vec2Model\n"
        "    cache_dir = os.getenv('HUGGINGFACE_HUB_CACHE') or os.getenv('HF_HUB_CACHE') or None\n"
        "    Wav2Vec2ForSequenceClassification.from_pretrained(\n"
        "        'ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition',\n"
        "        cache_dir=cache_dir,\n"
        "        local_files_only=True,\n"
        "    )\n"
        "    Wav2Vec2FeatureExtractor.from_pretrained(\n"
        "        'ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition',\n"
        "        cache_dir=cache_dir,\n"
        "        local_files_only=True,\n"
        "    )\n"
        "    Wav2Vec2Model.from_pretrained(\n"
        "        'facebook/wav2vec2-base-960h',\n"
        "        cache_dir=cache_dir,\n"
        "        local_files_only=True,\n"
        "    )\n"
        "    Wav2Vec2FeatureExtractor.from_pretrained(\n"
        "        'facebook/wav2vec2-base-960h',\n"
        "        cache_dir=cache_dir,\n"
        "        local_files_only=True,\n"
        "    )\n"
        "except Exception as exc:\n"
        "    print('wav2vec_enrichment_unavailable')\n"
        "    print(f'{type(exc).__name__}: {exc}')\n"
        "else:\n"
        "    print('wav2vec_enrichment_ready')\n"
        "PY"
    )


def probe_wsl_audio_runtime(distro: str, workspace: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "distro": str(distro or "").strip() or "Ubuntu",
        "workspace": str(workspace or "").strip().rstrip("/"),
        "workspace_ready": False,
        "gpu_ready": False,
        "transcription_ready": False,
        "process_import_ready": False,
        "diarization_ready": False,
        "wav2vec_enrichment_ready": False,
        "runtime_ready": False,
        "abi_ready": False,
        "ready": False,
        "detail": "unresolved",
        "detected_versions": {},
        "runtime_warnings": [],
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

    transcription_script = (
        f"source '{workspace}/setup_cuda_env.sh' >/dev/null 2>&1 && "
        "python3 -c \"import faster_whisper, torch; "
        "print('transcription_ready'); "
        "print('gpu_ready' if torch.cuda.is_available() else 'gpu_unavailable')\""
    )
    try:
        transcription_probe = _run_wsl_probe(distro, transcription_script, timeout=15)
    except Exception as exc:
        result["detail"] = f"runtime probe failed: {exc}"
        return result

    if transcription_probe.returncode != 0:
        result["detail"] = (
            (transcription_probe.stderr or transcription_probe.stdout).strip()
            or "python transcription probe failed"
        )
        return result

    transcription_stdout = (transcription_probe.stdout or "").strip()
    result["transcription_ready"] = "transcription_ready" in transcription_stdout
    result["gpu_ready"] = "gpu_ready" in transcription_stdout
    if not result["transcription_ready"]:
        result["detail"] = "python transcription probe did not report ready"
        return result

    process_audio_path = _python_path_literal(f"{workspace}/process_audio.py")
    process_import_script = (
        f"source '{workspace}/setup_cuda_env.sh' >/dev/null 2>&1 && "
        "python3 -c \"import importlib.util as iu; "
        f"spec = iu.spec_from_file_location('goodq_process_audio', '{process_audio_path}'); "
        "module = iu.module_from_spec(spec); "
        "spec.loader.exec_module(module); "
        "print('process_import_ready')\""
    )
    try:
        process_import_probe = _run_wsl_probe(distro, process_import_script, timeout=20)
    except Exception as exc:
        result["detail"] = f"process_audio import probe failed: {exc}"
        return result

    if process_import_probe.returncode != 0:
        result["detail"] = (
            (process_import_probe.stderr or process_import_probe.stdout).strip()
            or "process_audio import probe failed"
        )
        return result

    if "process_import_ready" not in (process_import_probe.stdout or ""):
        result["detail"] = "process_audio import probe did not report ready"
        return result

    result["process_import_ready"] = True
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
    else:
        result["abi_probe_stderr_tail"] = ((abi_probe.stderr or abi_probe.stdout or "").strip())[-600:]

    diarization_script = _build_diarization_probe_script(workspace)
    try:
        diarization_probe = _run_wsl_probe(distro, diarization_script, timeout=20)
    except Exception as exc:
        diarization_probe = None
        result["diarization_probe_stderr_tail"] = f"{type(exc).__name__}: {exc}"

    if diarization_probe is not None and diarization_probe.returncode == 0:
        diarization_stdout = (diarization_probe.stdout or "").strip()
        result["diarization_ready"] = "diarization_ready" in diarization_stdout
        if not result["diarization_ready"]:
            diarization_lines = [line.strip() for line in diarization_stdout.splitlines() if line.strip()]
            diarization_state = diarization_lines[0] if diarization_lines else ""
            diarization_message = diarization_lines[1] if len(diarization_lines) > 1 else ""
            if diarization_state == "diarization_token_missing":
                result["diarization_detail"] = "pyannote importable but no HuggingFace token available"
            elif diarization_state == "diarization_cache_missing":
                result["diarization_detail"] = diarization_message or "configured offline diarization cache is incomplete"
            elif diarization_state == "diarization_runtime_unavailable":
                result["diarization_detail"] = diarization_message or "pyannote runtime unavailable"
            else:
                result["diarization_detail"] = diarization_message or "diarization probe did not report ready"
    else:
        if diarization_probe is not None:
            result["diarization_probe_stderr_tail"] = (
                (diarization_probe.stderr or diarization_probe.stdout or "").strip()
            )[-600:]
        result["diarization_detail"] = "pyannote runtime unavailable"

    wav2vec_script = _build_wav2vec_enrichment_probe_script(workspace)
    try:
        wav2vec_probe = _run_wsl_probe(distro, wav2vec_script, timeout=35)
    except Exception as exc:
        wav2vec_probe = None
        result["wav2vec_enrichment_detail"] = f"{type(exc).__name__}: {exc}"

    if wav2vec_probe is not None and wav2vec_probe.returncode == 0:
        wav2vec_stdout = (wav2vec_probe.stdout or "").strip()
        wav2vec_stderr = (wav2vec_probe.stderr or "").strip()
        if wav2vec_stderr:
            result["wav2vec_enrichment_probe_stderr_tail"] = wav2vec_stderr[-600:]
        result["wav2vec_enrichment_ready"] = "wav2vec_enrichment_ready" in wav2vec_stdout
        if not result["wav2vec_enrichment_ready"]:
            wav2vec_lines = [line.strip() for line in wav2vec_stdout.splitlines() if line.strip()]
            result["wav2vec_enrichment_detail"] = (
                wav2vec_lines[1]
                if len(wav2vec_lines) > 1
                else "Wav2Vec enrichment probe did not report ready"
            )
    else:
        if wav2vec_probe is not None:
            result["wav2vec_enrichment_probe_stderr_tail"] = (
                (wav2vec_probe.stderr or wav2vec_probe.stdout or "").strip()
            )[-600:]
        result["wav2vec_enrichment_detail"] = result.get(
            "wav2vec_enrichment_detail",
            "Wav2Vec enrichment runtime unavailable",
        )

    result["detected_versions"] = {
        "torch": _probe_package_version(distro, workspace, "torch"),
        "torchvision": _probe_package_version(distro, workspace, "torchvision"),
        "torchaudio": _probe_package_version(distro, workspace, "torchaudio"),
        "pyannote.audio": _probe_package_version(distro, workspace, "pyannote.audio"),
        "faster-whisper": _probe_package_version(distro, workspace, "faster-whisper"),
        "transformers": _probe_package_version(distro, workspace, "transformers"),
        "tokenizers": _probe_package_version(distro, workspace, "tokenizers"),
        "safetensors": _probe_package_version(distro, workspace, "safetensors"),
    }
    if not result["wav2vec_enrichment_ready"]:
        result["runtime_warnings"] = ["wav2vec_enrichment_unavailable"]

    result["ready"] = True
    if result["abi_ready"] and result["diarization_ready"]:
        result["detail"] = "workspace, transcription runtime, process import, ABI, and diarization checks are ready"
    elif result["abi_ready"]:
        result["detail"] = "transcription runtime ready; process_audio import ready; diarization unavailable"
    else:
        result["detail"] = "transcription runtime ready; process_audio import ready; torchvision ABI unavailable (diarization may be degraded)"
    return result
