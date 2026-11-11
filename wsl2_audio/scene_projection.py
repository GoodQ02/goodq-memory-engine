"""One source-bound projection into existing scenes; no new recognition or purity rules."""
from copy import deepcopy
from fractions import Fraction
import hashlib
import math

from wsl2_audio.evidence_contract import validate_evidence
from wsl2_audio.recording_audio import _json_bytes
from wsl2_audio.source_clock import SourceClock, SampleSpan

SCHEMA = 'goodq.scene_audio.v1'


def _digest(value):
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _scene_rows(scenes):
    rows, identifiers = [], set()
    for scene in scenes:
        ident = scene.get('scene_id')
        if not isinstance(ident, str) or not ident or ident in identifiers:
            raise ValueError('Scenes require unique nonempty scene IDs')
        for field in ('start', 'end'):
            if type(scene.get(field)) not in (int, float) or not math.isfinite(scene[field]):
                raise ValueError('Invalid scene time')
        start, end = Fraction(str(scene['start'])), Fraction(str(scene['end']))
        if start >= end:
            raise ValueError('Scene must have positive duration')
        rows.append((ident, start, end))
        identifiers.add(ident)
    return sorted(rows, key=lambda row: (row[1], row[2], row[0]))


def _clock(evidence):
    source = evidence['source']
    return SourceClock(source['sample_rate'], source['sample_count'], source['origin_num'], source['origin_den'])


def _media_span(span, clock):
    return clock.media_time(span['start']), clock.media_time(span['end'])


def _owner(span, clock, scenes):
    start, end = _media_span(span, clock)
    matches = [(min(end, b)-max(start, a), a, ident) for ident, a, b in scenes if start < b and a < end]
    return min(matches, key=lambda row: (-row[0], row[1], row[2]))[2] if matches else None


def assign_owners(evidence, scenes):
    validate_evidence(evidence)
    rows = _scene_rows(scenes)
    if evidence['source'].get('audio_track') == 'absent':
        return {}
    clock = _clock(evidence)
    return {u['id']: _owner(u['span'], clock, rows) for u in evidence['utterances']}


def seal_scene_audio(payload):
    value = deepcopy(payload)
    value.pop('content_sha256', None)
    value['content_sha256'] = _digest(value)
    return value


def validate_scene_audio(payload):
    if not isinstance(payload, dict) or payload.get('schema') != SCHEMA:
        raise ValueError('Unsupported scene audio evidence schema')
    value = {k: v for k, v in payload.items() if k != 'content_sha256'}
    if payload.get('content_sha256') != _digest(value):
        raise ValueError('Scene audio evidence changed after projection')
    _scene_rows([payload['scene']])
    if not isinstance(payload.get('source'), dict) or not payload['source'].get('sha256'):
        raise ValueError('Scene audio source identity missing')
    if payload['source'].get('audio_track') != 'absent':
        clock = _clock(payload)
        for row in payload['utterances'] + payload['sound_events'] + payload['speaker_tracks'] + payload['overlap']:
            clock.require_span(SampleSpan(**row['span']))
            start, end = _media_span(row['span'], clock)
            if row['media_span'] != {'start': float(start), 'end': float(end)}:
                raise ValueError('Scene audio media clock differs from source samples')
            scene = payload['scene']
            expected = {'start': float(max(start, Fraction(str(scene['start'])))),
                        'end': float(min(end, Fraction(str(scene['end']))))}
            if row['display_span'] != expected or expected['start'] >= expected['end']:
                raise ValueError('Scene display span is not the source intersection')
            if row['ownership'] != ('owner' if row['owner_scene_id'] == scene['scene_id'] else 'reference'):
                raise ValueError('Scene audio ownership contradiction')
        units = {u['id']: u for u in payload['utterances']}
        if len(units) != len(payload['utterances']):
            raise ValueError('Duplicate scene utterance')
        for review in payload.get('voice_reviews', []):
            from wsl2_audio.scene_consumers import validate_review
            validate_review(review, payload['source'])
            u = units[review['utterance_id']]
            if any(review[key] != u[key] for key in ('span', 'channel', 'owner_scene_id', 'eligibility')):
                raise ValueError('Review differs from projected utterance')
        for signature in payload.get('voice_signatures', []):
            from wsl2_audio.scene_consumers import validate_signature
            validate_signature(signature)
            if signature['owner_scene_id'] != payload['scene']['scene_id']:
                raise ValueError('Referenced scenes cannot own a voice signature')
            for ident in signature['utterance_ids']:
                if units[ident]['eligibility']['voice_sample']['status'] != 'eligible' or units[ident]['ownership'] != 'owner':
                    raise ValueError('Voice signature contains an ineligible or referenced utterance')
    return payload


