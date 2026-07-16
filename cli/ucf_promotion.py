"""Portable, human-gated UCF promotion command.

The three subcommands are intentionally separate processes:

1. ``inspect`` reads the configured epoch ledger without mutation.
2. ``approve`` requests a scope-bound confirmation token.
3. ``execute`` consumes a separately supplied token for that exact scope.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from agents.mini_agent_client import MiniAgentClient
from steps.common.config_loader import load_configs


ClientFactory = Callable[..., MiniAgentClient]


class PromotionCommandError(RuntimeError):
    def __init__(
        self,
        message: str,
        exit_code: int = 2,
        code: str = "promotion_command_error",
        result: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.exit_code = exit_code
        self.code = code
        self.result = result


def _safe_envelope_error_code(envelope: Dict[str, Any]) -> str:
    """Return one bounded machine-readable MiniAgent error code."""
    errors = envelope.get("errors")
    if not isinstance(errors, list) or not errors or not isinstance(errors[0], dict):
        return "promotion_execution_failed"
    code = errors[0].get("code")
    if (
        isinstance(code, str)
        and 1 <= len(code) <= 64
        and code.isascii()
        and all(character.isalnum() or character in {"_", "-"} for character in code)
    ):
        return code
    return "promotion_execution_failed"


def _validate_identifier(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PromotionCommandError(f"{name} must be a non-empty string")
    normalized = value.strip()
    if normalized in {".", ".."} or Path(normalized).name != normalized:
        raise PromotionCommandError(f"{name} must be a single path-safe identifier")
    return normalized


def resolve_ledger_path(config: Dict[str, Any], epoch_id: str) -> Path:
    """Resolve the ledger only from the configured runtime epoch."""
    epoch_id = _validate_identifier("epoch_id", epoch_id)
    db_dir_value = (config.get("paths", {}) or {}).get("db_dir")
    if not isinstance(db_dir_value, str) or not db_dir_value.strip():
        raise PromotionCommandError("configured runtime is missing paths.db_dir")

    epoch_root = Path(db_dir_value).expanduser().resolve()
    if epoch_root.name != epoch_id:
        raise PromotionCommandError(
            f"requested epoch {epoch_id!r} does not match configured runtime epoch "
            f"{epoch_root.name!r}"
        )

    ledger_path = epoch_root / "ucf" / "ucf_ledger.db"
    if not ledger_path.is_file():
        raise PromotionCommandError(
            f"configured epoch ledger does not exist: {ledger_path}",
            exit_code=1,
        )
    return ledger_path


def inspect_epoch(
    config: Dict[str, Any],
    epoch_id: str,
    video_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """Return promotion readiness using a SQLite read-only connection."""
    epoch_id = _validate_identifier("epoch_id", epoch_id)
    if video_hash is not None:
        video_hash = _validate_identifier("video_hash", video_hash)
    ledger_path = resolve_ledger_path(config, epoch_id)

    query = (
        "SELECT video_hash, promotion_status, COUNT(*) "
        "FROM context_frames WHERE epoch_id = ?"
    )
    params: list[Any] = [epoch_id]
    if video_hash is not None:
        query += " AND video_hash = ?"
        params.append(video_hash)
    query += " GROUP BY video_hash, promotion_status ORDER BY video_hash, promotion_status"

    uri = f"{ledger_path.as_uri()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        try:
            rows = conn.execute(query, tuple(params)).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise PromotionCommandError(f"could not inspect configured epoch ledger: {exc}", exit_code=1) from exc

    by_video: Dict[str, Dict[str, int]] = {}
    for row_video_hash, promotion_status, count in rows:
        counts = by_video.setdefault(str(row_video_hash), {})
        counts[str(promotion_status)] = int(count)

    scopes = []
    for scoped_video_hash, counts in by_video.items():
        promotable = counts.get("validated", 0) > 0 and counts.get("staged", 0) == 0
        scopes.append(
            {
                "video_hash": scoped_video_hash,
                "counts": counts,
                "promotable": promotable,
            }
        )

    return {
        "status": "ready" if any(item["promotable"] for item in scopes) else "no_promotable_scopes",
        "epoch_id": epoch_id,
        "ledger_path": str(ledger_path),
        "scopes": scopes,
    }


def _require_ready_scope(config: Dict[str, Any], epoch_id: str, video_hash: str) -> None:
    report = inspect_epoch(config, epoch_id, video_hash)
    if len(report["scopes"]) != 1 or not report["scopes"][0]["promotable"]:
        raise PromotionCommandError(
            f"scope {video_hash!r} is not ready for promotion in epoch {epoch_id!r}",
            exit_code=3,
        )


def _pending_qdrant_sync(
    config: Dict[str, Any], epoch_id: str, video_hash: str
) -> Optional[Dict[str, Any]]:
    ledger_path = resolve_ledger_path(config, epoch_id)
    uri = f"{ledger_path.as_uri()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        try:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' "
                "AND name = 'ucf_qdrant_sync_outbox'"
            ).fetchone()
            if not exists:
                return None
            row = conn.execute(
                "SELECT delivery_state, attempt_count FROM ucf_qdrant_sync_outbox "
                "WHERE operation = 'promotion' AND epoch_id = ? AND video_hash = ? "
                "AND target_status = 'promoted'",
                (epoch_id, video_hash),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise PromotionCommandError(
            f"could not inspect promotion Qdrant sync state: {exc}", exit_code=1
        ) from exc
    if row is None:
        return None
    return {"delivery_state": str(row[0]), "attempt_count": int(row[1])}


def _require_pending_qdrant_sync(
    config: Dict[str, Any], epoch_id: str, video_hash: str
) -> None:
    pending = _pending_qdrant_sync(config, epoch_id, video_hash)
    if pending is None or pending["delivery_state"] != "pending":
        raise PromotionCommandError(
            f"scope {video_hash!r} has no pending promotion Qdrant sync in epoch {epoch_id!r}",
            exit_code=3,
            code="qdrant_sync_not_pending",
        )


def approve_scope(
    config: Dict[str, Any],
    epoch_id: str,
    video_hash: str,
    *,
    client_factory: ClientFactory = MiniAgentClient,
) -> Dict[str, Any]:
    """Issue a token; this function cannot execute promotion."""
    epoch_id = _validate_identifier("epoch_id", epoch_id)
    video_hash = _validate_identifier("video_hash", video_hash)
    _require_ready_scope(config, epoch_id, video_hash)
    client = client_factory(profile="safe", config=config)
    envelope, rc = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args={"video_hash": video_hash, "epoch_id": epoch_id},
        confirm=False,
    )
    token = (envelope.get("result", {}) or {}).get("confirmation_token")
    if rc != 3 or envelope.get("status") != "needs_confirmation" or not token:
        raise PromotionCommandError("promotion approval token was not issued", exit_code=1)
    return {
        "status": "approval_issued",
        "scope": {"video_hash": video_hash, "epoch_id": epoch_id},
        "confirmation_token": token,
        "expires_in_seconds": 600,
    }


def execute_scope(
    config: Dict[str, Any],
    epoch_id: str,
    video_hash: str,
    confirmation_token: str,
    *,
    client_factory: ClientFactory = MiniAgentClient,
) -> Dict[str, Any]:
    """Execute promotion using a token issued by a prior approve command."""
    epoch_id = _validate_identifier("epoch_id", epoch_id)
    video_hash = _validate_identifier("video_hash", video_hash)
    if not isinstance(confirmation_token, str) or not confirmation_token.strip():
        raise PromotionCommandError(
            "execute requires --confirmation-token or GOODQ_CONFIRMATION_TOKEN"
        )
    _require_ready_scope(config, epoch_id, video_hash)
    client = client_factory(profile="safe", config=config)
    envelope, rc = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args={"video_hash": video_hash, "epoch_id": epoch_id},
        confirm=True,
        confirmation_token=confirmation_token.strip(),
    )
    output = envelope.get("output", {}) or {}
    if rc != 0 or envelope.get("status") != "success" or output.get("status") != "promoted_complete":
        raise PromotionCommandError(
            "promotion execution did not complete",
            exit_code=1,
            code=_safe_envelope_error_code(envelope),
            result=output or None,
        )
    return {
        "status": "promotion_executed",
        "scope": {"video_hash": video_hash, "epoch_id": epoch_id},
        "result": output,
    }


def approve_reconcile_scope(
    config: Dict[str, Any],
    epoch_id: str,
    video_hash: str,
    *,
    client_factory: ClientFactory = MiniAgentClient,
) -> Dict[str, Any]:
    """Issue a fresh token for one durable pending projection scope."""
    epoch_id = _validate_identifier("epoch_id", epoch_id)
    video_hash = _validate_identifier("video_hash", video_hash)
    _require_pending_qdrant_sync(config, epoch_id, video_hash)
    client = client_factory(profile="safe", config=config)
    envelope, rc = client.execute_tool(
        tool_name="reconcile_ucf_qdrant",
        tool_args={"video_hash": video_hash, "epoch_id": epoch_id},
        confirm=False,
    )
    token = (envelope.get("result", {}) or {}).get("confirmation_token")
    if rc != 3 or envelope.get("status") != "needs_confirmation" or not token:
        raise PromotionCommandError(
            "Qdrant reconciliation approval token was not issued", exit_code=1
        )
    return {
        "status": "reconciliation_approval_issued",
        "scope": {"video_hash": video_hash, "epoch_id": epoch_id},
        "confirmation_token": token,
        "expires_in_seconds": 600,
    }


def execute_reconcile_scope(
    config: Dict[str, Any],
    epoch_id: str,
    video_hash: str,
    confirmation_token: str,
    *,
    client_factory: ClientFactory = MiniAgentClient,
) -> Dict[str, Any]:
    """Consume a fresh token to retry only the pending Qdrant projection."""
    epoch_id = _validate_identifier("epoch_id", epoch_id)
    video_hash = _validate_identifier("video_hash", video_hash)
    if not isinstance(confirmation_token, str) or not confirmation_token.strip():
        raise PromotionCommandError(
            "reconcile-execute requires --confirmation-token or GOODQ_CONFIRMATION_TOKEN"
        )
    _require_pending_qdrant_sync(config, epoch_id, video_hash)
    client = client_factory(profile="safe", config=config)
    envelope, rc = client.execute_tool(
        tool_name="reconcile_ucf_qdrant",
        tool_args={"video_hash": video_hash, "epoch_id": epoch_id},
        confirm=True,
        confirmation_token=confirmation_token.strip(),
    )
    output = envelope.get("output", {}) or {}
    if (
        rc != 0
        or envelope.get("status") != "success"
        or output.get("status") != "qdrant_sync_reconciled"
    ):
        raise PromotionCommandError(
            "Qdrant reconciliation did not complete",
            exit_code=1,
            code=_safe_envelope_error_code(envelope),
            result=output or None,
        )
    return {
        "status": "qdrant_sync_reconciled",
        "scope": {"video_hash": video_hash, "epoch_id": epoch_id},
        "result": output,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect, approve, and execute UCF promotion as separate operations."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Read promotion readiness")
    inspect_parser.add_argument("--epoch-id", required=True)
    inspect_parser.add_argument("--video-hash")

    approve_parser = subparsers.add_parser("approve", help="Issue a scope-bound token")
    approve_parser.add_argument("--epoch-id", required=True)
    approve_parser.add_argument("--video-hash", required=True)

    execute_parser = subparsers.add_parser("execute", help="Consume a prior approval token")
    execute_parser.add_argument("--epoch-id", required=True)
    execute_parser.add_argument("--video-hash", required=True)
    execute_parser.add_argument("--confirmation-token")

    reconcile_approve_parser = subparsers.add_parser(
        "reconcile-approve", help="Issue a token for one pending Qdrant sync"
    )
    reconcile_approve_parser.add_argument("--epoch-id", required=True)
    reconcile_approve_parser.add_argument("--video-hash", required=True)

    reconcile_execute_parser = subparsers.add_parser(
        "reconcile-execute", help="Retry one pending Qdrant sync"
    )
    reconcile_execute_parser.add_argument("--epoch-id", required=True)
    reconcile_execute_parser.add_argument("--video-hash", required=True)
    reconcile_execute_parser.add_argument("--confirmation-token")
    return parser


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    config: Optional[Dict[str, Any]] = None,
    client_factory: ClientFactory = MiniAgentClient,
) -> int:
    args = build_parser().parse_args(argv)
    runtime_config = config or load_configs({})
    try:
        if args.command == "inspect":
            result = inspect_epoch(runtime_config, args.epoch_id, args.video_hash)
        elif args.command == "approve":
            result = approve_scope(
                runtime_config,
                args.epoch_id,
                args.video_hash,
                client_factory=client_factory,
            )
        elif args.command == "execute":
            token = args.confirmation_token or os.environ.get("GOODQ_CONFIRMATION_TOKEN", "")
            result = execute_scope(
                runtime_config,
                args.epoch_id,
                args.video_hash,
                token,
                client_factory=client_factory,
            )
        elif args.command == "reconcile-approve":
            result = approve_reconcile_scope(
                runtime_config,
                args.epoch_id,
                args.video_hash,
                client_factory=client_factory,
            )
        else:
            token = args.confirmation_token or os.environ.get("GOODQ_CONFIRMATION_TOKEN", "")
            result = execute_reconcile_scope(
                runtime_config,
                args.epoch_id,
                args.video_hash,
                token,
                client_factory=client_factory,
            )
    except PromotionCommandError as exc:
        error_result: Dict[str, Any] = {
            "status": "error",
            "code": exc.code,
            "message": str(exc),
        }
        if exc.result is not None:
            error_result["result"] = exc.result
        print(
            json.dumps(error_result, ensure_ascii=False),
            file=sys.stderr,
        )
        return exc.exit_code

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
