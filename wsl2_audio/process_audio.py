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
from pathlib import Path

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
try:
    from pyannote.audio import Pipeline as DiarizationPipeline
    DIARIZATION_AVAILABLE = True
except ImportError:
    DIARIZATION_AVAILABLE = False

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


def process_audio(audio_file, output_dir):
    """Process audio file with full classification pipeline - Memory optimized"""
    
    result = {
        "status": "processing",
        "audio_file": str(audio_file),
        "output_dir": str(output_dir)
    }
    
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
    
    if device == "cuda":
        result["gpu_name"] = torch.cuda.get_device_name(0)
        result["gpu_memory_mb"] = torch.cuda.get_device_properties(0).total_memory // (1024**2)
        result["initial_gpu_memory"] = get_gpu_memory_info()
    
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
            whisper_model = WhisperModel("base", device=device, compute_type=compute_type)
            segments, info = whisper_model.transcribe(audio_file, language="en", beam_size=5)
            
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
        if DIARIZATION_AVAILABLE:
            try:
                hf_token = os.getenv("HUGGINGFACE_TOKEN", "")
                if hf_token:
                    diarization_pipeline = DiarizationPipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.1",
                        token=hf_token
                    )
                    diarization_pipeline.to(torch.device(device))
                    
                    diarization_result = diarization_pipeline(audio_file)
                    
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
        else:
            result["diarization_status"] = "unavailable"
            result["diarization_note"] = "pyannote.audio not installed"
        
        # === STEP 3: EMOTION CLASSIFICATION (Wav2Vec2 - optional) ===
        # Use CPU for emotion model to save GPU memory
        print("Processing: Emotion classification...", file=sys.stderr)
        emotion_device = "cpu"  # Force CPU to save GPU memory
        if TRANSFORMERS_AVAILABLE:
            try:
                emotion_model = Wav2Vec2ForSequenceClassification.from_pretrained(
                    "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"
                )
                emotion_extractor = Wav2Vec2FeatureExtractor.from_pretrained(
                    "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"
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
                embed_model = Wav2Vec2Model.from_pretrained("facebook/wav2vec2-base-960h")
                embed_model.to(device)
                
                if sr != 16000:
                    resampler = torchaudio.transforms.Resample(sr, 16000)
                    waveform_16k = resampler(waveform)
                else:
                    waveform_16k = waveform
                
                embed_extractor = Wav2Vec2FeatureExtractor.from_pretrained("facebook/wav2vec2-base-960h")
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
                
                # Clean up embedding model
                del embed_model
                del embed_extractor
                clear_gpu_memory()
                if device == "cuda":
                    result["after_embeddings_gpu_memory"] = get_gpu_memory_info()
                
            except Exception as e:
                result["embeddings_status"] = "error"
                result["embeddings_error"] = str(e)
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
    
    result = process_audio(audio_file, output_dir)
    print(json.dumps(result))
    
    if result["status"] != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
