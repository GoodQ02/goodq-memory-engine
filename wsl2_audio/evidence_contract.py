"""Validate the replacement's internal evidence format without repairing it.

Validation is structural. It does not certify observations, acoustic purity,
model accuracy, or the provenance of the supplied bytes.
"""

import json
import re

from wsl2_audio.source_clock import SampleSpan, SourceClock


STAGE_STATES = {"ok", "partial", "not_run", "not_applicable", "disabled", "unavailable", "error", "insufficient_evidence"}
ADMISSION_STATES = {"eligible", "ineligible", "unresolved"}
PURITY_STAGES = ("recognition", "speaker_activity", "overlap", "acoustic_events")


def _object(value, name):
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _array(value, name):
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value


def _sha(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{name} must be a SHA-256 digest")


def _span(value, clock):
    value = _object(value, "span")
    span = SampleSpan(value.get("start"), value.get("end"))
    clock.require_span(span)
    return span


def _covers(spans, target):
    cursor = target.start
    for part in sorted(spans, key=lambda item: (item.start, item.end)):
        if part.start > cursor:
            break
        cursor = max(cursor, part.end)
        if cursor >= target.end:
            return True
    return False


def validate_evidence(payload: dict) -> dict:
    """Return an independent JSON snapshot, or raise ValueError on contradiction."""
    _object(payload, "evidence")
    try:
        snapshot = json.loads(json.dumps(payload, allow_nan=False))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Evidence must contain finite JSON values") from exc
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
        raise ValueError("Unsupported evidence schema_version")
    source = _object(payload.get("source"), "source")
    _sha(source.get('sha256'), 'source.sha256')
    provenance = _object(payload.get("provenance"), "provenance")
    if 'config_identity_method' in provenance:
        from wsl2_audio.profile_identity import METHOD
        if provenance['config_identity_method'] != METHOD:
            raise ValueError('Unsupported configuration identity method')
    for key in ("run_id", "epoch_id", "source_revision"):
        _text(provenance.get(key), f"provenance.{key}")
    for key in ("worker_sha256", "config_sha256"):
        _sha(provenance.get(key), f"provenance.{key}")
    models = _array(provenance.get("models"), "models")
    model_ids = set()
    for model in models:
        _object(model, "model")
        _text(model.get("id"), "model.id")
        _text(model.get("revision"), "model.revision")
        _sha(model.get("sha256"), "model.sha256")
        if model["id"] in model_ids:
            raise ValueError("Duplicate model provenance id")
        model_ids.add(model["id"])

    if source.get('audio_track') == 'absent':
        if (payload.get('status') != 'not_applicable' or payload.get('reason') != 'audio_track_absent'
                or any(payload.get(key) != [] for key in ('utterances', 'overlap', 'sound_events', 'coverage'))
                or any(key in source for key in ('pcm_sha256', 'sample_count', 'sample_rate'))
                or payload.get('stages', {}).get('decode') != {'status': 'not_applicable', 'reason': 'audio_track_absent'}):
            raise ValueError('Absent audio cannot carry sample-clock or inference claims')
        for name, stage in payload['stages'].items():
            if stage.get('status') not in ('not_run', 'not_applicable', 'disabled') or not stage.get('reason'):
                raise ValueError('Absent audio cannot have completed inference stages')
        return snapshot
    _sha(source.get('pcm_sha256'), 'source.pcm_sha256')
    clock = SourceClock(source.get("sample_rate"), source.get("sample_count"),
                        source.get("origin_num"), source.get("origin_den"))

    stages = _object(payload.get("stages"), "stages")
    stage_coverage = {}
    for name, stage in stages.items():
        _text(name, "stage name")
        _object(stage, "stage")
        if stage.get("status") not in STAGE_STATES:
            raise ValueError(f"Unknown stage state: {name}")
        if stage["status"] != "ok":
            _text(stage.get("reason"), f"{name}.reason")
        if name in PURITY_STAGES and stage["status"] in {"ok", "partial"}:
            if stage.get("model_id") not in model_ids:
                raise ValueError("Assessed model stages require their pinned model provenance")
            full_source = SampleSpan(0, clock.sample_count)
            if stage["status"] == "ok" and "assessed_spans" not in stage:
                assessed = [full_source]
            else:
                assessed = [_span(item, clock) for item in _array(stage.get("assessed_spans"), "assessed_spans")]
            if not assessed or (stage["status"] == "ok" and not _covers(assessed, full_source)):
                raise ValueError("Stage outcome contradicts assessed source coverage")
            stage_coverage[name] = assessed

    def coverage_state(records):
        expected_start, analyzed, unassessed = 0, [], []
        for record in _array(records, 'coverage'):
            _object(record, 'coverage record')
            span = _span(record.get('span'), clock)
            if span.start != expected_start:
                raise ValueError('Coverage must account for every source sample exactly once')
            if record.get('status') not in {'analyzed', 'digital_silence', 'unresolved', 'error', 'not_run'}:
                raise ValueError('Unknown coverage state')
            if record['status'] == 'analyzed':
                analyzed.append(span)
            elif record['status'] != 'digital_silence':
                unassessed.append(span)
            expected_start = span.end
        if expected_start != clock.sample_count:
            raise ValueError('Coverage does not reach the end of the source')
        return analyzed, unassessed

    coverage_states = {None: coverage_state(payload.get('coverage'))}
    if 'channel_coverage' in payload:
        channel_coverage = _object(payload['channel_coverage'], 'channel_coverage')
        channels = source.get('channels')
        if type(channels) is not int or channels < 1 or set(channel_coverage) != {str(i) for i in range(channels)}:
            raise ValueError('Channel coverage must account for every retained channel')
        coverage_states.update({int(key): coverage_state(records) for key, records in channel_coverage.items()})

    def require_assessed_signal(span, channel=None):
        analyzed, unassessed = coverage_states[channel]
        if any(span.overlaps(part) for part in unassessed):
            raise ValueError("Admitted evidence intersects unassessed signal")
        if not any(span.overlaps(part) for part in analyzed):
            raise ValueError("Admitted evidence has only digital silence")

    exclusions = []
    for record in _array(payload.get("overlap"), "overlap"):
        _object(record, "overlap record")
        if record.get("status") not in {"observed", "unresolved"}:
            raise ValueError("Unknown overlap state")
        exclusions.append(_span(record.get("span"), clock))
    seen = set()

    def claim_id(record):
        value = _text(record.get("id"), "evidence id")
        if value in seen:
            raise ValueError("Duplicate evidence id")
        seen.add(value)

    for event in _array(payload.get("sound_events"), "sound_events"):
        _object(event, "sound event")
        claim_id(event)
        span = _span(event.get("span"), clock)
        label = _text(event.get("label"), "event label")
        if event.get("status") not in {"observed", "unresolved"}:
            raise ValueError("Unknown sound event state")
        if event["status"] == "observed":
            if event.get('evidence_basis') == 'independent_acoustic':
                from wsl2_audio.eligibility import stage_covers
                if not stage_covers(payload, 'acoustic_events', span, clock, event.get('channel')):
                    raise ValueError('Observed sound event requires independent acoustic assessment')
            else:
                require_assessed_signal(span)
                if not _covers(stage_coverage.get('acoustic_events', []), span):
                    raise ValueError('Observed sound event requires acoustic model provenance')
        if label == "crying":
            exclusions.append(span)

    from wsl2_audio.channel_reconciliation import validate_reconciliation
    validate_reconciliation(payload)
    from wsl2_audio.phrase_resolution import validate_phrase_resolution
    validate_phrase_resolution(payload)
    for utterance in _array(payload.get("utterances"), "utterances"):
        _object(utterance, "utterance")
        claim_id(utterance)
        _text(utterance.get("text"), "utterance text")
        span = _span(utterance.get("span"), clock)
        channel = utterance.get('channel') if 'channel_coverage' in payload else None
        if 'channel_coverage' in payload and (type(channel) is not int or channel not in coverage_states):
            raise ValueError('Utterance has no assessed source channel')
        if utterance.get("completeness") not in {"complete", "incomplete", "unresolved"}:
            raise ValueError("Unknown completeness state")
        language = _object(utterance.get("language"), "language")
        if language.get("status") not in {"observed", "unresolved"}:
            raise ValueError("Unknown language state")
        if language["status"] == "observed":
            _text(language.get("value"), "observed language")
        elif language.get("value") is not None:
            raise ValueError("Unresolved language has no canonical value; retain raw candidates separately")
        speaker = _object(utterance.get("speaker"), "speaker")
        if speaker.get("status") not in {"single", "mixed", "unresolved"}:
            raise ValueError("Unknown speaker state")
        if speaker["status"] == "single":
            _text(speaker.get("id"), "single speaker id")
        previous_start = previous_end = span.start
        for word in _array(utterance.get("words"), "words"):
            _object(word, "word")
            _text(word.get("text"), "word text")
            if word.get("timing") == "unavailable":
                if word.get("span") is not None:
                    raise ValueError("Unavailable word timing must not carry a timestamp")
                _text(word.get("reason"), "unavailable word timing reason")
            elif word.get("timing") == "supported":
                word_span = _span(word.get("span"), clock)
                require_assessed_signal(word_span, channel)
                previous_bound = previous_end if speaker["status"] == "single" else previous_start
                if word_span.start < previous_bound or word_span.end > span.end:
                    raise ValueError("Word times must be ordered inside the utterance")
                previous_start = word_span.start
                previous_end = word_span.end
            else:
                raise ValueError("Unknown word timing state")
        eligibility = _object(utterance.get("eligibility"), "eligibility")
        for purpose in ("transcript", "vocal_delivery", "voice_sample"):
            decision = _object(eligibility.get(purpose), f"eligibility.{purpose}")
            if decision.get("status") not in ADMISSION_STATES:
                raise ValueError("Unknown admission state")
            reasons = _array(decision.get("reasons"), "admission reasons")
            for reason in reasons:
                _text(reason, "admission reason")
            if decision["status"] != "eligible" and not reasons:
                raise ValueError("Withheld speech requires an explicit reason")
            if decision["status"] == "eligible":
                require_assessed_signal(span, channel if purpose == 'transcript' else None)
                if not _covers(stage_coverage.get("recognition", []), span):
                    raise ValueError("Admitted text requires source-bound recognition provenance")
            if purpose != "transcript" and decision["status"] == "eligible":
                if (utterance["completeness"] != "complete" or speaker["status"] != "single"
                        or any(span.overlaps(exclusion) for exclusion in exclusions)
                        or any(not _covers(stage_coverage.get(key, []), span) for key in PURITY_STAGES)):
                    raise ValueError("Individual admission contradicts completeness or purity evidence")
    if 'eligibility_policy' in payload:
        from wsl2_audio.eligibility import POLICY, assess_eligibility

        if payload['eligibility_policy'] != POLICY:
            raise ValueError('Unsupported shared eligibility policy')
        for utterance in payload['utterances']:
            if utterance['eligibility'] != assess_eligibility(utterance, payload, payload['eligibility_policy']):
                raise ValueError('Stored eligibility contradicts the shared eligibility policy')
    if 'vocal_delivery' in payload:
        utterances = {u['id']: u for u in payload['utterances']}
        seen_delivery = set()
        for prediction in _array(payload['vocal_delivery'], 'vocal_delivery'):
            _object(prediction, 'vocal prediction')
            identifier = prediction.get('utterance_id')
            u = utterances.get(identifier)
            if (u is None or identifier in seen_delivery or u['eligibility']['vocal_delivery']['status'] != 'eligible'
                    or prediction.get('span') != u['span'] or prediction.get('channel') != u.get('channel')
                    or prediction.get('model_id') not in model_ids
                    or prediction.get('status') != 'uncertain' or prediction.get('qualification') != 'unqualified'):
                raise ValueError('Vocal prediction contradicts its admitted source input or qualification')
            seen_delivery.add(identifier)
            scores = _object(prediction.get('scores'), 'vocal scores')
            if (not scores or prediction.get('label') not in scores
                    or any(type(value) not in (int, float) or not 0 <= value <= 1 for value in scores.values())
                    or not .999 <= sum(scores.values()) <= 1.001):
                raise ValueError('Invalid vocal score distribution')
    return snapshot
