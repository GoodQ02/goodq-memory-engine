from __future__ import annotations
from typing import Any, Dict, Optional, List

import os
import datetime as _dt


def _file_times(path: str) -> Dict[str, str]:
    try:
        st = os.stat(path)
        ctime = _dt.datetime.utcfromtimestamp(getattr(st, 'st_ctime', 0.0) or 0.0).isoformat()
        mtime = _dt.datetime.utcfromtimestamp(getattr(st, 'st_mtime', 0.0) or 0.0).isoformat()
        return {"created_utc": ctime, "modified_utc": mtime}
    except Exception:
        return {}


def _mutagen_tags(path: str) -> Dict[str, Any]:
    try:
        import mutagen  # type: ignore
        f = mutagen.File(path, easy=True)
        if not f or not getattr(f, 'tags', None):
            return {}
        tags: Dict[str, Any] = {}
        for k, v in (f.tags or {}).items():
            try:
                if isinstance(v, (list, tuple)):
                    tags[k] = v[0]
                else:
                    tags[k] = v
            except Exception:
                continue
        loc_keys = [k for k in tags.keys() if 'gps' in k.lower() or 'location' in k.lower() or 'geotag' in k.lower()]

        time_keys = [
            'date', 'year', 'originaldate', 'recording_time', 'tdrc', 'tdrl', 'tden', 'releasetime'
        ]
        time_hints: Dict[str, Any] = {"raw": {}}
        for tk in time_keys:
            for k in list(tags.keys()):
                if tk in k.lower():
                    time_hints["raw"][k] = tags[k]

        def _try_norm(vals: List[str | Any]) -> List[str]:
            out: List[str] = []
            for v in vals:
                s = str(v)
                for fmt in ("%Y-%m-%d", "%Y", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"):
                    try:
                        dt = _dt.datetime.strptime(s[:10], fmt)
                        out.append(dt.date().isoformat())
                        break
                    except Exception:
                        continue
            return out

        normalized_dates: List[str] = _try_norm(list(time_hints["raw"].values())) if time_hints["raw"] else []
        if normalized_dates:
            time_hints["normalized"] = normalized_dates

        out = {"tags": tags}
        if loc_keys:
            out["location_hints"] = {k: tags[k] for k in loc_keys}
        if time_hints.get("raw") or time_hints.get("normalized"):
            out["tag_time_hints"] = time_hints
        return out
    except Exception:
        return {}


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
    except Exception:
        pass
    try:
        import librosa  # type: ignore
        dur = librosa.get_duration(path=path)
        if dur:
            meta['duration_sec'] = float(dur)
        sr = None
        try:
            sr = librosa.get_samplerate(path)
        except Exception:
            pass
        if sr:
            meta['sample_rate'] = int(sr)
        if 'channels' not in meta:
            try:
                import soundfile as sf  # type: ignore
                with sf.SoundFile(path) as sfh:
                    meta['channels'] = int(sfh.channels)
            except Exception:
                pass
        return meta
    except Exception:
        return meta


def audio_metadata(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"audio_meta": None}
    meta: Dict[str, Any] = {}
    meta.update(_file_times(path))
    meta.update(_mutagen_tags(path))
    meta.update(_probe_audio(path))
    return {"audio_meta": meta}
