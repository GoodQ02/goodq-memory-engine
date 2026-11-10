from copy import deepcopy

import pytest

from tests.unit.test_audio_engine_enrichment import inputs
from tests.unit.test_audio_engine_recording_call import Recognizer, profile, make_request, ffmpeg, verify_test_assets
from wsl2_audio import enrichment_models, recording_engine as engine


class SpeechRecognizer(Recognizer):
    def observe(self, *args):
        observed = super().observe(*args)
        candidate, _ = inputs()
        u = deepcopy(candidate['utterances'][0])
        for key in ('id', 'eligibility', 'channel'):
            u.pop(key, None)
        observed['utterances'] = [u]
        return observed


class Observers:
    fail = None
    crying = False
    calls = []

    def __init__(self, profile, evidence, recording):
        self.evidence = evidence
        assert recording['source']['pcm_sha256'] == evidence['source']['pcm_sha256']

    def spec(self, name):
        return {'id': 'fixture-model', 'revision': 'fixture-revision', 'sha256': 'e'*64}

    def verify(self, name):
        if self.fail == name:
            raise ValueError('injected missing stage')

    def observe(self, name, previous):
        self.calls.append(name)
        _, observations = inputs()
        observation = deepcopy(observations[name])
        if name == 'acoustic_events':
            if self.crying:
                observation['events'] = [{'id': 'cry', 'label': 'crying', 'status': 'observed', 'channel': 0,
                    'span': {'start': 2000, 'end': 18000}}]
        return observation

    def vocal_delivery(self, utterances):
        self.calls.append('vocal_delivery')
        return {'results': [{'utterance_id': u['id'], 'span': u['span'], 'channel': u['channel'], 'model_id': 'fixture-model',
                 'scores': {'cheerful': .8, 'neutral': .2}, 'label': 'cheerful',
                 'status': 'uncertain', 'qualification': 'unqualified'} for u in utterances], 'errors': []}


def setup_call(tmp_path, ffmpeg, monkeypatch, recognizer=None):
    req = make_request(tmp_path, ffmpeg, count=32000)
    config = profile()
    config.update(window={'core_seconds': 20, 'context_seconds': 5}, enrichment={'device': 'cpu'})
    monkeypatch.setattr(engine, 'load_recognizer', lambda *args: recognizer or SpeechRecognizer())
    monkeypatch.setattr(enrichment_models, 'RecordingObservers', Observers)
    monkeypatch.setattr(Observers, 'calls', [])
    monkeypatch.setattr(Observers, 'fail', None)
    monkeypatch.setattr(Observers, 'crying', False)
    return req, config


def test_real_recording_caller_uses_one_decode_then_admits_the_full_clear_phrase(tmp_path, ffmpeg, monkeypatch):
    req, config = setup_call(tmp_path, ffmpeg, monkeypatch)
    calls = []
    prepare = engine.prepare_recording
    def counted(*args):
        calls.append(True)
        return prepare(*args)
    monkeypatch.setattr(engine, 'prepare_recording', counted)
    result = engine.analyze_recording(req, config, tmp_path/'out')
    assert len(calls) == 1
    assert result['vocal_delivery'][0]['span'] == result['utterances'][0]['span']
    assert result['vocal_delivery'][0]['status'] == 'uncertain'
    assert result['stages']['voice_samples']['reason'] == 'scene_ownership_not_projected'
    assert Observers.calls == ['speaker_activity', 'overlap', 'phrase_activity', 'acoustic_events', 'vocal_delivery']


def test_recording_caller_retains_late_acoustic_veto_before_envelope_resolution(tmp_path, ffmpeg, monkeypatch):
    from tests.unit.test_audio_engine_envelopes import coarse_sample

    class CoarseRecognizer(Recognizer):
        def observe(self, *args):
            observed = super().observe(*args)
            evidence, _ = coarse_sample()
            unit = deepcopy(evidence['utterances'][0])
            for key in ('id', 'eligibility', 'channel', 'observation_ids'):
                unit.pop(key, None)
            observed['utterances'] = [unit]
            return observed

    class EventObservers(Observers):
        def observe(self, name, prior):
            self.calls.append(name)
            observation = deepcopy(coarse_sample()[1][name])
            if name == 'acoustic_events':
                observation['events'] = [{'id':'cry','label':'crying','span':{'start':23000,'end':25000},
                                          'channel':0,'status':'observed'}]
            return observation

    recognizer = CoarseRecognizer()
    request, config = setup_call(tmp_path, ffmpeg, monkeypatch, recognizer)
    monkeypatch.setattr(enrichment_models, 'RecordingObservers', EventObservers)
    result = engine.analyze_recording(request, config, tmp_path/'out')
    assert result['sound_events'][0]['label'] == 'crying'
    assert result['utterances'][0]['span'] == coarse_sample()[0]['utterances'][0]['span']
    assert not result['vocal_delivery'] and not result['voice_sample_candidates']
    assert result['utterances'][0]['eligibility']['voice_sample']['status'] == 'ineligible'
    Observers.calls.clear()
    assert engine.analyze_recording(request, config, tmp_path/'out') == result
    assert not Observers.calls and len(recognizer.calls) == 1


