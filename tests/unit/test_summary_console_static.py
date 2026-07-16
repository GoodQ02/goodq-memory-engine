from __future__ import annotations

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]
SUMMARY_JS_PATH = REPO_ROOT / "ui" / "summary_console" / "static" / "js" / "summary.js"
SUMMARY_JS = SUMMARY_JS_PATH.read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    match = re.search(rf"(?:async\s+)?function\s+{re.escape(name)}\s*\(", SUMMARY_JS)
    assert match is not None, f"Missing JavaScript function: {name}"
    opening = SUMMARY_JS.index("{", match.end())
    depth = 0
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    index = opening
    while index < len(SUMMARY_JS):
        char = SUMMARY_JS[index]
        following = SUMMARY_JS[index + 1] if index + 1 < len(SUMMARY_JS) else ""
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
                return SUMMARY_JS[match.start() : index + 1]
        index += 1
    raise AssertionError(f"Unclosed JavaScript function: {name}")


def test_rewrite_requires_native_confirmation_before_prepare_fetch() -> None:
    listener = _function_source("setupRegenListener")

    assert "window.confirm(" in listener
    assert "if (!confirmed) return;" in listener
    assert listener.index("window.confirm(") < listener.index("await fetch(")


def test_rewrite_uses_exact_prepare_and_confirm_bodies() -> None:
    listener = _function_source("setupRegenListener")

    assert 'body: JSON.stringify({ action: "prepare" })' in listener
    assert re.search(
        r"body:\s*JSON\.stringify\(\{\s*"
        r'action:\s*"confirm",\s*'
        r"job_id:\s*jobId,\s*"
        r"confirmation_token:\s*confirmationToken\s*"
        r"\}\)",
        listener,
    )


def test_confirmation_token_is_local_and_cleared_after_confirm_attempt() -> None:
    listener = _function_source("setupRegenListener")
    state_declaration = SUMMARY_JS.split("let pollInterval", maxsplit=1)[0]

    assert "let confirmationToken =" in listener
    assert "finally" in listener
    assert "confirmationToken = null;" in listener
    assert "confirmationToken" not in state_declaration
    for line in listener.splitlines():
        if any(
            surface in line
            for surface in (
                "state.",
                "localStorage",
                "sessionStorage",
                "textContent",
                "innerHTML",
                "showToast",
                "console.",
                "URLSearchParams",
            )
        ):
            assert "confirmationToken" not in line


def _case_block(function_source: str, state: str) -> str:
    start = function_source.index(f'case "{state}":')
    candidates = [
        position
        for marker in ('\n    case "', "\n    default:")
        if (position := function_source.find(marker, start + 1)) != -1
    ]
    end = min(candidates) if candidates else len(function_source)
    return function_source[start:end]


def test_collection_create_requires_native_confirmation_before_prepare_fetch() -> None:
    creator = _function_source("createSummaryCollection")

    assert "window.confirm(" in creator
    assert "if (!confirmed) return null;" in creator
    assert creator.index("window.confirm(") < creator.index("await fetch(")


def test_collection_create_uses_exact_prepare_and_confirm_bodies() -> None:
    creator = _function_source("createSummaryCollection")

    assert re.search(
        r"body:\s*JSON\.stringify\(\{\s*"
        r'action:\s*"prepare",\s*'
        r"collection:\s*payload\s*"
        r"\}\)",
        creator,
    )
    assert re.search(
        r"body:\s*JSON\.stringify\(\{\s*"
        r'action:\s*"confirm",\s*'
        r"action_id:\s*actionId,\s*"
        r"epoch_id:\s*epochId,\s*"
        r"payload_sha256:\s*payloadSha256,\s*"
        r"confirmation_token:\s*confirmationToken,\s*"
        r"collection:\s*payload\s*"
        r"\}\)",
        creator,
    )


def test_collection_create_validates_exact_prepare_and_confirm_evidence() -> None:
    prepare_validator = _function_source("isSafeCollectionCreatePrepare")
    confirm_validator = _function_source("isSafeCollectionCreateConfirm")

    assert "/^action_[0-9a-f]{32}$/" in prepare_validator
    assert "/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/" in prepare_validator
    assert "/^[0-9a-f]{64}$/" in prepare_validator
    assert "data.success === true" in prepare_validator
    assert "data.action_id === actionId" in confirm_validator
    assert "data.collection.source_epoch === epochId" in confirm_validator
    assert "data.collection.name === expectedName" in confirm_validator
    assert '["recorded", "failed"].includes(data.audit_status)' in confirm_validator


