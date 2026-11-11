from __future__ import annotations
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Audio-specific GPU optimization
from steps.common.audio_gpu_optimizer import get_audio_gpu_optimizer
from steps.common.profile_config import (
    is_baseline,
    log_runtime_profile_state,
    require_gpu,
    require_wsl_audio,
)

from typing import Any, Dict, List, Optional, Tuple

import json as _json
import math
import re
import subprocess
import tempfile
import time
import logging
import shlex
import wave
from pathlib import Path

from steps.common.config_loader import get_runtime_paths, load_configs

logger = logging.getLogger(__name__)


_FW_CACHE: Dict[Tuple[str, str, str], Any] = {}  # (model_id, device, compute_type) -> model


def _resolve_models_root() -> str:
    runtime_paths = get_runtime_paths(load_configs({}), "models_cache")
    return str(Path(runtime_paths["models_cache"]).resolve())


def _detect_transcription_device() -> Tuple[str, str]:
    """
    Detect the best local device for faster-whisper.

    The Windows fallback path uses faster-whisper/CTranslate2 for inference, so
    torch-only CUDA probing is too narrow. Prefer torch when it is available
    because the optimizer stack uses it, but allow CTranslate2 to unlock local
    GPU transcription when torch itself is CPU-only.
    """
    if is_baseline() and not require_gpu():
        return "cpu", "profile:baseline_cpu_safe"

    try:
        import torch  # type: ignore

        if bool(getattr(torch, "cuda", None) and torch.cuda.is_available()):
            return "cuda", f"torch:{getattr(torch, '__version__', 'unknown')}"
    except Exception as e:
        logger.debug(
            "[TRANSCRIBE] Torch CUDA probe failed exc_type=%s exc=%s",
            type(e).__name__,
            e,
        )

    try:
        import ctranslate2  # type: ignore

        if int(ctranslate2.get_cuda_device_count()) > 0:
            # CTranslate2 can detect the GPU via the CUDA runtime (part of
            # the display driver), but actual inference requires cuBLAS.
            # Verify that cuBLAS is loadable before declaring CUDA ready;
            # a missing cuBLAS causes a RuntimeError on the first
            # model.transcribe() call which corrupts CTranslate2 internal
            # state and deadlocks all subsequent calls.
            import ctypes
            _cublas_name = "cublas64_12.dll" if os.name == "nt" else "libcublas.so.12"
            try:
                ctypes.CDLL(_cublas_name)
            except OSError:
                logger.warning(
                    "[TRANSCRIBE] CTranslate2 detects CUDA but %s is not loadable; "
                    "falling back to CPU to avoid inference deadlock",
                    _cublas_name,
                )
                return "cpu", f"ctranslate2_cublas_missing:{_cublas_name}"
            return "cuda", f"ctranslate2:{getattr(ctranslate2, '__version__', 'unknown')}"
    except Exception as e:
        logger.debug(
            "[TRANSCRIBE] CTranslate2 CUDA probe failed exc_type=%s exc=%s",
            type(e).__name__,
            e,
        )

    return "cpu", "no_cuda_backend"


