"""
GoodQ4All — Identity Workbench API Router
==========================================
Serves JSON for the identity_workbench UI:

  GET  /api/identity/face-clusters
  POST /api/identity/rebuild-face-clusters?eps=0.4
  POST /api/identity/face-clusters/label
  GET  /api/identity/speaker-clusters
  POST /api/identity/speaker-clusters/confirm
  GET  /api/identity/name-mentions
  GET  /api/identity/roster
  GET  /api/identity/evidence-pack
  GET  /api/identity/scene-evidence
  POST /api/identity/roster/save
  POST /api/identity/roster/validate
  POST /api/identity/roster/export

All routes are read-mostly. The only writes are:
  - face cluster labels (stored in face_clusters.json, no KG writes)
  - speaker cluster confirmations (stored in speaker_clusters.json, no KG writes)
  - roster saves (stored in family_roster.yaml, no KG writes)
  - roster export (writes family_roster.yaml to data path)

No KG mutations happen here. Mutations are Phase 5A (promote_identity_layer.py),
which requires a separate confirmed CLI flow.
"""

from __future__ import annotations

import json
import hashlib
import logging
import math
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from filelock import FileLock
from pydantic import BaseModel, Field

from agents.mini_agent_client import MiniAgentClient
from api.utils.identity_evidence_pack import (
    build_identity_evidence_pack,
    load_identity_scene_evidence,
)
from api.utils.action_jobs import (
    ActionJobLedger,
    ActionJobTransitionError,
    PassiveActionJobReader,
)
from api.utils.identity_read_projection import (
    epoch_authority_projection,
    identity_data_path,
    project_face_cluster_images,
)
from steps.common.config_loader import load_configs

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/identity", tags=["identity"])

_CFG = load_configs({})

_REBUILD_FACE_CLUSTERS_OPERATION = "identity.rebuild_face_clusters"
_VALIDATE_ROSTER_OPERATION = "identity.validate_roster"
_REBUILD_LAUNCH_PROTOCOL = "stdin_gate_v1"
_REBUILD_AUDIT_TARGETS = (
    "face_clusters.json",
    "reports/face_cluster_sheet.html",
)
_IDENTITY_PROCESS_OPERATIONS = frozenset(
    {_REBUILD_FACE_CLUSTERS_OPERATION, _VALIDATE_ROSTER_OPERATION}
)
_IDENTITY_PROCESS_OWNER_RE = re.compile(
    r"^identity-api:([0-9a-f]{16}):([1-9][0-9]{0,19}):"
    r"([0-9a-f]{1,32}|unknown):([0-9a-f]{32})$"
)
_IDENTITY_PROCESS_STATES = frozenset(
    {
        "pending_confirmation",
        "authorizing",
        "queued",
        "running",
        "succeeded",
        "failed",
        "interrupted",
        "expired",
    }
)
_IDENTITY_PROCESS_TERMINAL_STATES = frozenset(
    {"succeeded", "failed", "interrupted", "expired"}
)


def _identity_process_host_fingerprint() -> str:
    hostname = socket.gethostname().strip().lower()
    return hashlib.sha256(hostname.encode("utf-8")).hexdigest()[:16]


_IDENTITY_PROCESS_HOST_FINGERPRINT = _identity_process_host_fingerprint()


def _windows_process_start_token(pid: int) -> tuple[str, str | None]:
    try:
        import ctypes
        from ctypes import wintypes

        process_query_limited_information = 0x1000
        synchronize = 0x00100000
        wait_object_0 = 0x00000000
        wait_timeout = 0x00000102
        wait_failed = 0xFFFFFFFF
        error_invalid_parameter = 87
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.GetProcessTimes.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        ]
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        ctypes.set_last_error(0)
        handle = kernel32.OpenProcess(
            process_query_limited_information | synchronize,
            False,
            pid,
        )
        if not handle:
            if ctypes.get_last_error() == error_invalid_parameter:
                return "dead", None
            return "unknown", None
        try:
            wait_result = kernel32.WaitForSingleObject(handle, 0)
            if wait_result == wait_object_0:
                return "dead", None
            if wait_result == wait_failed:
                return "unknown", None
            if wait_result != wait_timeout:
                return "unknown", None
            creation = wintypes.FILETIME()
            exit_time = wintypes.FILETIME()
            kernel = wintypes.FILETIME()
            user = wintypes.FILETIME()
            if not kernel32.GetProcessTimes(
                handle,
                ctypes.byref(creation),
                ctypes.byref(exit_time),
                ctypes.byref(kernel),
                ctypes.byref(user),
            ):
                return "unknown", None
            filetime = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
            return "live", f"{filetime:x}"
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return "unknown", None


def _proc_process_start_token(pid: int) -> tuple[str, str | None]:
    stat_path = Path("/proc") / str(pid) / "stat"
    try:
        serialized = stat_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "dead", None
    except OSError:
        return "unknown", None
    closing_paren = serialized.rfind(")")
    if closing_paren < 0:
        return "unknown", None
    fields = serialized[closing_paren + 1 :].strip().split()
    if len(fields) <= 19 or not fields[19].isdigit():
        return "unknown", None
    if fields[0] == "Z":
        return "dead", None
    return "live", f"{int(fields[19]):x}"


def _probe_process_start_token(pid: int) -> tuple[str, str | None]:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return "unknown", None
    if os.name == "nt":
        return _windows_process_start_token(pid)
    if os.name == "posix" and Path("/proc").is_dir():
        return _proc_process_start_token(pid)
    return "unknown", None


def _new_identity_process_owner() -> str:
    state, start_token = _probe_process_start_token(os.getpid())
    bound_start_token = start_token if state == "live" and start_token else "unknown"
    return (
        f"identity-api:{_IDENTITY_PROCESS_HOST_FINGERPRINT}:{os.getpid()}:"
        f"{bound_start_token}:{uuid.uuid4().hex}"
    )


_IDENTITY_PROCESS_OWNER_INSTANCE = _new_identity_process_owner()


def _classify_identity_process_owner(owner_instance: Any) -> str:
    if not isinstance(owner_instance, str):
        return "unknown"
    match = _IDENTITY_PROCESS_OWNER_RE.fullmatch(owner_instance)
    if match is None:
        return "unknown"
    host_fingerprint, raw_pid, persisted_start_token, _random_instance = match.groups()
    if host_fingerprint != _IDENTITY_PROCESS_HOST_FINGERPRINT:
        return "unknown"
    if persisted_start_token == "unknown":
        return "unknown"
    state, observed_start_token = _probe_process_start_token(int(raw_pid))
    if state != "live":
        return state if state in {"dead", "unknown"} else "unknown"
    if observed_start_token is None:
        return "unknown"
    return "live" if observed_start_token == persisted_start_token else "dead"


def _classify_identity_process_child(pid: int, persisted_start_token: str) -> str:
    state, observed_start_token = _probe_process_start_token(pid)
    if state != "live":
        return state if state in {"dead", "unknown"} else "unknown"
    if observed_start_token is None:
        return "unknown"
    return "live" if observed_start_token == persisted_start_token else "dead"

