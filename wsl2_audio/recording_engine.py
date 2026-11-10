"""Recording observations on one source clock; no scene or VAD orchestration."""

from copy import deepcopy
import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path
import sys

from wsl2_audio.source_clock import SampleSpan, SourceClock, plan_windows
from wsl2_audio.eligibility import POLICY, assess_eligibility
from wsl2_audio.evidence_contract import validate_evidence
from wsl2_audio.recording_audio import prepare_recording, read_channel, publish_audio_artifact, _atomic_json, _sha_file
from wsl2_audio.recognition import load_recognizer, verify_recognizer, refresh_speech_activity, transcription_context
from wsl2_audio.profile_identity import METHOD as CONFIG_IDENTITY_METHOD, profile_identity


def _identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def _bounded(value, clock):
    span = SampleSpan(value['start'], value['end'])
    clock.require_span(span)
    return span


def _surface_key(row):
    """Conservative comparison only; never rewrite the retained decoder text."""
    # Leading decimal punctuation is numeric evidence, not sentence decoration.
    tokens = [t.lstrip('!?;:\"“”()[]').rstrip('.,!?;:\"“”()[]') or t
              for t in row['text'].casefold().replace('’', "'").split()]
    language = row.get('language', {})
    if language.get('configured') == 'en' or language.get('value') == 'en':
        small = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(), map(str, range(20))))
        months = set('january february march april may june july august september october november december'.split())
        for index, token in enumerate(tokens):
            tokens[index] = small.get(token, token)
            if index and tokens[index-1] in months:
                date = re.fullmatch(r'([1-9]|[12][0-9]|3[01])(st|nd|rd|th)', tokens[index])
                if date:
                    number = int(date[1])
                    suffix = 'th' if 10 < number % 100 < 14 else {1:'st',2:'nd',3:'rd'}.get(number % 10, 'th')
                    if date[2] == suffix:
                        tokens[index] = date[1]
    return tuple(tokens)


