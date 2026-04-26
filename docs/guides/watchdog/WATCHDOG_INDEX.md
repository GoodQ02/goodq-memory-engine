# GoodQ4All Watchdog Documentation Index

**Purpose:** Central entrypoint for all Watchdog (automatic ingestion) documentation. Use this to understand how to start, monitor, and maintain the Watchdog system.

---

## Canonical Watchdog Docs

- `docs/guides/watchdog/WATCHDOG_GUIDE.md` – Primary, comprehensive user guide for Watchdog behavior and configuration.
- `docs/guides/watchdog/WATCHDOG_QUICKREF.md` – Quick reference card for commands and common tasks.
- `docs/guides/watchdog/WATCHDOG_CHANGELOG.md` – Canonical development and version history.
- `docs/architecture/diagrams/watchdog_flow.md` – Architecture and flow diagrams for the Watchdog system.

---

## Quickstart & User-Facing Shortcuts

- `docs/guides/general/WATCHDOG_QUICKSTART.txt` – Text-mode quickstart; legacy helper that defers to the canonical Watchdog docs for current details.
- `conda run -n goodq_core python -m cli.watchdog` – Start Watchdog service.
- `python scripts/utils/check_watchdog_status.py` – One-time status snapshot.
- `scripts/monitoring/monitor_live.bat` – Live monitoring dashboard.

---

## Implementation & Maintenance

- `cli/watchdog.py` – Canonical Watchdog daemon (monitor + worker).
- `scripts/utils/check_watchdog_status.py` – Status dashboard script.
- `tests/integration/test_watchdog.py` – File classification and status behavior check.

See `docs/guides/watchdog/WATCHDOG_GUIDE.md` and `docs/architecture/diagrams/watchdog_flow.md` for details on these components.

---

## Agent & Cleanup Notes (Historical)

- `docs/archive/agent-comms/WATCHDOG_CLEANUP.md` – Historical agent-focused cleanup summary and active script list as of 2025-10-11.

This document is useful for understanding past cleanup decisions, but `WATCHDOG_GUIDE.md`, `WATCHDOG_QUICKREF.md`, and `WATCHDOG_INDEX.md` should be treated as the current sources of truth for usage.

Historical summary:

- `docs/archive/reports/WATCHDOG_SUMMARY.md` – Archived high-level implementation summary.
