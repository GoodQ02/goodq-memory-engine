from __future__ import annotations

import copy

import pytest


@pytest.mark.parametrize('legacy', [True, False])
def test_actual_transcription_callers_separate_words_from_segments(monkeypatch, legacy):
    from steps.audio import audio_wsl2_bridge as bridge
    segment = dict(start=0, end=4, text='hello family')
    words = [dict(start=.5,end=.9,text='hello',timing_status='aligned'),
             dict(start=1,end=1.6,text='family',timing_status='aligned')]
    raw = {'status':'success','transcription_status':'success','transcription':'hello family',
           'word_timestamps':[segment] if legacy else words}
    if not legacy:
        raw.update(segments=[segment], word_alignment={'status':'available','words':words,
            'timebase':'input_audio_seconds','review_status':'unreviewed'})
    class Worker:
        def process_audio(self, *a, **kw): return raw
    monkeypatch.setattr(bridge, 'WSL2AudioBridge', Worker)
    unified = bridge.audio_unified_wsl2('family.wav', duration=4)
    transcript = bridge.audio_transcribe_wsl2('family.wav')
    # An old worker may still expose diagnostic text, but cannot pass admission
    # without the coverage/decoding receipt requested by this retained caller.
    assert transcript['status'] == 'error'
    assert transcript['bridge_error_reason'] == 'transcription_policy_unconfirmed'
    assert unified['segments'] == transcript['segments'] == [segment]
    assert unified['word_timestamps'] == transcript['words'] == ([] if legacy else words)
    assert unified['transcript_meta']['word_alignment'] == raw.get('word_alignment')


@pytest.mark.parametrize("fault", [None, "unknown", "failed", "words", "tracks", "scores", "emotion_error", "diarization_error"])
def test_speech_enrichment_absence_requires_consistent_worker_evidence(monkeypatch, fault):
    from steps.audio import audio_wsl2_bridge as bridge
    raw = {"status": "success", "transcription_status": "success", "transcription": "",
           "speech_detection": {"status": "completed", "method": "silero_vad",
                                "input_duration_seconds": 5, "speech_duration_seconds": 0},
           "diarization_status": "not_applicable", "diarization_note": "no_speech_detected",
           "emotion_status": "not_applicable", "emotion_note": "no_speech_detected",
           "speakers": [], "speaker_count": 0, "diarization": [], "emotion": None, "emotion_scores": {}}
    if fault == "unknown": raw.pop("speech_detection")
    if fault == "failed": raw["transcription_error"] = "decoder failed"
    if fault == "words": raw["transcription"] = "spoken words"
    if fault == "tracks": raw["diarization"] = [{"speaker": "SPEAKER_00", "start": 0, "end": 1}]
    if fault == "scores": raw["emotion_scores"] = {"sad": 0.9}
    if fault in {"emotion_error", "diarization_error"}: raw[fault] = "model failed"
    class Worker:
        def process_audio(self, *args, **kwargs): return raw
    monkeypatch.setattr(bridge, "WSL2AudioBridge", Worker)
    result = bridge.audio_unified_wsl2("control.wav", duration=5)
    outcomes = result["wsl_capability_outcomes"]
    for component, invalid in [("diarization", {"unknown", "failed", "words", "tracks", "diarization_error"}),
                               ("acoustic_emotion", {"unknown", "failed", "words", "scores", "emotion_error"})]:
        assert outcomes[component]["status"] == ("error" if fault in invalid else "not_applicable")
    assert result["emotion_note"] == result["diarization_note"] == "no_speech_detected"


@pytest.mark.parametrize('speech_seconds,expected', [(0.0, 'no_speech'), (2.0, 'no_intelligible_speech')])
def test_completed_speech_detection_survives_unified_caller(monkeypatch, speech_seconds, expected):
    from steps.audio import audio_wsl2_bridge
    from cli.run_ingestion import _derive_transcript_outcome

    evidence = {'status': 'completed', 'method': 'silero_vad', 'input_duration_seconds': 5.0,
                'speech_duration_seconds': speech_seconds}
    class Bridge:
        def process_audio(self, *args, **kwargs):
            return {'status': 'success', 'transcription': '', 'transcription_status': 'success',
                    'speech_detection': evidence, 'whisper_model': 'medium'}
    monkeypatch.setattr(audio_wsl2_bridge, 'WSL2AudioBridge', Bridge)
    result = audio_wsl2_bridge.audio_unified_wsl2('sample.wav', duration=5)
    assert result['transcript_meta']['speech_detection'] == evidence
    assert result['transcript_outcome'] == expected
    capability = result['wsl_capability_outcomes']['transcription']
    assert capability['status'] == ('not_applicable' if speech_seconds == 0 else 'skipped')
    scene = _derive_transcript_outcome({'data': result}, audio_error=None, audio_backend_fields={})
    assert scene['transcript_outcome'] == expected


