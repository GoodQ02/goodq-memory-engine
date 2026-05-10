from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


_EXPECTED_TORCH_LANE = {
    "torch": "2.5.1+cu121",
    "torchvision": "0.20.1+cu121",
    "torchaudio": "2.5.1+cu121",
}
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


def _tail(value: str, limit: int = 900) -> str:
    return str(value or "")[-limit:]


def _classify_torch_lane(package_versions: Dict[str, Optional[str]]) -> str:
    observed = {name: package_versions.get(name) for name in _EXPECTED_TORCH_LANE}
    if not all(observed.values()):
        return "unknown"
    if all(str(observed[name]) == expected for name, expected in _EXPECTED_TORCH_LANE.items()):
        return "matches_expected"
    return "differs_from_expected"


def _classify_torchcodec_error(message: str) -> list[str]:
    text = str(message or "").lower()
    families: list[str] = []
    if "libavutil.so" in text or "libavcodec.so" in text or "libavformat.so" in text:
        families.append("ffmpeg_shared_library_unavailable")
    if "undefined symbol" in text:
        families.append("torch_abi_symbol_mismatch")
    if "not compatible" in text and "torchcodec" in text:
        families.append("torchcodec_torch_version_mismatch")
    return families or ["torchcodec_unavailable"]


def _probe_wsl_audio_black_box(distro: str, workspace: str) -> Dict[str, Any]:
    """Return optional WSL audio runtime diagnostics without changing readiness."""

    script = (
        f"source '{workspace}/setup_cuda_env.sh' >/dev/null 2>&1 && "
        "python3 - <<'PY'\n"
        "import importlib.metadata as md\n"
        "import json\n"
        "import os\n"
        "import re\n"
        "import shutil\n"
        "import subprocess\n"
        "import sys\n"
        "import traceback\n"
        "\n"
        "packages = ['torch', 'torchvision', 'torchaudio', 'torchcodec', 'pyannote.audio', 'faster-whisper', 'transformers', 'tokenizers', 'safetensors']\n"
        "versions = {}\n"
        "for package in packages:\n"
        "    try:\n"
        "        versions[package] = md.version(package)\n"
        "    except Exception:\n"
        "        versions[package] = None\n"
        "\n"
        "payload = {\n"
        "    'source': 'wsl_audio_preflight',\n"
        "    'python_version': sys.version.split()[0],\n"
        "    'active_env_kind': os.path.basename(sys.prefix.rstrip('/')),\n"
        "    'package_versions': versions,\n"
        "}\n"
        "\n"
        "try:\n"
        "    import torch\n"
        "    payload['torch'] = {\n"
        "        'version': getattr(torch, '__version__', None),\n"
        "        'cuda_compiled': getattr(torch.version, 'cuda', None),\n"
        "        'cuda_available': bool(torch.cuda.is_available()),\n"
        "        'cuda_device_count': int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,\n"
        "        'cuda_device_name': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,\n"
        "    }\n"
        "except Exception as exc:\n"
        "    payload['torch'] = {'error_type': type(exc).__name__, 'error_tail': str(exc)[-500:]}\n"
        "\n"
        "try:\n"
        "    import torchvision\n"
        "    from torchvision.ops import nms\n"
        "    payload['torchvision_abi'] = {'ready': True}\n"
        "except Exception as exc:\n"
        "    payload['torchvision_abi'] = {\n"
        "        'ready': False,\n"
        "        'error_type': type(exc).__name__,\n"
        "        'error_tail': str(exc)[-700:],\n"
        "    }\n"
        "\n"
        "try:\n"
        "    import torchaudio\n"
        "    payload['torchaudio'] = {'import_ready': True}\n"
        "except Exception as exc:\n"
        "    payload['torchaudio'] = {\n"
        "        'import_ready': False,\n"
        "        'error_type': type(exc).__name__,\n"
        "        'error_tail': str(exc)[-700:],\n"
        "    }\n"
        "\n"
        "try:\n"
        "    import torchcodec\n"
        "    payload['torchcodec'] = {'ready': True}\n"
        "except Exception as exc:\n"
        "    error_text = str(exc) + '\\n' + traceback.format_exc()\n"
        "    payload['torchcodec'] = {\n"
        "        'ready': False,\n"
        "        'error_type': type(exc).__name__,\n"
        "        'error_tail': error_text[-1200:],\n"
        "    }\n"
        "\n"
        "ffmpeg = {'available': False}\n"
        "ffmpeg_path = shutil.which('ffmpeg')\n"
        "if ffmpeg_path:\n"
        "    ffmpeg['available'] = True\n"
        "    try:\n"
        "        proc = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=10)\n"
        "        ffmpeg['returncode'] = proc.returncode\n"
        "        lines = (proc.stdout or proc.stderr or '').splitlines()\n"
        "        ffmpeg['version_first_line'] = lines[0] if lines else ''\n"
        "    except Exception as exc:\n"
        "        ffmpeg['error_type'] = type(exc).__name__\n"
        "        ffmpeg['error_tail'] = str(exc)[-500:]\n"
        "payload['ffmpeg'] = ffmpeg\n"
        "\n"
        "try:\n"
        "    proc = subprocess.run(\n"
        "        ['bash', '-lc', \"ldconfig -p | grep -E 'libav(util|codec|format)'\"],\n"
        "        capture_output=True,\n"
        "        text=True,\n"
        "        timeout=10,\n"
        "    )\n"
        "    libraries = sorted(set(re.findall(r'(libav(?:util|codec|format)\\\\.so\\\\.[0-9]+)', proc.stdout or '')))\n"
        "    payload['ffmpeg_libraries'] = {\n"
        "        'returncode': proc.returncode,\n"
        "        'libraries': libraries[:30],\n"
        "        'stderr_tail': (proc.stderr or '')[-300:],\n"
        "    }\n"
        "except Exception as exc:\n"
        "    payload['ffmpeg_libraries'] = {'error_type': type(exc).__name__, 'error_tail': str(exc)[-500:]}\n"
        "\n"
        "print(json.dumps(payload, sort_keys=True))\n"
        "PY"
    )
    try:
        completed = _run_wsl_probe(distro, script, timeout=35)
    except Exception as exc:
        return {
            "source": "wsl_audio_preflight",
            "probe_error_type": type(exc).__name__,
            "probe_error_tail": _tail(str(exc)),
        }
    if completed.returncode != 0:
        return {
            "source": "wsl_audio_preflight",
            "probe_returncode": completed.returncode,
            "probe_stderr_tail": _tail(completed.stderr),
            "probe_stdout_tail": _tail(completed.stdout),
        }
    try:
        payload = json.loads((completed.stdout or "").strip())
    except json.JSONDecodeError:
        return {
            "source": "wsl_audio_preflight",
            "probe_returncode": completed.returncode,
            "probe_json_error": "invalid_json",
            "probe_stdout_tail": _tail(completed.stdout),
            "probe_stderr_tail": _tail(completed.stderr),
        }
    if not isinstance(payload, dict):
        return {"source": "wsl_audio_preflight", "probe_json_error": "non_object_json"}
    return payload


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
        "if cache_dir:\n"
        "    os.environ.setdefault('HF_HUB_CACHE', cache_dir)\n"
        "    os.environ.setdefault('PYANNOTE_CACHE', cache_dir)\n"
        "if not token:\n"
        "    print('diarization_token_missing')\n"
        "    raise SystemExit(0)\n"
        f"required_repos = [{repo_list}]\n"
        f"pinned_revisions = {revision_map}\n"
        "missing = []\n"
        "for repo_id in required_repos:\n"
        "    try:\n"
        "        kwargs = {'repo_id': repo_id, 'local_files_only': True}\n"
        "        if cache_dir:\n"
        "            kwargs['cache_dir'] = cache_dir\n"
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
        "expected_torch_lane": dict(_EXPECTED_TORCH_LANE),
        "runtime_black_box": {},
        "runtime_warnings": [],
        "torch_lane_status": "unknown",
        "torchcodec_ready": None,
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
        diarization_stderr = (diarization_probe.stderr or "").strip()
        if diarization_stderr:
            result["diarization_probe_stderr_tail"] = diarization_stderr[-600:]
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

    black_box = _probe_wsl_audio_black_box(distro, workspace)
    result["runtime_black_box"] = black_box
    package_versions = black_box.get("package_versions") if isinstance(black_box, dict) else None
    if isinstance(package_versions, dict):
        result["detected_versions"] = {
            "torch": package_versions.get("torch"),
            "torchvision": package_versions.get("torchvision"),
            "torchaudio": package_versions.get("torchaudio"),
            "pyannote.audio": package_versions.get("pyannote.audio"),
            "faster-whisper": package_versions.get("faster-whisper"),
            "transformers": package_versions.get("transformers"),
            "tokenizers": package_versions.get("tokenizers"),
            "safetensors": package_versions.get("safetensors"),
        }
    else:
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
    if isinstance(package_versions, dict):
        result["torch_lane_status"] = _classify_torch_lane(package_versions)
    else:
        result["torch_lane_status"] = _classify_torch_lane(result["detected_versions"])
    runtime_warnings: list[str] = []
    if result["torch_lane_status"] == "differs_from_expected":
        runtime_warnings.append("torch_lane_differs_from_expected")
    torchcodec = black_box.get("torchcodec") if isinstance(black_box, dict) else None
    if isinstance(torchcodec, dict):
        result["torchcodec_ready"] = bool(torchcodec.get("ready"))
        if not result["torchcodec_ready"]:
            error_tail = str(torchcodec.get("error_tail") or "")
            families = _classify_torchcodec_error(error_tail)
            torchcodec["error_families"] = families
            result["torchcodec_detail"] = ", ".join(families)
            runtime_warnings.append("torchcodec_decoder_unavailable")
    pyannote_import = black_box.get("pyannote_import") if isinstance(black_box, dict) else None
    pyannote_warning_text = str(result.get("diarization_probe_stderr_tail") or "")
    if isinstance(pyannote_import, dict):
        pyannote_warning_text += "\n" + str(pyannote_import.get("warning_tail") or "")
    if "torchcodec" in pyannote_warning_text.lower():
        runtime_warnings.append("pyannote_warned_torchcodec_decoder_unavailable")
    if not result["wav2vec_enrichment_ready"]:
        runtime_warnings.append("wav2vec_enrichment_unavailable")
    result["runtime_warnings"] = sorted(set(runtime_warnings))

    result["ready"] = True
    if result["abi_ready"] and result["diarization_ready"]:
        result["detail"] = "workspace, transcription runtime, process import, ABI, and diarization checks are ready"
    elif result["abi_ready"]:
        result["detail"] = "transcription runtime ready; process_audio import ready; diarization unavailable"
    else:
        result["detail"] = "transcription runtime ready; process_audio import ready; torchvision ABI unavailable (diarization may be degraded)"
    return result


def _default_wsl_workspace() -> str:
    explicit = str(os.environ.get("GOODQ_WSL_WORKSPACE") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    wsl_user = str(os.environ.get("GOODQ_WSL_USER") or os.environ.get("USERNAME") or "goodq").strip()
    return f"/home/{wsl_user}/goodq_audio"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect the WSL audio runtime without mutating it.")
    parser.add_argument(
        "--distro",
        default=str(os.environ.get("GOODQ_WSL_DISTRO") or "Ubuntu").strip() or "Ubuntu",
        help="WSL distro to inspect. Defaults to GOODQ_WSL_DISTRO or Ubuntu.",
    )
    parser.add_argument(
        "--workspace",
        default=_default_wsl_workspace(),
        help="WSL audio workspace. Defaults to GOODQ_WSL_WORKSPACE or /home/<user>/goodq_audio.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Emit compact JSON on one line.",
    )
    args = parser.parse_args(argv)

    result = probe_wsl_audio_runtime(args.distro, args.workspace)
    if args.compact:
        print(json.dumps(result, sort_keys=True))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if bool(result.get("ready")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
