from copy import deepcopy

import pytest

from wsl2_audio.evidence_contract import validate_evidence


def evidence():
    return {
        "schema_version": 1,
        "source": {"sha256": "a" * 64, "pcm_sha256": "b" * 64,
                   "sample_rate": 16000, "sample_count": 32000, "origin_num": 0, "origin_den": 1},
        "provenance": {"run_id": "run-test", "epoch_id": "isolated-test",
                       "source_revision": "test-revision", "worker_sha256": "c" * 64,
                       "config_sha256": "d" * 64,
                       "models": [{"id": "fixture-model", "revision": "fixture-revision", "sha256": "e" * 64}]},
        "utterances": [{"id": "u1", "text": "Yay Joe", "span": {"start": 1000, "end": 20000},
            "language": {"value": "en", "status": "observed"}, "completeness": "complete",
            "speaker": {"id": "s1", "status": "single"},
            "words": [{"text": "Yay", "span": None, "timing": "unavailable", "reason": "alignment_unresolved"},
                      {"text": "Joe", "span": {"start": 10000, "end": 15000}, "timing": "supported"}],
            "eligibility": {purpose: {"status": "eligible", "reasons": []}
                            for purpose in ("transcript", "vocal_delivery", "voice_sample")}}],
        "overlap": [], "sound_events": [],
        "coverage": [{"span": {"start": 0, "end": 32000}, "status": "analyzed"}],
        "stages": {stage: {"status": "ok", "model_id": "fixture-model"} for stage in
                   ("recognition", "speaker_activity", "overlap", "acoustic_events")},
    }


def test_missing_word_timing_preserves_text_complete_phrase_and_separate_eligibility():
    raw = evidence()
    before = deepcopy(raw)
    result = validate_evidence(raw)
    assert result["utterances"][0]["text"] == "Yay Joe"
    assert result["utterances"][0]["words"][0]["span"] is None
    assert result["utterances"][0]["eligibility"]["vocal_delivery"]["status"] == "eligible"
    assert raw == before
    result["utterances"][0]["text"] = "changed"
    assert raw == before


@pytest.mark.parametrize("mode", ["mixed_label", "overlap", "crying", "incomplete", "unknown_purity", "detector_failed"])
def test_individual_admission_cannot_contradict_known_evidence(mode):
    raw = evidence()
    utterance = raw["utterances"][0]
    if mode == "mixed_label":
        utterance["speaker"]["status"] = "mixed"
    elif mode == "overlap":
        raw["overlap"] = [{"span": {"start": 15000, "end": 25000}, "status": "observed"}]
    elif mode == "crying":
        raw["sound_events"] = [{"id": "event1", "label": "crying", "span": {"start": 15000, "end": 25000}, "status": "observed"}]
    elif mode == "incomplete":
        utterance["completeness"] = "incomplete"
    elif mode == "unknown_purity":
        utterance["speaker"]["status"] = "unresolved"
    else:
        raw["stages"]["overlap"] = {"status": "error", "reason": "model_unavailable"}
    with pytest.raises(ValueError):
        validate_evidence(raw)


def test_mixed_words_are_retained_when_individual_uses_are_excluded():
    raw = evidence()
    u = raw["utterances"][0]
    u["speaker"] = {"id": None, "status": "mixed"}
    for use in ("vocal_delivery", "voice_sample"):
        u["eligibility"][use] = {"status": "ineligible", "reasons": ["overlapping_cheers"]}
    assert validate_evidence(raw)["utterances"][0]["text"] == "Yay Joe"


@pytest.mark.parametrize("mode", ["zero_word", "outside_word", "duplicate_id", "coverage_gap", "unknown_version", "nan", "missing_hash"])
def test_invalid_evidence_fails_without_repairs(mode):
    raw = evidence()
    if mode == "zero_word":
        raw["utterances"][0]["words"][1]["span"]["end"] = 10000
    elif mode == "outside_word":
        raw["utterances"][0]["words"][1]["span"]["end"] = 21000
    elif mode == "duplicate_id":
        raw["utterances"].append(deepcopy(raw["utterances"][0]))
    elif mode == "coverage_gap":
        raw["coverage"][0]["span"]["end"] = 31999
    elif mode == "unknown_version":
        raw["schema_version"] = 2
    elif mode == "nan":
        raw["diagnostic_score"] = float("nan")
    else:
        del raw["provenance"]["worker_sha256"]
    with pytest.raises(ValueError):
        validate_evidence(raw)