def test_collection_create_token_is_local_cleared_and_never_rendered() -> None:
    creator = _function_source("createSummaryCollection")
    state_declaration = SUMMARY_JS.split("let pollInterval", maxsplit=1)[0]

    assert "let confirmationToken =" in creator
    assert "prepareData.confirmation_token = null;" in creator
    assert creator.index("prepareData.confirmation_token = null;") < creator.index(
        "isSafeCollectionCreatePrepare(prepareData, confirmationToken)"
    )
    assert "finally" in creator
    assert "confirmationToken = null;" in creator
    assert "confirmationToken" not in state_declaration
    for line in creator.splitlines():
        if any(
            surface in line
            for surface in (
                "state.",
                "localStorage",
                "sessionStorage",
                "textContent",
                "innerHTML",
                "showToast",
                "console.",
                "URLSearchParams",
            )
        ):
            assert "confirmationToken" not in line


def test_collection_create_ui_success_follows_confirmed_durable_result() -> None:
    creator = _function_source("createSummaryCollection")
    listener = _function_source("setupModalListeners")

    assert "if (!confirmResp.ok)" in creator
    assert "isSafeCollectionCreateConfirm(" in creator
    assert creator.index("if (!confirmResp.ok)") < creator.index("return confirmData.collection;")
    assert creator.index("isSafeCollectionCreateConfirm(") < creator.index(
        'showToast("Collection saved successfully.")'
    )
    assert 'confirmData.audit_status === "failed"' in creator
    assert "durable audit recording needs attention" in creator
    assert "await createSummaryCollection(payload)" in listener
    assert listener.index("await createSummaryCollection(payload)") < listener.index("closeModal()")
    assert listener.index("await createSummaryCollection(payload)") < listener.index("loadCustomCollections()")
    assert "body: JSON.stringify(payload)" not in listener


def test_collection_delete_requires_confirmation_before_prepare_fetch() -> None:
    deleter = _function_source("handleDeleteCollection")

    assert "window.confirm(" in deleter
    assert "if (!confirmed) return;" in deleter
    assert deleter.index("window.confirm(") < deleter.index("await fetch(")


def test_collection_delete_uses_exact_prepare_and_confirm_bodies() -> None:
    deleter = _function_source("handleDeleteCollection")

    assert "encodeURIComponent(collectionId)" in deleter
    assert 'body: JSON.stringify({ action: "prepare" })' in deleter
    assert re.search(
        r"body:\s*JSON\.stringify\(\{\s*"
        r'action:\s*"confirm",\s*'
        r"job_id:\s*jobId,\s*"
        r"epoch_id:\s*epochId,\s*"
        r"expected_record_sha256:\s*expectedRecordSha256,\s*"
        r"confirmation_token:\s*confirmationToken\s*"
        r"\}\)",
        deleter,
    )


def test_collection_delete_validates_exact_public_job_scope() -> None:
    validator = _function_source("isSafeCollectionDeleteJob")

    assert "/^job_[0-9a-f]{32}$/" in validator
    assert 'job.operation === "summary_collection.delete"' in validator
    assert "Object.keys(job.scope).length === 3" in validator
    assert "job.scope.collection_id === collectionId" in validator
    assert "/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/" in validator
    assert "/^[0-9a-f]{64}$/" in validator


def test_collection_delete_token_is_local_cleared_and_never_rendered() -> None:
    deleter = _function_source("handleDeleteCollection")

    assert "let confirmationToken =" in deleter
    assert "prepareData.confirmation_token = null;" in deleter
    assert deleter.index("prepareData.confirmation_token = null;") < deleter.index(
        "!isSafeCollectionDeleteJob(preparedJob, collectionId)"
    )
    assert "finally" in deleter
    assert "confirmationToken = null;" in deleter
    for line in deleter.splitlines():
        if any(
            surface in line
            for surface in (
                "state.",
                "localStorage",
                "sessionStorage",
                "textContent",
                "innerHTML",
                "showToast",
                "console.",
                "URLSearchParams",
            )
        ):
            assert "confirmationToken" not in line


def test_collection_delete_success_requires_exact_terminal_outcome() -> None:
    deleter = _function_source("handleDeleteCollection")

    assert "if (confirmResp.status !== 200)" in deleter
    assert "isSafeCollectionDeleteJob(confirmData && confirmData.job, collectionId)" in deleter
    assert 'confirmData.job.state !== "succeeded"' in deleter
    assert 'confirmData.job.outcome.code !== "collection_deleted"' in deleter
    assert "collection_finalization_pending" in deleter
    assert "detail.job.scope.epoch_id === epochId" in deleter
    assert "detail.job.scope.expected_record_sha256 === expectedRecordSha256" in deleter
    assert 'detail.job.state === "running"' in deleter
    assert 'confirmData.job.audit_status === "failed"' in deleter
    assert "durable audit recording needs attention" in deleter
    assert deleter.index('confirmData.job.outcome.code !== "collection_deleted"') < deleter.index(
        "showToast('Collection deleted.')"
    )


def test_public_summary_job_validation_is_exact() -> None:
    validator = _function_source("isSafeSummaryJob")

    assert "/^job_[0-9a-f]{32}$/" in validator
    assert 'job.operation === "video_summary.generate"' in validator
    assert 'job.scope.video_hash === videoHash' in validator


