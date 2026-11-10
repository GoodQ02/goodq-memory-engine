"""Decode policy across configuration, transport and worker boundaries."""
import json
from unittest.mock import patch

import pytest


@pytest.mark.parametrize('requested,seconds,probability,mode,status,expected', [
    ('en', 2., 1., 'configured', 'configured_not_detected', None),
    (None, 2., .44, 'automatic', 'model_estimate_unreviewed', .44),
    (None, 0., .54, 'automatic', 'not_applicable_no_detected_speech', None),
    ('en', 0., 1., 'configured', 'not_applicable_no_detected_speech', None),
    (None, 2., float('nan'), 'automatic', 'language_evidence_unavailable', None),
])
def test_language_configuration_cannot_masquerade_as_detected_confidence(
        requested, seconds, probability, mode, status, expected):
    from types import SimpleNamespace
    from wsl2_audio.process_audio import _transcription_language_evidence
    evidence = _transcription_language_evidence(SimpleNamespace(
        language='en', language_probability=probability, duration_after_vad=seconds), requested)
    assert evidence['mode'] == mode
    assert evidence['status'] == status
    assert evidence['detection_probability'] == expected
    assert evidence['requested_language'] == requested
    assert evidence['reported_language'] == 'en'
    assert evidence['code_switching_qualified'] is False


def test_effective_options_support_installed_faster_whisper_dataclass():
    from dataclasses import make_dataclass
    from types import SimpleNamespace
    from wsl2_audio.process_audio import _resolved_transcription_options
    Options = make_dataclass('Options', [('temperatures', list)])
    assert _resolved_transcription_options(SimpleNamespace(
        transcription_options=Options([0.]))) == {'temperatures': [0.]}


def test_unified_projection_preserves_legacy_routing_config():
    from steps.audio.audio_wsl2_bridge import unified_transcription_options
    assert unified_transcription_options({'audio': {'transcribe': {
        'use_wsl2': True, 'model': 'small', 'temperature': 0.}}}) == {'transcription_temperature': 0.}


@pytest.mark.parametrize('value', [True, False, -0.1, 1.1, float('nan'), float('inf'), '0', None, [0., .2]])
def test_invalid_temperature_rejected_at_config_and_worker(value):
    from scripts.config_schema import AudioTranscriptionConfig
    from wsl2_audio.process_audio import _transcription_temperature
    with pytest.raises(ValueError):
        AudioTranscriptionConfig.model_validate({'temperature': value})
    with pytest.raises(ValueError):
        _transcription_temperature(value)


def test_unified_bridge_requires_receipt_and_preserves_effective_policy(monkeypatch):
    from steps.audio import audio_wsl2_bridge as mod
    receipt = {'policy': 'single_temperature_v1', 'temperature': 0.,
               'primary': {'temperatures': [0.]}, 'sampling_enabled': False,
               'source_regions': {'policy': 'source_audio_v2'}}
    payload = {'status': 'success', 'transcription': 'hello', 'transcription_status': 'success'}
    class Runner:
        def process_audio(self, path, **kwargs):
            assert kwargs['transcription_temperature'] == 0.
            return payload.copy()
    monkeypatch.setattr(mod, 'WSL2AudioBridge', Runner)
    result = mod.audio_unified_wsl2('clip.wav', **mod.unified_transcription_options({}))
    assert result['status'] == 'error'
    assert result['bridge_error_reason'] == 'transcription_policy_unconfirmed'
    assert result['wsl_capability_outcomes']['transcription']['status'] == 'error'
    payload['transcription_decoding'] = {**receipt, 'temperature': .2}
    assert mod.audio_unified_wsl2('clip.wav', transcription_temperature=0.)['status'] == 'error'
    payload['transcription_decoding'] = receipt
    result = mod.audio_unified_wsl2('clip.wav', transcription_temperature=0.)
    assert result['status'] == 'success'
    assert result['transcript_meta']['transcription_decoding'] == receipt


def test_proxy_forwards_temperature_without_vocabulary():
    from scripts.wsl2_audio_bridge import WSL2AudioBridge
    with patch('scripts.wsl2_audio_bridge.NativeAudioRunner') as runner, patch('sys.platform', 'linux'):
        WSL2AudioBridge().process_audio('clip.wav', transcription_temperature=0.)
    assert runner.return_value.process_audio.call_args.kwargs == {'transcription_temperature': 0.}


def test_cli_temperature_slot_preserves_legacy_vocabulary(monkeypatch, capsys):
    from wsl2_audio import process_audio as mod
    calls = []
    monkeypatch.setattr(mod, 'process_audio', lambda *a, **kw: calls.append(kw) or {'status': 'success'})
    monkeypatch.setattr(mod.sys, 'argv', ['worker', 'clip.wav', 'out', 'null', '0.0'])
    mod.main()
    assert json.loads(capsys.readouterr().out)['status'] == 'success'
    assert calls == [{'transcription_vocabulary': None, 'transcription_temperature': 0.}]


@pytest.mark.parametrize('temperature', [0.0, 0.2])
def test_local_faster_whisper_uses_same_single_temperature(monkeypatch, temperature):
    from dataclasses import make_dataclass
    from types import SimpleNamespace
    from steps.audio_transcribe.step import _transcribe_chunk_fw
    import numpy as np
    monkeypatch.setattr('faster_whisper.audio.decode_audio', lambda *a, **kw: np.ones(16000, dtype=np.float32))
    monkeypatch.setattr('wsl2_audio.transcription_contract._source_speech_regions', lambda _: [{'start': 0, 'end': 16000}])
    Options = make_dataclass('Options', [('temperatures', list)])
    class Model:
        def detect_language(self, **kwargs): return 'en', .9, []
        def transcribe(self, path, **kwargs):
            assert kwargs['temperature'] == temperature
            return [], SimpleNamespace(transcription_options=Options([temperature]))
    result = _transcribe_chunk_fw('clip.wav', 0., Model(), temperature)
    assert result['transcription_decoding']['primary']['temperatures'] == [temperature]
    assert result['transcription_decoding']['temperature_fallback'] is False