def project_audio(evidence: dict, scenes: list[dict]) -> dict[str, dict]:
    """Preserve full evidence everywhere it intersects; only one scene owns a contribution."""
    validate_evidence(evidence)
    scene_rows = _scene_rows(scenes)
    absent = evidence['source'].get('audio_track') == 'absent'
    clock = None if absent else _clock(evidence)
    # A new execution of unchanged analysis must not rename acoustic tracks or
    # re-embed/count the same source contribution. Run/epoch remain provenance.
    recording_id = _digest({'source': evidence['source'],
        'worker_sha256': evidence['provenance']['worker_sha256'],
        'config_sha256': evidence['provenance']['config_sha256']})
    evidence_digest = _digest(evidence)
    owners = assign_owners(evidence, scenes)
    output = {}
    tracks = evidence.get('enrichment_observations', {}).get('speaker_activity', {}).get('tracks', [])
    for ident, left, right in scene_rows:
        def rows(values, *, utterances=False, speakers=False):
            selected = []
            for original in values:
                start, end = _media_span(original['span'], clock)
                if not (start < right and left < end):
                    continue
                row = deepcopy(original)
                row['media_span'] = {'start': float(start), 'end': float(end)}
                row['display_span'] = {'start': float(max(start, left)), 'end': float(min(end, right))}
                row['owner_scene_id'] = owners[row['id']] if utterances else _owner(row['span'], clock, scene_rows)
                row['ownership'] = 'owner' if row['owner_scene_id'] == ident else 'reference'
                if speakers:
                    local = f"c{row['channel']}:{row['speaker']}"
                    row['track_id'] = recording_id + ':' + local
                    row['identity_claim'] = False
                if utterances:
                    quality = row.get('quality', {})
                    raw = {key: quality[key] for key in ('avg_logprob', 'no_speech_probability')
                           if type(quality.get(key)) in (float, int) and math.isfinite(quality[key])}
                    row['confidence'] = {'status': 'uncalibrated_model_score' if raw else 'unavailable',
                        'basis': 'native_decoder_block', 'raw': raw, 'recognition_accuracy': 'unqualified',
                        'warnings': deepcopy(row['eligibility']['transcript']['reasons'])}
                    row['track_id'] = (recording_id + ':' + row['speaker']['id']) if row['speaker'].get('id') else None
                selected.append(row)
            return selected
        projected = {
            'schema': SCHEMA, 'recording_id': recording_id, 'recording_evidence_sha256': evidence_digest,
            'source': deepcopy(evidence['source']), 'provenance': deepcopy(evidence['provenance']),
            'scene': {'scene_id': ident, 'start': float(left), 'end': float(right)},
            'status': evidence['status'], 'stages': deepcopy(evidence['stages']),
            'quality_qualification': evidence['quality_qualification'],
            'utterances': rows(evidence['utterances'], utterances=True),
            'sound_events': rows(evidence['sound_events']), 'overlap': rows(evidence['overlap']),
            'speaker_tracks': rows(tracks, speakers=True), 'voice_reviews': [],
            'voice_review_status': 'not_materialized', 'vocal_delivery': [],
        }
        unit_ids = {u['id'] for u in projected['utterances']}
        projected['vocal_delivery'] = [deepcopy(v) for v in evidence.get('vocal_delivery', []) if v['utterance_id'] in unit_ids]
        output[ident] = validate_scene_audio(seal_scene_audio(projected))
    return output


