<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_ROADMAP -->
<!-- DOC_LAST_VERIFIED: 2026-09-16 -->

# Public release qualification

This downstream register describes public validation scope. The private
development register remains the sole product planning authority; private
machine progress and corpus details are intentionally omitted.

### R-19 Public runtime qualification
- Status: OPEN
- Source publication includes lifecycle supervision, orderly drain, explicit
  vLLM ownership, ingestion persistence, and offline installer contract fixes.
- Each operator must configure local paths, verify dependencies, and run the
  appropriate health and retrieval checks on their own installation.
- Existing published installer assets retain their original release identity.
  This source update does not replace or newly qualify those binaries.
- See [the sanitization manifest](PUBLIC_SANITIZATION_MANIFEST.md) for the
  pinned source and public verification boundary.
