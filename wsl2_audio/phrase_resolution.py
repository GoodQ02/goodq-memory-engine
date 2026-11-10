"""Partition decoder blocks at independently observed pauses; never rewrite words."""

from copy import deepcopy
import hashlib

from wsl2_audio.eligibility import stage_covers
from wsl2_audio.evidence_contract import _span
from wsl2_audio.recording_audio import _json_bytes
from wsl2_audio.source_clock import SourceClock
from wsl2_audio.recognition import complete_word_span
from wsl2_audio.channel_reconciliation import recognition_coverage


METHOD = 'punctuation_and_unpadded_pause_v1'
COALESCED_METHOD = 'coalesced_punctuation_and_unpadded_pause_v2'
ENVELOPE_METHOD = 'word_disagreement_and_independent_activity_v1'
COMPLETE_ENVELOPE_METHOD = 'complete_alignment_and_independent_activity_v2'
PHRASE_EDGE_METHOD = 'complete_phrase_outer_activity_v3'
ACTIVITY_EDGE_METHOD = 'complete_phrase_activity_edges_v4'
ALIGNED_EDGE_METHOD = 'complete_aligned_phrase_activity_edges_v5'


def _groups(parent, *, short_endings=False):
    """Require exact decoder-text coverage, including words without timestamps."""
    text, words = parent['text'], parent['words']
    groups, start, offset, text_start = [], 0, 0, 0
    for index, word in enumerate(words):
        while offset < len(text) and text[offset].isspace():
            offset += 1
        if index == start:
            text_start = offset
        if not text.startswith(word['text'], offset):
            return []
        offset += len(word['text'])
        token = word['text'].rstrip('\"\'\u2019\u201d')
        # An abbreviation or decimal is not a sentence-ending proposal.
        terminal = token.endswith(('?', '!')) or (token.endswith('.') and token.count('.') == 1
            and len(token[:-1]) > (1 if short_endings else 2) and token[:-1].isalpha()
            and token[:-1].lower() not in ({'mrs', 'prof', 'rev', 'hon', 'gen', 'etc'}
                | ({'mr', 'ms', 'dr', 'st', 'sr', 'jr', 'vs'} if short_endings else set())))
        if terminal or index == len(words)-1:
            groups.append((start, index+1, text[text_start:offset]))
            start = index+1
    return groups if not text[offset:].strip() else []


def _proposal(parent, activity, evidence, *, method=METHOD):
    source = evidence['source']
    clock = SourceClock(source['sample_rate'], source['sample_count'], source['origin_num'], source['origin_den'])
    span, channel = _span(parent['span'], clock), parent.get('channel', 0)
    check = dict(evidence, stages=dict(evidence['stages'], phrase_activity=activity))
    if (parent.get('resolution') == 'conflicting_hypotheses' or parent.get('kind', 'speech') != 'speech'
            or not stage_covers(check, 'phrase_activity', span, clock, channel)):
        return None
    coalesce = method == COALESCED_METHOD
    groups = _groups(parent, short_endings=coalesce)
    if len(groups) < 2:
        return None
    words = parent['words']
    anchors = [[w['span'] for w in words[a:b] if w.get('timing') == 'supported'] for a, b, _ in groups]
    if not coalesce and not all(anchors):
        return None
    regions = sorted((r['span'] for r in activity.get('regions', []) if r.get('channel') == channel),
                     key=lambda r: (r['start'], r['end']))
    if any(a['end'] > b['start'] for a, b in zip(regions, regions[1:])):
        return None
    seams, boundaries = [], []
    for index, (left, right) in enumerate(zip(anchors, anchors[1:])):
        if coalesce:
            # A missing local anchor cannot locate this boundary. Keep its text
            # with its neighbor, but do not discard independently located later seams.
            if not left or not right:
                continue
            left = [part for group in anchors[:index+1] for part in group]
            right = [part for group in anchors[index+1:] for part in group]
        candidates = []
        for before, after in zip(regions, regions[1:]):
            low, high = max(max(w['end'] for w in left), before['end']), min(min(w['start'] for w in right), after['start'])
            hit = lambda region, parts: any(w['start'] < region['end'] and region['start'] < w['end'] for w in parts)
            if span.start < low < high < span.end and hit(before, left) and hit(after, right):
                candidates.append({'sample': (low+high)//2, 'gap': {'start': low, 'end': high},
                                   'before_activity': deepcopy(before), 'after_activity': deepcopy(after)})
        if len(candidates) != 1:
            if coalesce:
                continue
            return None
        seams.append(candidates[0])
        boundaries.append(index+1)
    if coalesce:
        if not seams:
            return None
        # Recover exact source substrings, including whitespace inside merged groups.
        offsets, cursor = [], 0
        for _, _, text in groups:
            start = parent['text'].index(text, cursor)
            cursor = start + len(text)
            offsets.append((start, cursor))
        limits = [0] + boundaries + [len(groups)]
        groups = [(groups[a][0], groups[b-1][1], parent['text'][offsets[a][0]:offsets[b-1][1]])
                  for a, b in zip(limits, limits[1:])]
    cuts = [span.start] + [r['sample'] for r in seams] + [span.end]
    if cuts != sorted(set(cuts)):
        return None
    return groups, seams, cuts