# ── Data path resolution ────────────────────────────────────────────────────

def _identity_data_path() -> Path:
    """Returns the identity data path from config or env."""
    return identity_data_path(_CFG)


def _identity_epoch_authority() -> dict[str, Any]:
    return epoch_authority_projection(_CFG, _identity_data_path())


def _data_path() -> Path:
    p = _identity_data_path()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _epoch_id() -> str:
    """Returns the active epoch ID from config."""
    return _CFG.get("epoch_id", "") or ""


def _identity_process_job_root() -> Path:
    return _identity_data_path() / "process_jobs"


@dataclass(frozen=True)
class _IdentityTargetObservation:
    state: str
    content: bytes | None = None
    identity: tuple[int, int, int, int] | None = None


def _target_stat_identity(stat_result: os.stat_result) -> tuple[int, int, int, int]:
    return (
        int(stat_result.st_dev),
        int(stat_result.st_ino),
        int(stat_result.st_size),
        int(stat_result.st_mtime_ns),
    )


def _observe_identity_target(path: Path) -> _IdentityTargetObservation:
    try:
        before = path.stat()
    except FileNotFoundError:
        try:
            path.stat()
        except FileNotFoundError:
            return _IdentityTargetObservation("absent")
        except OSError:
            return _IdentityTargetObservation("indeterminate")
        return _IdentityTargetObservation("indeterminate")
    except OSError:
        return _IdentityTargetObservation("indeterminate")
    try:
        content = path.read_bytes()
        after = path.stat()
    except (FileNotFoundError, OSError):
        return _IdentityTargetObservation("indeterminate")
    before_identity = _target_stat_identity(before)
    after_identity = _target_stat_identity(after)
    if before_identity != after_identity or len(content) != after.st_size:
        return _IdentityTargetObservation("indeterminate")
    return _IdentityTargetObservation(
        "present",
        content=content,
        identity=after_identity,
    )


def _target_was_mutated(
    before: _IdentityTargetObservation,
    after: _IdentityTargetObservation,
) -> bool:
    if "indeterminate" in {before.state, after.state}:
        return True
    return before != after


def _observe_identity_targets(
    paths: tuple[Path, ...],
) -> tuple[_IdentityTargetObservation, ...]:
    return tuple(_observe_identity_target(path) for path in paths)


def _targets_were_mutated(
    before: tuple[_IdentityTargetObservation, ...],
    after: tuple[_IdentityTargetObservation, ...],
) -> bool:
    return len(before) != len(after) or any(
        _target_was_mutated(before_item, after_item)
        for before_item, after_item in zip(before, after)
    )


def _nonempty_unique_strings(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
        and len(set(value)) == len(value)
    )


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _validate_face_cluster_rebuild_result(
    observation: _IdentityTargetObservation,
    *,
    epoch_id: str,
    eps: float,
) -> dict[str, Any]:
    if observation.state != "present" or observation.content is None:
        raise ValueError("Face cluster rebuild output is unavailable")
    try:
        loaded = json.loads(observation.content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Face cluster rebuild output is malformed") from exc
    if not isinstance(loaded, dict):
        raise ValueError("Face cluster rebuild output is not an object")
    if loaded.get("epoch_id") != epoch_id:
        raise ValueError("Face cluster rebuild epoch does not match request")
    eps_used = loaded.get("eps_used")
    if not _finite_number(eps_used) or not math.isclose(
        float(eps_used), float(eps), rel_tol=0.0, abs_tol=1e-12
    ):
        raise ValueError("Face cluster rebuild epsilon does not match request")
    generated_at = loaded.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise ValueError("Face cluster rebuild timestamp is invalid")
    try:
        generated = datetime.fromisoformat(generated_at)
    except ValueError as exc:
        raise ValueError("Face cluster rebuild timestamp is invalid") from exc
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise ValueError("Face cluster rebuild timestamp is not timezone aware")
    note = loaded.get("note")
    if not isinstance(note, str) or not note.strip():
        raise ValueError("Face cluster rebuild note is invalid")
    cluster_count = loaded.get("cluster_count")
    unassigned_count = loaded.get("unassigned_count")
    clusters = loaded.get("clusters")
    unassigned = loaded.get("unassigned_face_ids")
    if not _nonnegative_int(cluster_count) or not _nonnegative_int(unassigned_count):
        raise ValueError("Face cluster rebuild counts are invalid")
    if not isinstance(clusters, list) or not isinstance(unassigned, list):
        raise ValueError("Face cluster rebuild lists are invalid")
    if cluster_count != len(clusters) or unassigned_count != len(unassigned):
        raise ValueError("Face cluster rebuild counts do not match lists")
    if any(not isinstance(face_id, str) or not face_id.strip() for face_id in unassigned):
        raise ValueError("Unassigned face IDs are invalid")
    if len(set(unassigned)) != len(unassigned):
        raise ValueError("Unassigned face IDs are not unique")

    required_cluster_keys = {
        "cluster_id",
        "status",
        "label",
        "confirmed",
        "face_count",
        "video_count",
        "video_hashes",
        "timestamp_range",
        "face_ids",
        "representative_frame",
    }
    cluster_ids: set[str] = set()
    clustered_face_ids: set[str] = set()
    for cluster in clusters:
        if not isinstance(cluster, dict) or not required_cluster_keys <= set(cluster):
            raise ValueError("Face cluster object is incomplete")
        cluster_id = cluster.get("cluster_id")
        if (
            not isinstance(cluster_id, str)
            or not re.fullmatch(r"face_cluster_[0-9]+", cluster_id)
            or cluster_id in cluster_ids
        ):
            raise ValueError("Face cluster ID is invalid or duplicated")
        cluster_ids.add(cluster_id)
        if (
            cluster.get("status") != "candidate"
            or cluster.get("label") is not None
            or cluster.get("confirmed") is not False
        ):
            raise ValueError("Face cluster candidate state is invalid")
        face_count = cluster.get("face_count")
        video_count = cluster.get("video_count")
        face_ids = cluster.get("face_ids")
        video_hashes = cluster.get("video_hashes")
        if not _positive_int(face_count) or not _positive_int(video_count):
            raise ValueError("Face cluster member counts are invalid")
        if not _nonempty_unique_strings(face_ids) or not _nonempty_unique_strings(
            video_hashes
        ):
            raise ValueError("Face cluster members are invalid")
        if face_count != len(face_ids) or video_count != len(video_hashes):
            raise ValueError("Face cluster member counts do not match lists")
        timestamp_range = cluster.get("timestamp_range")
        if not isinstance(timestamp_range, list) or not (
            timestamp_range == []
            or (
                len(timestamp_range) == 2
                and all(_finite_number(item) for item in timestamp_range)
                and float(timestamp_range[0]) <= float(timestamp_range[1])
            )
        ):
            raise ValueError("Face cluster timestamp range is invalid")
        representative = cluster.get("representative_frame")
        if not isinstance(representative, str) or not representative.strip():
            raise ValueError("Face cluster representative frame is invalid")
        if clustered_face_ids.intersection(face_ids):
            raise ValueError("Face IDs are duplicated across clusters")
        clustered_face_ids.update(face_ids)
    if clustered_face_ids.intersection(unassigned):
        raise ValueError("Clustered and unassigned face IDs overlap")
    return loaded


def _canonical_utc_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("Persisted identity process timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Persisted identity process timestamp is invalid") from exc
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() != timezone.utc.utcoffset(parsed)
        or parsed.isoformat() != value
    ):
        raise ValueError("Persisted identity process timestamp is not canonical UTC")
    return parsed


