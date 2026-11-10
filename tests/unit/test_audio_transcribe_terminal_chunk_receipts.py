from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import pytest
import numpy as np

from steps.audio_transcribe.step import audio_transcribe


class _ModelContext:
    def __init__(self, model=None):
        self.model = model
    def __enter__(self):
        return self.model

    def __exit__(self, *_args):
        return False


class _LifecycleManager:
    model_registry = {"faster_whisper_small": {}}

    def __init__(self, _cfg):
        pass

    def load(self, *_args, **_kwargs):
        return _ModelContext(self.decoder)


def _run_transcription(monkeypatch, tmp_path: Path, results: list[dict | None], temperature=0.0):
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFF")
    chunks = [
        {"start": float(index * 10), "end": float(index * 10 + 10), "speaker": None}
        for index in range(len(results))
    ]

    monkeypatch.setattr("steps.audio_transcribe.step.require_wsl_audio", lambda: False)
    monkeypatch.setattr("steps.audio_transcribe.step.is_baseline", lambda: True)
    monkeypatch.setattr("steps.audio_transcribe.step.require_gpu", lambda: False)
    monkeypatch.setattr("steps.audio_transcribe.step._audio_duration", lambda _path: float(len(chunks) * 10))
    monkeypatch.setattr("steps.audio_transcribe.step._build_chunks", lambda *_args: chunks)
    monkeypatch.setattr("lib.model_lifecycle.ModelLifecycleManager", _LifecycleManager)
    monkeypatch.setattr(
        "steps.common.model_provisioner.ensure_model_cached",
        lambda *_args, **_kwargs: SimpleNamespace(status="ready", local_path=str(tmp_path / "model")),
    )

    # Exercise actual regional decoding/aggregation, not a synthetic chunk result.
    monkeypatch.setattr('faster_whisper.audio.decode_audio',lambda *a,**kw:np.zeros(len(chunks)*10*16000,dtype=np.float32))
    monkeypatch.setattr('wsl2_audio.transcription_contract._source_speech_regions',lambda _:[
        {'start':int(c['start']*16000),'end':int(c['end']*16000)} for c in chunks])
    monkeypatch.setattr('wsl2_audio.transcription_contract._recognition_source_regions',lambda _:[
        {'start':int(c['start']*16000),'end':int(c['end']*16000)} for c in chunks])
    class Decoder:
        def detect_language(self,**kwargs): return 'en',.9,[]
        def transcribe(self,audio,**kwargs):
            assert kwargs['temperature']==temperature
            assert kwargs['vad_filter'] is False and kwargs['condition_on_previous_text'] is False
            row=results.pop(0)
            if row is None: raise RuntimeError('region decoder failed')
            text=row.get('transcript') or ''
            words=[SimpleNamespace(word=w,start=.1+i*.2,end=.3+i*.2,probability=.9)
                   for i,w in enumerate(text.split())]
            segments=[SimpleNamespace(start=0.,end=2.,text=text,words=words,avg_logprob=-.1)] if text else []
            return iter(segments),SimpleNamespace(language='en',transcription_options=SimpleNamespace(
                no_speech_threshold=.6,log_prob_threshold=-1.,compression_ratio_threshold=2.4))
    monkeypatch.setattr(_LifecycleManager,'decoder',Decoder(),raising=False)

    return audio_transcribe(
        {"source_path": str(source)},
        {"audio": {"transcribe": {"use_wsl2": False, "model": "small", "temperature": temperature}}},
    )


def test_local_caller_preserves_explicit_temperature_and_chunk_receipt(monkeypatch, tmp_path):
    receipt = {'policy': 'single_temperature_v1', 'temperature': .2,
               'sampling_enabled': True, 'temperature_fallback': False}
    result = _run_transcription(monkeypatch, tmp_path, [{'transcript': 'Hello', 'segments': [],
        'engine': 'faster-whisper', 'transcription_decoding': receipt}], temperature=.2)
    decoding=result['transcript_meta']['transcription_decoding']
    assert all(decoding[key]==value for key,value in receipt.items())
    assert decoding['source_regions']['completed_region_count']==1


def test_empty_tail_chunk_is_explicitly_nonerror_when_transcript_exists(monkeypatch, tmp_path: Path):
    result = _run_transcription(
        monkeypatch,
        tmp_path,
        [
            {"transcript": "Hello there", "segments": [], "engine": "faster-whisper"},
            {"transcript": "", "segments": [], "engine": "faster-whisper"},
        ],
    )

    meta = result["transcript_meta"]

    assert result["transcript"] == "Hello there"
    assert meta["status"] == "ok"
    assert meta["reason"] == "transcript_emitted"
    assert meta["chunks"][1]["status"] == "empty"
    assert meta["chunks"][1]["reason"] == "no_text_returned"
    assert meta["chunks"][1].get("error") is None


def test_chunk_execution_error_marks_nonempty_transcript_partial(monkeypatch, tmp_path: Path):
    result = _run_transcription(
        monkeypatch,
        tmp_path,
        [
            {"transcript": "Hello there", "segments": [], "engine": "faster-whisper"},
            None,
        ],
    )

    meta = result["transcript_meta"]

    assert result["transcript"] == "Hello there"
    assert meta["status"] == "partial"
    assert meta["reason"] == "transcript_available_with_region_errors"
    assert meta["chunks"][1]["status"] == "error"
    assert meta["chunks"][1]["reason"] == "error"
    assert meta["chunks"][1]["error"] == "region decoder failed"


@pytest.mark.parametrize("source", [None, 42, "missing.wav"])
def test_missing_source_has_a_terminal_explainable_transcript_receipt(tmp_path: Path, source):
    result = audio_transcribe(
        {"source_path": str(tmp_path / source) if isinstance(source, str) else source},
        {"audio": {"transcribe": {"use_wsl2": False}}},
    )

    meta = result["transcript_meta"]

    assert meta["status"] == "no_file"
    assert meta["reason"] == "source_file_missing"
    assert meta["error"] == "source_file_missing"
    assert meta["engine"] == "hybrid_whisper"
    assert meta["device"] == "none"


def test_all_executed_empty_chunks_are_explicit_empty(monkeypatch, tmp_path: Path):
    result = _run_transcription(monkeypatch, tmp_path, [
        {"transcript": "", "segments": [], "engine": "faster-whisper"},
        {"transcript": "", "segments": [], "engine": "faster-whisper"},
    ])
    assert result["transcript"] is None
    assert result["transcript_meta"]["status"] == "empty"
    assert result["transcript_meta"]["reason"] == "speech_detected_without_words"
    assert all(chunk["status"] == "empty" for chunk in result["transcript_meta"]["chunks"])


def test_all_failed_chunks_do_not_become_empty_success(monkeypatch, tmp_path: Path):
    result = _run_transcription(monkeypatch, tmp_path, [None, None])
    assert result["transcript"] is None
    assert result["transcript_meta"]["status"] == "error"
    assert result["transcript_meta"]["reason"] == "transcription_error"
    assert [r['outcome'] for r in result['transcript_meta']['chunks']]==['error','not_attempted']
