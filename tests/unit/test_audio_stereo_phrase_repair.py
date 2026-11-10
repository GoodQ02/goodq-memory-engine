from copy import deepcopy

import numpy as np
import pytest

from tests.unit.test_audio_engine_recording import write_pcm, request, ffmpeg
from tests.unit.test_audio_engine_recording_call import verify_test_assets
from tests.unit.test_audio_engine_enrichment_call import SpeechRecognizer, Observers, setup_call
from tests.unit.test_audio_engine_enrichment import inputs
from wsl2_audio import enrichment_models, recording_engine
from wsl2_audio.eligibility import POLICY, select_inputs
from wsl2_audio.evidence_contract import validate_evidence


def stereo_call(tmp_path, ffmpeg, monkeypatch, mode='same', veto=None, coarse=False, recognizer_cls=None, activity_end=None):
    from tests.unit.test_audio_engine_envelopes import coarse_sample
    first = np.round(10000*np.sin(np.arange(32000)*.13)).astype(int)
    second = first.copy()
    if mode == 'near':
        second[::17] += 1
    elif mode == 'opposing':
        second = -first
    elif mode == 'other_voice':
        second = first + np.round(1000*np.sin(np.arange(32000)*.23)).astype(int)
    elif mode == 'brief_other_voice':
        second[6000:6320] += np.round(300*np.sin(np.arange(320)*.23)).astype(int)
    elif mode == 'other_voice_in_extension':
        second[23000:23320] += np.round(300*np.sin(np.arange(320)*.23)).astype(int)
    source = write_pcm(tmp_path/'stereo.wav', np.stack([first, second], axis=1).ravel().tolist(), channels=2)
    class StereoRecognizer(recognizer_cls or SpeechRecognizer):
        def observe(self, *args):
            row = super().observe(*args)
            if coarse:
                unit = deepcopy(coarse_sample()[0]['utterances'][0])
                for key in ('id','eligibility','channel','observation_ids'):
                    unit.pop(key,None)
                unit['quality']['speech_coverage'] = 1.
                row['utterances'] = [unit]
                row['speech_activity']['spans'] = [{'start':0,'end':32000}]
            row['speech_activity'].setdefault('spans', [deepcopy(row['utterances'][0]['span'])])
            return row
    recognizer = StereoRecognizer()
    _, config = setup_call(tmp_path, ffmpeg, monkeypatch, recognizer)
    req = request(source, ffmpeg)
    req.update(run_id='stereo-repair', epoch_id='isolated-stereo-repair')

    class StereoObservers(Observers):
        def observe(self, name, prior):
            row = deepcopy((coarse_sample() if coarse else inputs())[1][name])
            row['channel_assessed_spans']['1'] = deepcopy(row['assessed_spans'])
            for key in ('tracks', 'flags', 'regions', 'intervals', 'single_activity', 'events', 'speech_intervals'):
                if key in row:
                    row[key] += [dict(deepcopy(x), channel=1) for x in row[key]]
                    if activity_end:
                        for part in row[key]:
                            part['span']['end'] = activity_end
            if veto == 'crying' and name == 'acoustic_events':
                row['events'].append({'id':'second-channel-cry', 'channel':1, 'span':{'start':5000,'end':9000}, 'label':'crying','status':'observed'})
            if veto == 'margin_crying' and name == 'acoustic_events':
                row['events'].append({'id':'second-channel-margin-cry', 'channel':1, 'span':{'start':23000,'end':25000}, 'label':'crying','status':'observed'})
            if veto == 'margin_speaker' and name == 'speaker_activity':
                row['tracks'].append({'speaker':'other','channel':1,'span':{'start':23000,'end':25000}})
            if veto == 'missing_support' and name == 'overlap':
                row['single_activity'] = [x for x in row['single_activity'] if x['channel']==0]
            return row

    monkeypatch.setattr(enrichment_models, 'RecordingObservers', StereoObservers)
    return recording_engine.analyze_recording(req, config, tmp_path/'out'), recognizer


