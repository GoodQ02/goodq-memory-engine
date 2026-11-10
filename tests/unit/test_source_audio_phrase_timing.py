"""Recognition input, native phrase timing and DTW have independent contracts."""
from types import SimpleNamespace as NS
import copy
import numpy as np
import pytest
from wsl2_audio import transcription_contract as contract, acoustic_events as events


def raw_segment():
    return NS(start=.1, end=1.5, text='Hello Joe.', tokens=[105, 12, 13, 175], seek=999,
              words=None, avg_logprob=-.1, no_speech_prob=.01)


def native(raw=None, duration=2.):
    tokenizer = NS(timestamp_begin=100, decode=lambda _: 'Hello Joe.')
    model = NS(time_precision=.02, feature_extractor=NS(hop_length=160, sampling_rate=16000, nb_max_frames=3000))
    return contract._native_phrase_timing(raw or raw_segment(), tokenizer, model, duration)


def test_source_partition_preserves_quiet_onsets_and_all_nonzero_samples():
    audio = np.zeros(160000, dtype=np.float32)
    audio[1000:20000] = 1e-6
    audio[90000:150000] = .3
    regions = contract._recognition_source_regions(audio)
    mask = np.zeros(len(audio), dtype=bool)
    for region in regions:
        assert not mask[region['start']:region['end']].any()
        mask[region['start']:region['end']] = True
    assert not np.any(audio[~mask])
    assert len(regions) == 2


def test_zero_crossings_cannot_fragment_natural_audio():
    audio = np.ones(16000, dtype=np.float32)
    audio[::2] = 0
    assert contract._recognition_source_regions(audio) == [{'start': 0, 'end': 16000}]


def test_recognition_receives_audio_outside_vad_and_disables_alignment_feedback(monkeypatch):
    audio = np.ones(64000, dtype=np.float32)*.01
    monkeypatch.setattr(contract, '_source_speech_regions', lambda _: [{'start': 16000, 'end': 32000}])
    calls = []
    class Model:
        def transcribe(self, source, **kwargs):
            calls.append((source.copy(), kwargs))
            return iter([raw_segment()]), NS(transcription_options=None)
    coverage = {}
    contract._transcribe_source_regions(Model(), audio, language='en', beam_size=5,
        temperature=0., context_options={}, coverage=coverage)
    assert len(calls)==1 and np.array_equal(calls[0][0], audio)
    assert calls[0][1]['word_timestamps'] is False
    assert coverage['nonzero_samples_delivered']==coverage['nonzero_samples_total']==64000
    assert coverage['vad_regions'][0]['start']==1.
    assert coverage['regions'][0]['start']==0.


def test_late_decoder_error_retains_already_yielded_text(monkeypatch):
    monkeypatch.setattr(contract, '_source_speech_regions', lambda _: [{'start': 0, 'end': 32000}])
    class Model:
        def transcribe(self, *args, **kwargs):
            def rows():
                yield raw_segment()
                raise RuntimeError('later native window failed')
            return rows(), NS(transcription_options=None)
    coverage, partial = {}, []
    with pytest.raises(RuntimeError, match='later native window'):
        contract._transcribe_source_regions(Model(), np.ones(64000), language='en', beam_size=5,
            temperature=0., context_options={}, coverage=coverage, partial_segments=partial)
    assert partial[0]['text']=='Hello Joe.'
    assert coverage['status']=='error' and coverage['completed_region_count']==0
    assert coverage['regions'][0]['partial_segment_count']==1