@pytest.mark.parametrize('evidence', [None, {}, {'status': 'failed'},
    {'status': 'completed', 'method': 'silero_vad', 'input_duration_seconds': 0, 'speech_duration_seconds': 0},
    {'status': 'completed', 'method': 'silero_vad', 'input_duration_seconds': 5, 'speech_duration_seconds': float('nan')},
    {'status': 'completed', 'method': 'silero_vad', 'input_duration_seconds': 5, 'speech_duration_seconds': -1}])
def test_empty_transcript_without_valid_detection_stays_unclassified(evidence):
    from steps.audio.audio_wsl2_bridge import _build_wsl_capability_outcomes
    outcome = _build_wsl_capability_outcomes({'transcription_status': 'success', 'speech_detection': evidence})['transcription']
    assert outcome['status'] == 'skipped'
    assert outcome['transcript_outcome'] == 'unclassified'


@pytest.mark.parametrize('status', ['error', 'success'])
def test_failed_transcription_cannot_be_closed_by_detection(status):
    from steps.audio.audio_wsl2_bridge import _build_wsl_capability_outcomes
    outcome = _build_wsl_capability_outcomes({'transcription_status': status, 'transcription_error': 'decoder failed',
        'speech_detection': {'status': 'completed', 'method': 'silero_vad', 'input_duration_seconds': 5, 'speech_duration_seconds': 0}})['transcription']
    assert outcome['status'] == 'error'
    assert outcome['error'] == 'decoder failed'


@pytest.mark.parametrize('probability,expected', [(0.91,'not_applicable'),(0.3,'skipped'),(float('nan'),'skipped'),(1.2,'skipped')])
def test_whisper_no_speech_receipt_requires_rejected_candidate_evidence(probability, expected):
    from steps.audio.audio_wsl2_bridge import _build_wsl_capability_outcomes
    result = {'transcription_status':'success','transcription':'', 'transcription_quality': {
        'status':'completed','rule':'whisper_no_speech_threshold','threshold':0.6,
        'decoded_segment_count':1,'accepted_segment_count':0,
        'rejected_segments':[{'text':'arbitrary candidate','no_speech_probability':probability}]}}
    outcome = _build_wsl_capability_outcomes(result)['transcription']
    assert outcome['status'] == expected
    if expected == 'not_applicable': assert outcome['basis'] == 'whisper_no_speech_probability'


@pytest.mark.parametrize("text,status,expected", [
    ("", "success", "skipped"),
    ("hello", "success", "ok"),
    ("", "failed", "error"),
])
def test_unified_transcript_classification_matches_scene_truth(monkeypatch, text, status, expected):
    from steps.audio import audio_wsl2_bridge
    from cli.run_ingestion import _derive_transcript_outcome

    class Bridge:
        def process_audio(self, *args, **kwargs):
            return {"status": "success", "transcription": text,
                    "transcription_status": status, "segments": []}

    monkeypatch.setattr(audio_wsl2_bridge, "WSL2AudioBridge", Bridge)
    result = audio_wsl2_bridge.audio_unified_wsl2("disposable.wav", duration=10)
    capability = result["wsl_capability_outcomes"]["transcription"]
    assert capability["status"] == expected
    scene = _derive_transcript_outcome({"data": result}, audio_error=None,
                                      audio_backend_fields={"audio_backend_effective": "wsl"})
    if expected == "skipped":
        assert capability["transcript_outcome"] == scene["transcript_outcome"] == "unclassified"
        assert capability["reason"] == scene["transcript_outcome_reason"] == "worker_success_empty_transcript"
    elif expected == "ok":
        assert scene["transcript_outcome"] == "transcript_available"
    else:
        assert scene["transcript_outcome"] == "runtime_failure"