def _children(parent, proposal, evidence, *, method=METHOD):
    groups, seams, cuts = proposal
    # Recompute child coverage from the existing recognition-support observations.
    # Decoder confidence remains explicitly native-block-level evidence.
    children = []
    for index, ((first, last, text), start, end) in enumerate(zip(groups, cuts, cuts[1:])):
        child = deepcopy(parent)
        child['words'] = deepcopy(parent['words'][first:last])
        # Keep decoder spelling/punctuation; whitespace between phrases belongs
        # to the retained native text, not to a new recognition hypothesis.
        child['text'] = text
        child['span'] = {'start': start, 'end': end}
        child['phrase_source'] = {'parent_id': parent['id'], 'word_range': [first, last], 'method': method,
                                  'left_seam': index-1 if index else None,
                                  'right_seam': index if index < len(seams) else None}
        child['id'] = 'phrase-'+hashlib.sha256(_json_bytes([parent['id'], child['phrase_source'], child['span']])).hexdigest()
        child['quality']['speech_coverage'] = recognition_coverage(child, evidence)
        child['quality']['decoder_confidence_scope'] = 'parent_native_block'
        children.append(child)
    return children


def _envelope_plans(units, observations, evidence, *, complete_alignment=False, phrase_edges=False,
                    internal_edges=False, aligned_edges=False):
    """Reconcile a contradicted native edge once; never add a fixed time allowance."""
    source = evidence['source']
    clock = SourceClock(source['sample_rate'], source['sample_count'], source['origin_num'], source['origin_den'])
    check = dict(evidence, stages=dict(evidence['stages'], **observations))
    plans = {}
    for u in units:
        child = u.get('phrase_source')
        if ((child and not phrase_edges) or u.get('kind', 'speech') != 'speech'
                or u.get('resolution') == 'conflicting_hypotheses'):
            continue
        span = _span(u['span'], clock)
        native = _span(u['native_span'], clock) if u.get('native_span') else None
        words = [_span(w['span'], clock) for w in u['words'] if w.get('timing') == 'supported']
        extension = native and any(w.start < native.start or w.end > native.end for w in words)
        aligned = complete_word_span(u['text'], u['words']) if complete_alignment and not extension else None
        if aligned and u.get('channel_reconciliation_id') and not child:
            group = next(g for g in evidence['channel_reconciliation']['groups']
                         if g['representative_id'] == u['channel_reconciliation_id'])
            anchors = [complete_word_span(member['text'], member['words']) for member in group['members']]
            aligned = ({'start': min(p['start'] for p in anchors), 'end': max(p['end'] for p in anchors)}
                       if all(anchors) else None)
        if child:
            # Legacy internal seams stay fixed. Every version requires complete
            # word alignment before changing a child's envelope. Only v5 may
            # refine outer edges, retaining complete independent activity.
            if complete_word_span(u['text'], u['words']) is None:
                continue
            extension, aligned = True, None
        if not extension and not aligned:
            continue
        channel = u.get('channel', 0)
        source_channels = u.get('source_channels', [channel])
        supports = [[_span(r['span'], clock) for r in observations.get(stage, {}).get(field, [])
                     if r.get('channel') in source_channels and span.overlaps(_span(r['span'], clock))]
                    for stage, field in (('phrase_activity', 'regions'), ('speaker_activity', 'tracks'))]
        if not all(supports):
            continue
        activity = supports[0] + supports[1]
        if any(p.start == 0 or p.end == clock.sample_count for p in activity):
            continue
        base = _span(aligned, clock) if aligned else span
        proposed = {'start': min([base.start] + [p.start for p in activity]),
                    'end': max([base.end] + [p.end for p in activity])}
        if child:
            if child.get('left_seam') is not None:
                proposed['start'] = span.start
            if child.get('right_seam') is not None:
                proposed['end'] = span.end
            if internal_edges:
                proposed = _activity_edges(u, proposed, observations, evidence, clock, outer_edges=aligned_edges)
        if aligned:
            # Tighten coarse empty margins, or complete a recovered alignment.
            # Never crop away contamination to manufacture a clean voice sample.
            if not u.get('alignment_source') and not (span.start <= proposed['start'] < proposed['end'] <= span.end):
                continue
            vetoes = (evidence.get('overlap', []) + observations.get('overlap', {}).get('intervals', [])
                      + observations.get('speaker_activity', {}).get('flags', [])
                      + observations.get('acoustic_events', {}).get('events', []))
            channels = u.get('source_channels', [channel])
            if (any(r.get('channel', channel) in channels and span.overlaps(_span(r['span'], clock)) for r in vetoes)
                    or any(len({r['speaker'] for r in observations.get('speaker_activity', {}).get('tracks', [])
                                if r.get('channel') == selected and span.overlaps(_span(r['span'], clock))}) != 1
                           for selected in channels)):
                continue
        proposed_span = _span(proposed, clock)
        if proposed == u['span'] or any(v['id'] != u['id'] and v.get('channel', 0) == channel
                and proposed_span.overlaps(_span(v['span'], clock)) for v in units):
            continue
        contexts = [w['context'] for w in evidence.get('window_observations', [])
                    if w.get('channel') == channel and 'context' in w
                    and any(identifier.startswith(w.get('window_id', '')+':') for identifier in u.get('observation_ids', []))]
        if not any(p['start'] <= proposed['start'] < proposed['end'] <= p['end'] for p in contexts):
            continue
        if all(stage_covers(check, name, proposed_span, clock, channel)
               for name in ('phrase_activity', 'speaker_activity')):
            plans[u['id']] = proposed
    # Two independently proposed extensions must not create a new collision.
    return {key: value for key, value in plans.items() if not any(other != key
        and next(u.get('channel', 0) for u in units if u['id'] == other)
            == next(u.get('channel', 0) for u in units if u['id'] == key)
        and _span(value, clock).overlaps(_span(part, clock)) for other, part in plans.items())}