@pytest.mark.parametrize('mode', ['same', 'near'])
def test_recording_caller_reconciles_redundant_stereo_without_duplicate_text(tmp_path, ffmpeg, monkeypatch, mode):
    result, recognizer = stereo_call(tmp_path, ffmpeg, monkeypatch, mode)
    assert len(result['window_observations']) == len(recognizer.calls) == 2
    assert len(result['utterances']) == 1
    unit = result['utterances'][0]
    assert unit['source_channels'] == [0, 1]
    assert len(unit['observation_ids']) == 2
    assert result['eligibility_policy'] == POLICY
    assert select_inputs(result, 'voice_sample') == [unit]
    assert result['vocal_delivery'][0]['utterance_id'] == unit['id']
    assert validate_evidence(result) == result


@pytest.mark.parametrize('mode', ['opposing', 'other_voice', 'brief_other_voice'])
def test_waveform_disagreement_keeps_channels_and_exclusion(tmp_path, ffmpeg, monkeypatch, mode):
    result, _ = stereo_call(tmp_path, ffmpeg, monkeypatch, mode)
    assert len(result['utterances']) == 2
    assert not select_inputs(result, 'vocal_delivery')


@pytest.mark.parametrize('veto', ['crying', 'missing_support'])
def test_reconciliation_preserves_other_channel_veto_and_positive_support_requirements(tmp_path, ffmpeg, monkeypatch, veto):
    result, _ = stereo_call(tmp_path, ffmpeg, monkeypatch, veto=veto)
    assert len(result['utterances']) == 1
    assert not select_inputs(result, 'vocal_delivery')
    assert not select_inputs(result, 'voice_sample')


def test_split_phrase_outer_end_follows_complete_observed_activity_through_recording_caller(tmp_path, ffmpeg, monkeypatch):
    class PhraseRecognizer(SpeechRecognizer):
        def observe(self, *args):
            row = super().observe(*args)
            unit = row['utterances'][0]
            unit.update(text='One line. Last words.', span={'start':1000,'end':23000}, native_span={'start':1000,'end':23000})
            unit['words'] = [{'text':text,'span':{'start':a,'end':b},'timing':'supported'}
                             for text,a,b in [('One',2000,2500),('line.',2500,4000),('Last',16000,18000),('words.',18000,21000)]]
            row['speech_activity']['spans'] = [{'start':1000,'end':24000}]
            return row

    class PhraseObservers(Observers):
        def observe(self, name, prior):
            row = deepcopy(inputs()[1][name])
            if name == 'phrase_activity':
                row['regions'] = [{'channel':0,'span':{'start':a,'end':b}} for a,b in [(1800,4000),(17000,24000)]]
            elif name == 'speaker_activity':
                row['tracks'] = [{'channel':0,'speaker':'s0','span':{'start':a,'end':b}} for a,b in [(1500,4000),(15000,24000)]]
            elif name == 'overlap':
                row['single_activity'] = [{'channel':0,'span':{'start':1000,'end':24000}}]
            elif name == 'acoustic_events':
                row['speech_intervals'] = [{'channel':0,'span':{'start':1000,'end':24000}}]
            return row

    recognizer = PhraseRecognizer()
    req, config = setup_call(tmp_path, ffmpeg, monkeypatch, recognizer)
    monkeypatch.setattr(enrichment_models, 'RecordingObservers', PhraseObservers)
    result = recording_engine.analyze_recording(req, config, tmp_path/'out')
    assert [u['text'] for u in result['utterances']] == ['One line.', 'Last words.']
    last = result['utterances'][-1]
    assert last['envelope_source']['original_span'] == {'start':10000,'end':23000}
    assert last['span'] == {'start':15000,'end':24000}
    assert last in select_inputs(result, 'vocal_delivery')
    assert result['vocal_delivery'][-1]['span'] == last['span']
    assert len(recognizer.calls) == 1