def resolve_observations(observations: list, clock: SourceClock) -> dict:
    """Merge only unique matching occurrences in shared source context.

Conflicting text is retained as alternatives. Cross-window local speaker labels
are not a recurrence model and never become global identities by label number.
"""
    rows, windows, source_hash = [], set(), None
    for observation in sorted(observations, key=lambda item: item['window_id']):
        window_id = observation['window_id']
        if window_id in windows:
            raise ValueError('Duplicate window observation')
        windows.add(window_id)
        digest = observation['source_sha256']
        if not re.fullmatch('[0-9a-f]{64}', digest) or (source_hash is not None and source_hash != digest):
            raise ValueError('Conflicting source identity')
        source_hash = digest
        context = _bounded(observation['context'], clock)
        for index, utterance in enumerate(observation.get('utterances', [])):
            span = _bounded(utterance['span'], clock)
            if not context.start <= span.start < span.end <= context.end:
                raise ValueError('Utterance outside its actual input window')
            row = deepcopy(utterance)
            row.update(window_id=window_id, channel=observation['channel'],
                       observation_ids=[f'{window_id}:{index}'],
                       context_margin=min(span.start-context.start, context.end-span.end))
            rows.append(row)
    rows.sort(key=lambda row: (row['span']['start'], row['span']['end'], row['channel'], row['observation_ids']))
    pairs, matches = [], {}
    for left_index, left in enumerate(rows):
        a = _bounded(left['span'], clock)
        for right_index in range(left_index + 1, len(rows)):
            right = rows[right_index]
            b = _bounded(right['span'], clock)
            if b.start >= a.end:
                break
            if left['window_id'] == right['window_id'] or left['channel'] != right['channel']:
                continue
            intersection = min(a.end, b.end)-max(a.start, b.start)
            same_text = _surface_key(left) == _surface_key(right)
            same_occurrence = intersection * 5 >= max(a.end-a.start, b.end-b.start) * 4
            if same_text and same_occurrence:
                pairs.append((left_index, right_index))
                for index, other in ((left_index, right_index), (right_index, left_index)):
                    key = (index, rows[other]['window_id'])
                    matches[key] = matches.get(key, 0) + 1
            else:
                left['resolution'] = right['resolution'] = 'conflicting_hypotheses'
    parents = list(range(len(rows)))

    def root(index):
        while parents[index] != index:
            index = parents[index]
        return index

    for left, right in pairs:
        if matches[(left, rows[right]['window_id'])] == matches[(right, rows[left]['window_id'])] == 1:
            parents[root(right)] = root(left)
        else:
            rows[left]['resolution'] = rows[right]['resolution'] = 'conflicting_hypotheses'
    grouped = {}
    for index, row in enumerate(rows):
        grouped.setdefault(root(index), []).append(row)
    resolved, overlap = [], []
    for group in grouped.values():
        group.sort(key=lambda row: (-int(row['completeness'] == 'complete'), -row['context_margin'], row['window_id']))
        chosen = deepcopy(group[0])
        chosen['observation_ids'] = sorted(value for row in group for value in row['observation_ids'])
        chosen.pop('window_id')
        chosen.pop('context_margin')
        chosen['resolution'] = ('conflicting_hypotheses' if any(row.get('resolution') == 'conflicting_hypotheses' for row in group)
                                else 'matching_source_observations' if len(group) > 1 else 'single_observation')
        if len({row['text'] for row in group}) > 1:
            chosen['text_resolution'] = {'method': 'surface_equivalence_v1',
                'rewritten': False, 'variants': [{'text': row['text'], 'observation_ids': row['observation_ids']}
                                                for row in sorted(group, key=lambda row: row['observation_ids'])]}
        speakers = {(row['speaker'].get('status'), row['speaker'].get('id')) for row in group}
        if len(speakers) > 1:
            chosen['speaker'] = {'status': 'unresolved', 'id': None,
                                 'candidates': sorted({value for _, value in speakers if value})}
            overlap.append({'span': deepcopy(chosen['span']), 'status': 'unresolved',
                            'reason': 'cross_window_speaker_disagreement'})
        chosen['id'] = 'utterance-' + _identity({'source': source_hash, 'channel': chosen['channel'],
            'span': chosen['span'], 'text': chosen['text'], 'observations': chosen['observation_ids']})
        resolved.append(chosen)
    resolved.sort(key=lambda row: (row['span']['start'], row['span']['end'], row['channel'], row['id']))
    for index, left in enumerate(resolved):
        a = _bounded(left['span'], clock)
        for right in resolved[index+1:]:
            b = _bounded(right['span'], clock)
            if b.start >= a.end:
                break
            if left['channel'] != right['channel']:
                overlap.append({'span': {'start': max(a.start, b.start), 'end': min(a.end, b.end)},
                                'channels': sorted([left['channel'], right['channel']]),
                                'status': 'unresolved', 'reason': 'simultaneous_channel_observations'})
            elif left.get('native_span') or right.get('native_span'):
                overlap.append({'span': {'start': max(a.start, b.start), 'end': min(a.end, b.end)},
                                'channel': left['channel'], 'status': 'unresolved',
                                'reason': 'aligned_envelope_collision'})
    overlap = sorted({_identity(row): row for row in overlap}.values(), key=lambda row: (row['span']['start'], row['span']['end'], row['reason']))
    return {'utterances': resolved, 'overlap': overlap}


def _union(spans):
    result = []
    for span in sorted(spans, key=lambda row: (row['start'], row['end'])):
        if result and span['start'] <= result[-1]['end']:
            result[-1]['end'] = max(result[-1]['end'], span['end'])
        else:
            result.append(dict(span))
    return result


def _covers_interval(spans, start, end):
    return any(row['start'] <= start and end <= row['end'] for row in spans)


