"""Source-bound sound events and positive speech support from one frame-level pass."""

import hashlib

from wsl2_audio.acoustic_events import NON_SPEECH_LABELS
from wsl2_audio.recording_audio import _json_bytes
from wsl2_audio.source_clock import SampleSpan


METHOD = 'efficientsed_frames_v1'
METHOD_V2 = 'efficientsed_frames_v2'
THRESHOLD = .5
ANALYSIS_POLICY = {'id': METHOD, 'threshold': THRESHOLD, 'context_seconds': 5,
                   'hop_seconds': 2.5, 'model_input_seconds': 10, 'frame_rate_hz': 25,
                   'smoothing': 'none'}
ANALYSIS_POLICY_V2 = {'id': METHOD_V2, 'threshold': THRESHOLD, 'context_seconds': 5,
                      'hop_seconds': 2.5, 'model_input_seconds': 10, 'frame_rate_hz': 25,
                      'smoothing': 'none', 'window_aggregation': 'all_covering_windows'}
SUPPORTED_POLICIES = {METHOD: ANALYSIS_POLICY, METHOD_V2: ANALYSIS_POLICY_V2}
EVENT_LABELS = dict(NON_SPEECH_LABELS, **{'Male singing': 'singing', 'Female singing': 'singing',
                                       'Cheering': 'cheering'})
SPEECH_LABELS = ('Speech', 'Male speech, man speaking', 'Female speech, woman speaking',
                 'Child speech, kid speaking', 'Conversation', 'Narration, monologue')


def windows(count, rate):
    if type(count) is not int or type(rate) is not int or count <= 0 or rate <= 0:
        raise ValueError('Invalid acoustic source geometry')
    index, start = 0, 0
    while True:
        end = min(count, start+5*rate)
        yield SampleSpan(start, end)
        if end == count:
            break
        index += 1
        start = index*5*rate//2


