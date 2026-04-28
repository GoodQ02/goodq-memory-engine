from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse

from lib import control_recurrence_index


router = APIRouter(prefix="/api/control-recurrence", tags=["control-recurrence"])


@router.get("/reports")
def list_control_recurrence_reports() -> Dict[str, Any]:
    """Read the durable recurrence report index without regenerating reports."""

    return control_recurrence_index.list_report_index()


@router.get("/reports/latest")
def latest_control_recurrence_report() -> Dict[str, Any]:
    """Return the latest indexed recurrence report entry."""

    return control_recurrence_index.latest_report_entry()


@router.get("/reports/{report_id}")
def get_control_recurrence_report(report_id: str):
    """Return durable JSON content for an indexed recurrence report."""

    payload, status_code = control_recurrence_index.load_report_json(report_id)
    if status_code != 200:
        return JSONResponse(status_code=status_code, content=payload)
    return payload


@router.get("/reports/{report_id}/markdown")
def get_control_recurrence_report_markdown(report_id: str):
    """Return markdown content for an indexed recurrence report."""

    payload, status_code = control_recurrence_index.load_report_markdown(report_id)
    if status_code != 200 or not isinstance(payload, str):
        return JSONResponse(status_code=status_code, content=payload)
    return PlainTextResponse(payload, media_type="text/plain")