def _recording_coverage(observations, clock, channels, selected_channel=None):
    supports = {channel: {'analyzed': [], 'digital_silence': []}
                for channel in (range(channels) if selected_channel is None else [selected_channel])}
    for observation in observations:
        if observation['channel'] not in supports:
            continue
        support = supports[observation['channel']]
        if observation['status'] == 'digital_silence':
            support['digital_silence'].append(observation['context'])
        else:
            support['analyzed'].extend(observation.get('assessed_spans', []))
    edges = {0, clock.sample_count}
    for support in supports.values():
        for status, spans in support.items():
            support[status] = _union(spans)
            for row in spans:
                _bounded(row, clock)
                edges.update((row['start'], row['end']))
    edges = sorted(edges)
    coverage = []
    for start, end in zip(edges, edges[1:]):
        states = [('analyzed' if _covers_interval(value['analyzed'], start, end) else
                   'digital_silence' if _covers_interval(value['digital_silence'], start, end) else 'error')
                  for value in supports.values()]
        status = 'error' if 'error' in states else 'analyzed' if 'analyzed' in states else 'digital_silence'
        if coverage and coverage[-1]['status'] == status:
            coverage[-1]['span']['end'] = end
        else:
            coverage.append({'span': {'start': start, 'end': end}, 'status': status})
    return coverage


def _worker_digest():
    files = ('source_clock.py', 'recording_audio.py', 'evidence_contract.py', 'eligibility.py',
             'recording_engine.py', 'recognition.py', 'transcription_contract.py', 'model_cache.py',
             'enrichment.py', 'enrichment_models.py', 'bounded_audio.py', 'phrase_resolution.py', 'frame_events.py', 'channel_reconciliation.py',
             'process_audio.py', 'acoustic_events.py', 'speaker_signature.py', 'scene_projection.py', 'scene_consumers.py', 'profile_identity.py')
    return _identity({name: _sha_file(Path(__file__).with_name(name)) for name in files})


def _window_samples(seconds, rate, *, positive):
    if type(seconds) not in (int, float):
        raise ValueError('Window duration must be numeric')
    value = Fraction(str(seconds))*rate
    if value.denominator != 1 or value < int(positive):
        raise ValueError('Window duration must map exactly to source samples')
    return int(value)


