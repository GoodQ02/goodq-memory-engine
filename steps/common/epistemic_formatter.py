# This formatter assembles epistemic structure only. It must not be used to gate, rank, filter, or refuse.
from __future__ import annotations

"""
Epistemic Read Formatter (Integrity-Only)

This module assembles an EpistemicReadEnvelope (contract v1) from already-retrieved hits.

Non-authoritative by design:
- No policy coupling (does not gate, refuse, rerank, filter, or score retrieval).
- No thresholds (except minimal, label-only heuristics used to populate `limits` tags).
- No automatic truth claims: `answer_text` is intentionally non-persuasive and evidence-first.

Inputs are expected to be sanitized by the caller:
- `question` should be a safe dict like {"text": "..."}.
- `retrieval_context` should be a sanitized origin label (no raw user query).
"""

from dataclasses import dataclass
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple


EPISTEMIC_READ_MODEL_VERSION = 1

_EVIDENCE_ROLES = {"support", "contradict", "related", "meta"}
_EPISTEMIC_STATES = {
    "supported",
    "partially_supported",
    "conflicted",
    "stale",
    "unsupported_but_related",
    "unknown",
}


def _safe_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return s if s else None
    try:
        s = str(v).strip()
        return s if s else None
    except Exception:
        return None


def _default_confidence_payload() -> Dict[str, Any]:
    return {
        "intrinsic": None,
        "source": None,
        "temporal": None,
        "consistency": None,
        "overall": None,
    }


def _normalize_question(question: Any) -> Dict[str, Any]:
    if isinstance(question, dict):
        out = dict(question)
        if "text" not in out:
            out["text"] = ""
        if not isinstance(out.get("text"), str):
            out["text"] = _safe_str(out.get("text")) or ""
        return out
    if isinstance(question, str):
        return {"text": question}
    return {"text": _safe_str(question) or ""}


def _normalize_retrieval_context(ctx: Any) -> Optional[str]:
    s = _safe_str(ctx)
    if not s:
        return None
    try:
        # Prefer the shared normalizer when available.
        from steps.common.retrieval_events import normalize_retrieval_context

        return normalize_retrieval_context(s)
    except Exception:
        return s


def _infer_intents(question_text: str) -> Tuple[bool, set[str]]:
    """
    Return (explicit_intents, intents) where intents is a set of modality groups:
    {"visual", "audio", "text"}.

    This is a best-effort hint to label evidence as support vs related.
    It must not be used as a policy gate.
    """
    q = (question_text or "").lower()
    intents: set[str] = set()

    if re.search(r"\b(audio|sound|hear|music|song|voice|speaker)\b", q):
        intents.add("audio")
    if re.search(r"\b(transcript|caption|text|quote|words|subtitle|said|saying)\b", q):
        intents.add("text")
    if re.search(r"\b(see|show|look|image|picture|frame|visual)\b", q):
        intents.add("visual")

    if not intents:
        return False, {"visual", "audio", "text"}
    return True, intents


def _question_time_sensitive(question_text: str) -> bool:
    q = (question_text or "").lower()
    return bool(re.search(r"\b(now|today|current|latest|recent|still|anymore)\b", q))


def _infer_modality_group(hit: Dict[str, Any]) -> Optional[str]:
    payload = hit.get("payload") if isinstance(hit.get("payload"), dict) else {}
    prov = hit.get("provenance") if isinstance(hit.get("provenance"), dict) else {}

    raw = payload.get("modality") or payload.get("model") or prov.get("modality") or prov.get("model")
    s = _safe_str(raw)
    if not s:
        return None
    s = s.lower()

    if s in ("clip", "dino", "vision", "visual"):
        return "visual"
    if s in ("audio", "clap"):
        return "audio"
    if s in ("text", "frame_text", "audio_transcript", "transcript", "caption"):
        return "text"
    return s


def _vector_debug_enabled() -> bool:
    val = os.environ.get("GOODQ_VECTOR_DEBUG", "")
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


def _role_override(hit: Dict[str, Any]) -> Optional[str]:
    """
    DEBUG/TEST ONLY: allow a caller to force EvidenceHit.role via hit["evidence_role"].
    This is ignored unless GOODQ_VECTOR_DEBUG=1.
    """
    if not _vector_debug_enabled():
        return None
    raw = hit.get("evidence_role")
    s = _safe_str(raw)
    if s:
        s = s.lower()
        if s in _EVIDENCE_ROLES:
            return s
    return None


