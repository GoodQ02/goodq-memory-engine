from __future__ import annotations
import argparse
import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any

from steps.common.config_redaction import redact_config
from steps.common.config_loader import load_configs


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _cfg_mapping(value: Any, key: str) -> dict[str, Any]:
    if isinstance(value, dict):
        item = value.get(key)
        if isinstance(item, dict):
            return item
    return {}


def _derive_data_root(cfg: dict[str, Any]) -> str | None:
    host_data_root = _cfg_mapping(cfg, "host").get("data_root")
    if isinstance(host_data_root, str) and host_data_root.strip():
        return host_data_root

    paths_data_root = _cfg_mapping(cfg, "paths").get("data_root")
    if isinstance(paths_data_root, str) and paths_data_root.strip():
        normalized = paths_data_root.replace("\\", "/").rstrip("/")
        suffix = "/GoodQ_Data"
        if normalized.endswith(suffix):
            return normalized[: -len(suffix)]
        return normalized

    for value in _cfg_mapping(cfg, "paths").values():
        if not isinstance(value, str):
            continue
        normalized = value.replace("\\", "/")
        marker = "/GoodQ_Data/"
        marker_index = normalized.find(marker)
        if marker_index > 0:
            return normalized[:marker_index]
    return None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Print sanitized resolved GoodQ runtime configuration as JSON.")
    parser.add_argument(
        "--include-local-values",
        action="store_true",
        help="Include local path values while still redacting all secret-bearing values.",
    )
    args = parser.parse_args(argv)

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
        cfg = load_configs({})

    redacted_cfg = redact_config(
        cfg,
        include_local_values=args.include_local_values,
        repo_root=_repo_root(),
        data_root=_derive_data_root(cfg),
        user_root=Path.home(),
    )

    if stdout_buffer.getvalue().strip() or stderr_buffer.getvalue().strip():
        print("[WARN] load_configs emitted output while building sanitized config; suppressed for JSON safety.", file=sys.stderr)

    print(json.dumps(redacted_cfg, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
