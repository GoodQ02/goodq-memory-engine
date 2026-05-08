#!/usr/bin/env python3
"""
GoodQ Audio Processing Script - Full Classification
GPU-accelerated audio analysis with Whisper, Pyannote, and Wav2Vec2
Memory-optimized: Models loaded sequentially with cleanup between steps
"""

import sys
import json
import os
import gc
import logging
import traceback
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Dict, List, Optional

# Core imports
import torch
import torchaudio
import numpy as np

# Whisper for transcription
from faster_whisper import WhisperModel

# Profile semantics (fallback to canonical behavior when steps package is unavailable in WSL context)
try:
    from steps.common.profile_config import (
        log_runtime_profile_state,
        require_gpu,
        resolve_wsl_gpu_config,
    )
except Exception:
    def require_gpu() -> bool:  # type: ignore
        return os.getenv("GOODQ_REQUIRE_GPU", "").strip().lower() in {"1", "true", "yes", "on"}

    def resolve_wsl_gpu_config(gpu_cfg):  # type: ignore
        return dict(gpu_cfg or {})

    def log_runtime_profile_state(*args, **kwargs) -> None:  # type: ignore
        return None

# Pyannote for diarization (optional - requires HF token)
DIARIZATION_IMPORT_ERROR = None
try:
    from pyannote.audio import Pipeline as DiarizationPipeline
    DIARIZATION_AVAILABLE = True
except Exception as exc:
    DIARIZATION_AVAILABLE = False
    DIARIZATION_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

