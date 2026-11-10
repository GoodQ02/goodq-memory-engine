from __future__ import annotations
from typing import Any, Dict, Optional, List

import os
import datetime as _dt
import json
from pathlib import Path
import subprocess

from steps.common.tool_resolver import ToolResolver


def _file_times(path: str) -> Dict[str, str]:
    try:
        st = os.stat(path)
        ctime = _dt.datetime.utcfromtimestamp(getattr(st, 'st_ctime', 0.0) or 0.0).isoformat()
        mtime = _dt.datetime.utcfromtimestamp(getattr(st, 'st_mtime', 0.0) or 0.0).isoformat()
        return {"created_utc": ctime, "modified_utc": mtime}
    except Exception as e:
        print('[WARN] _file_times returning empty dict')
        return {}


def _tag_metadata(tags: Dict[str, Any]) -> Dict[str, Any]:
    loc_keys = [k for k in tags.keys() if 'gps' in k.lower() or 'location' in k.lower() or 'geotag' in k.lower()]
    time_keys = [
        'date', 'year', 'originaldate', 'recording_time', 'tdrc', 'tdrl', 'tden', 'releasetime'
    ]
    time_hints: Dict[str, Any] = {"raw": {}}
    for tk in time_keys:
        for k in tags:
            if tk in k.lower():
                time_hints["raw"][k] = tags[k]

    normalized_dates: List[str] = []
    for value in time_hints["raw"].values():
        for fmt in ("%Y-%m-%d", "%Y", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                date = _dt.datetime.strptime(str(value)[:10], fmt)
                normalized_dates.append(date.date().isoformat())
                break
            except ValueError:
                continue
    if normalized_dates:
        time_hints["normalized"] = normalized_dates
    out: Dict[str, Any] = {"tags": tags}
    if loc_keys:
        out["location_hints"] = {k: tags[k] for k in loc_keys}
    if time_hints.get("raw") or time_hints.get("normalized"):
        out["tag_time_hints"] = time_hints
    return out


def _mutagen_tags(path: str) -> Dict[str, Any]:
    try:
        import mutagen  # type: ignore
        f = mutagen.File(path, easy=True)
        if not f or not getattr(f, 'tags', None):
            print('[WARN] _mutagen_tags returning empty dict')
            return {}
        tags: Dict[str, Any] = {}
        for k, v in (f.tags or {}).items():
            try:
                if isinstance(v, (list, tuple)):
                    tags[k] = v[0]
                else:
                    tags[k] = v
            except Exception as e:
                print(f'[ERROR] Exception in step.py line 33: {str(e)}')
                continue
        return _tag_metadata(tags)
    except Exception as e:
        print('[WARN] _mutagen_tags returning empty dict')
        return {}


def _ffprobe_wav_tags(path: str) -> Dict[str, Any]:
    """Read RIFF container tags that Mutagen's WAV/ID3 reader can miss."""
    reader = {"engine": "ffprobe", "source": "container_tags"}
    try:
        tool = ToolResolver.resolve_tool("ffprobe")
        if not tool.get("found") or not tool.get("path"):
            return {"tag_reader": {**reader, "status": "unavailable", "reason": "ffprobe_missing"}}
        result = subprocess.run(
            [tool["path"], "-v", "error", "-show_entries", "format_tags", "-of", "json", path],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
            check=False,
        )
        if result.returncode != 0:
            return {"tag_reader": {**reader, "status": "error", "reason": "ffprobe_failed"}}
        tags = json.loads(result.stdout).get("format", {}).get("tags", {})
        if not isinstance(tags, dict):
            raise ValueError("invalid container tags")
        return {"tags": tags, "tag_reader": {**reader, "status": "ok" if tags else "no_tags"}}
    except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError) as exc:
        return {"tag_reader": {**reader, "status": "error", "reason": type(exc).__name__}}


def _probe_audio(path: str) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    try:
        import soundfile as sf  # type: ignore
        info = sf.info(path)
        if getattr(info, 'duration', None):
            meta['duration_sec'] = float(info.duration)
        if getattr(info, 'samplerate', None):
            meta['sample_rate'] = int(info.samplerate)
        if getattr(info, 'channels', None):
            meta['channels'] = int(info.channels)
        return meta
    except Exception as e:
        print(f'[ERROR] Exception in step.py line 88: {str(e)}')
        pass
    try:
        import librosa  # type: ignore
        dur = librosa.get_duration(path=path)
        if dur:
            meta['duration_sec'] = float(dur)
        sr = None
        try:
            sr = librosa.get_samplerate(path)
        except Exception as e:
            print(f'[ERROR] Exception in step.py line 99: {str(e)}')
            pass
        if sr:
            meta['sample_rate'] = int(sr)
        if 'channels' not in meta:
            try:
                import soundfile as sf  # type: ignore
                with sf.SoundFile(path) as sfh:
                    meta['channels'] = int(sfh.channels)
            except Exception as e:
                print(f'[ERROR] Exception in step.py line 109: {str(e)}')
                pass
        return meta
    except Exception as e:
        return meta


def audio_metadata(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"audio_meta": None}
    meta: Dict[str, Any] = {}
    meta.update(_file_times(path))
    tag_metadata = _mutagen_tags(path)
    if Path(path).suffix.lower() in {".wav", ".wave"} and not tag_metadata.get("tag_time_hints"):
        probed = _ffprobe_wav_tags(path)
        tags = {**probed.get("tags", {}), **tag_metadata.get("tags", {})}
        if tags:
            tag_metadata = _tag_metadata(tags)
        tag_metadata["tag_reader"] = probed["tag_reader"]
    elif tag_metadata:
        tag_metadata["tag_reader"] = {"engine": "mutagen", "source": "container_tags", "status": "ok"}
    # Filesystem creation/modification times describe this file, including a
    # freshly extracted WAV. Only explicit container tags feed recording hints.
    meta.update(tag_metadata)
    meta.update(_probe_audio(path))
    return {"audio_meta": meta}
