"""Publish recording evidence for existing scene, summary and identity consumers.

The caller supplies the canonical scenes and the durable processing root. This
module does no recognition, speaker reassignment or eligibility reassessment.
"""
from array import array
from copy import deepcopy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys
import uuid
import wave

from wsl2_audio import speaker_signature
from wsl2_audio.enrichment import select_voice_groups
from wsl2_audio.recording_audio import _atomic_json, _json_bytes, _sha_file, read_channel
from wsl2_audio.scene_projection import assign_owners, project_audio, seal_scene_audio, validate_scene_audio
from wsl2_audio.source_clock import SampleSpan

REVIEW_SCHEMA = 'goodq.audio_review.v1'


def _digest(value):
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _write_once(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        # Publish a complete inode without replacing another writer's retained
        # result. A killed writer may leave a temporary file, never a partial
        # final WAV/signature that poisons an otherwise identical retry.
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != contents:
                raise ValueError('Retained audio artifact changed')
    finally:
        temporary.unlink(missing_ok=True)


def _wav(samples, rate):
    # Preserve rate/channel and amplitude. Quantization is explicit, with no
    # normalization or clipping of an over-range source into a new signal.
    if any(not math.isfinite(v) or abs(v) > 1 for v in samples):
        raise ValueError('Review PCM is nonfinite or outside PCM32 range')
    pcm = array('i', (round(v * 2147483647) for v in samples))
    if pcm.itemsize != 4:
        raise ValueError('PCM32 requires four-byte integers')
    if sys.byteorder != 'little':
        pcm.byteswap()
    output = io.BytesIO()
    with wave.open(output, 'wb') as stream:
        stream.setparams((1, 4, rate, len(samples), 'NONE', 'not compressed'))
        stream.writeframes(pcm.tobytes())
    return output.getvalue()


def validate_review(review, source, *, root=None):
    if review.get('schema') != REVIEW_SCHEMA:
        raise ValueError('Unsupported audio review schema')
    if _digest({k: v for k, v in review.items() if k != 'content_sha256'}) != review.get('content_sha256'):
        raise ValueError('Audio review record changed')
    if review['source_sha256'] != source['sha256'] or review['pcm_sha256'] != source['pcm_sha256']:
        raise ValueError('Audio review source mismatch')
    span = SampleSpan(**review['span'])
    rate = source['sample_rate']
    if (span.end > source['sample_count'] or review['sample_rate'] != rate
            or type(review['channel']) is not int or not 0 <= review['channel'] < source['channels']
            or review['sample_count'] != span.end-span.start
            or review['encoding'] != 'pcm_s32le_quantized_from_source_f64le'):
        raise ValueError('Audio review geometry mismatch')
    relative = Path(review['relative_path'])
    if relative.is_absolute() or '..' in relative.parts or '\\' in review['relative_path'] or ':' in review['relative_path']:
        raise ValueError('Audio review path must be relative to processing')
    if root is None:
        return review
    root = Path(root).resolve(strict=True)
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root) or _sha_file(path) != review['sha256']:
        raise ValueError('Audio review media changed or escaped processing')
    with wave.open(str(path), 'rb') as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getnframes()) != (1, 4, rate, review['sample_count']):
            raise ValueError('Audio review WAV geometry mismatch')
    return path


class _Encoder:
    def __init__(self, scratch):
        self.scratch, self.model = scratch, None

    def __call__(self, pieces, rate):
        import numpy as np
        import torch
        import torchaudio
        if self.model is None:
            self.model = speaker_signature.load_encoder('cpu', str(self.scratch))
        tensors = [torch.from_numpy(np.asarray(piece, dtype=np.float32)).unsqueeze(0) for piece in pieces]
        if rate != 16000:
            tensors = [torchaudio.functional.resample(t, rate, 16000) for t in tensors]
        with torch.inference_mode():
            values = self.model.encode_batch(torch.cat(tensors, dim=-1)).flatten().detach().cpu().numpy()
        norm = float(np.linalg.norm(values))
        if values.size != speaker_signature.DIMENSION or not np.isfinite(values).all() or norm <= 1e-8:
            raise ValueError('Invalid ECAPA speaker embedding')
        return (values / norm).astype(np.float32).tolist()


def validate_signature(signature):
    if _digest({k: v for k, v in signature.items() if k != 'content_sha256'}) != signature.get('content_sha256'):
        raise ValueError('Voice contribution changed')
    speaker_signature.validate_metadata(signature)
    vector = signature['embedding']
    if (len(vector) != speaker_signature.DIMENSION or any(not math.isfinite(v) for v in vector)
            or not math.isclose(sum(v*v for v in vector), 1., rel_tol=1e-4, abs_tol=1e-4)):
        raise ValueError('Invalid normalized voice contribution')
    reviews = signature['review_evidence']
    if (not 2 <= len(reviews) <= 4 or len(reviews) != signature['segment_count']
            or len({r['utterance_id'] for r in reviews}) != len(reviews)
            or {r['utterance_id'] for r in reviews} != set(signature['utterance_ids'])):
        raise ValueError('Voice contribution diversity mismatch')
    for review in reviews:
        validate_review(review, signature['source'])
        if (review['owner_scene_id'] != signature['owner_scene_id']
                or review['eligibility']['voice_sample']['status'] != 'eligible'):
            raise ValueError('Voice contribution includes unowned or ineligible speech')
    return signature


