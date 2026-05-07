<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# Epistemic Read Model Contract (v1)

**Purpose:** Freeze a shared, stable language for how GoodQ represents answers, evidence, uncertainty, and explicit limits.  
**Scope:** Contract only. No policy, no thresholds, no automatic classification, no UI.  
**Non-goals:** Scoring, gating, refusal thresholds, reinforcement, ranking changes, retrieval changes.

---

## Principles (Non-Negotiable)

- **No policy coupling:** The read model is descriptive. It must not directly gate, refuse, rerank, or otherwise control retrieval behavior.
- **No thresholding:** This contract defines *states* and *evidence shapes*, not numeric cutoffs or decision rules.
- **`dont_know` is structural:** “I don’t know” is a first-class outcome, not an error condition.
- **Provenance is a pointer:** Provenance links a hit back to commit evidence (best-effort), but is not full lineage or ground truth.
- **Confidence is informational:** Confidence fields are metadata only; they may be null and must not be treated as policy.

## Basement Phase Summary (v1)

- Contract v1 defines the shared schema + semantics only (no scoring, no thresholds, no policy coupling).
- Reference implementation exists as a deterministic, non-authoritative formatter: `steps/common/epistemic_formatter.py`.

---

## Canonical Schema (TypedDict / Pydantic-style)

```py
from typing import Any, Dict, List, Literal, Optional

ReadOutcome = Literal["answer", "dont_know"]
EvidenceRole = Literal["support", "contradict", "related", "meta"]

EpistemicState = Literal[
  "supported",
  "partially_supported",
  "conflicted",
  "stale",
  "unsupported_but_related",
  "unknown",
]

class Confidence(TypedDict, total=False):
  intrinsic: Optional[float]
  source: Optional[float]
  temporal: Optional[float]
  temporal_explanation: Optional[str]
  consistency: Optional[float]
  overall: Optional[float]

class ProvenancePointer(TypedDict, total=False):
  provenance_version: int  # current: 1
  ts_utc: Optional[str]
  scene_id: Optional[str]
  video_id: Optional[str]
  modality: Optional[str]
  model: Optional[str]
  component: Optional[str]
  attempted: Optional[bool]
  committed: Optional[bool]
  reason: Optional[str]
  targets: Dict[str, Dict[str, Any]]  # per-target attempted/committed/ref/reason
  confidence: Confidence              # may be all-null

class EvidenceHit(TypedDict, total=False):
  role: EvidenceRole
  store: Optional[str]                # e.g. "qdrant" | "faiss" | "ephemeral"
  store_ref: Optional[str]            # e.g. Qdrant collection / FAISS index name
  embedding_id: Optional[str]
  score: Optional[float]
  payload: Dict[str, Any]             # sanitized; never includes raw user query
  provenance: Optional[ProvenancePointer]
  confidence: Confidence              # hit-level posture; temporal may be populated
  limits: List[str]                   # e.g. ["provenance_missing", "store_ref_unknown"]

class NextStepHint(TypedDict, total=False):
  action: str                         # e.g. "search text modality", "inspect scene manifest"
  rationale: str
  scope: Optional[Dict[str, Any]]     # e.g. {"video_id": "...", "modality": "text"}

class AnswerCandidate(TypedDict, total=False):
  candidate_id: str
  state: EpistemicState
  answer_text: str
  confidence: Confidence              # answer-level posture; may be all-null
  evidence: List[EvidenceHit]
  limits: List[str]                   # explicit uncertainties
  next_steps: List[NextStepHint]

class DontKnowOutcome(TypedDict, total=False):
  state: EpistemicState               # "unknown" or "unsupported_but_related"
  explanation: str                    # structural justification (no thresholds)
  evidence: List[EvidenceHit]         # optional related/meta evidence
  limits: List[str]
  next_steps: List[NextStepHint]

class EpistemicReadEnvelope(TypedDict, total=False):
  read_model_version: int             # = 1
  question: Dict[str, Any]            # includes user question text
  retrieval_context: Optional[str]    # sanitized origin label (no raw query)
  outcome: ReadOutcome
  candidates: List[AnswerCandidate]   # may be empty
  dont_know: Optional[DontKnowOutcome]
```

Notes:
- `provenance` is compatible with `steps/common/memory_provenance.py` output (`provenance_version=1`).
- `confidence.temporal` may be populated at read-time; other fields may remain null.

---

## Evidence Roles

- `support`: evidence that directly supports the candidate claim.
- `contradict`: evidence that directly contradicts the candidate claim (same facet/scope).
- `related`: topically related evidence that does not directly support or contradict the claim.
- `meta`: non-substantive evidence about system state (e.g., “provenance missing”, “store disabled”).

---

## Epistemic States (Semantics)

- `supported`: A candidate claim has directly supporting evidence; no contradictory evidence is present in the candidate’s evidence set; provenance (when present) indicates committed writes.
- `partially_supported`: Some supporting evidence exists, but explicit gaps remain (missing facets, missing modality coverage, or missing provenance for key support hits).
- `conflicted`: The evidence set contains both `support` and `contradict` for the same candidate claim/facet; the conflict is explicitly stated in `limits`.
- `stale`: The evidence supports the claim, but applicability is time-sensitive and the support is clearly dated; staleness is expressed via timestamps / temporal confidence explanation, not hard cutoffs.
- `unsupported_but_related`: Retrieved evidence is related to the query/topic but does not justify the specific claim.
- `unknown`: No relevant supporting evidence exists (or evidence is insufficient to responsibly form a claim).

