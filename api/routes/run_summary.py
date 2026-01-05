from __future__ import annotations

import re
from fastapi import APIRouter, HTTPException

from lib.run_summary import summarize_run_with_status

router = APIRouter()

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
)


@router.get("/runs/{run_id}")
def get_run_summary(run_id: str):
    if not UUID_RE.match(run_id):
        raise HTTPException(status_code=400, detail="invalid run_id")

    try:
        summary, status = summarize_run_with_status(run_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"unexpected read error: {exc}") from exc

    if status == "no_artifacts":
        raise HTTPException(status_code=404, detail="no observability artifacts available")
    if status == "not_found":
        raise HTTPException(status_code=404, detail="run_id not found")

    return summary
