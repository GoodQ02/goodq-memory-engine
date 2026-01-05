from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Response

from lib.run_index import list_runs_with_cursor

router = APIRouter()


@router.get("/runs")
def get_runs(
    response: Response,
    limit: int = Query(50),
    trigger: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    cursor: Optional[str] = Query(None),
    latest: bool = Query(False),
):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")

    try:
        runs, next_cursor = list_runs_with_cursor(
            limit=limit,
            trigger=trigger,
            status=status,
            cursor=cursor,
            latest=latest,
        )
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail=f"unexpected read error: {exc}") from exc

    if next_cursor:
        response.headers["X-Next-Cursor"] = next_cursor

    return runs
