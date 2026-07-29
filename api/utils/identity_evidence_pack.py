"""Passive, curated identity evidence for agent-facing read models."""
from __future__ import annotations

from typing import Any, Iterable


def _terms(identity: dict[str, Any]) -> list[str]:
    values = [identity.get("display_name"), *(identity.get("aliases") or []), *(identity.get("name_mention_keys") or [])]
    return [str(value).strip() for value in values if str(value).strip()]


def _public_identity(identity: dict[str, Any], matched_terms: list[str]) -> dict[str, Any]:
    return {
        "id": str(identity.get("id") or ""),
        "display_name": str(identity.get("display_name") or identity.get("id") or ""),
        "aliases": [str(value) for value in (identity.get("aliases") or []) if str(value).strip()],
        "role": identity.get("role"),
        "confirmed": bool(identity.get("confirmed", False)),
        "matched_terms": matched_terms,
        "identity_source": "curated_roster",
    }


def build_identity_evidence_pack(
    identities: Iterable[dict[str, Any]],
    subjects: Iterable[str],
) -> dict[str, Any]:
    """Resolve curated identities without deriving relationships from proximity.

    A legacy identity ``role`` remains an identity-level label. Only an explicit
    per-identity ``relationships`` record can establish a directed pairwise claim.
    """
    normalized = [str(subject).strip().lower() for subject in subjects if str(subject).strip()]
    source_identities = [item for item in identities if isinstance(item, dict)]
    matched: list[dict[str, Any]] = []
    matched_ids: set[str] = set()
    for identity in source_identities:
        terms = _terms(identity)
        matching = sorted({subject for subject in normalized if subject in {term.lower() for term in terms}})
        identity_id = str(identity.get("id") or "")
        if matching and identity_id:
            matched.append(_public_identity(identity, matching))
            matched_ids.add(identity_id)

    claims: list[dict[str, str]] = []
    for identity in source_identities:
        source_id = str(identity.get("id") or "")
        if source_id not in matched_ids:
            continue
        for relationship in identity.get("relationships") or []:
            if not isinstance(relationship, dict):
                continue
            target_id = str(relationship.get("target_id") or "")
            relationship_type = str(relationship.get("type") or "")
            if target_id in matched_ids and relationship_type:
                claims.append({
                    "source_id": source_id,
                    "target_id": target_id,
                    "type": relationship_type,
                    "authority": "curated_roster_relationship",
                })

    labels = [
        {
            "identity_id": item["id"],
            "field": "role",
            "value": item["role"],
            "scope": "identity_level_unscoped",
        }
        for item in matched
        if item.get("role") not in (None, "")
    ]
    return {
        "identities": matched,
        "identity_labels": labels,
        "relationships": claims,
        "claim_status": "established" if claims else "not_established",
        "withheld_reasons": ([] if claims else [
            "No explicit directed curated relationship record exists for the requested identities.",
            "Identity role labels and scene co-occurrence are not pairwise relationship claims.",
        ]),
    }