def test_error_and_supported_absence_require_distinct_reasons():
    raw = evidence()
    raw["stages"]["optional_enrichment"] = {"status": "unavailable"}
    with pytest.raises(ValueError):
        validate_evidence(raw)
    raw["stages"]["optional_enrichment"]["reason"] = "model_not_installed"
    assert validate_evidence(raw)["stages"]["optional_enrichment"]["status"] == "unavailable"


@pytest.mark.parametrize("state", ["digital_silence", "error", "not_run", "unresolved"])
def test_admitted_speech_cannot_overlap_unanalyzed_or_absent_signal(state):
    raw = evidence()
    raw["coverage"][0]["status"] = state
    with pytest.raises(ValueError):
        validate_evidence(raw)


def test_simultaneous_words_can_remain_as_mixed_transcript_evidence():
    raw = evidence()
    utterance = raw["utterances"][0]
    utterance["speaker"] = {"id": None, "status": "mixed"}
    utterance["words"] = [
        {"text": "Yay", "span": {"start": 1000, "end": 9000}, "timing": "supported"},
        {"text": "Joe", "span": {"start": 5000, "end": 15000}, "timing": "supported"},
    ]
    for purpose in ("vocal_delivery", "voice_sample"):
        utterance["eligibility"][purpose] = {"status": "ineligible", "reasons": ["mixed_voices"]}
    assert validate_evidence(raw)["utterances"][0]["words"] == utterance["words"]


def test_unresolved_language_cannot_silently_claim_a_language():
    raw = evidence()
    raw["utterances"][0]["language"] = {"value": "es", "status": "unresolved"}
    with pytest.raises(ValueError):
        validate_evidence(raw)


def test_complete_phrase_may_contain_a_digital_silence_pause():
    raw = evidence()
    raw["coverage"] = [
        {"span": {"start": 0, "end": 8000}, "status": "analyzed"},
        {"span": {"start": 8000, "end": 9000}, "status": "digital_silence"},
        {"span": {"start": 9000, "end": 32000}, "status": "analyzed"},
    ]
    assert validate_evidence(raw)["utterances"][0]["completeness"] == "complete"


def test_observed_music_cannot_be_published_on_exact_silence():
    raw = evidence()
    raw["utterances"] = []
    raw["coverage"][0]["status"] = "digital_silence"
    raw["sound_events"] = [{"id": "event1", "label": "music", "span": {"start": 0, "end": 1000}, "status": "observed"}]
    with pytest.raises(ValueError):
        validate_evidence(raw)


def test_admitted_transcript_requires_recognition_provenance():
    raw = evidence()
    raw["stages"] = {}
    raw["provenance"]["models"] = []
    for purpose in ("vocal_delivery", "voice_sample"):
        raw["utterances"][0]["eligibility"][purpose] = {"status": "unresolved", "reasons": ["not_assessed"]}
    with pytest.raises(ValueError):
        validate_evidence(raw)


def test_supported_word_cannot_be_timed_in_a_silent_pause():
    raw = evidence()
    raw["coverage"] = [
        {"span": {"start": 0, "end": 10000}, "status": "analyzed"},
        {"span": {"start": 10000, "end": 16000}, "status": "digital_silence"},
        {"span": {"start": 16000, "end": 32000}, "status": "analyzed"},
    ]
    with pytest.raises(ValueError):
        validate_evidence(raw)


def test_later_stage_failure_does_not_discard_supported_earlier_phrases():
    raw = evidence()
    raw["stages"]["overlap"] = {"status": "partial", "model_id": "fixture-model",
        "reason": "later_window_failed", "assessed_spans": [{"start": 0, "end": 20000}]}
    assert validate_evidence(raw)["utterances"][0]["eligibility"]["voice_sample"]["status"] == "eligible"
    raw["stages"]["overlap"]["assessed_spans"][0]["end"] = 19999
    with pytest.raises(ValueError):
        validate_evidence(raw)