def _infer_store_ref(hit: Dict[str, Any]) -> Optional[str]:
    payload = hit.get("payload") if isinstance(hit.get("payload"), dict) else {}
    for key in ("store_ref", "collection", "index", "index_path"):
        s = _safe_str(payload.get(key))
        if s:
            return s

    prov = hit.get("provenance") if isinstance(hit.get("provenance"), dict) else {}
    targets = prov.get("targets") if isinstance(prov.get("targets"), dict) else {}
    refs: List[str] = []
    for t in targets.values():
        if not isinstance(t, dict):
            continue
        r = _safe_str(t.get("ref"))
        if r:
            refs.append(r)
    refs = list(dict.fromkeys(refs))  # stable unique
    return refs[0] if len(refs) == 1 else None


def _infer_evidence_hit(hit: Dict[str, Any], *, intents: set[str]) -> Dict[str, Any]:
    payload = hit.get("payload") if isinstance(hit.get("payload"), dict) else {}
    prov = hit.get("provenance") if isinstance(hit.get("provenance"), dict) else None
    confidence = hit.get("confidence") if isinstance(hit.get("confidence"), dict) else _default_confidence_payload()

    evidence_limits: List[str] = []

    role = _role_override(hit)
    if role is None:
        if not isinstance(prov, dict):
            role = "meta"
            evidence_limits.append("provenance_missing")
        else:
            attempted = bool(prov.get("attempted")) if "attempted" in prov else None
            committed = bool(prov.get("committed")) if "committed" in prov else None
            if attempted is True and committed is False:
                role = "meta"
                evidence_limits.append("uncommitted_evidence")
                reason = _safe_str(prov.get("reason"))
                if reason:
                    evidence_limits.append(f"commit_reason:{reason}")
            else:
                group = _infer_modality_group(hit)
                role = "support" if (group in intents) else "related"

    # Temporal confidence is informational only; we surface a tag when it appears low-ish.
    try:
        temporal = confidence.get("temporal") if isinstance(confidence, dict) else None
        if isinstance(temporal, (int, float)):
            if float(temporal) < 0.5:
                evidence_limits.append("stale_possible")
    except Exception:
        pass

    evidence: Dict[str, Any] = {
        "role": role,
        "store": _safe_str(hit.get("store")),
        "store_ref": _infer_store_ref(hit),
        "embedding_id": _safe_str(hit.get("id")),
        "score": None,
        "payload": payload,
        "provenance": prov if isinstance(prov, dict) else None,
        "confidence": confidence if isinstance(confidence, dict) else _default_confidence_payload(),
        "limits": evidence_limits,
    }

    try:
        score = hit.get("score")
        if isinstance(score, (int, float)):
            evidence["score"] = float(score)
    except Exception:
        pass

    return evidence


def _candidate_key(ev: Dict[str, Any]) -> Tuple[str, str]:
    payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
    prov = ev.get("provenance") if isinstance(ev.get("provenance"), dict) else {}
    video_id = _safe_str(payload.get("video_id")) or _safe_str(prov.get("video_id")) or "unknown"
    scene_id = _safe_str(payload.get("scene_id")) or _safe_str(prov.get("scene_id")) or "unknown"
    return video_id, scene_id


@dataclass
class _CandidateAcc:
    candidate_id: str
    video_id: str
    scene_id: str
    evidence: List[Dict[str, Any]]
    source_hit_order: List[int]