def analyze_recording(request: dict, profile: dict, artifact_root: Path) -> dict:
    """Candidate caller: prepare -> fixed windows -> observations -> one gate.

The existing runner remains responsible for resource admission and the worker
deadline. This API never mutates scenes, identities, services or model packages.
"""
    if profile.get('schema_version') != 1 or profile.get('eligibility_policy') != POLICY:
        raise ValueError('Unsupported recording profile or speech policy')
    spelling_context = transcription_context(profile)
    language = profile.get('language')
    if language != 'auto' and (not isinstance(language, str) or not re.fullmatch('[a-z]{2,3}', language)):
        raise ValueError('Configure a language code or explicit auto detection')
    if profile['window']['core_seconds'] + 2*profile['window']['context_seconds'] > 30:
        raise ValueError('Pinned recognizer windows cannot exceed 30 seconds')
    worker_hash, config_hash = _worker_digest(), _identity(profile_identity(profile))
    models = [{key: spec[key] for key in ('id', 'revision', 'sha256')}
              for spec in (profile['recognizer'], profile['speech_activity_model'])]
    prepared_request = deepcopy(request)
    prepared_request['fingerprint'] = {
        'source_revision': request['fingerprint']['source_revision'], 'worker_sha256': worker_hash,
        'config_sha256': config_hash, 'models': models, 'window': profile['window'],
    }
    recording = prepare_recording(prepared_request, Path(artifact_root)/'decode')
    provenance = {'run_id': request['run_id'], 'epoch_id': request['epoch_id'],
                  'source_revision': prepared_request['fingerprint']['source_revision'],
                  'worker_sha256': worker_hash, 'config_sha256': config_hash, 'models': models,
                  'config_identity_method': CONFIG_IDENTITY_METHOD}
    if spelling_context:
        provenance['transcription_context'] = spelling_context
    result = {'schema_version': 1, 'source': deepcopy(recording['source']), 'provenance': provenance,
              'utterances': [], 'overlap': [], 'sound_events': [], 'coverage': [],
              'eligibility_policy': deepcopy(POLICY), 'stages': {},
              'quality_qualification': 'unqualified', 'model_adoption': 'baseline_candidate_only'}
    if recording['status'] == 'not_applicable':
        result['source']['audio_track'] = 'absent'
        result.update(status='not_applicable', reason='audio_track_absent')
        result['stages']['decode'] = {'status': 'not_applicable', 'reason': 'audio_track_absent'}
        publish_audio_artifact(result, Path(artifact_root)/'evidence.json')
        return result
    meta = recording['source']
    clock = SourceClock(meta['sample_rate'], meta['sample_count'], meta['origin_num'], meta['origin_den'])
    core = _window_samples(profile['window']['core_seconds'], clock.sample_rate, positive=True)
    context = _window_samples(profile['window']['context_seconds'], clock.sample_rate, positive=False)
    for duration in profile['window'].values():
        _window_samples(duration, 16000, positive=False)
    result['source']['decode_checkpoint_key'] = recording['checkpoint_key']
    observations, recognizer, verified, load_error = [], None, None, None
    cache_dir = Path(artifact_root)/'observations'
    try:
        for window in plan_windows(clock, core, context):
            for channel in range(meta['channels']):
                samples = read_channel(recording, window.context, channel)
                window_id = f'w{window.index}:c{channel}'
                base = {'source_sha256': meta['sha256'], 'window_id': window_id, 'channel': channel,
                        'core': vars(window.core), 'context': vars(window.context)}
                if not any(samples):
                    observations.append({**base, 'status': 'digital_silence', 'utterances': [],
                                         'assessed_spans': [], 'speech_activity': {'status': 'not_applicable'}})
                    continue
                if verified is None and load_error is None:
                    try:
                        verified = verify_recognizer(profile)
                        if verified['models'] != models:
                            raise ValueError('Verified models differ from requested profile')
                        result['provenance']['runtime'] = verified['runtime']
                    except Exception as exc:
                        load_error = str(exc)
                identity = {'source': meta, 'window': base, 'config': config_hash, 'worker': worker_hash,
                            'runtime': verified['runtime'] if verified else None}
                key = _identity(identity)
                path = cache_dir/(key + '.json')
                if load_error is not None:
                    observed = {'status': 'error', 'reason': 'recognizer_unavailable', 'error': load_error,
                                'utterances': [], 'assessed_spans': [], 'speech_activity': {'status': 'unavailable'}}
                elif path.is_file():
                    cached = json.loads(path.read_text(encoding='utf-8'))
                    observed = cached['observation']
                    if cached['identity'] != identity or cached['sha256'] != _identity(observed):
                        raise ValueError('Window checkpoint identity or content mismatch')
                    if observed.get('speech_activity', {}).get('status') != 'ok':
                        # One failed-stage recovery per requested resume; the
                        # successful recognized text and alignment are reused.
                        observed = refresh_speech_activity(observed, samples, clock.sample_rate, window.context)
                        _atomic_json({'identity': identity, 'observation': observed,
                                      'sha256': _identity(observed)}, path)
                else:
                    try:
                        if recognizer is None:
                            recognizer = load_recognizer(profile, verified)
                        observed = recognizer.observe(samples, clock.sample_rate, window.context,
                                                      None if language == 'auto' else language)
                        if observed['status'] not in ('ok', 'partial', 'error'):
                            raise ValueError('Invalid recognition stage outcome')
                        resolve_observations([{**observed, **base}], clock)
                        for span in observed.get('assessed_spans', []):
                            _bounded(span, clock)
                        # Raw successful observations are immutable and reusable. Failed
                        # work remains diagnostic evidence, never a successful cache entry.
                        if observed['status'] == 'ok':
                            _atomic_json({'identity': identity, 'observation': observed,
                                          'sha256': _identity(observed)}, path)
                        else:
                            _atomic_json({**base, **observed}, cache_dir/(key + '.failed.json'))
                    except Exception as exc:
                        observed = {'status': 'error', 'reason': 'recognition_window_failed', 'error': str(exc),
                                    'utterances': [], 'assessed_spans': [], 'speech_activity': {'status': 'error'}}
                        _atomic_json({**base, **observed}, cache_dir/(key + '.failed.json'))
                observations.append({**observed, **base})
    finally:
        if recognizer is not None and callable(getattr(recognizer, 'close', None)):
            recognizer.close()
    result['coverage'] = _recording_coverage(observations, clock, meta['channels'])
    result['channel_coverage'] = {str(channel): _recording_coverage(observations, clock, meta['channels'], channel)
                                  for channel in range(meta['channels'])}
    result.update(resolve_observations(observations, clock))
    result['window_observations'] = observations
    if meta['channels'] > 1:
        from wsl2_audio.channel_reconciliation import reconcile_channels
        result = reconcile_channels(result, recording)
    active = [row for row in observations if row['status'] != 'digital_silence']
    for name, model_index in (('recognition', 0), ('speech_activity', 1)):
        selected = [row if name == 'recognition' else row.get('speech_activity', {}) for row in active]
        spans = _union([span for row in selected for span in row.get('assessed_spans', [])] +
                       [row['context'] for row in observations if row['status'] == 'digital_silence'])
        successes = bool(selected) and any(row.get('status') in ('ok', 'partial') for row in selected)
        stage = {'status': 'ok' if active and all(row.get('status') == 'ok' for row in selected) else
                          'partial' if successes else 'error' if active else 'not_applicable',
                 'model_id': models[model_index]['id']}
        if stage['status'] in ('ok', 'partial'):
            stage['assessed_spans'] = spans
            stage['channel_assessed_spans'] = {str(channel): _union([
                span for row in observations if row['channel'] == channel
                for span in ([row['context']] if row['status'] == 'digital_silence' else
                             (row if name == 'recognition' else row.get('speech_activity', {})).get('assessed_spans', []))])
                for channel in range(meta['channels'])}
        if stage['status'] != 'ok':
            stage['reason'] = 'digital_silence' if not active else 'incomplete_window_assessment'
        result['stages'][name] = stage
    for name in ('speaker_activity', 'overlap', 'acoustic_events', 'vocal_delivery', 'voice_samples'):
        result['stages'][name] = {'status': 'not_run', 'reason': 'not_connected_in_recognition_milestone'}
    for utterance in result['utterances']:
        utterance['eligibility'] = assess_eligibility(utterance, result, POLICY)
    result['status'] = ('not_applicable' if not active else 'ok' if all(row['status'] == 'ok' and
                        row.get('speech_activity', {}).get('status') == 'ok' for row in active)
                        else 'partial' if any(row['status'] in ('ok', 'partial') for row in active) else 'error')
    if profile.get('enrichment'):
        from wsl2_audio.enrichment import enrich_recording
        result = enrich_recording(result, profile, Path(artifact_root),
                                  staging_errors=request.get('native_model_staging_errors'))
    snapshot = validate_evidence(result)
    publish_audio_artifact(snapshot, Path(artifact_root)/'evidence.json')
    return snapshot


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 3:
        raise SystemExit('usage: python -m wsl2_audio.recording_engine REQUEST.json PROFILE.json OUTPUT_ROOT')
    request = json.loads(Path(args[0]).read_text(encoding='utf-8'))
    profile = json.loads(Path(args[1]).read_text(encoding='utf-8'))
    result = analyze_recording(request, profile, Path(args[2]))
    if 'scenes' in request:
        # Opt-in candidate consumer path. Scene decisions remain the caller's;
        # the recording engine never re-recognizes per-scene crops.
        from wsl2_audio.scene_consumers import publish_scene_audio
        from wsl2_audio.recording_audio import _load_checkpoint
        from wsl2_audio.scene_projection import legacy_audio
        key = result['source'].get('decode_checkpoint_key')
        recording = (_load_checkpoint(Path(args[2])/'decode'/('decode-'+key)/'recording.json',
                     key, result['source']['sha256']) if key else None)
        projections = publish_scene_audio(result, request['scenes'], recording, request['processing_root'])
        _atomic_json({ident: legacy_audio(value) for ident, value in projections.items()},
                     Path(args[2])/'scene_audio.json')
    print(json.dumps({'status': result['status'], 'utterances': len(result['utterances']),
                      'quality_qualification': result['quality_qualification']}))
    return 1 if result['status'] == 'error' else 0


if __name__ == '__main__':
    raise SystemExit(main())
