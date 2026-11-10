#!/usr/bin/env python3
"""
GoodQ Audio Processing Script - Full Classification
GPU-accelerated audio analysis with Whisper, Pyannote, Wav2Vec2 emotion, and ECAPA
Memory-optimized: Models loaded sequentially with cleanup between steps
"""

import sys
import json
import os
import gc
import importlib
import logging
import math
import re
import traceback
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Dict, List, Optional

# Core imports
import torch
import numpy as np

try:
    from wsl2_audio import model_cache, speaker_signature, acoustic_events
except ImportError:  # Direct WSL worker execution from its workspace.
    import model_cache
    import speaker_signature
    import acoustic_events


class _LazyTorchaudio:
    """Defer torchaudio import until audio I/O is actually needed."""

    def _module(self):
        try:
            return importlib.import_module("torchaudio")
        except Exception as exc:
            raise RuntimeError(
                "torchaudio is required for WSL audio processing but failed to import. "
                "Verify the torch/torchaudio runtime in the selected environment."
            ) from exc

    def load(self, *args, **kwargs):
        return self._module().load(*args, **kwargs)

    @property
    def transforms(self):
        return self._module().transforms

    @property
    def functional(self):
        return self._module().functional


torchaudio = _LazyTorchaudio()

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
        Wav2Vec2Config,
        Wav2Vec2FeatureExtractor,
        Wav2Vec2Model
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


class _SpeechEmotionModel(torch.nn.Module):
    """The cached ehcalabres head: temporal mean, dense, tanh, output.

    Its classifier.dense/output tensors are not compatible with the generic
    Transformers sequence classifier's projector/classifier forward.
    Reference: the checkpoint's upstream discussion /discussions/12.
    """

    def __init__(self, config):
        super().__init__()
        if getattr(config, "pooling_mode", None) != "mean":
            raise ValueError("Unsupported emotion checkpoint pooling_mode")
        self.config = config
        self.wav2vec2 = Wav2Vec2Model(config)
        self.classifier = torch.nn.Module()
        self.classifier.dense = torch.nn.Linear(config.hidden_size, config.hidden_size)
        self.classifier.output = torch.nn.Linear(config.hidden_size, config.num_labels)

    def forward(self, **inputs):
        from types import SimpleNamespace

        hidden = self.wav2vec2(**inputs).last_hidden_state.mean(dim=1)
        logits = self.classifier.output(torch.tanh(self.classifier.dense(hidden)))
        return SimpleNamespace(logits=logits)


def _load_trained_wav2vec(repo, *, cache_dir, is_offline, emotion=False, revision=None):
    """Load all inference tensors strictly, including legacy weight-norm keys.

    Transformers 4.43's from_pretrained can initialize positional convolution
    weights before PyTorch migrates the old weight_g/weight_v names. Loading the
    complete state directly avoids that silent replacement. Never modify cache
    files or accept missing learned inference parameters.
    """
    from transformers.utils.hub import cached_file
    from safetensors.torch import load_file

    def resolve(name, *, optional=False):
        kwargs = dict(cache_dir=cache_dir, revision=revision,
                      _raise_exceptions_for_missing_entries=not optional)
        try:
            return cached_file(repo, name, local_files_only=True, **kwargs)
        except OSError:
            if is_offline:
                raise
            return cached_file(repo, name, local_files_only=False, **kwargs)

    config_path = resolve("config.json")
    config = Wav2Vec2Config.from_pretrained(str(Path(config_path).parent), local_files_only=True)
    # Mask embeddings are training-only; evaluation never applies SpecAugment.
    config.mask_time_prob = 0.0
    config.mask_feature_prob = 0.0
    config.apply_spec_augment = False
    model = _SpeechEmotionModel(config) if emotion else Wav2Vec2Model(config)
    weights_path = resolve("model.safetensors", optional=True)
    if weights_path:
        state = load_file(weights_path, device="cpu")
    else:
        weights_path = resolve("pytorch_model.bin")
        state = torch.load(weights_path, map_location="cpu", weights_only=True)

    ignored = []
    for key in ("wav2vec2.masked_spec_embed", "masked_spec_embed"):
        if key in state:
            ignored.append(key)
            del state[key]
    if not emotion:
        # These are the source checkpoint's CTC output tensors, not features.
        for key in ("lm_head.weight", "lm_head.bias"):
            if key in state:
                ignored.append(key)
                del state[key]
        state = {key.removeprefix("wav2vec2."): value for key, value in state.items()}

    expected_keys = set(model.state_dict())
    remapped = {}
    for key in list(state):
        target = key.replace(".weight_g", ".parametrizations.weight.original0").replace(
            ".weight_v", ".parametrizations.weight.original1")
        if target != key and target in expected_keys:
            if target in state:
                raise ValueError(f"Duplicate legacy/current checkpoint tensor: {target}")
            state[target] = state.pop(key)
            remapped[key] = target
    model.load_state_dict(state, strict=True)
    model.eval()
    snapshot_revision = Path(weights_path).parent.name
    return model, {
        "repo": repo, "revision": revision or snapshot_revision,
        "weights_path": str(weights_path), "strict": True,
        "missing_inference_keys": [], "ignored_non_inference_keys": ignored,
        "legacy_key_mapping": remapped,
    }


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
        "temperature": 0.0,
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
    cache_dir = os.getenv("HUGGINGFACE_HUB_CACHE") or os.getenv("HF_HUB_CACHE") or None
    if cache_dir:
        os.environ.setdefault("HF_HUB_CACHE", cache_dir)
        os.environ.setdefault("PYANNOTE_CACHE", cache_dir)
    return cache_dir


