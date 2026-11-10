"""Lossless partitioning through the recording and scene-consumer boundaries."""
from copy import deepcopy

import pytest

from tests.unit.test_audio_engine_enrichment import inputs
from tests.unit.test_audio_engine_enrichment_call import SpeechRecognizer, Observers, setup_call
from tests.unit.test_audio_engine_recording import ffmpeg, write_pcm, request as audio_request
from tests.unit.test_audio_engine_recording_call import verify_test_assets
from wsl2_audio import enrichment_models, recording_engine
from wsl2_audio.eligibility import POLICY, select_inputs
from wsl2_audio.evidence_contract import validate_evidence
from wsl2_audio.scene_projection import project_audio, legacy_audio


def fixture():
    evidence, observations = inputs()
    unit = evidence['utterances'][0]
    unit.update(text='Stay here. Keep going. All done.', span={'start':1000,'end':27000},
                native_span={'start':1000,'end':27000})
    unit['words'] = [{'text':text,'span':{'start':a,'end':b},'timing':'supported'} for text,a,b in
                     [('Stay',2000,3000),('here.',3000,4000),('Keep',5000,6000),
                      ('going.',6000,7000),('All',20000,23000),('done.',23000,26000)]]
    observations['phrase_activity']['regions'] = [
        {'channel':0,'span':{'start':a,'end':b}} for a,b in [(1800,8000),(19500,26500)]]
    observations['speaker_activity']['tracks'] = [
        {'channel':0,'speaker':'s0','span':{'start':a,'end':b}} for a,b in [(1500,8000),(19000,26500)]]
    for name, field in [('overlap','single_activity'),('acoustic_events','speech_intervals')]:
        observations[name][field] = [{'channel':0,'span':{'start':1000,'end':27000}}]
    return evidence, observations


def caller(tmp_path, ffmpeg, monkeypatch, change=None, channels=1):
    evidence, observations = fixture()
    if change:
        change(evidence, observations)
    if channels == 2:
        for row in observations.values():
            row['channel_assessed_spans']['1'] = deepcopy(row['assessed_spans'])
            for field in ('regions','tracks','flags','intervals','single_activity','events','speech_intervals'):
                if field in row:
                    row[field] += [dict(deepcopy(r),channel=1) for r in row[field] if r.get('channel') == 0]
    class Recognizer(SpeechRecognizer):
        def observe(self, *args):
            row = super().observe(*args)
            unit = deepcopy(evidence['utterances'][0])
            for key in ('id','eligibility','channel','observation_ids'):
                unit.pop(key, None)
            row['utterances'] = [unit]
            row['speech_activity']['spans'] = [{'start':1000,'end':8500},{'start':18500,'end':27000}]
            return row
    class RetainedObservers(Observers):
        def observe(self, name, prior):
            return deepcopy(observations[name])
    recognizer = Recognizer()
    request, profile = setup_call(tmp_path, ffmpeg, monkeypatch, recognizer)
    if channels == 2:
        source = write_pcm(tmp_path/'stereo.wav', [1,-1]*32000, channels=2)
        request.update(audio_request(source, ffmpeg))
    monkeypatch.setattr(enrichment_models, 'RecordingObservers', RetainedObservers)
    result = recording_engine.analyze_recording(request, profile, tmp_path/'out')
    projected = project_audio(result, [{'scene_id':'test','start':0,'end':2}])['test']
    return result, legacy_audio(projected), recognizer


def test_later_pause_survives_and_whole_activity_edges_reach_consumers(tmp_path, ffmpeg, monkeypatch):
    result, consumed, recognizer = caller(tmp_path, ffmpeg, monkeypatch)
    first, last = result['utterances']
    assert [first['text'],last['text']] == ['Stay here. Keep going.', 'All done.']
    assert last['envelope_source']['original_span'] == {'start':13750,'end':27000}
    assert last['span'] == {'start':19000,'end':26500}
    assert last['quality']['speech_coverage'] == 1
    assert last in select_inputs(result, 'transcript')
    assert last in select_inputs(result, 'vocal_delivery')
    assert consumed['transcript'] == 'Stay here. Keep going. All done.'
    assert [w for u in result['utterances'] for w in u['words']] == fixture()[0]['utterances'][0]['words']
    assert len(recognizer.calls) == 1
    assert result['eligibility_policy'] == POLICY
    assert validate_evidence(result) == result


