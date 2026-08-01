from __future__ import annotations

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]
RETRO_JS_PATH = REPO_ROOT / "ui" / "retro_console_v1" / "static" / "js" / "retro.js"
RETRO_JS = RETRO_JS_PATH.read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    match = re.search(rf"(?:async\s+)?function\s+{re.escape(name)}\s*\(", RETRO_JS)
    assert match is not None, f"Missing JavaScript function: {name}"
    opening = RETRO_JS.index("{", match.end())
    depth = 0
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    index = opening
    while index < len(RETRO_JS):
        char = RETRO_JS[index]
        following = RETRO_JS[index + 1] if index + 1 < len(RETRO_JS) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
        elif block_comment:
            if char == "*" and following == "/":
                block_comment = False
                index += 1
        elif quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char == "/" and following == "/":
            line_comment = True
            index += 1
        elif char == "/" and following == "*":
            block_comment = True
            index += 1
        elif char in {'"', "'", "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return RETRO_JS[match.start() : index + 1]
        index += 1
    raise AssertionError(f"Unclosed JavaScript function: {name}")


def test_temporal_summary_requires_native_confirmation_before_prepare() -> None:
    execution = _function_source("executeNarrativeSearch")

    assert "window.confirm(" in execution
    assert "if (!approved)" in execution
    assert execution.index("window.confirm(") < execution.index(
        'body: JSON.stringify({ action: "prepare", request: summaryRequest })'
    )


def test_temporal_summary_resubmits_one_exact_normalized_request() -> None:
    execution = _function_source("executeNarrativeSearch")
    request_block = execution[
        execution.index("const summaryRequest = {") : execution.index(
            "summaryBody.className", execution.index("const summaryRequest = {")
        )
    ]

    for field in (
        "entities",
        "start_date",
        "end_date",
        "time_hint",
        "source_file",
        "modality",
        "max_results",
        "grouping",
        "summary_style",
    ):
        assert re.search(rf"\b{field}\s*:", request_block)
    assert 'JSON.stringify({ action: "prepare", request: summaryRequest })' in execution
    assert re.search(
        r"body:\s*JSON\.stringify\(\{\s*"
        r'action:\s*"confirm",\s*'
        r"job_id:\s*jobId,\s*"
        r"epoch_id:\s*preparedScope\.epoch_id,\s*"
        r"request_sha256:\s*preparedScope\.request_sha256,\s*"
        r"execution_policy_sha256:\s*preparedScope\.execution_policy_sha256,\s*"
        r"confirmation_token:\s*confirmationToken,\s*"
        r"request:\s*summaryRequest\s*"
        r"\}\)",
        execution,
    )


def test_temporal_confirmation_token_is_local_and_cleared() -> None:
    execution = _function_source("executeNarrativeSearch")

    assert "let confirmationToken = prepareData && prepareData.confirmation_token;" in execution
    assert "prepareData.confirmation_token = null;" in execution
    assert execution.index("prepareData.confirmation_token = null;") < execution.index(
        "isSafeTemporalSummaryPrepare(prepareData, confirmationToken)"
    )
    assert "finally" in execution
    assert "confirmationToken = null;" in execution
    for line in execution.splitlines():
        if any(
            surface in line
            for surface in (
                "state.",
                "localStorage",
                "sessionStorage",
                "textContent",
                "innerHTML",
                "console.",
                "URLSearchParams",
            )
        ):
            assert "confirmationToken" not in line


def test_temporal_summary_polls_only_encoded_exact_job() -> None:
    poller = _function_source("pollTemporalSummaryJob")

    assert "encodeURIComponent(jobId)" in poller
    assert "isSafeTemporalSummaryJob(job, jobId, expectedScope)" in poller
    assert 'data.status !== job.state' in poller
    assert "state.activeTemporalSummaryJobId = jobId;" in poller
    assert "state.activeTemporalSummaryJobId !== jobId" in poller
    assert "state.activeTemporalSummaryJobId = null;" in poller
    assert "state.temporalSummaryGeneration !== generation" in poller
    assert re.search(
        r"fetch\(\s*`/api/search/temporal/summarize/"
        r"\$\{encodeURIComponent\(jobId\)\}`",
        poller,
    )
    assert "latest" not in poller.lower()


def test_temporal_success_requires_bound_receipt_and_reports_audit_failure() -> None:
    poller = _function_source("pollTemporalSummaryJob")
    validator = _function_source("isSafeTemporalSummaryReceipt")

    assert 'job.state === "succeeded"' in poller
    assert 'isSafeTemporalSummaryReceipt(data.receipt, job, "succeeded")' in poller
    assert '["recorded", "failed"].includes(job.audit_status)' in poller
    assert 'job.audit_status' in poller
    assert 'receipt.schema !== "goodq.temporal-summary-result.v1"' in validator
    assert "receipt.job_id !== job.job_id" in validator
    assert "receipt.request_sha256 !== job.scope.request_sha256" in validator
    assert "receipt.execution_policy_sha256 !== job.scope.execution_policy_sha256" in validator


def test_temporal_terminal_states_are_distinct_and_legacy_sync_path_is_gone() -> None:
    poller = _function_source("pollTemporalSummaryJob")
    execution = _function_source("executeNarrativeSearch")

    for state in ("failed", "interrupted", "expired"):
        assert f'job.state === "{state}"' in poller
    assert 'apiPost("/api/search/temporal/summarize"' not in execution
    assert "summaryResponse.status" not in execution


def test_overlapping_temporal_requests_cannot_reclaim_current_render() -> None:
    execution = _function_source("executeNarrativeSearch")
    poller = _function_source("pollTemporalSummaryJob")

    assert "const narrativeGeneration = state.temporalSummaryGeneration + 1;" in execution
    assert "state.temporalSummaryGeneration = narrativeGeneration;" in execution
    assert execution.count(
        "state.temporalSummaryGeneration !== narrativeGeneration"
    ) >= 6
    assert "generation" in poller.split("{", maxsplit=1)[0]
    assert "state.temporalSummaryGeneration !== generation" in poller


def test_confirm_conflict_preserves_exact_terminal_state() -> None:
    execution = _function_source("executeNarrativeSearch")

    assert "confirmResponse.status === 409" in execution
    assert "isSafeTemporalSummaryJob(conflictJob, jobId, preparedScope)" in execution
    assert 'conflictJob.state === "expired" || conflictJob.state === "failed"' in execution
    assert '"Summary confirmation expired. Start a new confirmed request."' in execution
    assert '"Summary authorization failed. Start a new confirmed request."' in execution


def test_lan_status_denial_stops_polling_and_explains_read_only_mode() -> None:
    api_get = _function_source("apiGet")
    polling = _function_source("pollStatus")

    assert "error.status = response.status;" in api_get
    assert "let shouldContinuePolling = true;" in polling
    assert "err.status === 403" in polling
    assert "shouldContinuePolling = false;" in polling
    assert (
        'headerStatus.textContent = "Status: LAN READ-ONLY — operator telemetry requires loopback";'
        in polling
    )
    assert re.search(
        r"if \(shouldContinuePolling\)\s*\{\s*"
        r"pollingTimeoutId = setTimeout\(pollStatus, currentPollInterval\);",
        polling,
    )


def test_cognitive_scene_context_renders_persisted_values_as_text() -> None:
    inspector = _function_source("renderInspector")
    cognitive_context = inspector[
        inspector.index("const evidenceList =") : inspector.index("const conflicts =")
    ]

    assert "innerHTML" not in cognitive_context
    for value in ("kind", "ev.value || ev", "axis", "h.claim", "weight"):
        assert f"textContent = {value}" in cognitive_context
    assert "document.createTextNode(role)" in cognitive_context
    assert "document.createTextNode(`${family}claim: `)" in cognitive_context