def test_alignment_setup_failure_preserves_recognition_and_fails_visibly(monkeypatch):
    monkeypatch.setattr(contract, '_source_speech_regions', lambda _: [{'start': 0, 'end': 32000}])
    def broken(*args): raise RuntimeError('alignment unavailable')
    monkeypatch.setattr(contract, '_align_after_decoding', broken)
    class Model:
        def transcribe(self, *args, **kwargs):
            return iter([raw_segment()]), NS(transcription_options=None)
    coverage={}
    segments,_,timing,_=contract._transcribe_source_regions(Model(),np.ones(64000),language='en',
        beam_size=5,temperature=0.,context_options={},coverage=coverage)
    assert segments[0]['text']=='Hello Joe.' and segments[0].get('words') is None
    assert segments[0]['phrase_timing']['status']=='unavailable'
    assert 'alignment unavailable' in timing['word_alignment']['regions'][0]['error']
    assert 'word_alignment_unavailable' in coverage['regions'][0]['quality_flags']


def test_native_origin_does_not_depend_on_advanced_legacy_seek():
    observed = native()
    assert observed['encoder_seek_frames']==0
    assert observed['start']==.1 and observed['end']==1.5
    assert observed['boundary_status']=='model_estimated_complete_phrase'


@pytest.mark.parametrize('change,reason', [
    ({'tokens':[12,13]}, 'paired_native_timestamps_unavailable'),
    ({'text':'Different words.'}, 'native_text_evidence_mismatch'),
    ({'end':1.6}, 'native_clock_inconsistent'),
    ({'start':0.,'end':1.4}, 'native_clock_inconsistent'),
])
def test_native_bounds_fail_visibly_when_evidence_disagrees(change, reason):
    raw=raw_segment();vars(raw).update(change)
    assert native(raw)['reason']==reason


def test_native_out_of_input_bounds_do_not_invalidate_encoder_origin():
    observed=native(duration=1.)
    assert observed['status']=='unavailable' and observed['encoder_seek_frames']==0
    assert observed['raw_end']==1.5 and 'end' not in observed


def test_decode_edge_is_not_a_complete_phrase():
    raw=raw_segment();raw.tokens[0]=100;raw.start=0.
    observed=native(raw)
    assert observed['boundary_status']=='unresolved'


def phrase_result():
    words=[{'text':'Hello','start':.1,'end':.6,'probability':.99},
           {'text':'Joe.','start':None,'end':None,'probability':.99}]
    return {'segments':[{'start':.1,'end':1.5,'text':'Hello Joe.','words':words,'phrase_timing':native()}],
        'word_timestamps':words,'diarization_status':'success',
        'diarization':[{'start':0.,'end':2.,'speaker':'S0'}],
        'overlap_detection':{'status':'ok','intervals':[]},
        'additional_overlap_detection':{'status':'ok','intervals':[]}}


def test_complete_native_phrase_survives_missing_word_time_but_voice_gate_does_not():
    result=phrase_result()
    candidates,rejected=events.emotion_phrase_candidates(result,2.)
    assert not rejected and candidates[0]['text']=='Hello Joe.'
    assert candidates[0]['start']==.1 and candidates[0]['end']==1.5
    windows=[{'start':0.,'end':2.,'speech_score':.99,'excluded_labels':[]}]
    voice,_=events.select_speech_intervals(result,windows,2.)
    assert voice==[]  # Missing edge still vetoes the remaining word voice sample.


@pytest.mark.parametrize('key', ['overlap_detection','additional_overlap_detection'])
def test_native_phrase_cannot_ignore_overlap_outside_the_valid_word_span(key):
    result=phrase_result();result[key]['intervals']=[{'start':1.,'end':1.2}]
    candidates,rejected=events.emotion_phrase_candidates(result,2.)
    assert not candidates and 'overlap' in rejected[0]['reason']


def test_native_phrase_cannot_ignore_a_sequential_speaker_change():
    result=phrase_result();result['diarization']=[{'start':0.,'end':1.,'speaker':'S0'},
        {'start':1.,'end':2.,'speaker':'S1'}]
    candidates,rejected=events.emotion_phrase_candidates(result,2.)
    assert not candidates and rejected[0]['reason']=='phrase_speakers_unresolved'


