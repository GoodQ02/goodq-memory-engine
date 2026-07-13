from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filelock import FileLock

from steps.common.atomic_io import (
    atomic_write_json_for_concurrent_readers,
    read_text_during_atomic_replace,
)


SCHEMA_VERSION = "goodq.action-job.v1"
JOB_ID_RE = re.compile(r"^job_[0-9a-f]{32}$")
NONTERMINAL_STATES = frozenset(
    {"pending_confirmation", "authorizing", "queued", "running"}
)
TERMINAL_STATES = frozenset({"succeeded", "failed", "interrupted", "expired"})
ALL_STATES = NONTERMINAL_STATES | TERMINAL_STATES
PERMITTED_TRANSITIONS = {
    "pending_confirmation": frozenset({"authorizing", "failed", "expired"}),
    "authorizing": frozenset({"queued", "failed", "expired"}),
    "queued": frozenset({"running", "failed", "interrupted"}),
    "running": frozenset({"succeeded", "failed", "interrupted"}),
}
_SECRET_KEY_NAMES = {
    "apikey",
    "authorization",
    "authtoken",
    "bearer",
    "bearertoken",
    "confirmationtoken",
    "password",
    "secret",
    "token",
}
_UPDATE_FIELDS = {
    "token_fingerprint",
    "authorization_request_id",
    "outcome",
    "audit_status",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalized_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _reject_secret_bearing(
    value: Any,
    *,
    allowed_top_level_keys: frozenset[str] = frozenset(),
    depth: int = 0,
) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = _normalized_key(str(key))
            allowed_metadata = (
                depth == 0 and normalized_key in allowed_top_level_keys
            )
            token_like = normalized_key.endswith("token")
            if not allowed_metadata and (
                normalized_key in _SECRET_KEY_NAMES
                or "bearer" in normalized_key
                or token_like
            ):
                raise ValueError("Action job data contains a secret-bearing field")
            _reject_secret_bearing(
                nested,
                allowed_top_level_keys=allowed_top_level_keys,
                depth=depth + 1,
            )
    elif isinstance(value, list):
        for nested in value:
            _reject_secret_bearing(
                nested,
                allowed_top_level_keys=allowed_top_level_keys,
                depth=depth + 1,
            )
    elif isinstance(value, str) and re.search(r"\bbearer\s+\S+", value, re.IGNORECASE):
        raise ValueError("Action job data contains bearer token material")


def _reject_unsanitized_message(message: str) -> None:
    unsafe_patterns = (
        r"traceback\s*\(",
        r"\b(?:stdout|stderr)\b\s*[:=]",
        r"\bsubprocess\s+output\b",
        r"\bcompletedprocess\s*\(",
        r"\b[A-Za-z]+(?:Error|Exception):",
        r"[A-Za-z]:[\\/]",
        r"(?:^|\s)\\\\[^\s]+",
        r"(?:^|\s)/(?:[^/\s]+/)*[^/\s]+",
        r"(?:^|\s)~[\\/]",
    )
    if "\n" in message or "\r" in message or any(
        re.search(pattern, message, re.IGNORECASE) for pattern in unsafe_patterns
    ):
        raise ValueError("Action job outcome message contains unsanitized detail")


def _normalize_scope(scope: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(scope, dict):
        raise ValueError("Action job scope must be a JSON object")
    try:
        payload = json.dumps(
            scope,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Action job scope must contain only JSON values") from exc
    normalized = json.loads(payload)
    if not isinstance(normalized, dict):
        raise ValueError("Action job scope must be a JSON object")
    _reject_secret_bearing(normalized)
    return normalized


def _scope_identity(scope: dict[str, Any]) -> str:
    return json.dumps(
        scope,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _validate_owner_instance(owner_instance: Any, *, label: str) -> str:
    if not isinstance(owner_instance, str) or not re.fullmatch(
        r"[A-Za-z0-9_.:-]{1,128}", owner_instance
    ):
        raise ValueError(f"{label} owner instance must be a safe non-empty string")
    return owner_instance


def _validate_updates(updates: dict[str, Any]) -> dict[str, Any]:
    unknown = set(updates) - _UPDATE_FIELDS
    if unknown:
        raise ValueError(f"Unsupported action job update fields: {sorted(unknown)}")
    _reject_secret_bearing(
        updates, allowed_top_level_keys=frozenset({"tokenfingerprint"})
    )

    validated: dict[str, Any] = {}
    if "token_fingerprint" in updates:
        fingerprint = updates["token_fingerprint"]
        if not isinstance(fingerprint, str) or not re.fullmatch(
            r"[0-9a-f]{64}", fingerprint
        ):
            raise ValueError("Token fingerprint must be a lowercase SHA-256 digest")
        validated["token_fingerprint"] = fingerprint
    if "authorization_request_id" in updates:
        request_id = updates["authorization_request_id"]
        if not isinstance(request_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_.:-]{1,128}", request_id
        ):
            raise ValueError("Invalid authorization request ID")
        validated["authorization_request_id"] = request_id
    if "outcome" in updates:
        outcome = updates["outcome"]
        if not isinstance(outcome, dict) or set(outcome) != {"code", "message"}:
            raise ValueError("Outcome must contain only code and message")
        code = outcome["code"]
        message = outcome["message"]
        if not isinstance(code, str) or not re.fullmatch(r"[a-z0-9_.-]{1,64}", code):
            raise ValueError("Invalid sanitized outcome code")
        if not isinstance(message, str) or not 1 <= len(message) <= 512:
            raise ValueError("Invalid sanitized outcome message")
        _reject_unsanitized_message(message)
        validated["outcome"] = {"code": code, "message": message}
    if "audit_status" in updates:
        audit_status = updates["audit_status"]
        if not isinstance(audit_status, str) or not re.fullmatch(
            r"[a-z0-9_.-]{1,64}", audit_status
        ):
            raise ValueError("Invalid audit status")
        validated["audit_status"] = audit_status
    return validated


class ActionJobTransitionError(RuntimeError):
    """Base error for a rejected action-job state transition."""


class InvalidTransitionError(ActionJobTransitionError):
    """The requested state edge is not part of the lifecycle contract."""


class StaleTransitionError(ActionJobTransitionError):
    """The persisted state no longer matches the caller's expectation."""


class TerminalTransitionError(ActionJobTransitionError):
    """A terminal action job cannot be modified."""


class PassiveActionJobReader:
    """Read existing action-job records without creating storage or locks."""

    def __init__(self, root_dir: Path | str):
        self.root_dir = Path(root_dir)

    def load(self, job_id: str) -> dict[str, Any] | None:
        path = self.record_path(job_id)
        try:
            serialized = read_text_during_atomic_replace(path, encoding="utf-8")
        except FileNotFoundError:
            return None
        loaded = json.loads(serialized)
        if not isinstance(loaded, dict):
            raise ValueError(f"Action job record is not a JSON object: {job_id}")
        return loaded

    def latest(
        self,
        *,
        operation: str,
        scope: dict[str, Any],
    ) -> dict[str, Any] | None:
        normalized_scope = _normalize_scope(scope)
        scope_identity = _scope_identity(normalized_scope)
        for attempt in range(50):
            lock_path = self.root_dir / ".action-jobs.lock"
            if lock_path.exists():
                time.sleep(0.001)
                continue
            paths_before = tuple(sorted(self.root_dir.glob("job_*.json")))
            try:
                records = self._matching_records(
                    paths_before,
                    operation=operation,
                    scope_identity=scope_identity,
                )
            except (FileNotFoundError, PermissionError):
                time.sleep(0.001)
                continue
            paths_after = tuple(sorted(self.root_dir.glob("job_*.json")))
            if lock_path.exists() or paths_after != paths_before:
                time.sleep(0.001)
                continue
            return self._latest_record(records)

        paths = tuple(sorted(self.root_dir.glob("job_*.json")))
        records = self._matching_records(
            paths,
            operation=operation,
            scope_identity=scope_identity,
        )
        return self._latest_record(records)

    def _matching_records(
        self,
        paths: tuple[Path, ...],
        *,
        operation: str,
        scope_identity: str,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in paths:
            if not JOB_ID_RE.fullmatch(path.stem):
                continue
            loaded = json.loads(
                read_text_during_atomic_replace(path, encoding="utf-8")
            )
            if not isinstance(loaded, dict):
                raise ValueError(
                    f"Action job record is not a JSON object: {path.name}"
                )
            if (
                loaded.get("operation") == operation
                and isinstance(loaded.get("scope"), dict)
                and _scope_identity(loaded["scope"]) == scope_identity
            ):
                records.append(loaded)
        return records

    @staticmethod
    def _latest_record(records: list[dict[str, Any]]) -> dict[str, Any] | None:
        records.sort(
            key=lambda record: (
                str(record.get("updated_at_utc") or ""),
                str(record.get("created_at_utc") or ""),
            ),
            reverse=True,
        )
        return records[0] if records else None

    def record_path(self, job_id: str) -> Path:
        if not isinstance(job_id, str) or not JOB_ID_RE.fullmatch(job_id):
            raise ValueError("Invalid action job ID")
        return self.root_dir / f"{job_id}.json"


class ActionJobLedger:
    def __init__(self, root_dir: Path | str):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._lock = FileLock(str(self.root_dir / ".action-jobs.lock"))

    def allocate_job_id(self) -> str:
        return f"job_{uuid.uuid4().hex}"

    def create_pending(
        self,
        *,
        operation: str,
        scope: dict[str, Any],
        owner_instance: str,
    ) -> dict[str, Any]:
        normalized_scope = _normalize_scope(scope)
        with self._lock:
            return self._create_pending_unlocked(
                operation=operation,
                normalized_scope=normalized_scope,
                owner_instance=owner_instance,
            )

    def prepare_or_find_active(
        self,
        *,
        operation: str,
        scope: dict[str, Any],
        owner_instance: str,
    ) -> dict[str, Any]:
        record, _ = self.prepare_or_find_active_with_status(
            operation=operation,
            scope=scope,
            owner_instance=owner_instance,
        )
        return record

    def prepare_or_find_active_with_status(
        self,
        *,
        operation: str,
        scope: dict[str, Any],
        owner_instance: str,
    ) -> tuple[dict[str, Any], bool]:
        normalized_scope = _normalize_scope(scope)
        scope_identity = _scope_identity(normalized_scope)
        with self._lock:
            for record in self._records_unlocked():
                if (
                    record.get("operation") == operation
                    and isinstance(record.get("scope"), dict)
                    and _scope_identity(record["scope"]) == scope_identity
                    and record.get("state") in NONTERMINAL_STATES
                ):
                    return record, False
            created = self._create_pending_unlocked(
                operation=operation,
                normalized_scope=normalized_scope,
                owner_instance=owner_instance,
            )
            return created, True

    def list_records(
        self,
        *,
        operation: str | None = None,
        scope: dict[str, Any] | None = None,
        states: str | set[str] | frozenset[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("Action job list limit must be between 1 and 100")
        normalized_scope = _normalize_scope(scope) if scope is not None else None
        scope_identity = (
            _scope_identity(normalized_scope) if normalized_scope is not None else None
        )
        if isinstance(states, str):
            state_filter = {states}
        elif states is None:
            state_filter = None
        else:
            state_filter = set(states)
        with self._lock:
            records = [
                record
                for record in self._records_unlocked()
                if (operation is None or record.get("operation") == operation)
                and (
                    scope_identity is None
                    or (
                        isinstance(record.get("scope"), dict)
                        and _scope_identity(record["scope"]) == scope_identity
                    )
                )
                and (state_filter is None or record.get("state") in state_filter)
            ]
        records.sort(
            key=lambda record: (
                str(record.get("updated_at_utc") or ""),
                str(record.get("created_at_utc") or ""),
            ),
            reverse=True,
        )
        return records[:limit]

    def latest(
        self,
        *,
        operation: str,
        scope: dict[str, Any],
    ) -> dict[str, Any] | None:
        records = self.list_records(operation=operation, scope=scope, limit=1)
        return records[0] if records else None

    def list_prior_owner_records(
        self,
        *,
        current_owner_instance: str,
        states: set[str] | frozenset[str],
    ) -> list[dict[str, Any]]:
        current_owner = _validate_owner_instance(
            current_owner_instance, label="Current"
        )
        if not isinstance(states, (set, frozenset)):
            raise ValueError(
                "Prior-owner action job states must be a non-empty set of "
                "known nonterminal states"
            )
        state_filter = set(states)
        if not state_filter or not state_filter <= NONTERMINAL_STATES:
            raise ValueError(
                "Prior-owner action job states must be a non-empty set of "
                "known nonterminal states"
            )

        with self._lock:
            records = [
                record
                for record in self._records_unlocked()
                if record.get("state") in state_filter
                and record.get("owner_instance") != current_owner
            ]
            records.sort(
                key=lambda record: (
                    str(record.get("updated_at_utc") or ""),
                    str(record.get("created_at_utc") or ""),
                    str(record.get("job_id") or ""),
                ),
                reverse=True,
            )
            return records

    def transition(
        self,
        job_id: str,
        *,
        expected_states: str | set[str] | frozenset[str],
        new_state: str,
        **updates: Any,
    ) -> dict[str, Any]:
        if isinstance(expected_states, str):
            expected = {expected_states}
        else:
            expected = set(expected_states)
        if not expected or not expected <= ALL_STATES:
            raise ValueError("Expected action job states must be known and non-empty")
        if new_state not in ALL_STATES:
            raise InvalidTransitionError(f"Unknown action job state: {new_state}")
        validated_updates = _validate_updates(updates)

        with self._lock:
            record = self.load(job_id)
            if record is None:
                raise FileNotFoundError(f"Action job record not found: {job_id}")
            current_state = record.get("state")
            if current_state in TERMINAL_STATES:
                raise TerminalTransitionError(
                    f"Action job {job_id} is terminal in state {current_state}"
                )
            if current_state not in expected:
                raise StaleTransitionError(
                    f"Action job {job_id} expected {sorted(expected)}, found {current_state}"
                )
            if new_state not in PERMITTED_TRANSITIONS.get(str(current_state), frozenset()):
                raise InvalidTransitionError(
                    f"Action job transition {current_state} -> {new_state} is not permitted"
                )
            updated = dict(record)
            updated.update(validated_updates)
            updated["state"] = new_state
            updated["updated_at_utc"] = _utc_now_iso()
            atomic_write_json_for_concurrent_readers(
                self.record_path(job_id), updated
            )
            return updated

    def compare_and_update(
        self,
        job_id: str,
        *,
        expected_state: str,
        **updates: Any,
    ) -> dict[str, Any]:
        if expected_state not in NONTERMINAL_STATES:
            raise ValueError("Expected action job state must be nonterminal")
        if not updates:
            raise ValueError("Action job metadata update must not be empty")
        validated_updates = _validate_updates(updates)

        with self._lock:
            record = self.load(job_id)
            if record is None:
                raise FileNotFoundError(f"Action job record not found: {job_id}")
            current_state = record.get("state")
            if current_state in TERMINAL_STATES:
                raise TerminalTransitionError(
                    f"Action job {job_id} is terminal in state {current_state}"
                )
            if current_state != expected_state:
                raise StaleTransitionError(
                    f"Action job {job_id} expected {expected_state}, found {current_state}"
                )
            updated = dict(record)
            updated.update(validated_updates)
            updated["updated_at_utc"] = _utc_now_iso()
            atomic_write_json_for_concurrent_readers(
                self.record_path(job_id), updated
            )
            return updated

    def adopt_owner(
        self,
        job_id: str,
        *,
        expected_state: str,
        expected_owner_instance: str,
        new_owner_instance: str,
    ) -> dict[str, Any]:
        if expected_state not in NONTERMINAL_STATES:
            raise ValueError("Expected action job state must be nonterminal")
        expected_owner = _validate_owner_instance(
            expected_owner_instance, label="Expected"
        )
        new_owner = _validate_owner_instance(new_owner_instance, label="Replacement")

        with self._lock:
            record = self.load(job_id)
            if record is None:
                raise FileNotFoundError(f"Action job record not found: {job_id}")
            current_state = record.get("state")
            if current_state in TERMINAL_STATES:
                raise TerminalTransitionError(
                    f"Action job {job_id} is terminal in state {current_state}"
                )
            if current_state != expected_state:
                raise StaleTransitionError(
                    f"Action job {job_id} expected {expected_state}, found {current_state}"
                )
            if record.get("owner_instance") != expected_owner:
                raise StaleTransitionError(
                    f"Action job {job_id} owner does not match expected owner"
                )
            updated = dict(record)
            updated["owner_instance"] = new_owner
            updated["updated_at_utc"] = _utc_now_iso()
            atomic_write_json_for_concurrent_readers(
                self.record_path(job_id), updated
            )
            return updated

    def reconcile_prior_owner(
        self, current_owner_instance: str
    ) -> list[dict[str, Any]]:
        if not isinstance(current_owner_instance, str) or not current_owner_instance:
            raise ValueError("Current owner instance must be a non-empty string")
        interrupted: list[dict[str, Any]] = []
        with self._lock:
            for record in self._records_unlocked():
                if (
                    record.get("state") not in {"queued", "running"}
                    or record.get("owner_instance") == current_owner_instance
                ):
                    continue
                updated = dict(record)
                updated["state"] = "interrupted"
                updated["updated_at_utc"] = _utc_now_iso()
                updated["outcome"] = {
                    "code": "owner_replaced",
                    "message": "Interrupted after owner instance changed",
                }
                job_id = str(updated.get("job_id"))
                atomic_write_json_for_concurrent_readers(
                    self.record_path(job_id), updated
                )
                interrupted.append(updated)
        return interrupted

    def _create_pending_unlocked(
        self,
        *,
        operation: str,
        normalized_scope: dict[str, Any],
        owner_instance: str,
    ) -> dict[str, Any]:
        job_id = self.allocate_job_id()
        while self.record_path(job_id).exists():
            job_id = self.allocate_job_id()
        timestamp = _utc_now_iso()
        record: dict[str, Any] = {
            "schema": SCHEMA_VERSION,
            "job_id": job_id,
            "operation": operation,
            "scope": normalized_scope,
            "owner_instance": owner_instance,
            "state": "pending_confirmation",
            "created_at_utc": timestamp,
            "updated_at_utc": timestamp,
            "token_fingerprint": None,
            "authorization_request_id": None,
            "outcome": None,
            "audit_status": None,
        }
        atomic_write_json_for_concurrent_readers(self.record_path(job_id), record)
        return record

    def _records_unlocked(self) -> list[dict[str, Any]]:
        records = []
        for path in self.root_dir.glob("job_*.json"):
            if not JOB_ID_RE.fullmatch(path.stem):
                continue
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError(f"Action job record is not a JSON object: {path.name}")
            records.append(loaded)
        return records

    def load(self, job_id: str) -> dict[str, Any] | None:
        path = self.record_path(job_id)
        if not path.exists():
            return None
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"Action job record is not a JSON object: {job_id}")
        return loaded

    def record_path(self, job_id: str) -> Path:
        if not isinstance(job_id, str) or not JOB_ID_RE.fullmatch(job_id):
            raise ValueError("Invalid action job ID")
        return self.root_dir / f"{job_id}.json"