def _conservative_segment_confidence(members):
    from wsl2_audio.channel_reconciliation import _confidence
    raw = {}
    for key, combine in (('avg_logprob', min), ('no_speech_probability', max)):
        value = _confidence(members, key, combine)
        if value is not None:
            raw[key] = value
    warnings = []
    for member in members:
        for reason in member['eligibility']['transcript']['reasons']:
            if reason not in warnings:
                warnings.append(reason)
    return {'status': 'uncalibrated_model_score' if raw else 'unavailable',
            'basis': 'native_decoder_block', 'raw': raw,
            'recognition_accuracy': 'unqualified', 'warnings': warnings}


def _transcript_segments(projection, offset):
    """Deduplicate co-occurring matching cross-channel text in linear consumer views only."""
    from wsl2_audio.channel_reconciliation import _matching_occurrence
    eligible = [u for u in projection['utterances']
                if u['eligibility']['transcript']['status'] == 'eligible']
    segments, dedup_groups, consumed = [], [], set()
    for index, first in enumerate(eligible):
        if index in consumed:
            continue
        members = [first]
        channels = set(first.get('source_channels', [first['channel']]))
        if first.get('resolution') != 'conflicting_hypotheses':
            for j in range(index + 1, len(eligible)):
                other = eligible[j]
                if j in consumed or other.get('resolution') == 'conflicting_hypotheses':
                    continue
                other_channels = set(other.get('source_channels', [other['channel']]))
                if channels & other_channels:
                    continue
                if all(_matching_occurrence(member, other, projection['utterances']) for member in members):
                    members.append(other)
                    channels |= other_channels
                    consumed.add(j)
        if len(members) == 1:
            u = first
            segments.append({'id': u['id'], 'text': u['text'],
                'start': u['display_span']['start'] - offset, 'end': u['display_span']['end'] - offset,
                'speaker': u['track_id'], 'speaker_status': u['speaker']['status'],
                'source_span': deepcopy(u['span']), 'owner_scene_id': u['owner_scene_id'],
                'confidence': deepcopy(u['confidence']), 'timing_scope': 'scene_display_only'})
            continue
        members.sort(key=lambda u: (min(u.get('source_channels', [u['channel']])), u['channel'], u['id']))
        rep = members[0]
        track_ids = {u['track_id'] for u in members if u.get('track_id')}
        same_speaker = len(track_ids) == 1 and all(u.get('track_id') for u in members)
        speaker = rep['track_id'] if same_speaker else None
        speaker_status = rep['speaker']['status'] if same_speaker else 'unresolved'
        union_span = {'start': min(u['span']['start'] for u in members),
                      'end': max(u['span']['end'] for u in members)}
        alternatives = [{'id': u['id'], 'channel': u['channel'],
                         'source_channels': list(u.get('source_channels', [u['channel']])),
                         'span': deepcopy(u['span']), 'track_id': u['track_id'],
                         'owner_scene_id': u['owner_scene_id']} for u in members]
        segments.append({'id': rep['id'], 'text': rep['text'],
            'start': min(u['display_span']['start'] for u in members) - offset,
            'end': max(u['display_span']['end'] for u in members) - offset,
            'speaker': speaker, 'speaker_status': speaker_status,
            'source_span': union_span, 'owner_scene_id': rep['owner_scene_id'],
            'confidence': _conservative_segment_confidence(members),
            'timing_scope': 'scene_display_only',
            'unreconciled_channel_alternatives': alternatives})
        dedup_groups.append({'representative_id': rep['id'],
            'member_ids': [u['id'] for u in members],
            'channels': sorted(channels), 'span': deepcopy(union_span),
            'reason': 'cooccurring_matching_surface_unreconciled_channels'})
    if dedup_groups:
        segments.sort(key=lambda row: (row['start'], row['end'],
            row['source_span']['start'], row['source_span']['end'], row['id']))
    return segments, dedup_groups


