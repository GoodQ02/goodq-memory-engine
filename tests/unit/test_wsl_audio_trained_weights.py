"""Exercise the worker with real, tiny legacy-format local checkpoints."""
from __future__ import annotations

import types
from pathlib import Path

import pytest
import torch
from safetensors.torch import save_file
from transformers import Wav2Vec2Config, Wav2Vec2FeatureExtractor, Wav2Vec2Model


@pytest.fixture
def worker_checkpoints(monkeypatch, tmp_path):
    from wsl2_audio import process_audio as mod

    torch.manual_seed(71)
    hub = tmp_path / "hub"
    labels = dict(enumerate(["angry", "calm", "disgust", "fearful", "happy", "neutral", "sad", "surprised"]))
    expected = {}
    for repo, revision, emotion in [
        ("ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition", "a" * 40, True),
        ("facebook/wav2vec2-base-960h", "22aad52d435eb6dbaf354bdad9b0da84ce7d6156", False),
    ]:
        root = hub / ("models--" + repo.replace("/", "--"))
        snapshot = root / "snapshots" / revision
        snapshot.mkdir(parents=True)
        (root / "refs").mkdir()
        (root / "refs" / "main").write_text(revision)
        cfg = Wav2Vec2Config(
            hidden_size=8, num_hidden_layers=1, num_attention_heads=2,
            intermediate_size=16, conv_dim=[4], conv_stride=[2], conv_kernel=[3],
            num_conv_pos_embeddings=16, num_conv_pos_embedding_groups=2,
            hidden_dropout=0, attention_dropout=0, activation_dropout=0,
            feat_proj_dropout=0, mask_time_prob=0.0, mask_feature_prob=0.0,
            id2label=labels, label2id={v: k for k, v in labels.items()},
            pooling_mode="mean", final_dropout=0,
        )
        cfg.save_pretrained(snapshot)
        extractor = Wav2Vec2FeatureExtractor()
        extractor.save_pretrained(snapshot)
        encoder = Wav2Vec2Model(cfg).eval()
        # The installed checkpoints predate PyTorch's parametrization key names.
        state = {"wav2vec2." + k.replace("parametrizations.weight.original0", "weight_g")
                 .replace("parametrizations.weight.original1", "weight_v"): v.contiguous()
                 for k, v in encoder.state_dict().items()}
        if emotion:
            dense = torch.nn.Linear(8, 8).eval()
            output = torch.nn.Linear(8, 8).eval()
            with torch.no_grad():
                output.bias[3] = 4.0
            for prefix, layer in [("classifier.dense", dense), ("classifier.output", output)]:
                state[prefix + ".weight"] = layer.weight.detach().contiguous()
                state[prefix + ".bias"] = layer.bias.detach().contiguous()
            expected["emotion_head"] = (dense, output)
            expected["emotion_file"] = snapshot / "model.safetensors"
        else:
            expected["embedding_file"] = snapshot / "model.safetensors"
            # An unused CTC head is legitimate when taking encoder features.
            state["lm_head.weight"] = torch.zeros(32, 8)
            state["lm_head.bias"] = torch.zeros(32)
        save_file(state, str(snapshot / "model.safetensors"), metadata={"format": "pt"})
        expected["emotion_encoder" if emotion else "encoder"] = encoder
        expected["extractor"] = extractor

    waveform = torch.sin(torch.arange(800) * 0.07).reshape(1, -1)
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"fixture")

    class Whisper:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            return iter([types.SimpleNamespace(start=0, end=0.04, text="retained words", avg_logprob=-0.1)]), types.SimpleNamespace(language="en", language_probability=1.0)

    monkeypatch.setattr(mod, "_load_runtime_config", lambda: {
        "gpu": {"device": "cpu"}, "diarization": {"enabled": False},
        "models": {"whisper": "medium"}, "processing": {}, "_sources": [],
    })
    monkeypatch.setattr(mod, "require_gpu", lambda: False)
    monkeypatch.setattr(mod, "resolve_wsl_gpu_config", dict)
    monkeypatch.setattr(mod.torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(mod.torchaudio, "load", lambda _: (waveform, 16000))
    monkeypatch.setattr(mod, '_source_speech_regions', lambda audio: [{'start': 0, 'end': len(audio)}])
    monkeypatch.setattr(mod, "WhisperModel", Whisper)
    monkeypatch.setattr(mod, "clear_gpu_memory", lambda: None)
    monkeypatch.setattr(mod, "_resolve_hf_cache_dir", lambda: str(hub))
    # These tiny-checkpoint tests isolate trained-weight loading. The acoustic
    # selector has its own real-interval tests; its fixture admits this tiny input.
    expected['real_prepare_inputs'] = mod.acoustic_events.prepare_inputs
    monkeypatch.setattr(mod.acoustic_events, "prepare_inputs", lambda *a, **kw: {
        "sound_events": [], "sound_event_meta": {"status": "success"},
        "emotion_input": {"policy": "clear_speech_only_v1", "status": "ready",
                          "selected": [{"start": 0, "end": .05, "speaker": "speaker_0"}],
                          "phrase_selection": {"selected": [{"start": 0, "end": .05, "speaker": "speaker_0"}]}}})
    monkeypatch.setattr(mod.model_cache, "is_offline_mode", lambda: True)
    monkeypatch.setattr(mod.model_cache, "check_whisper_cache", lambda _: True)
    monkeypatch.setattr(mod.model_cache, "check_hf_model_cache", lambda _: True)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.delenv("GOODQ_WAV2VEC2_BASE_REVISION", raising=False)
    expected.update(mod=mod, audio=audio, out=tmp_path / "out", waveform=waveform)
    return expected


@pytest.mark.parametrize('overlap_mode', ['multiple_labels', 'single_label', 'unavailable', 'additional', 'additional_error'])
def test_missed_overlap_is_vetoed_before_worker_voice_and_emotion_calls(worker_checkpoints, monkeypatch, overlap_mode):
    """Keep the real admission and inference callers; stub only model observations."""
    import json
    import numpy as np
    f = worker_checkpoints
    mod = f['mod']
    monkeypatch.setattr(mod.acoustic_events, 'prepare_inputs', f['real_prepare_inputs'])
    monkeypatch.setattr(mod.torchaudio, 'load', lambda _: (torch.ones(1, 96000), 16000))
    config = mod._load_runtime_config()
    config['diarization']['enabled'] = True
    if overlap_mode.startswith('additional'):
        config['diarization']['additional_overlap_model'] = 'isolated-fixture'
        def extra(*args):
            if overlap_mode == 'additional_error':
                raise RuntimeError('Additional detector unavailable')
            return {'status': 'ok', 'policy': 'nemotron3_overlap_exclusion_v1',
                    'intervals': [{'start': .85, 'end': 1.}, {'start': 3.85, 'end': 4.}]}
        monkeypatch.setattr(mod, '_detect_additional_overlap', extra)
    monkeypatch.setattr(mod, '_load_runtime_config', lambda: config)
    monkeypatch.setattr(mod, 'DIARIZATION_AVAILABLE', True)
    monkeypatch.setattr(mod, 'DiarizationPipeline', object, raising=False)
    monkeypatch.setenv('HF_TOKEN', 'fixture-token')
    monkeypatch.setattr(mod.model_cache, 'check_pyannote_cache', lambda _: True)

    class Whisper:
        def __init__(self, *args, **kwargs): pass
        def transcribe(self, *args, **kwargs):
            segments = []
            for offset in (0, 3):
                words = [types.SimpleNamespace(word=text, start=offset+start, end=offset+end, probability=.95)
                         for text, start, end in [("Don't", .2, .7), ('forget', .7, 1.2),
                                                   ('a', 1.2, 1.7), ('jacket.', 1.7, 2.2)]]
                segments.append(types.SimpleNamespace(start=offset+.2, end=offset+2.2,
                    text="Don't forget a jacket.", words=words, avg_logprob=-.1))
            return iter(segments), types.SimpleNamespace(language='en', language_probability=1.)
    monkeypatch.setattr(mod, 'WhisperModel', Whisper)

    class Pipeline:
        _segmentation = types.SimpleNamespace(model=types.SimpleNamespace(
            receptive_field=types.SimpleNamespace(start=0, duration=.1, step=.1)))
        def to(self, device): pass
        def reconstruct(self, segments, clusters, count): return self
        def __call__(self, audio):
            if overlap_mode == 'unavailable': return self
            data = np.zeros((1, 60, 2))
            data[:, :, 0] = 1
            if overlap_mode == 'single_label':
                data[0, 8:10, 1] = data[0, 38:40, 1] = 1
            return self.reconstruct(types.SimpleNamespace(data=data, sliding_window=[
                types.SimpleNamespace(start=0, end=6)]), np.zeros((1, 2), dtype=int), None)
        def itertracks(self, yield_label=False):
            for offset in (0, 3):
                for start, end, speaker in [(0, 1.2, 'A'), (1.2, 2.5, 'B')]:
                    label = speaker if overlap_mode == 'multiple_labels' else 'A'
                    yield types.SimpleNamespace(start=offset+start, end=offset+end), None, label
    monkeypatch.setattr(mod, '_load_pyannote_pipeline', lambda *a, **kw: Pipeline())

    def acoustics(*args, speech_intervals, emotion_phrases, **kwargs):
        window = lambda row: {**row, 'speech_score': 1., 'vad_speech_coverage': 1., 'excluded_labels': []}
        return [{'label': 'crying', 'start': 0, 'end': 6}], {
            'status': 'success', 'speech_presence': {'status': 'success', 'regions': [{'start': 0, 'end': 6}]},
            'speech_windows': [window(s) for s in speech_intervals],
            'phrase_windows': [window(s) for s in emotion_phrases]}
    monkeypatch.setattr(mod.acoustic_events, 'detect_sound_events', acoustics)
    select = mod._select_speaker_signature_segments
    monkeypatch.setattr(mod, '_select_speaker_signature_segments', lambda turns, **kw: select(
        turns, min_total_seconds=1., min_segment_seconds=.2, **kw))
    monkeypatch.setattr(mod, '_SPEAKER_SIGNATURE_MIN_SEGMENT_SECONDS', .2)
    monkeypatch.setattr(mod, '_SPEAKER_SIGNATURE_MIN_TOTAL_SECONDS', 1.)
    calls = []
    class Encoder:
        def encode_batch(self, waveform):
            calls.append('voice')
            return torch.ones(1, 1, 192)
    monkeypatch.setattr(mod.speaker_signature, 'load_encoder', lambda *a: Encoder())
    def emotion_load(*args, **kwargs):
        calls.append('emotion')
        raise AssertionError('Mixed speech must not reach the emotion model')
    monkeypatch.setattr(mod, '_load_trained_wav2vec', emotion_load)
    result = mod.process_audio(str(f['audio']), str(f['out']))
    assert result['status'] == 'success'
    assert calls == []
    assert result['emotion_input']['selected'] == []
    failed_observation = overlap_mode in ('unavailable', 'additional_error')
    assert result['emotion_status'] == ('error' if failed_observation else 'insufficient_evidence')
    assert not result['speaker_voice_signatures'] and not result['emotion_segments']
    assert len(result['emotion_input']['speaker_purity']['excluded_phrases']) == (0 if failed_observation else 2)
    assert result['sound_events'][0]['label'] == 'crying'
    stored = json.loads((f['out'] / 'result.json').read_text(encoding='utf-8'))
    assert stored['emotion_input'] == result['emotion_input']
    assert len(stored['word_timestamps']) == 8


def test_worker_uses_trained_emotion_head_and_legacy_encoder_weights(worker_checkpoints):
    f = worker_checkpoints
    result = f["mod"].process_audio(str(f["audio"]), str(f["out"]))
    inputs = f["extractor"](f["waveform"].numpy().flatten(), sampling_rate=16000, return_tensors="pt", padding=True)
    with torch.no_grad():
        features = f["emotion_encoder"](**inputs).last_hidden_state.mean(dim=1)
        dense, output = f["emotion_head"]
        scores = output(torch.tanh(dense(features))).softmax(dim=-1)[0]
    assert result["emotion_status"] == "success"
    assert result["emotion"] is None and result["emotion_scores"] == {}
    assert result["emotion_segments"][0]["label"] == "fearful"
    assert result["emotion_segments"][0]["interpretation_status"] == "uncertain"
    assert result["emotion_segments"][0]["scores"] == pytest.approx(dict(zip(f["emotion_encoder"].config.id2label.values(), scores.tolist())), abs=1e-6)
    assert "embeddings" not in result
    assert result["embeddings_status"] == "retired"
    assert result["emotion_model_load"]["missing_inference_keys"] == []
    assert "embedding_model_load" not in result


def test_worker_scores_only_admitted_samples_and_preserves_crying(worker_checkpoints, monkeypatch):
    f = worker_checkpoints
    event = {"start": 0, "end": .01, "label": "crying"}
    monkeypatch.setattr(f['mod'].acoustic_events, 'prepare_inputs', lambda *a, **kw: {
        'sound_events': [event], 'sound_event_meta': {'status': 'success'},
        'emotion_input': {'policy': 'clear_speech_only_v1', 'status': 'ready',
                          'selected': [{'start': .01, 'end': .04, 'speaker': 'S0'}],
                          'phrase_selection': {'selected': [{'start': .01, 'end': .04, 'speaker': 'S0'}]}}})
    result = f['mod'].process_audio(str(f['audio']), str(f['out']))
    inputs = f['extractor'](f['waveform'][:, 160:640].numpy().flatten(), sampling_rate=16000,
                            return_tensors='pt', padding=True)
    with torch.no_grad():
        features = f['emotion_encoder'](**inputs).last_hidden_state.mean(dim=1)
        dense, output = f['emotion_head']
        expected = output(torch.tanh(dense(features))).softmax(dim=-1)[0].tolist()
    segment = result['emotion_segments'][0]
    assert segment['scores'] == pytest.approx(dict(zip(f['emotion_encoder'].config.id2label.values(), expected)), abs=1e-6)
    assert (segment['sample_start'], segment['sample_end']) == (160, 640)
    assert result['sound_events'] == [event]
    assert result['emotion'] is None and result['emotion_scores'] == {}


def test_worker_rejects_missing_trained_head_without_losing_transcript(worker_checkpoints):
    from safetensors.torch import load_file
    f = worker_checkpoints
    state = {k: v.clone() for k, v in load_file(str(f["emotion_file"])).items()}
    del state["classifier.output.weight"]
    save_file(state, str(f["emotion_file"]), metadata={"format": "pt"})
    result = f["mod"].process_audio(str(f["audio"]), str(f["out"]))
    assert result["emotion_status"] == "error"
    assert "classifier.output.weight" in result["emotion_error"]
    assert result["emotion"] is None and result["emotion_segments"] == []
    assert result["transcription"] == "retained words"
    assert result["embeddings_status"] == "retired"


def test_worker_never_scores_a_fragment_when_complete_phrase_is_withheld(worker_checkpoints, monkeypatch):
    f = worker_checkpoints
    monkeypatch.setattr(f['mod'].acoustic_events, 'prepare_inputs', lambda *a, **kw: {
        'sound_events': [{'label':'crying','start':0,'end':.01}], 'sound_event_meta': {'status':'success'},
        'emotion_input': {'policy':'clear_speech_only_v2', 'status':'ready',
            'selected':[{'start':.01,'end':.04,'speaker':'S0'}],
            'phrase_selection':{'policy':'complete_observed_phrases_v1','selected':[],
                                'rejected':[{'reason':'phrase_speakers_unresolved'}]}}})
    def forbidden(*args, **kwargs):
        raise AssertionError('An incomplete phrase reached emotion model loading')
    monkeypatch.setattr(f['mod'], '_load_trained_wav2vec', forbidden)
    result = f['mod'].process_audio(str(f['audio']), str(f['out']))
    assert result['emotion_status'] == 'insufficient_evidence'
    assert result['emotion_note'] == 'no_complete_supported_phrase'
    assert not result['emotion_segments'] and result['sound_events'][0]['label'] == 'crying'


def test_worker_rejects_missing_encoder_weight(worker_checkpoints):
    from safetensors.torch import load_file
    f = worker_checkpoints
    state = {k: v.clone() for k, v in load_file(str(f["emotion_file"])).items()}
    del state["wav2vec2.encoder.pos_conv_embed.conv.weight_v"]
    save_file(state, str(f["emotion_file"]), metadata={"format": "pt"})
    result = f["mod"].process_audio(str(f["audio"]), str(f["out"]))
    assert result["emotion_status"] == "error"
    assert result["emotion"] is None and result["emotion_segments"] == []


def test_worker_does_not_load_unused_base_model_without_diarization(worker_checkpoints):
    from safetensors.torch import load_file
    f = worker_checkpoints
    state = {k: v.clone() for k, v in load_file(str(f["embedding_file"])).items()}
    del state["wav2vec2.encoder.pos_conv_embed.conv.weight_v"]
    save_file(state, str(f["embedding_file"]), metadata={"format": "pt"})
    result = f["mod"].process_audio(str(f["audio"]), str(f["out"]))
    assert result["embeddings_status"] == "retired"
    assert "embeddings" not in result
    assert result["speaker_voice_signatures"] == []
    assert result["transcription_status"] == "success"
    assert result["emotion_status"] == "success"

@pytest.mark.parametrize("broken_ecapa", [False, True])
def test_retired_global_vector_preserves_ecapa_caller(worker_checkpoints, monkeypatch, broken_ecapa):
    f = worker_checkpoints
    mod = f["mod"]
    config = mod._load_runtime_config()
    config["diarization"]["enabled"] = True
    monkeypatch.setattr(mod, "_load_runtime_config", lambda: config)
    monkeypatch.setattr(mod, "DIARIZATION_AVAILABLE", True)
    monkeypatch.setattr(mod, "DiarizationPipeline", object, raising=False)
    monkeypatch.setenv("HF_TOKEN", "fixture-token")
    monkeypatch.setattr(mod.model_cache, "check_pyannote_cache", lambda _: True)

    class Pipeline:
        def to(self, device): pass
        def __call__(self, audio): return self
        def itertracks(self, yield_label=False):
            yield types.SimpleNamespace(start=0, end=0.02), None, "speaker_0"
            yield types.SimpleNamespace(start=0.02, end=0.04), None, "speaker_0"

    monkeypatch.setattr(mod, "_load_pyannote_pipeline", lambda *a, **kw: Pipeline())
    # Small deterministic local model fixture; preserve the real signature inference/aggregation.
    monkeypatch.setattr(mod, "_select_speaker_signature_segments", lambda segments, **kwargs: [{
        "speaker": "speaker_0", "selected_segments": [
            {"start": 0, "end": .02, "duration": .02},
            {"start": .02, "end": .04, "duration": .02}],
    }])
    monkeypatch.setattr(mod, "_SPEAKER_SIGNATURE_MIN_SEGMENT_SECONDS", 0.01)
    monkeypatch.setattr(mod, "_SPEAKER_SIGNATURE_MIN_TOTAL_SECONDS", 0.03)
    forward_lengths = []
    class Encoder:
        def encode_batch(self, waveform):
            forward_lengths.append(waveform.shape[-1])
            return torch.arange(1, 193, dtype=torch.float32).reshape(1, 1, -1)
    def load(*args):
        if broken_ecapa:
            raise OSError("ECAPA fixture weights unavailable")
        return Encoder()
    monkeypatch.setattr(mod.speaker_signature, "load_encoder", load)
    result = mod.process_audio(str(f["audio"]), str(f["out"]))
    assert result["emotion_status"] == "success"
    assert result["transcription"] == "retained words"
    assert result["embeddings_status"] == "retired"
    assert "embeddings" not in result and "embedding_dim" not in result
    if broken_ecapa:
        assert result["speaker_voice_signature_meta"]["status"] == "error"
        assert result["speaker_voice_signatures"] == []
    else:
        assert forward_lengths == [640]  # Joined selected spans; no whole-scene forward.
        assert len(result["speaker_voice_signatures"]) == 1
        assert len(result["speaker_voice_signatures"][0]["embedding"]) == 192
        assert result["speaker_voice_signatures"][0]["embedding_space"] == mod.speaker_signature.SPACE
    import json
    persisted = json.loads((f["out"] / "result.json").read_text())
    assert persisted["embeddings_status"] == "retired"
    assert "embeddings" not in persisted

@pytest.mark.parametrize("enough_clean", [False, True])
def test_overlap_admission_through_worker_and_persisted_result(worker_checkpoints, monkeypatch, enough_clean):
    import json
    f = worker_checkpoints
    mod = f['mod']
    config = mod._load_runtime_config()
    config['diarization']['enabled'] = True
    monkeypatch.setattr(mod, '_load_runtime_config', lambda: config)
    monkeypatch.setattr(mod, 'DIARIZATION_AVAILABLE', True)
    monkeypatch.setattr(mod, 'DiarizationPipeline', object, raising=False)
    monkeypatch.setenv('HF_TOKEN', 'fixture-token')
    monkeypatch.setattr(mod.model_cache, 'check_pyannote_cache', lambda _: True)
    turns = [(0, .012, 'speaker_0'), (.004, .005, 'speaker_1'), (.012, .025, 'speaker_0')]
    if enough_clean:
        turns.append((.026, .039, 'speaker_0'))
    class Pipeline:
        def to(self, device): pass
        def __call__(self, audio): return self
        def itertracks(self, yield_label=False):
            for start, end, label in turns:
                yield types.SimpleNamespace(start=start, end=end), None, label
    monkeypatch.setattr(mod, '_load_pyannote_pipeline', lambda *a, **kw: Pipeline())
    select = mod._select_speaker_signature_segments
    monkeypatch.setattr(mod, '_select_speaker_signature_segments', lambda turns, **kw: select(
        turns, min_total_seconds=.02, min_segment_seconds=.005, **kw))
    monkeypatch.setattr(mod, '_SPEAKER_SIGNATURE_MIN_SEGMENT_SECONDS', .005)
    monkeypatch.setattr(mod, '_SPEAKER_SIGNATURE_MIN_TOTAL_SECONDS', .02)
    calls = []
    class Encoder:
        def encode_batch(self, waveform):
            calls.append(waveform.shape[-1])
            return torch.ones(1, 1, 192)
    monkeypatch.setattr(mod.speaker_signature, 'load_encoder', lambda *a: Encoder())
    result = mod.process_audio(str(f['audio']), str(f['out']))
    assert result['emotion_status'] == 'success'
    assert result['transcription'] == 'retained words'
    assert len(result['diarization']) == len(turns)
    meta = result['speaker_voice_signature_meta']
    assert len(meta['excluded_segments']) == 2  # Short overlapping interjection also counts.
    if enough_clean:
        assert calls == [416]
        sig = result['speaker_voice_signatures'][0]
        assert [(s['start'], s['end']) for s in sig['selected_segments']] == [(.012, .025), (.026, .039)]
        assert sig['excluded_segments'][0]['start'] == 0
    else:
        assert not calls and not result['speaker_voice_signatures']
        assert meta['reason'] == 'insufficient_unambiguous_speech'
    persisted = json.loads((f['out'] / 'result.json').read_text())
    assert persisted['speaker_voice_signature_meta'] == meta


@pytest.mark.parametrize("eligible,review_error", [(True, False), (False, False), (True, True)])
def test_collapsed_review_worker_to_workbench_without_admission_change(
        worker_checkpoints, monkeypatch, tmp_path, eligible, review_error):
    import json
    import sqlite3
    import numpy as np
    from unittest.mock import patch
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from steps.audio import audio_wsl2_bridge as bridge
    from lib.identity_ledger import _flatten_scene_payload
    from lib.kg_realtime_integration import update_kg_for_scene
    from api.routes import system

    f = worker_checkpoints
    mod = f['mod']
    config = mod._load_runtime_config()
    config['diarization']['enabled'] = True
    monkeypatch.setattr(mod, '_load_runtime_config', lambda: config)
    monkeypatch.setattr(mod, 'DIARIZATION_AVAILABLE', True)
    monkeypatch.setattr(mod, 'DiarizationPipeline', object, raising=False)
    monkeypatch.setenv('HF_TOKEN', 'fixture-token')
    monkeypatch.setattr(mod.model_cache, 'check_pyannote_cache', lambda _: True)
    data = np.zeros((1, 40, 2))
    data[0, :20, 0] = 1
    data[0, 20:25, 1] = .8 if review_error else 1
    data[0, 25:, 0] = 1
    hard = np.zeros((1, 2), dtype=int)
    turns = [(0, .012, 'speaker_0')]
    if eligible:
        turns.append((.015, .039, 'speaker_0'))
    class Pipeline:
        _segmentation = types.SimpleNamespace(model=types.SimpleNamespace(
            receptive_field=types.SimpleNamespace(start=0, duration=.001, step=.001)))
        def to(self, device): pass
        def reconstruct(self, segments, clusters, count): return self
        def __call__(self, audio):
            return self.reconstruct(types.SimpleNamespace(data=data, sliding_window=[
                types.SimpleNamespace(start=0, end=.04)]), hard, None)
        def itertracks(self, yield_label=False):
            for start, end, label in turns:
                yield types.SimpleNamespace(start=start, end=end), None, label
    pipeline = Pipeline()
    monkeypatch.setattr(mod, '_load_pyannote_pipeline', lambda *a, **kw: pipeline)
    selector = mod._select_speaker_signature_segments
    monkeypatch.setattr(mod, '_select_speaker_signature_segments', lambda turns, **kw: selector(
        turns, min_total_seconds=.02, min_segment_seconds=.005, **kw))
    monkeypatch.setattr(mod, '_SPEAKER_SIGNATURE_MIN_SEGMENT_SECONDS', .005)
    monkeypatch.setattr(mod, '_SPEAKER_SIGNATURE_MIN_TOTAL_SECONDS', .02)
    calls = []
    class Encoder:
        def encode_batch(self, waveform):
            calls.append(waveform.shape[-1])
            return torch.ones(1, 1, 192)
    monkeypatch.setattr(mod.speaker_signature, 'load_encoder', lambda *a: Encoder())
    result = mod.process_audio(str(f['audio']), str(f['out']))
    assert 'reconstruct' not in vars(pipeline)  # Process-local observer is restored.
    assert np.array_equal(hard, np.zeros((1, 2), dtype=int))
    assert result['emotion_status'] == 'success'
    assert len(result['diarization']) == len(turns)
    review = result['speaker_change_review']
    assert review['status'] == ('error' if review_error else 'ok')
    if not review_error:
        assert len(review['flags']) == 1
        flag = review['flags'][0]
        assert (flag['start'], flag['end']) == pytest.approx((.020, .025))
        assert flag['identity_claim'] is False and flag['status'] == 'unreviewed'
    else:
        assert review['flags'] == []
    if eligible:
        assert calls == [576]
        sig = result['speaker_voice_signatures'][0]
        assert [(s['start'], s['end']) for s in sig['selected_segments']] == [(0, .012), (.015, .039)]
        assert sig['excluded_segments'] == []
        assert sig['admission_policy'] == 'exclude_overlapping_turns_v1'
        assert sig['embedding'] == pytest.approx([1 / (192 ** .5)] * 192)
    else:
        assert calls == [] and result['speaker_voice_signatures'] == []
    persisted = json.loads((f['out'] / 'result.json').read_text())
    assert persisted['speaker_change_review'] == review
    monkeypatch.setattr(bridge, 'WSL2AudioBridge', lambda: type('Runner', (), {
        'process_audio': lambda self, *a, **kw: persisted})())
    payload = _flatten_scene_payload({'audio': bridge.audio_unified_wsl2('fixture.wav', duration=.04)})
    db = tmp_path / 'review-kg.db'
    cfg = {'paths': {'knowledge_graph_db': str(db)}}
    update_kg_for_scene(payload, 'review-scene', 'video', 'fixture.wav', cfg=cfg)
    update_kg_for_scene({}, 'legacy-scene', 'video', 'legacy.wav', cfg=cfg)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM edges WHERE edge_type='identity_evidence'").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM nodes WHERE node_type='speaker_pattern'").fetchone()[0] == int(eligible)
    app = FastAPI()
    app.include_router(system.router)
    with patch.object(system, '_get_kg_db_path', return_value=db), TestClient(app) as client:
        response = client.get('/api/system/identity/speaker-reviews')
        assert response.status_code == 200
        assert [r['scene_id'] for r in response.json()] == ['review-scene']
        assert response.json()[0]['review'] == review
