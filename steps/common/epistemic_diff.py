from __future__ import annotations

"""
Epistemic Diff Engine v1 (Integrity-Only; read-only).

Pure, deterministic comparison of two EnvelopeBundles:
    EnvelopeBundle = {
        "envelope": EpistemicReadEnvelope (dict),
        "nonActionDecisions": List[NonActionDecision] (dicts),
        "sourceLabel": str,
        "loaded_at_utc": str,
    }

Non-negotiable:
- No I/O, no logging, no mutation of inputs.
- No scoring/ranking; diffs are structural only.
- Never reads raw evidence payload text (only whitelisted identifiers like video_id/scene_id/model).
- Never implies correctness or improvement; diffs are descriptive only.
"""

import hashlib
import json
from typing import Any, Dict, Iterable, List, Literal, Mapping, Optional, Sequence, Tuple, TypedDict, cast


EPISTEMIC_DIFF_VERSION = 1

Presence = Literal["present_both", "present_a_only", "present_b_only", "absent_both"]


class EnvelopeBundle(TypedDict):
    envelope: Dict[str, Any]
    nonActionDecisions: List[Dict[str, Any]]
    sourceLabel: str
    loaded_at_utc: str


class IdentityBasis(TypedDict, total=False):
    type: str
    details: Dict[str, Any]
    initiated_ts_utc: str


class DiffKey(TypedDict):
    type: str
    value: str


class DiffSide(TypedDict, total=False):
    ts_utc: str
    pointers: Dict[str, str]
    role: str
    state: str


class DiffItem(TypedDict, total=False):
    category: str
    diff_code: str
    key: DiffKey
    a: DiffSide
    b: DiffSide


class CategorySummary(TypedDict):
    category: str
    presence: Presence
    changed: bool
    diff_count: int


class EpistemicDiff(TypedDict):
    diff_version: int
    comparison_id: str
    initiated_ts_utc: str
    identity_basis: Dict[str, Any]
    envelope_a: Dict[str, Any]
    envelope_b: Dict[str, Any]
    category_summaries: List[CategorySummary]
    diffs: List[DiffItem]
    diff_total: int
    diff_by_category: Dict[str, int]
    diff_codes: List[str]


_CATEGORY_ORDER: List[str] = [
    "identity_basis",
    "outcome",
    "candidates",
    "non_action_decisions",
    "evidence",
    "limits_aggregated",
    "limits_dont_know",
    "next_steps",
]


def _safe_str(value: Any) -> Optional[str]:
    if isinstance(value, str):
        s = value.strip()
        return s if s else None
    if value is None:
        return None
    try:
        s = str(value).strip()
        return s if s else None
    except Exception:
        return None


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _stable_json(obj: Any) -> str:
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except Exception:
        return "{}"