def test_audio_unified_wsl2_bounds_observed_turn_before_materialization(monkeypatch):
    from steps.audio import audio_wsl2_bridge

    # Fresh recurrence-run-003: model tail plus scene offset exceeded media EOF.
    raw = [{'start': 0.03096875, 'end': 4.03034375, 'speaker': 'SPEAKER_00'}]
    before = copy.deepcopy(raw)

    class _Bridge:
        def process_audio(self, audio_path, timeout=None, audio_duration=None):
            assert audio_duration == 3.98
            return {'status': 'success', 'diarization': raw}

    monkeypatch.setattr(audio_wsl2_bridge, 'WSL2AudioBridge', _Bridge)
    result = audio_wsl2_bridge.audio_unified_wsl2('scene.wav', duration=3.98)
    turn = result['speaker_segments'][0]
    assert turn['start'] == 0.03096875
    assert turn['end'] == 3.98
    assert turn['speaker'] == 'SPEAKER_00'
    assert turn['timing_adjustment'] == {
        'reason': 'caller_clip_bounds', 'original_start': 0.03096875,
        'original_end': 4.03034375, 'clip_duration': 3.98,
    }
    assert result['diarization'] == result['speaker_segments']
    assert raw == before
    assert 10.001 + turn['end'] <= 13.980633333333333 + 0.05


@pytest.mark.parametrize('start,end', [(4.0, 5.0), (-2.0, -1.0), (1.0, 1.0),
                                     (float('nan'), 2.0), (0.0, float('inf'))])
def test_audio_unified_wsl2_rejects_invalid_turns(monkeypatch, start, end):
    from steps.audio import audio_wsl2_bridge

    class _Bridge:
        def process_audio(self, *args, **kwargs):
            return {'status': 'success', 'diarization': [{'start': start, 'end': end}]}

    monkeypatch.setattr(audio_wsl2_bridge, 'WSL2AudioBridge', _Bridge)
    with pytest.raises(ValueError, match='Diarization turn'):
        audio_wsl2_bridge.audio_unified_wsl2('scene.wav', duration=3.98)


def test_audio_unified_wsl2_preserves_valid_turns_and_records_negative_lead(monkeypatch):
    from steps.audio import audio_wsl2_bridge

    valid = {'start': 0.2, 'end': 2.0, 'speaker': 'SPEAKER_01'}

    class _Bridge:
        def process_audio(self, *args, **kwargs):
            return {'status': 'success', 'diarization': [
                {'start': -0.03, 'end': 0.1, 'speaker': 'SPEAKER_00'}, valid]}

    monkeypatch.setattr(audio_wsl2_bridge, 'WSL2AudioBridge', _Bridge)
    result = audio_wsl2_bridge.audio_unified_wsl2('scene.wav', duration=3.98)
    assert result['speaker_segments'][0]['start'] == 0.0
    assert result['speaker_segments'][0]['timing_adjustment']['original_start'] == -0.03
    assert result['speaker_segments'][1] == valid


def test_audio_unified_wsl2_success_preserves_bridge_runtime_probe(monkeypatch):
    from steps.audio import audio_wsl2_bridge

    runtime_probe = {
        "torch_lane_status": "differs_from_expected",
        "torchcodec_ready": False,
        "runtime_warnings": ["torchcodec_decoder_unavailable"],
    }

    class _Bridge:
        def process_audio(self, audio_path, timeout=None, audio_duration=None):  # noqa: ANN001
            return {
                "status": "success",
                "transcription": "hello there",
                "transcription_status": "success",
                "device": "cuda",
                "diarization_status": "success",
                "emotion_status": "success",
                "speaker_count": 1,
                "bridge_runtime_probe": runtime_probe,
            }

    monkeypatch.setattr(audio_wsl2_bridge, "WSL2AudioBridge", _Bridge)

    result = audio_wsl2_bridge.audio_unified_wsl2("scene_0001.wav", duration=12.0)

    assert result["status"] == "success"
    assert result["bridge_runtime_probe"] == runtime_probe


