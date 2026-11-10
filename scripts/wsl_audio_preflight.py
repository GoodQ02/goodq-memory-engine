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
    "MIT/ast-finetuned-audioset-10-10-0.4593",
    "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition",
    "facebook/wav2vec2-base-960h",
    *WSL_DIARIZATION_MODEL_REPOS,
)


def _env_timeout_seconds(name: str, default: int) -> int:
    raw_value = os.environ.get(name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return max(1, value)


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


def _classify_torch_lane(package_versions: Dict[str, Optional[str]], expected=None) -> str:
    expected = _EXPECTED_TORCH_LANE if expected is None else expected
    observed = {name: package_versions.get(name) for name in expected}
    if not all(observed.values()):
        return "unknown"
    if all(str(observed[name]) == version for name, version in expected.items()):
        return "matches_expected"
    return "differs_from_expected"


def _check_runtime_manifest(black_box: dict) -> dict:
    """An optional workspace manifest declares an isolated, exactly pinned lane."""
    envelope = black_box.get('runtime_manifest')
    if envelope is None:
        return {'status': 'not_declared'}
    if not isinstance(envelope, dict) or envelope.get('error'):
        return {'status': 'invalid', 'reason': 'runtime_manifest_unreadable'}
    manifest = envelope.get('manifest')
    if not isinstance(manifest, dict) or manifest.get('schema_version') != 1:
        return {'status': 'invalid', 'reason': 'runtime_manifest_schema_invalid'}
    expected = manifest.get('expected_packages')
    expected_files = manifest.get('expected_files', {})
    if (not isinstance(expected, dict) or not all(name in expected for name in _EXPECTED_TORCH_LANE)
            or not all(isinstance(k, str) and isinstance(v, str) and k and v for k, v in expected.items())
            or not isinstance(manifest.get('python_version'), str)
            or not isinstance(manifest.get('torch_cuda'), str)
            or not isinstance(manifest.get('requires_torchcodec'), bool)
            or not isinstance(expected_files, dict)
            or not all(isinstance(k, str) and k and isinstance(v, str)
                       and len(v) == 64 and all(c in '0123456789abcdef' for c in v)
                       for k, v in expected_files.items())):
        return {'status': 'invalid', 'reason': 'runtime_manifest_contract_invalid'}
    observed = black_box.get('package_versions') or {}
    mismatches = {name: {'expected': version, 'observed': observed.get(name)}
                  for name, version in expected.items() if observed.get(name) != version}
    for name, actual in [('python_version', black_box.get('python_version')),
                         ('torch_cuda', (black_box.get('torch') or {}).get('cuda_compiled'))]:
        if actual != manifest[name]:
            mismatches[name] = {'expected': manifest[name], 'observed': actual}
    observed_files = envelope.get('files') or {}
    for name, digest in expected_files.items():
        if observed_files.get(name) != digest:
            mismatches['file:' + name] = {'expected': digest, 'observed': observed_files.get(name)}
    return {'status': 'mismatch' if mismatches else 'matched',
            'candidate_id': manifest.get('candidate_id'), 'sha256': envelope.get('sha256'),
            'requirements_lock_sha256': manifest.get('requirements_lock_sha256'),
            'expected_torch_lane': {name: expected[name] for name in _EXPECTED_TORCH_LANE},
            'requires_torchcodec': manifest['requires_torchcodec'], 'mismatches': mismatches}


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
        "import hashlib\n"
        "from pathlib import Path\n"
        "\n"
        "packages = ['torch', 'torchvision', 'torchaudio', 'torchcodec', 'pyannote.audio', 'faster-whisper', 'transformers', 'tokenizers', 'safetensors']\n"
        f"manifest_path = Path({workspace!r}) / 'runtime_manifest.json'\n"
        "runtime_manifest = None\n"
        "if manifest_path.exists():\n"
        "    try:\n"
        "        raw = manifest_path.read_bytes()\n"
        "        manifest = json.loads(raw)\n"
        "        runtime_manifest = {'manifest': manifest, 'sha256': hashlib.sha256(raw).hexdigest()}\n"
        "        expected = manifest.get('expected_packages') if isinstance(manifest, dict) else None\n"
        "        if isinstance(expected, dict):\n"
        "            packages = sorted(set(packages) | set(expected))\n"
        "        runtime_manifest['files'] = {}\n"
        "        for name in manifest.get('expected_files', {}):\n"
        "            path = (manifest_path.parent / name).resolve()\n"
        "            if Path(name).is_absolute() or not path.is_relative_to(manifest_path.parent.resolve()):\n"
        "                raise ValueError('Manifest file outside workspace')\n"
        "            runtime_manifest['files'][name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None\n"
        "    except Exception as exc:\n"
        "        runtime_manifest = {'error': type(exc).__name__}\n"
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
        "    'runtime_manifest': runtime_manifest,\n"
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
        "    import math, struct, tempfile, wave\n"
        "    from faster_whisper.audio import decode_audio\n"
        "    with tempfile.TemporaryDirectory(prefix='goodq-decode-probe-') as directory:\n"
        "        path = os.path.join(directory, 'probe.wav')\n"
        "        samples = [int(8000 * math.sin(i * 0.17)) for i in range(320)]\n"
        "        with wave.open(path, 'wb') as audio:\n"
        "            audio.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))\n"
        "            audio.writeframes(struct.pack('<320h', *samples))\n"
        "        expected = torch.tensor(samples, dtype=torch.float32).reshape(1, -1) / 32768\n"
        "        for key, backend in [('audio_decode', 'torchaudio.load'), ('transcription_decode', 'faster_whisper.audio.decode_audio')]:\n"
        "            try:\n"
        "                if key == 'audio_decode':\n"
        "                    decoded, rate = torchaudio.load(path)\n"
        "                else:\n"
        "                    decoded = torch.from_numpy(decode_audio(path, sampling_rate=16000)).reshape(1, -1)\n"
        "                    rate = 16000\n"
        "                assert rate == 16000 and decoded.shape == expected.shape\n"
        "                assert torch.allclose(decoded, expected, atol=1e-6, rtol=0)\n"
        "                payload[key] = {'ready': True, 'backend': backend, 'sample_rate': rate, 'samples': 320}\n"
        "            except Exception as exc:\n"
        "                payload[key] = {'ready': False, 'backend': backend, 'error_type': type(exc).__name__, 'error_tail': str(exc)[-700:]}\n"
        "except Exception as exc:\n"
        "    for key in ('audio_decode', 'transcription_decode'):\n"
        "        payload[key] = {'ready': False, 'error_type': type(exc).__name__, 'error_tail': str(exc)[-700:]}\n"
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
        completed = _run_wsl_probe(
            distro,
            script,
            timeout=_env_timeout_seconds("GOODQ_WSL_BLACK_BOX_PROBE_TIMEOUT_SEC", 180),
        )
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
        "import os, sys\n"
        "os.environ['HF_HUB_OFFLINE'] = '1'\n"
        "from huggingface_hub import snapshot_download\n"
        f"sys.path.insert(0, {workspace!r})\n"
        "from process_audio import _load_runtime_config, _load_pyannote_pipeline, _resolve_hf_cache_dir\n"
        "model_name = str((_load_runtime_config().get('models') or {}).get('diarization', 'pyannote/speaker-diarization-3.1'))\n"
        "token = os.getenv('PYANNOTE_TOKEN') or os.getenv('HUGGINGFACE_TOKEN') or os.getenv('HF_TOKEN')\n"
        "cache_dir = _resolve_hf_cache_dir()\n"
        f"required_repos = [{repo_list}]\n"
        "if model_name != 'pyannote/speaker-diarization-3.1':\n"
        f"    required_repos = [repo for repo in required_repos if repo not in {WSL_DIARIZATION_MODEL_REPOS!r}]\n"
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
        "    pipeline = _load_pyannote_pipeline(Pipeline, model_name, token or '', cache_dir=cache_dir, is_offline=True)\n"
        "    if pipeline is None:\n"
        "        raise RuntimeError('Configured diarization pipeline returned no model')\n"
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
        "import json, sys\n"
        f"sys.path.insert(0, {workspace!r})\n"
        "try:\n"
        "    from process_audio import _load_trained_wav2vec, _resolve_hf_cache_dir, Wav2Vec2FeatureExtractor\n"
        "    cache_dir = _resolve_hf_cache_dir()\n"
        "    model, receipt = _load_trained_wav2vec(\n"
        "        'ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition',\n"
        "        cache_dir=cache_dir, is_offline=True, emotion=True,\n"
        "    )\n"
        "    if receipt.get('strict') is not True or receipt.get('missing_inference_keys') != []:\n"
        "        raise RuntimeError('Emotion checkpoint did not load all trained inference tensors')\n"
        "    Wav2Vec2FeatureExtractor.from_pretrained(\n"
        "        'ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition',\n"
        "        cache_dir=cache_dir,\n"
        "        local_files_only=True,\n"
        "    )\n"
        "except Exception as exc:\n"
        "    print('wav2vec_enrichment_unavailable')\n"
        "    print(f'{type(exc).__name__}: {exc}')\n"
        "else:\n"
        "    print('wav2vec_model_load=' + json.dumps(receipt, sort_keys=True))\n"
        "    print('wav2vec_enrichment_ready')\n"
        "PY"
    )


