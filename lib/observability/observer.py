from __future__ import annotations

import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from lib.observability.event_types import (
    HEARTBEAT,
    STEP_END,
    STEP_ERROR,
    STEP_PROGRESS,
    STEP_START,
)


_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


def _env_with_alias(primary: str, *aliases: str) -> Optional[str]:
    """
    Resolve an env var with optional aliases.
    Canonical primary key always takes precedence when present.
    """
    value = os.getenv(primary)
    if value is not None:
        return value
    for alias in aliases:
        aliased = os.getenv(alias)
        if aliased is not None:
            return aliased
    return None


def _parse_bool_env(raw: Optional[str], default: bool) -> bool:
    if raw is None:
        return default
    norm = raw.strip().lower()
    if norm in _TRUTHY:
        return True
    if norm in _FALSY:
        return False
    return default


def _parse_float_env(raw: Optional[str], default: float) -> float:
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


@dataclass
class _StepState:
    started_at: float
    total: Optional[int] = None
    current: int = 0
    bar: Any = None


class PipelineObserver:
    """
    Read-only pipeline observer.
    Emits JSON lines telemetry and optional tqdm progress bars.
    """

    def __init__(
        self,
        *,
        run_id: Optional[str],
        enabled: bool,
        emit_json: bool,
        enable_tqdm: bool,
        heartbeat_interval_sec: float = 5.0,
    ) -> None:
        self.run_id = run_id
        self.enabled = bool(enabled)
        self.emit_json = bool(emit_json)
        self.heartbeat_interval_sec = max(1.0, float(heartbeat_interval_sec))
        self._lock = threading.Lock()
        self._steps: Dict[str, _StepState] = {}
        self._interactive = bool(enable_tqdm and sys.stdout.isatty())
        self._tqdm = None
        if self._interactive:
            try:
                from tqdm import tqdm  # type: ignore

                self._tqdm = tqdm
            except Exception:
                self._interactive = False
                self._tqdm = None

    @classmethod
    def from_runtime(cls, *, run_id: Optional[str], verbose: bool) -> "PipelineObserver":
        enabled = _parse_bool_env(
            _env_with_alias("GOODQ_OBSERVER_ENABLED", "GOODQ_OBSERVE"),
            bool(verbose),
        )
        emit_json = _parse_bool_env(
            _env_with_alias("GOODQ_OBSERVER_JSON", "GOODQ_OBSERVE_JSON"),
            True,
        )
        enable_tqdm = _parse_bool_env(
            _env_with_alias("GOODQ_OBSERVER_TQDM", "GOODQ_OBSERVE_TQDM"),
            True,
        )
        heartbeat_interval = _parse_float_env(
            _env_with_alias("GOODQ_OBSERVER_HEARTBEAT_SEC", "GOODQ_OBSERVE_HEARTBEAT_SEC"),
            5.0,
        )
        return cls(
            run_id=run_id,
            enabled=enabled,
            emit_json=emit_json,
            enable_tqdm=enable_tqdm,
            heartbeat_interval_sec=heartbeat_interval,
        )

    def _emit(self, event: str, step: str, **fields: Any) -> None:
        if not (self.enabled and self.emit_json):
            return
        payload: Dict[str, Any] = {
            "timestamp": time.time(),
            "run_id": self.run_id,
            "event": event,
            "step": step,
        }
        payload.update(fields)
        try:
            print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)
        except Exception:
            # Observability must never affect pipeline behavior.
            pass

    def step_start(self, step: str, *, total: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        if not self.enabled:
            return
        state = _StepState(started_at=time.perf_counter(), total=total if isinstance(total, int) else None)
        try:
            if self._interactive and self._tqdm and state.total is not None and state.total > 0:
                state.bar = self._tqdm(total=state.total, desc=step, leave=False, dynamic_ncols=True)
        except Exception:
            state.bar = None
        with self._lock:
            self._steps[step] = state
        self._emit(STEP_START, step, total=state.total, metadata=metadata or {})

    def step_progress(
        self,
        step: str,
        *,
        current: Optional[int] = None,
        total: Optional[int] = None,
        percent: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.enabled:
            return
        with self._lock:
            state = self._steps.get(step)
            if state is None:
                state = _StepState(started_at=time.perf_counter())
                self._steps[step] = state
            if isinstance(total, int) and total > 0:
                state.total = total
            if isinstance(current, int) and current >= 0:
                delta = max(0, current - state.current)
                state.current = current
                if state.bar is not None and delta:
                    try:
                        state.bar.update(delta)
                    except Exception:
                        pass
            calc_percent: Optional[float] = None
            if state.total and state.total > 0 and state.current >= 0:
                calc_percent = min(100.0, (float(state.current) / float(state.total)) * 100.0)
            elif percent is not None:
                calc_percent = float(percent)
            elapsed = max(0.0, time.perf_counter() - state.started_at)
        self._emit(
            STEP_PROGRESS,
            step,
            current=current,
            total=total or state.total,
            percent=calc_percent,
            elapsed_sec=elapsed,
            metadata=metadata or {},
        )

    def step_end(self, step: str, *, metadata: Optional[Dict[str, Any]] = None) -> None:
        if not self.enabled:
            return
        with self._lock:
            state = self._steps.pop(step, None)
        elapsed = None
        if state is not None:
            elapsed = max(0.0, time.perf_counter() - state.started_at)
            if state.bar is not None:
                try:
                    if state.total is not None and state.current < state.total:
                        state.bar.update(max(0, state.total - state.current))
                    state.bar.close()
                except Exception:
                    pass
        self._emit(STEP_END, step, elapsed_sec=elapsed, metadata=metadata or {})

    def step_error(
        self,
        step: str,
        *,
        error: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.enabled:
            return
        with self._lock:
            state = self._steps.pop(step, None)
        elapsed = None
        if state is not None:
            elapsed = max(0.0, time.perf_counter() - state.started_at)
            if state.bar is not None:
                try:
                    state.bar.close()
                except Exception:
                    pass
        self._emit(STEP_ERROR, step, error=error, elapsed_sec=elapsed, metadata=metadata or {})

    def heartbeat(self, step: str, *, metadata: Optional[Dict[str, Any]] = None) -> None:
        if not self.enabled:
            return
        with self._lock:
            state = self._steps.get(step)
            elapsed = max(0.0, time.perf_counter() - state.started_at) if state is not None else None
        self._emit(HEARTBEAT, step, elapsed_sec=elapsed, metadata=metadata or {})

    def begin_heartbeat(
        self,
        step: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        interval_sec: Optional[float] = None,
    ) -> Callable[[], None]:
        if not self.enabled:
            return lambda: None

        stop_event = threading.Event()
        interval = max(1.0, float(interval_sec or self.heartbeat_interval_sec))

        def _loop() -> None:
            while not stop_event.wait(interval):
                self.heartbeat(step, metadata=metadata)

        thread = threading.Thread(target=_loop, name=f"observer-heartbeat-{step}", daemon=True)
        thread.start()

        def _stop() -> None:
            stop_event.set()
            thread.join(timeout=0.2)

        return _stop

    def close(self) -> None:
        if not self.enabled:
            return
        with self._lock:
            states = list(self._steps.values())
            self._steps.clear()
        for state in states:
            if state.bar is not None:
                try:
                    state.bar.close()
                except Exception:
                    pass
