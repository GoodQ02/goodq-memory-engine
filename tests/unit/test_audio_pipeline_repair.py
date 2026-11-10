import asyncio
import os
import pytest

from steps.audio_speaker_merge.step import audio_speaker_merge


@pytest.mark.parametrize("case", ["bounded", "duplicate", "out_of_bounds", "weak"])
def test_alignment_recovery_requires_unique_bounded_evidence(case):
    from wsl2_audio.process_audio import _recover_word_timing
    word = {"text": "Yay!", "start": None, "end": None, "raw_start": 2., "raw_end": 2.,
            "timing_status": "invalid_model_alignment"}
    segments = [{"start": 1., "end": 2., "text": "Yay!", "words": [word]},
                {"start": 3., "end": 4., "words": [{"text": "next", "start": 3., "end": 4.}]}]
    candidate = {"text": "Yay,", "start": 1.5, "end": 2.2, "probability": .95}
    if case == "out_of_bounds": candidate["end"] = 3.5
    if case == "weak": candidate["probability"] = .1
    alternatives = [{"words": [candidate] * (2 if case == "duplicate" else 1)}]
    receipt = _recover_word_timing(segments, alternatives)
    assert receipt["recovered_words"] == int(case == "bounded")
    assert word["text"] == "Yay!" and word["raw_start"] == word["raw_end"] == 2.
    if case == "bounded":
        assert word["end"] == segments[0]["end"] == 2.2
        assert word["timing_review_status"] == "unreviewed"
    else:
        assert word["start"] is None


def test_word_turns_split_speakers_and_retain_unaligned_text():
    words = [{"start": 0, "end": .5, "text": "Hello"},
             {"start": .6, "end": 1, "text": "there"},
             {"start": None, "end": None, "text": "Yay!"}]
    result = audio_speaker_merge({"segments": [{"start": 0, "end": 2, "text": "Hello there Yay!", "words": words}],
        "diarization": [{"start": 0, "end": .5, "speaker": "A"}, {"start": .6, "end": 2, "speaker": "B"}]}, {})
    turns = result["speaker_transcript"]
    assert [t["speaker"] for t in turns] == ["A", "B", None]
    assert " ".join(t["text"] for t in turns) == "Hello there Yay!"
    assert turns[-1]["timing_scope"] == "containing_segment"
    assert turns[-1]["words"][0]["start"] is None


def test_overlapping_words_have_no_forced_speaker():
    turns = audio_speaker_merge({"segments": [{"start": 0, "end": 1,
        "words": [{"start": .1, "end": .5, "text": "Yes"}]}],
        "diarization": [{"start": 0, "end": 1, "speaker": s} for s in ("A", "B")]}, {})["speaker_transcript"]
    assert turns[0]["speaker"] is None
    assert turns[0]["speaker_candidates"] == ["A", "B"]


def test_summary_keeps_overlap_attribution_evidence():
    from steps.common.context_analyzer_llm import _build_scene_context_prompts
    merged=audio_speaker_merge({'segments':[{'start':0.,'end':1.,'text':'Yay!'}],
        'diarization':[{'start':0.,'end':1.,'speaker':s} for s in ('A','B')]}, {})
    _, prompt=_build_scene_context_prompts({'transcript':'Yay!',**merged})
    assert '"attribution_reason": "overlapping_speakers"' in prompt
    assert '"overlap_intervals": [{"start": 0.0, "end": 1.0' in prompt
    assert 'Speaker candidates are not confirmed people' in prompt


def test_sound_only_scene_reaches_summary_without_becoming_emotion(monkeypatch):
    from steps.video import cross_modal_harmonizer as h
    calls=[]
    monkeypatch.setattr(h,'analyze_scene_context_llm',lambda meta,cfg,**kw:calls.append(meta))
    sound={'label':'crying','start':0.,'end':2.,'status':'model_detected'}
    segment={'scene_id':'s','start':0.,'end':2.,'content_state':'signal',
             'full_transcript':'','sound_events':[sound],'emotion_segments':[]}
    h._apply_scene_context_llm([segment],{'s':{'index':0,'audio':{}}},
                              {'llm':{'features':{'scene_context_analysis':True}}})
    assert len(calls)==1 and calls[0]['sound_events']==[sound]
    assert calls[0]['emotion_segments']==[] and calls[0]['emotions']==[]


