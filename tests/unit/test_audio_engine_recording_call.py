from copy import deepcopy
from pathlib import Path
import subprocess

import pytest

from tests.unit.test_audio_engine_recording import write_pcm, request, ffmpeg
from wsl2_audio import recording_engine as engine
from wsl2_audio.eligibility import POLICY
from wsl2_audio.recording_audio import prepare_recording


class Recognizer:
    def __init__(self, fail_index=None):
        self.calls = []
        self.fail_index = fail_index
        self.models = [{'id': 'test-recognizer', 'revision': 'fixture', 'sha256': 'e'*64},
                       {'id': 'test-vad', 'revision': 'fixture', 'sha256': 'f'*64}]
        self.runtime = {'scope': 'test_adapter'}

    def observe(self, samples, sample_rate, span, language):
        self.calls.append((len(samples), span.start, span.end))
        if len(self.calls)-1 == self.fail_index:
            raise RuntimeError('injected worker failure')
        return {'status': 'ok', 'assessed_spans': [{'start': span.start, 'end': span.end}],
                'speech_activity': {'status': 'ok', 'assessed_spans': [{'start': span.start, 'end': span.end}]},
                'utterances': [], 'unplaced_hypotheses': [], 'raw_segments': []}


def profile():
    return {'schema_version': 1, 'recognizer': {'id': 'test-recognizer', 'revision': 'fixture', 'sha256': 'e'*64},
            'speech_activity_model': {'id': 'test-vad', 'revision': 'fixture', 'sha256': 'f'*64},
            'window': {'core_seconds': 1, 'context_seconds': .25},
            'language': 'en', 'eligibility_policy': deepcopy(POLICY)}


@pytest.fixture(autouse=True)
def verify_test_assets(monkeypatch):
    monkeypatch.setattr(engine, 'verify_recognizer', lambda profile: {
        'models': Recognizer().models, 'runtime': {'scope': 'test_adapter'}})


def make_request(tmp_path, ffmpeg, count=40001, silent=False):
    source = write_pcm(tmp_path/'source.wav', [0 if silent else 1]*count)
    result = request(source, ffmpeg)
    result.update(run_id='test-run', epoch_id='isolated-test')
    return result


def test_actual_recording_caller_is_independent_of_scene_cuts_and_vad_masks(tmp_path, ffmpeg, monkeypatch):
    req = make_request(tmp_path, ffmpeg)
    recognizer = Recognizer()
    monkeypatch.setattr(engine, 'load_recognizer', lambda *args: recognizer)
    result = engine.analyze_recording(req, profile(), tmp_path/'first')
    first_calls = list(recognizer.calls)
    recognizer.calls.clear()
    req['scene_cuts'] = [0, .1, 1.7]
    req['vad_masks'] = []
    again = engine.analyze_recording(req, profile(), tmp_path/'second')
    assert first_calls == recognizer.calls == [(20000, 0, 20000), (24000, 12000, 36000), (12001, 28000, 40001)]
    assert result['coverage'] == again['coverage'] == [{'span': {'start': 0, 'end': 40001}, 'status': 'analyzed'}]
    assert result['utterances'] == again['utterances']


def test_literal_silence_does_not_load_or_call_models(tmp_path, ffmpeg, monkeypatch):
    req = make_request(tmp_path, ffmpeg, silent=True)
    monkeypatch.setattr(engine, 'load_recognizer', lambda *args: pytest.fail('model loaded for literal silence'))
    result = engine.analyze_recording(req, profile(), tmp_path/'artifacts')
    assert result['status'] == 'not_applicable'
    assert result['stages']['recognition']['reason'] == 'digital_silence'
    assert not result['utterances']
    assert result['coverage'] == [{'span': {'start': 0, 'end': 40001}, 'status': 'digital_silence'}]


def test_interrupted_window_reuses_completed_windows_without_semantic_retries(tmp_path, ffmpeg, monkeypatch):
    req = make_request(tmp_path, ffmpeg)
    first = Recognizer(fail_index=1)
    monkeypatch.setattr(engine, 'load_recognizer', lambda *args: first)
    result = engine.analyze_recording(req, profile(), tmp_path/'artifacts')
    assert result['status'] == 'partial'
    assert len(first.calls) == 3
    second = Recognizer()
    monkeypatch.setattr(engine, 'load_recognizer', lambda *args: second)
    resumed = engine.analyze_recording(req, profile(), tmp_path/'artifacts')
    assert second.calls == [(24000, 12000, 36000)]
    assert resumed['status'] == 'ok'


def test_changed_profile_never_reuses_old_recognition(tmp_path, ffmpeg, monkeypatch):
    req = make_request(tmp_path, ffmpeg, count=16000)
    recognizer = Recognizer()
    monkeypatch.setattr(engine, 'load_recognizer', lambda *args: recognizer)
    engine.analyze_recording(req, profile(), tmp_path/'artifacts')
    changed = profile()
    changed['language'] = 'auto'
    engine.analyze_recording(req, changed, tmp_path/'artifacts')
    assert len(recognizer.calls) == 2


def test_vocabulary_profile_binds_recording_provenance_and_invalidates_cache(tmp_path,ffmpeg,monkeypatch):
    req=make_request(tmp_path,ffmpeg,count=16000)
    recognizer=Recognizer()
    monkeypatch.setattr(engine,'load_recognizer',lambda *args:recognizer)
    first=engine.analyze_recording(req,profile(),tmp_path/'artifacts')
    contextual=profile();contextual['vocabulary']=['Joe','Kathi']
    result=engine.analyze_recording(req,contextual,tmp_path/'artifacts')
    assert len(recognizer.calls)==2
    assert result['provenance']['config_sha256']!=first['provenance']['config_sha256']
    assert result['provenance']['transcription_context']=={
        'vocabulary':['Joe','Kathi'],'basis':'explicit_profile_vocabulary','identity_claim':False}
    assert result['eligibility_policy']==first['eligibility_policy']==POLICY


