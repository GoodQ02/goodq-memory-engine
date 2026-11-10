"""Verify fixtures and score separately bound audio references and predictions."""

import argparse
import hashlib
import json
import math
import re
import struct
import unicodedata
from pathlib import Path


NORMALIZATION = "nfkc_casefold_punctuation_removed_numbers_literal_v1"


def tokenize(text: str) -> list[str]:
    """No name/number correction. Apostrophes are removed, other punctuation splits."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.replace("'", "").replace("’", "")
    return re.findall(r"[^\W_]+", text, flags=re.UNICODE)


def score_lexical(reference: list[str], hypothesis: list[str]) -> dict:
    """Minimum edits; ties prefer diagonal, deletion, insertion, in that order.

    Inputs are complete normalized token streams, never only timed words. Matches
    are frozen before timing is inspected. Backtracking starts at the stream end.
    """
    if not all(isinstance(x, str) and x for x in reference + hypothesis):
        raise ValueError("Lexical inputs must be nonempty string tokens")
    n, m = len(reference), len(hypothesis)
    costs = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        costs[i][0] = i
    for j in range(m + 1):
        costs[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            costs[i][j] = min(costs[i-1][j-1] + (reference[i-1] != hypothesis[j-1]),
                              costs[i-1][j] + 1, costs[i][j-1] + 1)
    i, j = n, m
    counts = dict(correct=0, substitutions=0, deletions=0, insertions=0)
    matches, alignment = [], []
    while i or j:
        if i and j and costs[i][j] == costs[i-1][j-1] + (reference[i-1] != hypothesis[j-1]):
            kind = "correct" if reference[i-1] == hypothesis[j-1] else "substitutions"
            counts[kind] += 1
            alignment.append([kind, i-1, j-1])
            if kind == "correct":
                matches.append([i-1, j-1])
            i, j = i-1, j-1
        elif i and costs[i][j] == costs[i-1][j] + 1:
            counts["deletions"] += 1
            alignment.append(["deletions", i-1, None])
            i -= 1
        else:
            counts["insertions"] += 1
            alignment.append(["insertions", None, j-1])
            j -= 1
    return {**counts, "reference_words": n, "hypothesis_words": m,
            "wer": costs[n][m] / n if n else None,
            "retention": counts["correct"] / n if n else None,
            "matches": matches[::-1], "alignment": alignment[::-1],
            "status": "scored" if n else "empty_reference",
            "tie_break": "backtrack_diagonal_deletion_insertion"}


def _interval(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 2
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in value)
            or not 0 <= value[0] < value[1]):
        return None
    return tuple(value)


def _p95(values):
    return sorted(values)[math.ceil(.95 * len(values)) - 1] if values else None


def score_timing(matches: list, reference: dict, prediction: dict) -> dict:
    """Intervals keyed by normalized token index, in source seconds.

    Missing prediction times reduce coverage. Missing human times leave accuracy
    pending; they do not certify a model interval. Intervals must be marked
    supported by the adapter (unsupported model times are passed as null).
    """
    valid, paired, onset, offset = 0, 0, [], []
    for ri, hi in matches:
        ref = _interval(reference.get(str(ri), reference.get(ri)))
        pred = _interval(prediction.get(str(hi), prediction.get(hi)))
        valid += pred is not None
        if ref and pred:
            paired += 1
            onset.append(abs(pred[0] - ref[0]))
            offset.append(abs(pred[1] - ref[1]))
    return {"correct_lexical_matches": len(matches), "valid_prediction_intervals": valid,
            "missing_prediction_intervals": len(matches) - valid,
            "valid_timing_coverage": valid / len(matches) if matches else None,
            "reviewed_pairs": paired, "onset_errors_seconds": onset,
            "offset_errors_seconds": offset, "onset_p95_seconds": _p95(onset),
            "offset_p95_seconds": _p95(offset),
            "status": "scored" if matches and paired == len(matches) else "pending"}


def _union(intervals):
    checked = [_interval(x) for x in intervals]
    if any(x is None for x in checked):
        raise ValueError("Invalid source interval")
    merged = []
    for start, end in sorted(checked):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return merged


def _duration(intervals):
    return sum(b-a for a, b in _union(intervals))


def _intersections(left, right):
    return [[max(a, c), min(b, d)] for a, b in _union(left) for c, d in _union(right)
            if max(a, c) < min(b, d)]


def proportion_interval(successes, total):
    """Wilson 95% interval; descriptive only for correlated development items."""
    if not total:
        return None
    p, z = successes / total, 1.959963984540054
    center = (p + z*z/(2*total))/(1+z*z/total)
    half = z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/(1+z*z/total)
    return [max(0., center-half), min(1., center+half)]


def _subtract(intervals, excluded):
    result = _union(intervals)
    for left, right in _union(excluded):
        result = [part for start, end in result for part in
                  ([start, min(end, left)], [max(start, right), end]) if part[0] < part[1]]
    return result


def score_overlap(reference, prediction, reviewed, uncertain=()):
    """Duration-weighted detection, with an explicit unmasked sensitivity result."""
    reviewed = _union(reviewed)
    ref, pred = _intersections(reference, reviewed), _intersections(prediction, reviewed)
    scored = _subtract(reviewed, uncertain)
    truth, detected = _intersections(ref, scored), _intersections(pred, scored)
    true_positive = _duration(_intersections(truth, detected))
    ref_seconds, pred_seconds = _duration(truth), _duration(detected)
    result = {"true_positive_seconds": true_positive,
              "false_positive_seconds": max(0., pred_seconds-true_positive),
              "false_negative_seconds": max(0., ref_seconds-true_positive),
              "reference_seconds": ref_seconds, "predicted_seconds": pred_seconds,
              "reviewed_seconds": _duration(scored),
              "prediction_outside_review_seconds": _duration(prediction)-_duration(pred),
              "excluded_uncertain_seconds": _duration(reviewed)-_duration(scored),
              "precision": true_positive/pred_seconds if pred_seconds else None,
              "recall": true_positive/ref_seconds if ref_seconds else None,
              "status": "scored" if scored else "pending"}
    if uncertain:
        result["unmasked"] = score_overlap(reference, prediction, reviewed)
    return result


def score_events(reference, prediction, classes):
    """One-to-one maximum-cardinality matching at temporal IoU >= 0.5.

    The caller must supply a complete event review. Matching order is frozen:
    input prediction order, descending IoU, then reference index. Duplicate
    predictions remain false positives; absent reference classes stay pending.
    """
    if not classes or len(set(classes)) != len(classes):
        raise ValueError("Invalid event taxonomy")
    for row in [*reference, *prediction]:
        if row.get("label") not in classes or _interval(row.get("span")) is None:
            raise ValueError("Invalid event label or interval")
    result = {}
    for label in classes:
        refs = [r["span"] for r in reference if r["label"] == label]
        preds = [p["span"] for p in prediction if p["label"] == label]
        edges = []
        for start, end in preds:
            overlaps = []
            for index, (left, right) in enumerate(refs):
                intersection = max(0., min(end, right)-max(start, left))
                iou = intersection/(end-start+right-left-intersection)
                if iou >= .5:
                    overlaps.append((-iou, index))
            edges.append([index for _, index in sorted(overlaps)])
        matched = {}

        def augment(pred_index, visited):
            for ref_index in edges[pred_index]:
                if ref_index in visited:
                    continue
                visited.add(ref_index)
                if ref_index not in matched or augment(matched[ref_index], visited):
                    matched[ref_index] = pred_index
                    return True
            return False

        for index in range(len(preds)):
            augment(index, set())
        count = len(matched)
        result[label] = {"references": len(refs), "predictions": len(preds),
                         "true_positive": count, "false_positive": len(preds)-count,
                         "false_negative": len(refs)-count,
                         "precision": count/len(preds) if preds else None,
                         "recall": count/len(refs) if refs else None,
                         "precision_wilson95": proportion_interval(count, len(preds)),
                         "recall_wilson95": proportion_interval(count, len(refs)),
                         "matches": [[r, p] for r, p in sorted(matched.items())]}
    return {"classes": result, "iou_threshold": .5,
            "status": "scored" if all(r["references"] for r in result.values()) else "pending"}


def score_diarization(reference, prediction, reviewed):
    """No-collar non-overlap DER, with one anonymous-label mapping per recording.

    Reviewed silence counts false alarms. Unknown predicted attribution is missed
    attribution. Only human-reference overlap is excluded, never model overlap.
    """
    reviewed = _union(reviewed)
    for rows, is_reference in ((reference, True), (prediction, False)):
        for row in rows:
            speaker = row.get("speaker")
            if (_interval(row.get("span")) is None or
                    not (isinstance(speaker, str) and speaker.strip()) and
                    (is_reference or speaker is not None)):
                raise ValueError("Invalid speaker turn")
    points = sorted({v for span in reviewed for v in span} |
                    {v for row in [*reference, *prediction] for v in row["span"]})
    segments, excluded = [], 0.
    for start, end in zip(points, points[1:]):
        middle = (start+end)/2
        if not any(a <= middle < b for a, b in reviewed):
            continue
        ref = {r["speaker"] for r in reference if r["span"][0] <= middle < r["span"][1]}
        predicted = {r["speaker"] for r in prediction if r["span"][0] <= middle < r["span"][1]}
        unknown = None in predicted
        pred = predicted-{None}
        if len(ref) > 1:
            excluded += end-start
        else:
            segments.append((end-start, ref, pred, unknown))
    refs = sorted({s for _, ref, _, _ in segments for s in ref})
    preds = sorted({s for _, _, pred, _ in segments for s in pred})
    mapping = {}
    if refs and preds:
        from scipy.optimize import linear_sum_assignment
        weights = [[sum(dt for dt, ref, pred, _ in segments if r in ref and p in pred)
                    for p in preds] for r in refs]
        left, right = linear_sum_assignment(weights, maximize=True)
        mapping = {preds[p]: refs[r] for r, p in zip(left, right)}
    missed = false_alarm = confusion = total = 0.
    for duration, ref, pred, unknown in segments:
        correct = sum(mapping.get(p) in ref for p in pred)
        total += duration*len(ref)
        missed += duration*max(0, len(ref)-len(pred))
        false_alarm += duration*max(0, len(pred)+int(unknown)-len(ref))
        confusion += duration*(min(len(ref), len(pred))-correct)
    return {"mapping": mapping, "reference_speaker_seconds": total,
            "reviewed_seconds": _duration(reviewed),
            "excluded_reference_overlap_seconds": excluded,
            "missed_speech_seconds": missed, "false_alarm_seconds": false_alarm,
            "confusion_seconds": confusion,
            "der": (missed+false_alarm+confusion)/total if total else None,
            "collar_seconds": 0, "status": "scored" if total else "pending"}


def score_admission(clean: list, forbidden: list, admitted: list, *, complete_review=False) -> dict:
    """Clean complete utterances count once; partial admission is an exclusion.

    No collar; no model-derived mask is treated as human truth. Unknown regions
    cannot establish contamination precision and remain outside these labels.
    """
    clean_spans = [_interval(x) for x in clean]
    if any(x is None for x in clean_spans):
        raise ValueError("Invalid clean utterance interval")
    original_samples = list(admitted)
    admitted = _union(original_samples)
    forbidden = _union(forbidden)
    if _duration(_intersections(clean, forbidden)):
        raise ValueError("Conflicting clean and forbidden references")
    retained = sum(_duration(_intersections([span], admitted)) >= span[1]-span[0]-1e-9
                   for span in clean_spans)
    contaminated = _intersections(admitted, forbidden)
    return {"clean_utterances": len(clean), "complete_admitted": retained,
            "false_exclusions": len(clean)-retained,
            "clean_admission_rate": retained/len(clean) if clean else None,
            "clean_admission_wilson95": proportion_interval(retained, len(clean)),
            "admitted_seconds": _duration(admitted),
            "known_forbidden_seconds": _duration(forbidden),
            "contamination_seconds": _duration(contaminated),
            "contaminated_samples": sum(bool(_intersections([span], forbidden)) for span in original_samples),
            "reference_coverage": "complete" if complete_review else "partial",
            "status": "scored" if clean or forbidden else "pending"}


def score_labels(reference: list[str], prediction: list[str | None], classes: list[str]) -> dict:
    """Abstentions/unknown outputs are misses; absent classes stay pending."""
    if (len(reference) != len(prediction) or not classes or
            any(not isinstance(c, str) or not c or c == "__abstain__" for c in classes) or
            len(set(classes)) != len(classes)):
        raise ValueError("Mismatched labels or duplicate classes")
    if any(x not in classes for x in reference):
        raise ValueError("Unknown reference label")
    matrix = {r: {p: 0 for p in [*classes, "__abstain__"]} for r in classes}
    for r, p in zip(reference, prediction):
        matrix[r][p if p in classes else "__abstain__"] += 1
    accepted = sum(p in classes for p in prediction)
    correct = sum(r == p for r, p in zip(reference, prediction))
    per_class = {}
    for label in classes:
        total = sum(matrix[label].values())
        accepted_class = total-matrix[label]["__abstain__"]
        true_positive = matrix[label][label]
        false_positive = sum(matrix[r][label] for r in classes if r != label)
        false_negative = total-true_positive
        denominator = 2*true_positive+false_positive+false_negative
        per_class[label] = {"examples": total, "accepted": accepted_class,
                            "correct": true_positive,
                            "coverage": accepted_class/total if total else None,
                            "f1": 2*true_positive/denominator if denominator else None}
    return {"examples": len(reference), "accepted": accepted, "correct": correct,
            "misses": len(reference)-correct, "wrong_accepted": accepted-correct,
            "accepted_accuracy": correct/accepted if accepted else None,
            "coverage": accepted/len(reference) if reference else None,
            "accepted_accuracy_wilson95": proportion_interval(correct, accepted),
            "coverage_wilson95": proportion_interval(accepted, len(reference)),
            "per_class": per_class,
            "macro_f1": (sum(r["f1"] for r in per_class.values())/len(classes)
                         if all(r["examples"] for r in per_class.values()) else None),
            "confusion_matrix": matrix,
            "missing_classes": [c for c in classes if c not in reference],
            "status": "scored" if reference and all(c in reference for c in classes) else "pending"}


def _feature_scores(source, ref, pred):
    """Optional independent reference fields; missing observations stay pending."""
    pending = lambda: {"status": "pending", "reason": "missing_complete_reference_or_prediction"}
    result = {key: pending() for key in ("events", "overlap", "diarization", "sentiment", "vocal_delivery")}
    interval_keys = ("events", "overlap_intervals", "speaker_turns", "reviewed_intervals", "uncertain_intervals")
    if any(key in row for key in interval_keys for row in (ref, pred)):
        duration = source.get("duration_seconds")
        if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
            raise ValueError("Feature intervals require a finite source duration")
        for row in (ref, pred):
            for key in interval_keys:
                for value in row.get(key, []):
                    span = value.get("span") if key in ("events", "speaker_turns") else value
                    if _interval(span) is None or span[1] > duration:
                        raise ValueError("Feature interval exceeds source bounds")
    if ref.get("complete_event_review") is True and "events" in ref and "events" in pred:
        result["events"] = score_events(ref["events"], pred["events"],
            ["crying", "laughter", "cheering", "singing/humming", "music"])
    reviewed = ref.get("reviewed_intervals", [])
    if reviewed and "overlap_intervals" in ref and "overlap_intervals" in pred:
        result["overlap"] = score_overlap(ref["overlap_intervals"], pred["overlap_intervals"],
                                           reviewed, ref.get("uncertain_intervals", []))
    if reviewed and "speaker_turns" in ref and "speaker_turns" in pred:
        result["diarization"] = score_diarization(ref["speaker_turns"], pred["speaker_turns"], reviewed)
    for key, classes in (("sentiment", ["positive", "neutral", "negative"]),
                         ("vocal_delivery", ["cheerful/playful", "calm/neutral", "upset/distressed", "angry/irritated"])):
        if key not in ref or key not in pred:
            continue
        labels = []
        for rows in (ref[key], pred[key]):
            by_id = {}
            for row in rows:
                ident = row.get("id")
                if not isinstance(ident, str) or not ident or ident in by_id:
                    raise ValueError("Duplicate or missing reviewed utterance id")
                by_id[ident] = row.get("label")
            labels.append(by_id)
        truth, guesses = labels
        if set(guesses)-set(truth):
            raise ValueError("Prediction labels have no reviewed utterance binding")
        result[key] = score_labels(list(truth.values()), [guesses.get(k) for k in truth], classes)
    return result


def score_recurrence(inputs, evidence, references):
    """Score frozen cross-recording pairs without conferring identity authority."""
    same = different = recovered = false_links = accepted = 0
    missing = []
    seen = set()
    for key, pair in inputs.items():
        ref, pred = references.get(key), evidence.get(key)
        if ref is None:
            missing.append(key)
            continue
        if pred is None:
            missing.append(key)
        fields = ("left_sha256", "right_sha256", "left_recording_id", "right_recording_id")
        if (any(not isinstance(pair.get(k), str) or not pair[k] for k in fields) or
                pair["left_recording_id"] == pair["right_recording_id"] or
                pair["left_sha256"] == pair["right_sha256"] or
                any(row.get(k) != pair[k] for row in (ref, pred) if row is not None for k in fields)):
            raise ValueError("Recurrence source/recording binding mismatch: " + key)
        identity = tuple(sorted((pair["left_sha256"], pair["right_sha256"])))
        if identity in seen:
            raise ValueError("Duplicate recurrence source pair: " + key)
        seen.add(identity)
        truth, guess = ref.get("same_speaker"), pred.get("same_speaker") if pred is not None else None
        if type(truth) is not bool or (guess is not None and type(guess) is not bool):
            raise ValueError("Recurrence labels must be reviewed booleans or prediction abstention")
        same += truth
        different += not truth
        recovered += truth and guess is True
        false_links += not truth and guess is True
        accepted += guess is not None
    return {"same_speaker_pairs": same, "different_speaker_pairs": different,
            "same_speaker_recovered": recovered, "false_same_speaker_links": false_links,
            "same_speaker_recall": recovered/same if same else None,
            "recall_wilson95": proportion_interval(recovered, same),
            "false_link_rate_wilson95": proportion_interval(false_links, different),
            "accepted_pairs": accepted, "missing_pairs": missing,
            "status": "scored" if same and different and not missing else "pending",
            "qualification": "pair_labels_only; eligibility, independence and identity authority require separate evidence"}


def evaluate_suite(inputs: dict, evidence: dict, references: dict) -> dict:
    """Development scoring, with A-row acceptance conservatively kept separate.

    Each source binds SHA256 independently in all three manifests. References are
    never inferred from output. Partial lexical labels cannot produce WER. This
    runner does not yet verify all independent/integration requirements of any
    complete A-row, so it cannot award an A-row pass.
    """
    if inputs.get("normalization") != NORMALIZATION:
        raise ValueError("Unfrozen or unsupported normalization")
    results = {}
    for key, source in inputs["items"].items():
        ref, pred = references.get("items", {}).get(key), evidence.get("items", {}).get(key)
        if not ref or not pred:
            results[key] = {"status": "pending", "reason": "missing_reference_or_prediction"}
            continue
        if not source.get("sha256") or any(x.get("sha256") != source["sha256"] for x in (ref, pred)):
            raise ValueError("Source binding mismatch: " + key)
        if pred.get("status") != "complete":
            results[key] = {"status": "pending", "reason": "prediction_not_complete"}
            continue
        row = {"status": "scored", "evidence": pred.get("evidence", []),
               "references": ref.get("receipts", [])}
        row["features"] = _feature_scores(source, ref, pred)
        if ref.get("lexical_scope") == "complete":
            lex = score_lexical(tokenize(ref["text"]), tokenize(pred["text"]))
            row["lexical"] = lex
            row["timing"] = score_timing(lex["matches"], ref.get("word_intervals", {}),
                                          pred.get("word_intervals", {}))
        else:
            row["lexical"] = {"status": "pending", "reason": "no_complete_verbatim_reference"}
        if "admitted_intervals" in pred:
            row["admission"] = score_admission(ref.get("clean_intervals", []),
                ref.get("forbidden_intervals", []), pred["admitted_intervals"],
                complete_review=ref.get("complete_admission_review", False))
        else:
            row["admission"] = {"status": "pending", "reason": "missing_admission_evidence"}
        if ref.get("no_words") is True:
            row["negative_control"] = {"accepted_words": len(tokenize(pred["text"])),
                "raw_words": len(tokenize(pred.get("raw_text", pred["text"]))),
                "status": "fail" if tokenize(pred["text"]) else "pass"}
        if (row["lexical"]["status"] == "pending" and row["admission"]["status"] == "pending"
                and "negative_control" not in row):
            row["status"] = "pending"
        results[key] = row
    scored = [r["lexical"] for r in results.values() if r.get("lexical", {}).get("reference_words", 0)]
    totals = {k: sum(x[k] for x in scored) for k in
              ("reference_words", "correct", "substitutions", "deletions", "insertions")}
    n = totals["reference_words"]
    totals.update(wer=(sum(totals[k] for k in ("substitutions", "deletions", "insertions"))/n if n else None),
                  retention=totals["correct"]/n if n else None,
                  retention_wilson95=proportion_interval(totals["correct"], n))
    def check(value, threshold, minimum=False):
        return {"value": value, "threshold": threshold,
                "direction": "minimum" if minimum else "maximum",
                "status": "pending" if value is None else
                    ("pass" if (value >= threshold if minimum else value <= threshold) else "fail")}

    checks = {"micro_wer": check(totals["wer"], .15),
              "lexical_retention": check(totals["retention"], .95, True), "per_item": {}}
    for key, row in results.items():
        timing, admission = row.get("timing", {}), row.get("admission", {})
        checks["per_item"][key] = {
            "wer": check(row.get("lexical", {}).get("wer"), .25),
            "word_timing_coverage": check(timing.get("valid_timing_coverage"), .95, True),
            "onset_p95_seconds": check(timing.get("onset_p95_seconds"), .15),
            "offset_p95_seconds": check(timing.get("offset_p95_seconds"), .15),
            "clean_admission": check(admission.get("clean_admission_rate"), .90, True),
            "known_contamination_seconds": check(admission.get("contamination_seconds")
                if admission.get("known_forbidden_seconds", 0) else None, 0),
        }
        features = row.get("features", {})
        checks["per_item"][key]["features"] = {
            "overlap_recall": check(features.get("overlap", {}).get("recall"), .90, True),
            "overlap_precision": check(features.get("overlap", {}).get("precision"), .85, True),
            "non_overlap_der": check(features.get("diarization", {}).get("der"), .15),
            "sentiment_macro_f1": check(features.get("sentiment", {}).get("macro_f1"), .80, True),
            "delivery_accepted_accuracy": check(features.get("vocal_delivery", {}).get("accepted_accuracy"), .85, True),
            "delivery_coverage": check(features.get("vocal_delivery", {}).get("coverage"), .70, True),
            "delivery_class_coverage": {label: check(value["coverage"], .50, True)
                for label, value in features.get("vocal_delivery", {}).get("per_class", {}).items()},
            "events": {label: {name: check(value[name], .80, True) for name in ("precision", "recall")}
                for label, value in features.get("events", {}).get("classes", {}).items()},
        }
    recurrence = score_recurrence(inputs.get("recurrence_pairs", {}), evidence.get("recurrence_pairs", {}),
                                  references.get("recurrence_pairs", {}))
    checks["recurrence"] = {"same_speaker_recall": check(recurrence["same_speaker_recall"], .80, True),
        "false_same_speaker_links": check(recurrence["false_same_speaker_links"]
                                          if recurrence["different_speaker_pairs"] else None, 0)}
    if recurrence["missing_pairs"]:
        for result in checks["recurrence"].values():
            result.update(status="pending", reason="missing_pair_reference_or_prediction")
    return {"status": "development_scored", "split": inputs.get("split", "unspecified"),
            "normalization": NORMALIZATION, "items": results, "lexical_totals": totals,
            "recurrence": recurrence,
            "development_checks": checks,
            "acceptance": {f"A{i:02}": {"status": "pending",
                "reason": "full_row_independent_and_integration_evidence_not_verified"} for i in range(1, 26)},
            "ready_to_adopt": False}


def _bound_path(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise ValueError("Fixture paths must be relative and cannot escape their root")
    result = (root / value).resolve(strict=True)
    if not result.is_relative_to(root) or not result.is_file():
        raise ValueError("Fixture path is outside its root or is not a file")
    return result


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wav_metadata(path: Path) -> dict:
    """Read RIFF PCM/float sample metadata without decoding or modifying audio."""
    file_size = path.stat().st_size
    with path.open("rb") as stream:
        head = stream.read(12)
        if len(head) != 12 or head[:4] != b"RIFF" or head[8:] != b"WAVE":
            raise ValueError("Fixture must be RIFF WAVE")
        riff_end = struct.unpack("<I", head[4:8])[0] + 8
        if riff_end != file_size:
            raise ValueError("WAVE container size mismatch")
        fmt = None
        format_tag = None
        data_bytes = None
        while stream.tell() < riff_end:
            header = stream.read(8)
            if len(header) != 8:
                raise ValueError("Truncated WAVE chunk header")
            name, size = struct.unpack("<4sI", header)
            end = stream.tell() + size + size % 2
            if end > riff_end:
                raise ValueError("WAVE chunk exceeds file bounds")
            if name == b"fmt ":
                if fmt is not None or size < 16:
                    raise ValueError("Invalid WAVE format chunk")
                body = stream.read(min(size, 40))
                fmt = struct.unpack("<HHIIHH", body[:16])
                format_tag = fmt[0]
                if fmt[0] == 65534:
                    if len(body) < 40:
                        raise ValueError("Truncated extensible WAVE format")
                    fmt = (struct.unpack("<H", body[24:26])[0], *fmt[1:])
            elif name == b"data":
                if data_bytes is not None:
                    raise ValueError("Multiple data chunks are not supported")
                data_bytes = size
            stream.seek(end)
        if fmt is None or data_bytes is None:
            raise ValueError("Missing WAVE format or data")
        tag, channels, rate, byte_rate, block, bits = fmt
        if (tag not in (1, 3) or channels < 1 or rate < 1 or bits not in (8, 16, 24, 32, 64)
                or block != channels * bits // 8 or byte_rate != rate * block or data_bytes % block):
            raise ValueError("Unsupported or inconsistent WAVE metadata")
        return {"sample_rate": rate, "samples": data_bytes // block, "channels": channels,
                "wav_format_tag": format_tag, "bits_per_sample": bits}


def verify_manifest(manifest: Path, fixture_root: Path) -> dict:
    report = {"status": "failed", "audio_files_verified": 0, "reference_receipts_verified": 0,
              "runtime_inference": "not_run", "acceptance": {f"A{i:02}": "pending" for i in range(1, 26)},
              "pending_fixture_sets": [], "errors": []}
    try:
        root = Path(fixture_root).resolve(strict=True)
        data = json.loads(Path(manifest).read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
            raise ValueError("Unsupported fixture manifest version")
        fixtures = data.get("fixtures")
        if not isinstance(fixtures, list) or not fixtures:
            raise ValueError("Manifest requires fixtures")
        by_id = {}
        for record in fixtures:
            key = record.get("id")
            if not isinstance(key, str) or not key or key in by_id:
                raise ValueError("Missing or duplicate fixture id")
            path = _bound_path(root, record.get("path"))
            if _digest(path) != record.get("sha256"):
                raise ValueError(f"Fixture hash mismatch: {key}")
            metadata = _wav_metadata(path)
            required = {"sample_rate", "samples", "channels"}
            if any(type(record.get(k)) is not int or record[k] != value
                   for k, value in metadata.items() if k in required or k in record):
                raise ValueError(f"Fixture sample metadata mismatch: {key}")
            by_id[key] = record
            report["audio_files_verified"] += 1
        receipt_paths = set()
        for receipt in data.get("reference_receipts", []):
            path = _bound_path(root, receipt.get("path"))
            if _digest(path) != receipt.get("sha256"):
                raise ValueError("Reference receipt hash mismatch")
            if receipt["path"] in receipt_paths:
                raise ValueError("Duplicate reference receipt")
            receipt_paths.add(receipt["path"])
            report["reference_receipts_verified"] += 1
        origin = data.get("origin_manifest")
        if origin and _digest(_bound_path(root, origin.get("path"))) != origin.get("sha256"):
            raise ValueError("Origin manifest hash mismatch")
        for reference in data.get("human_references", []):
            if not set(reference.get("receipts", [])) <= receipt_paths:
                raise ValueError("Reference names an unverified receipt")
            for key in reference.get("source_fixtures", []):
                if key not in by_id:
                    raise ValueError("Reference names an unknown fixture")
            if "source_fixture" in reference:
                source = by_id[reference["source_fixture"]]
                start, end = reference["source_sample_interval"]
                if type(start) is not int or type(end) is not int or not 0 <= start < end <= source["samples"]:
                    raise ValueError("Reference interval exceeds source samples")
                if "excerpt_fixture" in reference:
                    child = by_id[reference["excerpt_fixture"]]
                    if child["samples"] != end - start or child["sample_rate"] != source["sample_rate"]:
                        raise ValueError("Reference excerpt metadata differs from its source interval")
        report["pending_fixture_sets"] = data.get("pending_fixture_sets", [])
        report["status"] = "verified"
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify-fixtures")
    verify.add_argument("--manifest", required=True, type=Path)
    verify.add_argument("--fixture-root", required=True, type=Path)
    score = commands.add_parser("score")
    for name in ("inputs", "evidence", "references"):
        score.add_argument("--" + name, required=True, type=Path)
    score.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "score":
        try:
            report = evaluate_suite(*(json.loads(getattr(args, name).read_text(encoding="utf-8-sig"))
                                      for name in ("inputs", "evidence", "references")))
            # Refuse to overwrite an earlier scoring receipt.
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, indent=2)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            print(json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {exc}"}))
            return 1
        print(json.dumps({"status": report["status"], "output": str(args.output),
                          "ready_to_adopt": False}))
        return 0
    report = verify_manifest(args.manifest, args.fixture_root)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