def _load_fw_model(model_id: str, device: str, compute_type: str, duration_minutes: float = None) -> Any:
    """Load faster-whisper model with GPU optimization"""
    key = (model_id, device, compute_type)
    if key in _FW_CACHE:
        return _FW_CACHE[key]
    
    try:
        from faster_whisper import WhisperModel  # type: ignore
        
        # CPU baseline must not initialize the GPU optimizer: that path imports
        # and probes Torch even though no CUDA work will be performed.
        optimizer = get_audio_gpu_optimizer() if device == "cuda" else None
        
        # Configure GPU for transcription
        if device == "cuda":
            gpu_config = optimizer.configure_for_transcription(duration_minutes)
            logger.info(f"[TRANSCRIBE] GPU configured: {gpu_config.memory_fraction*100:.0f}% VRAM, {gpu_config.compute_type} precision")
            
            # Warmup GPU
            optimizer.warmup_gpu()
            
            # Use optimized compute type from config
            compute_type = gpu_config.compute_type
        
        # CTranslate2 multi-worker loading on Windows is prone to silent
        # deadlocks, so keep one model worker.  CPU inference itself needs a
        # bounded number of intra-op threads: one thread made a 120-second
        # baseline witness exceed its bounded runtime on a follower host.
        #
        # On Intel hybrid architectures (P-core + E-core, 12th/13th/14th gen),
        # raising cpu_threads beyond the P-core count causes CTranslate2 to
        # schedule onto much slower E-cores, producing a 40%+ regression.
        # Cap at 4 threads which fits safely within the P-core pool on all
        # tested follower hardware (i7-13620H: 6P+4E).
        num_workers_val = 1 if (os.name == "nt" or device != "cuda") else 2
        cpu_threads_val = 4 if (os.name == "nt" and device == "cpu") else 0
        
        logger.info(
            "[TRANSCRIBE] Loading Whisper model '%s' on %s (%s) with "
            "num_workers=%s cpu_threads=%s...",
            model_id,
            device,
            compute_type,
            num_workers_val,
            cpu_threads_val,
        )
        load_start = time.time()
        
        model = WhisperModel(
            model_id, 
            device=device, 
            compute_type=compute_type,
            num_workers=num_workers_val,
            cpu_threads=cpu_threads_val,
        )
        
        load_time = time.time() - load_start
        logger.info(f"[TRANSCRIBE] Model loaded in {load_time:.1f}s")
        
        if device == "cuda":
            optimizer.print_memory_stats()
        
    except Exception as e:
        logger.error(f"[TRANSCRIBE] Model load failed: {e}")
        model = None
    
    _FW_CACHE[key] = model
    return model


def _audio_duration(path: str) -> Optional[float]:
    """Get audio duration using soundfile/librosa with stdlib WAV fallback."""
    try:
        import soundfile as sf  # type: ignore

        info = sf.info(path)
        if getattr(info, "duration", None):
            return float(info.duration)
        if getattr(info, "frames", None) and getattr(info, "samplerate", None):
            return float(info.frames) / float(info.samplerate)
    except ImportError:
        # soundfile not available, try librosa
        pass
    except Exception as e:
        print(f'[DEBUG] soundfile failed for {path}: {type(e).__name__}: {str(e)}')
        pass
    
    try:
        import librosa  # type: ignore
        return float(librosa.get_duration(filename=path))
    except ImportError:
        pass
    except Exception as e:
        print(f'[ERROR] Audio duration detection failed for {path}')
        print(f'[ERROR] Exception: {type(e).__name__}: {str(e)}')
        if os.path.isfile(path):
            print(f'[ERROR] File exists, size: {os.path.getsize(path)} bytes')
        else:
            print(f'[ERROR] File does not exist: {path}')
    
    # Final fallback: stdlib WAV parser (portable, no optional dependency required).
    try:
        with wave.open(path, 'rb') as wav_fh:
            frames = int(wav_fh.getnframes() or 0)
            rate = int(wav_fh.getframerate() or 0)
        if frames > 0 and rate > 0:
            return float(frames) / float(rate)
    except Exception as e:
        logger.warning(
            "audio_transcribe duration fallback failed operation=%s path=%s exc_type=%s exc=%s",
            "wave_duration_probe",
            path,
            type(e).__name__,
            e,
        )

    print(f'[ERROR] Audio duration detection unavailable for {path}')
    return None


def _split_range(start: float, end: float, chunk_seconds: float, speaker: Optional[str]) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    if not math.isfinite(start) or not math.isfinite(end):
        return segments
    if end <= start:
        return segments
    if chunk_seconds <= 0:
        segments.append({"start": start, "end": end, "speaker": speaker})
        return segments
    cur = start
    while cur < end:
        nxt = min(end, cur + chunk_seconds)
        if nxt - cur <= 0:
            break
        segments.append({"start": cur, "end": nxt, "speaker": speaker})
        cur = nxt
    return segments


def _build_chunks(item: Dict[str, Any], cfg: Dict[str, Any], duration: Optional[float], chunk_seconds: float) -> List[Dict[str, Any]]:
    diarization = item.get("diarization")
    chunks: List[Dict[str, Any]] = []
    if isinstance(diarization, list) and diarization:
        for seg in diarization:
            try:
                start = float(seg.get("start", 0.0) or 0.0)
                end = float(seg.get("end", start) or start)
            except Exception as e:
                print(f'[ERROR] Exception in step.py line 76: {str(e)}')
                continue
            speaker = seg.get("speaker")
            chunks.extend(_split_range(max(0.0, start), max(start, end), chunk_seconds, speaker))
    else:
        if duration is None:
            return []
        chunks.extend(_split_range(0.0, max(0.1, duration), chunk_seconds, None))
    filtered = [c for c in chunks if c["end"] - c["start"] >= 0.2]
    return filtered or chunks


