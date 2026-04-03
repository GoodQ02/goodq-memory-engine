from __future__ import annotations

from steps.common.tool_paths import resolve_piper


def test_resolve_piper_prefers_env_and_top_level_tts(monkeypatch):
    cfg = {
        "tts": {
            "piper_exe": "C:/Tools/piper/piper.exe",
            "voice_path": "C:/Tools/piper/voices/en_US-joe-medium/en_US-joe-medium.onnx",
            "out_dir": "L:/_DATA/GoodQ_Data/tts",
        },
        "config": {
            "tools": {
                "piper_exe": "ignored.exe",
                "piper_voice": "ignored.onnx",
            }
        },
    }

    exe, voice, out_dir = resolve_piper(cfg)
    assert exe == "C:/Tools/piper/piper.exe"
    assert voice == "C:/Tools/piper/voices/en_US-joe-medium/en_US-joe-medium.onnx"
    assert out_dir == "L:/_DATA/GoodQ_Data/tts"

    monkeypatch.setenv("GOODQ_PIPER_EXE", "C:/override/piper.exe")
    monkeypatch.setenv("GOODQ_PIPER_VOICE_PATH", "C:/override/voice.onnx")
    monkeypatch.setenv("GOODQ_PIPER_OUT_DIR", "C:/override/out")

    exe, voice, out_dir = resolve_piper(cfg)
    assert exe == "C:/override/piper.exe"
    assert voice == "C:/override/voice.onnx"
    assert out_dir == "C:/override/out"