def test_polling_uses_encoded_job_id_and_represents_every_durable_state() -> None:
    poller = _function_source("pollSummaryJobStatus")
    handler = _function_source("handleSummaryJobState")

    assert "?job_id=${encodeURIComponent(jobId)}" in poller
    for status in (
        "pending_confirmation",
        "authorizing",
        "queued",
        "running",
        "succeeded",
        "failed",
        "interrupted",
        "expired",
        "not_started",
    ):
        assert f'case "{status}":' in handler
    assert "default:" in handler


def test_success_notification_and_reload_exist_only_in_succeeded_branch() -> None:
    handler = _function_source("handleSummaryJobState")
    succeeded = _case_block(handler, "succeeded")
    without_succeeded = handler.replace(succeeded, "")
    success_handler = _function_source("handleSucceededSummaryJob")

    assert "handleSucceededSummaryJob(" in succeeded
    assert "handleSucceededSummaryJob(" not in without_succeeded
    assert "Narrative summary generated successfully." in success_handler
    assert "loadVideoProfile(" in success_handler


def test_non_success_states_stop_or_continue_without_false_completion() -> None:
    handler = _function_source("handleSummaryJobState")
    stopper = _function_source("stopSummaryPolling")

    for status in (
        "pending_confirmation",
        "failed",
        "interrupted",
        "expired",
        "not_started",
    ):
        branch = _case_block(handler, status)
        assert "stopSummaryPolling(" in branch
        assert "return false;" in branch
    for status in ("authorizing", "queued", "running"):
        branch = _case_block(handler, status)
        assert "return true;" in branch
        assert "stopSummaryPolling(" not in branch
    assert "clearTimeout(pollInterval)" in stopper
    assert "state.activeSummaryJobId = null;" in stopper
    assert "state.summarizationInProgress = false;" in stopper
    assert "regenBtn.disabled = false;" in stopper


def test_polling_failures_are_bounded_and_idle_completion_is_removed() -> None:
    poller = _function_source("pollSummaryJobStatus")
    listener = _function_source("setupRegenListener")

    assert "const MAX_SUMMARY_POLL_FAILURES =" in SUMMARY_JS
    assert "failureCount + 1" in poller
    assert "nextFailureCount >= MAX_SUMMARY_POLL_FAILURES" in poller
    assert "scheduleSummaryPoll(" in poller
    assert "Unknown summary status" in poller
    assert "idle" not in poller
    assert "idle" not in _function_source("loadVideoProfile")
    assert "{ method: 'POST' }" not in listener


def test_poller_rechecks_active_job_after_network_await() -> None:
    poller = _function_source("pollSummaryJobStatus")
    guard = "if (state.activeSummaryJobId !== jobId) return;"
    response_parsed = poller.index("await resp.json()")
    catch_started = poller.index("catch (error)")

    assert poller.count(guard) >= 3
    assert poller.index(guard, response_parsed) < catch_started
    assert poller.index(guard, catch_started) > catch_started


def test_poller_rejects_top_level_and_job_state_disagreement_before_dispatch() -> None:
    poller = _function_source("pollSummaryJobStatus")
    disagreement_guard = "data.job.state !== status"
    dispatch = "handleSummaryJobState("

    assert disagreement_guard in poller
    guard_start = poller.index(disagreement_guard)
    dispatch_start = poller.index(dispatch)
    guarded_block = poller[guard_start:dispatch_start]
    assert guard_start < dispatch_start
    assert "Unknown summary status. Try again." in guarded_block
    assert "return;" in guarded_block


def test_existing_profile_resumes_only_active_durable_jobs() -> None:
    resume = _function_source("resumeExistingSummaryJobStatus")
    loader = _function_source("loadVideoProfile")

    assert "resumeExistingSummaryJobStatus(videoId, statusData, regenBtn)" in loader
    assert "isSafeSummaryJob(job, videoHash)" in resume
    assert "startPollingStatus(videoHash, job.job_id)" in resume
    for status in ("authorizing", "queued", "running"):
        assert f'"{status}"' in resume
    for status in (
        "pending_confirmation",
        "succeeded",
        "failed",
        "interrupted",
        "expired",
        "not_started",
    ):
        assert f'"{status}"' in resume


def test_prepare_conflict_resumes_only_safe_active_job() -> None:
    conflict = _function_source("handlePrepareConflict")
    listener = _function_source("setupRegenListener")

    assert "prepareResp.status === 409" in listener
    assert "handlePrepareConflict(" in listener
    assert "isSafeSummaryJob(job, videoHash)" in conflict
    assert "startPollingStatus(videoHash, job.job_id)" in conflict
    for status in ("authorizing", "queued", "running"):
        assert f'"{status}"' in conflict
    assert 'job.state === "pending_confirmation"' in conflict
    assert "one-time confirmation token is no longer available" in conflict