---

## “I Don’t Know” Outcome (Structural Meaning)

`outcome="dont_know"` is appropriate when the evidence shape cannot justify a claim without speculation:
- There is **no** `EvidenceHit` with `role="support"` for any candidate claim, and
- There is no coherent `conflicted` set to resolve (i.e., not “support vs contradict”), and
- The system can only provide `related`/`meta` evidence or nothing.

Required fields for a `dont_know` outcome:
- `dont_know.state` is `unknown` or `unsupported_but_related`
- `dont_know.explanation` describes *why* (structural/evidence-based) a claim cannot be made
- `dont_know.limits` enumerates what is missing
- `dont_know.next_steps` provides safe “where to look next” hints

Difference from `unsupported_but_related`:
- `unsupported_but_related` can exist as a *candidate* state (a related narrative that is explicitly not supported).
- `dont_know` is the explicit refusal-to-claim envelope outcome while still returning breadcrumbs.

---

## Evidence Shapes → States (No Thresholds)

| Evidence shape (roles + metadata) | State |
|---|---|
| ≥1 `support`, no `contradict`, provenance present for key support hits | `supported` |
| ≥1 `support`, explicit gaps noted (facets/modality/provenance), no `contradict` | `partially_supported` |
| `support` and `contradict` exist for same facet/claim; limits explain mismatch | `conflicted` |
| `support` exists; timestamps indicate age matters; limits note staleness | `stale` |
| Only `related`/`meta` evidence exists (no `support`/`contradict`) | `unsupported_but_related` |
| No relevant hits, or only meta signals such that no claim can be grounded | `unknown` (often with `outcome="dont_know"`) |

---

## Examples (Sanitized, Illustrative)

### Example A — `supported`
```json
{
  "read_model_version": 1,
  "question": { "text": "Which scene shows a birthday celebration?" },
  "retrieval_context": "human.ui.search",
  "outcome": "answer",
  "candidates": [
    {
      "candidate_id": "a1",
      "state": "supported",
      "answer_text": "Scene <scene_id> in video <video_id> appears to depict a birthday celebration.",
      "confidence": { "intrinsic": null, "source": null, "temporal": null, "consistency": null, "overall": null },
      "evidence": [
        {
          "role": "support",
          "store": "qdrant",
          "store_ref": "goodq_clip",
          "embedding_id": "<uuid>",
          "score": 0.12,
          "payload": { "video_id": "<video_id>", "scene_id": "<scene_id>", "model": "clip" },
          "provenance": {
            "provenance_version": 1,
            "ts_utc": "<utc>",
            "scene_id": "<scene_id>",
            "video_id": "<video_id>",
            "modality": "clip",
            "model": "clip",
            "committed": true,
            "targets": { "qdrant": { "attempted": true, "committed": true } },
            "confidence": { "intrinsic": null, "source": null, "temporal": null, "consistency": null, "overall": null }
          },
          "confidence": {
            "intrinsic": null,
            "source": null,
            "temporal": 0.93,
            "temporal_explanation": "exp_decay(...source=provenance.ts_utc)",
            "consistency": null,
            "overall": null
          },
          "limits": []
        }
      ],
      "limits": [],
      "next_steps": []
    }
  ]
}
```

### Example B — `conflicted`
```json
{
  "read_model_version": 1,
  "question": { "text": "Is there music playing in scene <scene_id>?" },
  "retrieval_context": "human.cli.retrieve",
  "outcome": "answer",
  "candidates": [
    {
      "candidate_id": "a2",
      "state": "conflicted",
      "answer_text": "The evidence is mixed about whether music is present in this scene.",
      "evidence": [
        {
          "role": "support",
          "store": "qdrant",
          "store_ref": "goodq_audio",
          "payload": { "scene_id": "<scene_id>", "model": "clap" },
          "provenance": { "provenance_version": 1, "committed": true }
        },
        {
          "role": "contradict",
          "store": "qdrant",
          "store_ref": "goodq_text",
          "payload": { "scene_id": "<scene_id>", "model": "all-MiniLM-L6-v2" },
          "provenance": { "provenance_version": 1, "committed": true }
        }
      ],
      "limits": [
        "Cross-modal conflict: supporting and contradicting signals exist for the same claim; verify by inspecting the underlying audio segment/transcript."
      ],
      "next_steps": [
        { "action": "review scene audio clip + transcript", "rationale": "resolve cross-modal disagreement", "scope": { "scene_id": "<scene_id>" } }
      ]
    }
  ]
}
```

### Example C — `dont_know` (`unknown`)
```json
{
  "read_model_version": 1,
  "question": { "text": "What was the exact brand of the camera used?" },
  "retrieval_context": "human.ui.search",
  "outcome": "dont_know",
  "candidates": [],
  "dont_know": {
    "state": "unknown",
    "explanation": "No retrieved evidence directly supports the requested fact; emitting a specific brand would be speculative.",
    "evidence": [],
    "limits": [
      "No support evidence available for the requested fact",
      "No authoritative source present in current memory"
    ],
    "next_steps": [
      { "action": "search text modality for explicit mentions", "rationale": "camera brand may only exist in notes/transcripts" },
      { "action": "attach/ingest a source that contains the camera metadata", "rationale": "the system cannot recover facts that were never captured" }
    ]
  }
}
```