def _presence(a_has: bool, b_has: bool) -> Presence:
    if a_has and b_has:
        return "present_both"
    if a_has and not b_has:
        return "present_a_only"
    if (not a_has) and b_has:
        return "present_b_only"
    return "absent_both"


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _iter_candidates(envelope: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    raw = envelope.get("candidates")
    if isinstance(raw, list):
        for item in raw:
            if _is_mapping(item):
                yield cast(Mapping[str, Any], item)


def _candidate_id(candidate: Mapping[str, Any]) -> Optional[str]:
    return _safe_str(candidate.get("candidate_id"))


def _candidate_state(candidate: Mapping[str, Any]) -> Optional[str]:
    s = _safe_str(candidate.get("state"))
    return s.lower() if s else None


def _question_text(envelope: Mapping[str, Any]) -> Optional[str]:
    q = envelope.get("question")
    if _is_mapping(q):
        return _safe_str(cast(Mapping[str, Any], q).get("text"))
    return None


def _flatten_evidence(envelope: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    """
    Evidence in the same order the Justification Channel renders:
    - outcome="answer": candidates in order, then evidence per candidate in order
    - outcome="dont_know": dont_know.evidence in order
    """
    out: List[Mapping[str, Any]] = []
    outcome = _safe_str(envelope.get("outcome")) or ""
    if outcome == "answer":
        for cand in _iter_candidates(envelope):
            raw = cand.get("evidence")
            if isinstance(raw, list):
                for ev in raw:
                    if _is_mapping(ev):
                        out.append(cast(Mapping[str, Any], ev))
    elif outcome == "dont_know":
        dk = envelope.get("dont_know")
        if _is_mapping(dk):
            raw = cast(Mapping[str, Any], dk).get("evidence")
            if isinstance(raw, list):
                for ev in raw:
                    if _is_mapping(ev):
                        out.append(cast(Mapping[str, Any], ev))
    return out


def _fnv1a32_hex(text: str) -> str:
    h = 0x811C9DC5
    for b in text.encode("utf-8", errors="ignore"):
        h ^= b
        h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) & 0xFFFFFFFF
    return f"{h:08x}"


def _compute_order_fingerprint(evidence_hits: Sequence[Mapping[str, Any]]) -> str:
    """
    Stable order fingerprint matching the UI's intent (detect accidental sorting).
    Uses only safe identifiers; does not incorporate payload text.
    """
    parts: List[str] = []
    for i, h in enumerate(evidence_hits):
        payload = h.get("payload") if _is_mapping(h.get("payload")) else {}
        p = cast(Mapping[str, Any], payload) if _is_mapping(payload) else {}
        parts.append(
            "|".join(
                [
                    str(i),
                    _safe_str(h.get("role")) or "",
                    _safe_str(h.get("store")) or "",
                    _safe_str(h.get("store_ref")) or "",
                    _safe_str(h.get("embedding_id") or h.get("id")) or "",
                    _safe_str(p.get("video_id")) or "",
                    _safe_str(p.get("scene_id")) or "",
                    _safe_str(p.get("model")) or "",
                ]
            )
        )
    return f"fnv1a32:{_fnv1a32_hex(chr(10).join(parts))}"


def _aggregate_limits(envelope: Mapping[str, Any]) -> List[str]:
    """
    Matches the UI aggregation semantics:
    stable unique, collected from candidate.limits, evidence.limits, then dont_know.limits.
    """
    out: List[str] = []
    seen: set[str] = set()

    for cand in _iter_candidates(envelope):
        if isinstance(cand.get("limits"), list):
            for l in cast(List[Any], cand.get("limits")):
                s = _safe_str(l)
                if s and s not in seen:
                    seen.add(s)
                    out.append(s)

        raw_evidence = cand.get("evidence")
        if isinstance(raw_evidence, list):
            for ev in raw_evidence:
                if not _is_mapping(ev):
                    continue
                evm = cast(Mapping[str, Any], ev)
                if isinstance(evm.get("limits"), list):
                    for l in cast(List[Any], evm.get("limits")):
                        s = _safe_str(l)
                        if s and s not in seen:
                            seen.add(s)
                            out.append(s)

    dk = envelope.get("dont_know")
    if _is_mapping(dk):
        limits = cast(Mapping[str, Any], dk).get("limits")
        if isinstance(limits, list):
            for l in cast(List[Any], limits):
                s = _safe_str(l)
                if s and s not in seen:
                    seen.add(s)
                    out.append(s)

    return out


def _dont_know_limits(envelope: Mapping[str, Any]) -> List[str]:
    dk = envelope.get("dont_know")
    if not _is_mapping(dk):
        return []
    limits = cast(Mapping[str, Any], dk).get("limits")
    if not isinstance(limits, list):
        return []
    out: List[str] = []
    for l in cast(List[Any], limits):
        s = _safe_str(l)
        if s:
            out.append(s)
    return out


def _format_scope(scope: Any) -> str:
    if not _is_mapping(scope):
        return ""
    m = cast(Mapping[str, Any], scope)
    if not m:
        return ""
    parts: List[str] = []
    for k in sorted(m.keys()):
        parts.append(f"{k}={_safe_str(m.get(k)) or ''}")
    return "scope={" + ", ".join(parts) + "}"


def _aggregate_next_steps(envelope: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """
    Stable unique by (action, scope), preserving first appearance order.
    Records rationale presence only (no rationale text).
    """

    def iter_ns(src: Any) -> Iterable[Mapping[str, Any]]:
        if isinstance(src, list):
            for item in src:
                if _is_mapping(item):
                    yield cast(Mapping[str, Any], item)

    out: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for cand in _iter_candidates(envelope):
        for ns in iter_ns(cand.get("next_steps")):
            action = _safe_str(ns.get("action")) or ""
            scope_txt = _format_scope(ns.get("scope"))
            key = f"{action}::{scope_txt}"
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "action": action,
                    "scope": scope_txt,
                    "rationale_present": bool(_safe_str(ns.get("rationale"))),
                }
            )

    dk = envelope.get("dont_know")
    if _is_mapping(dk):
        for ns in iter_ns(cast(Mapping[str, Any], dk).get("next_steps")):
            action = _safe_str(ns.get("action")) or ""
            scope_txt = _format_scope(ns.get("scope"))
            key = f"{action}::{scope_txt}"
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "action": action,
                    "scope": scope_txt,
                    "rationale_present": bool(_safe_str(ns.get("rationale"))),
                }
            )

    return out


