import copy
import json

import pytest

from scripts.audio import run_acceptance as scoring


def event(label, start, end):
    return {"label": label, "span": [start, end]}


def turn(speaker, start, end):
    return {"speaker": speaker, "span": [start, end]}


def test_event_matching_is_one_to_one_and_uses_maximum_cardinality():
    # Greedily matching the first prediction to reference 0 loses a valid match.
    refs = [event("laugh", 0, 2), event("laugh", 1, 3)]
    preds = [event("laugh", 0, 3), event("laugh", 0, 1)]
    result = scoring.score_events(refs, preds, ["laugh"])
    assert result["classes"]["laugh"]["true_positive"] == 2
    duplicate = scoring.score_events(refs[:1], [refs[0], refs[0]], ["laugh"])
    assert duplicate["classes"]["laugh"]["precision"] == .5


def test_events_keep_empty_classes_pending_and_count_false_positives():
    result = scoring.score_events([], [event("music", 0, 2)], ["music", "crying"])
    assert result["classes"]["music"]["false_positive"] == 1
    assert result["classes"]["music"]["recall"] is None
    assert result["status"] == "pending"
    with pytest.raises(ValueError):
        scoring.score_events([], [event("unknown", 0, 1)], ["music"])


def test_overlap_is_duration_weighted_and_counts_misses_and_spurious_detection():
    result = scoring.score_overlap([[1, 3]], [[2, 4], [2, 4]], [[0, 5]])
    assert result["true_positive_seconds"] == 1
    assert result["false_positive_seconds"] == result["false_negative_seconds"] == 1
    assert result["precision"] == result["recall"] == .5
    assert scoring.score_overlap([[1, 3]], [], [[0, 5]])["recall"] == 0
    assert scoring.score_overlap([], [], [[0, 5]])["recall"] is None


def test_overlap_reports_masked_and_unmasked_results_without_hiding_denominators():
    result = scoring.score_overlap([[1, 3]], [[2, 4]], [[0, 5]], [[1, 2]])
    assert result["unmasked"]["recall"] == .5
    assert result["recall"] == 1
    assert result["excluded_uncertain_seconds"] == 1
    assert result["reviewed_seconds"] == 4


def test_diarization_uses_one_global_mapping_and_unknown_is_missed_attribution():
    refs = [turn("A", 0, 1), turn("B", 1, 2), turn("A", 2, 3), turn("B", 3, 4)]
    preds = [turn("X", 0, 1), turn("Y", 1, 2), turn("Y", 2, 3), turn("X", 3, 4)]
    result = scoring.score_diarization(refs, preds, [[0, 4]])
    assert result["confusion_seconds"] == 2 and result["der"] == .5
    result = scoring.score_diarization([turn("A", 0, 1)], [turn(None, 0, 1)], [[0, 1]])
    assert result["missed_speech_seconds"] == 1 and result["der"] == 1
    result = scoring.score_diarization([turn("A", 0, 1)], [turn(None, 1, 2)], [[0, 2]])
    assert result["missed_speech_seconds"] == result["false_alarm_seconds"] == 1
    assert result["der"] == 2


def test_diarization_counts_false_alarm_and_excludes_only_reference_overlap():
    refs = [turn("A", 0, 2), turn("B", 1, 2)]
    preds = [turn("X", 0, 3), turn("Y", 0, 1)]
    result = scoring.score_diarization(refs, preds, [[0, 3]])
    assert result["excluded_reference_overlap_seconds"] == 1
    assert result["reference_speaker_seconds"] == 1
    assert result["false_alarm_seconds"] == 2  # Extra voice plus speech in reviewed silence.
    assert result["der"] == 2


def test_labels_report_macro_f1_and_per_class_abstention():
    result = scoring.score_labels(["positive", "negative"], ["positive", None], ["positive", "negative"])
    assert result["macro_f1"] == .5
    assert result["per_class"]["negative"]["coverage"] == 0
    assert result["per_class"]["negative"]["f1"] == 0
    assert result["accepted_accuracy"] == 1 and result["coverage"] == .5


@pytest.mark.parametrize("invalid", [[], ["__abstain__"], ["x", "x"], [None]])
def test_invalid_label_taxonomy_is_rejected(invalid):
    with pytest.raises(ValueError):
        scoring.score_labels([], [], invalid)


def feature_suite():
    inputs = {"normalization": scoring.NORMALIZATION, "split": "development", "items": {"clip": {"sha256": "a", "duration_seconds": 5}}}
    refs = {"items": {"clip": {"sha256": "a", "complete_event_review": True,
        "events": [event("laughter", 1, 2)], "reviewed_intervals": [[0, 5]],
        "overlap_intervals": [[2, 3]], "speaker_turns": [turn("A", 0, 2)],
        "sentiment": [{"id": "u1", "label": "positive"}],
        "vocal_delivery": [{"id": "u1", "label": "cheerful/playful"}]}}}
    pred = {"items": {"clip": {"sha256": "a", "status": "complete", "text": "hello",
        "events": [event("laughter", 1, 2)], "overlap_intervals": [],
        "speaker_turns": [turn(None, 0, 2)], "sentiment": [], "vocal_delivery": []}}}
    return inputs, pred, refs


