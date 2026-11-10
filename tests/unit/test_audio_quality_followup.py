import json
import pytest


def test_active_async_video_caller_passes_vocabulary(monkeypatch, tmp_path):
    import asyncio
    from cli import run_ingestion as runner
    from steps.audio import audio_wsl2_bridge as bridge
    wav = tmp_path / "clip.wav"
    wav.write_bytes(b"fixture")
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"audio": {"transcribe": {"vocabulary": ["Joe"]}}}))
    monkeypatch.setattr(runner, "_extract_audio_chunk", lambda *a, **kw: wav)
    for name in ("_log_audio_to_ucf_ledger", "log_step_run", "_record_run_warning"):
        monkeypatch.setattr(runner, name, lambda *a, **kw: None)
    calls = []
    def worker(*args, **kwargs):
        calls.append(kwargs)
        return {"status": "success", "transcript": "Joe says hello.", "segments": []}
    async def step(*args, **kwargs):
        return {"status": "ok", "outputs": {}}
    monkeypatch.setattr(bridge, "audio_unified_wsl2", worker)
    monkeypatch.setattr(runner, "_run_step_async", step)
    async def run():
        return await runner._process_audio_async(cfg, "ffmpeg", wav,
            {"index": 0, "start": 0., "end": 5.}, tmp_path, tmp_path / "artifacts", "v", "s",
            asyncio.Lock(), asyncio.Lock(), audio_runtime_contract={"selected": "wsl", "reason": "test"},
            wsl_audio_lock=asyncio.Lock())
    asyncio.run(run())
    assert calls[0]["transcription_vocabulary"] == ["Joe"]
    assert calls[0]["transcription_temperature"] == 0.0


def test_step_dispatch_preserves_explicit_vocabulary(monkeypatch):
    from cli.step_runner import run_step
    from steps.audio import audio_wsl2_bridge as bridge
    calls = []
    monkeypatch.setattr(bridge, "audio_unified_wsl2", lambda *a, **kw: calls.append(kw) or {})
    run_step("audio_unified_wsl2", {"audio_path": "clip.wav", "duration": 4},
             {"audio": {"transcribe": {"vocabulary": ["Joe", "Ana Guttman"], "temperature": 0.2}}})
    assert calls[0]["transcription_vocabulary"] == ["Joe", "Ana Guttman"]
    assert calls[0]["transcription_temperature"] == 0.2


def test_unified_bridge_keeps_vocabulary_provenance(monkeypatch):
    from steps.audio import audio_wsl2_bridge as bridge
    context = {"status": "applied", "words": ["Joe"], "identity_claim": False}
    class Runner:
        def process_audio(self, path, **kwargs):
            assert kwargs["transcription_vocabulary"] == ["Joe"]
            return {"status": "success", "transcription": "Joe says hello.",
                    "transcription_status": "success", "transcription_context": context}
    monkeypatch.setattr(bridge, "WSL2AudioBridge", Runner)
    result = bridge.audio_unified_wsl2("clip.wav", transcription_vocabulary=["Joe"])
    assert result["transcript_meta"]["transcription_context"] == context


@pytest.mark.parametrize("value", ["Joe", [1], [""], ["x" * 65], ["Joe"] * 33])
def test_vocabulary_rejects_malformed_or_excessive_input(value):
    from wsl2_audio.process_audio import _normalize_transcription_vocabulary
    with pytest.raises(ValueError):
        _normalize_transcription_vocabulary(value)


def test_vocabulary_deduplicates_without_inventing_names():
    from wsl2_audio.process_audio import _normalize_transcription_vocabulary
    assert _normalize_transcription_vocabulary([" Joe ", "joe", "Ana Guttman"]) == ["Joe", "Ana Guttman"]
    assert _normalize_transcription_vocabulary(None) == []


def test_vocabulary_configuration_is_supported_by_strict_schema():
    from scripts.config_schema import AudioConfig, GoodQConfig
    from steps.audio.audio_wsl2_bridge import unified_transcription_options
    assert GoodQConfig.model_fields['audio'].annotation is not None
    cfg = AudioConfig.model_validate({'transcribe': {'vocabulary': ['Joe']}})
    assert unified_transcription_options({'audio': cfg.model_dump()}) == {
        'transcription_vocabulary': ['Joe'], 'transcription_temperature': 0.0}
    assert unified_transcription_options({'audio': None}) == {'transcription_temperature': 0.0}
    with pytest.raises(ValueError):
        AudioConfig.model_validate({'transcribe': {'vocabulary': ['Joe'] * 33}})
    with pytest.raises(ValueError):
        AudioConfig.model_validate({'transcribe': {'vocabulary': ['']}})
    with pytest.raises(ValueError):
        AudioConfig.model_validate({'transcribe': {'unknown': True}})


def test_summary_receives_distribution_instead_of_only_winning_label(monkeypatch):
    from steps.video import cross_modal_harmonizer as h
    from steps.common.context_analyzer_llm import _build_scene_context_prompts
    segment = {"scene_id": "s", "start": 0, "end": 3, "content_state": "signal", "full_transcript": "Yay Joe!",
        "emotion_segments": [{"start": 0, "end": 2, "speaker": "A", "label": "disgust",
                              "scores": {"disgust": .36, "sad": .33, "happy": .31}}],
        "transcript_meta": {"transcription_context": {"status": "applied", "words": ["Joe"], "identity_claim": False}}}
    captured = []
    monkeypatch.setattr(h, "analyze_scene_context_llm", lambda meta, cfg, **kw: captured.append(meta))
    h._apply_scene_context_llm([segment], {"s": {"index": 0, "audio": {}}},
        {"llm": {"features": {"scene_context_analysis": True}}})
    _, prompt = _build_scene_context_prompts(captured[0])
    assert '"disgust": 0.36' in prompt and '"sad": 0.33' in prompt
    assert '"identity_claim": false' in prompt
    assert "uncalibrated" in prompt
