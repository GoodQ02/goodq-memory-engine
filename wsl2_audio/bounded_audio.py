"""File-backed model audio with bounded, phase-aligned source reads."""

import hashlib
import json
import os
from pathlib import Path
import tempfile

from wsl2_audio.recording_audio import _atomic_json, _json_bytes, _sha_file, read_channel
from wsl2_audio.recognition import _model_audio
from wsl2_audio.source_clock import SampleSpan


def model_channel(recording, channel, *, reader=read_channel, read_seconds=30):
    """Resample once to a file mapping, preserving full-recording filter phase.

    Whole-second read anchors and a one-second filter halo preserve the existing
    resample_poly transform. No resampled full-channel ndarray is retained.
    Source PCM integrity was verified by the recording checkpoint loader.
    """
    import numpy as np

    if type(read_seconds) is not int or not 1 <= read_seconds <= 30:
        raise ValueError('Model-audio reads must be bounded to 1..30 seconds')
    meta = recording['source']
    rate, count = meta['sample_rate'], meta['sample_count']
    if type(channel) is not int or not 0 <= channel < meta['channels']:
        raise ValueError('Invalid source channel')
    identity = {'pcm_sha256': meta['pcm_sha256'], 'rate': rate, 'count': count,
                'channels': meta['channels'], 'channel': channel,
                'transform': 'phase_aligned_resample_poly_f32_v1', 'read_seconds': read_seconds,
                'implementation': _sha_file(Path(__file__))}
    key = hashlib.sha256(_json_bytes(identity)).hexdigest()
    root = Path(recording['pcm']['path']).parent / 'model-audio'
    path, receipt = root / (key+'.f32le'), root / (key+'.json')
    expected = (count*16000+rate-1)//rate
    if receipt.is_file():
        saved = json.loads(receipt.read_text(encoding='utf-8'))
        if (saved['identity'] != identity or path.stat().st_size != expected*4
                or _sha_file(path) != saved['sha256']):
            raise ValueError('Model-audio checkpoint differs from its source binding')
        return np.memmap(path, dtype='<f4', mode='c', shape=(expected,)), saved['silent']
    root.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=key+'.', suffix='.partial', dir=root)
    silent = True
    try:
        with os.fdopen(fd, 'wb') as stream:
            for start in range(0, count, read_seconds*rate):
                end = min(count, start+read_seconds*rate)
                context = SampleSpan(max(0, start-rate), min(count, end+rate))
                samples = reader(recording, context, channel)
                source, audio, _ = _model_audio(samples, rate, context)
                silent = silent and not bool(source.any())
                first = (start-context.start)*16000//rate
                length = (end*16000+rate-1)//rate-start*16000//rate
                stream.write(audio[first:first+length].astype('<f4', copy=False).tobytes())
            stream.flush()
            os.fsync(stream.fileno())
        if Path(temporary).stat().st_size != expected*4:
            raise ValueError('Model-audio sample coverage mismatch')
        digest = _sha_file(Path(temporary))
        os.replace(temporary, path)
        _atomic_json({'identity': identity, 'sha256': digest, 'silent': silent,
                      'samples': expected, 'sample_rate': 16000}, receipt)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return np.memmap(path, dtype='<f4', mode='c', shape=(expected,)), silent