def _load_pyannote_pipeline(pipeline_cls, model_name: str, token: str, cache_dir: Optional[str] = None, is_offline: bool = False):
    """Delegate PyAnnote compatibility handling to the shared cache authority."""
    return model_cache.load_pyannote_pipeline(
        pipeline_cls, model_name, token, cache_dir=cache_dir, is_offline=is_offline
    )


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
    excluded_segments: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    if not isinstance(diarization_segments, list):
        return []

    valid_turns = []
    for turn in diarization_segments:
        if not isinstance(turn, dict) or not isinstance(turn.get("speaker"), str) or not turn["speaker"].strip():
            continue
        try:
            start, end = float(turn["start"]), float(turn["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(start) and math.isfinite(end) and 0 <= start < end:
            valid_turns.append({**turn, "start": start, "end": end})
    for segment in valid_turns:
        if not isinstance(segment, dict):
            continue
        speaker = segment.get("speaker")
        if not isinstance(speaker, str) or not speaker.strip():
            continue
        duration = _segment_duration(segment)
        overlaps = [other for other in valid_turns
                    if other["speaker"].strip() != speaker.strip()
                    and float(other["start"]) < float(segment["end"])
                    and float(segment["start"]) < float(other["end"])]
        if overlaps:
            if excluded_segments is not None:
                excluded_segments.append({"speaker": speaker.strip(),
                    "start": float(segment["start"]), "end": float(segment["end"]),
                    "reason": "overlapping_speaker_turn",
                    "overlapping_speakers": sorted({s["speaker"].strip() for s in overlaps})})
            continue
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
    waveform_16k: torch.Tensor, diarization_segments: Any, *,
    embed_model: Any, device: str,
    sample_rate: int = _SPEAKER_SIGNATURE_TARGET_SR,
    speech_intervals=None,
) -> Dict[str, Any]:
    if sample_rate != 16000:
        raise ValueError("ECAPA requires 16kHz audio")
    signatures = []
    excluded = []
    for group in _select_speaker_signature_segments(diarization_segments, excluded_segments=excluded):
        pieces, spans = [], []
        segments = group["selected_segments"]
        if speech_intervals is not None:
            segments = [{**segment, "start": max(segment["start"], speech["start"]),
                         "end": min(segment["end"], speech["end"])}
                        for segment in segments for speech in speech_intervals
                        if speech.get("speaker") == group["speaker"]
                        and max(segment["start"], speech["start"]) < min(segment["end"], speech["end"])]
        for segment in segments:
            piece = _slice_waveform_segment(
                waveform_16k, start_seconds=segment["start"],
                end_seconds=segment["end"], sample_rate=sample_rate)
            if piece is None or piece.shape[-1] / sample_rate < _SPEAKER_SIGNATURE_MIN_SEGMENT_SECONDS:
                continue
            pieces.append(piece.mean(dim=0, keepdim=True) if piece.ndim == 2 else piece.unsqueeze(0))
            spans.append({**segment, "end": min(segment["end"], waveform_16k.shape[-1] / sample_rate),
                          "duration": piece.shape[-1] / sample_rate})
        seconds = sum(p.shape[-1] for p in pieces) / sample_rate
        if len(pieces) < _SPEAKER_SIGNATURE_MIN_SEGMENTS or seconds < _SPEAKER_SIGNATURE_MIN_TOTAL_SECONDS:
            continue
        with torch.inference_mode():
            vector = embed_model.encode_batch(torch.cat(pieces, dim=-1).to(device)).flatten().detach().cpu().numpy()
        normalized = _normalize_embedding_vector(vector)
        if normalized is None or normalized.size != speaker_signature.DIMENSION:
            raise ValueError("Invalid ECAPA speaker embedding")
        signatures.append({
            "speaker": group["speaker"], "embedding": normalized.astype(np.float32).tolist(),
            "embedding_dim": speaker_signature.DIMENSION, **speaker_signature.metadata(),
            "voiced_seconds": round(seconds, 3), "segment_count": len(spans),
            "available_segment_count": group.get("available_segment_count", len(spans)),
            "selected_segments": spans,
            "excluded_segments": [s for s in excluded if s["speaker"] == group["speaker"]],
          "admission_policy": "exclude_overlapping_turns_v1",
        })
    return {"signatures": signatures, "meta": {
        "status": "ok" if signatures else "skipped", "emitted": len(signatures),
        "reason": None if signatures else ("insufficient_unambiguous_speech" if excluded else "insufficient_diverse_speech"),
        "excluded_segments": excluded,
        "admission_policy": "exclude_overlapping_turns_v1",
        **speaker_signature.metadata(),
        "min_voiced_seconds": _SPEAKER_SIGNATURE_MIN_TOTAL_SECONDS,
        "min_segment_count": _SPEAKER_SIGNATURE_MIN_SEGMENTS,
        "purity": "diarization_hypothesis_not_confirmed_identity",
    }}


def _collapsed_return_flags(segmentations, hard_clusters, frames, audio_seconds):
    """Review-only A-B-A evidence; never modifies segmentation or clustering.

    Local slots are window-specific, not identities. Silence is retained as gaps;
    overlapping speech breaks a sequence. This rule is not speaker-purity proof.
    """
    data = segmentations.data
    if not np.isin(data, [0, 1]).all():
        raise ValueError("review rule requires decoded binary local activity")
    flags = []
    for chunk, activity in enumerate(data):
        count = activity.sum(axis=1)
        labels = np.where(count == 1, activity.argmax(axis=1), np.where(count == 0, -1, -2))
        edges = np.r_[0, np.flatnonzero(np.diff(labels) != 0) + 1, len(labels)]
        window = segmentations.sliding_window[chunk]
        origin = window.start + frames.start + frames.duration / 2 - frames.step / 2
        runs = [(int(labels[a]), max(0.0, origin + a * frames.step),
                 min(audio_seconds, origin + b * frames.step))
                for a, b in zip(edges[:-1], edges[1:])
                if labels[a] != -1 and origin + a * frames.step < audio_seconds]
        for left, middle, right in zip(runs, runs[1:], runs[2:]):
            outer, inner, returned = left[0], middle[0], right[0]
            if min(outer, inner, returned) < 0 or outer != returned or outer == inner:
                continue
            cluster = int(hard_clusters[chunk, outer])
            if cluster < 0 or cluster != int(hard_clusters[chunk, inner]):
                continue
            flags.append({"start": float(middle[1]), "end": float(middle[2]),
                          "window_start": float(window.start), "window_end": float(window.end),
                          "local_slots": [outer, inner, returned], "final_cluster": cluster,
                          "left_gap": float(middle[1] - left[2]),
                          "right_gap": float(right[1] - middle[2]),
                          "status": "unreviewed", "identity_claim": False})
    return flags


def _local_overlap_evidence(segmentations, frames, audio_seconds):
    """Retain binary local overlap before count averaging or speaker clustering.

    Local slots are window-specific model outputs, never person identities.
    A positive window remains exclusion evidence when other windows disagree.
    """
    data = np.asarray(segmentations.data)
    if data.ndim != 3 or not data.size or not np.isfinite(data).all() or not np.isin(data, [0., 1.]).all():
        raise ValueError("Local overlap requires finite binary segmentation outputs")
    if (not all(math.isfinite(x) for x in (frames.start, frames.duration, frames.step, audio_seconds))
            or frames.duration <= 0 or frames.step <= 0 or audio_seconds <= 0):
        raise ValueError("Invalid local overlap frame geometry")
    observations = []
    for chunk, values in enumerate(data):
        window = segmentations.sliding_window[chunk]
        if not math.isfinite(window.start) or not math.isfinite(window.end):
            raise ValueError("Invalid local overlap window geometry")
        active = values.sum(axis=-1) >= 2
        edges = np.flatnonzero(np.diff(np.r_[False, active, False])).reshape(-1, 2)
        origin = window.start + frames.start + frames.duration / 2 - frames.step / 2
        for first, last in edges:
            start, end = max(0., origin + first * frames.step), min(audio_seconds, origin + last * frames.step)
            if start < end:
                observations.append({"start": float(start), "end": float(end),
                    "window_start": float(window.start), "window_end": float(window.end)})
    intervals = []
    for row in sorted(observations, key=lambda r: (r["start"], r["end"])):
        if intervals and row["start"] <= intervals[-1]["end"] + 1e-9:
            intervals[-1]["end"] = max(intervals[-1]["end"], row["end"])
        else:
            intervals.append({"start": row["start"], "end": row["end"]})
    return {"status": "ok", "policy": "local_segmentation_overlap_v1",
        "timebase": "input_audio_seconds", "intervals": intervals, "observations": observations,
        "frame_step": float(frames.step), "review_status": "unreviewed", "identity_claim": False,
        "qualification": "model_observations_not_verified_overlap_boundaries"}


def _empty_speaker_observation(output, observed, frames, audio_seconds):
    """Qualify the pinned diarizer's early return from actual zero-activity hooks.

    An empty annotation alone is not an assessed recording. Require intact,
    finite segmentation/count arrays covering the input before accepting it.
    """
    annotation = getattr(output, 'speaker_diarization', output)
    if next(annotation.itertracks(yield_label=True), None) is not None:
        raise ValueError('Early speaker return is not empty')
    segments, count = observed['segmentation'], observed['speaker_counting']
    local = _local_overlap_evidence(segments, frames, audio_seconds)
    data = np.asarray(count.data)
    if (np.any(segments.data) or data.ndim != 2 or data.shape[1] != 1 or not data.size
            or not np.isfinite(data).all() or np.any(data)):
        raise ValueError('Empty speaker return requires finite zero activity and counts')
    window = count.sliding_window
    if (not all(math.isfinite(x) for x in (window.start, window.duration, window.step))
            or not 0 < window.step <= window.duration
            or window[0].start > 1e-9 or window[len(data)-1].end < audio_seconds-1e-9):
        raise ValueError('Empty speaker count does not cover the input')
    cursor = 0.
    frame_end = frames.start + (segments.data.shape[1]-1)*frames.step + frames.duration
    for chunk in range(segments.data.shape[0]):
        window = segments.sliding_window[chunk]
        # Validate the full analysis windows, including the final sub-frame
        # remainder. This does not extend any positive event/speaker interval.
        if (window.start > cursor+1e-9 or window.end <= window.start
                or not 0 <= frames.start <= frames.step
                or not -1e-9 <= window.end-window.start-frame_end < frames.step+1e-9):
            raise ValueError('Empty local activity has incomplete analysis windows')
        cursor = max(cursor, window.end)
    if cursor < audio_seconds-1e-9:
        raise ValueError('Empty local activity does not cover the input')
    local['reason'] = 'completed_no_speakers'
    proof = {'basis': 'finite_zero_local_activity_and_speaker_counts',
             'segmentation_shape': list(segments.data.shape), 'count_frames': len(data),
             'assessed_seconds': [0., audio_seconds]}
    return local, proof


def _diarize_with_review(pipeline, audio, *, overlap_evidence=None, observe_empty=False):
    """Observe the installed reconstruction seam once, restoring it on all exits."""
    review = {"rule": "collapsed_local_return_v1", "status": "unavailable", "flags": []}
    original = getattr(pipeline, "reconstruct", None)
    if overlap_evidence is not None:
        overlap_evidence.update(status="unavailable", policy="local_segmentation_overlap_v1",
                                reason="no_reconstruction_evidence", intervals=[])
    observed_overlap = False
    try:
        frames = pipeline._segmentation.model.receptive_field
    except AttributeError:
        frames = None
    if not callable(original) or frames is None:
        review["reason"] = "local_reconstruction_evidence_unavailable"
        return pipeline(audio), review
    had_override = "reconstruct" in vars(pipeline)
    previous = vars(pipeline).get("reconstruct")
    observed = {}

    def hook(name, artifact=None, **kwargs):
        if name in ('segmentation', 'speaker_counting') and artifact is not None:
            observed[name] = artifact

    def observe(segmentations, hard_clusters, count):
        nonlocal observed_overlap
        if overlap_evidence is not None and not observed_overlap:
            observed_overlap = True
            try:
                overlap_evidence.clear()
                overlap_evidence.update(_local_overlap_evidence(segmentations, frames,
                    audio["waveform"].shape[-1] / audio["sample_rate"]))
            except Exception as exc:
                overlap_evidence.update(status="error", policy="local_segmentation_overlap_v1",
                    reason=model_cache.redact_sensitive_info(str(exc)), intervals=[])
                logging.getLogger(__name__).warning("Local overlap evidence unavailable: %s", exc)
        output = original(segmentations, hard_clusters, count)
        try:
            review["flags"] = _collapsed_return_flags(
                segmentations, hard_clusters, frames,
                audio["waveform"].shape[-1] / audio["sample_rate"])
            review["status"] = "ok"
        except Exception as exc:
            logging.getLogger(__name__).warning("Speaker-change review evidence unavailable: %s", exc)
            review.update(status="error", reason=str(exc), flags=[])
        return output

    pipeline.reconstruct = observe
    try:
        # Only the pinned recording adapter opts into the supported hook API;
        # older callers retain their existing reconstruction-only contract.
        output = pipeline(audio, hook=hook) if observe_empty else pipeline(audio)
        if observe_empty and review['status'] == 'unavailable':
            try:
                local, proof = _empty_speaker_observation(output, observed, frames,
                    audio['waveform'].shape[-1] / audio['sample_rate'])
                if overlap_evidence is not None:
                    overlap_evidence.clear()
                    overlap_evidence.update(local)
                review.update(status='ok', reason='completed_no_speakers', observation=proof)
            except Exception as exc:
                review.update(status='unavailable', reason='empty_speaker_evidence_unqualified',
                              error=model_cache.redact_sensitive_info(str(exc)))
        if review["status"] == "unavailable":
            review.setdefault("reason", "no_reconstruction_evidence")
        return output, review
    finally:
        if had_override:
            pipeline.reconstruct = previous
        else:
            del pipeline.reconstruct


# One policy is shared with local and compatibility transcription callers.
try:
    from .transcription_contract import (_recover_word_timing, _bound_transcript_segments_to_audio, _filter_no_speech_segments, _normalize_transcription_vocabulary, _source_speech_regions, _transcription_temperature, _resolved_transcription_options, _transcription_language_evidence, _transcribe_source_regions as _transcribe_source_regions_core)
except ImportError:
    from transcription_contract import (_recover_word_timing, _bound_transcript_segments_to_audio, _filter_no_speech_segments, _normalize_transcription_vocabulary, _source_speech_regions, _transcription_temperature, _resolved_transcription_options, _transcription_language_evidence, _transcribe_source_regions as _transcribe_source_regions_core)


def _transcribe_source_regions(model, audio, *, language, beam_size, temperature,
                               context_options, coverage, partial_segments=None):
    return _transcribe_source_regions_core(model, audio, language=language,
        beam_size=beam_size, temperature=temperature, context_options=context_options,
        coverage=coverage, region_detector=_source_speech_regions, partial_segments=partial_segments)


def _diarization_outcome(diarization_segments: list[dict[str, Any]]) -> tuple[str, Optional[str]]:
    """Make a clean zero-track result visible instead of calling it success."""
    if diarization_segments:
        return "success", None
    return "completed_no_speakers", "diarization completed without emitted speaker tracks"






def _bound_diarization_segments_to_audio(
    raw_segments: Any,
    *,
    duration_seconds: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Keep diarization turn timestamps within the waveform actually processed.

    Pyannote sliding windows can emit trailing turns slightly beyond the end of
    the input waveform due to chunk padding. Clip overlapping turns to
    [0.0, duration_seconds] and drop turns that start at or after duration_seconds.
    """
    duration = max(0.0, float(duration_seconds))
    normalized: list[dict[str, Any]] = []
    clipped_count = 0
    dropped_count = 0

    for raw in raw_segments if isinstance(raw_segments, list) else []:
        if not isinstance(raw, dict):
            dropped_count += 1
            continue
        try:
            start = float(raw.get("start"))
            end = float(raw.get("end"))
        except (TypeError, ValueError):
            dropped_count += 1
            continue
        if not (math.isfinite(start) and math.isfinite(end)):
            dropped_count += 1
            continue

        bounded_start = min(duration, max(0.0, start))
        bounded_end = min(duration, max(0.0, end))
        if bounded_end <= bounded_start:
            dropped_count += 1
            continue
        if bounded_start != start or bounded_end != end:
            clipped_count += 1
        speaker = str(raw.get("speaker") or "UNKNOWN").strip() or "UNKNOWN"
        normalized.append({
            "start": bounded_start,
            "end": bounded_end,
            "speaker": speaker,
        })

    return normalized, {
        "status": "bounded" if clipped_count or dropped_count else "within_audio_bounds",
        "input_duration_seconds": duration,
        "clipped_segment_count": clipped_count,
        "dropped_segment_count": dropped_count,
    }














def _detect_additional_overlap(waveform, sample_rate, model_path, device):
    """Optional, local-only Nemotron exclusion evidence; never speaker identity.

    This bounded candidate supports isolated inputs up to 300 seconds. The native
    model carries its speaker cache across internal chunks; no external slicing
    or speaker-label reconciliation is introduced here.
    The caller keeps the original speech gate and fails closed if it is enabled
    but unavailable. No threshold tuning, audio separation or ASR substitution.
    """
    import hashlib
    from transformers import AutoModelForAudioFrameClassification, AutoProcessor

    if not isinstance(model_path, str) or not model_path.strip():
        raise ValueError("Additional overlap model must be an existing local directory")
    path = Path(model_path)
    if not path.is_dir():
        raise ValueError("Additional overlap model must be an existing local directory")
    weights_hash = hashlib.sha256((path / "model.safetensors").read_bytes()).hexdigest()
    if weights_hash != "c074d86335b3b794f8fa5edc25594558f128bdb3914d27806a3a5a2e44963cb6":
        raise ValueError("Additional overlap model does not match the evaluated Nemotron weights")
    duration = waveform.shape[-1] / sample_rate
    if not 0 < duration <= 300:
        raise ValueError("Additional overlap candidate supports only isolated inputs up to 300 seconds")
    audio = waveform.detach().cpu().mean(dim=0)
    if sample_rate != 16000:
        audio = torchaudio.functional.resample(audio, sample_rate, 16000)
    model = processor = inputs = logits = None
    try:
        model, loading = AutoModelForAudioFrameClassification.from_pretrained(
            path, local_files_only=True, trust_remote_code=False, dtype=torch.float32, output_loading_info=True)
        if any(loading.get(key) for key in ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")):
            raise ValueError("Additional overlap checkpoint did not load strictly")
        if model.config.model_type != "nemotron3_diarization":
            raise ValueError("Unsupported additional overlap architecture")
        model.to(device).eval()
        processor = AutoProcessor.from_pretrained(path, local_files_only=True, trust_remote_code=False)
        inputs = processor(audio.numpy(), sampling_rate=16000).to(device, dtype=torch.float32)
        with torch.inference_mode():
            logits = model(**inputs).logits
        if logits.ndim != 3 or logits.shape[0] != 1 or logits.shape[-1] < 2 or not torch.isfinite(logits).all():
            raise ValueError("Invalid additional overlap logits")
        mask = inputs.attention_mask.bool()
        if tuple(mask.shape) != tuple(logits.shape[:2]):
            raise ValueError("Additional overlap frame mask does not match logits")
        step = processor.feature_extractor.hop_length / processor.feature_extractor.sampling_rate
        if not math.isfinite(step) or step != .01:
            raise ValueError("Unexpected additional overlap frame timebase")
        active = (((logits.sigmoid() > .5).sum(dim=-1) >= 2) & mask)[0].cpu().numpy()
        intervals = []
        for i, value in enumerate(active):
            start, end = i * step, min((i + 1) * step, duration)
            if not value or end <= start:
                continue
            if intervals and abs(intervals[-1]["end"] - start) < 1e-9:
                intervals[-1]["end"] = end
            else:
                intervals.append({"start": start, "end": end})
        return {"status": "ok", "policy": "nemotron3_overlap_exclusion_v1",
            "model": "nvidia/Nemotron-3-Diarization", "weights_sha256": weights_hash,
            "revision": "f667ed73aee57d40cc39428eb768b4fd87a0a29e",
            "timebase": "input_audio_seconds", "threshold": .5, "frame_step": step,
            "dtype": "float32", "intervals": intervals, "review_status": "unreviewed",
            "processing_mode": "native_offline_chunked", "max_input_seconds": 300,
            "identity_claim": False, "qualification": "additional_exclusion_only_not_speech_purity_certification"}
    finally:
        del model, processor, inputs, logits
        clear_gpu_memory()


def process_audio(audio_file, output_dir, *, transcription_vocabulary=None, transcription_temperature=None):
    """Process audio file with full classification pipeline - Memory optimized"""
    request_uuid = (os.getenv("GOODQ_BRIDGE_REQUEST_UUID") or "").strip()
    runtime_cfg = _load_runtime_config()
    

    is_offline = model_cache.is_offline_mode()

    result = {
        "status": "processing",
        "audio_file": str(audio_file),
        "output_dir": str(output_dir),
        "config_sources": runtime_cfg.get("_sources", []),
        "speaker_voice_signatures": [],
        "speaker_voice_signature_meta": {"status": "pending"},
        "overlap_detection": {"status": "unavailable", "reason": "diarization_not_run", "intervals": []},
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
    mps_available = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    
    env_device = os.getenv("GOODQ_DEVICE")
    gpu_profile_cfg = resolve_wsl_gpu_config({
        "device": env_device.lower() if env_device else ("cuda" if cuda_available else ("mps" if mps_available else "cpu")),
        "compute_type": "float16" if cuda_available else "int8",
        "memory_fraction": 0.8,
        **dict(runtime_cfg.get("gpu") or {}),
    })
    device = str(gpu_profile_cfg.get("device", "cuda" if cuda_available else ("mps" if mps_available else "cpu"))).lower()
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
    elif device == "mps" and not mps_available:
        device = "cpu"
        
    is_gpu = device in {"cuda", "mps"}
    if not is_gpu and require_gpu():
        raise RuntimeError(f"GOODQ_REQUIRE_GPU=1 but profile/config resolved WSL audio processing to CPU ({device})")
        
    if device in {"cpu", "mps"} and compute_type in {"float16", "fp16", "mixed", "bfloat16"}:
        compute_type = "int8" if device == "cpu" else "float32"

    log_runtime_profile_state(
        logger=logging.getLogger(__name__),
        context="wsl2_audio.process_audio",
        gpu_enabled=is_gpu,
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
        partial_segments = []
        try:
            vocabulary = _normalize_transcription_vocabulary(transcription_vocabulary)
            result["transcription_context"] = {"status": "applied" if vocabulary else "not_supplied",
                "source": "request_config", "kind": "vocabulary_hints", "words": vocabulary,
                "identity_claim": False}
            context_options = {"hotwords": ", ".join(vocabulary)} if vocabulary else {}
            processing_cfg = dict(runtime_cfg.get("processing") or {})
            temperature = _transcription_temperature(
                processing_cfg.get("temperature", 0.0)
                if transcription_temperature is None else transcription_temperature)
            transcription_language_raw = str(processing_cfg.get("language", "en") or "").strip()
            transcription_language = None if transcription_language_raw.lower() in {"", "auto", "detect", "none"} else transcription_language_raw
            beam_size = int(processing_cfg.get("beam_size", 5) or 5)
            result['transcription_decoding'] = {
                'policy': 'single_temperature_v1', 'temperature': temperature,
                'source': 'worker_config' if transcription_temperature is None else 'request_config',
                'sampling_enabled': temperature > 0, 'temperature_fallback': False,
                'beam_size': beam_size, 'primary': None, 'timing_retry': None,
            }
            whisper_device = "cpu" if device == "mps" else device
            whisper_compute = "int8" if whisper_device == "cpu" and compute_type not in {"float32", "float64"} else compute_type
            
            if is_offline and not model_cache.check_whisper_cache(result["whisper_model"]):
                raise OSError(
                    f"Offline mode: Faster-Whisper model '{result['whisper_model']}' is missing from local cache.\n"
                    "Status: Non-gated.\n"
                    "Requirements: No Hugging Face token or license terms required.\n"
                    "Approved Provisioning Command: python3 scripts/install_pipeline_wsl.py --download-whisper"
                )
                
            whisper_model = WhisperModel(result["whisper_model"], device=whisper_device, compute_type=whisper_compute, local_files_only=is_offline)
            asr_waveform = waveform if sr == 16000 else torchaudio.functional.resample(waveform, sr, 16000)
            asr_audio = asr_waveform.squeeze(0).detach().cpu().numpy().astype(np.float32, copy=False)
            source_coverage = result['transcription_decoding']['source_regions'] = {}
            word_timestamps, info, transcript_timing, result['transcription_quality'] = _transcribe_source_regions(
                whisper_model, asr_audio, language=transcription_language, beam_size=beam_size,
                temperature=temperature, context_options=context_options, coverage=source_coverage,
                partial_segments=partial_segments)
            result['transcription_decoding']['primary'] = _resolved_transcription_options(info)
            result['transcription_decoding']['language'] = _transcription_language_evidence(info, transcription_language)
            result['transcription_decoding']['timing_retry'] = info.timing_retry_options
            transcription_text = " ".join(
                str(segment.get("text") or "").strip()
                for segment in word_timestamps
                if str(segment.get("text") or "").strip()
            )
            
            result["transcription"] = transcription_text
            result["segments"] = word_timestamps
            result["word_timestamps"] = [word for segment in word_timestamps
                                         for word in segment.get("words", [])]
            result["word_alignment"] = {
                "method": "whisper_cross_attention_dtw",
                "timebase": "input_audio_seconds",
                "review_status": "unreviewed",
                "words": result["word_timestamps"],
                "status": "available" if result["word_timestamps"] else "no_word_alignment",
            }
            result["transcription_timing"] = transcript_timing
            result["language"] = info.language
            result["language_probability"] = result['transcription_decoding']['language']['detection_probability']
            result["transcription_status"] = "success"
            # An empty decoded string alone cannot establish absent speech.
            # Keep the completed VAD measurement, including on non-speech input.
            input_seconds = getattr(info, "duration", None)
            speech_seconds = getattr(info, "duration_after_vad", None)
            if (isinstance(input_seconds, (int, float)) and not isinstance(input_seconds, bool)
                    and isinstance(speech_seconds, (int, float)) and not isinstance(speech_seconds, bool)
                    and math.isfinite(input_seconds) and math.isfinite(speech_seconds)
                    and 0 <= speech_seconds <= input_seconds and input_seconds > 0):
                result["speech_detection"] = {
                    "status": "completed", "method": "silero_vad",
                    "input_duration_seconds": input_seconds,
                    "speech_duration_seconds": speech_seconds,
                }
            
            # Clean up Whisper model
            del whisper_model
            clear_gpu_memory()
            if device == "cuda":
                result["after_whisper_gpu_memory"] = get_gpu_memory_info()
            
        except Exception as e:
            result["transcription_status"] = "error"
            result["transcription_error"] = model_cache.redact_sensitive_info(str(e))
            # A later decoder failure must not erase completed source regions.
            # The failed coverage/status remains explicit, including in offline receipts.
            result['segments'] = partial_segments
            result['transcription'] = ' '.join(str(s.get('text') or '').strip()
                for s in partial_segments if str(s.get('text') or '').strip())
            result['word_timestamps'] = [w for s in partial_segments for w in s.get('words', [])]
            result['word_alignment'] = {
                'method': 'whisper_cross_attention_dtw', 'timebase': 'input_audio_seconds',
                'review_status': 'unreviewed', 'words': result['word_timestamps'],
                'status': 'available' if result['word_timestamps'] else 'no_word_alignment'}
            # Ensure cleanup even on error
            try:
                del whisper_model
            except:
                pass
            clear_gpu_memory()
            if is_offline:
                raise
        
        # Only completed transcription evidence can make speech enrichments
        # inapplicable. Empty/failed transcription alone leaves them independent.
        detection = result.get("speech_detection") or {}
        quality = result.get("transcription_quality") or {}
        no_speech = (
            result.get("transcription_status") == "success"
            and not result.get("transcription_error") and not result.get("transcription", "").strip()
            and ((detection.get("status") == "completed" and detection.get("speech_duration_seconds") == 0)
                 or (quality.get("status") == "completed" and quality.get("decoded_segment_count", 0) > 0
                     and (quality.get("scope") != "per_source_region"
                          or quality.get("whole_input_no_speech_supported") is True)
                     and quality.get("accepted_segment_count") == 0
                     and len(quality.get("rejected_segments", [])) == quality["decoded_segment_count"]))
        )

        # === STEP 2: SPEAKER DIARIZATION (Pyannote - optional) ===
        print("Processing: Diarization...", file=sys.stderr)
        if bool(result["diarization_enabled"]) and no_speech:
            result.update({"diarization_status": "not_applicable", "diarization_note": "no_speech_detected",
                           "speakers": [], "speaker_count": 0, "diarization": [],
                           "overlap_detection": {"status": "not_applicable", "reason": "no_speech_detected", "intervals": []},
                           "speaker_change_review": {"status": "not_applicable", "reason": "no_speech_detected"}})
        elif bool(result["diarization_enabled"]) and DIARIZATION_AVAILABLE:
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
                if is_offline and not model_cache.check_pyannote_cache(result["diarization_model"]):
                    raise OSError(
                        f"Offline mode: PyAnnote diarization model '{result['diarization_model']}' is missing from local cache.\n"
                        "Status: Gated.\n"
                        "Requirements: Requires Hugging Face account licensing approval and access token (HF_TOKEN or PYANNOTE_TOKEN).\n"
                        "Approved Provisioning Command: python3 scripts/install_pipeline_wsl.py --download-pyannote"
                    )
                    
                if hf_token or is_offline:
                    os.environ.setdefault("HUGGINGFACE_TOKEN", hf_token or "")
                    os.environ.setdefault("HF_TOKEN", hf_token or "")
                    diarization_pipeline = _load_pyannote_pipeline(
                        DiarizationPipeline,
                        result["diarization_model"],
                        hf_token or "",
                        cache_dir=_resolve_hf_cache_dir(),
                        is_offline=is_offline,
                    )
                    diarization_device = "cpu" if (device == "mps" and os.getenv("GOODQ_MPS_DIARIZATION") == "0") else device
                    diarization_pipeline.to(torch.device(diarization_device))
                    
                    diarization_audio = {
                        "waveform": waveform.detach().cpu(),
                        "sample_rate": sr,
                    }
                    diarization_result, result["speaker_change_review"] = _diarize_with_review(
                        diarization_pipeline, diarization_audio, overlap_evidence=result["overlap_detection"])
                    
                    # Handle new pyannote API - DiarizeOutput object
                    # The actual annotation is in the speaker_diarization attribute
                    if hasattr(diarization_result, 'speaker_diarization'):
                        diarization = diarization_result.speaker_diarization
                    else:
                        diarization = diarization_result
                    
                    raw_diarization_segments = []
                    for segment, track, speaker in diarization.itertracks(yield_label=True):
                        raw_diarization_segments.append({
                            "start": float(segment.start),
                            "end": float(segment.end),
                            "speaker": speaker
                        })
                    diarization_segments, diarization_timing = _bound_diarization_segments_to_audio(
                        raw_diarization_segments,
                        duration_seconds=result["duration_seconds"],
                    )
                    speakers = [seg["speaker"] for seg in diarization_segments if seg.get("speaker")]
                    
                    result["speakers"] = sorted(set(speakers))
                    result["speaker_count"] = len(result["speakers"])
                    result["diarization"] = diarization_segments
                    result["diarization_timing"] = diarization_timing
                    diarization_status, diarization_note = _diarization_outcome(diarization_segments)
                    result["diarization_status"] = diarization_status
                    if diarization_note:
                        result["diarization_note"] = diarization_note
                    
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
                result["diarization_error"] = model_cache.redact_sensitive_info(str(e))
                # Ensure cleanup even on error
                try:
                    del diarization_pipeline
                except:
                    pass
                clear_gpu_memory()
                if is_offline:
                    raise
        elif not bool(result["diarization_enabled"]):
            result["diarization_status"] = "skipped"
            result["diarization_note"] = "disabled by runtime config"
        else:
            result["diarization_status"] = "unavailable"
            if DIARIZATION_IMPORT_ERROR:
                result["diarization_note"] = f"pyannote.audio unavailable: {DIARIZATION_IMPORT_ERROR}"
            else:
                result["diarization_note"] = "pyannote.audio not installed"
        
        # The optional detector adds vetoes only, before either individual
        # inference caller. Absent configuration preserves the established path.
        if "additional_overlap_model" in (runtime_cfg.get("diarization") or {}):
            result["additional_overlap_detection"] = {"status": "unavailable", "intervals": [],
                "policy": "nemotron3_overlap_exclusion_v1", "timebase": "input_audio_seconds",
                "review_status": "unreviewed", "identity_claim": False}
            if no_speech:
                result["additional_overlap_detection"].update(status="not_applicable", reason="no_speech_detected")
            else:
                try:
                    result["additional_overlap_detection"] = _detect_additional_overlap(
                        waveform, sr, runtime_cfg["diarization"]["additional_overlap_model"], device)
                except Exception as exc:
                    result["additional_overlap_detection"].update(status="error",
                        error=model_cache.redact_sensitive_info(str(exc)))

        # === STEP 3: EMOTION CLASSIFICATION (Wav2Vec2 - optional) ===
        # Use CPU for emotion model to save GPU memory
        print("Processing: Emotion classification...", file=sys.stderr)
        emotion_device = "cpu"  # Force CPU to save GPU memory
        # Keep sound observations even when there is no usable speech. Failure
        # to establish clean intervals must never restore whole-scene scoring.
        result.update({"emotion": None, "emotion_scores": {}, "emotion_segments": []})
        try:
            result.update(acoustic_events.prepare_inputs(
                waveform, sr, result, cache_dir=_resolve_hf_cache_dir(), device=device))
        except Exception as exc:
            result.update({"sound_events": [], "sound_event_meta": {
                "status": "error", "error": model_cache.redact_sensitive_info(str(exc))},
                "emotion_input": {"status": "unavailable", "policy": acoustic_events.POLICY, "selected": []}})
        if no_speech:
            result.update({"emotion_status": "not_applicable", "emotion_note": "no_speech_detected",
                           "emotion": None, "emotion_scores": {}})
        elif result["emotion_input"]["status"] == "unavailable":
            result.update({"emotion_status": "error", "emotion_error": "speech_selection_unavailable"})
        elif not (result["emotion_input"].get("phrase_selection") or {}).get("selected"):
            result.update({"emotion_status": "insufficient_evidence", "emotion_note": "no_complete_supported_phrase"})
        elif TRANSFORMERS_AVAILABLE:
            try:
                wav2vec_cache_dir = _resolve_hf_cache_dir()
                model_repo = "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"
                if is_offline and not model_cache.check_hf_model_cache(model_repo):
                    raise OSError(
                        f"Offline mode: Wav2Vec2 Emotion model '{model_repo}' is missing from local cache.\n"
                        "Status: Non-gated.\n"
                        "Requirements: No Hugging Face token or license terms required.\n"
                        "Approved Provisioning Command: python3 scripts/install_pipeline_wsl.py --download-emotion"
                    )
                
                emotion_model, result["emotion_model_load"] = _load_trained_wav2vec(
                    model_repo, cache_dir=wav2vec_cache_dir,
                    is_offline=is_offline, emotion=True,
                )

                try:
                    emotion_extractor = Wav2Vec2FeatureExtractor.from_pretrained(
                        model_repo,
                        cache_dir=wav2vec_cache_dir,
                        local_files_only=True,
                    )
                except Exception as exc:
                    if is_offline:
                        raise OSError(f"Offline mode: Failed to load Wav2Vec2 Emotion feature extractor '{model_repo}' from cache: {exc}") from exc
                    emotion_extractor = Wav2Vec2FeatureExtractor.from_pretrained(
                        model_repo,
                        cache_dir=wav2vec_cache_dir,
                    )
                emotion_model.to(emotion_device)
                
                # Resample if needed
                if sr != 16000:
                    resampler = torchaudio.transforms.Resample(sr, 16000)
                    waveform_16k = resampler(waveform)
                else:
                    waveform_16k = waveform
                
                for segment in result["emotion_input"]["phrase_selection"]["selected"]:
                    first = math.ceil(segment["start"] * 16000)
                    last = math.floor(segment["end"] * 16000)
                    sample = waveform_16k[:, first:last]
                    if sample.shape[-1] == 0:
                        raise ValueError("Selected emotion interval has no samples")
                    inputs = emotion_extractor(sample.numpy().flatten(), sampling_rate=16000,
                                               return_tensors="pt", padding=True)
                    inputs = {k: v.to(emotion_device) for k, v in inputs.items()}
                    with torch.no_grad():
                        logits = emotion_model(**inputs).logits
                    if not torch.isfinite(logits).all():
                        raise ValueError("Non-finite speech emotion logits")
                    labels = [emotion_model.config.id2label[index] for index in range(logits.shape[-1])]
                    scores = logits.softmax(dim=-1).cpu().numpy()[0]
                    result["emotion_segments"].append({**segment,
                        **acoustic_events.emotion_uncertainty(segment),
                        "label": labels[torch.argmax(logits, dim=-1).item()],
                        "scores": {label: float(score) for label, score in zip(labels, scores)},
                        "sample_start": first, "sample_end": last, "sample_rate": 16000,
                        "source": "speech_acoustics", "review_status": "unreviewed"})
                # Segment estimates are never promoted into a scene/person mood.
                result["emotion_status"] = "success"
                result["emotion_note"] = "uncertain_complete_phrase_estimates"
                
                # Clean up emotion model
                del emotion_model
                del emotion_extractor
                clear_gpu_memory()
                if device == "cuda":
                    result["after_emotion_gpu_memory"] = get_gpu_memory_info()
                
            except Exception as e:
                result["emotion_segments"] = []
                result["emotion_status"] = "error"
                result["emotion_error"] = model_cache.redact_sensitive_info(str(e))
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
        
        # === STEP 5: DEDICATED SPEAKER SIGNATURES ===
        result["embeddings_status"] = "retired"
        result["embeddings_note"] = "whole_scene_vector_retired"
        diarization_segments = result.get("diarization")
        embed_model = None
        if no_speech:
            result["speaker_voice_signature_meta"] = {
                "status": "not_applicable", "reason": "no_speech_detected"}
        elif not isinstance(diarization_segments, list) or not diarization_segments:
            result["speaker_voice_signature_meta"] = {
                "status": "skipped", "reason": "diarization_unavailable"}
        else:
            try:
                embed_model = speaker_signature.load_encoder(
                    device, str(Path(output_dir) / "speaker_model"), _resolve_hf_cache_dir())
                waveform_16k = (torchaudio.transforms.Resample(sr, 16000)(waveform)
                               if sr != 16000 else waveform)
                # Voice references require acoustic speech evidence as well as
                # exclusive diarization. Keep the encoder's own duration/diversity gates.
                qualified_segments = (result.get("emotion_input") or {}).get("selected", [])
                signature_result = _build_speaker_voice_signatures(
                    waveform_16k.detach().cpu(), diarization_segments,
                    embed_model=embed_model, device=device, speech_intervals=qualified_segments)
                signature_result["meta"]["speech_admission"] = "acoustically_assessed_phrases"
                result["speaker_voice_signatures"] = signature_result["signatures"]
                result["speaker_voice_signature_meta"] = signature_result["meta"]
            except Exception as exc:
                result["speaker_voice_signatures"] = []
                result["speaker_voice_signature_meta"] = {
                    "status": "error", "reason": "speaker_signature_step_failed",
                    "error": model_cache.redact_sensitive_info(str(exc))}
            finally:
                del embed_model
                clear_gpu_memory()

        # Final cleanup
        print("Processing complete. Final cleanup...", file=sys.stderr)
        clear_gpu_memory()
        if device == "cuda":
            result["final_gpu_memory"] = get_gpu_memory_info()
        
        # Final status
        result["status"] = "success"
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = model_cache.redact_sensitive_info(str(e))
        result["traceback"] = model_cache.redact_sensitive_info(traceback.format_exc())
        if output_dir:
            try:
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)
                output_file = output_path / "result.json"
                with open(output_file, 'w') as f:
                    json.dump(result, f, indent=2)
            except Exception:
                pass
        if is_offline:
            raise
    
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
        vocabulary = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
        temperature = json.loads(sys.argv[4]) if len(sys.argv) > 4 else None
        result = process_audio(audio_file, output_dir, transcription_vocabulary=vocabulary,
                               transcription_temperature=temperature)
    print(json.dumps(result))
    
    if result["status"] != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
