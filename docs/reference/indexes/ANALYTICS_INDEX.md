<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_POINTER -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# GoodQ4All Analytics Index

**Purpose:** Central entrypoint for analytics-related documentation and tools. Use this to navigate the secondary analytics/reporting stack, not the canonical runtime authority.

---

## Active Analytics Docs

- `docs/ANALYTICS_QUICK_REFERENCE.md` – Active quick reference for analytics commands, workflows, and configuration.
- `docs/ANALYTICS_PAGES_COMPLETE.md` – Historical implementation summary for the web analytics pages and the retired `/api/analytics/*` endpoints.
- `docs/PHASE7_ANALYTICS_COMPLETE.md` – Phase 7 completion report focused on analytics.

---

## CLI & Scripts (Analytics Tooling)

Located in `scripts/`:

- `scripts/analytics_cli.py` – CLI interface for analytics-related commands.
- `scripts/analytics_dashboard.py` – Generates analytics dashboards.
- `scripts/analytics_engine.py` – Core analytics engine module.
- `scripts/analytics_query.py` – Interactive/natural-language analytics querying.

Current truth:
- analytics remains functional as a reporting/inspection sidecar
- analytics is not the canonical ingest, retrieval, or runtime-status authority
- retired `/api/analytics/*` HTTP surfaces should stay historical only

See `docs/ANALYTICS_QUICK_REFERENCE.md` for usage examples and parameters.

---

## Related Documentation & Reports

- `docs/audits/UI_AUDIT_REPORT_2025-11-15.md` – UI audit coverage for analytics tabs and endpoints.
- `docs/audits/AUDIT_COMPLETE.md` – Mentions `/api/analytics/*` in the context of full-system audits.
- `docs/COMPLETE_AUDIT_SUMMARY.md` and `docs/COMPREHENSIVE_AUDIT_SUCCESS_REPORT_2025-11-09.md` – High-level references to analytics capabilities.

---

## When to Use What

- Start with:
  - `docs/ANALYTICS_QUICK_REFERENCE.md` for commands, scripts, and basic workflows.
  - `docs/ANALYTICS_PAGES_COMPLETE.md` to understand the historical analytics page rollout and retired HTTP surfaces.
- Use:
  - `scripts/analytics_dashboard.py` and `scripts/analytics_query.py` for day-to-day analytics work.
  - Phase and audit docs (Phase 7 and UI audits) when validating or extending analytics features.
- Do not use:
  - analytics docs as a substitute for the canonical API, ingest, retrieval, or witness truth surfaces
