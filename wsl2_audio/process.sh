#!/bin/bash
set -euo pipefail

# GoodQ Audio Processing Script - Full Classification
AUDIO_FILE="$1"
OUTPUT_DIR="$2"

# Activate CUDA environment (includes venv + cuDNN library paths)
# Redirect setup messages to /dev/null to keep stdout clean for JSON
source ~/goodq_audio/setup_cuda_env.sh >/dev/null 2>&1

# Run full audio classification pipeline
python3 << 'PYTHON_EOF'
import sys
import json
import os
import torch
import torchaudio
import numpy as np
from pathlib import Path
from faster_whisper import WhisperModel
from pyannote.audio import Pipeline
from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2FeatureExtractor

# Paths
audio_file = sys.argv[1] if len(sys.argv) > 1 else os.getenv("AUDIO_FILE", "")
output_dir = sys.argv[2] if len(sys.argv) > 2 else os.getenv("OUTPUT_DIR", "")

if not audio_file or not Path(audio_file).exists():
    print(json.dumps({"status": "error", "message": "Audio file not found"}))
    sys.exit(1)

# GPU Check
device = "cuda" if torch.cuda.is_available() else "cpu"
compute_type = "float16" if device == "cuda" else "int8"

result = {
    "status": "processing",
    "device": device,
    "transcription": None,
    "speakers": [],
    "diarization": [],
    "emotion": None,
    "language": None,
    "energy": None,
    "embeddings": None
}

try:
    # Load audio
    waveform, sr = torchaudio.load(audio_file)
    
    # === STEP 1: TRANSCRIPTION (Faster-Whisper) ===
    whisper_model = WhisperModel("base", device=device, compute_type=compute_type)
    segments, info = whisper_model.transcribe(audio_file, language="en", beam_size=5)
    
    transcription_text = ""
    word_timestamps = []
    
    for segment in segments:
        transcription_text += segment.text + " "
        word_timestamps.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text,
            "confidence": segment.avg_logprob
        })
    
    result["transcription"] = transcription_text.strip()
    result["word_timestamps"] = word_timestamps
    result["language"] = info.language
    result["language_probability"] = info.language_probability
    
    # === STEP 2: SPEAKER DIARIZATION (Pyannote) ===
    try:
        hf_token = os.getenv("HUGGINGFACE_TOKEN", "")
        if hf_token:
            diarization_pipeline = Pipeline.from_pretrained(
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
                    "start": turn.start,
                    "end": turn.end,
                    "speaker": speaker
                })
            
            result["speakers"] = list(set(speakers))
            result["speaker_count"] = len(set(speakers))
            result["diarization"] = diarization_segments
    except Exception as e:
        result["diarization_error"] = str(e)
    
    # === STEP 3: EMOTION CLASSIFICATION (Wav2Vec2) ===
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
            waveform = resampler(waveform)
        
        inputs = emotion_extractor(waveform.numpy().flatten(), sampling_rate=16000, return_tensors="pt", padding=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            logits = emotion_model(**inputs).logits
        
        emotion_labels = ["angry", "calm", "disgust", "fear", "happy", "neutral", "sad", "surprise"]
        predicted_emotion = emotion_labels[torch.argmax(logits, dim=-1).item()]
        emotion_scores = torch.nn.functional.softmax(logits, dim=-1).cpu().numpy()[0]
        
        result["emotion"] = predicted_emotion
        result["emotion_scores"] = {label: float(score) for label, score in zip(emotion_labels, emotion_scores)}
    except Exception as e:
        result["emotion_error"] = str(e)
    
    # === STEP 4: AUDIO FEATURES ===
    # Energy/Volume
    energy = torch.mean(torch.abs(waveform)).item()
    result["energy"] = float(energy)
    result["duration"] = waveform.shape[1] / sr
    
    # === STEP 5: EMBEDDINGS (Wav2Vec2) ===
    try:
        from transformers import Wav2Vec2Model
        embed_model = Wav2Vec2Model.from_pretrained("facebook/wav2vec2-base-960h")
        embed_model.to(device)
        
        inputs = emotion_extractor(waveform.numpy().flatten(), sampling_rate=16000, return_tensors="pt", padding=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            embeddings = embed_model(**inputs).last_hidden_state
        
        # Mean pooling
        embedding_vector = torch.mean(embeddings, dim=1).cpu().numpy()[0]
        result["embeddings"] = embedding_vector.tolist()
        result["embedding_dim"] = len(embedding_vector)
    except Exception as e:
        result["embedding_error"] = str(e)
    
    # Final status
    result["status"] = "success"
    
except Exception as e:
    result["status"] = "error"
    result["error"] = str(e)
    result["traceback"] = traceback.format_exc()

# Write output
if output_dir:
    output_file = Path(output_dir) / "result.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

# Print to stdout
print(json.dumps(result))

PYTHON_EOF