def test_complete_phrase_still_requires_speaker_support_for_all_vad_speech():
    result=phrase_result();result['diarization'][0]['end']=1.4
    candidates,rejected=events.emotion_phrase_candidates(result,2.)
    meta={'phrase_windows':[{'start':.1,'end':1.5,'speech_score':.99,'excluded_labels':[]}],
          'speech_presence':{'status':'success','regions':[{'start':.1,'end':1.5}]}}
    selected=events.select_complete_emotion_phrases(candidates,rejected,meta,result,2.)
    assert selected['selected']==[]
    assert selected['rejected'][0]['reason']=='phrase_speaker_boundary_unresolved'


def test_unavailable_native_phrase_cannot_fallback_to_only_good_words():
    result=phrase_result();result['segments'][0]['phrase_timing']={'status':'unavailable'}
    result['segments'][0]['words'][1].update(start=.6,end=1.)
    candidates,rejected=events.emotion_phrase_candidates(result,2.)
    assert not candidates and rejected[0]['reason']=='native_phrase_boundaries_unavailable'


@pytest.mark.parametrize('word_end', [1.4, None])
def test_unresolved_native_keeps_only_the_preexisting_complete_word_path(word_end):
    result=phrase_result()
    result['segments'][0]['phrase_timing'].update(boundary_status='unresolved',reason='native_phrase_touches_decode_boundary')
    result['word_timestamps'][1].update(start=.6 if word_end else None,end=word_end)
    candidates,rejected=events.emotion_phrase_candidates(result,2.)
    if word_end:
        assert not rejected and candidates[0]['timing_basis']=='complete_word_alignment'
        assert candidates[0]['native_boundary_evidence']['boundary_status']=='unresolved'
    else:
        assert not candidates and rejected[0]['reason']=='phrase_word_timing_unavailable'


@pytest.mark.parametrize('reason', ['native_text_evidence_mismatch','native_clock_inconsistent','native_bounds_outside_input'])
def test_contradictory_native_evidence_cannot_use_word_fallback(reason):
    result=phrase_result();result['word_timestamps'][1].update(start=.6,end=1.4)
    result['segments'][0]['phrase_timing'].update(status='unavailable',reason=reason)
    candidates,rejected=events.emotion_phrase_candidates(result,2.)
    assert not candidates and rejected[0]['boundary_detail']==reason


def test_native_text_mismatch_cannot_hide_behind_an_edge_warning():
    result=phrase_result();result['word_timestamps'][1].update(start=.6,end=1.4)
    result['segments'][0]['phrase_timing'].update(text='Different text.',boundary_status='unresolved',reason='native_phrase_touches_decode_boundary')
    candidates,rejected=events.emotion_phrase_candidates(result,2.)
    assert not candidates and rejected[0]['reason']=='phrase_text_evidence_mismatch'


def test_native_invalid_bounds_cannot_hide_behind_an_edge_warning():
    result=phrase_result();result['word_timestamps'][1].update(start=.6,end=1.4)
    result['segments'][0]['phrase_timing'].update(start=-1.,boundary_status='unresolved',reason='native_phrase_touches_decode_boundary')
    candidates,rejected=events.emotion_phrase_candidates(result,2.)
    assert not candidates and rejected[0]['reason']=='native_phrase_bounds_invalid'


def test_native_overlap_failure_is_never_rescued_by_word_fallback():
    result=phrase_result();result['word_timestamps'][1].update(start=.6,end=1.)
    result['overlap_detection']['intervals']=[{'start':1.2,'end':1.3}]
    candidates,rejected=events.emotion_phrase_candidates(result,2.)
    assert not candidates and rejected[0]['reason']=='local_overlap_in_phrase'