def test_recording_caller_observes_acoustics_before_partitioning_individual_inputs_without_second_asr(tmp_path, ffmpeg, monkeypatch):
    from tests.unit.test_audio_engine_phrases import block

    class BlockRecognizer(Recognizer):
        def observe(self, *args):
            observation = super().observe(*args)
            evidence, _ = block()
            unit = deepcopy(evidence['utterances'][0])
            for key in ('id', 'eligibility', 'channel'):
                unit.pop(key, None)
            observation['utterances'] = [unit]
            observation['speech_activity']['spans'] = [{'start': 1000, 'end': 24000}]
            return observation

    class BlockObservers(Observers):
        def observe(self, name, previous):
            self.calls.append(name)
            _, observations = block()
            row = deepcopy(observations[name])
            if name == 'acoustic_events':
                assert len(self.evidence['utterances']) == 1
            return row

    recognizer = BlockRecognizer()
    req, config = setup_call(tmp_path, ffmpeg, monkeypatch, recognizer)
    monkeypatch.setattr(enrichment_models, 'RecordingObservers', BlockObservers)
    result = engine.analyze_recording(req, config, tmp_path/'out')
    assert len(result['utterances']) == 3
    question = next(u for u in result['utterances'] if u['text'] == 'Is this clear?')
    assert question['words'][-1]['span'] is None
    assert next(v for v in result['vocal_delivery'] if v['utterance_id'] == question['id'])['span'] == question['span']
    assert len(recognizer.calls) == 1
    Observers.calls.clear()
    replay = engine.analyze_recording(req, config, tmp_path/'out')
    assert replay == result and not Observers.calls and len(recognizer.calls) == 1


def test_sound_event_survives_failed_recognition_through_recording_caller(tmp_path, ffmpeg, monkeypatch):
    req, config = setup_call(tmp_path, ffmpeg, monkeypatch, Recognizer(fail_index=0))
    monkeypatch.setattr(Observers, 'crying', True)
    result = engine.analyze_recording(req, config, tmp_path/'out')
    assert result['status'] == 'partial'
    assert not result['utterances'] and not result['vocal_delivery']
    assert result['sound_events'][0]['label'] == 'crying'
    assert 'vocal_delivery' not in Observers.calls


def test_one_detector_failure_preserves_other_observations_and_withholds_individual_use(tmp_path, ffmpeg, monkeypatch):
    req, config = setup_call(tmp_path, ffmpeg, monkeypatch)
    monkeypatch.setattr(Observers, 'fail', 'overlap')
    monkeypatch.setattr(Observers, 'crying', True)
    result = engine.analyze_recording(req, config, tmp_path/'out')
    assert result['stages']['overlap']['status'] == 'error'
    assert result['sound_events'][0]['label'] == 'crying'
    assert result['utterances'] and not result['vocal_delivery']


def test_recognition_recovery_reuses_recording_acoustics_without_repeating_independent_observers(tmp_path, ffmpeg, monkeypatch):
    req, config = setup_call(tmp_path, ffmpeg, monkeypatch, Recognizer(fail_index=0))
    first = engine.analyze_recording(req, config, tmp_path/'out')
    assert not first['utterances']
    Observers.calls.clear()
    monkeypatch.setattr(engine, 'load_recognizer', lambda *args: SpeechRecognizer())
    recovered = engine.analyze_recording(req, config, tmp_path/'out')
    assert recovered['vocal_delivery']
    assert Observers.calls == ['vocal_delivery']


def test_cached_success_does_not_rescore_vocal_delivery(tmp_path, ffmpeg, monkeypatch):
    req, config = setup_call(tmp_path, ffmpeg, monkeypatch)
    first = engine.analyze_recording(req, config, tmp_path/'out')
    Observers.calls.clear()
    second = engine.analyze_recording(req, config, tmp_path/'out')
    assert second == first
    assert Observers.calls == []


def test_optional_observer_setup_failure_preserves_recognition(tmp_path, ffmpeg, monkeypatch):
    req, config = setup_call(tmp_path, ffmpeg, monkeypatch)
    def unavailable(*args):
        raise ValueError('optional runtime unavailable')
    monkeypatch.setattr(enrichment_models, 'RecordingObservers', unavailable)
    result = engine.analyze_recording(req, config, tmp_path/'out')
    assert result['status'] == 'partial'
    assert result['utterances'][0]['text'] == 'Yay Joe'
    assert result['stages']['speaker_activity']['status'] == 'unavailable'


def test_real_zero_recording_keeps_all_inference_as_supported_absence(tmp_path, ffmpeg, monkeypatch):
    req = make_request(tmp_path, ffmpeg, count=32000, silent=True)
    config = profile()
    config['enrichment'] = {'device': 'cpu', 'models': {}, 'runtime_packages': {}}
    monkeypatch.setattr(engine, 'load_recognizer', lambda *a: pytest.fail('inference on digital silence'))
    result = engine.analyze_recording(req, config, tmp_path/'out')
    assert result['status'] == 'not_applicable'
    assert not result['sound_events'] and not result['vocal_delivery']
    assert all(s['status'] == 'not_applicable' for s in result['stages'].values())


@pytest.mark.parametrize('corruption', ['different_span', 'ineligible_utterance', 'claimed_qualified', 'unknown_model'])
def test_stored_vocal_output_cannot_bypass_gate_or_input_identity(tmp_path, ffmpeg, monkeypatch, corruption):
    from wsl2_audio.evidence_contract import validate_evidence
    req, config = setup_call(tmp_path, ffmpeg, monkeypatch)
    result = engine.analyze_recording(req, config, tmp_path/'out')
    row = result['vocal_delivery'][0]
    if corruption == 'different_span':
        row['span'] = {'start': 1100, 'end': 20000}
    elif corruption == 'ineligible_utterance':
        row['utterance_id'] = 'another-unit'
    elif corruption == 'claimed_qualified':
        row['status'] = 'qualified'
    else:
        row['model_id'] = 'unknown'
    with pytest.raises(ValueError):
        validate_evidence(result)
