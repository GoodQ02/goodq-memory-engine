"""Read projection of versioned recording evidence; no inference or identity writes."""
from copy import deepcopy
from urllib.parse import quote

from wsl2_audio.scene_projection import validate_scene_audio
from wsl2_audio.scene_consumers import validate_review


def public_audio_evidence(video_id, projection):
    if projection is None:
        return None
    projection = validate_scene_audio(projection)
    scene_id = projection['scene']['scene_id']
    result = {key: deepcopy(projection[key]) for key in (
        'recording_id', 'scene', 'status', 'quality_qualification', 'voice_review_status')}
    result.update(schema='goodq.scene_audio_view.v1', source_sha256=projection['source']['sha256'],
                  evidence_sha256=projection['content_sha256'], identity_claim=False,
                  voice_signature_status=projection.get('voice_signature_status', 'not_materialized'))
    if projection['provenance'].get('transcription_context'):
        result['transcription_context'] = deepcopy(projection['provenance']['transcription_context'])
    fields = ('id', 'text', 'media_span', 'display_span', 'span', 'channel', 'speaker', 'track_id',
              'completeness', 'eligibility', 'confidence', 'owner_scene_id', 'ownership')
    result['utterances'] = [{k: deepcopy(row[k]) for k in fields if k in row} for row in projection['utterances']]
    result['sound_events'] = [{k: deepcopy(v) for k, v in row.items() if k in (
        'id', 'label', 'span', 'channel', 'status', 'score', 'boundary_precision', 'media_span', 'display_span')}
        for row in projection['sound_events']]
    result['overlap'] = [{k: deepcopy(v) for k, v in row.items() if k in (
        'span', 'channel', 'status', 'reason', 'detector', 'precision',
        'media_span', 'display_span')} for row in projection['overlap']]
    result['vocal_delivery'] = deepcopy(projection['vocal_delivery'])
    result['reviews'] = []
    for review in projection['voice_reviews']:
        result['reviews'].append({k: deepcopy(review[k]) for k in (
            'id', 'utterance_id', 'span', 'channel', 'sample_rate', 'sample_count', 'owner_scene_id', 'purpose')})
        result['reviews'][-1]['url'] = (f"/api/videos/{quote(str(video_id), safe='')}/scenes/"
            f"{quote(scene_id, safe='')}/audio-evidence/{review['id']}")
    return result


def review_media(projection, review_id, processing_root):
    projection = validate_scene_audio(projection)
    matches = [row for row in projection['voice_reviews'] if row['id'] == review_id]
    if len(matches) != 1:
        raise ValueError('Review audio is missing or ambiguous')
    return validate_review(matches[0], projection['source'], root=processing_root)
