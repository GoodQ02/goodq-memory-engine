# GoodQ4All Analytics Index

**Purpose:** Central entrypoint for analytics-related documentation and tools. Use this to navigate dashboards, APIs, and CLI helpers for analytics and reporting.

---

## Canonical Analytics Docs

- `docs/ANALYTICS_QUICK_REFERENCE.md` – Canonical quick reference for analytics commands, workflows, and configuration.
- `docs/ANALYTICS_PAGES_COMPLETE.md` – Implementation summary for the web analytics pages and `/api/analytics/*` endpoints.
- `docs/PHASE7_ANALYTICS_COMPLETE.md` – Phase 7 completion report focused on analytics.

---

## CLI & Scripts (Analytics Tooling)

Located in `scripts/`:

- `scripts/analytics_cli.py` – CLI interface for analytics-related commands.
- `scripts/analytics_dashboard.py` – Generates analytics dashboards.
- `scripts/analytics_engine.py` – Core analytics engine module.
- `scripts/analytics_query.py` – Interactive/natural-language analytics querying.

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
  - `docs/ANALYTICS_PAGES_COMPLETE.md` to understand how the analytics pages and APIs are wired into the web UI and backend.
- Use:
  - `scripts/analytics_dashboard.py` and `scripts/analytics_query.py` for day-to-day analytics work.
  - Phase and audit docs (Phase 7 and UI audits) when validating or extending analytics features.

