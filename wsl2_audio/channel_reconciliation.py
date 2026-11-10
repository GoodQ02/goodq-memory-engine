"""Reconcile redundant recording channels, without mixing audio or identifying people."""

from copy import deepcopy
import math

from wsl2_audio.recording_audio import read_channel
from wsl2_audio.source_clock import SampleSpan


METHOD = 'matching_text_and_bounded_waveform_residual_v1'
PHRASE_METHOD = 'resolved_phrase_matching_text_and_bounded_waveform_residual_v1'
# No gain, polarity, lag or denoising fit. Both whole-span and local residuals
# must be small. These bounds describe recording redundancy, never speech purity.
MAX_RELATIVE_RMS = .001
MAX_FRAME_RELATIVE_RMS = .01
FRAME_HZ = 50


def recognition_coverage(unit, evidence):
    """Recompute support on the current span, conservatively across source channels."""
    start, end = unit['span']['start'], unit['span']['end']
    coverage = []
    for channel in unit.get('source_channels', [unit.get('channel', 0)]):
        regions = sorted((r for w in evidence.get('window_observations', [])
                          if w.get('channel') == channel and w.get('speech_activity', {}).get('status') == 'ok'
                          for r in w['speech_activity'].get('spans', [])), key=lambda r: (r['start'], r['end']))
        if not regions:
            return None
        cursor, covered = start, 0
        for region in regions:
            a, b = max(cursor, region['start']), min(end, region['end'])
            if a < b:
                covered += b-a
                cursor = b
        coverage.append(covered/(end-start))
    return min(coverage)


def _confidence(members, key, combine):
    values = [u.get('quality', {}).get(key) for u in members]
    valid = lambda v: (type(v) in (int, float) and math.isfinite(v)
                       and (v <= 0 if key == 'avg_logprob' else 0 <= v <= 1))
    return combine(values) if all(valid(v) for v in values) else None