def _validate_identity_process_outcome(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {"code", "message"}:
        raise ValueError("Persisted identity process outcome is invalid")
    code = value.get("code")
    message = value.get("message")
    if not isinstance(code, str) or not re.fullmatch(r"[a-z0-9_.-]{1,64}", code):
        raise ValueError("Persisted identity process outcome code is invalid")
    if not isinstance(message, str) or not 1 <= len(message) <= 512:
        raise ValueError("Persisted identity process outcome message is invalid")
    unsafe_patterns = (
        r"traceback\s*\(",
        r"\b(?:stdout|stderr)\b\s*[:=]",
        r"\bsubprocess\s+output\b",
        r"\b[A-Za-z]+(?:Error|Exception):",
        r"[A-Za-z]:[\\/]",
        r"(?:^|\s)\\\\[^\s]+",
        r"(?:^|\s)/(?:[^/\s]+/)*[^/\s]+",
        r"(?:^|\s)~[\\/]",
    )
    if "\n" in message or "\r" in message or any(
        re.search(pattern, message, re.IGNORECASE) for pattern in unsafe_patterns
    ):
        raise ValueError("Persisted identity process outcome is not sanitized")


def _validate_identity_process_record(
    record: Any,
    *,
    expected_job_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("Persisted identity process job is not an object")
    if record.get("schema") != "goodq.action-job.v1":
        raise ValueError("Persisted identity process schema is invalid")
    job_id = record.get("job_id")
    if not isinstance(job_id, str) or not re.fullmatch(r"job_[0-9a-f]{32}", job_id):
        raise ValueError("Persisted identity process job ID is invalid")
    if expected_job_id is not None and job_id != expected_job_id:
        raise ValueError("Persisted identity process job ID does not match its file")
    _identity_process_audit_arguments(record)
    owner = record.get("owner_instance")
    if not isinstance(owner, str) or not re.fullmatch(
        r"[A-Za-z0-9_.:-]{1,128}", owner
    ):
        raise ValueError("Persisted identity process owner is invalid")
    state = record.get("state")
    if state not in _IDENTITY_PROCESS_STATES:
        raise ValueError("Persisted identity process state is invalid")
    launch_protocol_present = "launch_protocol" in record
    child_pid_present = "child_pid" in record
    child_token_present = "child_start_token" in record
    if record.get("operation") != _REBUILD_FACE_CLUSTERS_OPERATION and (
        launch_protocol_present or child_pid_present or child_token_present
    ):
        raise ValueError("Persisted launch metadata is invalid for operation")
    if launch_protocol_present:
        if record.get("launch_protocol") != _REBUILD_LAUNCH_PROTOCOL:
            raise ValueError("Persisted identity process launch protocol is invalid")
        if state not in {"running", "succeeded", "failed", "interrupted"}:
            raise ValueError("Persisted identity process launch state is invalid")
    if child_pid_present != child_token_present:
        raise ValueError("Persisted identity process child pair is incomplete")
    if child_pid_present:
        child_pid = record.get("child_pid")
        child_start_token = record.get("child_start_token")
        if not launch_protocol_present:
            raise ValueError("Persisted identity process child has no launch protocol")
        if (
            not isinstance(child_pid, int)
            or isinstance(child_pid, bool)
            or child_pid <= 0
        ):
            raise ValueError("Persisted identity process child PID is invalid")
        if not isinstance(child_start_token, str) or not re.fullmatch(
            r"[0-9a-f]{1,32}", child_start_token
        ):
            raise ValueError("Persisted identity process child token is invalid")
    created = _canonical_utc_timestamp(record.get("created_at_utc"))
    updated = _canonical_utc_timestamp(record.get("updated_at_utc"))
    if updated < created:
        raise ValueError("Persisted identity process timestamps are inconsistent")
    token_fingerprint = record.get("token_fingerprint")
    if token_fingerprint is not None and (
        not isinstance(token_fingerprint, str)
        or not re.fullmatch(r"[0-9a-f]{64}", token_fingerprint)
    ):
        raise ValueError("Persisted identity process token fingerprint is invalid")
    request_id = record.get("authorization_request_id")
    if request_id is not None and (
        not isinstance(request_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", request_id)
    ):
        raise ValueError("Persisted identity process authorization ID is invalid")
    _validate_identity_process_outcome(record.get("outcome"))
    if state in _IDENTITY_PROCESS_TERMINAL_STATES and record.get("outcome") is None:
        raise ValueError("Persisted terminal identity process has no outcome")
    if state not in _IDENTITY_PROCESS_TERMINAL_STATES and record.get("outcome") is not None:
        raise ValueError("Persisted active identity process has an outcome")
    audit_status = record.get("audit_status")
    if audit_status is not None and (
        not isinstance(audit_status, str)
        or not re.fullmatch(r"[a-z0-9_.-]{1,64}", audit_status)
    ):
        raise ValueError("Persisted identity process audit status is invalid")
    return record


def _validate_identity_process_job_files(root: Path) -> None:
    if not root.exists():
        return
    reader = PassiveActionJobReader(root)
    for path in sorted(root.glob("job_*.json")):
        if not re.fullmatch(r"job_[0-9a-f]{32}", path.stem):
            continue
        record = reader.load(path.stem)
        if record is None or record.get("operation") not in _IDENTITY_PROCESS_OPERATIONS:
            continue
        _validate_identity_process_record(record, expected_job_id=path.stem)


def _public_identity_process_job(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in (
            "job_id",
            "operation",
            "scope",
            "state",
            "created_at_utc",
            "updated_at_utc",
            "outcome",
            "audit_status",
        )
    }


def _identity_process_audit_arguments(record: dict[str, Any]) -> dict[str, Any]:
    operation = record.get("operation")
    scope = record.get("scope")
    if not isinstance(scope, dict):
        raise ValueError("Persisted identity process scope is invalid")
    if operation == _REBUILD_FACE_CLUSTERS_OPERATION:
        if set(scope) != {"epoch_id", "eps"}:
            raise ValueError("Persisted face rebuild scope is invalid")
        epoch_id = scope.get("epoch_id")
        eps = scope.get("eps")
        if not isinstance(epoch_id, str) or not epoch_id:
            raise ValueError("Persisted face rebuild epoch is invalid")
        if (
            not isinstance(eps, (int, float))
            or isinstance(eps, bool)
            or not math.isfinite(float(eps))
            or not 0.05 <= float(eps) <= 0.95
        ):
            raise ValueError("Persisted face rebuild epsilon is invalid")
        return {"eps": eps}
    if operation == _VALIDATE_ROSTER_OPERATION:
        if scope:
            raise ValueError("Persisted roster validation scope is invalid")
        return {}
    raise ValueError("Persisted identity process operation is invalid")


def _record_identity_process_audit(
    authority: Any,
    record: dict[str, Any],
    *,
    status: str,
    return_code: int,
    duration_ms: int,
    mutated: bool,
    error_codes: list[str],
) -> str:
    operation = str(record.get("operation") or "")
    arguments = _identity_process_audit_arguments(record)
    targets = (
        list(_REBUILD_AUDIT_TARGETS)
        if operation == _REBUILD_FACE_CLUSTERS_OPERATION
        else []
    )
    try:
        result = authority.record_external_execution_outcome(
            operation=operation,
            arguments=arguments,
            request_id=str(record.get("authorization_request_id") or ""),
            mode="ops",
            status=status,
            return_code=return_code,
            duration_ms=max(0, int(duration_ms)),
            side_effect_report={"mutated": mutated, "targets": targets},
            error_codes=error_codes,
        )
    except Exception:
        log.error("Identity process execution audit failed for operation %s", operation)
        return "failed"
    if isinstance(result, dict) and result.get("audit_status") == "recorded":
        return "recorded"
    return "failed"


def _terminalize_identity_process(
    ledger: ActionJobLedger,
    record: dict[str, Any],
    authority: Any,
    *,
    terminal_state: str,
    outcome_code: str,
    outcome_message: str,
    audit_status: str,
    return_code: int,
    duration_ms: int,
    mutated: bool,
) -> dict[str, Any]:
    persisted_audit_status = _record_identity_process_audit(
        authority,
        record,
        status=audit_status,
        return_code=return_code,
        duration_ms=duration_ms,
        mutated=mutated,
        error_codes=[] if audit_status == "succeeded" else [outcome_code],
    )
    return ledger.transition(
        str(record["job_id"]),
        expected_states="running",
        new_state=terminal_state,
        outcome={"code": outcome_code, "message": outcome_message},
        audit_status=persisted_audit_status,
    )


def _close_gated_process_stdin(process: Any) -> None:
    stream = getattr(process, "stdin", None)
    if stream is None:
        return
    try:
        stream.close()
    except Exception:
        pass
    try:
        process.stdin = None
    except Exception:
        pass


def _terminate_and_reap_gated_process(process: Any) -> tuple[bool, int]:
    _close_gated_process_stdin(process)
    try:
        process.terminate()
    except Exception:
        pass
    confirmed = False
    return_code = 1
    try:
        return_code = int(process.wait(timeout=2))
        confirmed = True
    except Exception:
        try:
            process.kill()
        except Exception:
            pass
        try:
            return_code = int(process.wait(timeout=2))
            confirmed = True
        except Exception:
            confirmed = False
    if confirmed:
        try:
            process.communicate(timeout=2)
        except Exception:
            pass
    return confirmed, return_code


def _terminalize_face_rebuild_failure(
    ledger: ActionJobLedger,
    job: dict[str, Any],
    authority: Any,
    *,
    target_paths: tuple[Path, ...],
    targets_before: tuple[_IdentityTargetObservation, ...],
    started_at: float,
    return_code: int,
) -> dict[str, Any]:
    targets_after = _observe_identity_targets(target_paths)
    return _terminalize_identity_process(
        ledger,
        job,
        authority,
        terminal_state="failed",
        outcome_code="face_cluster_rebuild_failed",
        outcome_message="Face cluster rebuild failed",
        audit_status="failed",
        return_code=return_code,
        duration_ms=int((time.time() - started_at) * 1000),
        mutated=_targets_were_mutated(targets_before, targets_after),
    )


def _recover_dead_identity_process_job(
    ledger: ActionJobLedger,
    record: dict[str, Any],
    *,
    authority: Any | None = None,
) -> dict[str, Any]:
    validated = _validate_identity_process_record(record)
    job_id = str(validated["job_id"])
    recovery_lock = FileLock(
        str(ledger.root_dir / ".identity-process-recovery.lock")
    )
    with recovery_lock:
        current = ledger.load(job_id)
        if current is None:
            raise ActionJobTransitionError("Identity process recovery record disappeared")
        current = _validate_identity_process_record(
            current,
            expected_job_id=job_id,
        )
        state = str(current["state"])
        prior_owner = str(current["owner_instance"])
        if (
            state != validated.get("state")
            or prior_owner != validated.get("owner_instance")
            or _classify_identity_process_owner(prior_owner) != "dead"
        ):
            raise ActionJobTransitionError("Identity process recovery claim is stale")

        running_rebuild_may_have_mutated = False
        if (
            state == "running"
            and current.get("operation") == _REBUILD_FACE_CLUSTERS_OPERATION
        ):
            if current.get("launch_protocol") != _REBUILD_LAUNCH_PROTOCOL:
                raise ActionJobTransitionError(
                    "Running face rebuild has no proven launch protocol"
                )
            if "child_pid" in current:
                child_state = _classify_identity_process_child(
                    int(current["child_pid"]),
                    str(current["child_start_token"]),
                )
                if child_state != "dead":
                    raise ActionJobTransitionError(
                        "Running face rebuild child is not conclusively dead"
                    )
                running_rebuild_may_have_mutated = True

        updates: dict[str, Any]
        if state in {"pending_confirmation", "authorizing"}:
            terminal_state = "failed"
            updates = {
                "outcome": {
                    "code": "authorization_interrupted",
                    "message": "Identity process authorization was interrupted by restart",
                }
            }
        elif state in {"queued", "running"}:
            terminal_state = "interrupted"
            operation = current.get("operation")
            mutation_is_unknown = running_rebuild_may_have_mutated
            if mutation_is_unknown:
                audit_status = "not_recorded_mutation_unknown"
            else:
                if authority is None:
                    try:
                        authority = MiniAgentClient(profile="safe")
                    except Exception:
                        log.error(
                            "Identity process recovery audit authority is unavailable"
                        )
                audit_status = (
                    _record_identity_process_audit(
                        authority,
                        current,
                        status="interrupted",
                        return_code=1,
                        duration_ms=0,
                        mutated=False,
                        error_codes=["execution_interrupted"],
                    )
                    if authority is not None
                    else "failed"
                )
            updates = {
                "outcome": {
                    "code": "execution_interrupted",
                    "message": "Identity process execution was interrupted by owner exit",
                },
                "audit_status": audit_status,
            }
        else:
            raise ActionJobTransitionError(
                "Persisted identity process is no longer recoverable"
            )
        return ledger.adopt_and_transition(
            job_id,
            expected_state=state,
            expected_owner_instance=prior_owner,
            new_owner_instance=prior_owner,
            new_state=terminal_state,
            **updates,
        )


def _reject_or_recover_active_identity_process_job(
    ledger: ActionJobLedger,
    record: dict[str, Any],
    *,
    authority: Any,
) -> None:
    owner_instance = record.get("owner_instance")
    if owner_instance == _IDENTITY_PROCESS_OWNER_INSTANCE:
        raise HTTPException(status_code=409, detail="identity_process_active")
    classification = _classify_identity_process_owner(owner_instance)
    if classification != "dead":
        raise HTTPException(status_code=409, detail="identity_process_active")
    try:
        _recover_dead_identity_process_job(ledger, record, authority=authority)
    except ActionJobTransitionError:
        raise HTTPException(status_code=409, detail="identity_process_active")
    raise HTTPException(
        status_code=409,
        detail="identity_process_recovered_retry_required",
    )


def _prepare_identity_process_job(
    *,
    operation: str,
    scope: dict[str, Any],
    confirmation_token: str,
    authorization_result: dict[str, Any],
    authority: Any,
) -> tuple[ActionJobLedger, dict[str, Any]]:
    request_id = authorization_result.get("request_id")
    if not isinstance(request_id, str) or not re.fullmatch(
        r"[A-Za-z0-9_.:-]{1,128}", request_id
    ):
        raise HTTPException(
            status_code=500,
            detail="identity_process_authorization_invalid",
        )
    root = _identity_process_job_root()
    ledger = ActionJobLedger(root)
    _validate_identity_process_job_files(root)
    record, created = ledger.prepare_or_find_active_with_status(
        operation=operation,
        scope=scope,
        owner_instance=_IDENTITY_PROCESS_OWNER_INSTANCE,
    )
    _validate_identity_process_job_files(root)
    _validate_identity_process_record(record)
    if not created:
        _reject_or_recover_active_identity_process_job(
            ledger,
            record,
            authority=authority,
        )
    record = ledger.transition(
        str(record["job_id"]),
        expected_states="pending_confirmation",
        new_state="authorizing",
        token_fingerprint=hashlib.sha256(
            confirmation_token.encode("utf-8")
        ).hexdigest(),
        authorization_request_id=request_id,
    )
    record = ledger.transition(
        str(record["job_id"]),
        expected_states="authorizing",
        new_state="queued",
    )
    record = ledger.transition(
        str(record["job_id"]),
        expected_states="queued",
        new_state="running",
        **(
            {"launch_protocol": _REBUILD_LAUNCH_PROTOCOL}
            if operation == _REBUILD_FACE_CLUSTERS_OPERATION
            else {}
        ),
    )
    return ledger, record


def _reconcile_identity_process_jobs() -> None:
    root = _identity_process_job_root()
    if not root.exists():
        return
    _validate_identity_process_job_files(root)
    ledger = ActionJobLedger(root)
    records = ledger.list_prior_owner_records(
        current_owner_instance=_IDENTITY_PROCESS_OWNER_INSTANCE,
        states={"pending_confirmation", "authorizing", "queued", "running"},
    )
    _validate_identity_process_job_files(root)
    for record in records:
        if record.get("operation") not in _IDENTITY_PROCESS_OPERATIONS:
            continue
        _validate_identity_process_record(record)
        if _classify_identity_process_owner(record.get("owner_instance")) != "dead":
            continue
        try:
            _recover_dead_identity_process_job(ledger, record)
        except ActionJobTransitionError:
            continue


async def _reconcile_identity_process_jobs_on_startup() -> None:
    _reconcile_identity_process_jobs()


router.add_event_handler("startup", _reconcile_identity_process_jobs_on_startup)


def _load_json_file(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json_file(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@router.get("/process-jobs/{job_id}")
async def get_identity_process_job(job_id: str) -> dict[str, Any]:
    reader = PassiveActionJobReader(_identity_process_job_root())
    try:
        record = reader.load(job_id)
    except ValueError:
        record = None
    if record is None or record.get("operation") not in _IDENTITY_PROCESS_OPERATIONS:
        raise HTTPException(status_code=404, detail="identity_process_job_not_found")
    try:
        _validate_identity_process_record(record, expected_job_id=job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="identity_process_job_not_found")
    return _public_identity_process_job(record)


# ── Face Clusters ───────────────────────────────────────────────────────────

@router.get("/face-clusters")
async def get_face_clusters() -> dict:
    """Returns face_clusters.json from the identity data path."""
    path = _identity_data_path() / "face_clusters.json"
    data = _load_json_file(path)
    authority = _identity_epoch_authority()
    if data is None:
        return {
            "clusters": [],
            "message": "face_clusters.json not found. Run Phase 1.",
            "epoch_authority": authority,
        }
    projected = project_face_cluster_images(data, _CFG, authority)
    projected["epoch_authority"] = authority
    return projected


class RebuildFaceClustersRequest(BaseModel):
    eps: float = Field(0.4, ge=0.05, le=0.95)
    confirmation_token: Optional[str] = Field(None)


@router.post("/rebuild-face-clusters")
async def rebuild_face_clusters(body: RebuildFaceClustersRequest) -> dict:
    """
    Triggers a re-run of build_face_clusters.py with the given eps.
    Blocking — may take ~30s for large datasets.
    Requires MiniAgent confirmation before subprocess execution.
    """
    _start = time.time()

    _tool_args = {"eps": body.eps}
    _authority = MiniAgentClient(profile="safe")
    _result, _code = _authority.authorize_action(
        prompt="Confirm identity process execution: rebuild face clusters",
        mode="ops",
        tool_name="identity.rebuild_face_clusters",
        tool_args=_tool_args,
        confirm=bool(body.confirmation_token),
        confirmation_token=body.confirmation_token or "",
    )
    if _code != 0:
        return JSONResponse(status_code=403, content=_result)

    epoch_id = _epoch_id()
    if not epoch_id:
        raise HTTPException(status_code=400, detail="epoch_id not set in config.")

    script = Path(__file__).resolve().parents[2] / "scripts" / "identity" / "build_face_clusters.py"
    if not script.is_file():
        raise HTTPException(status_code=500, detail="build_face_clusters.py not found.")

    try:
        ledger, job = _prepare_identity_process_job(
            operation=_REBUILD_FACE_CLUSTERS_OPERATION,
            scope={"epoch_id": epoch_id, "eps": body.eps},
            confirmation_token=body.confirmation_token or "",
            authorization_result=_result,
            authority=_authority,
        )
    except ValueError:
        log.error("Persisted identity process state is invalid")
        raise HTTPException(status_code=500, detail="identity_process_state_invalid")

    identity_data_path = _identity_data_path()
    target_paths = (
        identity_data_path / "face_clusters.json",
        identity_data_path / "reports" / "face_cluster_sheet.html",
    )
    targets_before = _observe_identity_targets(target_paths)
    command = [
        sys.executable,
        str(script),
        "--epoch-id",
        epoch_id,
        "--eps",
        str(body.eps),
        "--data-path",
        str(identity_data_path),
        "--start-gate-job-id",
        str(job["job_id"]),
    ]
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            close_fds=True,
        )
    except Exception:
        log.error("Face cluster rebuild process failed before child registration")
        _terminalize_face_rebuild_failure(
            ledger,
            job,
            _authority,
            target_paths=target_paths,
            targets_before=targets_before,
            started_at=_start,
            return_code=1,
        )
        raise HTTPException(status_code=500, detail="face_cluster_rebuild_failed")

    try:
        child_state, child_start_token = _probe_process_start_token(process.pid)
    except Exception:
        child_state, child_start_token = "unknown", None
    if child_state != "live" or child_start_token is None:
        confirmed_dead, return_code = _terminate_and_reap_gated_process(process)
        if confirmed_dead:
            _terminalize_face_rebuild_failure(
                ledger,
                job,
                _authority,
                target_paths=target_paths,
                targets_before=targets_before,
                started_at=_start,
                return_code=return_code,
            )
        else:
            log.error("Face cluster rebuild child death could not be confirmed")
        raise HTTPException(status_code=500, detail="face_cluster_rebuild_failed")

    try:
        job = ledger.compare_and_update(
            str(job["job_id"]),
            expected_state="running",
            expected_owner_instance=str(job["owner_instance"]),
            child_pid=int(process.pid),
            child_start_token=child_start_token,
        )
    except Exception:
        confirmed_dead, _return_code = _terminate_and_reap_gated_process(process)
        if not confirmed_dead:
            log.error("Face cluster rebuild child death could not be confirmed")
        raise HTTPException(status_code=500, detail="face_cluster_rebuild_failed")

    try:
        if process.stdin is None:
            raise OSError("gated child stdin unavailable")
        process.stdin.write(f"START {job['job_id']}\n")
        process.stdin.flush()
        _close_gated_process_stdin(process)
    except Exception:
        confirmed_dead, return_code = _terminate_and_reap_gated_process(process)
        if confirmed_dead:
            _terminalize_face_rebuild_failure(
                ledger,
                job,
                _authority,
                target_paths=target_paths,
                targets_before=targets_before,
                started_at=_start,
                return_code=return_code,
            )
        else:
            log.error("Face cluster rebuild child death could not be confirmed")
        raise HTTPException(status_code=500, detail="face_cluster_rebuild_failed")

    try:
        process.communicate(timeout=120)
    except Exception:
        confirmed_dead, return_code = _terminate_and_reap_gated_process(process)
        if confirmed_dead:
            _terminalize_face_rebuild_failure(
                ledger,
                job,
                _authority,
                target_paths=target_paths,
                targets_before=targets_before,
                started_at=_start,
                return_code=return_code,
            )
        else:
            log.error("Face cluster rebuild child death could not be confirmed")
        raise HTTPException(status_code=500, detail="face_cluster_rebuild_failed")

    return_code = process.returncode
    if not isinstance(return_code, int) or return_code != 0:
        log.error("Face cluster rebuild process returned a nonzero status")
        _terminalize_face_rebuild_failure(
            ledger,
            job,
            _authority,
            target_paths=target_paths,
            targets_before=targets_before,
            started_at=_start,
            return_code=int(return_code) if isinstance(return_code, int) else 1,
        )
        raise HTTPException(status_code=500, detail="face_cluster_rebuild_failed")

    targets_after = _observe_identity_targets(target_paths)
    try:
        data = _validate_face_cluster_rebuild_result(
            targets_after[0],
            epoch_id=epoch_id,
            eps=body.eps,
        )
    except ValueError:
        log.error("Face cluster rebuild result is invalid")
        _terminalize_identity_process(
            ledger,
            job,
            _authority,
            terminal_state="failed",
            outcome_code="face_cluster_rebuild_failed",
            outcome_message="Face cluster rebuild failed",
            audit_status="failed",
            return_code=1,
            duration_ms=int((time.time() - _start) * 1000),
            mutated=_targets_were_mutated(targets_before, targets_after),
        )
        raise HTTPException(status_code=500, detail="face_cluster_rebuild_failed")
    job = _terminalize_identity_process(
        ledger,
        job,
        _authority,
        terminal_state="succeeded",
        outcome_code="face_clusters_rebuilt",
        outcome_message="Face clusters rebuilt successfully",
        audit_status="succeeded",
        return_code=0,
        duration_ms=int((time.time() - _start) * 1000),
        mutated=_targets_were_mutated(targets_before, targets_after),
    )
    payload = dict(data)
    payload["job"] = _public_identity_process_job(job)
    return payload


class FaceClusterLabelRequest(BaseModel):
    cluster_id: str
    label: str
    operator_note: str = ""
    confirmation_token: Optional[str] = Field(None)


@router.post("/face-clusters/label")
async def label_face_cluster(req: FaceClusterLabelRequest) -> dict:
    """Writes a label onto a cluster in face_clusters.json."""
    import time
    _start = time.time()
    _authority = MiniAgentClient(profile="safe")
    _tool_args = {"cluster_id": req.cluster_id, "label": req.label}
    _result, _code = _authority.authorize_action(
        prompt="Confirm identity mutation: label face cluster",
        mode="ops",
        tool_name="identity.label_face_cluster",
        tool_args=_tool_args,
        confirm=bool(req.confirmation_token),
        confirmation_token=req.confirmation_token or "",
    )
    if _code != 0:
        return JSONResponse(status_code=403, content=_result)

    path = _data_path() / "face_clusters.json"
    data = _load_json_file(path)
    if not data or not isinstance(data.get("clusters"), list):
        raise HTTPException(status_code=404, detail="face_clusters.json not found or empty.")

    updated = False
    for cluster in data["clusters"]:
        if cluster["cluster_id"] == req.cluster_id:
            cluster["label"] = req.label
            cluster["operator_note"] = req.operator_note
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail=f"Cluster '{req.cluster_id}' not found.")

    _save_json_file(path, data)
    log.info("Face cluster %s labeled → %s", req.cluster_id, req.label)
    _request_id = _result.get("request_id") if isinstance(_result, dict) else ""
    _authority.record_external_execution_outcome(
        operation="identity.label_face_cluster",
        arguments=_tool_args,
        request_id=_request_id or "",
        mode="ops",
        status="succeeded",
        return_code=0,
        duration_ms=int((time.time() - _start) * 1000),
        side_effect_report={"mutated": True, "targets": [str(path)]},
    )
    return {"ok": True, "cluster_id": req.cluster_id, "label": req.label}


# ── Speaker Clusters ─────────────────────────────────────────────────────────

@router.get("/speaker-clusters")
async def get_speaker_clusters() -> dict:
    path = _identity_data_path() / "speaker_clusters.json"
    data = _load_json_file(path)
    authority = _identity_epoch_authority()
    if data is None:
        return {
            "clusters": [],
            "message": "speaker_clusters.json not found. Run Phase 2.",
            "epoch_authority": authority,
        }
    payload = dict(data)
    payload["epoch_authority"] = authority
    return payload


class SpeakerConfirmRequest(BaseModel):
    cluster_id: str
    confirmed: bool
    identity_label: Optional[str] = None
    confirmation_token: Optional[str] = Field(None)


@router.post("/speaker-clusters/confirm")
async def confirm_speaker_cluster(req: SpeakerConfirmRequest) -> dict:
    """Persists a speaker cluster confirmation + optional identity label."""
    import time
    _start = time.time()
    _authority = MiniAgentClient(profile="safe")
    _tool_args = {"cluster_id": req.cluster_id, "confirmed": req.confirmed}
    _result, _code = _authority.authorize_action(
        prompt="Confirm identity mutation: confirm speaker cluster",
        mode="ops",
        tool_name="identity.confirm_speaker_cluster",
        tool_args=_tool_args,
        confirm=bool(req.confirmation_token),
        confirmation_token=req.confirmation_token or "",
    )
    if _code != 0:
        return JSONResponse(status_code=403, content=_result)

    path = _data_path() / "speaker_clusters.json"
    data = _load_json_file(path)
    if not data or not isinstance(data.get("clusters"), list):
        raise HTTPException(status_code=404, detail="speaker_clusters.json not found.")

    updated = False
    for cluster in data["clusters"]:
        if cluster["cluster_id"] == req.cluster_id:
            cluster["confirmed"] = req.confirmed
            if req.identity_label is not None:
                cluster["identity_label"] = req.identity_label
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail=f"Speaker cluster '{req.cluster_id}' not found.")

    _save_json_file(path, data)
    _request_id = _result.get("request_id") if isinstance(_result, dict) else ""
    _authority.record_external_execution_outcome(
        operation="identity.confirm_speaker_cluster",
        arguments=_tool_args,
        request_id=_request_id or "",
        mode="ops",
        status="succeeded",
        return_code=0,
        duration_ms=int((time.time() - _start) * 1000),
        side_effect_report={"mutated": True, "targets": [str(path)]},
    )
    return {"ok": True, "cluster_id": req.cluster_id, "confirmed": req.confirmed}


# ── Name Mentions ─────────────────────────────────────────────────────────────

@router.get("/name-mentions")
async def get_name_mentions() -> dict:
    path = _identity_data_path() / "name_mentions.json"
    data = _load_json_file(path)
    authority = _identity_epoch_authority()
    if data is None:
        return {
            "mentions": {},
            "message": "name_mentions.json not found. Run Phase 3.",
            "epoch_authority": authority,
        }
    payload = dict(data)
    payload["epoch_authority"] = authority
    return payload


# ── Roster ────────────────────────────────────────────────────────────────────

@router.get("/roster")
async def get_roster() -> dict:
    """Reads family_roster.yaml and returns as JSON."""
    roster_path = _identity_data_path() / "family_roster.yaml"
    authority = _identity_epoch_authority()
    if not roster_path.exists():
        return {
            "identities": [],
            "message": "family_roster.yaml not found. Use the UI to create it.",
            "epoch_authority": authority,
        }
    try:
        import yaml
        with open(roster_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {
            "identities": data.get("identities", []),
            "epoch_authority": authority,
        }
    except ImportError:
        raise HTTPException(status_code=500, detail="PyYAML not installed in the active environment.")


@router.get("/evidence-pack")
async def get_identity_evidence_pack(
    subjects: str = Query(..., min_length=1, max_length=500),
) -> dict:
    """Return bounded curated identity labels and explicit pairwise claims only."""
    roster_path = _identity_data_path() / "family_roster.yaml"
    authority = _identity_epoch_authority()
    if not roster_path.exists():
        return {
            **build_identity_evidence_pack([], []),
            "epoch_authority": authority,
            "message": "family_roster.yaml not found.",
        }
    try:
        import yaml
        with open(roster_path, encoding="utf-8") as handle:
            roster = yaml.safe_load(handle) or {}
    except ImportError:
        raise HTTPException(status_code=500, detail="PyYAML not installed in the active environment.")
    requested = [item.strip() for item in subjects.split(",") if item.strip()]
    return {
        **build_identity_evidence_pack(roster.get("identities") or [], requested),
        "epoch_authority": authority,
    }


@router.get("/scene-evidence")
async def get_identity_scene_evidence(
    subjects: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """Return bounded promoted Person-to-scene evidence without running retrieval."""
    roster_path = _identity_data_path() / "family_roster.yaml"
    authority = _identity_epoch_authority()
    if not roster_path.exists():
        return {
            "scene_refs": [],
            "source": "promoted_knowledge_graph",
            "epoch_authority": authority,
            "message": "family_roster.yaml not found.",
        }
    try:
        import yaml
        with open(roster_path, encoding="utf-8") as handle:
            roster = yaml.safe_load(handle) or {}
    except ImportError:
        raise HTTPException(status_code=500, detail="PyYAML not installed in the active environment.")
    requested = [item.strip() for item in subjects.split(",") if item.strip()]
    pack = build_identity_evidence_pack(roster.get("identities") or [], requested)
    identity_cfg = _CFG.get("identity_search") or {}
    paths_cfg = _CFG.get("paths") or {}
    kg_path = Path(identity_cfg.get("kg_db_path") or paths_cfg.get("knowledge_graph_db") or "")
    return {
        **load_identity_scene_evidence(pack["identities"], kg_path, limit=limit),
        "matched_identities": pack["identities"],
        "relationship_claim_status": pack["claim_status"],
        "epoch_authority": authority,
        "limitations": [
            "Scene references prove only promoted appearance or mention evidence.",
            "They do not establish a personal relationship or provide scene narration.",
        ],
    }


class RosterSaveRequest(BaseModel):
    identity: dict
    confirmation_token: Optional[str] = Field(None)


@router.post("/roster/save")
async def save_roster_identity(req: RosterSaveRequest) -> dict:
    """
    Upserts a single identity into family_roster.yaml by id.
    Creates the file if it doesn't exist.
    """
    import time
    _start = time.time()
    try:
        import yaml
    except ImportError:
        raise HTTPException(status_code=500, detail="PyYAML not installed.")

    _authority = MiniAgentClient(profile="safe")
    _identity_id = req.identity.get("id", "")
    _tool_args = {"identity_id": str(_identity_id)}
    _result, _code = _authority.authorize_action(
        prompt="Confirm identity mutation: save roster identity",
        mode="ops",
        tool_name="identity.save_roster",
        tool_args=_tool_args,
        confirm=bool(req.confirmation_token),
        confirmation_token=req.confirmation_token or "",
    )
    if _code != 0:
        return JSONResponse(status_code=403, content=_result)

    roster_path = _data_path() / "family_roster.yaml"
    if roster_path.exists():
        with open(roster_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    identities: list = data.get("identities") or []
    identity_id = req.identity.get("id", "")
    requested_clusters = {
        str(cluster_id)
        for cluster_id in (req.identity.get("face_cluster_ids") or [])
        if cluster_id
    }
    conflicting_owners: dict[str, str] = {}
    for existing in identities:
        existing_id = str(existing.get("id") or "")
        if existing_id == str(identity_id):
            continue
        for cluster_id in existing.get("face_cluster_ids") or []:
            cluster_key = str(cluster_id)
            if cluster_key in requested_clusters:
                conflicting_owners[cluster_key] = existing_id
    if conflicting_owners:
        ordered_clusters = sorted(conflicting_owners)
        raise HTTPException(
            status_code=409,
            detail={
                "code": "face_cluster_already_owned",
                "cluster_ids": ordered_clusters,
                "owner_ids": sorted(
                    {conflicting_owners[cluster] for cluster in ordered_clusters}
                ),
            },
        )
    found = False
    for i, existing in enumerate(identities):
        if existing.get("id") == identity_id:
            identities[i] = req.identity
            found = True
            break
    if not found:
        identities.append(req.identity)

    data["identities"] = identities
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=roster_path.parent, suffix=".tmp", delete=False, encoding="utf-8") as tmp:
            tmp_path = tmp.name
            yaml.dump(data, tmp, default_flow_style=False, allow_unicode=True, sort_keys=False)
        os.replace(tmp_path, roster_path)
    except Exception as e:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        log.error("save_roster failed: %s", e)
        raise HTTPException(status_code=500, detail="roster_save_failed")

    _request_id = _result.get("request_id") if isinstance(_result, dict) else ""
    _authority.record_external_execution_outcome(
        operation="identity.save_roster",
        arguments=_tool_args,
        request_id=_request_id or "",
        mode="ops",
        status="succeeded",
        return_code=0,
        duration_ms=int((time.time() - _start) * 1000),
        side_effect_report={"mutated": True, "targets": [str(roster_path)]},
    )
    return {"ok": True, "id": identity_id}


class ValidateRosterRequest(BaseModel):
    confirmation_token: Optional[str] = Field(None)


@router.post("/roster/validate")
async def validate_roster(body: ValidateRosterRequest) -> dict:
    """Runs validate_roster.py and returns structured results.
    Requires MiniAgent confirmation before subprocess execution.
    """
    _start = time.time()
    _tool_args: dict = {}
    _authority = MiniAgentClient(profile="safe")
    _result, _code = _authority.authorize_action(
        prompt="Confirm identity process execution: validate roster",
        mode="ops",
        tool_name="identity.validate_roster",
        tool_args=_tool_args,
        confirm=bool(body.confirmation_token),
        confirmation_token=body.confirmation_token or "",
    )
    if _code != 0:
        return JSONResponse(status_code=403, content=_result)

    script = Path(__file__).resolve().parents[2] / "scripts" / "identity" / "validate_roster.py"
    if not script.is_file():
        raise HTTPException(status_code=500, detail="validate_roster.py not found.")

    try:
        ledger, job = _prepare_identity_process_job(
            operation=_VALIDATE_ROSTER_OPERATION,
            scope={},
            confirmation_token=body.confirmation_token or "",
            authorization_result=_result,
            authority=_authority,
        )
    except ValueError:
        log.error("Persisted identity process state is invalid")
        raise HTTPException(status_code=500, detail="identity_process_state_invalid")
    data_path = str(_data_path())
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--data-path", data_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        log.error("Roster validation process failed before returning a result")
        job = _terminalize_identity_process(
            ledger,
            job,
            _authority,
            terminal_state="failed",
            outcome_code="roster_validation_failed",
            outcome_message="Roster validation failed",
            audit_status="failed",
            return_code=1,
            duration_ms=int((time.time() - _start) * 1000),
            mutated=False,
        )
        raise HTTPException(status_code=500, detail="roster_validation_failed")

    passed = []
    warnings = []
    errors = []
    all_output = (result.stdout or "") + (result.stderr or "")
    for line in all_output.splitlines():
        if " ✓ " in line:
            passed.append("validation_check_passed")
        elif " ⚠ " in line:
            warnings.append("validation_check_warning")
        elif " ✗ " in line:
            match = re.search(
                r"Face cluster '([A-Za-z0-9_.:-]+)' is assigned to multiple identities",
                line,
            )
            if match:
                cluster_id = match.group(1)
                errors.append(
                    {
                        "code": "face_cluster_multiple_owners",
                        "cluster_id": cluster_id,
                        "message": (
                            f"Face cluster {cluster_id} is assigned to multiple identities."
                        ),
                    }
                )
            else:
                errors.append("validation_check_failed")
        elif "[ERROR]" in line and "error" in line.lower():
            errors.append("validation_error")

    log.debug(
        "validate_roster result returncode=%d passed=%d warnings=%d errors=%d",
        result.returncode,
        len(passed),
        len(warnings),
        len(errors),
    )

    succeeded = result.returncode == 0
    job = _terminalize_identity_process(
        ledger,
        job,
        _authority,
        terminal_state="succeeded" if succeeded else "failed",
        outcome_code=(
            "roster_validation_succeeded"
            if succeeded
            else "roster_validation_failed"
        ),
        outcome_message=(
            "Roster validation succeeded" if succeeded else "Roster validation failed"
        ),
        audit_status="succeeded" if succeeded else "failed",
        return_code=0 if succeeded else int(result.returncode),
        duration_ms=int((time.time() - _start) * 1000),
        mutated=False,
    )
    return {
        "ok": succeeded,
        "passed": passed,
        "warnings": warnings,
        "errors": errors,
        "job": _public_identity_process_job(job),
    }


class RosterExportRequest(BaseModel):
    identities: list
    confirmation_token: Optional[str] = Field(None)


@router.post("/roster/export")
async def export_roster(req: RosterExportRequest) -> dict:
    """Writes the full roster as family_roster.yaml to the data path."""
    import time
    _start = time.time()
    try:
        import yaml
    except ImportError:
        raise HTTPException(status_code=500, detail="PyYAML not installed.")

    _authority = MiniAgentClient(profile="safe")
    _tool_args = {"identity_count": len(req.identities)}
    _result, _code = _authority.authorize_action(
        prompt="Confirm identity mutation: export roster",
        mode="ops",
        tool_name="identity.export_roster",
        tool_args=_tool_args,
        confirm=bool(req.confirmation_token),
        confirmation_token=req.confirmation_token or "",
    )
    if _code != 0:
        return JSONResponse(status_code=403, content=_result)

    roster_path = _data_path() / "family_roster.yaml"
    data = {"identities": req.identities}
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=roster_path.parent, suffix=".tmp", delete=False, encoding="utf-8") as tmp:
            tmp_path = tmp.name
            yaml.dump(data, tmp, default_flow_style=False, allow_unicode=True, sort_keys=False)
        os.replace(tmp_path, roster_path)
    except Exception as e:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        log.error("export_roster failed: %s", e)
        raise HTTPException(status_code=500, detail="roster_export_failed")

    log.info("Roster exported: %d identities", len(req.identities))
    _request_id = _result.get("request_id") if isinstance(_result, dict) else ""
    _authority.record_external_execution_outcome(
        operation="identity.export_roster",
        arguments=_tool_args,
        request_id=_request_id or "",
        mode="ops",
        status="succeeded",
        return_code=0,
        duration_ms=int((time.time() - _start) * 1000),
        side_effect_report={"mutated": True, "targets": ["family_roster.yaml"]},
    )
    return {"ok": True, "count": len(req.identities)}