@pytest.mark.parametrize('installed', ['1.0.3','1.2.1'])
@pytest.mark.parametrize('failure', [None, 'features', 'alignment', 'text'])
def test_postdecode_alignment_cannot_mutate_native_bounds_or_erase_text(monkeypatch, installed, failure):
    monkeypatch.setattr('importlib.metadata.version', lambda _: installed)
    monkeypatch.setattr('faster_whisper.tokenizer.Tokenizer', lambda *a, **kw: NS(
        timestamp_begin=100, decode=lambda _: 'Hello Joe.'))
    observed=[]
    class Features:
        hop_length=160; sampling_rate=16000; nb_max_frames=3000
        def __call__(self, audio):
            assert len(audio)==32000
            if failure=='features':raise RuntimeError('feature failure')
            return np.ones((80, 3200 if installed=='1.0.3' else 201))
    class Model:
        time_precision=.02; feature_extractor=Features(); hf_tokenizer=object()
        model=NS(is_multilingual=True)
        def encode(self, features):
            assert features.shape==(80,3000)
            assert np.all(features[:,:200]==1) and np.all(features[:,200:]==0)
            return object()
        def add_word_timestamps(self, groups, tokenizer, encoder, frames, *args):
            assert frames==200
            group=groups[0] if installed=='1.2.1' else groups
            observed.extend(group)
            if failure=='alignment':raise RuntimeError('alignment failure')
            for item in group:
                item.update(start=.3,end=.8,words=[
                    {'word':'Wrong ' if failure=='text' else 'Hello ', 'start':.3,'end':.5,'probability':.9},
                    {'word':'Joe.','start':.5,'end':.8,'probability':.9}])
    original=raw_segment()
    raw,receipt=contract._align_after_decoding(Model(),np.ones(32000),[original],'en')
    assert raw[0].text==original.text and raw[0].start==.1 and raw[0].end==1.5
    assert raw[0].phrase_timing['boundary_status']=='model_estimated_complete_phrase'
    assert original.words is None and receipt['recognition_feedback'] is False
    if failure:
        assert receipt['status']=='unavailable' and raw[0].words is None
    else:
        assert receipt['status']=='completed' and raw[0].words[0].start==.3


def test_unaligned_legacy_segment_prevents_a_complete_alignment_receipt(monkeypatch):
    monkeypatch.setattr('importlib.metadata.version', lambda _: '1.0.3')
    monkeypatch.setattr('faster_whisper.tokenizer.Tokenizer', lambda *a, **kw: NS(
        timestamp_begin=100, decode=lambda _: 'Hello Joe.'))
    class Features:
        hop_length=160; sampling_rate=16000; nb_max_frames=3000
        def __call__(self, audio):return np.ones((80,3200))
    class Model:
        time_precision=.02; feature_extractor=Features(); hf_tokenizer=object(); model=NS(is_multilingual=True)
        def encode(self, features):return object()
        def add_word_timestamps(self, groups, *args):
            groups[0]['words']=[{'word':'Hello Joe.','start':.1,'end':1.5,'probability':.9}]
    unpaired=raw_segment();unpaired.tokens=[12,13]
    rows,receipt=contract._align_after_decoding(Model(),np.ones(32000),[raw_segment(),unpaired],'en')
    assert receipt['status']=='partial' and rows[1].words is None
    assert receipt['segments'][1]['reason']=='decoder_origin_unavailable'
    _,receipt=contract._align_after_decoding(Model(),np.ones(32000),[unpaired],'en')
    assert receipt['status']=='unavailable'


def test_projection_and_speaker_merge_keep_native_phrases_separate_from_word_turns():
    from steps.audio.audio_wsl2_bridge import _transcription_projection
    from cli.step_runner import run_step
    result=phrase_result()
    result.update(transcription='Hello Joe.',transcription_status='success',status='success',
        word_alignment={'words':result['word_timestamps'],'timebase':'input_audio_seconds'})
    projected={**result,**_transcription_projection(result,engine='faster-whisper')}
    merged=run_step('audio_speaker_merge',projected,{})
    observation=merged['transcript_meta']['phrase_observations'][0]
    assert observation['text']=='Hello Joe.' and observation['start']==.1 and observation['end']==1.5
    assert all('phrase_timing' not in row for row in merged['speaker_transcript'])
    assert observation['source_segment_index']==0