def test_phrase_support_does_not_count_activity_outside_its_span_but_incomplete_edge_stays_closed():
    from wsl2_audio.enrichment import attach_observations
    evidence, observations = inputs()
    observations['phrase_activity']['regions'][0]['span'] = {'start':2000,'end':30000}
    observations['speaker_activity']['tracks'][0]['span'] = {'start':2000,'end':30000}
    result = attach_observations(evidence, observations)
    unit = result['utterances'][0]
    assert unit['speaker']['secondary_speech_coverage'] == pytest.approx(8/9)
    assert unit['acoustic_support']['ordinary_speech_coverage'] == pytest.approx(8/9)
    assert unit['completeness'] == 'unresolved'
    assert not select_inputs(result,'vocal_delivery')


@pytest.mark.parametrize('veto', ['margin_crying','margin_speaker'])
def test_outer_margin_on_other_reconciled_channel_cannot_be_cropped_to_pass(tmp_path, ffmpeg, monkeypatch, veto):
    from tests.unit.test_audio_engine_envelopes import coarse_sample
    result, _ = stereo_call(tmp_path, ffmpeg, monkeypatch, veto=veto, coarse=True)
    assert len(result['utterances']) == 1
    assert result['utterances'][0]['span'] == coarse_sample()[0]['utterances'][0]['span']
    assert not select_inputs(result,'voice_sample')


@pytest.mark.parametrize('mutation', ['record','marker','member','residual','span'])
def test_stereo_provenance_cannot_be_removed_or_forged(tmp_path, ffmpeg, monkeypatch, mutation):
    result, _ = stereo_call(tmp_path, ffmpeg, monkeypatch)
    if mutation == 'record':
        result.pop('channel_reconciliation')
    elif mutation == 'marker':
        result['utterances'][0].pop('source_channels')
        result['utterances'][0].pop('channel_reconciliation_id')
    elif mutation == 'member':
        result['channel_reconciliation']['groups'][0]['members'][1]['text'] = 'Different speech'
    elif mutation == 'residual':
        result['channel_reconciliation']['groups'][0]['proofs'][0]['relative_rms'] = .1
    else:
        result['channel_reconciliation']['groups'][0]['proofs'][0]['span']['end'] -= 1
    with pytest.raises(ValueError, match='[Cc]hannel'):
        validate_evidence(result)


def test_recovered_alignment_on_redundant_channels_preserves_each_members_bounds(tmp_path, ffmpeg, monkeypatch):
    class Recovered(SpeechRecognizer):
        def observe(self, *args):
            row = super().observe(*args)
            unit = row['utterances'][0]
            a,b = (1000,21000) if len(self.calls)==1 else (1200,22000)
            unit.update(span={'start':a,'end':b},alignment_source={'method':'complete_aligned_text_v1','reason':'native_envelope_outside_input'})
            unit['words'] = [{'text':'Yay','span':{'start':a,'end':9000},'timing':'supported'},
                             {'text':'Joe','span':{'start':9000,'end':b},'timing':'supported'}]
            return row
    result, _ = stereo_call(tmp_path,ffmpeg,monkeypatch,recognizer_cls=Recovered)
    assert len(result['utterances'])==1
    assert result['utterances'][0]['span']=={'start':1000,'end':22000}
    assert validate_evidence(result)==result


def test_union_recomputes_recognition_support_instead_of_reusing_shorter_member_score(tmp_path, ffmpeg, monkeypatch):
    class PartialSupport(SpeechRecognizer):
        def observe(self,*args):
            row = super().observe(*args)
            unit = row['utterances'][0]
            a,b = (1000,21000) if len(self.calls)==1 else (5000,25000)
            unit['span'] = {'start':a,'end':b}
            unit['quality']['speech_coverage'] = .8
            unit['words'] = []
            row['speech_activity']['spans'] = [{'start':5000,'end':21000}]
            return row
    result, _ = stereo_call(tmp_path,ffmpeg,monkeypatch,recognizer_cls=PartialSupport)
    assert len(result['utterances']) == 1
    unit = result['utterances'][0]
    assert unit['span'] == {'start':1000,'end':25000}
    assert unit['quality']['speech_coverage'] == pytest.approx(2/3)
    assert not select_inputs(result,'voice_sample')
    unit['quality']['speech_coverage'] = .8
    with pytest.raises(ValueError, match='[Cc]hannel'):
        validate_evidence(result)


