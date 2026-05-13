from __future__ import annotations

from steps.common.tool_paths import resolve_piper


def test_resolve_piper_prefers_env_and_top_level_tts(monkeypatch):
    monkeypatch.delenv("GOODQ_PIPER_EXE", raising=False)
    monkeypatch.delenv("GOODQ_PIPER_VOICE_PATH", raising=False)
    monkeypatch.delenv("GOODQ_PIPER_OUT_DIR", raising=False)

    cfg = {
        "tts": {
            "piper_exe": "tools/piper/piper.exe",
            "voice_path": "tools/piper/voices/en_US-joe-medium/en_US-joe-medium.onnx",
            "out_dir": "data/tts",
        },
        "config": {
            "tools": {
                "piper_exe": "ignored.exe",
                "piper_voice": "ignored.onnx",
            }
        },
    }

    exe, voice, out_dir = resolve_piper(cfg)
    assert exe == "tools/piper/piper.exe"
    assert voice == "tools/piper/voices/en_US-joe-medium/en_US-joe-medium.onnx"
    assert out_dir == "data/tts"

    monkeypatch.setenv("GOODQ_PIPER_EXE", "override/piper.exe")
    monkeypatch.setenv("GOODQ_PIPER_VOICE_PATH", "override/voice.onnx")
    monkeypatch.setenv("GOODQ_PIPER_OUT_DIR", "override/out")

    exe, voice, out_dir = resolve_piper(cfg)
    assert exe == "override/piper.exe"
    assert voice == "override/voice.onnx"
    assert out_dir == "override/out"