def test_offline_sentiment_attempts_cached_model_and_discloses_failure(monkeypatch):
    from steps.sentiment import step
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    attempted = []
    monkeypatch.setattr(step, "_load", lambda device: attempted.append(device) or False)
    monkeypatch.setattr(step, "_preferred_device", lambda: "cpu")
    monkeypatch.setitem(step._SENT, "load_error", "missing local snapshot")
    result = step.sentiment({"transcript": "Some ordinary words."}, {"ingestion_isolation": True})
    assert attempted == ["cpu"]
    assert result["sentiment_meta"]["status"] == "fallback"
    assert result["sentiment_meta"]["error"] == "missing local snapshot"


def test_short_phrase_assessed_without_nearby_crying_veto(monkeypatch):
    import torch
    from wsl2_audio import acoustic_events as step
    raw = {"diarization_status": "success", "diarization": [{"start": 0, "end": 4, "speaker": "A"}],
           "word_timestamps": [{"text": "Hello", "start": 1, "end": 1.5, "probability": .95}]}
    def detect(*args, speech_intervals, **kwargs):
        assert speech_intervals == [{"start": 1., "end": 1.5, "speaker": "A", "word_count": 1}]
        return [{"label": "crying", "start": 0, "end": 4}], {
            "status": "success", "windows": [{"start": 0, "end": 4, "excluded_labels": ["crying"]}],
            "speech_presence": {"status": "success", "method": "silero_vad"},
            "speech_windows": [{"start": 1, "end": 1.5, "speech_score": .95,
                                "vad_speech_coverage": 1., "excluded_labels": []}]}
    monkeypatch.setattr(step, "detect_sound_events", detect)
    result = step.prepare_inputs(torch.zeros(1, 64000), 16000, raw, cache_dir=None, device="cpu")
    assert result["emotion_input"]["selected_seconds"] == .5
    assert result["sound_events"][0]["label"] == "crying"


def test_sentiment_fallback_retains_inference_failure(monkeypatch):
    from steps.sentiment import step
    monkeypatch.setattr(step, "_load", lambda *_: True)
    monkeypatch.setattr(step, "_preferred_device", lambda: "cpu")
    def failed_tokenizer(*args, **kwargs):
        raise ValueError("invalid model input")
    monkeypatch.setitem(step._SENT, "tok", failed_tokenizer)
    monkeypatch.setitem(step._SENT, "device", "cpu")
    result = step.sentiment({"transcript": "Some ordinary words."}, {"ingestion_isolation": True})
    assert result["sentiment_meta"]["reason"] == "inference_failed"
    assert result["sentiment_meta"]["error"] == "ValueError: invalid model input"


def test_summary_caller_receives_separate_channels(monkeypatch):
    from steps.video import cross_modal_harmonizer as h
    from steps.common.context_analyzer_llm import _build_scene_context_prompts
    segment = {"scene_id": "s", "start": 0, "end": 3, "content_state": "signal", "full_transcript": "Yay Joe!",
               "text_emotion_ranking": [{"label": "joy", "score": .9}],
               "sound_events": [{"label": "crying", "start": 1, "end": 2}],
               "emotion_segments": [], "sentiment": {"label": "POSITIVE", "score": .8}}
    captured = []
    monkeypatch.setattr(h, "analyze_scene_context_llm", lambda meta, cfg, **kw: captured.append(meta))
    h._apply_scene_context_llm([segment], {"s": {"index": 0, "audio": {}}},
        {"llm": {"features": {"scene_context_analysis": True}}})
    assert captured[0]["text_emotion_ranking"] == segment["text_emotion_ranking"]
    assert captured[0]["sound_events"] == segment["sound_events"]
    assert captured[0]["emotions"] == []
    _, prompt = _build_scene_context_prompts(captured[0])
    assert "not evidence of neutral mood" in prompt and '"label": "joy"' in prompt


