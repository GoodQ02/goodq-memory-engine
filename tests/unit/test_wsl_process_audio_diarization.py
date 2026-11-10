from __future__ import annotations

import types
import json
import sys
import os
from pathlib import Path

import torch
import pytest


def test_no_speech_veto_preserves_candidates_and_accepts_spoken_segments():
    from wsl2_audio.process_audio import _filter_no_speech_segments
    candidates = [{'text': 'arbitrary candidate', 'no_speech_probability': 0.9126, 'confidence': -0.89,
                   'words': [{'text': 'candidate', 'probability': .05}]},
                  {'text': 'family dialogue', 'no_speech_probability': 0.03},
                  {'text': 'at threshold', 'no_speech_probability': 0.6}]
    accepted, quality = _filter_no_speech_segments(candidates, 0.6, log_prob_threshold=-1.0)
    assert accepted == candidates
    assert quality['rejected_segments'] == []
    assert quality['uncertain_segments'] == candidates[:1]
    assert quality['decoded_segment_count'] == 3
    assert quality['accepted_segment_count'] == 3
    assert len(candidates) == 3
    accepted, quality = _filter_no_speech_segments(candidates[:1], 0.6, log_prob_threshold=-1.0)
    assert accepted == [] and quality['rejected_segments'] == candidates[:1]


@pytest.mark.parametrize('threshold', [None, True, -1, float('nan'), 2])
def test_missing_or_invalid_threshold_cannot_discard_speech(threshold):
    from wsl2_audio.process_audio import _filter_no_speech_segments
    segments = [{'text':'words', 'no_speech_probability':0.9}]
    accepted, quality = _filter_no_speech_segments(segments, threshold)
    assert accepted == segments
    assert quality['status'] == 'unavailable'


def test_diarization_outcome_requires_emitted_tracks_for_success() -> None:
    from wsl2_audio import process_audio as mod

    assert mod._diarization_outcome([{"speaker": "SPEAKER_00"}]) == ("success", None)
    assert mod._diarization_outcome([]) == (
        "completed_no_speakers",
        "diarization completed without emitted speaker tracks",
    )


def test_transcript_timestamps_are_bounded_to_loaded_audio() -> None:
    from wsl2_audio import process_audio as mod

    segments = [
        types.SimpleNamespace(start=-2.0, end=1.5, text=" opening ", avg_logprob=-0.2),
        types.SimpleNamespace(start=8.0, end=13.0, text=" trailing ", avg_logprob=-0.4),
        types.SimpleNamespace(start=14.0, end=16.0, text=" outside ", avg_logprob=-0.6),
    ]

    bounded, timing = mod._bound_transcript_segments_to_audio(
        segments,
        duration_seconds=10.0,
    )

    assert bounded == [
        {"start": 0.0, "end": 1.5, "text": "opening", "confidence": -0.2},
        {"start": 8.0, "end": 10.0, "text": "trailing", "confidence": -0.4},
    ]
    assert timing == {
        "status": "bounded",
        "input_duration_seconds": 10.0,
        "clipped_segment_count": 2,
        "dropped_segment_count": 1,
    }


def test_word_alignment_keeps_unaligned_words_without_fabricating_times():
    from wsl2_audio.process_audio import _bound_transcript_segments_to_audio
    words = [types.SimpleNamespace(word=text, start=start, end=end, probability=.75)
             for text, start, end in [(" hello", .2, .5), (" quiet", .5, .5),
                                      (" overlap", float('nan'), 1), (" tail", 1, 3)]]
    raw = types.SimpleNamespace(start=0, end=2, text="hello quiet overlap tail",
                                avg_logprob=-.8, words=words, temperature=.6)
    segments, _ = _bound_transcript_segments_to_audio([raw], duration_seconds=2)
    assert segments[0]['text'] == raw.text
    assert segments[0]['temperature'] == .6
    aligned = segments[0]['words']
    assert aligned[0] == dict(text='hello', start=.2, end=.5, probability=.75, timing_status='aligned')
    assert [w['text'] for w in aligned[1:]] == ['quiet', 'overlap', 'tail']
    assert all(w['start'] is None and w['end'] is None and w['timing_status'] == 'invalid_model_alignment'
               for w in aligned[1:])


