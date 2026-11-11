"""Opt-in recording job shared by the existing ingestion callers.

This adapter owns no models, scene detection, store or identity policy. A caller
provides the original file and canonical scenes before any scene audio work.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

from wsl2_audio.recording_audio import _atomic_json, _sha_file
from wsl2_audio.recording_engine import _identity, _worker_digest
from wsl2_audio.scene_projection import legacy_audio, validate_scene_audio


RECOGNITION_STEPS = frozenset({
    'audio_transcribe', 'audio_transcribe_local', 'audio_diarize',
    'audio_unified_wsl2', 'audio_emotion',
})


def selected(cfg):
    value = (cfg.get('audio') or {}).get('recording_engine') or {}
    return value.get('enabled') is True


def settings(cfg):
    from scripts.config_schema import RecordingEngineConfig
    value = RecordingEngineConfig.model_validate((cfg.get('audio') or {}).get('recording_engine') or {})
    if not value.enabled:
        raise ValueError('Recording engine was not explicitly selected')
    result = value.model_dump()
    for key in ('profile', 'python', 'source_revision'):
        if not result.get(key):
            raise ValueError(f'Recording engine requires {key}')
    if result['transport'] == 'wsl' and not all(result.get(k) for k in ('distro', 'user')):
        raise ValueError('Recording WSL transport requires an explicit distro and user')
    # Segmented modes must consume shared recording evidence rather than chunk ASR;
    # reject unknown activation strings up front.
    mode = str((cfg.get('segmentation') or {}).get('activation') or 'off').lower()
    env_mode = os.environ.get('GOODQ_SEGMENTATION_MODE', '').lower()
    if mode not in ('off', 'shadow', 'authoritative') or env_mode not in ('', 'off', 'shadow', 'authoritative'):
        raise ValueError('Unsupported segmentation activation mode for recording engine')
    return result


def runtime_path(path, transport):
    path = Path(path).resolve()
    if transport == 'wsl' and os.name == 'nt':
        if not path.drive or path.drive.startswith('\\\\'):
            raise ValueError('Recording WSL transport requires a local drive path')
        return '/mnt/' + path.drive[0].lower() + path.as_posix()[2:]
    return str(path)


def prepare(cfg, source, scenes, *, processing_root=None):
    """Run once before scene fan-out; the returned handle is immutable and reusable."""
    options = settings(cfg)
    source = Path(source).resolve(strict=True)
    profile = Path(options['profile']).resolve(strict=True)
    from wsl2_audio.recognition import transcription_context
    profile_context = transcription_context(json.loads(profile.read_text(encoding='utf-8-sig')))
    configured_context = transcription_context((cfg.get('audio') or {}).get('transcribe') or {})
    if configured_context and configured_context != profile_context:
        raise ValueError('Recording profile must declare the configured transcription vocabulary')
    if options.get('ecapa_model_dir'):
        from wsl2_audio.speaker_signature import FILES
        encoder_root = Path(options['ecapa_model_dir']).resolve(strict=True)
        for name, digest in FILES.items():
            if _sha_file(encoder_root / name) != digest:
                raise ValueError(f'Pinned ECAPA asset hash mismatch: {name}')
        options['ecapa_model_dir'] = str(encoder_root)
    run = cfg.get('run') or {}
    if not run.get('id'):
        raise ValueError('Recording job requires a run id')
    if processing_root is None:
        db_dir = (cfg.get('paths') or {}).get('db_dir')
        if not db_dir:
            raise ValueError('Recording job requires an isolated processing root')
        processing_root = Path(db_dir) / 'processing'
    root = Path(processing_root).resolve()
    request = {'source_path': runtime_path(source, options['transport']),
        'run_id': run['id'], 'epoch_id': str(run.get('epoch_id') or root.parent.name),
        'fingerprint': {'source_revision': options['source_revision']},
        'limits': {'max_pcm_bytes': options['max_pcm_bytes'], 'timeout_seconds': options['timeout_seconds']},
        'scenes': deepcopy(scenes), 'processing_root': runtime_path(root, options['transport'])}
    source_hash = _sha_file(source)
    if options.get('native_scratch_root'):
        request['source_sha256'] = source_hash
    identity = {'request': request, 'source_sha256': source_hash,
        'profile_sha256': _sha_file(profile), 'worker_sha256': _worker_digest(),
        'runtime': {key: options[key] for key in ('transport', 'python', 'distro', 'user', 'ecapa_model_dir')}}
    if options.get('native_scratch_root'):
        identity['runtime']['native_scratch_root'] = options['native_scratch_root']
    job = root / 'audio-recordings' / _identity(identity)
    from filelock import FileLock
    job.mkdir(parents=True, exist_ok=True)
    with FileLock(str(job / 'job.lock'), timeout=options['timeout_seconds']):
        return _complete_job(job, identity, request, source, profile, scenes, options)


def _complete_job(job, identity, request, source, profile, scenes, options):
    from scripts.wsl2_audio_bridge import finalize_recording_request
    receipt = job / 'job.json'
    if receipt.is_file():
        saved = json.loads(receipt.read_text(encoding='utf-8'))
        if saved['identity'] != identity:
            raise ValueError('Recording job identity changed')
        load(saved['handle'])
        if saved.get('reusable', True):
            finalize_recording_request(job, options)
            return saved['handle']
    job.mkdir(parents=True, exist_ok=True)
    request_path = job / 'request.json'
    _atomic_json(request, request_path)
    from scripts.wsl2_audio_bridge import run_recording_request
    run_recording_request(request_path, profile, job, options)
    if (_sha_file(source) != identity['source_sha256'] or _worker_digest() != identity['worker_sha256']
            or _sha_file(profile) != identity['profile_sha256']):
        raise ValueError('Recording source, profile or worker changed during analysis')
    if options.get('native_scratch_root'):
        from wsl2_audio.native_scratch import verify_export
        plan = json.loads((job/'native-plan.json').read_text(encoding='utf-8'))
        verify_export(job, job.parent.parent, plan)
    output = job / 'scene_audio.json'
    handle = {'path': str(output), 'sha256': _sha_file(output),
        'processing_root': str(job.parent.parent), 'source_sha256': identity['source_sha256'],
        'run_id': request['run_id'], 'epoch_id': request['epoch_id']}
    values = load(handle)
    if set(values) != {s['scene_id'] for s in scenes}:
        raise ValueError('Recording result does not cover the canonical scenes')
    for scene in scenes:
        if values[scene['scene_id']]['scene'] != scene:
            raise ValueError('Recording result changed the canonical scene bounds')
    reusable = not any(p.get('voice_signature_errors') or
        any(stage.get('status') in ('error', 'unavailable', 'partial') for stage in p['stages'].values())
        for p in values.values())
    _atomic_json({'identity': identity, 'handle': handle, 'reusable': reusable}, receipt)
    if reusable:
        finalize_recording_request(job, options)
    return handle


def load(handle, scene_id=None):
    path = Path(handle['path'])
    if _sha_file(path) != handle['sha256']:
        raise ValueError('Recording scene artifact changed')
    payload = json.loads(path.read_text(encoding='utf-8'))
    result = {}
    for ident, audio in payload.items():
        if scene_id is not None and ident != scene_id:
            continue
        projection = validate_scene_audio(audio['audio_evidence'])
        if projection['source']['sha256'] != handle['source_sha256'] or projection['scene']['scene_id'] != ident:
            raise ValueError('Recording source/scene binding mismatch')
        if any(projection['provenance'][key] != handle[key] for key in ('run_id', 'epoch_id')):
            raise ValueError('Recording run/epoch binding mismatch')
        reviews = {r['id']: r for r in projection.get('voice_reviews', [])}
        for signature in projection.get('voice_signatures', []):
            reviews.update({r['id']: r for r in signature['review_evidence']})
        if reviews:
            from wsl2_audio.scene_consumers import validate_review
            # Earlier candidate-only handles have this fixed layout but no root field.
            root = handle.get('processing_root')
            if root is None and path.parent.parent.name == 'audio-recordings':
                root = path.parent.parent.parent
            if root is None:
                raise ValueError('Recording handle lacks its processing root')
            for review in reviews.values():
                validate_review(review, projection['source'], root=root)
        result[ident] = projection
    return result


def ucf_transcript_segments(projection):
    """Per-utterance eligible transcript occurrences before linear consumer deduplication."""
    projection = validate_scene_audio(projection)
    offset = projection['scene']['start']
    return [{'id': u['id'], 'text': u['text'],
        'start': u['display_span']['start'] - offset, 'end': u['display_span']['end'] - offset,
        'speaker': u['track_id'], 'speaker_status': u['speaker']['status'],
        'source_span': deepcopy(u['span']), 'owner_scene_id': u['owner_scene_id'],
        'confidence': deepcopy(u['confidence']), 'timing_scope': 'scene_display_only'}
        for u in projection['utterances']
        if u['eligibility']['transcript']['status'] == 'eligible']


def scene_result(handle, scene_id, scene=None):
    projection = load(handle, scene_id)[scene_id]
    if scene is not None and any(float(projection['scene'][k]) != float(scene[k]) for k in ('start', 'end')):
        raise ValueError('Recording scene bounds differ from caller')
    return {**legacy_audio(projection), 'recording_audio': deepcopy(handle)}


def require_matching_resume(audio, handle, scene_id):
    """A completed legacy/stale scene is not completion of the selected candidate."""
    audio = audio.get('data', audio)
    previous = audio.get('audio_evidence')
    current = load(handle, scene_id)[scene_id]
    if previous is None:
        raise ValueError('Existing audio belongs to another engine; use a fresh isolated destination or explicit reprocessing')
    validate_scene_audio(previous)
    execution_fields = {'provenance', 'recording_evidence_sha256', 'content_sha256'}
    if {k:v for k,v in previous.items() if k not in execution_fields} != {
            k:v for k,v in current.items() if k not in execution_fields}:
        raise ValueError('Existing recording analysis differs; use a fresh isolated destination or explicit reprocessing')


def step_result(item, cfg):
    """Direct aliases consume a job; only a standalone whole-file item can create one."""
    handle = item.get('recording_audio')
    if handle is None:
        if not item.get('recording_source_path'):
            raise ValueError('Recording step requires recording_audio or explicit recording_source_path; scene crops are not recordings')
        scene = item.get('scene') or {'start': 0., 'end': item['duration']}
        handle = prepare(cfg, item['recording_source_path'],
            [{'scene_id': item['scene_id'], 'start': scene['start'], 'end': scene['end']}])
    return scene_result(handle, item['scene_id'], item.get('scene'))


TEXT_FIELDS = {
    'sentiment': ('sentiment', 'sentiment_label', 'sentiment_score', 'sentiment_meta'),
    'emotion_classify': ('emotions', 'emotion_meta'),
    'audio_music_events': ('music_events', 'music_events_meta'),
    'audio_time_hints': ('time_hints', 'time_hints_meta'),
}


def text_binding(projection):
    audio = legacy_audio(projection)
    return {'audio_evidence_sha256': projection['content_sha256'],
        'text_sha256': hashlib.sha256(audio['transcript'].encode()).hexdigest(),
        'basis': 'admitted_transcript_only', 'scope': 'text_estimate_not_vocal_emotion'}


def analyze_text(step, function, item, cfg):
    if not item.get('audio_evidence'):
        return function(item, cfg)
    audio = legacy_audio(item['audio_evidence'])
    clean = {**item, 'transcript': audio['transcript'], 'text': audio['transcript'],
             'segments': audio['segments'], 'speaker_transcript': audio['speaker_transcript'],
             'transcript_meta': audio['transcript_meta'], 'full_text': audio['transcript'],
             'document_text': None, 'ocr_text': None, 'caption': None}
    result = function(clean, cfg)
    if not isinstance(result, dict):
        raise ValueError('Text analysis returned a non-object result')
    meta_key = TEXT_FIELDS[step][-1]
    return {**result, meta_key: {**(result.get(meta_key) or {}), 'input_binding': text_binding(item['audio_evidence'])}}


def bound_text_fields(item):
    """Do not adopt cached legacy scores with no matching recording/text provenance."""
    expected = text_binding(item['audio_evidence'])
    output = {}
    for fields in TEXT_FIELDS.values():
        if (item.get(fields[-1]) or {}).get('input_binding') == expected:
            output.update({key: deepcopy(item[key]) for key in fields if key in item})
    if (item.get('text_emotion_meta') or {}).get('input_binding') == expected:
        output.update({key: deepcopy(item[key]) for key in ('text_emotion_ranking', 'text_emotion_meta') if key in item})
    return output
