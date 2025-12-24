from __future__ import annotations

"""
Passive Health Collector v1 (PHC v1) — pull-based, finite-run, vault-first.

This script:
- Pulls a JSON payload from a local Health Auto Export server (HTTP GET)
- Writes the raw payload *unchanged* to the local vault (PHI-equivalent, vault-only)
- Runs HIN v1 to emit derived CanonicalHealthEvent (CHE) summaries (metadata only)

Non-goals (by design):
- No DB writes (memory.db / KG / conduits)
- No always-on server, no scheduling, no retries/backoff loops
- No health semantics, no trends, no alerts, no UI

Example:
  $env:GOODQ_HEALTH_EXPORT_URL = "http://192.168.0.106:9000/export"
  $env:GOODQ_HEALTH_SOURCE_ID = "ipad-air-health"
  $env:GOODQ_VAULT_ROOT = "L:\\_DATA\\GoodQ_Vault"
  python scripts/health/pull_health_export.py

Dry run (fetch + fingerprint only; no vault write; no CHE emission):
  python scripts/health/pull_health_export.py --dry-run
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request


# Make repo-root imports work when invoked as `python scripts/health/pull_health_export.py`.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from steps.health_auto_export.normalizer import normalize_health_payload  # noqa: E402
from steps.health_auto_export.normalizer import _fingerprint_schema as _hin_fingerprint_schema  # noqa: E402


_ENV_URL = "GOODQ_HEALTH_EXPORT_URL"
_ENV_SOURCE_ID = "GOODQ_HEALTH_SOURCE_ID"
_ENV_VAULT_ROOT = "GOODQ_VAULT_ROOT"
_ENV_AUTH_HEADER = "GOODQ_HEALTH_AUTH_HEADER"
_ENV_AUTH_TOKEN = "GOODQ_HEALTH_AUTH_TOKEN"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _log(event: str, **fields: object) -> None:
    record = {"event": event, **fields}
    print(json.dumps(record, ensure_ascii=False, sort_keys=True))


def _build_headers() -> dict[str, str]:
    token = os.getenv(_ENV_AUTH_TOKEN) or ""
    if not token.strip():
        return {}

    header_name = (os.getenv(_ENV_AUTH_HEADER) or "").strip()
    if header_name:
        return {header_name: token}
    return {"Authorization": f"Bearer {token}"}


def _http_get_json_bytes(url: str, *, timeout_s: float) -> bytes:
    request = urllib.request.Request(url, headers=_build_headers(), method="GET")
    with urllib.request.urlopen(request, timeout=timeout_s) as resp:  # noqa: S310 (local-only URL by contract)
        return resp.read()


def _vault_rel_path(dt: datetime) -> Path:
    return Path(
        "health",
        "auto_export",
        dt.strftime("%Y"),
        dt.strftime("%m"),
        dt.strftime("%d"),
        dt.strftime("%H%M%S") + ".json",
    )


def _reserve_output_path(vault_root: Path, rel_path: Path) -> Path:
    """
    Choose a deterministic primary path, with a safe collision suffix fallback.
    """
    target = vault_root / rel_path
    if not target.exists():
        return target
    stem = target.stem
    for i in range(1, 1000):
        candidate = target.with_name(f"{stem}_{i:03d}.json")
        if not candidate.exists():
            return candidate
    raise RuntimeError("Could not reserve unique vault filename (too many collisions)")


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    with open(tmp, "xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser(prog="pull_health_export.py", add_help=True)
    parser.add_argument("--dry-run", action="store_true", help="Fetch + fingerprint only; do not write vault or emit CHEs.")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=15.0,
        help="HTTP timeout (no retries).",
    )
    args = parser.parse_args()

    url = (os.getenv(_ENV_URL) or "").strip()
    source_id = (os.getenv(_ENV_SOURCE_ID) or "").strip()
    vault_root = (os.getenv(_ENV_VAULT_ROOT) or "").strip()

    if not url:
        _log("error", reason="missing_env", env=_ENV_URL)
        return 2
    if not source_id:
        _log("error", reason="missing_env", env=_ENV_SOURCE_ID)
        return 2
    if not vault_root and not args.dry_run:
        _log("error", reason="missing_env", env=_ENV_VAULT_ROOT)
        return 2

    started = time.time()
    received_dt = _utc_now()
    received_at_utc = _iso_utc(received_dt)

    _log("health_pull_started", source_id=source_id, received_at_utc=received_at_utc, dry_run=bool(args.dry_run))

    try:
        raw_bytes = _http_get_json_bytes(url, timeout_s=float(args.timeout_seconds))
    except urllib.error.HTTPError as exc:
        _log("health_pull_failed", source_id=source_id, received_at_utc=received_at_utc, error="http_error", status=int(exc.code))
        return 1
    except urllib.error.URLError as exc:
        _log("health_pull_failed", source_id=source_id, received_at_utc=received_at_utc, error="url_error", reason=str(exc.reason))
        return 1
    except Exception as exc:
        _log("health_pull_failed", source_id=source_id, received_at_utc=received_at_utc, error="exception", reason=str(exc))
        return 1

    if not raw_bytes:
        _log("health_pull_failed", source_id=source_id, received_at_utc=received_at_utc, error="empty_payload")
        return 1

    payload_size_bytes = len(raw_bytes)
    payload_sha256 = hashlib.sha256(raw_bytes).hexdigest()

    if args.dry_run:
        try:
            decoded = raw_bytes.decode("utf-8", errors="strict")
            parsed = json.loads(decoded)
        except Exception as exc:
            _log(
                "health_payload_invalid_json",
                source_id=source_id,
                received_at_utc=received_at_utc,
                payload_size_bytes=payload_size_bytes,
                payload_sha256=payload_sha256,
                error=str(exc),
            )
            return 1

        if not isinstance(parsed, dict):
            _log(
                "health_payload_unexpected_shape",
                source_id=source_id,
                received_at_utc=received_at_utc,
                payload_size_bytes=payload_size_bytes,
                payload_sha256=payload_sha256,
                root_type=type(parsed).__name__,
            )
            return 1

        schema_fp = _hin_fingerprint_schema(parsed)
        schema_fp_safe = {
            "fingerprint_version": schema_fp.get("fingerprint_version"),
            "top_level_keys_sha256": schema_fp.get("top_level_keys_sha256"),
            "top_level_key_count": schema_fp.get("top_level_key_count"),
            "shape_signature_sha256": schema_fp.get("shape_signature_sha256"),
            "payload_size_bytes": schema_fp.get("payload_size_bytes"),
        }
        _log(
            "health_pull_dry_run_ok",
            source_id=source_id,
            received_at_utc=received_at_utc,
            payload_size_bytes=payload_size_bytes,
            payload_sha256=payload_sha256,
            schema_fingerprint=schema_fp_safe,
            duration_ms=int((time.time() - started) * 1000),
        )
        return 0

    # Vault write is performed *before* parsing/normalization so parse failures cannot alter the raw artifact.
    vault_root_path = Path(vault_root)
    rel_path = _vault_rel_path(received_dt)
    out_path = _reserve_output_path(vault_root_path, rel_path)
    try:
        _atomic_write_bytes(out_path, raw_bytes)
    except Exception as exc:
        _log("vault_write_failed", source_id=source_id, received_at_utc=received_at_utc, error=str(exc))
        return 1

    try:
        decoded = raw_bytes.decode("utf-8", errors="strict")
        parsed = json.loads(decoded)
    except Exception as exc:
        _log(
            "health_payload_invalid_json",
            source_id=source_id,
            received_at_utc=received_at_utc,
            payload_size_bytes=payload_size_bytes,
            payload_sha256=payload_sha256,
            error=str(exc),
        )
        return 1

    if not isinstance(parsed, dict):
        _log(
            "health_payload_unexpected_shape",
            source_id=source_id,
            received_at_utc=received_at_utc,
            payload_size_bytes=payload_size_bytes,
            payload_sha256=payload_sha256,
            root_type=type(parsed).__name__,
        )
        return 1

    schema_fp_safe = None
    try:
        schema_fp = _hin_fingerprint_schema(parsed)
        schema_fp_safe = {
            "fingerprint_version": schema_fp.get("fingerprint_version"),
            "top_level_keys_sha256": schema_fp.get("top_level_keys_sha256"),
            "top_level_key_count": schema_fp.get("top_level_key_count"),
            "shape_signature_sha256": schema_fp.get("shape_signature_sha256"),
            "payload_size_bytes": schema_fp.get("payload_size_bytes"),
        }
    except Exception:
        schema_fp_safe = None

    try:
        che_events = normalize_health_payload(parsed, source_id=source_id, received_at_utc=received_at_utc)
    except Exception as exc:
        _log("health_normalize_failed", source_id=source_id, received_at_utc=received_at_utc, error=str(exc))
        return 1

    if not che_events:
        _log(
            "health_no_events_emitted",
            source_id=source_id,
            received_at_utc=received_at_utc,
            payload_size_bytes=payload_size_bytes,
            payload_sha256=payload_sha256,
            schema_fingerprint=schema_fp_safe,
            che_count=0,
            duration_ms=int((time.time() - started) * 1000),
        )
        return 0

    # Metadata-only CHE emission (no raw values, no transcript-like content).
    _log(
        "health_normalize_ok",
        source_id=source_id,
        received_at_utc=received_at_utc,
        payload_size_bytes=payload_size_bytes,
        payload_sha256=payload_sha256,
        schema_fingerprint=schema_fp_safe,
        che_count=len(che_events),
    )

    for che in che_events:
        if not isinstance(che, dict):
            continue
        _log(
            "che_derived",
            metric_name=che.get("metric_name"),
            category=che.get("category"),
            time_range=che.get("time_range"),
            data_quality=che.get("data_quality"),
            schema_fingerprint=schema_fp_safe,
        )

    _log(
        "health_pull_completed",
        source_id=source_id,
        received_at_utc=received_at_utc,
        payload_size_bytes=payload_size_bytes,
        payload_sha256=payload_sha256,
        che_count=len(che_events),
        duration_ms=int((time.time() - started) * 1000),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