@pytest.mark.parametrize('field,value,expected', [('speech_coverage', .7, .7), ('avg_logprob', -1.2, -1.2),
    ('no_speech_probability', .9, .9), ('avg_logprob', .2, None), ('no_speech_probability', -.1, None)])
def test_duplicate_reconciliation_retains_worst_confidence_and_recomputes_coverage(tmp_path, ffmpeg, monkeypatch, field, value, expected):
    class WeakChannel(SpeechRecognizer):
        def observe(self, *args):
            row = super().observe(*args)
            if len(self.calls) == 2:
                row['utterances'][0]['quality'][field] = value
                if field == 'speech_coverage':
                    row['speech_activity']['spans'] = [{'start':1000,'end':14300}]
            return row
    result, _ = stereo_call(tmp_path, ffmpeg, monkeypatch, recognizer_cls=WeakChannel)
    assert len(result['utterances']) == 1
    unit = result['utterances'][0]
    assert unit['quality'][field] == (pytest.approx(expected) if expected is not None else None)
    assert not select_inputs(result, 'voice_sample')


@pytest.mark.parametrize('mode', ['same', 'other_voice_in_extension'])
def test_extended_stereo_phrase_requires_fresh_pcm_proof_on_new_samples(tmp_path, ffmpeg, monkeypatch, mode):
    class Recovered(SpeechRecognizer):
        def observe(self, *args):
            row = super().observe(*args)
            row['utterances'][0].update(span={'start':1000,'end':21000},
                alignment_source={'method':'complete_aligned_text_v1','reason':'native_envelope_outside_input'},
                words=[{'text':'Yay','span':{'start':1000,'end':9000},'timing':'supported'},
                       {'text':'Joe','span':{'start':9000,'end':21000},'timing':'supported'}])
            row['speech_activity']['spans'] = [{'start':1000,'end':24000}]
            return row
    result, _ = stereo_call(tmp_path, ffmpeg, monkeypatch, mode=mode, recognizer_cls=Recovered, activity_end=24000)
    assert len(result['utterances']) == 1
    unit = result['utterances'][0]
    assert unit['span'] == {'start':1000,'end':24000}
    assert bool(select_inputs(result,'voice_sample')) == (mode == 'same')
    group = result['channel_reconciliation']['groups'][0]
    assert bool(group.get('envelope_proofs')) == (mode == 'same')


def test_coarse_and_recovered_stereo_envelopes_match_complete_aligned_occurrence(tmp_path, ffmpeg, monkeypatch):
    class CoarseAndRecovered(SpeechRecognizer):
        def observe(self, *args):
            row = super().observe(*args)
            unit = row['utterances'][0]
            unit['words'] = [{'text':'Yay','span':{'start':1000,'end':9000},'timing':'supported'},
                             {'text':'Joe','span':{'start':9000,'end':21000},'timing':'supported'}]
            if len(self.calls) == 1:
                unit.update(span={'start':1000,'end':21000},
                    alignment_source={'method':'complete_aligned_text_v1','reason':'native_envelope_outside_input'})
            else:
                unit['span'] = {'start':0,'end':30000}
            row['speech_activity']['spans'] = [{'start':1000,'end':21000}]
            return row
    result, _ = stereo_call(tmp_path, ffmpeg, monkeypatch, recognizer_cls=CoarseAndRecovered)
    assert len(result['utterances']) == 1
    unit = result['utterances'][0]
    assert unit['span'] == {'start':1000,'end':21000}
    assert unit['source_channels'] == [0,1]
    assert result['channel_reconciliation']['groups'][0]['proofs'][0]['span'] == {'start':0,'end':30000}
    assert select_inputs(result,'voice_sample') == [unit]
