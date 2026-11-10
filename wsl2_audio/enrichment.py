"""Independent recording observations and consumers of the shared speech gate."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from wsl2_audio.eligibility import POLICY, assess_eligibility, select_inputs, stage_covers
from wsl2_audio.evidence_contract import _span, validate_evidence
from wsl2_audio.recording_audio import _atomic_json, _json_bytes, _load_checkpoint
from wsl2_audio.source_clock import SampleSpan, SourceClock


OBSERVATION_STAGES = ('speaker_activity', 'overlap', 'phrase_activity', 'acoustic_events')


def _clock(evidence):
    s = evidence['source']
    return SourceClock(s['sample_rate'], s['sample_count'], s['origin_num'], s['origin_den'])


def _hit(row, span, clock, channel):
    return row.get('channel') == channel and span.overlaps(_span(row['span'], clock))


def _support(regions, intervals, clock, within=None):
    """Fraction of positive speech samples independently covered, without padding."""
    total = covered = 0
    for row in regions:
        target = _span(row['span'], clock)
        if within is not None:
            start, end = max(target.start, within.start), min(target.end, within.end)
            if start >= end:
                continue
            target = SampleSpan(start, end)
        total += target.end - target.start
        cursor = target.start
        for part in sorted((_span(r['span'], clock) for r in intervals), key=lambda p: (p.start, p.end)):
            left, right = max(cursor, part.start), min(target.end, part.end)
            if left < right:
                covered += right-left
                cursor = right
    return covered/total if total else 0.


def observation_overlap(evidence, observations):
    """Rebuild observed exclusions using the currently recorded PCM proofs."""
    result = {'overlap': deepcopy(evidence.get('overlap', []))}
    clock = _clock(evidence)
    speakers, overlap = observations['speaker_activity'], observations['overlap']
    result['overlap'].extend(deepcopy(overlap.get('intervals', [])))
    result['overlap'].extend(dict(deepcopy(row), status='unresolved', reason='collapsed_local_speaker_change')
                             for row in speakers.get('flags', []))
    tracks = speakers.get('tracks', [])
    # Other retained channels are evidence too; no silent channel mixing or
    # identity match is used to declare simultaneous channel activity pure.
    for i, left in enumerate(tracks):
        for right in tracks[i+1:]:
            a, b = _span(left['span'], clock), _span(right['span'], clock)
            if left['channel'] != right['channel'] and a.overlaps(b):
                from wsl2_audio.channel_reconciliation import unreconciled_spans
                for remaining in unreconciled_spans(evidence, [left['channel'], right['channel']],
                        {'start': max(a.start, b.start), 'end': min(a.end, b.end)}):
                    result['overlap'].append({'span': remaining,
                        'status': 'unresolved', 'reason': 'simultaneous_source_channels'})
    return result['overlap']


def attach_observations(evidence: dict, observations: dict) -> dict:
    """Retain observations; qualify whole native or independently resolved phrases."""
    result = deepcopy(evidence)
    clock = _clock(result)
    result['enrichment_observations'] = deepcopy(observations)
    for name in OBSERVATION_STAGES:
        row = observations[name]
        result['stages'][name] = {key: deepcopy(row[key]) for key in
            ('status', 'reason', 'error', 'model_id', 'assessed_spans', 'channel_assessed_spans') if key in row}
    speakers, overlap, activity, acoustic = (observations[name] for name in OBSERVATION_STAGES)
    result['sound_events'] = [dict(deepcopy(row), evidence_basis='independent_acoustic')
                              for row in acoustic.get('events', [])]
    result['overlap'] = observation_overlap(result, observations)
    tracks = speakers.get('tracks', [])
    for u in result['utterances']:
        span, channel = _span(u['span'], clock), u.get('channel', 0)
        active = [row for row in tracks if _hit(row, span, clock, channel)]
        regions = [row for row in activity.get('regions', []) if _hit(row, span, clock, channel)]
        labels = sorted({row['speaker'] for row in active})
        second = [row for row in overlap.get('single_activity', []) if _hit(row, span, clock, channel)]
        from wsl2_audio.frame_events import METHOD, THRESHOLD
        speech_frames = [row for row in acoustic.get('speech_intervals', []) if _hit(row, span, clock, channel)]
        acoustic_coverage = _support(regions, speech_frames, clock, span)
        acoustic_supported = (acoustic.get('method') == METHOD and acoustic.get('threshold') == THRESHOLD
                              and acoustic_coverage >= POLICY['min_speech_coverage'])
        u['acoustic_support'] = {'method': acoustic.get('method'), 'threshold': acoustic.get('threshold'),
                                 'ordinary_speech_coverage': acoustic_coverage,
                                 'basis': 'frame_speech_classes_over_unpadded_voice_activity',
                                 'support_scope': 'utterance_intersection_v1'}
        source = u.get('phrase_source', {})
        left_seam, right_seam = source.get('left_seam'), source.get('right_seam')
        # A diarization turn may contain several sentences. At an independently
        # supported internal pause, its continued speaker label is not evidence
        # of a clipped phrase. Outer native edges remain conservative.
        complete = (bool(regions) and bool(active) and stage_covers(result, 'phrase_activity', span, clock, channel)
            and stage_covers(result, 'speaker_activity', span, clock, channel)
            and all(span.start <= row['span']['start'] < row['span']['end'] <= span.end for row in regions)
            and all(0 < row['span']['start'] and row['span']['end'] < clock.sample_count for row in regions)
            and all((left_seam is not None or 0 < row['span']['start'] >= span.start)
                    and (right_seam is not None or row['span']['end'] <= span.end and row['span']['end'] < clock.sample_count)
                    for row in active))
        u['completeness'] = 'complete' if complete else 'unresolved'
        u['boundary_evidence'] = {'status': 'supported' if complete else 'unresolved',
            'method': ('complete_phrase_with_observed_pauses' if source else
                       'reconciled_envelope_contains_unpadded_activity_and_speaker_turns' if u.get('envelope_source') else
                       'native_envelope_contains_unpadded_activity_and_speaker_turns'),
            'reason': 'model_supported_envelope_not_word_certification' if complete else 'unresolved_or_crossing_speech_edges',
            'regions': deepcopy(regions), 'speaker_turns': deepcopy(active), 'review_status': 'unreviewed'}
        primary_support = _support(regions, active, clock, span)
        secondary_support = _support(regions, second, clock, span)
        # Every reconciled channel must independently support the whole phrase.
        # Redundancy never lets a favorable channel override another's failure.
        for other_channel in u.get('source_channels', [channel]):
            if other_channel == channel:
                continue
            other_regions = [row for row in activity.get('regions', []) if _hit(row, span, clock, other_channel)]
            other_tracks = [row for row in tracks if _hit(row, span, clock, other_channel)]
            other_labels = {row['speaker'] for row in other_tracks}
            if len(other_labels) > 1:
                labels = sorted(set(labels) | {f'channel{other_channel}:{label}' for label in other_labels})
            elif not other_labels:
                primary_support = 0.
            primary_support = min(primary_support, _support(other_regions, other_tracks, clock, span))
            secondary_support = min(secondary_support, _support(other_regions,
                [row for row in overlap.get('single_activity', []) if _hit(row, span, clock, other_channel)], clock, span))
            acoustic_coverage = min(acoustic_coverage, _support(other_regions,
                [row for row in acoustic.get('speech_intervals', []) if _hit(row, span, clock, other_channel)], clock, span))
            complete = complete and (bool(other_regions) and bool(other_tracks)
                and stage_covers(result, 'phrase_activity', span, clock, other_channel)
                and stage_covers(result, 'speaker_activity', span, clock, other_channel)
                and all(span.start <= r['span']['start'] < r['span']['end'] <= span.end
                        and 0 < r['span']['start'] and r['span']['end'] < clock.sample_count for r in other_regions)
                and all((left_seam is not None or 0 < r['span']['start'] >= span.start)
                        and (right_seam is not None or r['span']['end'] <= span.end and r['span']['end'] < clock.sample_count)
                        for r in other_tracks))
        u['completeness'] = 'complete' if complete else 'unresolved'
        u['boundary_evidence']['status'] = 'supported' if complete else 'unresolved'
        u['boundary_evidence']['reason'] = 'model_supported_envelope_not_word_certification' if complete else 'unresolved_or_crossing_speech_edges'
        u['acoustic_support']['ordinary_speech_coverage'] = acoustic_coverage
        acoustic_supported = acoustic_supported and acoustic_coverage >= POLICY['min_speech_coverage']
        supported = (len(labels) == 1 and acoustic_supported
            and primary_support >= POLICY['min_speech_coverage'] and secondary_support >= POLICY['min_speech_coverage']
            and stage_covers(result, 'overlap', span, clock, channel)
            and stage_covers(result, 'acoustic_events', span, clock, channel))
        u['speaker'] = {'status': 'mixed' if len(labels) > 1 else 'single' if supported else 'unresolved',
                        'id': f'c{channel}:{labels[0]}' if supported else None,
                        'purity': 'supported_single' if supported else 'unresolved',
                        'candidates': labels, 'identity_claim': False,
                        'basis': 'independent_activity_agreement_and_frame_speech_support',
                        'primary_speech_coverage': primary_support, 'secondary_speech_coverage': secondary_support}
        u['eligibility'] = assess_eligibility(u, result, POLICY)
    return validate_evidence(result)


def select_voice_groups(evidence: dict, owners: dict, *, diagnostics=None) -> list[dict]:
    """Existing ECAPA duration/diversity rules, grouped only by owning scene/speaker."""
    clock = _clock(evidence)
    groups, voiced = {}, {}
    if diagnostics is not None:
        diagnostics.update(policy='recording_speech_v1', minimum_segment_seconds=.75,
            minimum_segments=2, minimum_voiced_seconds=4., maximum_segments=4,
            units=[{'utterance_id': u['id'], 'owner_scene_id': owners.get(u['id']),
                'speaker': u['speaker'].get('id'), 'channel': u.get('channel', 0),
                'gate': deepcopy(u['eligibility']['voice_sample'])} for u in evidence['utterances']], groups=[])
    for u in select_inputs(evidence, 'voice_sample'):
        owner = owners.get(u['id'])
        if not isinstance(owner, str) or not owner.strip():
            continue
        span = _span(u['span'], clock)
        regions = [_span(row['span'], clock) for row in u.get('boundary_evidence', {}).get('regions', [])]
        cursor, spoken = span.start, 0
        for part in sorted(regions, key=lambda p: (p.start, p.end)):
            start, end = max(cursor, part.start), min(span.end, part.end)
            if start < end:
                spoken += end-start
                cursor = end
        if spoken*4 < clock.sample_rate*3:
            if diagnostics is not None:
                next(row for row in diagnostics['units'] if row['utterance_id'] == u['id']).update(
                    voiced_seconds=spoken/clock.sample_rate, selection='below_segment_minimum')
            continue
        if diagnostics is not None:
            next(row for row in diagnostics['units'] if row['utterance_id'] == u['id']).update(
                voiced_seconds=spoken/clock.sample_rate, selection='group_candidate')
        voiced[u['id']] = spoken
        key = (owner, u['speaker']['id'], u.get('channel', 0))
        groups.setdefault(key, []).append(u)
    selected = []
    for (scene, speaker, channel), rows in sorted(groups.items()):
        # Stable longest-first selection; don't count overlapping evidence twice.
        chosen = []
        for u in sorted(rows, key=lambda u: (u['span']['start']-u['span']['end'], u['span']['start'], u['id'])):
            if not any(_span(u['span'], clock).overlaps(_span(v['span'], clock)) for v in chosen):
                chosen.append(u)
            if len(chosen) == 4:
                break
        chosen.sort(key=lambda u: (u['span']['start'], u['id']))
        samples = sum(u['span']['end']-u['span']['start'] for u in chosen)
        spoken = sum(voiced[u['id']] for u in chosen)
        if diagnostics is not None:
            diagnostics['groups'].append({'scene_id': scene, 'speaker': speaker, 'channel': channel,
                'utterance_ids': [u['id'] for u in chosen], 'segment_count': len(chosen),
                'voiced_seconds': spoken/clock.sample_rate, 'status': 'selected' if len(chosen) >= 2
                and spoken >= 4*clock.sample_rate else 'insufficient_qualified_speech',
                'reasons': (['below_segment_count'] if len(chosen) < 2 else []) +
                    (['below_total_voiced_duration'] if spoken < 4*clock.sample_rate else [])})
        if len(chosen) >= 2 and spoken >= 4*clock.sample_rate:
            selected.append({'scene_id': scene, 'speaker': speaker, 'channel': channel,
                             'utterance_ids': [u['id'] for u in chosen],
                             'spans': [deepcopy(u['span']) for u in chosen],
                             'source_samples': samples, 'voiced_samples': spoken})
    return selected


def enrich_recording(evidence: dict, profile: dict, artifact_root: Path, *, staging_errors=None) -> dict:
    """Observe the already decoded recording; no second decoder or ASR route."""
    from wsl2_audio.enrichment_models import RecordingObservers

    staging_errors = staging_errors or {}
    result = validate_evidence(evidence)
    if result['source'].get('audio_track') == 'absent':
        return result
    clock = _clock(result)
    key = result['source']['decode_checkpoint_key']
    path = Path(artifact_root)/'decode'/('decode-'+key)/'recording.json'
    recording = _load_checkpoint(path, key, result['source']['sha256'])
    if recording['source']['pcm_sha256'] != result['source']['pcm_sha256']:
        raise ValueError('Enrichment PCM differs from recognition PCM')
    try:
        observers = RecordingObservers(profile, result, recording)
    except Exception as exc:
        from wsl2_audio.model_cache import redact_sensitive_info
        for name in (*OBSERVATION_STAGES, 'vocal_delivery', 'voice_samples'):
            result['stages'][name] = {'status': 'unavailable', 'reason': 'independent_runtime_unavailable',
                                     'error': redact_sensitive_info(str(exc))}
        for u in result['utterances']:
            u['eligibility'] = assess_eligibility(u, result, POLICY)
        result['vocal_delivery'] = []
        if result['status'] == 'ok':
            result['status'] = 'partial'
        return validate_evidence(result)
    observations = {}
    for name in OBSERVATION_STAGES:
        spec = observers.spec(name)
        if spec and spec['id'] not in {m['id'] for m in result['provenance']['models']}:
            result['provenance']['models'].append({k: spec[k] for k in ('id', 'revision', 'sha256')})
        identity = {'source': result['source'], 'config': result['provenance']['config_sha256'],
                    'worker': result['provenance']['worker_sha256'], 'stage': name}
        if name == 'overlap':
            identity['primary_activity_sha256'] = hashlib.sha256(_json_bytes(observations['speaker_activity'])).hexdigest()
        cache = Path(artifact_root)/'enrichment'/ (hashlib.sha256(_json_bytes(identity)).hexdigest()+'.json')
        try:
            if name in staging_errors and not observers.silent:
                raise ValueError('Native model staging failed: '+staging_errors[name])
            observers.verify(name)
            if cache.is_file():
                saved = json.loads(cache.read_text(encoding='utf-8'))
                if saved['identity'] != identity or saved['sha256'] != hashlib.sha256(_json_bytes(saved['observation'])).hexdigest():
                    raise ValueError('Independent observation checkpoint mismatch')
                observed = saved['observation']
            else:
                observed = observers.observe(name, observations)
                if observed['status'] in ('ok', 'not_applicable'):
                    _atomic_json({'identity': identity, 'observation': observed,
                                  'sha256': hashlib.sha256(_json_bytes(observed)).hexdigest()}, cache)
            observations[name] = observed
        except Exception as exc:
            from wsl2_audio.model_cache import redact_sensitive_info
            observations[name] = {'status': 'error', 'reason': 'independent_observation_failed',
                                  'error': redact_sensitive_info(str(exc))}
    # Envelope tightening must see every independent veto, including acoustic
    # events in the original margins. Detector inputs are recording-level and
    # do not depend on phrase partitioning.
    from wsl2_audio.phrase_resolution import resolve_phrases
    from wsl2_audio.channel_reconciliation import extend_reconciliation_proofs, reconcile_phrase_channels
    result = resolve_phrases(result, observations)
    result = extend_reconciliation_proofs(result, recording)
    result = attach_observations(reconcile_phrase_channels(result, recording), observations)
    result['vocal_delivery'] = []
    if all(row['status'] == 'not_applicable' and row.get('reason') == 'digital_silence'
           for row in observations.values()):
        for name in ('vocal_delivery', 'voice_samples'):
            result['stages'][name] = {'status': 'not_applicable', 'reason': 'digital_silence'}
        result['voice_sample_candidates'] = []
        return validate_evidence(result)
    admitted = select_inputs(result, 'vocal_delivery')
    if admitted:
        spec = observers.spec('vocal_delivery')
        if spec and spec['id'] not in {m['id'] for m in result['provenance']['models']}:
            result['provenance']['models'].append({k: spec[k] for k in ('id', 'revision', 'sha256')})
        try:
            if 'vocal_delivery' in staging_errors and not observers.silent:
                raise ValueError('Native model staging failed: '+staging_errors['vocal_delivery'])
            observers.verify('vocal_delivery')
            pending, saved_predictions, checkpoints = [], {}, {}
            for u in admitted:
                from wsl2_audio.profile_identity import model_identity
                identity = {'source': result['source'], 'model': model_identity(spec),
                    'worker': result['provenance']['worker_sha256'], 'config': result['provenance']['config_sha256'],
                    'input': {key: u[key] for key in ('id', 'span', 'channel')}}
                path = Path(artifact_root)/'vocal_delivery'/(hashlib.sha256(_json_bytes(identity)).hexdigest()+'.json')
                checkpoints[u['id']] = (path, identity)
                if path.is_file():
                    saved = json.loads(path.read_text(encoding='utf-8'))
                    if saved['identity'] != identity or saved['sha256'] != hashlib.sha256(_json_bytes(saved['prediction'])).hexdigest():
                        raise ValueError('Vocal prediction checkpoint mismatch')
                    saved_predictions[u['id']] = saved['prediction']
                else:
                    pending.append(u)
            delivery = observers.vocal_delivery(pending) if pending else {'results': [], 'errors': []}
            validate_evidence(dict(result, vocal_delivery=delivery['results']))
            for prediction in delivery['results']:
                path, identity = checkpoints[prediction['utterance_id']]
                _atomic_json({'identity': identity, 'prediction': prediction,
                              'sha256': hashlib.sha256(_json_bytes(prediction)).hexdigest()}, path)
                saved_predictions[prediction['utterance_id']] = prediction
            result['vocal_delivery'] = [saved_predictions[u['id']] for u in admitted if u['id'] in saved_predictions]
            result['vocal_delivery_failures'] = delivery['errors']
            result['stages']['vocal_delivery'] = {'status': 'partial' if delivery['errors'] else 'ok', 'model_id': spec['id'],
                'qualification': 'unqualified_uncertain_estimates', 'input_utterance_ids': [u['id'] for u in admitted]}
            if delivery['errors']:
                result['stages']['vocal_delivery']['reason'] = 'incomplete_utterance_scoring'
        except Exception as exc:
            from wsl2_audio.model_cache import redact_sensitive_info
            result['stages']['vocal_delivery'] = {'status': 'error', 'reason': 'vocal_delivery_failed',
                                                  'error': redact_sensitive_info(str(exc))}
    else:
        result['stages']['vocal_delivery'] = {'status': 'insufficient_evidence', 'reason': 'no_complete_clear_single_voice'}
    # Recording analysis does not invent scene ownership to bypass signature rules.
    result['stages']['voice_samples'] = {'status': 'not_run', 'reason': 'scene_ownership_not_projected'}
    result['voice_sample_candidates'] = [u['id'] for u in select_inputs(result, 'voice_sample')]
    if any(row['status'] in ('error', 'unavailable', 'partial') for row in result['stages'].values()):
        result['status'] = 'partial' if result['utterances'] or result['sound_events'] else 'error'
    return validate_evidence(result)
