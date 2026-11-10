import json

import pytest

from scripts.audio.run_acceptance import (
    NORMALIZATION, evaluate_suite, main, score_admission, score_labels,
    score_lexical, score_timing, tokenize,
)


def test_lexical_grouping_and_missing_timestamps_do_not_change_credit():
    reference = tokenize("Don't forget a jacket. It's cold.")
    split = ["Don't forget", "a jacket.", "It's cold."]
    merged = ["Don't forget a jacket. It's cold."]
    assert score_lexical(reference, tokenize(" ".join(split))) == score_lexical(reference, tokenize(" ".join(merged)))
    result = score_lexical(reference, reference)
    assert result["wer"] == 0 and result["retention"] == 1
    timing = score_timing(result["matches"], {}, {})
    assert timing["valid_timing_coverage"] == 0
    assert timing["correct_lexical_matches"] == len(reference)


def test_edits_repetitions_and_stable_ties():
    r = score_lexical(["a", "b", "c"], ["a", "a", "d", "c"])
    assert (r["correct"], r["insertions"], r["substitutions"], r["deletions"]) == (2, 1, 1, 0)
    assert r["wer"] == pytest.approx(2/3)
    assert score_lexical(["a"], ["a", "a"])["matches"] == [[0, 1]]
    assert score_lexical(["a", "a"], ["a"])["deletions"] == 1


def test_all_abstain_and_empty_reference_never_fabricate_accuracy():
    r = score_lexical(["one", "two"], [])
    assert r["deletions"] == 2 and r["wer"] == 1 and r["retention"] == 0
    r = score_lexical([], ["hallucination"])
    assert r["insertions"] == 1 and r["wer"] is None
    assert score_lexical([], [])["retention"] is None


def test_frozen_normalization_preserves_names_numbers_and_repetitions():
    assert tokenize("JOE, Joe! Seven 7 don't.") == ["joe", "joe", "seven", "7", "dont"]
    assert score_lexical(tokenize("Joe is seven"), tokenize("Jose is 7"))["substitutions"] == 2


@pytest.mark.parametrize("invalid", [None, [0, 0], [2, 1], [-1, 2], [0, float("nan")], [False, 1]])
def test_invalid_time_reduces_coverage(invalid):
    r = score_timing([[0, 0], [1, 1]], {0: [0, 1], 1: [1, 2]}, {0: [0, 1], 1: invalid})
    assert r["valid_timing_coverage"] == .5 and r["missing_prediction_intervals"] == 1
    assert r["status"] == "pending"


def test_wrong_time_cannot_erase_lexical_match_or_pass_timing():
    lex = score_lexical(["yes"], ["yes"])
    r = score_timing(lex["matches"], {0: [0, 1]}, {0: [10, 11]})
    assert lex["wer"] == 0
    assert r["onset_p95_seconds"] == 10 and r["offset_p95_seconds"] == 10


def test_missing_reference_times_are_pending_even_with_valid_model_times():
    r = score_timing([[0, 0]], {}, {0: [0, 1]})
    assert r["valid_timing_coverage"] == 1 and r["reviewed_pairs"] == 0
    assert r["status"] == "pending" and r["onset_p95_seconds"] is None


def test_admission_counts_partial_phrase_as_false_exclusion():
    r = score_admission([[0, 2], [3, 4]], [[5, 6]], [[.2, 2], [3, 4], [5, 5.5], [5.2, 6]])
    assert r["complete_admitted"] == 1 and r["false_exclusions"] == 1
    assert r["contamination_seconds"] == 1  # union, not duplicated intersections
    assert r["contaminated_samples"] == 2  # both actual inputs intersect it
    assert r["clean_admission_rate"] == .5
    assert score_admission([[0, 2]], [], [])["false_exclusions"] == 1
    assert score_admission([], [], [])["status"] == "pending"


def test_conflicting_labels_and_invalid_intervals_fail():
    with pytest.raises(ValueError):
        score_admission([[0, 2]], [[1, 3]], [])
    with pytest.raises(ValueError):
        score_admission([], [], [[2, 2]])


def test_unknown_output_and_abstention_are_label_misses():
    r = score_labels(["happy", "sad"], [None, "unknown"], ["happy", "sad"])
    assert r["misses"] == 2 and r["coverage"] == 0 and r["accepted_accuracy"] is None
    assert score_labels(["happy"], ["happy"], ["happy", "sad"])["status"] == "pending"
    assert score_labels([], [], ["happy"])["status"] == "pending"


def bound_suite():
    inputs = {"normalization": NORMALIZATION, "split": "development", "items": {"one": {"sha256": "a"}}}
    refs = {"items": {"one": {"sha256": "a", "lexical_scope": "complete", "text": "One two"}}}
    pred = {"items": {"one": {"sha256": "a", "status": "complete", "text": "One"}}}
    return inputs, pred, refs


def test_suite_keeps_quality_pending_and_counts_misses():
    inputs, pred, refs = bound_suite()
    r = evaluate_suite(inputs, pred, refs)
    assert r["lexical_totals"]["deletions"] == 1
    assert r["lexical_totals"]["retention"] == .5
    assert r["development_checks"]["lexical_retention"]["status"] == "fail"
    assert r["development_checks"]["per_item"]["one"]["onset_p95_seconds"]["status"] == "pending"
    assert not r["ready_to_adopt"]
    assert {x["status"] for x in r["acceptance"].values()} == {"pending"}
    pred["items"]["one"]["sha256"] = "different"
    with pytest.raises(ValueError, match="binding"):
        evaluate_suite(inputs, pred, refs)


def test_partial_reference_missing_output_and_failed_execution_stay_pending():
    inputs, pred, refs = bound_suite()
    refs["items"]["one"]["lexical_scope"] = "partial"
    assert evaluate_suite(inputs, pred, refs)["items"]["one"]["lexical"]["status"] == "pending"
    pred["items"]["one"]["status"] = "failed"
    assert evaluate_suite(inputs, pred, refs)["items"]["one"]["status"] == "pending"
    assert evaluate_suite(inputs, {}, refs)["items"]["one"]["status"] == "pending"


def test_real_cli_scores_separate_inputs_and_does_not_overwrite(tmp_path):
    args = ["score"]
    for key, data in zip(("inputs", "evidence", "references"), bound_suite()):
        path = tmp_path / (key + ".json")
        path.write_text(json.dumps(data))
        args += ["--" + key, str(path)]
    out = tmp_path / "score.json"
    args += ["--output", str(out)]
    assert main(args) == 0
    assert json.loads(out.read_text())["lexical_totals"]["reference_words"] == 2
    assert main(args) == 1
