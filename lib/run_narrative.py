from __future__ import annotations

from typing import Any, Dict, List, Optional

NARRATIVE_EVIDENCE_LINE = "This narrative is based on available logs and telemetry."
NO_EVIDENCE_LINE = "No evidence available."

OBSERVED_TEMPLATE = "{label} observed: {count}."
NOT_OBSERVED_TEMPLATE = "{label} were not observed."

UNKNOWN_VALUE = "unknown"


def build_run_narrative(summary: Dict[str, Any]) -> List[str]:
    sentences: List[str] = []

    evidence = summary.get("evidence") if isinstance(summary, dict) else None
    files_read = None
    if isinstance(evidence, dict):
        files_read = evidence.get("files_read")

    if isinstance(files_read, list) and files_read:
        sentences.append(NARRATIVE_EVIDENCE_LINE)
    elif files_read == []:
        sentences.append(NO_EVIDENCE_LINE)

    run_header = summary.get("run_header") if isinstance(summary, dict) else None
    if isinstance(run_header, dict):
        run_id = _value_or_unknown(run_header.get("run_id"))
        trigger = _value_or_unknown(run_header.get("trigger_source"))
        start_time = _value_or_unknown(run_header.get("start_time"))
        end_time = _value_or_unknown(run_header.get("end_time"))
        duration = _value_or_unknown(run_header.get("total_duration_seconds"))

        sentences.append(f"Run ID: {run_id}.")
        sentences.append(f"Trigger source: {trigger}.")
        sentences.append(f"Start time: {start_time}.")
        sentences.append(f"End time: {end_time}.")
        sentences.append(f"Total duration seconds: {duration}.")

    overview = summary.get("file_job_overview") if isinstance(summary, dict) else None
    if isinstance(overview, dict):
        input_files = overview.get("input_files")
        if isinstance(input_files, list) and input_files:
            sentences.append(
                OBSERVED_TEMPLATE.format(label="Input files", count=len(input_files))
            )
        else:
            sentences.append(NOT_OBSERVED_TEMPLATE.format(label="Input files"))

        scenes = overview.get("scenes_processed")
        sentences.append(f"Scenes processed: {_value_or_unknown(scenes)}.")

        steps = overview.get("steps_executed")
        sentences.append(f"Steps executed: {_value_or_unknown(steps)}.")

    audio_summary = summary.get("audio_wsl2_summary") if isinstance(summary, dict) else None
    if isinstance(audio_summary, dict):
        notes = audio_summary.get("notes")
        if notes == "not observed":
            sentences.append(NOT_OBSERVED_TEMPLATE.format(label="Audio jobs"))
        else:
            jobs_found = audio_summary.get("jobs_found")
            sentences.append(
                OBSERVED_TEMPLATE.format(label="Audio jobs", count=_value_or_unknown(jobs_found))
            )

    agent_activity = summary.get("agent_activity") if isinstance(summary, dict) else None
    if isinstance(agent_activity, list):
        if agent_activity:
            sentences.append(
                OBSERVED_TEMPLATE.format(label="Agent activity", count=len(agent_activity))
            )
        else:
            sentences.append("Agent activity was not observed.")
    else:
        sentences.append("Agent activity could not be determined from available data.")

    errors_warnings = summary.get("errors_warnings") if isinstance(summary, dict) else None
    if isinstance(errors_warnings, dict):
        errors = errors_warnings.get("errors")
        warnings = errors_warnings.get("warnings")
        sentences.append(f"Errors recorded: {_count_or_unknown(errors)}.")
        sentences.append(f"Warnings recorded: {_count_or_unknown(warnings)}.")

    outcome = summary.get("outcome_classification") if isinstance(summary, dict) else None
    if isinstance(outcome, dict):
        status = outcome.get("status")
        sentences.append(f"Overall outcome: {_format_outcome(status)}.")

    return sentences


def render_run_narrative(summary: Dict[str, Any]) -> str:
    return "\n".join(build_run_narrative(summary))


def _value_or_unknown(value: Any) -> str:
    if value is None:
        return UNKNOWN_VALUE
    if isinstance(value, str) and not value.strip():
        return UNKNOWN_VALUE
    return str(value)


def _count_or_unknown(value: Optional[Any]) -> str:
    if isinstance(value, list):
        return str(len(value))
    return UNKNOWN_VALUE


def _format_outcome(value: Any) -> str:
    normalized = str(value or UNKNOWN_VALUE).strip().lower()
    if normalized == "partial_success":
        return "partial success"
    if normalized in ("success", "failed", "unknown"):
        return normalized
    return UNKNOWN_VALUE
