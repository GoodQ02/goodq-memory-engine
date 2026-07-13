from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filelock import FileLock


SCHEMA_VERSION = "goodq.temporal-summary-result.v1"
_JOB_ID_RE = re.compile(r"^job_[0-9a-f]{32}$")
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_SAFE_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_PATH_DETAIL_RE = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|file:/{2,3}|https?://|"
    r"/(?:mnt/[a-z]|home|users|var|tmp|etc)(?:/|$)|~[\\/])",
    re.IGNORECASE,
)
_RECORD_KEYS = {
    "schema",
    "job_id",
    "epoch_id",
    "request_sha256",
    "execution_policy_sha256",
    "started_at_utc",
    "completed_at_utc",
    "terminal_state",
    "result",
    "error_code",
    "model_evidence",
    "result_sha256",
}
_RESULT_KEYS = {
    "summary",
    "segments",
    "source_scene_ids",
    "source_count",
    "truncated",
    "warning_codes",
}
_SEGMENT_KEYS = {
    "scene_index",
    "scene_id",
    "text",
    "start_time",
    "end_time",
}
_MODEL_EVIDENCE_KEYS = {"model_id", "provider"}


class TemporalSummaryResultError(RuntimeError):
    """Base error for temporal-summary result authority failures."""


class TemporalSummaryResultConflict(TemporalSummaryResultError):
    """An immutable exact-job result conflicts with requested result truth."""