def _build_speaker_signature_probe_script(workspace: str) -> str:
    return (
        f"source '{workspace}/setup_cuda_env.sh' >/dev/null 2>&1 && "
        "python3 - <<'PY'\n"
        "import sys, tempfile\n"
        f"sys.path.insert(0, {workspace!r})\n"
        "from speaker_signature import load_encoder\n"
        "with tempfile.TemporaryDirectory(prefix='goodq-ecapa-probe-') as directory:\n"
        "    load_encoder('cpu', directory)\n"
        "print('speaker_signature_ready')\n"
        "PY"
    )


def _probe_clap_handoff_contract() -> Dict[str, Any]:
    """Prove the WSL composite has a canonical Windows CLAP continuation."""

    import ast

    repo_root = Path(__file__).resolve().parents[1]
    try:
        bridge_source = (repo_root / "steps" / "audio" / "audio_wsl2_bridge.py").read_text(
            encoding="utf-8"
        )
        clap_source = (repo_root / "steps" / "audio_embed_clap" / "step.py").read_text(
            encoding="utf-8"
        )
        bridge_functions = {
            node.name
            for node in ast.parse(bridge_source).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        clap_functions = {
            node.name
            for node in ast.parse(clap_source).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        ready = (
            "_build_wsl_capability_outcomes" in bridge_functions
            and "audio_embed_clap" in clap_functions
            and '"clap_handoff": clap_handoff' in bridge_source
            and '"canonical_clap_required"' in bridge_source
            and '"required_step": "audio_embed_clap"' in bridge_source
        )
        return {
            "ready": bool(ready),
            "required_step": "audio_embed_clap",
            "reason": (
                "canonical_clap_required"
                if ready
                else "canonical_clap_contract_unavailable"
            ),
        }
    except Exception as exc:
        return {
            "ready": False,
            "required_step": "audio_embed_clap",
            "reason": "canonical_clap_contract_unavailable",
            "error_type": type(exc).__name__,
            "error": str(exc)[-500:],
        }


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
        "clap_handoff_ready": False,
        "clap_handoff": {
            "ready": False,
            "required_step": "audio_embed_clap",
            "reason": "unresolved",
        },
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
        "torchcodec_applicability": "unknown",
        "audio_decode_ready": None,
        "recommended_install_command": _RECOMMENDED_INSTALL_COMMAND,
    }
    workspace = result["workspace"]
    distro = result["distro"]

    workspace_script = (
        f"test -f '{workspace}/setup_cuda_env.sh' && "
        f"test -f '{workspace}/process_audio.py' && "
        f"(test -x '{workspace}/venv/bin/python' || test -x '{workspace}/env/bin/python') && "
        f"{{ if test -f '{workspace}/runtime_manifest.json'; then printf 'runtime_manifest_declared\\n'; fi; }}"
    )
    try:
        workspace_probe = _run_wsl_probe(
            distro,
            workspace_script,
            timeout=_env_timeout_seconds("GOODQ_WSL_WORKSPACE_PROBE_TIMEOUT_SEC", 90),
        )
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
    manifest_declared = 'runtime_manifest_declared' in (workspace_probe.stdout or '')

    transcription_script = (
        f"source '{workspace}/setup_cuda_env.sh' >/dev/null 2>&1 && "
        "python3 -c \"import faster_whisper, torch; "
        "print('transcription_ready'); "
        "print('gpu_ready' if torch.cuda.is_available() else 'gpu_unavailable')\""
    )
    try:
        transcription_probe = _run_wsl_probe(
            distro,
            transcription_script,
            timeout=_env_timeout_seconds("GOODQ_WSL_TRANSCRIPTION_PROBE_TIMEOUT_SEC", 180),
        )
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
        "python3 -c \"import importlib.util as iu, sys; "
        f"sys.path.insert(0, '{_python_path_literal(workspace)}'); "
        f"spec = iu.spec_from_file_location('goodq_process_audio', '{process_audio_path}'); "
        "module = iu.module_from_spec(spec); "
        "spec.loader.exec_module(module); "
        "print('process_import_ready')\""
    )
    try:
        process_import_probe = _run_wsl_probe(
            distro,
            process_import_script,
            timeout=_env_timeout_seconds("GOODQ_WSL_PROCESS_IMPORT_PROBE_TIMEOUT_SEC", 180),
        )
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
    result["clap_handoff"] = _probe_clap_handoff_contract()
    result["clap_handoff_ready"] = bool(result["clap_handoff"].get("ready"))

    abi_script = (
        f"source '{workspace}/setup_cuda_env.sh' >/dev/null 2>&1 && "
        "python3 -c \"import torch, torchvision; from torchvision.ops import nms; print('abi_ready')\""
    )
    try:
        abi_probe = _run_wsl_probe(
            distro,
            abi_script,
            timeout=_env_timeout_seconds("GOODQ_WSL_ABI_PROBE_TIMEOUT_SEC", 120),
        )
    except Exception as exc:
        if manifest_declared:
            result.update(runtime_ready=False, ready=False, detail=f'declared runtime ABI probe failed: {exc}')
            return result
        result["ready"] = True
        result["detail"] = f"transcription runtime ready; ABI probe failed: {exc}"
        return result

    if abi_probe.returncode == 0:
        result["abi_ready"] = True
    else:
        result["abi_probe_stderr_tail"] = ((abi_probe.stderr or abi_probe.stdout or "").strip())[-600:]

    diarization_script = _build_diarization_probe_script(workspace)
    try:
        diarization_probe = _run_wsl_probe(
            distro,
            diarization_script,
            timeout=_env_timeout_seconds("GOODQ_WSL_DIARIZATION_PROBE_TIMEOUT_SEC", 180),
        )
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

    try:
        signature_probe = _run_wsl_probe(
            distro, _build_speaker_signature_probe_script(workspace),
            timeout=_env_timeout_seconds("GOODQ_WSL_SPEAKER_PROBE_TIMEOUT_SEC", 180))
        result["speaker_signature_ready"] = (
            signature_probe.returncode == 0 and
            "speaker_signature_ready" in (signature_probe.stdout or ""))
        if not result["speaker_signature_ready"]:
            result["speaker_signature_detail"] = (signature_probe.stderr or signature_probe.stdout or "")[-600:]
    except Exception as exc:
        result["speaker_signature_ready"] = False
        result["speaker_signature_detail"] = f"{type(exc).__name__}: {exc}"

    wav2vec_script = _build_wav2vec_enrichment_probe_script(workspace)
    try:
        wav2vec_probe = _run_wsl_probe(
            distro,
            wav2vec_script,
            timeout=_env_timeout_seconds("GOODQ_WSL_WAV2VEC_PROBE_TIMEOUT_SEC", 180),
        )
    except Exception as exc:
        wav2vec_probe = None
        result["wav2vec_enrichment_detail"] = f"{type(exc).__name__}: {exc}"

    if wav2vec_probe is not None and wav2vec_probe.returncode == 0:
        wav2vec_stdout = (wav2vec_probe.stdout or "").strip()
        wav2vec_stderr = (wav2vec_probe.stderr or "").strip()
        if wav2vec_stderr:
            result["wav2vec_enrichment_probe_stderr_tail"] = wav2vec_stderr[-600:]
        result["wav2vec_enrichment_ready"] = "wav2vec_enrichment_ready" in wav2vec_stdout.splitlines()
        for line in wav2vec_stdout.splitlines():
            if line.startswith("wav2vec_model_load="):
                result["wav2vec_model_load"] = json.loads(line.partition("=")[2])
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
    manifest_check = _check_runtime_manifest(black_box)
    if manifest_declared and manifest_check['status'] == 'not_declared':
        manifest_check = {'status': 'invalid', 'reason': 'runtime_manifest_probe_unavailable'}
    result['runtime_manifest'] = manifest_check
    if manifest_check.get('expected_torch_lane'):
        result['expected_torch_lane'] = manifest_check['expected_torch_lane']
        result['recommended_install_command'] = None
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
        result["torch_lane_status"] = _classify_torch_lane(package_versions, result['expected_torch_lane'])
    else:
        result["torch_lane_status"] = _classify_torch_lane(result["detected_versions"])
    runtime_warnings: list[str] = []
    if result["torch_lane_status"] == "differs_from_expected":
        runtime_warnings.append("torch_lane_differs_from_expected")
    audio_decode = black_box.get("audio_decode") if isinstance(black_box, dict) else None
    if isinstance(audio_decode, dict):
        result["audio_decode_ready"] = audio_decode.get("ready") is True
        if not result["audio_decode_ready"]:
            runtime_warnings.append("active_audio_decoder_unavailable")
    transcription_decode = black_box.get('transcription_decode') if isinstance(black_box, dict) else None
    if isinstance(transcription_decode, dict):
        result['transcription_decode_ready'] = transcription_decode.get('ready') is True
        if not result['transcription_decode_ready']:
            runtime_warnings.append('transcription_decoder_unavailable')
    # This exact supported lane decodes via torchaudio and passes waveforms to
    # pyannote 3.3.2. Do not imply that TorchCodec is installed, or extrapolate
    # this applicability decision to other versions or an untested decoder.
    if (result["torch_lane_status"] == "matches_expected"
            and manifest_check['status'] == 'not_declared'
            and isinstance(package_versions, dict)
            and package_versions.get("pyannote.audio") == "3.3.2"
            and result["audio_decode_ready"] is True):
        result["torchcodec_applicability"] = "not_required_for_active_lane"
    torchcodec = black_box.get("torchcodec") if isinstance(black_box, dict) else None
    if isinstance(torchcodec, dict):
        result["torchcodec_ready"] = bool(torchcodec.get("ready"))
        if not result["torchcodec_ready"]:
            error_tail = str(torchcodec.get("error_tail") or "")
            families = _classify_torchcodec_error(error_tail)
            torchcodec["error_families"] = families
            result["torchcodec_detail"] = ", ".join(families)
            if result["torchcodec_applicability"] != "not_required_for_active_lane":
                runtime_warnings.append("torchcodec_decoder_unavailable")
    pyannote_import = black_box.get("pyannote_import") if isinstance(black_box, dict) else None
    pyannote_warning_text = str(result.get("diarization_probe_stderr_tail") or "")
    if isinstance(pyannote_import, dict):
        pyannote_warning_text += "\n" + str(pyannote_import.get("warning_tail") or "")
    if "torchcodec" in pyannote_warning_text.lower():
        result["torchcodec_applicability"] = "unknown"
        if result["torchcodec_ready"] is False:
            runtime_warnings.append("torchcodec_decoder_unavailable")
        runtime_warnings.append("pyannote_warned_torchcodec_decoder_unavailable")
    if manifest_check.get('requires_torchcodec'):
        result['torchcodec_applicability'] = 'required_by_runtime_manifest'
    if not result.get("speaker_signature_ready", False):
        runtime_warnings.append("speaker_signature_unavailable")
    if not result["wav2vec_enrichment_ready"]:
        runtime_warnings.append("wav2vec_enrichment_unavailable")
    if not result["clap_handoff_ready"]:
        runtime_warnings.append("clap_handoff_unavailable")
    result["runtime_warnings"] = sorted(set(runtime_warnings))

    if manifest_check['status'] != 'not_declared':
        required = ['gpu_ready', 'abi_ready', 'diarization_ready', 'wav2vec_enrichment_ready',
                    'speaker_signature_ready', 'audio_decode_ready', 'transcription_decode_ready']
        if manifest_check.get('requires_torchcodec'):
            required.append('torchcodec_ready')
        missing = [key for key in required if result.get(key) is not True]
        result['runtime_manifest']['unavailable_capabilities'] = missing
        if manifest_check['status'] != 'matched' or missing:
            result.update(runtime_ready=False, ready=False, detail='declared_audio_runtime_not_ready')
            return result

    result["ready"] = True
    if result["abi_ready"] and result["diarization_ready"]:
        result["detail"] = "workspace, transcription runtime, process import, ABI, and diarization checks are ready"
    elif result["abi_ready"]:
        result["detail"] = "transcription runtime ready; process_audio import ready; diarization unavailable"
    else:
        result["detail"] = "transcription runtime ready; process_audio import ready; torchvision ABI unavailable (diarization may be degraded)"
    return result


