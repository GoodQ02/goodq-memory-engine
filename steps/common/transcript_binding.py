"""Validate scene-bound transcript outcome evidence without inferring support."""
import hashlib


class TimelineReadCache:
    """Request-local reads shared by enrichment and provenance projection."""

    def __init__(self, loader):
        self.loader = loader
        self.inventory = None
        self.timelines = {}
        self.metadata = {}
        self.sources = None

    def list_processed_videos(self):
        if self.inventory is None:
            self.inventory = tuple(self.loader.list_processed_videos())
        return list(self.inventory)

    def load_temporal_index(self, key):
        if key not in self.timelines:
            self.timelines[key] = self.loader.load_temporal_index(key)
        return self.timelines[key]

    def get_video_metadata(self, key):
        if key not in self.metadata:
            self.metadata[key] = self.loader.get_video_metadata(key)
        return self.metadata[key]

    def __getattr__(self, name):
        return getattr(self.loader, name)

    def matching_timelines(self, video_id):
        if self.sources is None:
            sources = {}
            for key in self.list_processed_videos():
                timeline = self.load_temporal_index(key)
                if isinstance(timeline, dict) and isinstance(timeline.get('video_id'), str):
                    sources.setdefault(timeline['video_id'], []).append(timeline)
            self.sources = sources
        return self.sources.get(video_id, [])

OUTCOMES = {'transcript_available', 'no_speech', 'no_intelligible_speech',
            'low_confidence', 'runtime_failure', 'missing_audio_artifact', 'unclassified'}
KEYS = ('video_id', 'scene_id', 'run_id', 'epoch_id')

def unknown(reason):
    return {'status': 'unverified', 'reason': reason}

def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def scope(video, scene, cfg):
    from steps.common.transcript_authority import lookup
    record = lookup(video, scene, cfg)
    return {k: (record or {}).get(k) for k in KEYS}

def validate(record, expected, text):
    if not isinstance(record, dict): return unknown('missing_record')
    if any(not isinstance(expected.get(k), str) or not expected[k].strip() for k in KEYS):
        return unknown('missing_authority')
    if any(record.get(k) != expected[k] for k in KEYS): return unknown('provenance_mismatch')
    if type(record.get('schema')) is not int or record.get('schema') != 1: return unknown('unsupported_schema')
    if not isinstance(record.get('outcome'), str) or record['outcome'] not in OUTCOMES: return unknown('invalid_outcome')
    if not isinstance(record.get('outcome_reason'), str) or not record['outcome_reason'].strip():
        return unknown('missing_outcome_reason')
    if not isinstance(text, str) or record.get('text_sha256') != digest(text):
        return unknown('transcript_mismatch')
    if (record['outcome'] in {'no_speech','no_intelligible_speech'} and text.strip()) or (
            record['outcome'] == 'transcript_available' and not text.strip()):
        return unknown('content_conflict')
    return {'status':'bound', **{k:record[k] for k in ('schema', *KEYS, 'outcome', 'outcome_reason', 'text_sha256')}}

def persist(scene, video, cfg, text):
    record = scene.get('transcript_outcome_evidence')
    from steps.common.transcript_authority import lookup
    authority = lookup(video, str(scene.get('scene_id') or ''), cfg)
    if record != authority: return unknown('authority_record_mismatch')
    result = validate(record, scope(video, str(scene.get('scene_id') or ''), cfg), text)
    if result['status'] != 'bound': return result
    audio = scene.get('audio') if isinstance(scene.get('audio'), dict) else {}
    for source in (scene, audio):
        if source.get('transcript_outcome') not in (None, record['outcome']):
            return unknown('outcome_conflict')
        if source.get('transcript_outcome_reason') not in (None, record['outcome_reason']):
            return unknown('reason_conflict')
        if (source.get('audio_error') or source.get('error')) and record['outcome'] != 'runtime_failure':
            return unknown('error_conflict')
    meta = audio.get('transcript_meta') or {}
    if isinstance(meta,dict) and meta.get('status') in {'failed','error'} and record['outcome'] != 'runtime_failure':
        return unknown('error_conflict')
    return result

def project(payload, loader, cfg, text):
    expected = scope(payload.get('video_id'), payload.get('scene_id'), cfg)
    if any(payload.get(k) != expected[k] or not payload.get(k) for k in KEYS):
        return unknown('candidate_provenance_mismatch')
    try:
        if isinstance(loader, TimelineReadCache):
            timelines = loader.matching_timelines(payload['video_id'])
        else:
            timelines = []
            for key in loader.list_processed_videos():
                candidate = loader.load_temporal_index(key)
                if isinstance(candidate,dict) and candidate.get('video_id') == payload['video_id']:
                    timelines.append(candidate)
        if len(timelines) != 1: return unknown('source_missing_or_ambiguous')
        timeline = timelines[0]
    except (OSError, ValueError): return unknown('timeline_unavailable')
    if not isinstance(timeline,dict): return unknown('timeline_unavailable')
    if timeline.get('video_id') != expected['video_id']: return unknown('source_mismatch')
    segments=timeline.get('segments')
    if not isinstance(segments,list): return unknown('invalid_segments')
    matches=[s for s in segments if isinstance(s,dict) and s.get('scene_id') == expected['scene_id']]
    if len(matches)!=1: return unknown('scene_missing_or_ambiguous')
    s=matches[0]
    if s.get('full_transcript') != text: return unknown('returned_text_mismatch')
    record=s.get('transcript_outcome_evidence')
    if not isinstance(record,dict) or record.get('status') != 'bound': return unknown('unbound_persisted_record')
    from steps.common.transcript_authority import lookup
    authority = lookup(payload.get("video_id"), payload.get("scene_id"), cfg)
    if {k:v for k,v in record.items() if k != "status"} != authority: return unknown("authority_record_mismatch")
    return validate(record, expected, text)

def fts_provenance(payload, cfg):
    """Carry only validated provenance from the promoted scene's stored metadata."""
    meta = payload.get('meta')
    if not isinstance(meta, dict): return {}
    if any(meta.get(k) != payload.get(k) or not payload.get(k) for k in ('video_id', 'scene_id')):
        return {}
    audio = meta.get('audio')
    if not isinstance(audio, dict): return {}
    text = audio.get('full_text', audio.get('transcript', ''))
    if not isinstance(text, str): return {}
    result = persist(meta, payload['video_id'], cfg, text.strip())
    if result.get('status') != 'bound': return {}
    return {k: result[k] for k in ('run_id', 'epoch_id')}