# Transformers for emotion/embeddings
try:
    from transformers import (
        Wav2Vec2ForSequenceClassification,
        Wav2Vec2FeatureExtractor,
        Wav2Vec2Model
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


_DEFAULT_RUNTIME_CONFIG = {
    "gpu": {
        "device": "cuda",
        "compute_type": "float16",
        "memory_fraction": 0.8,
    },
    "models": {
        "whisper": "medium",
        "diarization": "pyannote/speaker-diarization-3.1",
    },
    "diarization": {
        "enabled": True,
    },
    "processing": {
        "language": "en",
        "beam_size": 5,
    },
}

_SPEAKER_SIGNATURE_TARGET_SR = 16000
_SPEAKER_SIGNATURE_MIN_TOTAL_SECONDS = 4.0
_SPEAKER_SIGNATURE_MIN_SEGMENTS = 2
_SPEAKER_SIGNATURE_MIN_SEGMENT_SECONDS = 0.75
_SPEAKER_SIGNATURE_MAX_SEGMENTS = 4


def _deep_merge(base, override):
    for key, value in (override or {}).items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _load_json_dict(path: Path):
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _normalize_runtime_overlay(raw_cfg):
    normalized = {}
    if not isinstance(raw_cfg, dict):
        return normalized

    gpu_cfg = raw_cfg.get("gpu")
    if isinstance(gpu_cfg, dict):
        normalized["gpu"] = dict(gpu_cfg)
    else:
        inline_gpu = {}
        for key in ("device", "compute_type", "memory_fraction"):
            if key in raw_cfg:
                inline_gpu[key] = raw_cfg.get(key)
        if inline_gpu:
            normalized["gpu"] = inline_gpu

    if isinstance(raw_cfg.get("models"), dict):
        normalized["models"] = dict(raw_cfg.get("models") or {})

    whisper_cfg = raw_cfg.get("whisper")
    if isinstance(whisper_cfg, dict):
        whisper_model = whisper_cfg.get("model") or whisper_cfg.get("name")
        if whisper_model:
            normalized.setdefault("models", {})["whisper"] = whisper_model
    elif isinstance(whisper_cfg, str) and whisper_cfg.strip():
        normalized.setdefault("models", {})["whisper"] = whisper_cfg.strip()

    diarization_cfg = raw_cfg.get("diarization")
    if isinstance(diarization_cfg, dict):
        model_name = diarization_cfg.get("model") or diarization_cfg.get("name")
        if model_name:
            normalized.setdefault("models", {})["diarization"] = model_name
        normalized.setdefault("diarization", {}).update(
            {k: v for k, v in diarization_cfg.items() if k not in {"model", "name"}}
        )
    elif isinstance(diarization_cfg, str) and diarization_cfg.strip():
        normalized.setdefault("models", {})["diarization"] = diarization_cfg.strip()

    if isinstance(raw_cfg.get("processing"), dict):
        normalized.setdefault("processing", {}).update(raw_cfg.get("processing") or {})

    for key in ("huggingface_token", "huggingface_token_env"):
        if key in raw_cfg:
            normalized[key] = raw_cfg.get(key)

    return normalized


def _load_runtime_config():
    config = json.loads(json.dumps(_DEFAULT_RUNTIME_CONFIG))
    config_sources = []
    base_dir = Path(__file__).resolve().parent
    for candidate in (base_dir / "config.json", base_dir / "config_wsl2_audio.json"):
        if not candidate.exists():
            continue
        overlay = _normalize_runtime_overlay(_load_json_dict(candidate))
        if overlay:
            _deep_merge(config, overlay)
            config_sources.append(candidate.name)
    config["_sources"] = config_sources
    return config


def _resolve_secret(raw_value, env_key=None):
    if isinstance(env_key, str) and env_key.strip():
        env_value = os.getenv(env_key.strip())
        if env_value:
            return env_value

    if isinstance(raw_value, str):
        value = raw_value.strip()
        if value.startswith("${") and value.endswith("}"):
            ref = value[2:-1].strip()
            if ref:
                return os.getenv(ref)
        return value or None
    return None


def _resolve_hf_cache_dir() -> Optional[str]:
    """Return the canonical HF cache path exported by bootstrap, when present."""
    return os.getenv("HUGGINGFACE_HUB_CACHE") or os.getenv("HF_HUB_CACHE") or None


def _load_pyannote_pipeline(pipeline_cls, model_name: str, token: str, cache_dir: Optional[str] = None):
    """Load pyannote across the 3.x/4.x auth kwarg boundary."""
    kwargs = {"use_auth_token": token}
    if cache_dir:
        kwargs["cache_dir"] = cache_dir
    try:
        return pipeline_cls.from_pretrained(model_name, **kwargs)
    except TypeError as exc:
        message = str(exc)
        if "use_auth_token" not in message or "unexpected keyword" not in message:
            raise
        kwargs.pop("use_auth_token", None)
        kwargs["token"] = token
        return pipeline_cls.from_pretrained(model_name, **kwargs)


def clear_gpu_memory():
    """Clear GPU memory cache and run garbage collection"""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()


def get_gpu_memory_info():
    """Get current GPU memory usage"""
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated(0) / (1024**2)  # MB
        reserved = torch.cuda.memory_reserved(0) / (1024**2)    # MB
        return {"allocated_mb": allocated, "reserved_mb": reserved}
    return {"allocated_mb": 0, "reserved_mb": 0}


def _segment_duration(segment: Dict[str, Any]) -> float:
    try:
        start_val = float(segment.get("start") or 0.0)
    except Exception:
        start_val = 0.0
    try:
        end_val = float(segment.get("end") or start_val)
    except Exception:
        end_val = start_val
    return max(0.0, end_val - start_val)


def _select_speaker_signature_segments(
    diarization_segments: Any,
    *,
    min_total_seconds: float = _SPEAKER_SIGNATURE_MIN_TOTAL_SECONDS,
    min_segments: int = _SPEAKER_SIGNATURE_MIN_SEGMENTS,
    min_segment_seconds: float = _SPEAKER_SIGNATURE_MIN_SEGMENT_SECONDS,
    max_segments: int = _SPEAKER_SIGNATURE_MAX_SEGMENTS,
) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    if not isinstance(diarization_segments, list):
        return []

    for segment in diarization_segments:
        if not isinstance(segment, dict):
            continue
        speaker = segment.get("speaker")
        if not isinstance(speaker, str) or not speaker.strip():
            continue
        duration = _segment_duration(segment)
        if duration < min_segment_seconds:
            continue
        grouped.setdefault(speaker.strip(), []).append(
            {
                "speaker": speaker.strip(),
                "start": float(segment.get("start") or 0.0),
                "end": float(segment.get("end") or 0.0),
                "duration": duration,
            }
        )

    selected_groups: List[Dict[str, Any]] = []
    for speaker, segments in grouped.items():
        ranked = sorted(
            segments,
            key=lambda item: (-float(item.get("duration") or 0.0), float(item.get("start") or 0.0)),
        )
        chosen = ranked[: max(1, int(max_segments))]
        total_seconds = sum(float(item.get("duration") or 0.0) for item in chosen)
        if len(chosen) < int(min_segments) or total_seconds < float(min_total_seconds):
            continue
        selected_groups.append(
            {
                "speaker": speaker,
                "selected_segments": sorted(chosen, key=lambda item: float(item.get("start") or 0.0)),
                "selected_segment_count": len(chosen),
                "available_segment_count": len(segments),
                "voiced_seconds": round(total_seconds, 3),
            }
        )
    return selected_groups


def _slice_waveform_segment(
    waveform: torch.Tensor,
    *,
    start_seconds: float,
    end_seconds: float,
    sample_rate: int,
) -> Optional[torch.Tensor]:
    if not isinstance(waveform, torch.Tensor):
        return None
    safe_start = max(0.0, float(start_seconds or 0.0))
    safe_end = max(safe_start, float(end_seconds or safe_start))
    if safe_end <= safe_start:
        return None
    start_idx = int(round(safe_start * sample_rate))
    end_idx = int(round(safe_end * sample_rate))
    if end_idx <= start_idx:
        return None
    clipped = waveform[..., start_idx:end_idx]
    if clipped.numel() == 0:
        return None
    return clipped.detach().cpu()


def _normalize_embedding_vector(vector: np.ndarray) -> Optional[np.ndarray]:
    if not isinstance(vector, np.ndarray):
        return None
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm <= 1e-8:
        return None
    return vector / norm


def _build_speaker_voice_signatures(
    waveform_16k: torch.Tensor,
    diarization_segments: Any,
    *,
    embed_model: Any,
    embed_extractor: Any,
    device: str,
    sample_rate: int = _SPEAKER_SIGNATURE_TARGET_SR,
) -> Dict[str, Any]:
    selected_groups = _select_speaker_signature_segments(diarization_segments)
    signatures: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    if not selected_groups:
        return {
            "signatures": [],
            "meta": {
                "status": "skipped",
                "reason": "insufficient_diverse_speech",
                "emitted": 0,
                "attempted_speakers": 0,
                "min_voiced_seconds": _SPEAKER_SIGNATURE_MIN_TOTAL_SECONDS,
                "min_segment_count": _SPEAKER_SIGNATURE_MIN_SEGMENTS,
            },
        }

    for group in selected_groups:
        speaker = str(group.get("speaker") or "").strip()
        segment_vectors: List[np.ndarray] = []
        emitted_segments: List[Dict[str, Any]] = []
        for segment in group.get("selected_segments") or []:
            clipped = _slice_waveform_segment(
                waveform_16k,
                start_seconds=float(segment.get("start") or 0.0),
                end_seconds=float(segment.get("end") or 0.0),
                sample_rate=int(sample_rate),
            )
            if clipped is None:
                continue
            inputs = embed_extractor(
                clipped.numpy().flatten(),
                sampling_rate=int(sample_rate),
                return_tensors="pt",
                padding=True,
            )
            inputs = {key: value.to(device) for key, value in inputs.items()}
            with torch.no_grad():
                hidden_state = embed_model(**inputs).last_hidden_state
            pooled = torch.mean(hidden_state, dim=1).detach().cpu().numpy()[0]
            normalized = _normalize_embedding_vector(pooled)
            if normalized is None:
                continue
            segment_vectors.append(normalized)
            emitted_segments.append(
                {
                    "start": float(segment.get("start") or 0.0),
                    "end": float(segment.get("end") or 0.0),
                    "duration": round(float(segment.get("duration") or 0.0), 3),
                }
            )

        if len(segment_vectors) < _SPEAKER_SIGNATURE_MIN_SEGMENTS:
            skipped.append(
                {
                    "speaker": speaker,
                    "reason": "insufficient_embedded_segments",
                    "selected_segment_count": len(emitted_segments),
                    "required_segment_count": _SPEAKER_SIGNATURE_MIN_SEGMENTS,
                }
            )
            continue

        centroid = np.mean(np.stack(segment_vectors, axis=0), axis=0)
        normalized_centroid = _normalize_embedding_vector(centroid)
        if normalized_centroid is None:
            skipped.append(
                {
                    "speaker": speaker,
                    "reason": "invalid_centroid",
                    "selected_segment_count": len(emitted_segments),
                }
            )
            continue

        signatures.append(
            {
                "speaker": speaker,
                "embedding": normalized_centroid.astype(np.float32).tolist(),
                "embedding_dim": int(normalized_centroid.shape[0]),
                "voiced_seconds": float(group.get("voiced_seconds") or 0.0),
                "segment_count": len(emitted_segments),
                "available_segment_count": int(group.get("available_segment_count") or len(emitted_segments)),
                "selected_segments": emitted_segments,
            }
        )

    status = "ok" if signatures else "skipped"
    meta: Dict[str, Any] = {
        "status": status,
        "emitted": len(signatures),
        "attempted_speakers": len(selected_groups),
        "min_voiced_seconds": _SPEAKER_SIGNATURE_MIN_TOTAL_SECONDS,
        "min_segment_count": _SPEAKER_SIGNATURE_MIN_SEGMENTS,
    }
    if skipped:
        meta["skipped"] = skipped
    if status != "ok":
        meta.setdefault("reason", "no_signatures_emitted")
    return {"signatures": signatures, "meta": meta}


def process_audio(audio_file, output_dir):
    """Process audio file with full classification pipeline - Memory optimized"""
    request_uuid = (os.getenv("GOODQ_BRIDGE_REQUEST_UUID") or "").strip()
    runtime_cfg = _load_runtime_config()

    result = {
        "status": "processing",
        "audio_file": str(audio_file),
        "output_dir": str(output_dir),
        "config_sources": runtime_cfg.get("_sources", []),
        "speaker_voice_signatures": [],
        "speaker_voice_signature_meta": {"status": "pending"},
    }
    if request_uuid:
        result["request_uuid"] = request_uuid
    
    # Check file exists
    if not Path(audio_file).exists():
        result["status"] = "error"
        result["error"] = f"Audio file not found: {audio_file}"
        return result
    
    # GPU setup (profile-aware defaults)
    cuda_available = torch.cuda.is_available()
    gpu_profile_cfg = resolve_wsl_gpu_config({
        "device": "cuda" if cuda_available else "cpu",
        "compute_type": "float16" if cuda_available else "int8",
        "memory_fraction": 0.8,
        **dict(runtime_cfg.get("gpu") or {}),
    })
    device = str(gpu_profile_cfg.get("device", "cuda" if cuda_available else "cpu")).lower()
    compute_type = str(
        gpu_profile_cfg.get(
            "compute_type",
            "float16" if device == "cuda" else "int8",
        )
    ).lower()
    if device == "cuda" and not cuda_available:
        if require_gpu():
            raise RuntimeError("GOODQ_REQUIRE_GPU=1 but CUDA is not available in WSL audio process")
        device = "cpu"
    if device != "cuda" and require_gpu():
        raise RuntimeError("GOODQ_REQUIRE_GPU=1 but profile/config resolved WSL audio processing to CPU")
    if device == "cpu" and compute_type in {"float16", "fp16", "mixed", "bfloat16"}:
        compute_type = "int8"

    log_runtime_profile_state(
        logger=logging.getLogger(__name__),
        context="wsl2_audio.process_audio",
        gpu_enabled=(device == "cuda"),
        wsl_enabled=True,
    )

    result["device"] = device
    result["cuda_available"] = cuda_available
    result["gpu_memory_fraction"] = gpu_profile_cfg.get("memory_fraction", 0.8)
    result["whisper_model"] = str((runtime_cfg.get("models", {}) or {}).get("whisper", "medium"))
    result["diarization_model"] = str(
        (runtime_cfg.get("models", {}) or {}).get("diarization", "pyannote/speaker-diarization-3.1")
    )
    result["diarization_enabled"] = bool((runtime_cfg.get("diarization", {}) or {}).get("enabled", True))
    
    if device == "cuda":
        result["gpu_name"] = torch.cuda.get_device_name(0)
        result["gpu_memory_mb"] = torch.cuda.get_device_properties(0).total_memory // (1024**2)
        result["initial_gpu_memory"] = get_gpu_memory_info()
        try:
            torch.cuda.set_per_process_memory_fraction(float(result["gpu_memory_fraction"]), 0)
        except Exception as exc:
            result["gpu_memory_fraction_warning"] = f"{type(exc).__name__}: {exc}"
    
    try:
        # Load audio ONCE and keep in memory (small footprint)
        waveform, sr = torchaudio.load(audio_file)
        result["sample_rate"] = sr
        result["duration_seconds"] = waveform.shape[1] / sr
        result["channels"] = waveform.shape[0]
        
        # Convert to mono if stereo
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        
        # === STEP 1: TRANSCRIPTION (Faster-Whisper) ===
        print("Processing: Transcription...", file=sys.stderr)
        try:
            processing_cfg = dict(runtime_cfg.get("processing") or {})
            transcription_language_raw = str(processing_cfg.get("language", "en") or "").strip()
            transcription_language = None if transcription_language_raw.lower() in {"", "auto", "detect", "none"} else transcription_language_raw
            beam_size = int(processing_cfg.get("beam_size", 5) or 5)
            whisper_model = WhisperModel(result["whisper_model"], device=device, compute_type=compute_type)
            segments, info = whisper_model.transcribe(
                audio_file,
                language=transcription_language,
                beam_size=beam_size,
            )
            
            transcription_text = ""
            word_timestamps = []
            
            for segment in segments:
                transcription_text += segment.text + " "
                word_timestamps.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                    "confidence": float(segment.avg_logprob) if hasattr(segment, 'avg_logprob') else None
                })
            
            result["transcription"] = transcription_text.strip()
            result["word_timestamps"] = word_timestamps
            result["language"] = info.language
            result["language_probability"] = float(info.language_probability)
            result["transcription_status"] = "success"
            
            # Clean up Whisper model
            del whisper_model
            clear_gpu_memory()
            if device == "cuda":
                result["after_whisper_gpu_memory"] = get_gpu_memory_info()
            
        except Exception as e:
            result["transcription_status"] = "error"
            result["transcription_error"] = str(e)
            # Ensure cleanup even on error
            try:
                del whisper_model
            except:
                pass
            clear_gpu_memory()
        
        # === STEP 2: SPEAKER DIARIZATION (Pyannote - optional) ===
        print("Processing: Diarization...", file=sys.stderr)
        if bool(result["diarization_enabled"]) and DIARIZATION_AVAILABLE:
            try:
                # Runtime env overrides must win so tests, local overrides, and
                # temporary credential swaps can take effect without mutating config.
                hf_token = (
                    os.getenv("HF_TOKEN", "")
                    or os.getenv("PYANNOTE_TOKEN", "")
                    or os.getenv("HUGGINGFACE_TOKEN", "")
                    or _resolve_secret(
                        runtime_cfg.get("huggingface_token"),
                        runtime_cfg.get("huggingface_token_env"),
                    )
                )
                if hf_token:
                    os.environ.setdefault("HUGGINGFACE_TOKEN", hf_token)
                    os.environ.setdefault("HF_TOKEN", hf_token)
                    diarization_pipeline = _load_pyannote_pipeline(
                        DiarizationPipeline,
                        result["diarization_model"],
                        hf_token,
                        cache_dir=_resolve_hf_cache_dir(),
                    )
                    diarization_pipeline.to(torch.device(device))
                    
                    diarization_audio = {
                        "waveform": waveform.detach().cpu(),
                        "sample_rate": sr,
                    }
                    diarization_result = diarization_pipeline(diarization_audio)
                    
                    # Handle new pyannote API - DiarizeOutput object
                    # The actual annotation is in the speaker_diarization attribute
                    if hasattr(diarization_result, 'speaker_diarization'):
                        diarization = diarization_result.speaker_diarization
                    else:
                        diarization = diarization_result
                    
                    speakers = []
                    diarization_segments = []
                    for segment, track, speaker in diarization.itertracks(yield_label=True):
                        speakers.append(speaker)
                        diarization_segments.append({
                            "start": float(segment.start),
                            "end": float(segment.end),
                            "speaker": speaker
                        })
                    
                    result["speakers"] = list(set(speakers))
                    result["speaker_count"] = len(set(speakers))
                    result["diarization"] = diarization_segments
                    result["diarization_status"] = "success"
                    
                    # Clean up diarization pipeline
                    del diarization_pipeline
                    del diarization_result
                    del diarization
                    clear_gpu_memory()
                    if device == "cuda":
                        result["after_diarization_gpu_memory"] = get_gpu_memory_info()
                else:
                    result["diarization_status"] = "skipped"
                    result["diarization_note"] = "HUGGINGFACE_TOKEN not set"
            except Exception as e:
                result["diarization_status"] = "error"
                result["diarization_error"] = str(e)
                # Ensure cleanup even on error
                try:
                    del diarization_pipeline
                except:
                    pass
                clear_gpu_memory()
        elif not bool(result["diarization_enabled"]):
            result["diarization_status"] = "skipped"
            result["diarization_note"] = "disabled by runtime config"
        else:
            result["diarization_status"] = "unavailable"
            if DIARIZATION_IMPORT_ERROR:
                result["diarization_note"] = f"pyannote.audio unavailable: {DIARIZATION_IMPORT_ERROR}"
            else:
                result["diarization_note"] = "pyannote.audio not installed"
        
        # === STEP 3: EMOTION CLASSIFICATION (Wav2Vec2 - optional) ===
        # Use CPU for emotion model to save GPU memory
        print("Processing: Emotion classification...", file=sys.stderr)
        emotion_device = "cpu"  # Force CPU to save GPU memory
        if TRANSFORMERS_AVAILABLE:
            try:
                wav2vec_cache_dir = _resolve_hf_cache_dir()
                emotion_model = Wav2Vec2ForSequenceClassification.from_pretrained(
                    "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition",
                    cache_dir=wav2vec_cache_dir,
                )
                emotion_extractor = Wav2Vec2FeatureExtractor.from_pretrained(
                    "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition",
                    cache_dir=wav2vec_cache_dir,
                )
                emotion_model.to(emotion_device)
                
                # Resample if needed
                if sr != 16000:
                    resampler = torchaudio.transforms.Resample(sr, 16000)
                    waveform_16k = resampler(waveform)
                else:
                    waveform_16k = waveform
                
                inputs = emotion_extractor(
                    waveform_16k.numpy().flatten(),
                    sampling_rate=16000,
                    return_tensors="pt",
                    padding=True
                )
                inputs = {k: v.to(emotion_device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    logits = emotion_model(**inputs).logits
                
                emotion_labels = ["angry", "calm", "disgust", "fear", "happy", "neutral", "sad", "surprise"]
                predicted_emotion = emotion_labels[torch.argmax(logits, dim=-1).item()]
                emotion_scores = torch.nn.functional.softmax(logits, dim=-1).cpu().numpy()[0]
                
                result["emotion"] = predicted_emotion
                result["emotion_scores"] = {
                    label: float(score) for label, score in zip(emotion_labels, emotion_scores)
                }
                result["emotion_status"] = "success"
                
                # Clean up emotion model
                del emotion_model
                del emotion_extractor
                clear_gpu_memory()
                if device == "cuda":
                    result["after_emotion_gpu_memory"] = get_gpu_memory_info()
                
            except Exception as e:
                result["emotion_status"] = "error"
                result["emotion_error"] = str(e)
                # Ensure cleanup even on error
                try:
                    del emotion_model
                    del emotion_extractor
                except:
                    pass
                clear_gpu_memory()
        else:
            result["emotion_status"] = "unavailable"
            result["emotion_note"] = "transformers not installed"
        
        # === STEP 4: AUDIO FEATURES ===
        print("Processing: Audio features...", file=sys.stderr)
        try:
            # Energy/Volume
            energy = torch.mean(torch.abs(waveform)).item()
            result["energy"] = float(energy)
            result["volume_db"] = float(20 * np.log10(energy + 1e-10))
            
            # Zero crossing rate
            zcr = torch.sum(torch.diff(torch.sign(waveform)) != 0).item() / waveform.shape[1]
            result["zero_crossing_rate"] = float(zcr)
            
            result["features_status"] = "success"
            
        except Exception as e:
            result["features_status"] = "error"
            result["features_error"] = str(e)
        
        # === STEP 5: EMBEDDINGS (Wav2Vec2 - optional) ===
        print("Processing: Embeddings...", file=sys.stderr)
        if TRANSFORMERS_AVAILABLE:
            try:
                wav2vec_cache_dir = _resolve_hf_cache_dir()
                embed_model = Wav2Vec2Model.from_pretrained(
                    "facebook/wav2vec2-base-960h",
                    cache_dir=wav2vec_cache_dir,
                )
                embed_model.to(device)
                
                if sr != 16000:
                    resampler = torchaudio.transforms.Resample(sr, 16000)
                    waveform_16k = resampler(waveform)
                else:
                    waveform_16k = waveform
                
                embed_extractor = Wav2Vec2FeatureExtractor.from_pretrained(
                    "facebook/wav2vec2-base-960h",
                    cache_dir=wav2vec_cache_dir,
                )
                inputs = embed_extractor(
                    waveform_16k.numpy().flatten(),
                    sampling_rate=16000,
                    return_tensors="pt",
                    padding=True
                )
                inputs = {k: v.to(device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    embeddings = embed_model(**inputs).last_hidden_state
                
                # Mean pooling
                embedding_vector = torch.mean(embeddings, dim=1).cpu().numpy()[0]
                result["embeddings"] = embedding_vector.tolist()
                result["embedding_dim"] = len(embedding_vector)
                result["embeddings_status"] = "success"

                diarization_segments = result.get("diarization")
                if isinstance(diarization_segments, list) and diarization_segments:
                    try:
                        signature_result = _build_speaker_voice_signatures(
                            waveform_16k.detach().cpu(),
                            diarization_segments,
                            embed_model=embed_model,
                            embed_extractor=embed_extractor,
                            device=device,
                            sample_rate=_SPEAKER_SIGNATURE_TARGET_SR,
                        )
                        result["speaker_voice_signatures"] = signature_result.get("signatures", [])
                        result["speaker_voice_signature_meta"] = signature_result.get("meta", {})
                    except Exception as signature_exc:
                        result["speaker_voice_signatures"] = []
                        result["speaker_voice_signature_meta"] = {
                            "status": "error",
                            "error": str(signature_exc),
                        }
                else:
                    result["speaker_voice_signatures"] = []
                    result["speaker_voice_signature_meta"] = {
                        "status": "skipped",
                        "reason": "diarization_unavailable",
                    }
                
                # Clean up embedding model
                del embed_model
                del embed_extractor
                clear_gpu_memory()
                if device == "cuda":
                    result["after_embeddings_gpu_memory"] = get_gpu_memory_info()
                
            except Exception as e:
                result["embeddings_status"] = "error"
                result["embeddings_error"] = str(e)
                result["speaker_voice_signatures"] = []
                result["speaker_voice_signature_meta"] = {
                    "status": "error",
                    "reason": "embedding_step_failed",
                    "error": str(e),
                }
                # Ensure cleanup even on error
                try:
                    del embed_model
                    del embed_extractor
                except:
                    pass
                clear_gpu_memory()
        else:
            result["embeddings_status"] = "unavailable"
            result["embeddings_note"] = "transformers not installed"
            result["speaker_voice_signatures"] = []
            result["speaker_voice_signature_meta"] = {
                "status": "unavailable",
                "reason": "transformers_not_installed",
            }
        
        # Final cleanup
        print("Processing complete. Final cleanup...", file=sys.stderr)
        clear_gpu_memory()
        if device == "cuda":
            result["final_gpu_memory"] = get_gpu_memory_info()
        
        # Final status
        result["status"] = "success"
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
    
    # Write output file
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        output_file = output_path / "result.json"
        
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
    
    return result


def main():
    if len(sys.argv) < 3:
        print(json.dumps({
            "status": "error",
            "error": "Usage: process_audio.py <audio_file> <output_dir>"
        }))
        sys.exit(1)
    
    audio_file = sys.argv[1]
    output_dir = sys.argv[2]

    # Keep stdout reserved for the final machine-readable JSON payload.
    # Third-party libraries occasionally print progress or auth messages to
    # stdout during processing, which would otherwise corrupt the bridge
    # contract.
    with redirect_stdout(sys.stderr):
        result = process_audio(audio_file, output_dir)
    print(json.dumps(result))
    
    if result["status"] != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