def _slice_to_wav(src_path: str, start: float, end: float, ffmpeg_path: Optional[str]) -> Optional[str]:
    """Slice audio file from start to end time, using soundfile or ffmpeg fallback."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp_path = tmp.name
    tmp.close()
    duration = max(0.1, end - start)
    
    # Check if debug mode is enabled
    debug_mode = os.environ.get('GOODQ_DEBUG_KEEP_TEMP', '').lower() == 'true'
    
    try:
        import soundfile as sf  # type: ignore

        with sf.SoundFile(src_path) as fh:
            sr = fh.samplerate
            start_frame = max(0, int(start * sr))
            end_frame = max(start_frame + 1, int((start + duration) * sr))
            fh.seek(start_frame)
            data = fh.read(end_frame - start_frame)
        if data.size == 0:
            raise ValueError("empty slice")
        sf.write(tmp_path, data, sr)
        if debug_mode:
            print(f'[DEBUG] Sliced audio with soundfile: {tmp_path} ({data.size} samples)')
        return tmp_path
    except ImportError:
        # soundfile not available, try ffmpeg
        if debug_mode:
            print(f'[DEBUG] soundfile not available, trying ffmpeg')
        pass
    except Exception as e:
        print(f'[DEBUG] soundfile slicing failed: {type(e).__name__}: {str(e)}')
        if ffmpeg_path is None:
            print(f'[ERROR] Audio slicing failed: {type(e).__name__}: {str(e)}')
            print(f'[ERROR] soundfile unavailable and no ffmpeg path configured')
            print(f'[ERROR] Source: {src_path}, slice: {start:.2f}s-{end:.2f}s')
            try:
                os.remove(tmp_path)
            except Exception as remove_err:
                print(f"[DEBUG] Failed to remove temp slice file: {remove_err}")
            return None
    
    # Try ffmpeg fallback
    if ffmpeg_path:
        try:
            cmd = [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{max(0.0, start):.3f}",
                "-t",
                f"{duration:.3f}",
                "-i",
                src_path,
                tmp_path,
            ]
            if debug_mode:
                print(f'[DEBUG] Running ffmpeg: {" ".join(cmd)}')
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
            
            # Verify output file was created
            if not os.path.isfile(tmp_path) or os.path.getsize(tmp_path) == 0:
                raise ValueError(f"ffmpeg produced empty or missing file")
            
            if debug_mode:
                print(f'[DEBUG] ffmpeg slice created: {tmp_path} ({os.path.getsize(tmp_path)} bytes)')
            return tmp_path
        except subprocess.CalledProcessError as e:
            print(f'[ERROR] ffmpeg slicing failed with code {e.returncode}')
            print(f'[ERROR] Command: {" ".join(cmd)}')
            print(f'[ERROR] Stderr: {e.stderr}')
            print(f'[ERROR] Source: {src_path}, slice: {start:.2f}s-{end:.2f}s')
        except Exception as e:
            print(f'[ERROR] Audio slicing failed: {type(e).__name__}: {str(e)}')
            print(f'[ERROR] Source: {src_path}, slice: {start:.2f}s-{end:.2f}s')
    else:
        print(f'[ERROR] Audio slicing failed: no ffmpeg available')
        print(f'[ERROR] Source: {src_path}, slice: {start:.2f}s-{end:.2f}s')
    
    # Clean up on failure
    try:
        if os.path.isfile(tmp_path):
            if debug_mode:
                print(f'[DEBUG] Keeping failed temp file for inspection: {tmp_path}')
            else:
                os.remove(tmp_path)
    except Exception as remove_err:
        print(f"[DEBUG] Failed to clean up temp slice: {remove_err}")
    return None


def _transcribe_chunk_whisper_cli(chunk_path, offset, whisper_cli, whisper_model):
    from steps.audio_transcribe.whisper_cpp import WhisperCppModel
    from wsl2_audio.transcription_contract import transcribe_file
    return transcribe_file(WhisperCppModel(whisper_cli, whisper_model), chunk_path,
                           offset=offset, engine="whisper.cpp")


def _transcribe_chunk_fw(chunk_path: str, offset: float, model: Any, temperature: float = 0.0,
                         *, vocabulary=None, language=None, beam_size=5) -> Optional[Dict[str, Any]]:
    if model is None:
        return None
    from wsl2_audio.transcription_contract import transcribe_file
    return transcribe_file(model, chunk_path, offset=offset, temperature=temperature,
                           vocabulary=vocabulary, language=language, beam_size=beam_size)


def _windows_to_wsl_path(path: str) -> Optional[str]:
    if not isinstance(path, str) or not path:
        return None
    normalized = path.replace("\\", "/")
    match = re.match(r"^([A-Za-z]):/(.*)$", normalized)
    if match:
        drive = match.group(1).lower()
        remainder = match.group(2)
        return f"/mnt/{drive}/{remainder}"
    if normalized.startswith("/"):
        return normalized
    return None


def _resolve_wsl_python(distro: str, wsl_workspace: str) -> str:
    candidates = [
        f"{wsl_workspace}/venv/bin/python",
        f"{wsl_workspace}/env/bin/python",
    ]
    for candidate in candidates:
        probe = subprocess.run(
            ["wsl", "-d", distro, "--", "test", "-x", candidate],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if probe.returncode == 0:
            return candidate
    return candidates[0]


def _run_wsl_faster_whisper_venv(input_path: str, options: Optional[dict] = None) -> Dict[str, Any]:
    distro = (os.environ.get("GOODQ_WSL_DISTRO") or "Ubuntu-22.04").strip() or "Ubuntu-22.04"
    wsl_workspace = (os.environ.get("GOODQ_WSL_WORKSPACE") or "").strip()
    if not wsl_workspace:
        wsl_user = (
            os.environ.get("GOODQ_WSL_USER")
            or os.environ.get("USERNAME")
            or os.environ.get("USER")
            or "goodq"
        )
        wsl_workspace = f"/home/{wsl_user}/goodq_audio"
    wsl_workspace = wsl_workspace.rstrip("/")
    wsl_python = _resolve_wsl_python(distro, wsl_workspace)

    helper_candidates: List[str] = [f"{wsl_workspace}/fw_transcribe.py"]

    deduped_helpers: List[str] = []
    seen_helpers = set()
    for candidate in helper_candidates:
        if candidate and candidate not in seen_helpers:
            deduped_helpers.append(candidate)
            seen_helpers.add(candidate)

    helper_path = None
    for candidate in deduped_helpers:
        probe = subprocess.run(
            ["wsl", "-d", distro, "--", "test", "-f", candidate],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if probe.returncode == 0:
            helper_path = candidate
            break
    if not helper_path:
        raise RuntimeError(f"WSL helper script not found. Checked: {', '.join(deduped_helpers) or 'none'}")

    wsl_input_path = _windows_to_wsl_path(input_path)
    if not wsl_input_path:
        raise RuntimeError(f"Could not map audio path to WSL mount path: {input_path}")

    tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
    output_json_path = tmp_out.name
    tmp_out.close()
    try:
        wsl_output_path = _windows_to_wsl_path(output_json_path)
        if not wsl_output_path:
            raise RuntimeError(f"Could not map output path to WSL mount path: {output_json_path}")

        arguments = [wsl_python, helper_path, wsl_input_path, wsl_output_path,
                     _json.dumps(options or {'temperature': 0.})]
        environment = []
        for name in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_HUB_DISABLE_TELEMETRY'):
            if os.environ.get(name) in ('0', '1'):
                environment.append(f'{name}={os.environ[name]}')
        command = f"source {shlex.quote(wsl_workspace+'/setup_cuda_env.sh')} && exec "
        command += ' '.join(shlex.quote(value) for value in ['env', *environment, *arguments])
        cmd = ['wsl', '-d', distro, '--', 'bash', '-lc', command]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if not os.path.isfile(output_json_path):
            raise RuntimeError("WSL faster-whisper did not produce an output JSON file")
        with open(output_json_path, "r", encoding="utf-8") as fh:
            payload = _json.load(fh)
        if not isinstance(payload, dict):
            raise RuntimeError('WSL transcription returned a non-object result')
        if proc.returncode != 0:
            payload.update(status='error', transcription_status='error',
                transcription_error=payload.get('error') or f'WSL helper exited {proc.returncode}')
        decoding = payload.get('transcription_decoding') or {}
        if payload.get('status') == 'success' and (
                decoding.get('temperature') != (options or {}).get('temperature', 0.)
                or (decoding.get('source_regions') or {}).get('policy') != 'source_audio_v2'):
            payload.update(status='error', transcription_status='error',
                transcription_error='WSL helper did not confirm requested coverage and decoding policy')
        return payload
    finally:
        try:
            if os.path.isfile(output_json_path):
                os.remove(output_json_path)
        except Exception:
            pass


def audio_transcribe(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transcribe audio using Whisper with GPU optimization.
    Tracks performance metrics for continuous optimization.
    
    Tries WSL2 GPU acceleration first (2-5x faster), falls back to Windows if unavailable.
    Wraps the underlying implementation in ModelLifecycleManager to guarantee clean VRAM unloading.
    """
    model_ctx_holder = [None]
    try:
        return _audio_transcribe_impl(item, cfg, model_ctx_holder)
    finally:
        if model_ctx_holder[0]:
            try:
                model_ctx_holder[0].__exit__(None, None, None)
            except Exception:
                pass