def _decision_key(decision: Mapping[str, Any]) -> Tuple[str, str, str]:
    domain = _safe_str(decision.get("domain")) or ""
    condition = _safe_str(decision.get("condition")) or ""
    required = _safe_str(decision.get("required_response")) or ""
    return (domain, condition, required)


def _decision_rationale_keys(decision: Mapping[str, Any]) -> Tuple[str, ...]:
    r = decision.get("rationale")
    if not _is_mapping(r):
        return tuple()
    keys = sorted([k for k in cast(Mapping[str, Any], r).keys() if isinstance(k, str)])
    return tuple(keys)


def _evidence_key(ev: Mapping[str, Any]) -> Tuple[str, str]:
    """
    Evidence match key per spec (content-free):
    - Preferred: embedding_id (stable across stores)
    - Fallback: store/store_ref + provenance pointer fields
    - Last resort: store/store_ref + payload identifiers (video_id/scene_id/model only)
    """
    emb = _safe_str(ev.get("embedding_id") or ev.get("id"))
    if emb:
        return ("embedding_id", emb)

    store = _safe_str(ev.get("store")) or ""
    store_ref = _safe_str(ev.get("store_ref")) or ""

    prov = ev.get("provenance")
    if _is_mapping(prov):
        p = cast(Mapping[str, Any], prov)
        parts = [
            store,
            store_ref,
            _safe_str(p.get("video_id")) or "",
            _safe_str(p.get("scene_id")) or "",
            _safe_str(p.get("modality")) or "",
            _safe_str(p.get("model")) or "",
            _safe_str(p.get("component")) or "",
            _safe_str(p.get("ts_utc")) or "",
        ]
        if any(parts):
            return ("provenance_ptr", "|".join(parts))

    payload = ev.get("payload")
    if _is_mapping(payload):
        pl = cast(Mapping[str, Any], payload)
        parts = [
            store,
            store_ref,
            _safe_str(pl.get("video_id")) or "",
            _safe_str(pl.get("scene_id")) or "",
            _safe_str(pl.get("model")) or "",
        ]
        if any(parts):
            return ("payload_ids", "|".join(parts))

    return ("unknown", f"{store}|{store_ref}")


def _evidence_meta(ev: Mapping[str, Any]) -> DiffSide:
    out: DiffSide = {}

    prov = ev.get("provenance")
    if _is_mapping(prov):
        ts = _safe_str(cast(Mapping[str, Any], prov).get("ts_utc"))
        if ts:
            out["ts_utc"] = ts
        pointers: Dict[str, str] = {}
        for k in ("modality", "model", "component"):
            v = _safe_str(cast(Mapping[str, Any], prov).get(k))
            if v:
                pointers[k] = v
        if pointers:
            out["pointers"] = pointers

    store = _safe_str(ev.get("store"))
    store_ref = _safe_str(ev.get("store_ref"))
    if store or store_ref:
        pointers = dict(out.get("pointers", {}))
        if store:
            pointers["store"] = store
        if store_ref:
            pointers["store_ref"] = store_ref
        out["pointers"] = pointers

    role = _safe_str(ev.get("role"))
    if role:
        out["role"] = role
    return out