def test_invalid_vocabulary_rejected_even_before_digital_silence_decode(tmp_path,monkeypatch):
    invalid=profile();invalid['vocabulary']='Joe'
    monkeypatch.setattr(engine,'prepare_recording',lambda *args:pytest.fail('invalid profile reached decode'))
    with pytest.raises(ValueError,match='vocabulary'):
        engine.analyze_recording({},invalid,tmp_path)


def test_failed_current_asset_verification_cannot_serve_cached_model_results(tmp_path, ffmpeg, monkeypatch):
    req = make_request(tmp_path, ffmpeg, count=16000)
    recognizer = Recognizer()
    monkeypatch.setattr(engine, 'load_recognizer', lambda *args: recognizer)
    engine.analyze_recording(req, profile(), tmp_path/'artifacts')

    def changed(profile):
        raise ValueError('current model assets changed')

    monkeypatch.setattr(engine, 'verify_recognizer', changed)
    result = engine.analyze_recording(req, profile(), tmp_path/'artifacts')
    assert result['status'] == 'error'
    assert len(recognizer.calls) == 1
    assert not result['utterances']


def test_failed_speech_detector_is_partial_and_recovers_without_repeating_asr(tmp_path, ffmpeg, monkeypatch):
    req = make_request(tmp_path, ffmpeg, count=16000)

    class FailedSpeechActivity(Recognizer):
        def observe(self, *args):
            observed = super().observe(*args)
            observed['speech_activity'] = {'status': 'error', 'reason': 'injected_detector_failure',
                                           'assessed_spans': [], 'spans': []}
            return observed

    recognizer = FailedSpeechActivity()
    monkeypatch.setattr(engine, 'load_recognizer', lambda *args: recognizer)
    first = engine.analyze_recording(req, profile(), tmp_path/'artifacts')
    assert first['status'] == 'partial'
    calls = []

    def refresh(observed, samples, sample_rate, context):
        calls.append(context)
        observed = deepcopy(observed)
        observed['speech_activity'] = {'status': 'ok', 'assessed_spans': [vars(context)], 'spans': [vars(context)]}
        return observed

    monkeypatch.setattr(engine, 'refresh_speech_activity', refresh)
    monkeypatch.setattr(engine, 'load_recognizer', lambda *args: pytest.fail('completed ASR was repeated'))
    second = engine.analyze_recording(req, profile(), tmp_path/'artifacts')
    assert second['status'] == 'ok'
    assert len(recognizer.calls) == len(calls) == 1


def test_failed_stereo_channel_preserves_supported_words_on_the_successful_channel(tmp_path, ffmpeg, monkeypatch):
    source = write_pcm(tmp_path/'stereo.wav', [100, 200]*16000, channels=2)
    req = request(source, ffmpeg)
    req.update(run_id='test-stereo', epoch_id='isolated-test')

    class PartialChannels(Recognizer):
        def observe(self, *args):
            observed = super().observe(*args)
            if len(self.calls) == 2:
                raise RuntimeError('second channel failed')
            observed['utterances'] = [{
                'text': 'hello', 'span': {'start': 1600, 'end': 12000},
                'words': [{'text': 'hello', 'span': {'start': 2000, 'end': 10000}, 'timing': 'supported'}],
                'completeness': 'unresolved', 'speaker': {'status': 'unresolved', 'id': None},
                'language': {'status': 'unresolved', 'value': None},
                'quality': {'avg_logprob': -.2, 'no_speech_probability': .02, 'speech_coverage': 1.0}}]
            return observed

    monkeypatch.setattr(engine, 'load_recognizer', lambda *args: PartialChannels())
    result = engine.analyze_recording(req, profile(), tmp_path/'artifacts')
    assert result['status'] == 'partial'
    assert result['utterances'][0]['words'][0]['timing'] == 'supported'
    assert result['utterances'][0]['eligibility']['transcript']['status'] == 'eligible'
    assert result['utterances'][0]['eligibility']['voice_sample']['status'] != 'eligible'
    assert result['channel_coverage']['1'] == [{'span': {'start': 0, 'end': 16000}, 'status': 'error'}]


def test_recording_caller_preserves_proven_absent_audio_without_a_fake_clock(tmp_path, ffmpeg, monkeypatch):
    source = tmp_path/'video_without_audio.mkv'
    subprocess.run([ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                    '-i', 'color=s=16x16:r=1', '-frames:v', '1', '-c:v', 'ffv1', '-an', str(source)],
                   check=True, capture_output=True, timeout=20)
    req = request(source, ffmpeg)
    req.update(run_id='test-no-audio', epoch_id='isolated-test')
    monkeypatch.setattr(engine, 'load_recognizer', lambda *args: pytest.fail('model loaded for absent track'))
    result = engine.analyze_recording(req, profile(), tmp_path/'artifacts')
    assert result['status'] == 'not_applicable'
    assert result['reason'] == 'audio_track_absent'
    assert 'sample_count' not in result['source']
    assert (tmp_path/'artifacts/evidence.json').is_file()

    from wsl2_audio.evidence_contract import validate_evidence
    result['source']['sample_count'] = 0
    with pytest.raises(ValueError, match='Absent audio'):
        validate_evidence(result)