def test_audio_unified_wsl2_success_preserves_wav2vec_enrichment_fields(monkeypatch):
    from steps.audio import audio_wsl2_bridge

    class _Bridge:
        def process_audio(self, audio_path, timeout=None, audio_duration=None):  # noqa: ANN001
            return {
                "status": "success",
                "transcription": "hello there",
                "transcription_status": "success",
                "device": "cuda",
                "diarization_status": "success",
                "emotion": "calm",
                "emotion_scores": {"calm": 0.9},
                "emotion_status": "success",
                "emotion_note": "wav2vec_ready",
                "embeddings": [0.1, 0.2],
                "embedding_dim": 2,
                "embeddings_status": "success",
                "embeddings_note": "wav2vec_ready",
                "speaker_voice_signatures": [{"speaker": "SPEAKER_00", "embedding": [1.0]}],
                "speaker_voice_signature_meta": {"status": "ok", "emitted": 1},
            }

    monkeypatch.setattr(audio_wsl2_bridge, "WSL2AudioBridge", _Bridge)

    result = audio_wsl2_bridge.audio_unified_wsl2("scene_0001.wav", duration=12.0)

    assert result["emotion_status"] == "success"
    assert result["emotion_note"] == "wav2vec_ready"
    assert result["embeddings_status"] == "success"
    assert result["embeddings_note"] == "wav2vec_ready"
    assert result["speaker_voice_signature_meta"]["status"] == "ok"


def test_audio_unified_wsl2_exposes_five_independent_capability_outcomes(monkeypatch):
    from steps.audio import audio_wsl2_bridge

    class _Bridge:
        def process_audio(self, audio_path, timeout=None, audio_duration=None):  # noqa: ANN001
            return {
                "status": "success",
                "transcription": "hello there",
                "transcription_status": "success",
                "diarization": [
                    {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}
                ],
                "diarization_status": "success",
                "emotion": "calm",
                "emotion_scores": {"calm": 0.9},
                "emotion_status": "success",
                "embeddings": [0.1, 0.2],
                "embedding_dim": 2,
                "embeddings_status": "success",
            }

    monkeypatch.setattr(audio_wsl2_bridge, "WSL2AudioBridge", _Bridge)

    result = audio_wsl2_bridge.audio_unified_wsl2("scene_0001.wav", duration=12.0)

    outcomes = result["wsl_capability_outcomes"]
    assert set(outcomes) == {
        "transcription",
        "diarization",
        "acoustic_emotion",
        "wav2vec2",
        "clap_handoff",
    }
    assert all(outcomes[name]["status"] == "ok" for name in outcomes)
    assert outcomes["wav2vec2"]["embedding_dim"] == 2
    assert outcomes["clap_handoff"]["reason"] == "canonical_clap_required"
    assert outcomes["clap_handoff"]["required_step"] == "audio_embed_clap"


def test_audio_unified_wsl2_marks_missing_wav2vec_output_as_error(monkeypatch):
    from steps.audio import audio_wsl2_bridge

    class _Bridge:
        def process_audio(self, audio_path, timeout=None, audio_duration=None):  # noqa: ANN001
            return {
                "status": "success",
                "transcription": "hello there",
                "transcription_status": "success",
                "diarization": [],
                "diarization_status": "completed_no_speakers",
                "emotion": "calm",
                "emotion_scores": {"calm": 0.9},
                "emotion_status": "success",
                "embeddings": [],
                "embedding_dim": 768,
                "embeddings_status": "success",
            }

    monkeypatch.setattr(audio_wsl2_bridge, "WSL2AudioBridge", _Bridge)

    result = audio_wsl2_bridge.audio_unified_wsl2("scene_0001.wav", duration=12.0)

    assert result["status"] == "success"
    assert result["wsl_capability_outcomes"]["diarization"] == {
        "status": "not_applicable",
        "reason": "content_appropriate_empty",
        "raw_status": "completed_no_speakers",
    }
    assert result["wsl_capability_outcomes"]["wav2vec2"]["status"] == "error"
    assert (
        result["wsl_capability_outcomes"]["wav2vec2"]["reason"]
        == "successful_status_without_embedding"
    )