def test_summary_caller_preserves_transcription_coverage_limits(monkeypatch):
    from steps.video import cross_modal_harmonizer as h
    from steps.common.context_analyzer_llm import _build_scene_context_prompts
    coverage = {'policy': 'source_regions_v1', 'status': 'completed', 'detected_region_count': 2,
        'completed_region_count': 2, 'regions_without_text': 1, 'recognition_accuracy': 'unverified',
        'regions': [{'start': 10, 'end': 11, 'outcome': 'no_text_returned', 'quality_flags': []},
                    {'start': 20, 'end': 21, 'outcome': 'text_returned',
                     'quality_flags': ['compression_ratio_threshold_exceeded']}]}
    segment = {'scene_id': 's', 'start': 0, 'end': 30, 'content_state': 'signal', 'full_transcript': 'unverified repetition',
        'transcript_meta': {'transcription_decoding': {'source_regions': coverage}}}
    captured = []
    monkeypatch.setattr(h, 'analyze_scene_context_llm', lambda meta, cfg, **kw: captured.append(meta))
    h._apply_scene_context_llm([segment], {'s': {'index': 0, 'audio': {}}},
        {'llm': {'features': {'scene_context_analysis': True}}})
    assert captured[0]['transcription_coverage'] == coverage
    _, prompt = _build_scene_context_prompts(captured[0])
    assert 'source_regions_v1' in prompt and 'no_text_returned' in prompt
    assert 'compression_ratio_threshold_exceeded' in prompt
    assert 'does not prove that every word was recognized' in prompt


@pytest.mark.parametrize("transcript", ["Yay!", "Please say hello to the camera over here today."])
def test_audio_evidence_reaches_summary_instead_of_monologue_shortcut(transcript):
    import json
    from steps.common.context_analyzer_llm import analyze_scene_context_llm
    calls = []

    class Client:
        last_model_used = None
        last_provider_used = "fixture"

        def chat(self, **kwargs):
            calls.append(kwargs)
            return {"choices": [{"message": {"content": json.dumps({
                "narrative_summary": "Speech is audible.", "key_moments": [],
                "emotional_arc": "", "context_tags": [], "activity_description": "Speech is audible.",
            })}}]}

    result = analyze_scene_context_llm({"transcript": transcript,
        "sound_events": [{"label": "crying", "start": 4, "end": 5}]}, {}, llm_client=Client())
    assert len(calls) == 1
    assert '"label": "crying"' in calls[0]["messages"][1]["content"]
    assert result["reason"] == "model_output"


@pytest.mark.parametrize('text,outcome,flags', [
    ('', 'no_text_returned', []),
    ('We went on a vacation vacation vacation vacation vacation.', 'text_returned', ['compression_ratio_threshold_exceeded']),
])
def test_summary_uncertainty_survives_heuristics_and_unavailable_llm(text, outcome, flags):
    from steps.common.context_analyzer_llm import analyze_scene_context_llm
    meta = {'transcript': text, 'transcription_coverage': {'policy': 'source_regions_v1',
        'status': 'completed', 'regions': [{'outcome': outcome, 'quality_flags': flags}]}}
    result = analyze_scene_context_llm(meta, {}, llm_client=None)
    assert result['status'] == 'fallback'
    assert result['reason'] == 'llm_client_unavailable'
    assert result.get('transcription_coverage_uncertain') is True
    assert 'uncertain' in result['narrative_summary'].lower()
    assert 'vacation' not in result['narrative_summary'].lower()
    calls = []
    class Client:
        def chat(self, **kwargs):
            calls.append(kwargs)
            return {'choices': [{'message': {'content': '{}'}}]}
    analyze_scene_context_llm(meta, {}, llm_client=Client())
    assert len(calls) == 1
    assert '"warning_region_count": 1' in calls[0]['messages'][1]['content']


