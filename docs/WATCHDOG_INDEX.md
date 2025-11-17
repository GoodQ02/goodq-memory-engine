# GoodQ4All Watchdog Documentation Index

**Purpose:** Central entrypoint for all Watchdog (automatic ingestion) documentation. Use this to understand how to start, monitor, and maintain the Watchdog system.

---

## Canonical Watchdog Docs

- `docs/WATCHDOG_GUIDE.md` – Primary, comprehensive user guide for Watchdog behavior and configuration.
- `docs/WATCHDOG_QUICKREF.md` – Quick reference card for commands and common tasks.
- `docs/WATCHDOG_SUMMARY.md` – High-level implementation and performance summary.
- `docs/WATCHDOG_CHANGELOG.md` – Canonical development and version history.
- `docs/diagrams/watchdog_flow.md` – Architecture and flow diagrams for the Watchdog system.

---

## Quickstart & User-Facing Shortcuts

- `docs/user-guides/WATCHDOG_QUICKSTART.txt` – Text-mode quickstart; legacy helper that defers to `WATCHDOG_GUIDE.md` and `WATCHDOG_QUICKREF.md` for current details.
- `START_WATCHDOG.bat` (root) – Start Watchdog service.
- `CHECK_WATCHDOG_STATUS.bat` (root) – One-time status snapshot.
- `MONITOR_WATCHDOG.bat` (root) – Live monitoring dashboard (looped status updates).

---

## Implementation & Maintenance

- `scripts/watchdog_ingest.py` – Main Watchdog daemon (monitor + worker).
- `scripts/check_watchdog_status.py` – Status dashboard script.
- `scripts/test_watchdog.py` – Test suite for file classification and behavior.
- `scripts/test_watchdog_simple.py` – Simple manual verification tool.

See `docs/WATCHDOG_GUIDE.md` and `docs/diagrams/watchdog_flow.md` for details on these components.

---

## Agent & Cleanup Notes (Historical)

- `docs/agent-communications/WATCHDOG_CLEANUP.md` – Agent-focused cleanup summary and active script list as of 2025-10-11.

This document is useful for understanding past cleanup decisions, but `WATCHDOG_GUIDE.md`, `WATCHDOG_QUICKREF.md`, and `WATCHDOG_INDEX.md` should be treated as the current sources of truth for usage.