def _match_by_key(
    a_items: Sequence[Mapping[str, Any]],
    b_items: Sequence[Mapping[str, Any]],
    key_fn,
) -> Tuple[List[Tuple[int, int, Tuple[str, str]]], List[int], List[int]]:
    """
    Stable greedy matching:
    - match by key in first-appearance order
    - returns matched pairs (idx_a, idx_b, key)
    - removed indices in A, added indices in B
    """
    b_queues: Dict[Tuple[str, str], List[int]] = {}
    for j, item in enumerate(b_items):
        k = key_fn(item)
        b_queues.setdefault(k, []).append(j)

    matched: List[Tuple[int, int, Tuple[str, str]]] = []
    removed: List[int] = []
    used_b: set[int] = set()

    for i, item in enumerate(a_items):
        k = key_fn(item)
        q = b_queues.get(k, [])
        if q:
            j = q.pop(0)
            matched.append((i, j, k))
            used_b.add(j)
        else:
            removed.append(i)

    added = [j for j in range(len(b_items)) if j not in used_b]
    return matched, removed, added


def _identity_basis_eval(envelope_a: Mapping[str, Any], envelope_b: Mapping[str, Any], basis: IdentityBasis) -> Dict[str, Any]:
    btype = _safe_str(basis.get("type")) or "custom"
    details = dict(basis.get("details") or {})

    matches = True
    mismatch_reason: Optional[str] = None

    if btype == "question_text_exact":
        ta = _question_text(envelope_a) or ""
        tb = _question_text(envelope_b) or ""
        matches = bool(ta and tb and ta == tb)
        if not matches:
            mismatch_reason = "question_text_mismatch"
    elif btype == "question_text_hash":
        ta = _question_text(envelope_a) or ""
        tb = _question_text(envelope_b) or ""
        ha = _sha256_hex(ta) if ta else ""
        hb = _sha256_hex(tb) if tb else ""
        details.setdefault("a_question_hash", ha)
        details.setdefault("b_question_hash", hb)
        matches = bool(ha and hb and ha == hb)
        if not matches:
            mismatch_reason = "question_hash_mismatch"
    elif btype == "subject_scope":
        target_vid = _safe_str(details.get("video_id"))
        target_sid = _safe_str(details.get("scene_id"))

        def extract_scopes(env: Mapping[str, Any]) -> set[Tuple[str, str]]:
            scopes: set[Tuple[str, str]] = set()
            for ev in _flatten_evidence(env):
                prov = ev.get("provenance")
                if _is_mapping(prov):
                    vid = _safe_str(cast(Mapping[str, Any], prov).get("video_id"))
                    sid = _safe_str(cast(Mapping[str, Any], prov).get("scene_id"))
                    if vid and sid:
                        scopes.add((vid, sid))
                payload = ev.get("payload")
                if _is_mapping(payload):
                    vid = _safe_str(cast(Mapping[str, Any], payload).get("video_id"))
                    sid = _safe_str(cast(Mapping[str, Any], payload).get("scene_id"))
                    if vid and sid:
                        scopes.add((vid, sid))
            return scopes

        scopes_a = extract_scopes(envelope_a)
        scopes_b = extract_scopes(envelope_b)
        details.setdefault("a_scopes_count", len(scopes_a))
        details.setdefault("b_scopes_count", len(scopes_b))

        if target_vid and target_sid:
            matches = (target_vid, target_sid) in scopes_a and (target_vid, target_sid) in scopes_b
            if not matches:
                mismatch_reason = "subject_scope_target_missing"
        else:
            matches = bool(scopes_a and scopes_b and scopes_a == scopes_b)
            if not matches:
                mismatch_reason = "subject_scope_mismatch"
    else:
        matches = False
        mismatch_reason = "custom_basis_not_evaluable"

    out: Dict[str, Any] = {"type": btype, "details": details, "matches": matches}
    if not matches and mismatch_reason:
        out["mismatch_reason"] = mismatch_reason
    return out


