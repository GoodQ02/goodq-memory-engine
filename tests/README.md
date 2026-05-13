# GoodQ4All Test Surface

**Last Verified:** 2026-03-20  
**Status:** Authoritative for the maintained test contract

## Canonical Contract

The supported automated test suite is the `pytest` unit suite under `tests/unit`.

- Discovery is governed by `pytest.ini`
- CI runs `python -m pytest -q`
- `pytest` currently collects `tests/unit`
- `tests/integration` and `tests/utils` are excluded from default collection

## Active Test Surfaces

### Unit Suite

CI uses the canonical Python environment directly:

```powershell
python -m pytest -q
```

On Windows, local agents and long-lived shells should use the repo wrapper. It always runs through the canonical `goodq_core` Conda environment and scopes Conda temp files under `tmp/conda_run` instead of shared Windows TEMP:

```powershell
.\scripts\dev\run_pytest.ps1
```

To run only the unit tree locally:

```powershell
.\scripts\dev\run_pytest.ps1 tests/unit -q
```

Use direct `python -m pytest ...` only inside an already-bound canonical environment such as CI or an explicit `conda run -n goodq_core ...` command.


### Manual Integration Check

The only integration harness still treated as a live manual check is:

- `tests/integration/test_watchdog.py`

Run it explicitly when you need watchdog-specific validation:

```powershell
python -m pytest tests/integration/test_watchdog.py -q
```

## Historical Surfaces

Legacy test harnesses from earlier workstation-specific phases are not part of
the public branch. They remain private historical material on the development
line when needed for archaeology, but public validation should use the active
unit suite or an explicitly documented integration check.

## Guidance

- Prefer `python -m pytest -q` for routine verification.
- Retired harnesses are historical unless explicitly re-promoted.
- If a retired harness becomes valuable again, reintroduce it deliberately as a maintained test instead of relying on drift.