def _get_config_and_host_cfg() -> Dict[str, Any]:
    REPO_ROOT = Path(__file__).resolve().parents[1]
    import sys
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        from steps.common.config_loader import load_configs
        cfg = load_configs()
    except Exception:
        cfg = {}
    return cfg.get("host", {}) if isinstance(cfg, dict) else {}


def _default_wsl_distro() -> str:
    explicit = os.environ.get("GOODQ_WSL_DISTRO")
    if explicit:
        return explicit.strip()
    host_cfg = _get_config_and_host_cfg()
    config_distro = host_cfg.get("wsl_distro")
    if config_distro and config_distro != "auto":
        return str(config_distro).strip()
    return "Ubuntu"


def _default_wsl_user() -> str:
    explicit = os.environ.get("GOODQ_WSL_USER")
    if explicit:
        return explicit.strip()
    host_cfg = _get_config_and_host_cfg()
    config_user = host_cfg.get("wsl_user")
    if config_user and config_user != "auto":
        return str(config_user).strip()
    for candidate in (os.environ.get("USER"), os.environ.get("USERNAME"), os.environ.get("LOGNAME")):
        if candidate:
            return candidate.strip()
    return "goodq"


def _default_wsl_workspace() -> str:
    explicit = os.environ.get("GOODQ_WSL_WORKSPACE")
    if explicit:
        return explicit.strip().rstrip("/")
    host_cfg = _get_config_and_host_cfg()
    config_workspace = host_cfg.get("wsl_workspace")
    if config_workspace and config_workspace != "auto":
        return str(config_workspace).strip().rstrip("/")
    wsl_user = _default_wsl_user()
    return f"/home/{wsl_user}/goodq_audio"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect the WSL audio runtime without mutating it.")
    parser.add_argument(
        "--distro",
        default=_default_wsl_distro(),
        help="WSL distro to inspect. Defaults to configuration or GOODQ_WSL_DISTRO or Ubuntu.",
    )
    parser.add_argument(
        "--workspace",
        default=_default_wsl_workspace(),
        help="WSL audio workspace. Defaults to configuration or GOODQ_WSL_WORKSPACE or /home/<user>/goodq_audio.",
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