def test_real_scoring_cli_binds_feature_labels_and_keeps_release_pending(tmp_path):
    args = ["score"]
    for key, value in zip(("inputs", "evidence", "references"), feature_suite()):
        path = tmp_path / (key + ".json")
        path.write_text(json.dumps(value))
        args.extend(["--" + key, str(path)])
    output = tmp_path / "score.json"
    assert scoring.main([*args, "--output", str(output)]) == 0
    result = json.loads(output.read_text())
    features = result["items"]["clip"]["features"]
    assert features["events"]["classes"]["laughter"]["recall"] == 1
    assert features["diarization"]["der"] == 1
    assert features["sentiment"]["misses"] == 1
    assert features["vocal_delivery"]["coverage"] == 0
    assert not result["ready_to_adopt"]
    assert all(row["status"] == "pending" for row in result["acceptance"].values())


def test_partial_event_reviews_and_missing_prediction_are_pending():
    inputs, pred, refs = feature_suite()
    refs["items"]["clip"]["complete_event_review"] = False
    pred["items"]["clip"].pop("speaker_turns")
    result = scoring.evaluate_suite(inputs, pred, refs)["items"]["clip"]["features"]
    assert result["events"]["status"] == result["diarization"]["status"] == "pending"


def test_duplicate_labels_and_out_of_source_intervals_cannot_score():
    inputs, pred, refs = feature_suite()
    refs["items"]["clip"]["sentiment"] *= 2
    with pytest.raises(ValueError, match="Duplicate"):
        scoring.evaluate_suite(inputs, pred, refs)
    inputs, pred, refs = feature_suite()
    pred["items"]["clip"]["events"][0]["span"] = [4, 6]
    with pytest.raises(ValueError, match="source"):
        scoring.evaluate_suite(inputs, pred, refs)


def test_reference_and_prediction_label_order_do_not_change_matching():
    inputs, pred, refs = feature_suite()
    refs["items"]["clip"]["sentiment"].append({"id": "u2", "label": "negative"})
    pred["items"]["clip"]["sentiment"] = list(reversed(copy.deepcopy(refs["items"]["clip"]["sentiment"])))
    result = scoring.evaluate_suite(inputs, pred, refs)["items"]["clip"]["features"]["sentiment"]
    assert result["correct"] == 2


def test_bound_cross_recording_recurrence_counts_abstention_and_false_links():
    inputs, predictions, references = feature_suite()
    pairs = {str(n): {"left_sha256": "a", "right_sha256": str(n),
        "left_recording_id": "recording-a", "right_recording_id": "recording-b"} for n in range(3)}
    inputs["recurrence_pairs"] = pairs
    references["recurrence_pairs"] = {k: {**p, "same_speaker": k != "2"} for k, p in pairs.items()}
    predictions["recurrence_pairs"] = {k: {**p, "same_speaker": None if k == "1" else True} for k, p in pairs.items()}
    result = scoring.evaluate_suite(inputs, predictions, references)
    assert result["recurrence"]["same_speaker_recall"] == .5
    assert result["recurrence"]["false_same_speaker_links"] == 1
    assert result["development_checks"]["recurrence"]["false_same_speaker_links"]["status"] == "fail"
    predictions["recurrence_pairs"]["0"]["right_sha256"] = "changed"
    with pytest.raises(ValueError, match="binding"):
        scoring.evaluate_suite(inputs, predictions, references)


def test_missing_recurrence_pairs_are_pending_not_true_negatives():
    result = scoring.score_recurrence({"pair": {}}, {}, {})
    assert result["missing_pairs"] == ["pair"] and result["status"] == "pending"
    assert result["same_speaker_recall"] is None


def test_repeated_recurrence_pair_cannot_inflate_example_counts():
    pair = {"left_sha256": "a", "right_sha256": "b", "left_recording_id": "A", "right_recording_id": "B"}
    inputs = {"one": pair, "two": pair}
    labels = {k: {**p, "same_speaker": True} for k, p in inputs.items()}
    with pytest.raises(ValueError, match="Duplicate recurrence"):
        scoring.score_recurrence(inputs, labels, labels)


def test_missing_recurrence_prediction_preserves_known_positive_denominator():
    inputs, predictions, references = feature_suite()
    pairs = {str(n): {"left_sha256": "a", "right_sha256": str(n),
        "left_recording_id": "A", "right_recording_id": "B"} for n in range(2)}
    inputs["recurrence_pairs"] = pairs
    references["recurrence_pairs"] = {k: {**p, "same_speaker": True} for k, p in pairs.items()}
    predictions["recurrence_pairs"] = {"0": references["recurrence_pairs"]["0"]}
    result = scoring.evaluate_suite(inputs, predictions, references)
    assert result["recurrence"]["same_speaker_pairs"] == 2
    assert result["recurrence"]["same_speaker_recall"] == .5
    assert result["recurrence"]["missing_pairs"] == ["1"]
    assert result["development_checks"]["recurrence"]["same_speaker_recall"]["status"] == "pending"
