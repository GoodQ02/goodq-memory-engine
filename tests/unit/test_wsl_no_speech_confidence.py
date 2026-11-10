"""Regression controls for the production worker's post-decoder speech decision."""
import copy
import math

import pytest

from wsl2_audio.process_audio import _filter_no_speech_segments


def candidate(probabilities, *, confidence=-0.25878905737772584, no_speech=0.70703125):
    return {"text": "decoded candidate", "confidence": confidence,
            "no_speech_probability": no_speech,
            "words": [{"text": f"word{i}", "probability": p} for i, p in enumerate(probabilities)]}


@pytest.mark.parametrize("segments,expected_count", [
    ([candidate([.98, .88, .99])], 1),
    ([candidate([.005519866943359375, .7705078125, .951171875],
                confidence=-.8900669983455113, no_speech=.91259765625)], 0),
    ([candidate([.9, .9], confidence=-1.2)], 0),
    ([candidate([.9, .9], confidence=-1.0)], 0),
    ([candidate([0.0, .9])], 0),
    ([], 0),
])
def test_confidence_exception_requires_decoder_and_word_support(segments, expected_count):
    original = copy.deepcopy(segments)
    accepted, quality = _filter_no_speech_segments(segments, .6, log_prob_threshold=-1.0)
    assert len(accepted) == expected_count
    assert quality["accepted_segment_count"] == expected_count
    assert len(quality["rejected_segments"]) == len(segments) - expected_count
    assert quality["confidence_override"]["log_prob_threshold"] == -1.0
    assert segments == original


@pytest.mark.parametrize("threshold", [None, True, float("nan"), float("inf"), .1, "-1"])
def test_missing_decoder_threshold_cannot_establish_absence(threshold):
    segments = [candidate([.01])]
    accepted, quality = _filter_no_speech_segments(segments, .6, log_prob_threshold=threshold)
    assert accepted == segments
    assert quality["rejected_segments"] == []
    assert quality["uncertain_segments"] == segments


@pytest.mark.parametrize("fault", ["missing_words", "missing_probability", "nan", "boolean", "out_of_range", "missing_confidence"])
def test_incomplete_confidence_evidence_stays_reviewable(fault):
    segment = candidate([.01, .9])
    if fault == "missing_words": segment.pop("words")
    elif fault == "missing_probability": segment["words"][0].pop("probability")
    elif fault == "missing_confidence": segment.pop("confidence")
    else: segment["words"][0]["probability"] = {"nan": math.nan, "boolean": True, "out_of_range": 1.1}[fault]
    accepted, quality = _filter_no_speech_segments([segment], .6, log_prob_threshold=-1.0)
    assert accepted == [segment]
    assert quality["rejected_segments"] == []
    assert quality["uncertain_segments"] == [segment]


def test_mixed_dialogue_retains_disputed_words_with_evidence():
    segments = [candidate([.01], no_speech=.91), candidate([.9], no_speech=.04)]
    accepted, quality = _filter_no_speech_segments(segments, .6, log_prob_threshold=-1.0)
    assert accepted == segments
    assert quality["rejected_segments"] == []
    assert quality["uncertain_segments"] == segments[:1]


def test_uses_configured_cutoff_not_a_sample_specific_constant():
    segments = [candidate([.7, .8], confidence=-.3)]
    accepted, _ = _filter_no_speech_segments(segments, .6, log_prob_threshold=-1.0)
    rejected, quality = _filter_no_speech_segments(segments, .6, log_prob_threshold=-.2)
    assert accepted == segments and rejected == []
    assert quality["rejected_segments"] == segments
