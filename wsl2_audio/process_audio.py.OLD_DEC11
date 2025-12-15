#!/usr/bin/env python3
"""
GoodQ Audio Processing Script - Full Classification
GPU-accelerated audio analysis with Whisper, Pyannote, and Wav2Vec2
"""

import sys
import json
import os
import traceback
from pathlib import Path

# Core imports
import torch
import torchaudio
import numpy as np

# Whisper for transcription
from faster_whisper import WhisperModel

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


def process_audio(audio_file, output_dir):
    """Process audio file with full classification pipeline"""
    
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
    
    # GPU setup
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    result["device"] = device
    result["cuda_available"] = torch.cuda.is_available()
    
    if device == "cuda":
        result["gpu_name"] = torch.cuda.get_device_name(0)
        result["gpu_memory_mb"] = torch.cuda.get_device_properties(0).total_memory // (1024**2)
    
    try:
        # Load audio
        waveform, sr = torchaudio.load(audio_file)
        result["sample_rate"] = sr
        result["duration_seconds"] = waveform.shape[1] / sr
        result["channels"] = waveform.shape[0]
        
        # Convert to mono if stereo
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        
        # === STEP 1: TRANSCRIPTION (Faster-Whisper) ===
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
            
        except Exception as e:
            result["transcription_status"] = "error"
            result["transcription_error"] = str(e)
        
        # === STEP 2: SPEAKER DIARIZATION (Pyannote - optional) ===
        if DIARIZATION_AVAILABLE:
            try:
                hf_token = os.getenv("HUGGINGFACE_TOKEN", "")
                if hf_token:
                    diarization_pipeline = DiarizationPipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.1",
                        use_auth_token=hf_token
                    )
                    diarization_pipeline.to(torch.device(device))
                    
                    diarization = diarization_pipeline(audio_file)
                    
                    speakers = []
                    diarization_segments = []
                    for turn, _, speaker in diarization.itertracks(yield_label=True):
                        speakers.append(speaker)
                        diarization_segments.append({
                            "start": float(turn.start),
                            "end": float(turn.end),
                            "speaker": speaker
                        })
                    
                    result["speakers"] = list(set(speakers))
                    result["speaker_count"] = len(set(speakers))
                    result["diarization"] = diarization_segments
                    result["diarization_status"] = "success"
                else:
                    result["diarization_status"] = "skipped"
                    result["diarization_note"] = "HUGGINGFACE_TOKEN not set"
            except Exception as e:
                result["diarization_status"] = "error"
                result["diarization_error"] = str(e)
        else:
            result["diarization_status"] = "unavailable"
            result["diarization_note"] = "pyannote.audio not installed"
        
        # === STEP 3: EMOTION CLASSIFICATION (Wav2Vec2 - optional) ===
        if TRANSFORMERS_AVAILABLE:
            try:
                emotion_model = Wav2Vec2ForSequenceClassification.from_pretrained(
                    "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"
                )
                emotion_extractor = Wav2Vec2FeatureExtractor.from_pretrained(
                    "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"
                )
                emotion_model.to(device)
                
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
                inputs = {k: v.to(device) for k, v in inputs.items()}
                
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
                
            except Exception as e:
                result["emotion_status"] = "error"
                result["emotion_error"] = str(e)
        else:
            result["emotion_status"] = "unavailable"
            result["emotion_note"] = "transformers not installed"
        
        # === STEP 4: AUDIO FEATURES ===
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
        if TRANSFORMERS_AVAILABLE:
            try:
                embed_model = Wav2Vec2Model.from_pretrained("facebook/wav2vec2-base-960h")
                embed_model.to(device)
                
                if sr != 16000:
                    resampler = torchaudio.transforms.Resample(sr, 16000)
                    waveform_16k = resampler(waveform)
                else:
                    waveform_16k = waveform
                
                inputs = Wav2Vec2FeatureExtractor.from_pretrained("facebook/wav2vec2-base-960h")(
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
                
            except Exception as e:
                result["embeddings_status"] = "error"
                result["embeddings_error"] = str(e)
        else:
            result["embeddings_status"] = "unavailable"
            result["embeddings_note"] = "transformers not installed"
        
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