@pytest.mark.parametrize('kind', ['crying','overlap','flag','other_channel_cry','missing_acoustics','untimed_word'])
def test_internal_margin_cannot_erase_veto_or_unknown_evidence(tmp_path, ffmpeg, monkeypatch, kind):
    def change(evidence, observations):
        span = {'start':15000,'end':17000}
        if kind in ('crying','other_channel_cry'):
            observations['acoustic_events']['events'] = [{'id':'veto','label':'crying','status':'observed',
                'channel':1 if kind == 'other_channel_cry' else 0,'span':span}]
        elif kind == 'overlap':
            observations['overlap']['intervals'] = [{'channel':0,'status':'observed','span':span}]
        elif kind == 'flag':
            observations['speaker_activity']['flags'] = [{'channel':0,'span':span}]
        elif kind == 'missing_acoustics':
            observations['acoustic_events'].update(status='unavailable', reason='injected')
        else:
            evidence['utterances'][0]['words'][-1].update(timing='unavailable',span=None,reason='invalid_word_alignment')
    channels = 2 if kind == 'other_channel_cry' else 1
    result, consumed, _ = caller(tmp_path, ffmpeg, monkeypatch, change, channels=channels)
    last = result['utterances'][-1]
    assert last['span']['start'] == 13750
    assert last not in select_inputs(result, 'vocal_delivery')
    assert last not in select_inputs(result, 'voice_sample')
    assert last['text'] == 'All done.'
    assert len(consumed['audio_evidence']['utterances']) == 2*channels


def test_broad_overlap_stays_a_veto_after_activity_refinement(tmp_path, ffmpeg, monkeypatch):
    def change(_, observations):
        observations['overlap']['intervals'] = [{'channel':0,'status':'unresolved',
                                                'span':{'start':1000,'end':27000}}]
    result, consumed, _ = caller(tmp_path, ffmpeg, monkeypatch, change)
    last = result['utterances'][-1]
    assert last['span']['start'] == 19000
    assert last in select_inputs(result, 'transcript')
    assert 'overlap_unresolved' in last['eligibility']['voice_sample']['reasons']
    assert last not in select_inputs(result, 'voice_sample')
    assert 'All done.' in consumed['transcript']


def test_other_speaker_in_margin_is_retained_in_full(tmp_path, ffmpeg, monkeypatch):
    def change(_, observations):
        observations['speaker_activity']['tracks'].append({'channel':0,'speaker':'other',
                                                          'span':{'start':15000,'end':17000}})
    result, _, _ = caller(tmp_path, ffmpeg, monkeypatch, change)
    last = result['utterances'][-1]
    assert last['span']['start'] == 15000
    assert 'mixed_speakers' in last['eligibility']['voice_sample']['reasons']
    assert last not in select_inputs(result, 'voice_sample')


def test_unanchored_earlier_sentence_is_kept_without_losing_later_pause(tmp_path, ffmpeg, monkeypatch):
    def change(evidence, _):
        for word in evidence['utterances'][0]['words'][:2]:
            word.update(timing='unavailable',span=None,reason='invalid_word_alignment')
    result, _, _ = caller(tmp_path, ffmpeg, monkeypatch, change)
    assert [u['text'] for u in result['utterances']] == ['Stay here. Keep going.','All done.']
    assert all(w['span'] is None for w in result['utterances'][0]['words'][:2])


@pytest.mark.parametrize('mutation', ['remove_word','move_edge','change_method','drop_child'])
def test_new_partition_and_extent_cannot_be_forged(tmp_path, ffmpeg, monkeypatch, mutation):
    result, _, _ = caller(tmp_path, ffmpeg, monkeypatch)
    if mutation == 'remove_word':
        result['utterances'][0]['words'].pop(0)
    elif mutation == 'move_edge':
        result['utterances'][-1]['span']['start'] += 1
    elif mutation == 'change_method':
        result['phrase_resolution']['method'] = 'punctuation_and_unpadded_pause_v1'
    else:
        result['utterances'].pop(0)
    with pytest.raises(ValueError):
        validate_evidence(result)


def test_legacy_partition_and_midpoints_still_validate():
    from tests.unit.test_audio_engine_phrases import block
    from wsl2_audio.phrase_resolution import _proposal, _children, METHOD, PHRASE_EDGE_METHOD
    from wsl2_audio.enrichment import attach_observations
    evidence, observations = block()
    parent = deepcopy(evidence['utterances'][0])
    proposal = _proposal(parent, observations['phrase_activity'], evidence)
    children = _children(parent, proposal, evidence)
    evidence['utterances'] = children
    evidence['phrase_resolution'] = {'method':METHOD,'envelope_method':PHRASE_EDGE_METHOD,
        'parents':[{'native':parent,'seams':proposal[1],'child_ids':[u['id'] for u in children]}]}
    result = attach_observations(evidence, observations)
    assert validate_evidence(result) == result
    assert result['utterances'][1]['span'] == {'start':4500,'end':14000}


def test_short_sentence_endings_are_distinct_from_abbreviations():
    from wsl2_audio.phrase_resolution import _groups
    parent = {'text':'Go on. Dr. Smith agreed. It is 2.5.',
              'words':[{'text':s} for s in 'Go on. Dr. Smith agreed. It is 2.5.'.split()]}
    assert [g[2] for g in _groups(parent, short_endings=True)] == ['Go on.','Dr. Smith agreed.','It is 2.5.']
    assert [g[2] for g in _groups(parent)] == ['Go on. Dr. Smith agreed.','It is 2.5.']