def publish_scene_audio(evidence, scenes, recording, processing_root, *, embed=None):
    """Retain full-span playback and only owner-scene qualified voice signatures."""
    projections = project_audio(evidence, scenes)
    root = Path(processing_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not projections:
        return projections
    first = next(iter(projections.values()))
    source = evidence['source']
    if source.get('audio_track') == 'absent':
        return projections
    if any(recording['source'][key] != source[key] for key in (
            'sha256', 'pcm_sha256', 'sample_count', 'sample_rate', 'channels', 'origin_num', 'origin_den')):
        raise ValueError('Decoded recording differs from evidence')
    if _sha_file(Path(recording['pcm']['path'])) != source['pcm_sha256']:
        raise ValueError('Decoded PCM changed before scene publication')
    owners = assign_owners(evidence, scenes)
    relative_root = Path('audio-evidence') / first['recording_id']
    reviews = {}
    for unit in evidence['utterances']:
        if owners[unit['id']] is None:
            continue
        span = SampleSpan(**unit['span'])
        key = _digest([source['sha256'], source['pcm_sha256'], unit['id'], unit['span'], unit['channel']])
        relative = relative_root / (key + '.wav')
        contents = _wav(read_channel(recording, span, unit['channel']), source['sample_rate'])
        _write_once(root / relative, contents)
        review = {'schema': REVIEW_SCHEMA, 'id': key, 'utterance_id': unit['id'],
            'source_sha256': source['sha256'], 'pcm_sha256': source['pcm_sha256'],
            'span': deepcopy(unit['span']), 'channel': unit['channel'], 'sample_rate': source['sample_rate'],
            'sample_count': span.end-span.start, 'relative_path': relative.as_posix(),
            'sha256': hashlib.sha256(contents).hexdigest(), 'encoding': 'pcm_s32le_quantized_from_source_f64le',
            'owner_scene_id': owners[unit['id']], 'identity_claim': False,
            'eligibility': deepcopy(unit['eligibility']), 'purpose': 'source_review_not_identity_admission'}
        review['content_sha256'] = _digest(review)
        validate_review(review, source, root=root)
        reviews[unit['id']] = review
    signatures, failures = {}, []
    encoder = embed or _Encoder(root / relative_root / 'encoder')
    diagnostics = {}
    for group in select_voice_groups(evidence, owners, diagnostics=diagnostics):
        contribution = _digest([source, speaker_signature.metadata(), group])
        path = root / relative_root / (contribution + '.json')
        try:
            if path.exists():
                signature = json.loads(path.read_text(encoding='utf-8'))
                if _digest({k: v for k, v in signature.items() if k != 'content_sha256'}) != signature.get('content_sha256'):
                    raise ValueError('Voice contribution cache changed')
            else:
                pieces = [read_channel(recording, SampleSpan(**span), group['channel']) for span in group['spans']]
                vector = encoder(pieces, source['sample_rate'])
                if (len(vector) != speaker_signature.DIMENSION or any(not math.isfinite(v) for v in vector)
                        or not math.isclose(sum(v*v for v in vector), 1., rel_tol=1e-4, abs_tol=1e-4)):
                    raise ValueError('Invalid normalized ECAPA contribution')
                signature = {**speaker_signature.metadata(), 'embedding_dim': len(vector), 'embedding': vector,
                    'speaker': first['recording_id'] + ':' + group['speaker'],
                    'contribution_id': contribution, 'owner_scene_id': group['scene_id'],
                    'voiced_seconds': group['voiced_samples']/source['sample_rate'],
                    'segment_count': len(group['spans']), 'utterance_ids': group['utterance_ids'],
                    'source': deepcopy(source), 'review_evidence': [reviews[u] for u in group['utterance_ids']],
                    # Never reinterpret full recording spans as old scene seconds.
                    'selected_segments': [], 'admission_policy': 'recording_speech_v1',
                    'identity_claim': False}
                signature['content_sha256'] = _digest(signature)
                _write_once(path, _json_bytes(signature))
            validate_signature(signature)
            if signature['contribution_id'] != contribution or signature['owner_scene_id'] != group['scene_id']:
                raise ValueError('Voice contribution owner mismatch')
            for review in signature['review_evidence']:
                validate_review(review, source, root=root)
            signatures.setdefault(group['scene_id'], []).append(signature)
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            failures.append({'scene_id': group['scene_id'], 'contribution_id': contribution,
                             'status': 'error', 'reason': type(exc).__name__ + ': ' + str(exc)})
    for scene_id, projection in projections.items():
        projection['voice_selection'] = {**diagnostics,
            'units': [row for row in diagnostics['units'] if row['owner_scene_id'] == scene_id],
            'groups': [row for row in diagnostics['groups'] if row['scene_id'] == scene_id]}
        projection['voice_reviews'] = [deepcopy(reviews[u['id']]) for u in projection['utterances']]
        projection['voice_review_status'] = 'retained' if projection['voice_reviews'] else 'no_utterances'
        projection['voice_signatures'] = signatures.get(scene_id, [])
        projection['voice_signature_errors'] = [row for row in failures if row['scene_id'] == scene_id]
        projection['voice_signature_status'] = ('error' if projection['voice_signature_errors'] else
            'ok' if projection['voice_signatures'] else 'insufficient_qualified_speech')
        projections[scene_id] = validate_scene_audio(seal_scene_audio(projection))
    _atomic_json(projections, root / relative_root / 'scenes.json')
    return projections