def _waveform_proof(recording, left, right, span):
    import numpy as np

    rate = recording['source']['sample_rate']
    step = max(1, rate // FRAME_HZ)
    sums = np.zeros(3, dtype=np.float64)
    worst = 0.
    # Read at most one second, aligned to the local comparison frames.
    block = step * FRAME_HZ
    for start in range(span.start, span.end, block):
        region = SampleSpan(start, min(start+block, span.end))
        a = np.asarray(read_channel(recording, region, left), dtype=np.float64)
        b = np.asarray(read_channel(recording, region, right), dtype=np.float64)
        if not np.isfinite(a).all() or not np.isfinite(b).all():
            raise ValueError('Nonfinite channel comparison')
        for offset in range(0, len(a), step):
            x, y = a[offset:offset+step], b[offset:offset+step]
            energy = np.array([np.dot(x, x), np.dot(y, y), np.dot(x-y, x-y)])
            reference = min(energy[:2])
            ratio = math.sqrt(energy[2]/reference) if reference else (0. if energy[2] == 0 else math.inf)
            if ratio > MAX_FRAME_RELATIVE_RMS:
                return None
            worst = max(worst, ratio)
            sums += energy
    reference = min(sums[:2])
    if not reference:
        return None  # Silence supplies no duplicate speech evidence.
    relative = math.sqrt(sums[2]/reference)
    if relative > MAX_RELATIVE_RMS:
        return None
    return {'channels': [left, right], 'span': vars(span),
            'relative_rms': relative, 'max_frame_relative_rms': worst}


def unreconciled_spans(evidence, channels, span):
    """Subtract only waveform-proven cross-channel coincidence; keep all other vetoes."""
    pair = sorted(channels)
    remaining = [dict(span)]
    groups = (evidence.get('channel_reconciliation', {}).get('groups', [])
              + evidence.get('phrase_channel_reconciliation', {}).get('groups', []))
    for group in groups:
        for proof in group['proofs'] + group.get('envelope_proofs', []):
            if proof['channels'] != pair:
                continue
            a, b = proof['span']['start'], proof['span']['end']
            pieces = []
            for part in remaining:
                if b <= part['start'] or a >= part['end']:
                    pieces.append(part)
                else:
                    if part['start'] < a:
                        pieces.append({'start': part['start'], 'end': a})
                    if b < part['end']:
                        pieces.append({'start': b, 'end': part['end']})
            remaining = pieces
    return remaining


def _matching_occurrence(first, other, units):
    from wsl2_audio.recording_engine import _surface_key
    from wsl2_audio.recognition import complete_word_span

    if _surface_key(first) != _surface_key(other):
        return False
    a, b = first['span'], other['span']
    aligned = [complete_word_span(u['text'], u['words']) for u in (first, other)]
    left, right = aligned if all(aligned) else (a, b)
    overlap = min(left['end'], right['end'])-max(left['start'], right['start'])
    if overlap*5 < max(left['end']-left['start'], right['end']-right['start'])*4:
        return False
    # A repeated matching phrase may not be arbitrarily paired across channels.
    for anchor, candidate in ((first,other),(other,first)):
        if any(u['id'] != candidate['id'] and u['channel'] == candidate['channel']
               and _surface_key(u) == _surface_key(anchor)
               and u['span']['start'] < anchor['span']['end'] and anchor['span']['start'] < u['span']['end']
               for u in units):
            return False
    return True


def reconcile_channels(evidence, recording):
    from wsl2_audio.recording_engine import _surface_key

    result = deepcopy(evidence)
    units = result['utterances']
    groups, consumed = [], set()
    for index, first in enumerate(units):
        if index in consumed or first.get('resolution') == 'conflicting_hypotheses':
            continue
        members, proofs = [first], []
        for j in range(index+1, len(units)):
            other = units[j]
            if j in consumed or other.get('resolution') == 'conflicting_hypotheses':
                continue
            if other['channel'] in {u['channel'] for u in members} or _surface_key(first) != _surface_key(other):
                continue
            if not _matching_occurrence(first, other, units):
                continue
            b = other['span']
            proposed = []
            for member in members:
                channels = sorted([member['channel'], other['channel']])
                span = SampleSpan(min(member['span']['start'], b['start']), max(member['span']['end'], b['end']))
                proof = _waveform_proof(recording, *channels, span)
                if proof is None:
                    break
                proposed.append(proof)
            if len(proposed) == len(members):
                members.append(other)
                proofs.extend(proposed)
                consumed.add(j)
        if len(members) > 1:
            members = sorted(members, key=lambda u: u['channel'])
            groups.append({'representative_id': members[0]['id'], 'members': deepcopy(members), 'proofs': proofs})
            # A deterministic channel, never the best score, owns the occurrence.
            representative = deepcopy(members[0])
            representative['source_channels'] = [u['channel'] for u in members]
            representative['observation_ids'] = sorted({key for u in members for key in u['observation_ids']})
            # Retain the union: reconciliation cannot shorten an uncertain edge.
            representative['span'] = {'start': min(u['span']['start'] for u in members),
                                      'end': max(u['span']['end'] for u in members)}
            representative['channel_reconciliation_id'] = representative['id']
            representative['quality']['avg_logprob'] = _confidence(members, 'avg_logprob', min)
            representative['quality']['no_speech_probability'] = _confidence(members, 'no_speech_probability', max)
            representative['quality']['speech_coverage'] = recognition_coverage(representative, result)
            units[index] = representative
    result['utterances'] = sorted([u for index, u in enumerate(units) if index not in consumed],
                                 key=lambda u: (u['span']['start'], u['span']['end'], u['channel'], u['id']))
    if not groups:
        return result
    result['channel_reconciliation'] = {'method': METHOD, 'source_sha256': result['source']['sha256'],
        'pcm_sha256': result['source']['pcm_sha256'], 'groups': groups}
    overlap = []
    for row in result['overlap']:
        if row.get('reason') == 'simultaneous_channel_observations' and 'channels' in row:
            overlap.extend(dict(row, span=span) for span in unreconciled_spans(result, row['channels'], row['span']))
        else:
            overlap.append(row)
    result['overlap'] = overlap
    return result


def _phrase_representative(members, evidence):
    representative = deepcopy(members[0])
    representative['source_channels'] = [u['channel'] for u in members]
    representative['observation_ids'] = sorted({key for u in members for key in u['observation_ids']})
    representative['span'] = {'start':min(u['span']['start'] for u in members),
                              'end':max(u['span']['end'] for u in members)}
    representative['phrase_channel_reconciliation_id'] = representative['id']
    representative['quality']['avg_logprob'] = _confidence(members, 'avg_logprob', min)
    representative['quality']['no_speech_probability'] = _confidence(members, 'no_speech_probability', max)
    representative['quality']['speech_coverage'] = recognition_coverage(representative, evidence)
    return representative


def reconcile_phrase_channels(evidence, recording):
    """Revisit resolved phrases using the same strict, whole-span PCM proof.

    A failed native-block comparison cannot veto a later independent phrase.
    Keep every pre-merge child so partition/envelope validation remains lossless.
    """
    if 'phrase_channel_reconciliation' in evidence:
        raise ValueError('Phrase channel reconciliation must run once')
    candidates = [u for u in evidence['utterances'] if u.get('phrase_source')
                  and not u.get('source_channels')]
    if len({u['channel'] for u in candidates}) < 2:
        return evidence
    probe = dict(evidence, utterances=deepcopy(candidates), overlap=[])
    probe.pop('channel_reconciliation', None)
    compared = reconcile_channels(probe, recording)
    record = compared.get('channel_reconciliation')
    if not record:
        return evidence
    result = deepcopy(evidence)
    record = deepcopy(record)
    record['method'] = PHRASE_METHOD
    result['phrase_channel_reconciliation'] = record
    replacements, consumed = {}, set()
    for group in record['groups']:
        replacements[group['representative_id']] = _phrase_representative(group['members'], result)
        consumed.update(u['id'] for u in group['members'][1:])
    result['utterances'] = sorted(
        [replacements.get(u['id'], u) for u in result['utterances'] if u['id'] not in consumed],
        key=lambda u:(u['span']['start'],u['span']['end'],u['channel'],u['id']))
    overlap = []
    for row in result['overlap']:
        if row.get('reason') == 'simultaneous_channel_observations' and 'channels' in row:
            overlap.extend(dict(row, span=part) for part in unreconciled_spans(result, row['channels'], row['span']))
        else:
            overlap.append(row)
    # Replay the earlier envelope decisions with their original overlap evidence.
    record['original_overlap'] = deepcopy(evidence['overlap'])
    result['overlap'] = overlap
    return result


def expand_phrase_channels(evidence):
    """Restore pre-merge units for the original partition/envelope validators."""
    record = evidence.get('phrase_channel_reconciliation')
    if not record:
        return evidence
    result = deepcopy(evidence)
    groups = {g['representative_id']:g['members'] for g in record['groups']}
    result['utterances'] = sorted(
        [deepcopy(member) for u in evidence['utterances']
         for member in groups.get(u.get('phrase_channel_reconciliation_id'), [u])],
        key=lambda u:(u['span']['start'],u['span']['end'],u['channel'],u['id']))
    result['overlap'] = deepcopy(record['original_overlap'])
    result.pop('phrase_channel_reconciliation')
    if result.get('enrichment_observations'):
        from wsl2_audio.enrichment import observation_overlap
        result['overlap'] = observation_overlap(result, result['enrichment_observations'])
    return result


def _validate_phrase_channels(evidence):
    from wsl2_audio.recording_engine import _surface_key, resolve_observations
    from wsl2_audio.source_clock import SourceClock

    record = evidence.get('phrase_channel_reconciliation')
    marked = [u for u in evidence['utterances'] if 'phrase_channel_reconciliation_id' in u]
    if not record:
        if marked:
            raise ValueError('Phrase channel provenance missing')
        return
    source = evidence['source']
    if (record.get('method') != PHRASE_METHOD or record.get('source_sha256') != source['sha256']
            or record.get('pcm_sha256') != source['pcm_sha256']):
        raise ValueError('Phrase channel source or method mismatch')
    clock = SourceClock(source['sample_rate'], source['sample_count'], source['origin_num'], source['origin_den'])
    native_overlap = resolve_observations(evidence['window_observations'], clock)['overlap']
    prior = deepcopy(evidence)
    prior.pop('phrase_channel_reconciliation')
    for group in prior.get('channel_reconciliation', {}).get('groups', []):
        group.pop('envelope_proofs', None)
    expected_overlap = []
    for row in native_overlap:
        if row.get('reason') == 'simultaneous_channel_observations' and 'channels' in row:
            expected_overlap.extend(dict(row, span=part) for part in unreconciled_spans(prior, row['channels'], row['span']))
        else:
            expected_overlap.append(row)
    if record.get('original_overlap') != expected_overlap:
        raise ValueError('Phrase reconciliation changed original overlap evidence')
    originals = [u for u in expand_phrase_channels(evidence)['utterances']
                 if u.get('phrase_source') and not u.get('source_channels')]
    groups, claimed = {}, set()
    for group in record['groups']:
        members = group['members']
        channels = [u['channel'] for u in members]
        if (len(channels) < 2 or channels != sorted(set(channels))
                or group['representative_id'] != members[0]['id']
                or any(not u.get('phrase_source') or u.get('source_channels')
                       or _surface_key(u) != _surface_key(members[0]) for u in members)):
            raise ValueError('Invalid phrase channel members')
        ids = {u['id'] for u in members}
        if len(ids) != len(members) or claimed.intersection(ids):
            raise ValueError('Repeated phrase channel member')
        if any(not _matching_occurrence(members[0], other, originals) for other in members[1:]):
            raise ValueError('Phrase reconciliation has no unique matching occurrence')
        claimed.update(ids)
        pairs = {(a,b) for i,a in enumerate(channels) for b in channels[i+1:]}
        if len(group['proofs']) != len(pairs) or {tuple(p['channels']) for p in group['proofs']} != pairs:
            raise ValueError('Incomplete phrase waveform proof')
        if group.get('envelope_proofs'):
            raise ValueError('Phrase proof must cover its final envelope')
        for proof in group['proofs']:
            clock.require_span(SampleSpan(**proof['span']))
            pair = [u for u in members if u['channel'] in proof['channels']]
            if proof['span'] != {'start':min(u['span']['start'] for u in pair),
                                  'end':max(u['span']['end'] for u in pair)}:
                raise ValueError('Phrase waveform span mismatch')
            for key, maximum in (('relative_rms',MAX_RELATIVE_RMS), ('max_frame_relative_rms',MAX_FRAME_RELATIVE_RMS)):
                value = proof.get(key)
                if type(value) not in (int,float) or not math.isfinite(value) or not 0 <= value <= maximum:
                    raise ValueError('Phrase waveform disagreement')
        groups[group['representative_id']] = group
    if {u['phrase_channel_reconciliation_id'] for u in marked} != set(groups) or len(marked) != len(groups):
        raise ValueError('Phrase reconciliation lost its representative')
    for unit in marked:
        expected = _phrase_representative(groups[unit['phrase_channel_reconciliation_id']]['members'], evidence)
        keys = ('id','text','words','span','quality','channel','source_channels','observation_ids','language',
                'phrase_source','envelope_source','native_span','alignment_source','phrase_channel_reconciliation_id')
        if any(unit.get(key) != expected.get(key) for key in keys):
            raise ValueError('Phrase reconciliation changed retained evidence')


def extend_reconciliation_proofs(evidence, recording):
    """An independently extended phrase needs PCM proof on its new samples too."""
    for group in evidence.get('channel_reconciliation', {}).get('groups', []):
        units = [u for u in evidence['utterances'] if u.get('channel_reconciliation_id') == group['representative_id']]
        spans = [u['span'] for u in units + group['members']]
        outer = SampleSpan(min(p['start'] for p in spans), max(p['end'] for p in spans))
        proofs = []
        for original in group['proofs']:
            if original['span'] == vars(outer):
                continue
            proof = _waveform_proof(recording, *original['channels'], outer)
            if proof is not None:
                proofs.append(proof)
        if proofs:
            group['envelope_proofs'] = proofs
    return evidence


def validate_reconciliation(evidence):
    """Validate provenance and deterministic ownership; PCM truth is checked at creation."""
    from wsl2_audio.recording_engine import resolve_observations, _surface_key
    from wsl2_audio.source_clock import SourceClock
    from wsl2_audio.recognition import complete_word_span

    _validate_phrase_channels(evidence)
    evidence = expand_phrase_channels(evidence)

    record = evidence.get('channel_reconciliation')
    parents = [r['native'] for r in evidence.get('phrase_resolution', {}).get('parents', [])]
    marked = [u for u in evidence['utterances'] + parents if 'source_channels' in u or 'channel_reconciliation_id' in u]
    if record is None:
        if marked:
            raise ValueError('Channel reconciliation provenance missing')
        return
    source = evidence['source']
    if record.get('method') != METHOD:
        raise ValueError('Invalid channel reconciliation identity')
    if record.get('source_sha256') != source['sha256'] or record.get('pcm_sha256') != source['pcm_sha256']:
        raise ValueError('Channel reconciliation source mismatch')
    clock = SourceClock(source['sample_rate'], source['sample_count'], source['origin_num'], source['origin_den'])
    originals = {u['id']: u for u in resolve_observations(evidence['window_observations'], clock)['utterances']}
    records = {}
    for group in record['groups']:
        members = group['members']
        channels = [u['channel'] for u in members]
        if len(channels) < 2 or channels != sorted(set(channels)) or group['representative_id'] != members[0]['id']:
            raise ValueError('Invalid channel reconciliation members')
        if any(originals.get(u['id']) != u or _surface_key(u) != _surface_key(members[0]) for u in members):
            raise ValueError('Channel reconciliation changed original observations')
        for member in members:
            if member.get('alignment_source') and (member['alignment_source'] != {
                    'method':'complete_aligned_text_v1', 'reason':'native_envelope_outside_input'}
                    or complete_word_span(member['text'], member['words']) != member['span']):
                raise ValueError('Channel member lost its recovered alignment')
        expected_pairs = {(a, b) for i, a in enumerate(channels) for b in channels[i+1:]}
        if {tuple(p['channels']) for p in group['proofs']} != expected_pairs or len(group['proofs']) != len(expected_pairs):
            raise ValueError('Incomplete channel waveform evidence')
        extended_pairs = [tuple(p['channels']) for p in group.get('envelope_proofs', [])]
        if len(set(extended_pairs)) != len(extended_pairs) or not set(extended_pairs) <= expected_pairs:
            raise ValueError('Invalid channel envelope comparison')
        for proof in group['proofs'] + group.get('envelope_proofs', []):
            clock.require_span(SampleSpan(**proof['span']))
            pair = [u for u in members if u['channel'] in proof['channels']]
            if proof in group.get('envelope_proofs', []):
                pair = members + [u for u in evidence['utterances']
                    if u.get('channel_reconciliation_id') == group['representative_id']]
            if proof['span'] != {'start':min(u['span']['start'] for u in pair), 'end':max(u['span']['end'] for u in pair)}:
                raise ValueError('Channel waveform span mismatch')
            for key, maximum in [('relative_rms', MAX_RELATIVE_RMS), ('max_frame_relative_rms', MAX_FRAME_RELATIVE_RMS)]:
                value = proof.get(key)
                if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
                    raise ValueError('Channel waveform disagreement')
        records[group['representative_id']] = group
    if {u.get('channel_reconciliation_id') for u in marked} != set(records):
        raise ValueError('Channel reconciliation lost its representative')
    for unit in marked:
        group = records.get(unit.get('channel_reconciliation_id'))
        if group is None:
            raise ValueError('Unknown channel reconciliation group')
        if unit['source_channels'] != [u['channel'] for u in group['members']] or unit['channel'] != unit['source_channels'][0]:
            raise ValueError('Channel reconciliation ownership changed')
        if unit['observation_ids'] != sorted({key for u in group['members'] for key in u['observation_ids']}):
            raise ValueError('Channel reconciliation lost observations')
        for key, combine in [('avg_logprob', min), ('no_speech_probability', max)]:
            if unit['quality'][key] != _confidence(group['members'], key, combine):
                raise ValueError('Channel reconciliation changed conservative confidence')
        if unit['quality']['speech_coverage'] != recognition_coverage(unit, evidence):
            raise ValueError('Channel reconciliation support differs from its source span')
        if not unit.get('phrase_source'):
            expected = group['members'][0]
            original_span = unit.get('envelope_source', {}).get('original_span', unit['span'])
            union = {'start':min(u['span']['start'] for u in group['members']),
                     'end':max(u['span']['end'] for u in group['members'])}
            if original_span != union or any(unit.get(k) != expected.get(k) for k in ('text', 'words', 'id')):
                raise ValueError('Channel reconciliation altered retained text or timing')