def compute_epistemic_diff(bundle_a: EnvelopeBundle, bundle_b: EnvelopeBundle, identity_basis: IdentityBasis) -> EpistemicDiff:
    """
    Compute EpistemicDiff v1 from two EnvelopeBundles.
    """
    env_a = bundle_a.get("envelope") or {}
    env_b = bundle_b.get("envelope") or {}
    decisions_a = bundle_a.get("nonActionDecisions") or []
    decisions_b = bundle_b.get("nonActionDecisions") or []

    envelope_a = cast(Mapping[str, Any], env_a if _is_mapping(env_a) else {})
    envelope_b = cast(Mapping[str, Any], env_b if _is_mapping(env_b) else {})

    identity = _identity_basis_eval(envelope_a, envelope_b, identity_basis)

    comparison_seed = {
        "diff_version": EPISTEMIC_DIFF_VERSION,
        "identity_basis": {"type": identity.get("type"), "details": identity.get("details")},
        "a": {"source": bundle_a.get("sourceLabel"), "loaded_at": bundle_a.get("loaded_at_utc")},
        "b": {"source": bundle_b.get("sourceLabel"), "loaded_at": bundle_b.get("loaded_at_utc")},
    }
    comparison_id = f"ediff1_{_sha256_hex(_stable_json(comparison_seed))[:24]}"

    initiated_ts_utc = _safe_str(identity_basis.get("initiated_ts_utc"))
    if not initiated_ts_utc:
        a_ts = _safe_str(bundle_a.get("loaded_at_utc")) or ""
        b_ts = _safe_str(bundle_b.get("loaded_at_utc")) or ""
        initiated_ts_utc = max(a_ts, b_ts) if (a_ts and b_ts) else (a_ts or b_ts or "")

    diffs: List[DiffItem] = []

    if identity.get("matches") is False:
        diffs.append(
            {
                "category": "identity_basis",
                "diff_code": "identity_basis_mismatch",
                "key": {"type": "identity_basis", "value": _safe_str(identity.get("type")) or "custom"},
            }
        )

    out_a = _safe_str(envelope_a.get("outcome")) or ""
    out_b = _safe_str(envelope_b.get("outcome")) or ""
    if out_a != out_b:
        diffs.append(
            {
                "category": "outcome",
                "diff_code": "outcome_changed",
                "key": {"type": "outcome", "value": "outcome"},
                "a": {"state": out_a} if out_a else {},
                "b": {"state": out_b} if out_b else {},
            }
        )

    # Candidates diff
    cands_a = list(_iter_candidates(envelope_a))
    cands_b = list(_iter_candidates(envelope_b))
    ids_a = [_candidate_id(c) or "" for c in cands_a if _candidate_id(c)]
    ids_b = [_candidate_id(c) or "" for c in cands_b if _candidate_id(c)]
    set_a = set(ids_a)
    set_b = set(ids_b)

    if set_a == set_b and ids_a != ids_b and len(ids_a) > 1:
        diffs.append(
            {
                "category": "candidates",
                "diff_code": "candidate_order_changed",
                "key": {"type": "candidates_order", "value": "candidate_id"},
            }
        )

    state_a: Dict[str, Optional[str]] = {(_candidate_id(c) or ""): _candidate_state(c) for c in cands_a if _candidate_id(c)}
    state_b: Dict[str, Optional[str]] = {(_candidate_id(c) or ""): _candidate_state(c) for c in cands_b if _candidate_id(c)}

    for cid in ids_a:
        if cid in set_b and (state_a.get(cid) or "") != (state_b.get(cid) or ""):
            diffs.append(
                {
                    "category": "candidates",
                    "diff_code": "candidate_state_changed",
                    "key": {"type": "candidate_id", "value": cid},
                    "a": {"state": state_a.get(cid) or ""},
                    "b": {"state": state_b.get(cid) or ""},
                }
            )

    for cid in ids_a:
        if cid and cid not in set_b:
            diffs.append({"category": "candidates", "diff_code": "candidate_removed", "key": {"type": "candidate_id", "value": cid}})

    for cid in ids_b:
        if cid and cid not in set_a:
            diffs.append({"category": "candidates", "diff_code": "candidate_added", "key": {"type": "candidate_id", "value": cid}})

    # Non-action decisions diff
    decs_a = [cast(Mapping[str, Any], d) for d in decisions_a if _is_mapping(d)]
    decs_b = [cast(Mapping[str, Any], d) for d in decisions_b if _is_mapping(d)]
    keys_a = [_decision_key(d) for d in decs_a]
    keys_b = [_decision_key(d) for d in decs_b]
    set_dec_a = set(keys_a)
    set_dec_b = set(keys_b)

    if set_dec_a == set_dec_b and keys_a != keys_b and len(keys_a) > 1:
        diffs.append(
            {
                "category": "non_action_decisions",
                "diff_code": "decision_order_changed",
                "key": {"type": "decisions_order", "value": "domain|condition|required_response"},
            }
        )

    rationale_a: Dict[Tuple[str, str, str], Tuple[str, ...]] = {k: _decision_rationale_keys(d) for k, d in zip(keys_a, decs_a)}
    rationale_b: Dict[Tuple[str, str, str], Tuple[str, ...]] = {k: _decision_rationale_keys(d) for k, d in zip(keys_b, decs_b)}

    for k in keys_a:
        if k in set_dec_b and rationale_a.get(k, tuple()) != rationale_b.get(k, tuple()):
            diffs.append(
                {
                    "category": "non_action_decisions",
                    "diff_code": "decision_rationale_keys_changed",
                    "key": {"type": "decision", "value": "|".join(k)},
                }
            )

    for k in keys_a:
        if k not in set_dec_b:
            diffs.append({"category": "non_action_decisions", "diff_code": "decision_removed", "key": {"type": "decision", "value": "|".join(k)}})

    for k in keys_b:
        if k not in set_dec_a:
            diffs.append({"category": "non_action_decisions", "diff_code": "decision_added", "key": {"type": "decision", "value": "|".join(k)}})

    # Evidence diff (order/presence only; no payload text)
    evidence_a = _flatten_evidence(envelope_a)
    evidence_b = _flatten_evidence(envelope_b)

    matched, removed_idx, added_idx = _match_by_key(evidence_a, evidence_b, _evidence_key)

    if not removed_idx and not added_idx and matched:
        b_indices_in_a_order = [j for (_, j, _) in matched]
        if b_indices_in_a_order != sorted(b_indices_in_a_order) and len(b_indices_in_a_order) > 1:
            diffs.append({"category": "evidence", "diff_code": "evidence_order_changed", "key": {"type": "evidence_order", "value": "evidence"}})

    for i, j, k in matched:
        a_item = evidence_a[i]
        b_item = evidence_b[j]

        a_store = _safe_str(a_item.get("store")) or ""
        b_store = _safe_str(b_item.get("store")) or ""
        a_ref = _safe_str(a_item.get("store_ref")) or ""
        b_ref = _safe_str(b_item.get("store_ref")) or ""
        if a_store != b_store or a_ref != b_ref:
            diffs.append(
                {
                    "category": "evidence",
                    "diff_code": "evidence_store_changed",
                    "key": {"type": k[0], "value": k[1]},
                    "a": _evidence_meta(a_item),
                    "b": _evidence_meta(b_item),
                }
            )

        a_role = _safe_str(a_item.get("role")) or ""
        b_role = _safe_str(b_item.get("role")) or ""
        if a_role != b_role:
            diffs.append(
                {
                    "category": "evidence",
                    "diff_code": "evidence_role_changed",
                    "key": {"type": k[0], "value": k[1]},
                    "a": _evidence_meta(a_item),
                    "b": _evidence_meta(b_item),
                }
            )

    for i in removed_idx:
        k = _evidence_key(evidence_a[i])
        diffs.append(
            {
                "category": "evidence",
                "diff_code": "evidence_removed",
                "key": {"type": k[0], "value": k[1]},
                "a": _evidence_meta(evidence_a[i]),
            }
        )

    for j in added_idx:
        k = _evidence_key(evidence_b[j])
        diffs.append(
            {
                "category": "evidence",
                "diff_code": "evidence_added",
                "key": {"type": k[0], "value": k[1]},
                "b": _evidence_meta(evidence_b[j]),
            }
        )

    # Limits diffs (aggregated + dont_know)
    lim_a = _aggregate_limits(envelope_a)
    lim_b = _aggregate_limits(envelope_b)
    set_lim_a = set(lim_a)
    set_lim_b = set(lim_b)

    for l in lim_a:
        if l not in set_lim_b:
            diffs.append({"category": "limits_aggregated", "diff_code": "limit_removed", "key": {"type": "limit", "value": l}})
    for l in lim_b:
        if l not in set_lim_a:
            diffs.append({"category": "limits_aggregated", "diff_code": "limit_added", "key": {"type": "limit", "value": l}})

    dk_lim_a = _dont_know_limits(envelope_a)
    dk_lim_b = _dont_know_limits(envelope_b)
    set_dk_a = set(dk_lim_a)
    set_dk_b = set(dk_lim_b)
    for l in dk_lim_a:
        if l not in set_dk_b:
            diffs.append({"category": "limits_dont_know", "diff_code": "limit_removed", "key": {"type": "limit", "value": l}})
    for l in dk_lim_b:
        if l not in set_dk_a:
            diffs.append({"category": "limits_dont_know", "diff_code": "limit_added", "key": {"type": "limit", "value": l}})

    # Next steps diffs (aggregated)
    ns_a = _aggregate_next_steps(envelope_a)
    ns_b = _aggregate_next_steps(envelope_b)

    by_action_a: Dict[str, List[Dict[str, Any]]] = {}
    by_action_b: Dict[str, List[Dict[str, Any]]] = {}
    for ns in ns_a:
        by_action_a.setdefault(ns["action"], []).append(ns)
    for ns in ns_b:
        by_action_b.setdefault(ns["action"], []).append(ns)

    scope_changed_actions: set[str] = set()
    for action in [ns["action"] for ns in ns_a]:
        if action not in by_action_b:
            continue
        if len(by_action_a.get(action, [])) == 1 and len(by_action_b.get(action, [])) == 1:
            a_scope = _safe_str(by_action_a[action][0].get("scope")) or ""
            b_scope = _safe_str(by_action_b[action][0].get("scope")) or ""
            if a_scope != b_scope:
                scope_changed_actions.add(action)
                diffs.append(
                    {
                        "category": "next_steps",
                        "diff_code": "next_step_scope_changed",
                        "key": {"type": "next_step_action", "value": f"{action}|a={a_scope}|b={b_scope}"},
                    }
                )

    key_to_rationale_a: Dict[str, bool] = {
        f"{ns['action']}::{ns.get('scope') or ''}": bool(ns.get("rationale_present")) for ns in ns_a
    }
    key_to_rationale_b: Dict[str, bool] = {
        f"{ns['action']}::{ns.get('scope') or ''}": bool(ns.get("rationale_present")) for ns in ns_b
    }
    for k in [f"{ns['action']}::{ns.get('scope') or ''}" for ns in ns_a]:
        if k in key_to_rationale_b and key_to_rationale_a.get(k) != key_to_rationale_b.get(k):
            diffs.append(
                {"category": "next_steps", "diff_code": "next_step_rationale_presence_changed", "key": {"type": "next_step", "value": k}}
            )

    keys_ns_a = [f"{ns['action']}::{ns.get('scope') or ''}" for ns in ns_a]
    keys_ns_b = [f"{ns['action']}::{ns.get('scope') or ''}" for ns in ns_b]
    set_ns_a = set(keys_ns_a)
    set_ns_b = set(keys_ns_b)
    for k in keys_ns_a:
        action = k.split("::", 1)[0] if "::" in k else k
        if action in scope_changed_actions:
            continue
        if k not in set_ns_b:
            diffs.append({"category": "next_steps", "diff_code": "next_step_removed", "key": {"type": "next_step", "value": k}})
    for k in keys_ns_b:
        action = k.split("::", 1)[0] if "::" in k else k
        if action in scope_changed_actions:
            continue
        if k not in set_ns_a:
            diffs.append({"category": "next_steps", "diff_code": "next_step_added", "key": {"type": "next_step", "value": k}})
    summary_a = {
        "sourceLabel": _safe_str(bundle_a.get("sourceLabel")) or "",
        "loaded_at_utc": _safe_str(bundle_a.get("loaded_at_utc")) or "",
        "read_model_version": envelope_a.get("read_model_version"),
        "retrieval_context": _safe_str(envelope_a.get("retrieval_context")) or "",
        "outcome": out_a,
        "counts": {
            "candidates": len(ids_a),
            "evidence_hits": len(evidence_a),
            "non_action_decisions": len(decs_a),
        },
        "order_fingerprint": _compute_order_fingerprint(evidence_a),
        "warning_codes": [],
    }
    summary_b = {
        "sourceLabel": _safe_str(bundle_b.get("sourceLabel")) or "",
        "loaded_at_utc": _safe_str(bundle_b.get("loaded_at_utc")) or "",
        "read_model_version": envelope_b.get("read_model_version"),
        "retrieval_context": _safe_str(envelope_b.get("retrieval_context")) or "",
        "outcome": out_b,
        "counts": {
            "candidates": len(ids_b),
            "evidence_hits": len(evidence_b),
            "non_action_decisions": len(decs_b),
        },
        "order_fingerprint": _compute_order_fingerprint(evidence_b),
        "warning_codes": [],
    }

    diff_by_category: Dict[str, int] = {cat: 0 for cat in _CATEGORY_ORDER}
    for d in diffs:
        cat = _safe_str(d.get("category")) or ""
        diff_by_category[cat] = diff_by_category.get(cat, 0) + 1

    category_summaries: List[CategorySummary] = []
    for cat in _CATEGORY_ORDER:
        if cat == "identity_basis":
            pres = "present_both"
        elif cat == "outcome":
            pres = _presence(bool(out_a), bool(out_b))
        elif cat == "candidates":
            pres = _presence(len(ids_a) > 0, len(ids_b) > 0)
        elif cat == "non_action_decisions":
            pres = _presence(bool(summary_a["counts"]["non_action_decisions"]), bool(summary_b["counts"]["non_action_decisions"]))
        elif cat == "evidence":
            pres = _presence(len(evidence_a) > 0, len(evidence_b) > 0)
        elif cat == "limits_aggregated":
            pres = _presence(len(lim_a) > 0, len(lim_b) > 0)
        elif cat == "limits_dont_know":
            pres = _presence(len(dk_lim_a) > 0, len(dk_lim_b) > 0)
        elif cat == "next_steps":
            pres = _presence(len(ns_a) > 0, len(ns_b) > 0)
        else:
            pres = "absent_both"

        cnt = diff_by_category.get(cat, 0)
        category_summaries.append({"category": cat, "presence": pres, "changed": cnt > 0, "diff_count": cnt})

    diff_codes: List[str] = []
    seen_codes: set[str] = set()
    for d in diffs:
        code = _safe_str(d.get("diff_code")) or ""
        if code and code not in seen_codes:
            seen_codes.add(code)
            diff_codes.append(code)

    return {
        "diff_version": EPISTEMIC_DIFF_VERSION,
        "comparison_id": comparison_id,
        "initiated_ts_utc": initiated_ts_utc,
        "identity_basis": identity,
        "envelope_a": summary_a,
        "envelope_b": summary_b,
        "category_summaries": category_summaries,
        "diffs": diffs,
        "diff_total": len(diffs),
        "diff_by_category": diff_by_category,
        "diff_codes": diff_codes,
    }
