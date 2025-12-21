from __future__ import annotations

"""
Non-Action Contract v1 (declarative; integrity-only).

This module defines *when the system must not proceed* across four domains:
- answer (LLM output)
- ingest (pipeline registration/execution)
- train (dataset export/training)
- act (agent/tool actions)

Non-negotiable:
- No enforcement/wiring here (returns decisions only).
- No thresholds/scoring (structural checks only).
- Pure helpers only: no I/O, no logging, no mutation.
"""

from enum import Enum
from typing import Any, Dict, Iterable, List, Literal, Mapping, Optional, Sequence, TypedDict, cast


NON_ACTION_CONTRACT_VERSION = 1

NonActionDomain = Literal["answer", "ingest", "train", "act"]
NonActionRequiredResponse = Literal["refuse", "defer", "dont_know", "silent"]


class NonActionCondition(str, Enum):
    # Answering
    MISSING_EPISTEMIC_ENVELOPE = "missing_epistemic_envelope"
    INSUFFICIENT_EVIDENCE_SHAPE = "insufficient_evidence_shape"
    ENVELOPE_OUTCOME_DONT_KNOW = "envelope_outcome_dont_know"
    SENSITIVE_SOURCE_WITHOUT_CONSENT = "sensitive_source_without_consent"
    CONFLICT_WITHOUT_NEXT_STEPS = "conflict_without_next_steps"

    # Ingestion
    INGEST_BLOCKED_BY_DESIGN = "ingest_blocked_by_design"
    SENSITIVE_STAGING_REQUIRED = "sensitive_staging_required"
    INGEST_ADAPTER_MISSING = "ingest_adapter_missing"
    INGEST_PIPELINE_NOT_REGISTERED = "ingest_pipeline_not_registered"

    # Training / dataset export
    TRAINING_VAULT_MANIFEST_REQUIRED = "training_vault_manifest_required"
    TRAINING_HUMAN_APPROVAL_REQUIRED = "training_human_approval_required"
    TRAINING_MIXED_PROVENANCE = "training_mixed_provenance"
    TRAINING_BLOCKED_BY_DESIGN = "training_blocked_by_design"

    # Agent / tool action
    ACT_REQUIRES_EPISTEMIC_ENVELOPE = "act_requires_epistemic_envelope"
    ACT_REQUIRES_JUSTIFICATION_PAYLOAD = "act_requires_justification_payload"
    ACT_BLOCKED_ON_CONFLICT = "act_blocked_on_conflict"


class NonActionDecision(TypedDict):
    contract_version: int
    domain: NonActionDomain
    condition: str
    required_response: NonActionRequiredResponse
    rationale: Dict[str, Any]


class SensitiveRequestContext(TypedDict, total=False):
    """
    Sensitivity markers for answer/ingest/train decisions.

    `consent_granted` is an explicit, caller-provided flag. This contract does not infer consent.
    """

    source_class: str  # e.g. "messages" | "health" | "wearables" | other
    sensitive_requested: bool
    consent_granted: bool


class IngestRequestContext(TypedDict, total=False):
    source_kind: str  # e.g. "health_auto_export" | "chat_export" | "wearables_capture"
    sensitive: bool
    blocked_by_design: bool
    staged_under_processing: bool
    under_vault_root: bool
    adapter_present: bool
    pipeline_registered: bool


class TrainingRequestContext(TypedDict, total=False):
    blocked_by_design: bool
    includes_sensitive_sources: bool
    vault_manifest_present: bool
    human_approved: bool
    mixed_provenance_sources: bool


class ActionRequestContext(TypedDict, total=False):
    intends_tool_action: bool
    requires_epistemic_envelope: bool
    requires_justification_payload: bool
    has_justification_payload: bool


