"""Bounded native Nemotron caller: preserve timebase and reject unsupported input."""
from types import SimpleNamespace

import pytest
import torch


def setup_detector(monkeypatch, tmp_path):
    from wsl2_audio import process_audio as worker
    import hashlib
    import transformers
    (tmp_path / 'model.safetensors').write_bytes(b'fixture')
    monkeypatch.setattr(hashlib, 'sha256', lambda _: SimpleNamespace(
        hexdigest=lambda: 'c074d86335b3b794f8fa5edc25594558f128bdb3914d27806a3a5a2e44963cb6'))
    calls = []
    class Inputs(dict):
        def to(self, *a, **kw): return self
        @property
        def attention_mask(self): return self['attention_mask']
    class Processor:
        feature_extractor = SimpleNamespace(hop_length=160, sampling_rate=16000)
        def __call__(self, audio, **kw):
            count = (len(audio)+159)//160
            mask = torch.ones(1, count+1)
            mask[:, -1] = 0
            return Inputs(attention_mask=mask)
    class Model:
        config = SimpleNamespace(model_type='nemotron3_diarization', chunk_length=340)
        def to(self, *a, **kw): return self
        def eval(self): return self
        def __call__(self, **inputs):
            calls.append(inputs['attention_mask'].shape[1])
            scores = torch.full((1, calls[-1], 8), -10.)
            scores[:, 6000:6002, :2] = 10.  # Exact input time 60.00–60.02 s.
            scores[:, -1, :2] = 10.  # Padding cannot become an event.
            return SimpleNamespace(logits=scores)
    monkeypatch.setattr(transformers.AutoModelForAudioFrameClassification, 'from_pretrained',
        lambda *a, **kw: (Model(), {}))
    monkeypatch.setattr(transformers.AutoProcessor, 'from_pretrained', lambda *a, **kw: Processor())
    monkeypatch.setattr(worker, 'clear_gpu_memory', lambda: None)
    return worker, calls


def test_native_chunked_candidate_accepts_long_input_without_time_reset(monkeypatch, tmp_path):
    worker, calls = setup_detector(monkeypatch, tmp_path)
    result = worker._detect_additional_overlap(torch.zeros(1, 61*16000), 16000, str(tmp_path), 'cpu')
    assert calls == [6101]
    assert result['intervals'] == [{'start': 60., 'end': 60.02}]
    assert result['identity_claim'] is False


def test_candidate_refuses_beyond_tested_limit_before_inference(monkeypatch, tmp_path):
    worker, calls = setup_detector(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match='300 seconds'):
        worker._detect_additional_overlap(torch.zeros(1, 300*16000+1), 16000, str(tmp_path), 'cpu')
    assert calls == []
