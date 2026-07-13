from __future__ import annotations
import os
import sys
import pathlib
import re
from urllib.parse import unquote_plus


_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "q",
        "token",
        "session_token",
        "api_key",
        "auth_token",
        "password",
        "secret",
    }
)
_SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"\b(token|session_token|api_key|auth_token|password|secret)"
    r"\s*=\s*[a-zA-Z0-9_\-\%\.\+\/\~\@]+",
    flags=re.IGNORECASE,
)


def _redact_query_parameters(value: str) -> str:
    """Redact sensitive URL-query values without rewriting safe parameters."""
    if "?" not in value:
        return value

    prefix, _, query_with_fragment = value.partition("?")
    query, fragment_marker, fragment = query_with_fragment.partition("#")
    redacted_fields: list[str] = []

    for field in query.split("&"):
        raw_key, separator, _raw_value = field.partition("=")
        normalized_key = unquote_plus(raw_key).strip().lower()
        if normalized_key in _SENSITIVE_QUERY_KEYS:
            field = f"{raw_key}=REDACTED"
        elif not separator:
            field = raw_key
        redacted_fields.append(field)

    redacted = f"{prefix}?{'&'.join(redacted_fields)}"
    if fragment_marker:
        redacted = f"{redacted}#{fragment}"
    return redacted


def _redact_log_value(value: str) -> str:
    redacted = _redact_query_parameters(value)
    return _SENSITIVE_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}=REDACTED",
        redacted,
    )


def _resolve_api_bind_defaults() -> tuple[str, int]:
    config_host = "127.0.0.1"
    config_port = 30000

    try:
        from steps.common.config_loader import load_configs

        cfg = load_configs({})
        if isinstance(cfg, dict):
            api_cfg = cfg.get("api")
            if isinstance(api_cfg, dict):
                host_value = api_cfg.get("host")
                if isinstance(host_value, str) and host_value.strip():
                    config_host = host_value.strip()
                port_value = api_cfg.get("port")
                try:
                    if port_value not in (None, ""):
                        config_port = int(port_value)
                except Exception:
                    pass
    except Exception:
        pass

    host = os.environ.get("GOODQ_API_HOST", config_host)
    try:
        port = int(os.environ.get("GOODQ_API_PORT", str(config_port)))
    except Exception:
        port = config_port
    return host, port


def _find_available_port(host: str, start_port: int) -> int:
    import socket
    for p in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, p))
                return p
        except OSError:
            print(f"[api] [WARNING] Port {p} is occupied. Probing fallback port...")
            continue
    print(f"[api] [ERROR] Port exhaustion: All ports from {start_port} to {start_port + 99} are in use.")
    raise OSError(f"Could not find an available port in range {start_port} to {start_port + 99}")


def main() -> None:
    # Ensure repo root is on sys.path so 'goodq4all' is importable
    here = pathlib.Path(__file__).resolve()
    repo_root = here.parents[1]  # .../goodq4all/api/server.py -> goodq4all root
    sys.path.insert(0, str(repo_root))

    # Apply token redaction filters to uvicorn loggers to protect session tokens in logs
    import logging
    class TokenRedactingFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if isinstance(record.msg, str):
                record.msg = _redact_log_value(record.msg)
            if record.args:
                new_args = []
                for arg in record.args:
                    if isinstance(arg, str):
                        new_args.append(_redact_log_value(arg))
                    else:
                        new_args.append(arg)
                record.args = tuple(new_args)
            return True

    for name in ("uvicorn.access", "uvicorn", "uvicorn.error"):
        logger_obj = logging.getLogger(name)
        if not any(isinstance(f, TokenRedactingFilter) for f in logger_obj.filters):
            logger_obj.addFilter(TokenRedactingFilter())

    host, start_port = _resolve_api_bind_defaults()
    try:
        port = _find_available_port(host, start_port)
    except OSError as e:
        print(f"[api] [CRITICAL] {e}")
        sys.exit(1)

    from uvicorn import run  # type: ignore
    from api.main import app
    print(f"[api] Starting FastAPI on http://{host}:{port}")
    run(app, host=host, port=port, log_level="info", proxy_headers=False)


if __name__ == "__main__":
    main()