class NonActionContext(TypedDict, total=False):
    """
    Inputs for contract evaluation.

    Notes:
    - `epistemic_envelope` is expected to be the EpistemicReadEnvelope (contract v1) dict.
    - All flags are caller-provided; this module does not read config or runtime state.
    """

    domains: List[NonActionDomain]
    epistemic_envelope: Dict[str, Any]
    sensitive: SensitiveRequestContext
    ingest: IngestRequestContext
    train: TrainingRequestContext
    act: ActionRequestContext


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _iter_candidates(envelope: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    raw = envelope.get("candidates")
    if isinstance(raw, list):
        for item in raw:
            if _is_mapping(item):
                yield cast(Mapping[str, Any], item)


def _candidate_state(candidate: Mapping[str, Any]) -> Optional[str]:
    raw = candidate.get("state")
    if isinstance(raw, str) and raw.strip():
        return raw.strip().lower()
    return None


def _iter_evidence(candidate: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    raw = candidate.get("evidence")
    if isinstance(raw, list):
        for item in raw:
            if _is_mapping(item):
                yield cast(Mapping[str, Any], item)


def _evidence_role(ev: Mapping[str, Any]) -> Optional[str]:
    raw = ev.get("role")
    if isinstance(raw, str) and raw.strip():
        return raw.strip().lower()
    return None


def _has_support_evidence(envelope: Mapping[str, Any]) -> bool:
    for cand in _iter_candidates(envelope):
        for ev in _iter_evidence(cand):
            if _evidence_role(ev) == "support":
                return True
    return False


def _any_conflicted_candidate(envelope: Mapping[str, Any]) -> bool:
    return any(_candidate_state(c) == "conflicted" for c in _iter_candidates(envelope))


def _conflict_without_next_steps(envelope: Mapping[str, Any]) -> bool:
    for cand in _iter_candidates(envelope):
        if _candidate_state(cand) != "conflicted":
            continue
        ns = cand.get("next_steps")
        if not (isinstance(ns, list) and len(ns) > 0):
            return True
    return False


def _decision(
    *,
    domain: NonActionDomain,
    condition: NonActionCondition,
    required_response: NonActionRequiredResponse,
    rationale: Dict[str, Any],
) -> NonActionDecision:
    return {
        "contract_version": NON_ACTION_CONTRACT_VERSION,
        "domain": domain,
        "condition": condition.value,
        "required_response": required_response,
        "rationale": dict(rationale or {}),
    }


def _evaluate_answer(ctx: NonActionContext) -> List[NonActionDecision]:
    decisions: List[NonActionDecision] = []

    sensitive = ctx.get("sensitive") if _is_mapping(ctx.get("sensitive")) else {}
    if _safe_bool(sensitive.get("sensitive_requested"), False) and not _safe_bool(sensitive.get("consent_granted"), False):
        decisions.append(
            _decision(
                domain="answer",
                condition=NonActionCondition.SENSITIVE_SOURCE_WITHOUT_CONSENT,
                required_response="refuse",
                rationale={"source_class": sensitive.get("source_class"), "consent_granted": False},
            )
        )

    env = ctx.get("epistemic_envelope")
    if not _is_mapping(env):
        decisions.append(
            _decision(
                domain="answer",
                condition=NonActionCondition.MISSING_EPISTEMIC_ENVELOPE,
                required_response="silent",
                rationale={"missing": "epistemic_envelope"},
            )
        )
        return decisions

    envelope = cast(Mapping[str, Any], env)
    outcome = envelope.get("outcome")
    if isinstance(outcome, str) and outcome.strip().lower() == "dont_know":
        decisions.append(
            _decision(
                domain="answer",
                condition=NonActionCondition.ENVELOPE_OUTCOME_DONT_KNOW,
                required_response="dont_know",
                rationale={"outcome": "dont_know"},
            )
        )
        return decisions

    # Structural integrity: an "answer" outcome requires at least one support hit.
    if isinstance(outcome, str) and outcome.strip().lower() == "answer":
        candidates_raw = envelope.get("candidates")
        if not (isinstance(candidates_raw, list) and len(candidates_raw) > 0):
            decisions.append(
                _decision(
                    domain="answer",
                    condition=NonActionCondition.INSUFFICIENT_EVIDENCE_SHAPE,
                    required_response="dont_know",
                    rationale={"outcome": "answer", "candidates": "empty"},
                )
            )
        elif not _has_support_evidence(envelope):
            decisions.append(
                _decision(
                    domain="answer",
                    condition=NonActionCondition.INSUFFICIENT_EVIDENCE_SHAPE,
                    required_response="dont_know",
                    rationale={"outcome": "answer", "support_evidence": False},
                )
            )

    if _conflict_without_next_steps(envelope):
        decisions.append(
            _decision(
                domain="answer",
                condition=NonActionCondition.CONFLICT_WITHOUT_NEXT_STEPS,
                required_response="defer",
                rationale={"candidate_state": "conflicted", "next_steps": "missing"},
            )
        )

    return decisions


def _evaluate_ingest(ctx: NonActionContext) -> List[NonActionDecision]:
    ingest = ctx.get("ingest") if _is_mapping(ctx.get("ingest")) else {}
    decisions: List[NonActionDecision] = []

    if _safe_bool(ingest.get("blocked_by_design"), False):
        decisions.append(
            _decision(
                domain="ingest",
                condition=NonActionCondition.INGEST_BLOCKED_BY_DESIGN,
                required_response="refuse",
                rationale={"source_kind": ingest.get("source_kind")},
            )
        )
        return decisions

    if _safe_bool(ingest.get("sensitive"), False):
        if _safe_bool(ingest.get("under_vault_root"), False) or not _safe_bool(ingest.get("staged_under_processing"), False):
            decisions.append(
                _decision(
                    domain="ingest",
                    condition=NonActionCondition.SENSITIVE_STAGING_REQUIRED,
                    required_response="defer",
                    rationale={
                        "sensitive": True,
                        "under_vault_root": _safe_bool(ingest.get("under_vault_root"), False),
                        "staged_under_processing": _safe_bool(ingest.get("staged_under_processing"), False),
                    },
                )
            )

    if ingest and not _safe_bool(ingest.get("adapter_present"), True):
        decisions.append(
            _decision(
                domain="ingest",
                condition=NonActionCondition.INGEST_ADAPTER_MISSING,
                required_response="refuse",
                rationale={"source_kind": ingest.get("source_kind")},
            )
        )

    if ingest and not _safe_bool(ingest.get("pipeline_registered"), True):
        decisions.append(
            _decision(
                domain="ingest",
                condition=NonActionCondition.INGEST_PIPELINE_NOT_REGISTERED,
                required_response="refuse",
                rationale={"source_kind": ingest.get("source_kind")},
            )
        )

    return decisions


def _evaluate_train(ctx: NonActionContext) -> List[NonActionDecision]:
    train = ctx.get("train") if _is_mapping(ctx.get("train")) else {}
    decisions: List[NonActionDecision] = []

    if _safe_bool(train.get("blocked_by_design"), False):
        decisions.append(
            _decision(
                domain="train",
                condition=NonActionCondition.TRAINING_BLOCKED_BY_DESIGN,
                required_response="refuse",
                rationale={},
            )
        )
        return decisions

    if _safe_bool(train.get("includes_sensitive_sources"), False) and not _safe_bool(train.get("vault_manifest_present"), False):
        decisions.append(
            _decision(
                domain="train",
                condition=NonActionCondition.TRAINING_VAULT_MANIFEST_REQUIRED,
                required_response="refuse",
                rationale={"includes_sensitive_sources": True, "vault_manifest_present": False},
            )
        )

    if train and not _safe_bool(train.get("human_approved"), False):
        decisions.append(
            _decision(
                domain="train",
                condition=NonActionCondition.TRAINING_HUMAN_APPROVAL_REQUIRED,
                required_response="refuse",
                rationale={"human_approved": False},
            )
        )

    if _safe_bool(train.get("mixed_provenance_sources"), False):
        decisions.append(
            _decision(
                domain="train",
                condition=NonActionCondition.TRAINING_MIXED_PROVENANCE,
                required_response="defer",
                rationale={"mixed_provenance_sources": True},
            )
        )

    return decisions


def _evaluate_act(ctx: NonActionContext) -> List[NonActionDecision]:
    act = ctx.get("act") if _is_mapping(ctx.get("act")) else {}
    decisions: List[NonActionDecision] = []

    intends = _safe_bool(act.get("intends_tool_action"), False)
    if not intends:
        return decisions

    requires_env = _safe_bool(act.get("requires_epistemic_envelope"), True)
    requires_just = _safe_bool(act.get("requires_justification_payload"), True)

    env = ctx.get("epistemic_envelope")
    if requires_env and not _is_mapping(env):
        decisions.append(
            _decision(
                domain="act",
                condition=NonActionCondition.ACT_REQUIRES_EPISTEMIC_ENVELOPE,
                required_response="silent",
                rationale={"missing": "epistemic_envelope"},
            )
        )
        return decisions

    if requires_just and not _safe_bool(act.get("has_justification_payload"), False):
        decisions.append(
            _decision(
                domain="act",
                condition=NonActionCondition.ACT_REQUIRES_JUSTIFICATION_PAYLOAD,
                required_response="silent",
                rationale={"has_justification_payload": False},
            )
        )

    if _is_mapping(env) and _any_conflicted_candidate(cast(Mapping[str, Any], env)):
        decisions.append(
            _decision(
                domain="act",
                condition=NonActionCondition.ACT_BLOCKED_ON_CONFLICT,
                required_response="defer",
                rationale={"candidate_state": "conflicted"},
            )
        )

    return decisions


def evaluate_non_action(context: NonActionContext) -> List[NonActionDecision]:
    """
    Evaluate the Non-Action Contract and return a list of declarative decisions.

    This function has no side effects and does not enforce blocking.
    """
    domains: Sequence[NonActionDomain]
    raw_domains = context.get("domains")
    if isinstance(raw_domains, list) and all(isinstance(d, str) for d in raw_domains):
        domains = cast(List[NonActionDomain], raw_domains)
    else:
        domains = ("answer", "ingest", "train", "act")

    out: List[NonActionDecision] = []
    for d in domains:
        if d == "answer":
            out.extend(_evaluate_answer(context))
        elif d == "ingest":
            out.extend(_evaluate_ingest(context))
        elif d == "train":
            out.extend(_evaluate_train(context))
        elif d == "act":
            out.extend(_evaluate_act(context))
    return out

