<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-07-29 -->

# Hermes Personal-Memory Retrieval

## Purpose

Keep Hermes useful against GoodQ's private local corpus without turning roster
labels, scene co-presence, or semantic rank into personal facts.

## Required Route

For identity, relationship, history, and interaction requests, call bridge
`personal_memory_evidence` first. Supply the named subjects and the original
user question. The bridge composes curated identity labels, explicit directed
relationship records, and bounded source-scene evidence, then returns an
`answer_contract`.

## Contract Outcomes

| Outcome | Required response |
|---|---|
| `identity_label_only` | Return `safe_response`; role label is identity-level and unscoped. |
| `relationship_not_established` | Return `safe_response`; do not infer a pairwise relationship. |
| `clarification_needed` | Return only `safe_response`; wait for the requested date, event, or scene scope. |
| `source_evidence_unavailable` | Return `safe_response`; do not replace the missing source with a semantic inference. |
| `evidence_ready` | Cite only returned source-scene evidence and explicit relationship records. |

Never rewrite an unscoped role as a possessive or pairwise fact such as “your
cousin,” “Joe's cousin,” or “your mother.” Co-presence, names in the same
transcript, aliases, and semantic score do not establish a relationship.

## Evidence Escalation

1. `personal_memory_evidence`
2. `identity_scene_evidence`
3. `identity_scene_context`
4. `scene_evidence` only once an exact video and scene ID are known
5. General semantic search only when the preceding evidence does not answer a
   non-relationship retrieval request

## Verification

Use fresh Hermes sessions for these gates:

| Request | Expected result |
|---|---|
| “Who is Jamie?” | Identity-level label only. |
| “What is Maria's relationship to Joe?” | Explicitly not established when no directed record exists. |
| “What were notable interactions between Joe and Maria over time?” | One scope clarification question. |

The bridge test and MCP discovery test must pass before the model acceptance
gates. No GoodQ epoch, vector, graph, or identity data is changed by this
workflow.