def legacy_audio(projection):
    """Compatibility fields use clipped scene seconds; full playback/eligibility stays versioned."""
    projection = validate_scene_audio(projection)
    offset = projection['scene']['start']
    segments, dedup_groups = _transcript_segments(projection, offset)
    text = ' '.join(row['text'] for row in segments)
    tracks = [{'speaker': row['track_id'], 'start': row['display_span']['start']-offset,
               'end': row['display_span']['end']-offset, 'identity_claim': False} for row in projection['speaker_tracks']]
    events = [dict(deepcopy(row), start=row['display_span']['start']-offset,
                   end=row['display_span']['end']-offset) for row in projection['sound_events']]
    absent = projection['source'].get('audio_track') == 'absent'
    recognition = projection['stages'].get('recognition', {})
    outcome = ('transcript_available' if text else 'low_confidence' if projection['utterances'] else
        'runtime_failure' if recognition.get('status') in ('error', 'unavailable') else
        'no_speech' if recognition.get('reason') == 'digital_silence' else 'unclassified')
    reason = ('audio_track_absent' if absent else 'digital_silence' if outcome == 'no_speech' else
              'versioned_recording_evidence')
    return {'audio_evidence': deepcopy(projection), 'transcript': text, 'segments': segments,
        'speaker_transcript': deepcopy(segments), 'transcript_meta': {'engine': 'recording_audio_v1',
            'status': 'ok' if text else 'unresolved' if projection['utterances'] else 'empty',
            'segments': deepcopy(segments), 'recognition_accuracy': 'unqualified', 'time_basis': 'scene_relative_display',
            **({'channel_deduplication': {'method': 'matching_occurrence_disjoint_channels_v1',
                'groups': dedup_groups}} if dedup_groups else {}),
            **({'transcription_context': deepcopy(projection['provenance']['transcription_context'])}
               if projection['provenance'].get('transcription_context') else {})},
        'transcript_outcome': outcome, 'transcript_outcome_reason': reason,
        'speakers': sorted({row['speaker'] for row in tracks}), 'speaker_count': len({row['speaker'] for row in tracks}),
        'speaker_segments': tracks, 'diarization': deepcopy(tracks),
        'diarization_status': projection['stages'].get('speaker_activity', {}).get('status'),
        'emotion': None, 'audio_emotion': None, 'emotion_scores': {},
        'emotion_status': 'uncertain' if projection['vocal_delivery'] else 'insufficient_evidence',
        'emotion_segments': deepcopy(projection['vocal_delivery']),
        'emotion_input': {'policy': 'recording_speech_v1', 'status': 'qualified_inputs_only',
                          'scene_mood': 'not_inferred_from_individual_delivery'},
        'sentiment': None, 'sentiment_label': None, 'sentiment_score': None,
        'sentiment_meta': {'status': 'not_run', 'reason': 'recording_transcript_analysis_not_connected'},
        'emotions': [], 'emotion_meta': {'status': 'not_run'},
        'text_emotion_ranking': [], 'text_emotion_meta': {'status': 'not_run'},
        'music_events': [], 'time_hints': {},
        'sound_events': events, 'sound_event_meta': {'basis': 'independent_acoustic',
            'status': projection['stages'].get('acoustic_events', {}).get('status'), 'quality': 'unqualified'},
        'speaker_voice_signatures': deepcopy(projection.get('voice_signatures', [])),
        'speaker_voice_signature_meta': {'status': projection.get('voice_signature_status', 'not_materialized'),
            'errors': deepcopy(projection.get('voice_signature_errors', [])),
            'selection': deepcopy(projection.get('voice_selection', {})), 'identity_claim': False},
        'audio_backend_selected': 'recording', 'audio_backend_effective': 'recording',
        'audio_backend_effective_reason': 'shared_recording_evidence', 'status': 'success' if projection['status'] != 'error' else 'error'}
