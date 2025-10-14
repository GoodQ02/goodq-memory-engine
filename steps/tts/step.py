from __future__ import annotations
from typing import Any, Dict, Optional

import os
import tempfile
import requests
import subprocess
from goodq4all.steps.common.tool_paths import resolve_piper


def _resolve_elevenlabs_voice_id(api_key: str) -> Optional[str]:
    try:
        r = requests.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": api_key},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json() or {}
        voices = data.get("voices") or []
        return (voices[0].get("voice_id") if voices else None)
    except Exception as e:
        print(f'[WARN] _resolve_elevenlabs_voice_id returning None')
        return None


def _elevenlabs_tts(text: str, voice_id: str, api_key: str) -> Optional[str]:
    if not voice_id:
        voice_id = _resolve_elevenlabs_voice_id(api_key) or ""
        if not voice_id:
            print(f'[WARN] _elevenlabs_tts returning None')
            return None
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
        headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
        payload = {"text": text, "model_id": "eleven_multilingual_v2"}
        r = requests.post(url, headers=headers, json=payload, stream=True, timeout=30)
        r.raise_for_status()
        fd, path = tempfile.mkstemp(suffix=".wav")
        with os.fdopen(fd, "wb") as f:
            for chunk in r.iter_content(4096):
                if chunk:
                    f.write(chunk)
        return path
    except Exception as e:
        print(f'[WARN] _elevenlabs_tts returning None')
        return None


def _piper_tts(text: str, piper_exe: str, voice_path: str, out_dir: str) -> Optional[str]:
    try:
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "goodq_tts.wav")
        cmd = [piper_exe, "-m", voice_path, "-f", out_path]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert proc.stdin is not None
        proc.stdin.write(text.encode("utf-8"))
        proc.stdin.close()
        proc.wait(timeout=30)
        return out_path if os.path.isfile(out_path) else None
    except Exception as e:
        print(f'[WARN] _piper_tts returning None')
        return None


def tts_speak(chat: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    text = chat.get("text")
    if not isinstance(text, str) or not text.strip():
        return {"status": "no_text"}

    tts_cfg = cfg.get("config", {}).get("tts", {})
    engine = tts_cfg.get("engine", "piper")

    if engine == "elevenlabs":
        api_key = os.getenv("ELEVENLABS_API_KEY", "")
        voice_id = (
            os.getenv("ELEVENLABS_VOICE_ID")
            or os.getenv("elevenlabs_voice_id")
            or tts_cfg.get("voice_id", "")
        )
        path = _elevenlabs_tts(text, voice_id, api_key) if api_key and voice_id else None
        return {"status": "ok" if path else "failed", "path": path, "engine": engine}

    # default piper
    piper_exe, voice_path, out_dir = resolve_piper(cfg)
    path = _piper_tts(text, piper_exe, voice_path, out_dir)
    return {"status": "ok" if path else "failed", "path": path, "engine": "piper"}
