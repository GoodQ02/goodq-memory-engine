"""Resolve a sampled face image from its persisted UCF observation authority."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def resolve_sampled_face(epoch: Path, raw: Path, rows: list[dict], *, manifest_cache: dict | None = None) -> tuple[Path, float] | None:
    fields = ('image_path', 'image_sha256', 'observation_timestamp')
    if not any(any(key in row['payload'] for key in fields) for row in rows):
        return None  # Historical midpoint/standalone records keep their own path.
    for row in rows:
        if row.get('payload_hash') and hashlib.sha256(json.dumps(row['payload'], sort_keys=True).encode()).hexdigest() != row['payload_hash']:
            raise ValueError('Face observation payload hash mismatch')
    first = rows[0]['payload']
    if any(any(key not in row['payload'] or row['payload'][key] != first.get(key)
               for key in fields) for row in rows):
        raise ValueError('Face observation authority is incomplete or inconsistent')
    timestamp = first['observation_timestamp']
    if type(timestamp) not in (float, int) or not math.isfinite(timestamp):
        raise ValueError('Face observation timestamp is invalid')
    # UCF's existing unique key uses per-face offsets. The observed media time
    # is separate and must be what reviewers see; no schema migration is needed.
    if any(abs(row['t_start'] - (timestamp + .001 * row['payload']['face_index'])) > .00051 for row in rows):
        raise ValueError('Face observation timestamp disagrees with UCF authority')
    processing = (epoch / 'processing').resolve()
    relative = raw.resolve().relative_to(processing)
    media = processing / relative.parts[0]
    image = Path(first['image_path']).resolve(strict=True)
    if not image.is_relative_to(media):
        raise ValueError('Face observation image escapes its source media directory')
    if hashlib.sha256(image.read_bytes()).hexdigest() != first['image_sha256']:
        raise ValueError('Face observation image hash mismatch')
    manifest_path = media / 'video/scene_manifest.json'
    # Callers may reuse source metadata within one read request, never across
    # requests. Each observation still verifies its payload, image and scene.
    if manifest_cache is None:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    else:
        if manifest_path not in manifest_cache:
            manifest_cache[manifest_path] = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest = manifest_cache[manifest_path]
    if manifest.get('epoch_id', epoch.name) != epoch.name:
        raise ValueError('Face observation epoch mismatch')
    hashes = {row['video_hash'] for row in rows}
    sources = {row['source_artifact_id'] for row in rows}
    if len(hashes) != 1 or len(sources) != 1 or manifest.get('video_hash', manifest.get('video_id')) not in hashes:
        raise ValueError('Face observation source mismatch')
    scenes = [scene for scene in manifest.get('scenes', []) if (scene.get('scene_id') or scene.get('id')) in sources]
    if len(scenes) != 1 or not (scenes[0]['start'] <= timestamp < scenes[0]['end'] or
                               scenes[0]['start'] == timestamp == scenes[0]['end']):
        raise ValueError('Face observation is outside its scene')
    return image, float(timestamp)