def _audio_transcribe_impl(item: Dict[str, Any], cfg: Dict[str, Any], model_ctx_holder: list) -> Dict[str, Any]:
    """
    Transcribe audio using Whisper with GPU optimization.
    Tracks performance metrics for continuous optimization.
    
    Tries WSL2 GPU acceleration first (2-5x faster), falls back to Windows if unavailable.
    """
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {
            "transcript": None,
            "transcript_meta": {
                "status": "no_file",
                "reason": "source_file_missing",
                "error": "source_file_missing",
                "engine": "hybrid_whisper",
                "model": None,
                "device": "none",
            },
        }

    # Try WSL2 acceleration first (if available and enabled)
    cfg_audio = (cfg.get("audio", {}) or {})
    tx_cfg = (cfg_audio.get("transcribe", {}) or {})
    use_wsl_default = False if is_baseline() else True
    use_wsl = tx_cfg.get("use_wsl2", use_wsl_default)

    log_runtime_profile_state(
        logger=logger,
        context="steps.audio_transcribe.step",
        gpu_enabled=None,
        wsl_enabled=bool(use_wsl),
    )

    if not use_wsl and require_wsl_audio():
        raise RuntimeError("GOODQ_REQUIRE_WSL_AUDIO=1 but WSL audio is disabled by profile/config")
    
    wsl_attempt = None
    if use_wsl:
        from steps.audio.audio_wsl2_bridge import (
            audio_transcribe_wsl2, unified_transcription_options, _transcription_projection)
        try:
            if str(os.environ.get('GOODQ_WSL_TRANSCRIBE_ENGINE') or '').upper() == 'FASTER_WHISPER_VENV':
                from steps.audio.audio_wsl2_bridge import _apply_post_filter_vocabulary_context
                tx_mode = tx_cfg.get('vocabulary_mode', 'guarded_hotwords')
                options = {'temperature': tx_cfg.get('temperature', 0.),
                           'vocabulary': None if tx_mode == 'post_filter_only' else tx_cfg.get('vocabulary'),
                           'language': tx_cfg.get('language'), 'beam_size': tx_cfg.get('beam_size', 5)}
                if tx_cfg.get('model'): options['model'] = tx_cfg['model']
                raw = _run_wsl_faster_whisper_venv(path, options)
                if tx_mode == 'post_filter_only' and tx_cfg.get('vocabulary') is not None and isinstance(raw, dict):
                    raw = _apply_post_filter_vocabulary_context(raw, tx_cfg.get('vocabulary'))
                wsl_result = _transcription_projection(raw, engine='wsl_faster_whisper_venv')
            else:
                wsl_result = audio_transcribe_wsl2(path, duration=item.get('duration'),
                    timeout=tx_cfg.get('timeout', 3600), **unified_transcription_options(cfg))
            if wsl_result.get('status') in ('success', 'partial'):
                return wsl_result
            wsl_attempt = wsl_result
            raise RuntimeError(str(wsl_result.get('error') or 'WSL transcription failed'))
        except Exception as exc:
            if require_wsl_audio():
                raise RuntimeError(f'GOODQ_REQUIRE_WSL_AUDIO=1 and WSL transcription failed: {exc}') from exc
            logger.warning('[TRANSCRIBE] WSL failed; using the configured local path: %s', exc)
            if wsl_attempt is None:
                wsl_attempt = {'status': 'error', 'error': str(exc)}

    # Windows processing
    logger.info(f"[TRANSCRIBE] Using Windows processing")
    
    cfg_audio = (cfg.get("audio", {}) or {})
    tx_cfg = (cfg_audio.get("transcribe", {}) or {})
    chunk_seconds = float(tx_cfg.get("chunk_seconds") or 10)
    chunk_seconds = max(1.0, chunk_seconds)

    from steps.common.tool_paths import resolve_ffmpeg

    ffmpeg_path = resolve_ffmpeg(cfg) or "ffmpeg"

    duration = _audio_duration(path)
    duration_minutes = (duration / 60.0) if duration else None
    
    tools_cfg = ((cfg.get("config", {}) or {}).get("tools", {}) or {})
    whisper_cli = tools_cfg.get("whisper_cli")
    whisper_model_path = tools_cfg.get("whisper_ggml_model")

    device, device_probe = _detect_transcription_device()
    logger.info("[TRANSCRIBE] Device selected=%s via=%s", device, device_probe)
    optimizer = get_audio_gpu_optimizer() if device == "cuda" else None
    
    # Smart model selection based on CPU count.  An explicit config value
    # in audio.transcribe.model always takes precedence.
    #
    # Machines with fewer than 20 logical CPUs (laptop-class, e.g. i7-13620H
    # with 16 threads) use 'small' regardless of device.  Reasons:
    #
    # 1. CPU baseline: medium takes ~507s vs ~184s for small on these CPUs,
    #    and transcript quality is nearly identical for memory/search.
    # 2. GPU on laptops (6 GB RTX 3060/4050): medium (1.5 GB) competes for
    #    VRAM with other pipeline models.  On 6 GB laptop GPUs, the CUDA path
    #    with medium caused WhisperModel() to hang for 1600+ seconds due to
    #    symlink resolution and HF hub metadata issues on Windows.
    #    small (0.5 GB) loads reliably in ~2s on the same hardware.
    #
    # Desktop-class machines (>=20 CPUs, e.g. 28-thread workstations)
    # keep medium on both CPU and GPU.
    import multiprocessing
    _logical_cpus = multiprocessing.cpu_count()
    _explicit_model = tx_cfg.get("model")
    if _explicit_model:
        model_id = str(_explicit_model)
        _model_reason = "config_explicit"
    elif _logical_cpus < 20:
        model_id = "small"
        _model_reason = f"cpu_auto_cores={_logical_cpus}"
    else:
        model_id = "medium"
        _model_reason = f"cpu_auto_cores={_logical_cpus}"
    logger.info(
        "[TRANSCRIBE] Model selected=%s reason=%s logical_cpus=%s device=%s",
        model_id, _model_reason, _logical_cpus, device,
    )
    
    # Get GPU config and optimal compute type
    if device == "cuda":
        gpu_config = optimizer.configure_for_transcription(duration_minutes)
        compute_type = gpu_config.compute_type
        logger.info(f"[TRANSCRIBE] Starting on GPU with {compute_type} precision")
    else:
        compute_type = "int8"
        logger.info("[TRANSCRIBE] Starting on CPU")

    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    models_root = _resolve_models_root()
    os.environ.setdefault("HF_HOME", os.environ.get("HF_HOME") or models_root)
    os.environ.setdefault("TORCH_HOME", os.environ.get("TORCH_HOME") or models_root)
    # Prevent faster-whisper / huggingface_hub from making blocking network
    # calls during model loading.  The model is already provisioned locally
    # via ensure_model_cached(); any hub connectivity attempt is a regression
    # risk that can hang for 1600+ seconds on installed follower nodes.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    
    use_fw = True
    if whisper_cli and whisper_model_path and os.path.isfile(str(whisper_cli)) and os.path.isfile(str(whisper_model_path)):
        use_fw = False
    else:
        whisper_cli = None

    fw_model = None
    if use_fw:
        from lib.model_lifecycle import ModelLifecycleManager
        manager = ModelLifecycleManager(cfg)
        
        # Resolve the model name for the registry
        registry_key = f"faster_whisper_{model_id}".replace("-", "_")
        if registry_key not in manager.model_registry:
            found_key = None
            for k in manager.model_registry.keys():
                if model_id.replace("-", "_") in k or k in model_id.replace("-", "_"):
                    found_key = k
                    break
            registry_key = found_key or registry_key

        try:
            from steps.common.config_loader import load_configs
            offline_mode = load_configs({}).get("verification", {}).get("offline_mode", False)
        except Exception:
            offline_mode = False

        from steps.common.model_provisioner import ensure_model_cached
        provision_result = ensure_model_cached(registry_key, offline=offline_mode)
        if provision_result.status in ("offline_missing", "gated_unauthorized", "failed"):
            raise OSError(f"Failed to provision Whisper model: {provision_result.error or 'reason unknown'}")
        
        local_model_path = provision_result.local_path

        def load_fn():
            return _load_fw_model(local_model_path, device, compute_type, duration_minutes)

        def unload_fn():
            _FW_CACHE.clear()

        try:
            model_ctx = manager.load(registry_key, load_fn, unload_fn, target_engine="CTranslate2", device=device)
            model_ctx_holder[0] = model_ctx
            fw_model = model_ctx.__enter__()
        except Exception as e:
            logger.error(f"[TRANSCRIBE] Lifecycle load failed: {e}")
            fw_model = None

    # No transcription backend available
    if fw_model is None and whisper_cli is None:
        logger.warning(
            "[TRANSCRIBE] No transcription backend available model_id=%s device=%s",
            model_id,
            device,
        )
        return {
            "transcript": None,
            "transcript_meta": {
                "status": "model_unavailable",
                "reason": "transcription_backend_unavailable",
                "error": "model_unavailable",
                "engine": "hybrid_whisper",
                "model": model_id,
                "device": "none",
                "attempted_device": device,
                "device_probe": device_probe,
                "used_cli": False,
                "chunk_seconds": chunk_seconds,
                "duration": duration,
            },
        }

    from scripts.config_schema import AudioTranscriptionConfig
    from steps.audio.audio_wsl2_bridge import _apply_post_filter_vocabulary_context, _transcription_projection
    settings = AudioTranscriptionConfig.model_validate(
        {key: tx_cfg[key] for key in ('temperature', 'vocabulary', 'vocabulary_mode') if key in tx_cfg})
    decode_vocab = None if settings.vocabulary_mode == 'post_filter_only' else settings.vocabulary
    started = time.time()
    if whisper_cli:
        from steps.audio_transcribe.whisper_cpp import WhisperCppModel
        from wsl2_audio.transcription_contract import transcribe_file
        model = WhisperCppModel(str(whisper_cli), str(whisper_model_path))
        raw = transcribe_file(model, path, temperature=settings.temperature,
            vocabulary=decode_vocab, language=tx_cfg.get('language'),
            beam_size=int(tx_cfg.get('beam_size', 5)), engine='whisper.cpp')
    else:
        raw = _transcribe_chunk_fw(path, 0., fw_model, settings.temperature,
            vocabulary=decode_vocab, language=tx_cfg.get('language'),
            beam_size=int(tx_cfg.get('beam_size', 5)))
    if raw is None:
        raw = {'status': 'error', 'transcription_status': 'error', 'error': 'transcription_backend_no_result'}
    if settings.vocabulary_mode == 'post_filter_only' and settings.vocabulary is not None:
        raw = _apply_post_filter_vocabulary_context(raw, settings.vocabulary)
    raw.update(device=device, model=model_id)
    projected = _transcription_projection(raw, engine='whisper.cpp' if whisper_cli else 'faster-whisper')
    meta = projected['transcript_meta']
    coverage = (meta.get('transcription_decoding') or {}).get('source_regions') or {}
    meta.update(duration=raw.get('duration_seconds', duration), attempted_device=device,
        device_probe=device_probe, used_cli=bool(whisper_cli), processing_time=time.time()-started,
        chunk_seconds=30., requested_chunk_seconds=chunk_seconds,
        chunks=[{**region, 'status': 'error' if region['outcome'] in ('error', 'not_attempted')
                 else 'ok' if region['outcome']=='text_returned' else 'empty',
                 'reason': region['outcome']} for region in coverage.get('regions', [])])
    if meta['status'] == 'success': meta['status'] = 'ok' if projected['transcript'] else 'empty'
    if wsl_attempt is not None: meta['prior_wsl_attempt'] = wsl_attempt
    if not projected['transcript']: projected['transcript'] = None
    return projected