def _activity_edges(unit, proposed, observations, evidence, clock, *, outer_edges=False):
    """Refine internal silence margins, retaining every observed voice and veto.

    Outer refinement requires the versioned complete-alignment path. The result
    is independent of confidence or eligibility; no passing crop is searched for.
    """
    span = _span(unit['span'], clock)
    check = dict(evidence, stages=dict(evidence['stages'], **observations))
    if not all(stage_covers(check, name, span, clock) for name in
               ('phrase_activity', 'speaker_activity', 'overlap', 'acoustic_events')):
        return proposed
    activity = [r['span'] for name, field in (('phrase_activity', 'regions'), ('speaker_activity', 'tracks'))
                for r in observations.get(name, {}).get(field, []) if span.overlaps(_span(r['span'], clock))]
    anchors = [w['span'] for w in unit['words']] + activity
    refined = dict(proposed)
    left, right = unit['phrase_source'].get('left_seam'), unit['phrase_source'].get('right_seam')
    if outer_edges or left is not None:
        start = min(p['start'] for p in anchors)
        refined['start'] = start if outer_edges and left is None else max(span.start, start)
    if outer_edges or right is not None:
        end = max(p['end'] for p in anchors)
        refined['end'] = end if outer_edges and right is None else min(span.end, end)
    target = _span(refined, clock)
    vetoes = (evidence.get('overlap', []) + observations.get('overlap', {}).get('intervals', [])
              + observations.get('speaker_activity', {}).get('flags', [])
              + observations.get('acoustic_events', {}).get('events', []))
    # Include all channels, like the gate. A recorded veto may not disappear
    # because a silence margin was refined; broad vetoes continue to apply.
    if any(span.overlaps(_span(row['span'], clock)) and not target.overlaps(_span(row['span'], clock))
           for row in vetoes):
        return proposed
    return refined