@pytest.mark.parametrize("speech_case", ["speech", "vad_absent", "whisper_absent", "unknown", "failed", "mixed", "confident_high_no_speech", "timing_recovery", "speaker_inventory", "rejected_then_empty", "rejected_then_unplaced", "rejected_then_rejected", "partial_failed", "partial_failed_offline"])
@pytest.mark.parametrize("request_temperature", [None, 0.0, 0.2])
def test_process_audio_gates_speech_enrichments_from_evidence(monkeypatch, tmp_path: Path, speech_case, request_temperature):
    from wsl2_audio import process_audio as mod
    monkeypatch.setattr(mod.acoustic_events, 'detect_sound_events', lambda *a, **kw: (
        [], {'status': 'success', 'windows': [{'start': 0, 'end': 1, 'speech_score': .9, 'excluded_labels': []}]}))

    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"wav")
    output_dir = tmp_path / "out"

    multi_region = speech_case.startswith(('rejected_then_', 'partial_failed'))
    waveform = torch.zeros((1, 32000 if multi_region else 16000))
    captured = {}

    class _FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            captured.setdefault('transcribe_calls', []).append(kwargs)
            if speech_case == "failed" or (speech_case.startswith('partial_failed') and len(captured['transcribe_calls']) == 2):
                raise RuntimeError("decoder failed")
            info = types.SimpleNamespace(language="en", language_probability=1.0)
            segments = []
            if speech_case != "unknown":
                info.duration = 1.0
                info.duration_after_vad = 0.0 if speech_case == "vad_absent" else 1.0
                info.transcription_options = types.SimpleNamespace(no_speech_threshold=0.6, log_prob_threshold=-1.0)
            if speech_case.startswith('rejected_then_'):
                s = types.SimpleNamespace(start=0., end=.5, text='candidate', avg_logprob=-2., no_speech_prob=.99,
                    words=[types.SimpleNamespace(word='candidate', start=.1, end=.4, probability=.01)])
                if len(captured['transcribe_calls']) == 2:
                    if speech_case == 'rejected_then_empty': return iter([]), info
                    if speech_case == 'rejected_then_unplaced': s.start = s.end = .2
                return iter([s]), info
            if speech_case in {"speech", "whisper_absent", "mixed", "confident_high_no_speech"} or speech_case.startswith('partial_failed'):
                segments.append(types.SimpleNamespace(start=0.0, end=0.5, text="candidate",
                    avg_logprob=-0.3, temperature=0.8, no_speech_prob=0.91 if speech_case in {"whisper_absent", "confident_high_no_speech"} else 0.1,
                    words=[types.SimpleNamespace(word=' candidate',start=.1,end=.4,probability=.01 if speech_case == "whisper_absent" else .8)]))
            if speech_case == "timing_recovery":
                segments.append(types.SimpleNamespace(start=0., end=.5, text="candidate",
                    words=[types.SimpleNamespace(word=' candidate', start=.3 if kwargs.get('hotwords') else .1,
                                                 end=.3, probability=.95)]))
            if speech_case == "mixed":
                segments.append(types.SimpleNamespace(start=0.5, end=1.0, text="quiet word",
                    avg_logprob=-0.3, no_speech_prob=0.9))
            return iter(segments), info

    class _FakeAnnotation:
        def itertracks(self, yield_label=False):
            if speech_case == 'speaker_inventory':
                for index, speaker in enumerate(['speaker_2', 'speaker_0', 'speaker_1', 'speaker_2']):
                    yield (types.SimpleNamespace(start=index*.2, end=(index+1)*.2), str(index), speaker)
                return
            yield (types.SimpleNamespace(start=0.0, end=1.0), "track_0", "speaker_0")

    class _FakePipeline:
        _segmentation = types.SimpleNamespace(model=types.SimpleNamespace(
            receptive_field=types.SimpleNamespace(start=0, duration=.1, step=.1)))
        def to(self, device):
            captured["device"] = str(device)

        def reconstruct(self, segments, clusters, count):
            return _FakeAnnotation()

        def __call__(self, audio_input):
            captured["audio_input"] = audio_input
            # This fixture supplies observed single-speaker frames; an absent
            # observer is separately tested as unavailable, not clean evidence.
            return self.reconstruct(types.SimpleNamespace(data=mod.np.ones((1, 10, 1)),
                sliding_window=[types.SimpleNamespace(start=0, end=1)]), mod.np.zeros((1, 1), dtype=int), None)

    class _FakePipelineFactory:
        @staticmethod
        def from_pretrained(model_name, **kwargs):
            if kwargs.get("local_files_only"):
                raise OSError("Mock cache miss for online fallback test")
            captured["model_name"] = model_name
            captured["token"] = kwargs.get("use_auth_token") or kwargs.get("token")
            captured["cache_dir"] = kwargs.get("cache_dir")
            return _FakePipeline()

    monkeypatch.setattr(mod, "_load_runtime_config", lambda: {
        "gpu": {"device": "cpu", "compute_type": "int8", "memory_fraction": 0.8},
        "models": {"whisper": "medium", "diarization": "pyannote/speaker-diarization-3.1"},
        "diarization": {"enabled": True},
        "processing": {"language": "en", "beam_size": 5,
                       **({'temperature': 0.6} if request_temperature is not None else {})},
        "_sources": [],
    })
    monkeypatch.setattr(mod, "require_gpu", lambda: False)
    monkeypatch.setattr(mod, "resolve_wsl_gpu_config", lambda cfg: dict(cfg))
    monkeypatch.setattr(mod.torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(mod.torchaudio, "load", lambda _: (waveform.clone(), 16000))
    monkeypatch.setattr(mod, '_source_speech_regions', lambda audio: [] if speech_case == 'vad_absent'
                        else ([{'start': 0, 'end': 16000}, {'start': 16000, 'end': 32000}]
                              if multi_region else [{'start': 0, 'end': len(audio)}]))
    monkeypatch.setattr('wsl2_audio.transcription_contract._recognition_source_regions', mod._source_speech_regions)
    monkeypatch.setattr(mod, "WhisperModel", _FakeWhisperModel)
    monkeypatch.setattr(mod, "DIARIZATION_AVAILABLE", True)
    monkeypatch.setattr(mod, "DiarizationPipeline", _FakePipelineFactory, raising=False)
    monkeypatch.setattr(mod, "TRANSFORMERS_AVAILABLE", True)
    class EmotionModel:
        config = types.SimpleNamespace(id2label={0: "neutral", 1: "happy"})
        def to(self, device): return self
        def __call__(self, **kwargs): return types.SimpleNamespace(logits=torch.tensor([[0.0, 1.0]]))
    def load_emotion(*args, **kwargs):
        captured["emotion_loaded"] = True
        return EmotionModel(), {"strict": True}
    class Extractor:
        @classmethod
        def from_pretrained(cls, *args, **kwargs): return cls()
        def __call__(self, *args, **kwargs): return {"input_values": waveform}
    monkeypatch.setattr(mod, "_load_trained_wav2vec", load_emotion)
    monkeypatch.setattr(mod, "Wav2Vec2FeatureExtractor", Extractor, raising=False)
    def load_encoder(*args, **kwargs):
        captured["signature_loaded"] = True
        return object()
    monkeypatch.setattr(mod.speaker_signature, "load_encoder", load_encoder)
    monkeypatch.setattr(mod, "_build_speaker_voice_signatures", lambda *a, **k: {
        "signatures": [{"speaker_id": "speaker_0"}], "meta": {"status": "ok"}})
    monkeypatch.setattr(mod, "clear_gpu_memory", lambda: None)
    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", "/mnt/c/models/hub")
    
    try:
        from wsl2_audio import model_cache
    except ImportError:
        import model_cache
    monkeypatch.setattr(model_cache, "check_whisper_cache", lambda _: True)
    monkeypatch.setattr(model_cache, "check_pyannote_cache", lambda _: True)
    monkeypatch.setattr(model_cache, "is_offline_mode", lambda: speech_case == 'partial_failed_offline')

    if speech_case == 'partial_failed_offline':
        with pytest.raises(RuntimeError, match='decoder failed'):
            mod.process_audio(str(audio_file), str(output_dir), transcription_vocabulary=['Joe', 'Ana'],
                              transcription_temperature=request_temperature)
        result = json.loads((output_dir / 'result.json').read_text())
    else:
        result = mod.process_audio(str(audio_file), str(output_dir), transcription_vocabulary=["Joe", "Ana"],
                                   transcription_temperature=request_temperature)

    if speech_case.startswith('partial_failed'):
        assert result['transcription'] == 'candidate'
        assert result['word_timestamps'][0]['start'] == .1
        assert result['word_alignment']['words'] == result['word_timestamps']
        assert result['transcription_status'] == 'error'
        assert 'decoder failed' in result['transcription_error']
        assert result['transcription_decoding']['source_regions']['completed_region_count'] == 1
        if speech_case == 'partial_failed_offline':
            assert result['status'] == 'error'
            return
    assert result["status"] == "success"
    if speech_case == 'vad_absent':
        assert not captured.get('transcribe_calls')
    else:
        assert captured['transcribe_calls'][0]['vad_filter'] is False
        assert captured['transcribe_calls'][0]['condition_on_previous_text'] is False
        assert captured['transcribe_calls'][0]['word_timestamps'] is False
        assert captured['transcribe_calls'][0]['hotwords'] == 'Joe, Ana'
    expected_temperature = request_temperature if request_temperature is not None else 0.0
    assert all(call['temperature'] == expected_temperature for call in captured.get('transcribe_calls', []))
    assert result['transcription_decoding']['temperature_fallback'] is False
    assert result['transcription_decoding']['sampling_enabled'] is (expected_temperature > 0)
    assert result['transcription_context']['identity_claim'] is False
    if speech_case == 'timing_recovery':
        assert len(captured['transcribe_calls']) == 1
        assert result['word_timestamps'][0]['timing_status'] == 'invalid_model_alignment'
        assert result['word_timestamps'][0]['start'] is None
        assert result['transcription_timing']['word_alignment']['second_asr_pass'] is False
    if speech_case in {'speech', 'mixed', 'confident_high_no_speech'}:
        assert result['word_timestamps'][0]['text'] == 'candidate'
        assert result['word_timestamps'][0]['start'] == .1
        assert result['segments'][0]['start'] == 0
        assert result['word_alignment']['words'] == result['word_timestamps']
        assert result['transcription_quality']['sampled_segment_count'] == 1
    if speech_case in {'vad_absent', 'whisper_absent'}:
        assert result['word_timestamps'] == []
    assert result["device"] == "cpu"
    if speech_case in {"vad_absent", "whisper_absent", "rejected_then_rejected"}:
        assert result["diarization_status"] == "not_applicable"
        assert result["emotion_status"] == "not_applicable"
        assert result["diarization_note"] == result["emotion_note"] == "no_speech_detected"
        assert result["speakers"] == result["diarization"] == result["speaker_voice_signatures"] == []
        assert result["speaker_count"] == 0
        assert result["emotion"] is None and result["emotion_scores"] == {}
        assert result["speaker_voice_signature_meta"]["reason"] == "no_speech_detected"
        assert result["speaker_change_review"]["reason"] == "no_speech_detected"
        assert not {"emotion_loaded", "signature_loaded", "audio_input"}.intersection(captured)
        return
    assert captured["signature_loaded"]
    assert "emotion_loaded" not in captured
    # At most one .3-second aligned word: insufficient for a speech emotion.
    assert result["emotion_status"] == "insufficient_evidence" and result["emotion"] is None
    if speech_case == "failed":
        assert result["transcription_status"] == "error"
    if speech_case == "mixed":
        assert "quiet word" in result["transcription"]
    assert result["diarization_status"] == "success"
    assert result["speaker_count"] == (3 if speech_case == 'speaker_inventory' else 1)
    if speech_case == 'speaker_inventory':
        assert result['speakers'] == ['speaker_0', 'speaker_1', 'speaker_2']
        assert [turn['speaker'] for turn in result['diarization']] == ['speaker_2', 'speaker_0', 'speaker_1', 'speaker_2']
    assert captured["model_name"] == "pyannote/speaker-diarization-3.1"
    assert captured["token"] == "test-token"
    assert captured["cache_dir"] == "/mnt/c/models/hub"
    assert isinstance(captured["audio_input"], dict)
    assert captured["audio_input"]["sample_rate"] == 16000
    assert torch.equal(captured["audio_input"]["waveform"], waveform)


def test_process_audio_diarization_loader_falls_back_to_token_kwarg():
    from wsl2_audio import process_audio as mod

    captured = {}

    class _FakePipeline:
        pass

    class _FakePipelineFactory:
        calls = 0

        @classmethod
        def from_pretrained(cls, model_name, **kwargs):
            cls.calls += 1
            if kwargs.get("local_files_only"):
                raise ValueError("Local cache miss")
            if "use_auth_token" in kwargs:
                raise TypeError("Pipeline.from_pretrained() got an unexpected keyword argument 'use_auth_token'")
            captured["model_name"] = model_name
            captured["token"] = kwargs.get("token")
            captured["cache_dir"] = kwargs.get("cache_dir")
            return _FakePipeline()

    pipeline = mod._load_pyannote_pipeline(
        _FakePipelineFactory,
        "pyannote/speaker-diarization-3.1",
        "test-token",
        cache_dir="/mnt/c/models/hub",
    )

    assert isinstance(pipeline, _FakePipeline)
    assert _FakePipelineFactory.calls == 3
    assert captured["model_name"] == "pyannote/speaker-diarization-3.1"
    assert captured["token"] == "test-token"
    assert captured["cache_dir"] == "/mnt/c/models/hub"


def test_process_audio_hf_cache_resolver_exports_pyannote_aliases(monkeypatch):
    from wsl2_audio import process_audio as mod

    monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", "/mnt/c/models/hub")
    monkeypatch.delenv("HF_HUB_CACHE", raising=False)
    monkeypatch.delenv("PYANNOTE_CACHE", raising=False)

    assert mod._resolve_hf_cache_dir() == "/mnt/c/models/hub"
    assert os.environ["HF_HUB_CACHE"] == "/mnt/c/models/hub"
    assert os.environ["PYANNOTE_CACHE"] == "/mnt/c/models/hub"


def test_audio_service_diarization_loader_prefers_use_auth_token(monkeypatch):
    monkeypatch.setitem(sys.modules, "soundfile", types.ModuleType("soundfile"))
    from wsl2_audio import audio_service as mod

    captured = {}

    class _FakePipeline:
        pass

    class _FakePipelineFactory:
        @staticmethod
        def from_pretrained(model_name, **kwargs):
            if kwargs.get("local_files_only"):
                raise OSError("Mock cache miss")
            captured["model_name"] = model_name
            captured["use_auth_token"] = kwargs.get("use_auth_token") or kwargs.get("token")
            captured["cache_dir"] = kwargs.get("cache_dir")
            return _FakePipeline()

    pipeline = mod._load_pyannote_pipeline(
        _FakePipelineFactory,
        "pyannote/speaker-diarization-3.1",
        "test-token",
        cache_dir="/mnt/c/models/hub",
    )

    assert isinstance(pipeline, _FakePipeline)
    assert captured["model_name"] == "pyannote/speaker-diarization-3.1"
    assert captured["use_auth_token"] == "test-token"
    assert captured["cache_dir"] == "/mnt/c/models/hub"


def test_audio_service_hf_cache_resolver_exports_pyannote_aliases(monkeypatch):
    monkeypatch.setitem(sys.modules, "soundfile", types.ModuleType("soundfile"))
    from wsl2_audio import audio_service as mod

    monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", "/mnt/c/models/hub")
    monkeypatch.delenv("HF_HUB_CACHE", raising=False)
    monkeypatch.delenv("PYANNOTE_CACHE", raising=False)

    assert mod._resolve_hf_cache_dir() == "/mnt/c/models/hub"
    assert os.environ["HF_HUB_CACHE"] == "/mnt/c/models/hub"
    assert os.environ["PYANNOTE_CACHE"] == "/mnt/c/models/hub"


def test_audio_service_load_models_uses_canonical_hf_cache(monkeypatch):
    monkeypatch.setitem(sys.modules, "soundfile", types.ModuleType("soundfile"))
    from wsl2_audio import audio_service as mod

    captured = {}

    class _FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            captured["whisper"] = {"args": args, "kwargs": kwargs}

    class _FakePipeline:
        pass

    class _FakePipelineFactory:
        @staticmethod
        def from_pretrained(model_name, **kwargs):
            if kwargs.get("local_files_only"):
                raise OSError("Mock cache miss")
            captured["diarization_model"] = model_name
            captured["diarization_kwargs"] = kwargs
            return _FakePipeline()

    pyannote_mod = types.ModuleType("pyannote")
    pyannote_audio_mod = types.ModuleType("pyannote.audio")
    pyannote_audio_mod.Pipeline = _FakePipelineFactory
    monkeypatch.setitem(sys.modules, "pyannote", pyannote_mod)
    monkeypatch.setitem(sys.modules, "pyannote.audio", pyannote_audio_mod)

    monkeypatch.setattr(mod, "WhisperModel", _FakeWhisperModel)
    monkeypatch.setattr(mod.torch.cuda, "is_available", lambda: False)
    
    try:
        from wsl2_audio import model_cache
    except ImportError:
        import model_cache
    monkeypatch.setattr(model_cache, "load_silero_vad", lambda *args, **kwargs: ("vad", [None, None, None, None, "collect"]))
    monkeypatch.setattr(model_cache, "check_whisper_cache", lambda _: True)
    monkeypatch.setattr(model_cache, "check_pyannote_cache", lambda _: True)
    monkeypatch.setattr(model_cache, "is_offline_mode", lambda: False)
    
    monkeypatch.setenv("PYANNOTE_TOKEN", "test-token")
    monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", "/mnt/c/models/hub")

    service = object.__new__(mod.AudioService)
    service.config = {
        "gpu": {"device": "cpu", "compute_type": "int8"},
        "models": {
            "whisper": "medium",
            "diarization": "pyannote/speaker-diarization-3.1",
        },
        "huggingface_token_env": "PYANNOTE_TOKEN",
    }
    service.whisper_model = None
    service.diarization_pipeline = None
    service.vad_model = None

    service._load_models()

    assert service.diarization_pipeline is not None
    assert captured["diarization_model"] == "pyannote/speaker-diarization-3.1"
    assert captured["diarization_kwargs"]["use_auth_token"] == "test-token"
    assert captured["diarization_kwargs"]["cache_dir"] == "/mnt/c/models/hub"


def test_select_speaker_signature_segments_requires_diversity():
    from wsl2_audio import process_audio as mod

    single_segment = mod._select_speaker_signature_segments(
        [{"speaker": "SPEAKER_00", "start": 0.0, "end": 4.2}]
    )
    assert single_segment == []

    diverse_segments = mod._select_speaker_signature_segments(
        [
            {"speaker": "SPEAKER_00", "start": 0.0, "end": 2.1},
            {"speaker": "SPEAKER_00", "start": 3.0, "end": 5.2},
        ]
    )
    assert len(diverse_segments) == 1
    assert diverse_segments[0]["speaker"] == "SPEAKER_00"
    assert diverse_segments[0]["selected_segment_count"] == 2
    assert diverse_segments[0]["voiced_seconds"] >= 4.0


def test_build_speaker_voice_signatures_emits_signature_for_diverse_segments():
    from wsl2_audio import process_audio as mod

    waveform = torch.ones((1, 16000 * 6), dtype=torch.float32)

    class _FakeModel:
        def encode_batch(self, waveform):
            assert waveform.shape == (1, 70400)
            return torch.ones(1, 1, 192)

    result = mod._build_speaker_voice_signatures(
        waveform,
        [
            {"speaker": "SPEAKER_00", "start": 0.0, "end": 2.2},
            {"speaker": "SPEAKER_00", "start": 3.0, "end": 5.2},
        ],
        embed_model=_FakeModel(),
        device="cpu",
    )

    assert result["meta"]["status"] == "ok"
    assert result["meta"]["emitted"] == 1
    signature = result["signatures"][0]
    assert signature["speaker"] == "SPEAKER_00"
    assert signature["embedding_dim"] == 192
    assert signature["segment_count"] == 2
    assert abs(sum(value * value for value in signature["embedding"]) - 1.0) < 1e-6


def test_process_audio_wav2vec_loads_use_canonical_hf_cache(monkeypatch, tmp_path: Path):
    from wsl2_audio import process_audio as mod
    # Isolate the cache-loader contract; acoustic selection is tested separately.
    monkeypatch.setattr(mod.acoustic_events, 'prepare_inputs', lambda *a, **kw: {
        'sound_events': [], 'sound_event_meta': {'status': 'success'},
        'emotion_input': {'policy': 'clear_speech_only_v1', 'status': 'ready',
                          'selected': [{'start': 0, 'end': 1, 'speaker': 'S0'}],
                          'phrase_selection': {'selected': [{'start': 0, 'end': 1, 'speaker': 'S0'}]}}})
    monkeypatch.setattr(mod, '_source_speech_regions', lambda audio: [{'start': 0, 'end': len(audio)}])

    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"wav")
    output_dir = tmp_path / "out"
    waveform = torch.zeros((1, 16000))
    captured: dict[str, list[dict[str, object]]] = {"calls": []}

    class _FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            info = types.SimpleNamespace(language="en", language_probability=1.0)
            return iter(()), info

    class _FakeFeatureExtractor:
        @classmethod
        def from_pretrained(cls, model_name, **kwargs):
            captured["calls"].append({"kind": "extractor", "model": model_name, **kwargs})
            return cls()

        def __call__(self, audio, sampling_rate, return_tensors, padding):
            return {"input_values": torch.zeros((1, 16000))}

    class _FakeEmotionModel:
        @classmethod
        def from_pretrained(cls, model_name, **kwargs):
            captured["calls"].append({"kind": "emotion_model", "model": model_name, **kwargs})
            return cls()

        def to(self, device):
            return self

        def __call__(self, **kwargs):
            return types.SimpleNamespace(logits=torch.tensor([[0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]]))

    class _FakeEmbeddingModel:
        @classmethod
        def from_pretrained(cls, model_name, **kwargs):
            captured["calls"].append({"kind": "embedding_model", "model": model_name, **kwargs})
            return cls()

        def to(self, device):
            return self

        def __call__(self, **kwargs):
            return types.SimpleNamespace(last_hidden_state=torch.ones((1, 2, 3)))

    monkeypatch.setattr(mod, "_load_runtime_config", lambda: {
        "gpu": {"device": "cpu", "compute_type": "int8", "memory_fraction": 0.8},
        "models": {"whisper": "medium", "diarization": "pyannote/speaker-diarization-3.1"},
        "diarization": {"enabled": False},
        "processing": {"language": "en", "beam_size": 5},
        "_sources": [],
    })
    monkeypatch.setattr(mod, "require_gpu", lambda: False)
    monkeypatch.setattr(mod, "resolve_wsl_gpu_config", lambda cfg: dict(cfg))
    monkeypatch.setattr(mod.torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(mod.torchaudio, "load", lambda _: (waveform.clone(), 16000))
    monkeypatch.setattr(mod, "WhisperModel", _FakeWhisperModel)
    monkeypatch.setattr(mod, "TRANSFORMERS_AVAILABLE", True)
    def load_trained(model_name, *, cache_dir, is_offline, emotion=False, revision=None):
        kind = _FakeEmotionModel if emotion else _FakeEmbeddingModel
        model = kind.from_pretrained(model_name, cache_dir=cache_dir, revision=revision)
        model.config = types.SimpleNamespace(id2label=dict(enumerate(
            ["angry", "calm", "disgust", "fearful", "happy", "neutral", "sad", "surprised"])))
        return model, {"strict": True, "missing_inference_keys": []}

    monkeypatch.setattr(mod, "_load_trained_wav2vec", load_trained)
    monkeypatch.setattr(mod, "Wav2Vec2FeatureExtractor", _FakeFeatureExtractor, raising=False)
    monkeypatch.setattr(mod, "clear_gpu_memory", lambda: None)
    monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", "/mnt/c/models/hub")
    
    try:
        from wsl2_audio import model_cache
    except ImportError:
        import model_cache
    monkeypatch.setattr(model_cache, "check_whisper_cache", lambda _: True)
    monkeypatch.setattr(model_cache, "check_hf_model_cache", lambda _: True)

    result = mod.process_audio(str(audio_file), str(output_dir))

    assert result["emotion_status"] == "success"
    assert result["embeddings_status"] == "retired"
    assert captured["calls"]
    assert all(call.get("cache_dir") == "/mnt/c/models/hub" for call in captured["calls"])


def test_bound_diarization_segments_to_audio_drops_trailing_ghost_turns():
    from wsl2_audio import process_audio as mod

    raw_segments = [
        {"start": 0.0, "end": 12.5, "speaker": "SPEAKER_00"},
        {"start": 28.0, "end": 30.8, "speaker": "SPEAKER_01"},
        {"start": 30.946, "end": 30.963, "speaker": "SPEAKER_02"},
    ]

    bounded, stats = mod._bound_diarization_segments_to_audio(raw_segments, duration_seconds=30.531)

    assert bounded == [
        {"start": 0.0, "end": 12.5, "speaker": "SPEAKER_00"},
        {"start": 28.0, "end": 30.531, "speaker": "SPEAKER_01"},
    ]
    assert stats["clipped_segment_count"] == 1
    assert stats["dropped_segment_count"] == 1