def test_audio_unified_wsl2_error_preserves_bridge_runtime_probe(monkeypatch):
    from steps.audio import audio_wsl2_bridge

    runtime_probe = {
        "torch_lane_status": "differs_from_expected",
        "torchcodec_ready": False,
        "runtime_warnings": ["torchcodec_decoder_unavailable"],
    }

    class _Bridge:
        def process_audio(self, audio_path, timeout=None, audio_duration=None):  # noqa: ANN001
            return {
                "status": "error",
                "error": "WSL audio processor failed",
                "bridge_error_reason": "wsl_subprocess_nonzero",
                "bridge_error_details": {"processor_diarization_status": "error"},
                "bridge_runtime_probe": runtime_probe,
            }

    monkeypatch.setattr(audio_wsl2_bridge, "WSL2AudioBridge", _Bridge)

    result = audio_wsl2_bridge.audio_unified_wsl2("scene_0001.wav", duration=12.0)

    assert result["status"] == "error"
    assert result["bridge_error_reason"] == "wsl_subprocess_nonzero"
    assert result["bridge_runtime_probe"] == runtime_probe
    assert result["wsl_capability_outcomes"]["clap_handoff"]["status"] == "error"
    assert (
        result["wsl_capability_outcomes"]["clap_handoff"]["reason"]
        == "wsl_composite_failed_before_clap_handoff"
    )

@pytest.mark.parametrize("retired", [True, False])
def test_whole_scene_retirement_bridge_preserves_other_audio_and_legacy_vectors(monkeypatch, retired):
    from steps.audio import audio_wsl2_bridge
    from cli import run_ingestion
    from lib.ingestion_capability_contract import build_capability_receipt
    raw = {"status": "success", "transcription": "fixture words", "transcription_status": "success",
           "emotion": "calm", "emotion_status": "success", "emotion_scores": {"calm": .9},
           "speaker_voice_signatures": [{"speaker": "speaker_0", "embedding": [.6, .8]}],
           "speaker_voice_signature_meta": {"status": "success"},
           "embeddings_status": "retired" if retired else "success"}
    if not retired:
        raw.update(embeddings=[.1, .2], embedding_dim=2)
    class Bridge:
        def process_audio(self, *args, **kwargs): return copy.deepcopy(raw)
    monkeypatch.setattr(audio_wsl2_bridge, "WSL2AudioBridge", Bridge)
    result = audio_wsl2_bridge.audio_unified_wsl2("fixture.wav", duration=1)
    assert result["speaker_voice_signatures"] == raw["speaker_voice_signatures"]
    assert result["emotion"] == "calm"
    assert result["embeddings"] == ([] if retired else [.1, .2])
    assert result["embedding_dim"] == (0 if retired else 2)
    rows = []
    def log(cfg, step, item, duration, status, error, extra):
        rows.append({"step": step, "status": status, "error": error, "extra": extra})
    monkeypatch.setattr(run_ingestion, "log_step_run", log)
    run_ingestion._log_wsl_capability_outcomes(cfg={}, item={}, duration_ms=0,
        outcomes=result["wsl_capability_outcomes"])
    receipt = build_capability_receipt(run_id="retirement", profile="PERSONAL_AIR_GAP",
        terminal_status="completed", step_rows=[r for r in rows if r['step']=='audio_wav2vec2_enrichment'],
        warnings=[], scenes=[], evidence_paths={}, input_count=1, full_coverage=True,
        expected_capabilities={"audio_wav2vec2_enrichment": {
            "disposition": "policy_excluded", "reason": "whole_scene_vector_retired"}})
    assert receipt["outcome"] == ("completed" if retired else "failed")

def test_retired_worker_cannot_hide_a_still_emitted_vector(monkeypatch):
    from steps.audio import audio_wsl2_bridge
    class Bridge:
        def process_audio(self, *args, **kwargs):
            return {"status": "success", "embeddings_status": "retired",
                    "embeddings": [.1, .2], "embedding_dim": 2}
    monkeypatch.setattr(audio_wsl2_bridge, "WSL2AudioBridge", Bridge)
    result = audio_wsl2_bridge.audio_unified_wsl2("fixture.wav", duration=1)
    assert result["embeddings"] == [.1, .2]
    assert result["wsl_capability_outcomes"]["wav2vec2"]["status"] == "error"
    assert result["wsl_capability_outcomes"]["wav2vec2"]["reason"] == "retired_status_with_embedding"