def test_valid_summary_output_cannot_reintroduce_warned_transcript_topics():
    import json
    from steps.common.context_analyzer_llm import analyze_scene_context_llm
    class Client:
        last_model_used = None
        last_provider_used = 'fixture'
        def chat(self, **kwargs):
            return {'choices': [{'message': {'content': json.dumps({
                'narrative_summary': 'Speech recognition is uncertain; review the source audio.',
                'key_moments': [], 'emotional_arc': 'unqualified', 'context_tags': [],
                'activity_description': 'Speech recognition requires source review.',
            })}}]}
    result = analyze_scene_context_llm({'transcript': 'We went on a vacation vacation vacation vacation vacation.',
        'transcription_coverage': {'status': 'completed', 'regions': [{'outcome': 'text_returned',
            'quality_flags': ['compression_ratio_threshold_exceeded']}]}}, {}, llm_client=Client())
    assert result.get('transcription_coverage_uncertain') is True
    assert 'uncertain' in result['narrative_summary'].lower()
    assert 'vacation' not in json.dumps(result).lower()


def test_audio_coverage_warning_preserves_independent_visual_summary():
    from steps.common.context_analyzer_llm import _normalize_scene_context_payload
    result = _normalize_scene_context_payload({
        'narrative_summary': 'A person opens a wooden door.', 'key_moments': ['A person opens a wooden door'],
        'emotional_arc': '', 'context_tags': [], 'activity_description': 'A person opens a wooden door.',
    }, {'caption': 'A person opens a wooden door.', 'transcript': 'vacation vacation vacation',
        'transcription_coverage': {'status': 'error', 'regions': []}})
    assert 'wooden door' in result['narrative_summary']
    assert 'uncertain' in result['narrative_summary']
    assert result['claim_provenance']['narrative_summary']['depends_on'] == ['image_caption']


def test_async_fallback_keeps_parent_policy_and_enriches_before_index(monkeypatch, tmp_path):
    from cli import run_ingestion as runner
    wav = tmp_path / "clip.wav"
    wav.write_bytes(b"fixture")
    cfg = tmp_path / "config.json"
    cfg.write_text("{}")
    monkeypatch.setenv("GOODQ_REQUIRE_WSL_AUDIO", "1")
    monkeypatch.setattr(runner, "_extract_audio_chunk", lambda *a, **kw: wav)
    for name in ("_log_audio_to_ucf_ledger", "log_step_run", "_record_run_warning"):
        monkeypatch.setattr(runner, name, lambda *a, **kw: None)
    calls = []
    async def run_step(env, name, item, cfg, **kwargs):
        calls.append(name)
        await asyncio.sleep(0)
        assert os.environ["GOODQ_REQUIRE_WSL_AUDIO"] == "1"
        if name == "audio_transcribe_local":
            assert kwargs["_step_env_overrides"] == {"GOODQ_REQUIRE_WSL_AUDIO": "0"}
            return {"status": "ok", "step_name": "audio_transcribe_local", "outputs": {"transcript": "Hello world"}}
        if name == "text_embed":
            assert "sentiment" in calls and "audio_speaker_merge" in calls
        if name == "emotion_classify":
            return {"status": "skipped", "outputs": {"emotion_meta": {
                "status": "unavailable", "reason": "model_not_cached"}}}
        return {"status": "ok", "outputs": {}}
    monkeypatch.setattr(runner, "_run_step_async", run_step)
    async def run():
        return await runner._process_audio_async(cfg, "ffmpeg", tmp_path / "video.mp4",
            {"index": 0, "start": 0., "end": 5.}, tmp_path, tmp_path / "artifacts", "v", "s",
            asyncio.Lock(), asyncio.Lock(), audio_runtime_contract={"selected": "windows", "reason": "test"})
    result = asyncio.run(run())
    assert result["data"]["emotion_meta"] == {"status": "unavailable", "reason": "model_not_cached"}
    assert "text_embed" in calls
