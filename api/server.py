from __future__ import annotations
import os
import sys
import pathlib


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


def main() -> None:
    # Ensure repo root is on sys.path so 'goodq4all' is importable
    here = pathlib.Path(__file__).resolve()
    repo_root = here.parents[1]  # .../goodq4all/api/server.py -> goodq4all root
    sys.path.insert(0, str(repo_root))

    host, port = _resolve_api_bind_defaults()

    from uvicorn import run  # type: ignore
    from api.main import app
    print(f"[api] Starting FastAPI on http://{host}:{port}")
    run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