def valid_frames(span, rate):
    """250 frames per ten seconds; round from the origin and discard padded time."""
    if rate <= 0 or span.end-span.start > 10*rate:
        raise ValueError('Invalid frame-model geometry')
    return [SampleSpan(span.start+i*rate//25, min(span.end, span.start+((i+1)*rate+24)//25))
            for i in range(250) if span.start+i*rate//25 < span.end]


def _union(spans):
    result = []
    for span in sorted(spans, key=lambda r: (r['start'], r['end'])):
        if result and span['start'] <= result[-1]['end']:
            result[-1]['end'] = max(result[-1]['end'], span['end'])
        else:
            result.append(dict(span))
    return result


def _runs(values, frames):
    import numpy as np
    return [{'start': frames[a].start, 'end': frames[b-1].end}
            for a, b in np.flatnonzero(np.diff(np.r_[False, values, False])).reshape(-1, 2)]


def _consensus_spans(assessed_event_windows, raw_label):
    points = set()
    per_window = []
    for w_span, w_events in assessed_event_windows:
        positives = [r['span'] for r in w_events if r['raw_label'] == raw_label]
        points.update((w_span['start'], w_span['end']))
        for pos in positives:
            points.update((pos['start'], pos['end']))
        per_window.append((w_span, positives))
    ordered = sorted(points)
    accepted = []
    for a, b in zip(ordered, ordered[1:]):
        covering = [positives for w_span, positives in per_window
                    if w_span['start'] <= a and b <= w_span['end']]
        if covering and all(any(p['start'] <= a and b <= p['end'] for p in positives)
                            for positives in covering):
            accepted.append({'start': a, 'end': b})
    return _union(accepted)


def observe_frames(session, labels, audio_for_span, rate, count, channel, source_hash, *, policy=None):
    """Read original source samples, independently of ASR and phrase boundaries."""
    import numpy as np
    from wsl2_audio.model_cache import redact_sensitive_info
    from wsl2_audio.recognition import _model_audio

    if policy is None:
        active_policy = dict(ANALYSIS_POLICY)
    else:
        method_id = policy.get('id') if isinstance(policy, dict) else None
        expected_policy = SUPPORTED_POLICIES.get(method_id)
        if expected_policy is None or policy != expected_policy:
            raise ValueError('Unsupported frame-event analysis policy')
        active_policy = dict(expected_policy)
    method = active_policy['id']
    if len(labels) != 447 or len(set(labels)) != 447 or not all(isinstance(s, str) for s in labels):
        raise ValueError('Invalid frame-event class map')
    speech_indices = [i for i, label in enumerate(labels) if label in SPEECH_LABELS]
    if not speech_indices:
        raise ValueError('Frame-event model has no ordinary-speech classes')
    retained = [i for i, label in enumerate(labels) if label in EVENT_LABELS or label in SPEECH_LABELS]
    observations, assessed, failures, positive, raw_events, assessed_event_windows = [], [], [], [], [], []
    for span in windows(count, rate):
        row = {'span': vars(span), 'channel': channel}
        window_positive, window_events = [], []
        try:
            source, audio, transform = _model_audio(audio_for_span(span), rate, span)
            expected = ((span.end-span.start)*16000+rate-1)//rate
            if (audio.ndim != 1 or len(audio) != expected or len(audio) > 160000
                    or not np.isfinite(audio).all() or np.abs(audio).max() > 1 or np.abs(source).max() > 1):
                raise ValueError('Unsupported acoustic input; no silent normalization or clipping')
            row['input_sha256'] = hashlib.sha256(audio.tobytes()).hexdigest()
            row['source_window_sha256'] = hashlib.sha256(source.tobytes()).hexdigest()
            row['transform'] = transform
            if not source.any():
                row.update(status='not_applicable', reason='digital_silence')
            elif len(audio) < 400:
                row.update(status='unavailable', reason='insufficient_samples_for_acoustic_frame')
                failures.append(dict(row))
                observations.append(row)
                continue
            else:
                padded = np.pad(audio, (0, 160000-len(audio)))
                output = session.run(['scores'], {'waveform': padded[None, :]})[0]
                if (output.shape != (1, 250, 447) or not np.isfinite(output).all()
                        or (output < 0).any() or (output > 1).any()):
                    raise ValueError('Invalid frame-event model output')
                scores = output[0]
                frames = valid_frames(span, rate)
                # Keep raw scores, but zero-valued source frames cannot establish
                # an audible event even if adjacent context influences the model.
                audible = np.array([source[frame.start-span.start:frame.end-span.start].any()
                                    for frame in frames])
                window_positive.extend(_runs((scores[:len(frames), speech_indices].max(axis=1) >= THRESHOLD) & audible, frames))
                for i, label in enumerate(labels):
                    if label not in EVENT_LABELS:
                        continue
                    for part in _runs((scores[:len(frames), i] >= THRESHOLD) & audible, frames):
                        window_events.append({'span': part, 'raw_label': label, 'label': EVENT_LABELS[label]})
                row.update(status='ok', valid_frame_count=len(frames), input_samples=len(audio),
                           padded_input_sha256=hashlib.sha256(padded.tobytes()).hexdigest(),
                           frame_scores=scores[:, retained].tolist())
            assessed.append(vars(span))
            assessed_event_windows.append((vars(span), window_events))
            positive.extend(window_positive)
            raw_events.extend(window_events)
        except Exception as exc:
            row.update(status='error', reason='acoustic_window_failed', error=redact_sensitive_info(str(exc)))
            failures.append(dict(row))
        observations.append(row)
    events = []
    for label in sorted({r['raw_label'] for r in raw_events}):
        spans = (_consensus_spans(assessed_event_windows, label)
                 if active_policy.get('window_aggregation') == 'all_covering_windows'
                 else _union([r['span'] for r in raw_events if r['raw_label'] == label]))
        for span in spans:
            events.append({'id': hashlib.sha256(_json_bytes([source_hash, channel, method, label, span])).hexdigest(),
                'span': span, 'channel': channel, 'label': EVENT_LABELS[label], 'raw_label': label,
                'status': 'observed', 'scope': 'recording_frames', 'boundary_precision': '40ms_model_frame',
                'review_status': 'unreviewed'})
    return {'status': 'partial' if failures else 'ok', 'method': method, 'threshold': THRESHOLD,
            'analysis_policy': active_policy,
            'frame_rate_hz': 25, 'score_kind': 'uncalibrated_audioset_sigmoid',
            'assessed_spans': _union(assessed), 'windows': observations, 'events': events,
            'speech_intervals': [{'span': span, 'channel': channel} for span in _union(positive)],
            'frame_labels': [labels[i] for i in retained], 'failures': failures}