def _derive_candidate_state(
    candidate: _CandidateAcc, *, explicit_intents: bool, intents: set[str], time_sensitive: bool
) -> Tuple[str, List[str], List[Dict[str, Any]]]:
    evidence = candidate.evidence
    support = [e for e in evidence if e.get("role") == "support"]
    contradict = [e for e in evidence if e.get("role") == "contradict"]
    related = [e for e in evidence if e.get("role") == "related"]
    meta = [e for e in evidence if e.get("role") == "meta"]

    limits: List[str] = []
    if meta:
        for e in meta:
            for lim in e.get("limits") or []:
                if isinstance(lim, str) and lim and lim not in limits:
                    limits.append(lim)

    if explicit_intents:
        present_groups = set(_infer_modality_group({"payload": e.get("payload"), "provenance": e.get("provenance")}) for e in support)
        for g in sorted(intents):
            if g not in present_groups:
                limits.append(f"expected_modality_missing:{g}")

    stale_possible = any("stale_possible" in (e.get("limits") or []) for e in support)
    if stale_possible:
        limits.append("stale_possible")

    # Evidence-shape mapping (no scoring/thresholds).
    if support and contradict:
        state = "conflicted"
    elif support:
        if time_sensitive and stale_possible:
            state = "stale"
        elif limits:
            state = "partially_supported"
        else:
            state = "supported"
    elif related:
        state = "unsupported_but_related"
    else:
        state = "unknown"

    if state not in _EPISTEMIC_STATES:
        state = "unknown"

    next_steps: List[Dict[str, Any]] = []
    for lim in limits:
        if not isinstance(lim, str):
            continue
        if lim.startswith("expected_modality_missing:"):
            mod = lim.split(":", 1)[1]
            next_steps.append(
                {
                    "action": f"retrieve modality {mod}",
                    "rationale": "query asked for evidence in a specific modality group",
                    "scope": {"video_id": candidate.video_id, "scene_id": candidate.scene_id, "modality_group": mod},
                }
            )
    if "provenance_missing" in limits:
        next_steps.append(
            {
                "action": "inspect memory_commit_events for this scene",
                "rationale": "provenance is missing, so commit evidence cannot be correlated",
                "scope": {"video_id": candidate.video_id, "scene_id": candidate.scene_id},
            }
        )

    return state, limits, next_steps


def format_epistemic_read(
    *,
    question: Any,
    retrieval_context: Any,
    hits: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Assemble an EpistemicReadEnvelope (contract v1) from retrieval hits.

    Determinism: identical inputs (including hit ordering and fields) produce identical outputs.
    """
    q = _normalize_question(question)
    ctx = _normalize_retrieval_context(retrieval_context)
    explicit_intents, intents = _infer_intents(q.get("text") or "")
    time_sensitive = _question_time_sensitive(q.get("text") or "")

    # Preserve incoming order (do not rerank); group by (video_id, scene_id).
    candidates: Dict[Tuple[str, str], _CandidateAcc] = {}
    ordered_keys: List[Tuple[str, str]] = []

    any_support = False
    evidence_hits_flat: List[Dict[str, Any]] = []

    for hit in hits or []:
        hit_index = len(evidence_hits_flat)
        if not isinstance(hit, dict):
            continue
        ev = _infer_evidence_hit(hit, intents=intents)
        evidence_hits_flat.append(ev)
        if ev.get("role") == "support":
            any_support = True

        video_id, scene_id = _candidate_key(ev)
        key = (video_id, scene_id)
        if key not in candidates:
            candidates[key] = _CandidateAcc(
                candidate_id=f"scene:{video_id}:{scene_id}",
                video_id=video_id,
                scene_id=scene_id,
                evidence=[],
                source_hit_order=[],
            )
            ordered_keys.append(key)
        candidates[key].evidence.append(ev)
        candidates[key].source_hit_order.append(hit_index)

    envelope: Dict[str, Any] = {
        "read_model_version": EPISTEMIC_READ_MODEL_VERSION,
        "question": q,
        "retrieval_context": ctx,
        "outcome": "answer" if any_support else "dont_know",
        "candidates": [],
    }

    if not any_support:
        # Determine dont_know state from evidence shape (related/meta only).
        any_related = any(e.get("role") == "related" for e in evidence_hits_flat)
        dk_state = "unsupported_but_related" if any_related else "unknown"
        envelope["dont_know"] = {
            "state": dk_state,
            "explanation": "no_support_evidence: formatter found no EvidenceHit(role='support') for this question",
            "evidence": evidence_hits_flat,
            "limits": ["no_support_evidence"],
            "next_steps": [{"action": "broaden retrieval modalities", "rationale": "no supporting evidence was identified"}],
        }
        return envelope

    # Answer outcome: emit candidates (one per scene key).
    out_candidates: List[Dict[str, Any]] = []
    for key in ordered_keys:
        cand = candidates[key]
        state, limits, next_steps = _derive_candidate_state(
            cand, explicit_intents=explicit_intents, intents=intents, time_sensitive=time_sensitive
        )
        out_candidates.append(
            {
                "candidate_id": cand.candidate_id,
                "state": state,
                "answer_text": f"candidate_scene video_id={cand.video_id} scene_id={cand.scene_id}",
                "confidence": _default_confidence_payload(),
                "evidence": cand.evidence,
                "source_hit_order": list(cand.source_hit_order),
                "limits": limits,
                "next_steps": next_steps,
            }
        )

    envelope["candidates"] = out_candidates
    return envelope
