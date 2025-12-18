from __future__ import annotations
import os
import sys
import pathlib


def main() -> None:
    # Ensure repo root is on sys.path so 'goodq4all' is importable
    here = pathlib.Path(__file__).resolve()
    repo_root = here.parents[1]  # .../goodq4all/api/server.py -> goodq4all root
    sys.path.insert(0, str(repo_root))

    host = os.environ.get("GOODQ_API_HOST", "0.0.0.0")
    try:
        port = int(os.environ.get("GOODQ_API_PORT", "30000"))
    except Exception:
        port = 30000

    from uvicorn import run  # type: ignore
    from api.main import app
    print(f"[api] Starting FastAPI on http://{host}:{port}")
    run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

