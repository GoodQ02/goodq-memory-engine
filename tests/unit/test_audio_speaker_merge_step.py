from __future__ import annotations

from steps.audio_speaker_merge.step import audio_speaker_merge
import copy
import pytest


@pytest.mark.parametrize('layout', ['segment', 'word', 'flat_word'])
def test_overlap_never_assigns_majority_speaker_through_production_caller(layout):
    from cli.step_runner import run_step
    row = {'start': 1.0, 'end': 2.0, 'text': 'Yay!', 'speaker': 'A'}
    key = 'word_timestamps' if layout == 'flat_word' else 'segments'
    segment = {**row, 'words': [dict(row)]} if layout == 'word' else row
    item = {key: [segment], 'diarization': [
        {'start': 0.0, 'end': 3.0, 'speaker': 'A'},
        {'start': 1.2, 'end': 1.7, 'speaker': 'B'}],
        'transcript_meta': {'speakers': ['A']}}
    before = copy.deepcopy(item)
    result = run_step('audio_speaker_merge', item, {})
    turn = result['speaker_transcript'][0]
    assert turn['text'] == 'Yay!' and (turn['start'],turn['end']) == (1.0,2.0)
    assert turn['speaker'] is None
    assert turn['attribution_status'] == 'unresolved'
    assert turn['attribution_reason'] == 'overlapping_speakers'
    assert turn['speaker_candidates'] == ['A','B']
    assert turn['overlap_intervals'] == [{'start':1.2,'end':1.7,'speakers':['A','B'],
                                         'review_status':'unreviewed'}]
    assert result['transcript_meta']['speakers'] == []
    assert item == before


@pytest.mark.parametrize('tracks,reason', [
    ([{'start':0.,'end':1.,'speaker':'A'}, {'start':1.,'end':2.,'speaker':'B'}], 'multiple_speakers'),
    ([{'start':0.,'end':.8,'speaker':'A'}, {'start':1.2,'end':2.,'speaker':'A'}], 'incomplete_speaker_support'),
])
def test_coarse_turn_does_not_hide_speaker_changes_or_gaps(tracks, reason):
    turn=audio_speaker_merge({'segments':[{'start':0.,'end':2.,'text':'Whole phrase.'}],
                             'diarization':tracks}, {})['speaker_transcript'][0]
    assert turn['speaker'] is None and turn['attribution_reason']==reason
    assert not turn['overlap_intervals']


def test_adjacent_same_speaker_tracks_cover_word_without_gap():
    turn=audio_speaker_merge({'segments':[{'start':0.,'end':2.,'words':[
        {'start':.5,'end':1.5,'text':'Hello'}]}], 'diarization':[
        {'start':0.,'end':1.,'speaker':'A'}, {'start':1.,'end':2.,'speaker':'A'}]}, {})['speaker_transcript'][0]
    assert turn['speaker']=='A' and turn['attribution_status']=='unreviewed'


def test_words_do_not_merge_across_another_speakers_interjection():
    item={'segments':[{'start':0.,'end':1.,'words':[
        {'start':0.,'end':.4,'text':'Hello'}, {'start':.6,'end':1.,'text':'there'}]}],
        'diarization':[{'start':0.,'end':1.,'speaker':'A'},
                       {'start':.45,'end':.55,'speaker':'B'}]}
    turns=audio_speaker_merge(item,{})['speaker_transcript']
    assert len(turns)==2 and [t['speaker'] for t in turns]==['A','A']


@pytest.mark.parametrize('start,end', [(None,None),(float('nan'),1.),(2.,1.),(-1.,1.),('0',1.)])
def test_invalid_times_cannot_inherit_speaker(start,end):
    row=audio_speaker_merge({'segments':[{'start':start,'end':end,'speaker':'A','text':'Keep words'}],
                            'diarization':[{'start':0.,'end':3.,'speaker':'A'}]}, {})['speaker_transcript'][0]
    assert row['speaker'] is None and row['attribution_reason']=='timing_unavailable'
    assert row['text']=='Keep words'


def test_audio_speaker_merge_uses_top_level_segments_when_meta_segments_missing():
    item = {
        "segments": [
            {"start": 0.0, "end": 2.0, "text": "Hello there."},
            {"start": 2.0, "end": 4.0, "text": "General Kenobi."},
        ],
        "diarization": [
            {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
            {"start": 2.0, "end": 4.0, "speaker": "SPEAKER_01"},
        ],
        "transcript_meta": {"status": "success"},
    }

    result = audio_speaker_merge(item, {})

    assert [{k: row[k] for k in ('start','end','text','speaker')} for row in result['speaker_transcript']] == [
        {"start": 0.0, "end": 2.0, "text": "Hello there.", "speaker": "SPEAKER_00"},
        {"start": 2.0, "end": 4.0, "text": "General Kenobi.", "speaker": "SPEAKER_01"},
    ]
    assert result["transcript_meta"]["segment_count"] == 2
    assert all(row['attribution_status']=='unreviewed' and not row['overlap_intervals']
               for row in result['speaker_transcript'])
    assert result["transcript_meta"]["speakers"] == ["SPEAKER_00", "SPEAKER_01"]


def test_audio_speaker_merge_falls_back_to_word_timestamps():
    item = {
        "word_timestamps": [
            {"start": 5.0, "end": 7.0, "text": "I know."},
        ],
        "diarization": [
            {"start": 4.5, "end": 7.5, "speaker": "SPEAKER_02"},
        ],
        "transcript_meta": {"status": "success"},
    }

    result = audio_speaker_merge(item, {})

    assert [{k: row[k] for k in ('start','end','text','speaker')} for row in result['speaker_transcript']] == [
        {"start": 5.0, "end": 7.0, "text": "I know.", "speaker": "SPEAKER_02"},
    ]
    assert result["transcript_meta"]["segment_count"] == 1
    assert result['speaker_transcript'][0]['attribution_status']=='unreviewed'
    assert result["transcript_meta"]["speakers"] == ["SPEAKER_02"]