def _envelope_coverage(unit, evidence):
    return recognition_coverage(unit, evidence)


def resolve_phrases(evidence: dict, observations: dict) -> dict:
    """Retain native evidence; coalesce text across unsupported boundaries."""
    result = deepcopy(evidence)
    if 'phrase_resolution' in result:
        raise ValueError('Phrase resolution must run once on native recording evidence')
    result['phrase_resolution'] = {'method': COALESCED_METHOD, 'envelope_method': ALIGNED_EDGE_METHOD, 'parents': []}
    units = []
    for parent in evidence['utterances']:
        proposal = _proposal(parent, observations.get('phrase_activity', {}), evidence, method=COALESCED_METHOD)
        if proposal is None:
            units.append(deepcopy(parent))
            continue
        children = _children(parent, proposal, evidence, method=COALESCED_METHOD)
        result['phrase_resolution']['parents'].append({'native': deepcopy(parent), 'seams': proposal[1],
                                                       'child_ids': [u['id'] for u in children]})
        units.extend(children)
    plans = _envelope_plans(units, observations, evidence, complete_alignment=True, phrase_edges=True,
                            internal_edges=True, aligned_edges=True)
    for unit in units:
        if unit['id'] in plans:
            unit['envelope_source'] = {'method': ALIGNED_EDGE_METHOD, 'original_span': deepcopy(unit['span'])}
            unit['span'] = plans[unit['id']]
            unit['quality']['speech_coverage'] = _envelope_coverage(unit, evidence)
    result['utterances'] = units
    return result


