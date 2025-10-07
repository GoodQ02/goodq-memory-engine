from __future__ import annotations
import os
import sys
import pathlib


def main() -> None:
    # Ensure repo root is on sys.path so 'zenml_project' is importable
    here = pathlib.Path(__file__).resolve()
    repo_root = here.parents[2]  # .../zenml_project/api/server.py -> repo root
    sys.path.insert(0, str(repo_root))

    host = os.environ.get("GOODQ_API_HOST", "0.0.0.0")
    try:
        port = int(os.environ.get("GOODQ_API_PORT", "8000"))
    except Exception:
        port = 8000

    from uvicorn import run  # type: ignore
    from zenml_project.api.main import app
    print(f"[api] Starting FastAPI on http://{host}:{port}")
    run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

