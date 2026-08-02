<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: HISTORICAL_REFERENCE -->
<!-- DOC_LAST_VERIFIED: 2026-08-02 -->

# Dev Mode Operator Dashboard Design

## Purpose

Give the existing `dev_on.bat` and `dev_off.bat` launchers a compact,
CRT-inspired operator receipt. It must show the actual path to BUILD MODE or
OPEN DESKTOP as runtime checks complete, without becoming a new UI or service.

## Scope

- Keep the batch launchers as the sole operator entry points.
- Render a fixed text signal path with node states for configuration, WSL audio,
  vLLM, Qdrant, API/watchdog, and GPU release where applicable.
- Update each node only from an existing successful check or a newly bounded
  endpoint/process check.
- Leave the final terminal open until the user closes it.
- Use text, symbols, and color together: lime `[READY]`, blue `[INFO]`, white
  `[CHECK]`, yellow `[WARN]`, and red `[BLOCKED]`.

## Mode contracts

### Dev On / BUILD MODE

1. Show the fixed path with all nodes pending.
2. Mark configuration, WSL audio, vLLM, Qdrant, API, and watchdog as each
   existing or bounded readiness check succeeds.
3. Stop at the first failed node, state the actionable reason, and leave the
   receipt visible. Do not start later services after a blocking prerequisite.
4. On success, show `SYSTEM READY — BUILD MODE` with the verified loopback
   endpoints and keepalive state.

### Dev Off / OPEN DESKTOP

1. Show the fixed release path with all nodes pending.
2. Mark vLLM/WSL, API, and watchdog released only after their stop checks pass.
3. Mark Qdrant as intentionally retained on loopback, rather than released.
4. On success, show `OPEN DESKTOP — GPU SERVICES RELEASED` and keep the
   receipt visible.

## Design constraints

- No Mermaid renderer, browser page, background service, network call, model
  load, or repository data access.
- No color-only status meaning; the terminal must remain understandable without
  ANSI color support.
- Oh My Posh remains an optional interactive-shell enhancement and is not a
  launcher dependency.
- All launcher PowerShell automation uses `-NoProfile`, so cosmetic profile
  initialization cannot affect GoodQ runtime control.

## Verification

1. Contract tests prove every displayed success node has an associated bounded
   check and every blocking failure stops the correct downstream path.
2. Dev Off to Dev On proves the live vLLM, Qdrant, and API endpoints plus WSL
   anchor state.
3. Dev On while healthy proves a readable receipt and no duplicate WSL anchor.
4. Dev Off proves vLLM/WSL/API/watchdog are released and Qdrant remains
   reachable.

## Rollback

Revert only the launcher receipt/helper files and their contract tests. Runtime
service ownership and network bindings remain unchanged.