def validate_phrase_resolution(evidence):
    """Stored children must be the lossless, reproducible partition of their parent."""
    from wsl2_audio.channel_reconciliation import expand_phrase_channels
    evidence = expand_phrase_channels(evidence)
    source = evidence['source']
    clock = SourceClock(source['sample_rate'], source['sample_count'], source['origin_num'], source['origin_den'])
    for unit in evidence['utterances']:
        if unit.get('alignment_source') and not unit.get('phrase_source') and not unit.get('channel_reconciliation_id'):
            original = unit.get('envelope_source', {}).get('original_span', unit['span'])
            if (unit['alignment_source'] != {'method': 'complete_aligned_text_v1', 'reason': 'native_envelope_outside_input'}
                    or complete_word_span(unit['text'], unit['words']) != original):
                raise ValueError('Recovered alignment lost complete text or source boundaries')
        if unit.get('native_span') and not unit.get('phrase_source') and not unit.get('channel_reconciliation_id'):
            anchors = [_span(unit['native_span'], clock)] + [_span(w['span'], clock)
                for w in unit['words'] if w.get('timing') == 'supported']
            original = {'start': min(p.start for p in anchors), 'end': max(p.end for p in anchors)}
            recorded = unit.get('envelope_source', {}).get('original_span', unit['span'])
            if recorded != original:
                raise ValueError('Envelope original differs from native and aligned word evidence')
    resolved = evidence.get('phrase_resolution')
    children = {u['id']: u for u in evidence['utterances'] if 'phrase_source' in u}
    if resolved is None:
        if children or any('envelope_source' in u for u in evidence['utterances']):
            raise ValueError('Phrase provenance missing')
        return
    method = resolved.get('method')
    if method not in (METHOD, COALESCED_METHOD):
        raise ValueError('Unknown phrase resolution method')
    envelope_method = resolved.get('envelope_method', ENVELOPE_METHOD)
    if envelope_method not in (ENVELOPE_METHOD, COMPLETE_ENVELOPE_METHOD, PHRASE_EDGE_METHOD, ACTIVITY_EDGE_METHOD, ALIGNED_EDGE_METHOD):
        raise ValueError('Unknown envelope resolution method')
    if (method == COALESCED_METHOD) != (envelope_method in (ACTIVITY_EDGE_METHOD, ALIGNED_EDGE_METHOD)):
        raise ValueError('Phrase and envelope method versions disagree')
    claimed = set()
    activity = evidence.get('enrichment_observations', {}).get('phrase_activity', {})
    for record in resolved['parents']:
        native = record['native']
        proposal = _proposal(native, activity, evidence, method=method)
        if proposal is None or record['seams'] != proposal[1]:
            raise ValueError('Phrase boundary evidence does not reproduce')
        expected = _children(native, proposal, evidence, method=method)
        if record['child_ids'] != [u['id'] for u in expected]:
            raise ValueError('Phrase child sequence changed')
        for row in expected:
            actual = children.get(row['id'])
            comparable = deepcopy(actual) if actual else None
            if comparable and 'envelope_source' in comparable:
                comparable['span'] = comparable['envelope_source']['original_span']
                # The changed envelope's coverage is independently checked below.
                comparable['quality'] = dict(comparable['quality'], speech_coverage=row['quality']['speech_coverage'])
            if row['id'] in claimed or comparable is None or any(comparable.get(k) != row.get(k)
                    for k in ('text', 'words', 'span', 'phrase_source', 'quality', 'channel', 'language',
                              'source_channels', 'channel_reconciliation_id', 'observation_ids')):
                raise ValueError('Phrase partition lost or changed source text/timing')
            claimed.add(row['id'])
    if claimed != set(children):
        raise ValueError('Phrase child has no native parent')
    original_units = deepcopy(evidence['utterances'])
    for unit in original_units:
        if 'envelope_source' in unit:
            record = unit.pop('envelope_source')
            if record.get('method') != envelope_method:
                raise ValueError('Unknown envelope resolution method')
            unit['span'] = record['original_span']
    plans = _envelope_plans(original_units, evidence.get('enrichment_observations', {}), evidence,
                            complete_alignment=envelope_method in (COMPLETE_ENVELOPE_METHOD, PHRASE_EDGE_METHOD, ACTIVITY_EDGE_METHOD, ALIGNED_EDGE_METHOD),
                            phrase_edges=envelope_method in (PHRASE_EDGE_METHOD, ACTIVITY_EDGE_METHOD, ALIGNED_EDGE_METHOD),
                            internal_edges=envelope_method in (ACTIVITY_EDGE_METHOD, ALIGNED_EDGE_METHOD),
                            aligned_edges=envelope_method == ALIGNED_EDGE_METHOD)
    for unit in evidence['utterances']:
        if 'envelope_source' in unit and (plans.get(unit['id']) != unit['span']
                or unit['quality']['speech_coverage'] != _envelope_coverage(unit, evidence)):
            raise ValueError('Envelope boundary evidence does not reproduce')