class TemporalSummaryResultRecoveryError(TemporalSummaryResultError):
    """A failed first-write replacement requires manual recovery."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_clone(value: Any, *, label: str) -> Any:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must contain only canonical JSON values") from exc
    return json.loads(encoded)


def _validate_job_id(job_id: Any) -> str:
    if not isinstance(job_id, str) or _JOB_ID_RE.fullmatch(job_id) is None:
        raise ValueError("Invalid temporal summary result job ID")
    return job_id


def _validate_identifier(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or _SAFE_IDENTIFIER_RE.fullmatch(value) is None:
        raise ValueError(f"Invalid temporal summary result {label}")
    return value


def _validate_digest(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"Invalid temporal summary result {label}")
    return value


def _validate_timestamp(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Invalid temporal summary result {label}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid temporal summary result {label}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Invalid temporal summary result {label}")
    return value


def _parsed_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _validate_code(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or _CODE_RE.fullmatch(value) is None:
        raise ValueError(f"Invalid temporal summary result {label}")
    return value


def _validate_text(value: Any, *, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"Invalid temporal summary result {label}")
    if _PATH_DETAIL_RE.search(value):
        raise ValueError(f"Temporal summary result {label} contains path detail")
    return value


def _validate_optional_time(value: Any, *, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Invalid temporal summary result segment {label}")
    converted = float(value)
    if not math.isfinite(converted) or converted < 0:
        raise ValueError(f"Invalid temporal summary result segment {label}")
    return converted


def _validate_success_result(result: Any) -> dict[str, Any]:
    normalized = _canonical_clone(result, label="Temporal summary result")
    if not isinstance(normalized, dict) or set(normalized) != _RESULT_KEYS:
        raise ValueError("Temporal summary success result schema is invalid")

    _validate_text(normalized["summary"], label="summary", maximum=200_000)
    source_ids = normalized["source_scene_ids"]
    if (
        not isinstance(source_ids, list)
        or len(source_ids) > 100
        or any(
            not isinstance(scene_id, str)
            or _SAFE_IDENTIFIER_RE.fullmatch(scene_id) is None
            for scene_id in source_ids
        )
        or len(source_ids) != len(set(source_ids))
    ):
        raise ValueError("Temporal summary source scene IDs are invalid")
    source_count = normalized["source_count"]
    if (
        isinstance(source_count, bool)
        or not isinstance(source_count, int)
        or source_count != len(source_ids)
    ):
        raise ValueError("Temporal summary source count is invalid")
    if not isinstance(normalized["truncated"], bool):
        raise ValueError("Temporal summary truncated flag is invalid")

    warning_codes = normalized["warning_codes"]
    if (
        not isinstance(warning_codes, list)
        or len(warning_codes) > 32
        or any(not isinstance(code, str) or _CODE_RE.fullmatch(code) is None for code in warning_codes)
        or len(warning_codes) != len(set(warning_codes))
    ):
        raise ValueError("Temporal summary warning codes are invalid")
    if source_count == 0:
        if warning_codes != ["no_matching_scenes"]:
            raise ValueError("Temporal summary success has no grounding evidence")
    elif "no_matching_scenes" in warning_codes:
        raise ValueError("Temporal summary no-match code conflicts with grounding")

    segments = normalized["segments"]
    if not isinstance(segments, list) or len(segments) > 20:
        raise ValueError("Temporal summary segments are invalid")
    seen_indexes: set[int] = set()
    for segment in segments:
        if not isinstance(segment, dict) or set(segment) != _SEGMENT_KEYS:
            raise ValueError("Temporal summary segment schema is invalid")
        scene_index = segment["scene_index"]
        if (
            isinstance(scene_index, bool)
            or not isinstance(scene_index, int)
            or scene_index < 1
            or scene_index > source_count
            or scene_index in seen_indexes
        ):
            raise ValueError("Temporal summary segment scene index is invalid")
        seen_indexes.add(scene_index)
        scene_id = _validate_identifier(segment["scene_id"], label="segment scene ID")
        if scene_id != source_ids[scene_index - 1]:
            raise ValueError("Temporal summary segment scene ID violates source order")
        _validate_text(segment["text"], label="segment text", maximum=50_000)
        start_time = _validate_optional_time(segment["start_time"], label="start time")
        end_time = _validate_optional_time(segment["end_time"], label="end time")
        if start_time is not None and end_time is not None and end_time < start_time:
            raise ValueError("Temporal summary segment time range is invalid")
    return normalized


def _validate_model_evidence(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    normalized = _canonical_clone(value, label="Temporal summary model evidence")
    if not isinstance(normalized, dict) or set(normalized) != _MODEL_EVIDENCE_KEYS:
        raise ValueError("Temporal summary model evidence schema is invalid")
    model_id = normalized["model_id"]
    if not isinstance(model_id, str) or _SAFE_MODEL_ID_RE.fullmatch(model_id) is None:
        raise ValueError("Temporal summary model identifier is invalid")
    if normalized["provider"] not in {"ollama", "vllm"}:
        raise ValueError("Temporal summary model provider is invalid")
    return normalized


def result_record_sha256(record: dict[str, Any]) -> str:
    if not isinstance(record, dict):
        raise ValueError("Temporal summary result record must be an object")
    digest_payload = {key: value for key, value in record.items() if key != "result_sha256"}
    encoded = json.dumps(
        digest_payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_record(record: Any) -> dict[str, Any]:
    normalized = _canonical_clone(record, label="Temporal summary result record")
    if not isinstance(normalized, dict) or set(normalized) != _RECORD_KEYS:
        raise ValueError("Temporal summary result record schema is invalid")
    if normalized["schema"] != SCHEMA_VERSION:
        raise ValueError("Temporal summary result schema version is invalid")
    _validate_job_id(normalized["job_id"])
    _validate_identifier(normalized["epoch_id"], label="epoch ID")
    _validate_digest(normalized["request_sha256"], label="request digest")
    _validate_digest(
        normalized["execution_policy_sha256"], label="execution policy digest"
    )
    started = _validate_timestamp(normalized["started_at_utc"], label="start timestamp")
    completed = _validate_timestamp(
        normalized["completed_at_utc"], label="completion timestamp"
    )
    if _parsed_timestamp(completed) < _parsed_timestamp(started):
        raise ValueError("Temporal summary result timestamp order is invalid")
    model_evidence = _validate_model_evidence(normalized["model_evidence"])

    terminal_state = normalized["terminal_state"]
    if terminal_state == "succeeded":
        result = _validate_success_result(normalized["result"])
        if normalized["error_code"] is not None:
            raise ValueError("Successful temporal summary result has an error code")
        if result["source_count"] == 0 and model_evidence is not None:
            raise ValueError("No-match temporal summary has unexpected model evidence")
    elif terminal_state == "failed":
        if normalized["result"] is not None:
            raise ValueError("Failed temporal summary result has a narrative payload")
        _validate_code(normalized["error_code"], label="failure code")
        result = None
    else:
        raise ValueError("Temporal summary terminal result state is invalid")

    expected_digest = result_record_sha256(normalized)
    persisted_digest = _validate_digest(
        normalized["result_sha256"], label="result digest"
    )
    if not hmac.compare_digest(expected_digest, persisted_digest):
        raise ValueError("Temporal summary result digest is invalid")
    normalized["result"] = result
    normalized["model_evidence"] = model_evidence
    return normalized


def _fsync_directory_if_supported(directory: Path) -> bool:
    if os.name == "nt":
        return False
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        descriptor = os.open(directory, flags)
        os.fsync(descriptor)
        return True
    except OSError:
        return False
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                return False


class TemporalSummaryResultStore:
    def __init__(self, root_dir: Path | str):
        self.root_dir = Path(root_dir)

    def record_path(self, job_id: str) -> Path:
        return self.root_dir / f"{_validate_job_id(job_id)}.json"

    def _load_path(
        self,
        path: Path,
        *,
        enforce_authoritative_name: bool = True,
    ) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Temporal summary result record is malformed") from exc
        try:
            record = _validate_record(raw)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
        if enforce_authoritative_name and path.name != f"{record['job_id']}.json":
            raise RuntimeError("Temporal summary result file and job ID are inconsistent")
        return record

    def load(self, job_id: str) -> dict[str, Any] | None:
        path = self.record_path(job_id)
        if not path.is_file():
            return None
        return self._load_path(path)

    def load_exact(
        self,
        *,
        job_id: str,
        epoch_id: str,
        request_sha256: str,
        execution_policy_sha256: str,
    ) -> dict[str, Any] | None:
        expected = {
            "job_id": _validate_job_id(job_id),
            "epoch_id": _validate_identifier(epoch_id, label="epoch ID"),
            "request_sha256": _validate_digest(
                request_sha256, label="request digest"
            ),
            "execution_policy_sha256": _validate_digest(
                execution_policy_sha256, label="execution policy digest"
            ),
        }
        record = self.load(job_id)
        if record is None:
            return None
        if any(record[key] != value for key, value in expected.items()):
            raise TemporalSummaryResultConflict(
                "Temporal summary result binding does not match exact job scope"
            )
        return record

    def write_success(
        self,
        *,
        job_id: str,
        epoch_id: str,
        request_sha256: str,
        execution_policy_sha256: str,
        started_at_utc: str,
        result: dict[str, Any],
        model_evidence: dict[str, str] | None,
    ) -> dict[str, Any]:
        return self._write_once(
            self._build_record(
                job_id=job_id,
                epoch_id=epoch_id,
                request_sha256=request_sha256,
                execution_policy_sha256=execution_policy_sha256,
                started_at_utc=started_at_utc,
                terminal_state="succeeded",
                result=result,
                error_code=None,
                model_evidence=model_evidence,
            )
        )

    def write_failure(
        self,
        *,
        job_id: str,
        epoch_id: str,
        request_sha256: str,
        execution_policy_sha256: str,
        started_at_utc: str,
        error_code: str,
        model_evidence: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._write_once(
            self._build_record(
                job_id=job_id,
                epoch_id=epoch_id,
                request_sha256=request_sha256,
                execution_policy_sha256=execution_policy_sha256,
                started_at_utc=started_at_utc,
                terminal_state="failed",
                result=None,
                error_code=error_code,
                model_evidence=model_evidence,
            )
        )

    def _build_record(
        self,
        *,
        job_id: str,
        epoch_id: str,
        request_sha256: str,
        execution_policy_sha256: str,
        started_at_utc: str,
        terminal_state: str,
        result: dict[str, Any] | None,
        error_code: str | None,
        model_evidence: dict[str, str] | None,
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "schema": SCHEMA_VERSION,
            "job_id": _validate_job_id(job_id),
            "epoch_id": _validate_identifier(epoch_id, label="epoch ID"),
            "request_sha256": _validate_digest(
                request_sha256, label="request digest"
            ),
            "execution_policy_sha256": _validate_digest(
                execution_policy_sha256, label="execution policy digest"
            ),
            "started_at_utc": _validate_timestamp(
                started_at_utc, label="start timestamp"
            ),
            "completed_at_utc": _utc_now_iso(),
            "terminal_state": terminal_state,
            "result": result,
            "error_code": error_code,
            "model_evidence": model_evidence,
            "result_sha256": "0" * 64,
        }
        record["result_sha256"] = result_record_sha256(record)
        return _validate_record(record)

    @staticmethod
    def _semantic_identity(record: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in record.items()
            if key not in {"completed_at_utc", "result_sha256"}
        }

    def _write_once(self, record: dict[str, Any]) -> dict[str, Any]:
        validated = _validate_record(record)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        lock = FileLock(str(self.root_dir / ".temporal-summary-results.lock"))
        path = self.record_path(validated["job_id"])
        temp_path = path.with_name(
            f"{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
        )
        replacement_completed = False
        with lock:
            if path.is_file():
                existing = self._load_path(path)
                if self._semantic_identity(existing) == self._semantic_identity(validated):
                    return existing
                raise TemporalSummaryResultConflict(
                    "Temporal summary result is immutable for this job"
                )
            try:
                with temp_path.open("x", encoding="utf-8") as handle:
                    json.dump(validated, handle, ensure_ascii=False, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                if self._load_path(
                    temp_path,
                    enforce_authoritative_name=False,
                ) != validated:
                    raise RuntimeError("Temporal summary result candidate mismatch")
                os.replace(temp_path, path)
                replacement_completed = True
                _fsync_directory_if_supported(self.root_dir)
                if self._load_path(path) != validated:
                    raise RuntimeError("Temporal summary result inspection mismatch")
                return validated
            except Exception as exc:
                if replacement_completed:
                    try:
                        path.unlink(missing_ok=True)
                        _fsync_directory_if_supported(self.root_dir)
                        if path.exists():
                            raise RuntimeError(
                                "Temporal summary result first write could not be removed"
                            )
                    except Exception as cleanup_exc:
                        raise TemporalSummaryResultRecoveryError(
                            "Temporal summary result persistence failed; manual recovery required"
                        ) from cleanup_exc
                if isinstance(exc, TemporalSummaryResultError):
                    raise
                raise RuntimeError("Failed to persist temporal summary result") from exc
            finally:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
