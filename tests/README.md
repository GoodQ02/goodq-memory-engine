# GoodQ4All Test Surface

**Last Verified:** 2026-03-20  
**Status:** Authoritative for the maintained test contract

## Canonical Contract

The supported automated test suite is the `pytest` unit suite under `tests/unit`.

- Discovery is governed by `pytest.ini`
- CI runs `python -m pytest -q`
- `pytest` currently collects `tests/unit`
- `tests/integration`, `tests/legacy`, and `tests/utils` are excluded from default collection

## Active Test Surfaces

### Unit Suite

Use this for normal validation and CI parity:

```powershell
python -m pytest -q
```

Or run only the unit tree explicitly:

```powershell
python -m pytest tests/unit -q
```

### Manual Integration Check

The only integration harness still treated as a live manual check is:

- `tests/integration/test_watchdog.py`

Run it explicitly when you need watchdog-specific validation:

```powershell
python -m pytest tests/integration/test_watchdog.py -q
```

## Historical Surfaces

The following areas are preserved for reference and one-off forensic work, but they are not part of the supported automated contract:

- `tests/legacy/root_harnesses/`
- `tests/legacy/integration_harnesses/`
- `tests/legacy/utilities/`
- `tests/legacy/` older archived diagnostics

Many of those files were created to validate intermediate build steps, old path assumptions, or retired runtime phases. They may still be useful as historical notes, but they should not be treated as current acceptance tests.

## Guidance

- Prefer `python -m pytest -q` for routine verification.
- Treat anything under `tests/legacy/` as historical unless explicitly re-promoted.
- If a legacy harness becomes valuable again, reintroduce it deliberately instead of relying on drift.
