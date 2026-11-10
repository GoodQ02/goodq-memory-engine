"""One use-specific speech decision; it never edits model observations."""

from copy import deepcopy
import math

from wsl2_audio.evidence_contract import PURITY_STAGES, _covers, _span
from wsl2_audio.source_clock import SampleSpan, SourceClock


POLICY = {
    'id': 'recording_speech_v1', 'min_speech_coverage': .8,
    'min_avg_logprob': -1.0, 'max_no_speech_probability': .6,
}
INDIVIDUAL_EXCLUSIONS = {'crying', 'laughter', 'singing', 'humming', 'babbling', 'screaming', 'cheering'}


def stage_covers(evidence, name, span, clock, channel=None):
    stage = evidence.get('stages', {}).get(name, {})
    if stage.get('status') not in ('ok', 'partial'):
        return False
    models = {model['id'] for model in evidence.get('provenance', {}).get('models', [])}
    if stage.get('model_id') not in models:
        return False
    spans = stage.get('assessed_spans')
    if channel is None and 'channel_assessed_spans' in stage:
        return all(stage_covers(evidence, name, span, clock, selected)
                   for selected in range(evidence['source'].get('channels', 1)))
    if channel is not None and 'channel_assessed_spans' in stage:
        spans = stage['channel_assessed_spans'].get(str(channel), [])
    if spans is None and stage['status'] == 'ok':
        spans = [{'start': 0, 'end': clock.sample_count}]
    return _covers([_span(value, clock) for value in spans or []], span)


def assess_eligibility(utterance: dict, evidence: dict, policy: dict) -> dict:
    """Decide input eligibility, not model accuracy, emotion or named identity.

Missing word alignment alone is irrelevant to this decision. Boundary/purity
observations must support the whole phrase; no shorter surviving crop is scored.
"""
    if policy != POLICY:
        raise ValueError('Unsupported or modified eligibility policy')
    source = evidence['source']
    clock = SourceClock(source['sample_rate'], source['sample_count'], source['origin_num'], source['origin_den'])
    span = _span(utterance['span'], clock)
    text_reasons, individual_reasons, vetoes = [], [], []
    channel = utterance.get('channel')
    source_coverage = evidence.get('channel_coverage', {}).get(str(channel), evidence.get('coverage', []))
    records = [(row, _span(row['span'], clock)) for row in source_coverage]
    analyzed = [part for row, part in records if row['status'] == 'analyzed']
    accounted = [part for row, part in records if row['status'] in ('analyzed', 'digital_silence')]
    all_silent = (_covers([part for row, part in records if row['status'] == 'digital_silence'], span))
    if all_silent:
        return {purpose: {'status': 'ineligible', 'reasons': ['digital_silence']}
                for purpose in ('transcript', 'vocal_delivery', 'voice_sample')}
    if not _covers(accounted, span) or not any(span.overlaps(part) for part in analyzed):
        text_reasons.append('source_not_fully_assessed')
    if not stage_covers(evidence, 'recognition', span, clock, channel):
        text_reasons.append('recognition_not_assessed')
    if not stage_covers(evidence, 'speech_activity', span, clock, channel):
        text_reasons.append('speech_activity_not_assessed')
    if utterance.get('resolution') == 'conflicting_hypotheses':
        text_reasons.append('conflicting_hypotheses')
    quality = utterance.get('quality', {})
    checks = (
        ('avg_logprob', lambda x: policy['min_avg_logprob'] <= x <= 0),
        ('no_speech_probability', lambda x: 0 <= x <= policy['max_no_speech_probability']),
        ('speech_coverage', lambda x: policy['min_speech_coverage'] <= x <= 1),
    )
    for name, supported in checks:
        value = quality.get(name)
        if type(value) not in (int, float) or not math.isfinite(value) or not supported(value):
            text_reasons.append(name + '_unsupported')
    for row in evidence.get('overlap', []):
        if span.overlaps(_span(row['span'], clock)):
            vetoes.append('overlap_' + row['status'])
    for event in evidence.get('sound_events', []):
        if event['label'] in INDIVIDUAL_EXCLUSIONS and span.overlaps(_span(event['span'], clock)):
            # A coarse window is a conservative exclusion, not a claim that
            # this exact phrase contains the event. A negative crop cannot
            # override it while localization and recall remain unqualified.
            context = (event.get('scope') == 'recording_window'
                       and event.get('boundary_precision') == 'analysis_window'
                       and (event['span']['start'] < span.start or event['span']['end'] > span.end))
            vetoes.append('sound_event_context_' + event['label'] + '_unresolved' if context
                          else 'sound_event_' + event['label'])
    if utterance.get('kind', 'speech') != 'speech':
        vetoes.append('non_individual_speech')
    all_channels_assessed = [_span(row['span'], clock) for row in evidence.get('coverage', [])
                            if row['status'] in ('analyzed', 'digital_silence')]
    if not _covers(all_channels_assessed, span):
        individual_reasons.append('other_channel_not_assessed')
    speaker = utterance.get('speaker', {})
    if speaker.get('status') == 'mixed':
        vetoes.append('mixed_speakers')
    if speaker.get('status') != 'single' or speaker.get('purity') != 'supported_single':
        individual_reasons.append('single_voice_unresolved')
    boundary = utterance.get('boundary_evidence', {})
    if (utterance.get('completeness') != 'complete' or boundary.get('status') != 'supported'
            or not isinstance(boundary.get('method'), str) or not boundary['method'].strip()):
        individual_reasons.append('complete_phrase_unresolved')
    for name in PURITY_STAGES:
        if not stage_covers(evidence, name, span, clock):
            individual_reasons.append(name + '_not_assessed')
    reasons = sorted(set(text_reasons + individual_reasons + vetoes))
    individual = {'status': 'ineligible' if vetoes else 'unresolved' if reasons else 'eligible', 'reasons': reasons}
    return {
        'transcript': {'status': 'unresolved' if text_reasons else 'eligible', 'reasons': sorted(set(text_reasons))},
        'vocal_delivery': deepcopy(individual), 'voice_sample': deepcopy(individual),
    }


def select_inputs(evidence: dict, purpose: str) -> list[dict]:
    """Both individual consumers read the same validated, complete source spans."""
    from wsl2_audio.evidence_contract import validate_evidence

    if purpose not in ('transcript', 'vocal_delivery', 'voice_sample'):
        raise ValueError('Unknown audio evidence purpose')
    if evidence.get('eligibility_policy') != POLICY:
        raise ValueError('Missing shared eligibility policy')
    snapshot = validate_evidence(evidence)
    return [utterance for utterance in snapshot['utterances'] if utterance['eligibility'][purpose]['status'] == 'eligible']
