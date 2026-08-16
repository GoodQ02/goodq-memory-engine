"""Offline Wav2Vec speaker-signature generation from existing audio evidence.

This worker deliberately does not transcribe, diarize, classify emotion, or
persist anything.  It accepts an existing scene audio file and the scene's
already-persisted diarization segments, then emits only signature evidence.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import process_audio as audio_worker


def build_signatures(audio_file: str | Path, diarization_segments: list[dict[str, Any]]) -> dict[str, Any]:
    """Return signature-only evidence using the pinned offline Wav2Vec model."""
    if not audio_worker.TRANSFORMERS_AVAILABLE:
        raise RuntimeError("Wav2Vec signature runtime is unavailable: transformers not installed")
    if not isinstance(diarization_segments, list) or not diarization_segments:
        raise ValueError("signature-only work requires existing diarization segments")

    repo = "facebook/wav2vec2-base-960h"
    revision = os.getenv("GOODQ_WAV2VEC2_BASE_REVISION", "22aad52d435eb6dbaf354bdad9b0da84ce7d6156").strip()
    if model_cache.is_offline_mode() and not model_cache.check_hf_model_cache(repo):
        raise OSError(f"Offline Wav2Vec model is unavailable in the configured cache: {repo}")

    waveform, sample_rate = audio_worker.torchaudio.load(str(audio_file))
    if int(sample_rate) != audio_worker._SPEAKER_SIGNATURE_TARGET_SR:
        waveform = audio_worker.torchaudio.transforms.Resample(
            int(sample_rate), audio_worker._SPEAKER_SIGNATURE_TARGET_SR
        )(waveform)
    waveform = waveform.detach().cpu()
    cache_dir = audio_worker._resolve_hf_cache_dir()
    device = "cuda" if audio_worker.torch.cuda.is_available() else "cpu"
    model = audio_worker.Wav2Vec2Model.from_pretrained(
        repo, revision=revision or None, cache_dir=cache_dir, local_files_only=True
    ).to(device)
    extractor = audio_worker.Wav2Vec2FeatureExtractor.from_pretrained(
        repo, revision=revision or None, cache_dir=cache_dir, local_files_only=True
    )
    try:
        signature_result = audio_worker._build_speaker_voice_signatures(
            waveform,
            diarization_segments,
            embed_model=model,
            embed_extractor=extractor,
            device=device,
            sample_rate=audio_worker._SPEAKER_SIGNATURE_TARGET_SR,
        )
        return {
            "status": "success",
            "mode": "signature_only",
            "source_audio_file": str(audio_file),
            "model_repo": repo,
            "model_revision": revision,
            "device": device,
            "speaker_voice_signatures": signature_result.get("signatures", []),
            "speaker_voice_signature_meta": signature_result.get("meta", {}),
        }
    finally:
        del model
        del extractor
        audio_worker.clear_gpu_memory()


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("Usage: signature_only.py <audio_file> <diarization.json> <output.json>")
    audio_file, diarization_file, output_file = map(Path, sys.argv[1:])
    try:
        payload = json.loads(diarization_file.read_text(encoding="utf-8"))
        result = build_signatures(audio_file, payload)
    except Exception as exc:
        result = {"status": "error", "mode": "signature_only", "error": str(exc)}
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    if result["status"] != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
