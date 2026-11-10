"""Optional whisper.cpp decoder adapter for the shared source-region policy."""
from pathlib import Path
from types import SimpleNamespace
import json
import math
import subprocess
import tempfile
import wave
import numpy as np


def _seconds(value, scale=1.):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return value/scale
    return None


class WhisperCppModel:
    def __init__(self, executable, model):
        self.executable, self.model = executable, model

    def detect_language(self, **kwargs):
        # This CLI contract does not supply a calibrated detection probability.
        # Each independent decode can use native automatic language selection.
        return None, None, []

    def transcribe(self, audio, *, language, beam_size, temperature, vad_filter,
                   word_timestamps, condition_on_previous_text, hotwords=None):
        if vad_filter or condition_on_previous_text:
            raise ValueError('CLI adapter requires independent original-time source regions')
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as handle:
            path=Path(handle.name)
        output=path.with_suffix('.json')
        try:
            with wave.open(str(path),'wb') as target:
                target.setnchannels(1); target.setsampwidth(2); target.setframerate(16000)
                target.writeframes(np.clip(np.asarray(audio)*32768,-32768,32767).astype('<i2').tobytes())
            command=[self.executable,'-m',self.model,'-f',str(path),'-oj','-of',str(path.with_suffix('')),
                '--max-context','0','--temperature',str(temperature),'--temperature-inc','0','--no-fallback',
                '--beam-size',str(beam_size),'--language',language or 'auto']
            if hotwords: command += ['--prompt',hotwords]
            process=subprocess.run(command,capture_output=True,text=True,timeout=300)
            if process.returncode:
                raise RuntimeError(f'whisper.cpp exited {process.returncode}: {process.stderr[-1200:]}')
            data=json.loads(output.read_text(encoding='utf-8'))
            rows=data if isinstance(data,list) else data.get('transcription',data.get('segments',[]))
            if not isinstance(rows,list): raise ValueError('whisper.cpp returned invalid segment data')
            segments=[]
            for row in rows:
                if not isinstance(row,dict): raise ValueError('whisper.cpp returned invalid segment')
                offsets=row.get('offsets')
                start=_seconds(offsets.get('from'),1000) if isinstance(offsets,dict) else _seconds(row.get('start'))
                end=_seconds(offsets.get('to'),1000) if isinstance(offsets,dict) else _seconds(row.get('end'))
                segments.append(SimpleNamespace(start=start,end=end,text=str(row.get('text') or ''),words=None))
            if not rows and isinstance(data,dict) and data.get('text'):
                segments.append(SimpleNamespace(start=None,end=None,text=str(data['text']),words=None))
            # Segment timestamps and token offsets do not establish word alignment.
            return iter(segments),SimpleNamespace(language=language,transcription_options=None)
        finally:
            path.unlink(missing_ok=True)
            output.unlink(missing_ok=True)
