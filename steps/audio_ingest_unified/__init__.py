"""
Unified WSL2 Audio Ingestion Step

Calls the upgraded WSL2 process_audio.py which provides:
- Transcription (Faster-Whisper)
- Diarization (Pyannote 3.1)  
- Emotion classification (Wav2Vec2)
- Audio embeddings (Wav2Vec2-768d)
- Audio features (energy, duration, etc.)
"""
