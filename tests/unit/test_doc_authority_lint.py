from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts.docs import doc_authority_lint as lint


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_metadata_check_exempts_skill_frontmatter(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "guide.md", "# Missing metadata\n")
    _write(
        tmp_path / "docs" / "skills" / "sample" / "SKILL.md",
        "---\nname: sample\ndescription: sample skill\n---\n\n# Sample\n",
    )

    findings = lint.check_metadata(tmp_path)

    assert [(item.code, item.path) for item in findings] == [
        ("DOC_METADATA", "docs/guide.md")
    ]


def test_metadata_check_rejects_invalid_duplicate_values_and_dates(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "bad.md",
        "<!-- DOC_BADGE: OPERATIONAL -->\n"
        "<!-- DOC_BADGE: bogus -->\n"
        "<!-- DOC_STATUS: DEFINITELY_NOT_A_REAL_STATE -->\n"
        "<!-- DOC_LAST_VERIFIED: 9999-99-99 -->\n\n# Bad\n",
    )

    findings = lint.check_metadata(tmp_path)

    assert [(item.code, item.path) for item in findings] == [
        ("DOC_METADATA", "docs/bad.md")
    ]
    assert "duplicate DOC_BADGE" in findings[0].detail
    assert "invalid DOC_BADGE=bogus" in findings[0].detail
    assert "invalid DOC_STATUS=DEFINITELY_NOT_A_REAL_STATE" in findings[0].detail
    assert "invalid DOC_LAST_VERIFIED" in findings[0].detail


def test_link_check_reports_only_missing_local_targets(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "<!-- DOC_BADGE: OPERATIONAL -->\n"
        "<!-- DOC_STATUS: ACTIVE -->\n"
        "<!-- DOC_LAST_VERIFIED: 2026-07-11 -->\n\n"
        "[present](docs/present.md#anchor)\n"
        "[missing](docs/missing.md)\n"
        "[web](https://example.com)\n"
        "[local anchor](#section)\n",
    )
    _write(
        tmp_path / "docs" / "present.md",
        "<!-- DOC_BADGE: OPERATIONAL -->\n"
        "<!-- DOC_STATUS: ACTIVE -->\n"
        "<!-- DOC_LAST_VERIFIED: 2026-07-11 -->\n\n# Present\n",
    )

    findings = lint.check_links(tmp_path)

    assert [(item.code, item.path, item.detail) for item in findings] == [
        ("BROKEN_LINK", "README.md", "docs/missing.md")
    ]


def test_link_check_ignores_fences_and_handles_parentheses(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "<!-- DOC_BADGE: OPERATIONAL -->\n"
        "<!-- DOC_STATUS: ACTIVE -->\n"
        "<!-- DOC_LAST_VERIFIED: 2026-07-11 -->\n\n"
        "```md\n[fake](docs/missing.md)\n```\n"
        "[real](docs/file_(v1).md)\n",
    )
    _write(
        tmp_path / "docs" / "file_(v1).md",
        "<!-- DOC_BADGE: OPERATIONAL -->\n"
        "<!-- DOC_STATUS: ACTIVE -->\n"
        "<!-- DOC_LAST_VERIFIED: 2026-07-11 -->\n",
    )

    assert lint.check_links(tmp_path) == []


def test_agent_index_is_deterministic_and_exact(tmp_path: Path) -> None:
    paths = [
        "docs/zeta.md",
        "api/main.py",
        "vendor/ignored.bin",
        "docs/archive/old.md",
        "tests/unit/test_sample.py",
    ]

    rendered = lint.render_agent_file_index(paths)

    assert "<!-- DOC_BADGE: OPERATIONAL -->" in rendered
    assert "<!-- DOC_STATUS: GENERATED_INDEX -->" in rendered
    assert "`/api/main.py`" in rendered
    assert "`/docs/zeta.md`" in rendered
    assert "`/tests/unit/test_sample.py`" in rendered
    assert "vendor/ignored.bin" not in rendered
    assert "docs/archive/old.md" not in rendered
    assert rendered.index("`/api/main.py`") < rendered.index("`/docs/zeta.md`")

    index_path = tmp_path / lint.AGENT_FILE_INDEX_PATH
    _write(index_path, rendered)
    assert lint.check_agent_file_index(tmp_path, tracked_paths=paths) == []

    index_path.write_text(rendered + "stale\n", encoding="utf-8")
    findings = lint.check_agent_file_index(tmp_path, tracked_paths=paths)
    assert [item.code for item in findings] == ["INDEX_DRIFT"]


def test_codebase_index_contains_exact_active_python_scope(tmp_path: Path) -> None:
    paths = [
        "api/main.py",
        "lib/memory.py",
        "tests/unit/test_memory.py",
        "docs/example.py",
        "vendor/library.py",
        "archive/retired.py",
        "README.md",
    ]

    rendered = lint.render_codebase_index(paths)

    assert "`api/main.py`" in rendered
    assert "`lib/memory.py`" in rendered
    assert "tests/unit/test_memory.py" not in rendered
    assert "docs/example.py" not in rendered
    assert "vendor/library.py" not in rendered
    assert "archive/retired.py" not in rendered

    path = tmp_path / lint.CODEBASE_INDEX_PATH
    _write(path, rendered)
    assert lint.check_codebase_index(tmp_path, tracked_paths=paths) == []

    path.write_text(rendered.replace("lib/memory.py", "lib/stale.py"), encoding="utf-8")
    findings = lint.check_codebase_index(tmp_path, tracked_paths=paths)
    assert [item.code for item in findings] == ["INDEX_DRIFT"]


def test_plan_and_project_contracts_are_bounded(tmp_path: Path) -> None:
    _write(tmp_path / "PLAN.md", "Read PLANS.md first.\n")
    _write(tmp_path / "PROJECT.md", "# Completed old mission\n")

    findings = lint.check_mission_contract(tmp_path)

    assert {item.code for item in findings} == {
        "PLAN_NAME_DRIFT",
        "PROJECT_MISSION_DRIFT",
    }

    _write(
        tmp_path / "PLAN.md",
        "<!-- DOC_BADGE: CANONICAL -->\n"
        "<!-- DOC_STATUS: AUTHORITATIVE -->\n"
        "<!-- DOC_LAST_VERIFIED: 2026-07-11 -->\n\n"
        "# Execution plan protocol\nUse PLAN.md.\n",
    )
    _write(
        tmp_path / "PROJECT.md",
        "<!-- DOC_BADGE: OPERATIONAL -->\n"
        "<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->\n"
        "<!-- DOC_LAST_VERIFIED: 2026-07-11 -->\n\n"
        "# Active bounded mission\n\nRoadmap item: R-10\n",
    )
    _write(
        tmp_path / "docs" / "releases" / "ROADMAP.md",
        "### R-10 — Align contracts\n\n- Status: OPEN\n",
    )
    assert lint.check_mission_contract(tmp_path) == []

    _write(
        tmp_path / "PROJECT.md",
        "<!-- DOC_BADGE: OPERATIONAL -->\n"
        "<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->\n"
        "<!-- DOC_LAST_VERIFIED: 2026-07-11 -->\n\n"
        "# Active bounded mission\n\nRoadmap item: R-10\nAlso R-13.\n",
    )
    findings = lint.check_mission_contract(tmp_path)
    assert [item.code for item in findings] == ["PROJECT_MISSION_DRIFT"]

    _write(
        tmp_path / "PROJECT.md",
        "<!-- DOC_BADGE: OPERATIONAL -->\n"
        "<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->\n"
        "<!-- DOC_LAST_VERIFIED: 2026-07-11 -->\n\n"
        "# Active bounded mission\n\nRoadmap item: R-10\n",
    )
    _write(
        tmp_path / "docs" / "releases" / "ROADMAP.md",
        "### R-10 — Align contracts\n\n- Status: VERIFIED\n",
    )
    findings = lint.check_mission_contract(tmp_path)
    assert [item.code for item in findings] == ["PROJECT_MISSION_DRIFT"]


def test_current_epoch_projection_parity(tmp_path: Path) -> None:
    state = {
        "schema_version": 1,
        "authoritative_epoch": {"epoch_id": "epoch_current"},
    }
    _write(
        tmp_path / "docs" / "agent" / "current_state.json",
        json.dumps(state),
    )
    _write(
        tmp_path / "docs" / "agent" / "CURRENT_STATE.md",
        "Authoritative epoch: `epoch_current`\n",
    )
    _write(
        tmp_path / "docs" / "GOODQ_RAG_CONTEXT_PACK.md",
        "Authoritative epoch: `epoch_current`\n",
    )
    _write(
        tmp_path / "docs" / "goodq4all_agent_status.md",
        "Current state authority: `docs/agent/current_state.json`.\n",
    )

    assert lint.check_epoch_parity(tmp_path) == []

    _write(
        tmp_path / "docs" / "GOODQ_RAG_CONTEXT_PACK.md",
        "Authoritative epoch: `epoch_stale`\n",
    )
    findings = lint.check_epoch_parity(tmp_path)
    assert [(item.code, item.path) for item in findings] == [
        ("EPOCH_DRIFT", "docs/GOODQ_RAG_CONTEXT_PACK.md")
    ]


def test_qdrant_storage_parity_detects_contract_mismatch(tmp_path: Path) -> None:
    _write(
        tmp_path / "configs" / "config.yaml",
        "paths:\n  qdrant_storage: ${GOODQ_DATA_ROOT}/qdrant_storage\n",
    )
    doc_names = (
        "MEMORY_STORAGE.md",
        "ARCHITECTURE_REFERENCE.md",
        "SYSTEM_ARCHITECTURE.md",
    )
    for name in doc_names:
        _write(
            tmp_path / "docs" / "architecture" / name,
            "`${GOODQ_DATA_ROOT}/GoodQ_Data/qdrant_storage`\n",
        )

    findings = lint.check_qdrant_storage_parity(tmp_path)

    assert [item.code for item in findings] == ["QDRANT_STORAGE_DRIFT"]

    for name in doc_names:
        _write(
            tmp_path / "docs" / "architecture" / name,
            "`${GOODQ_DATA_ROOT}/qdrant_storage`\n",
        )
    assert lint.check_qdrant_storage_parity(tmp_path) == []

    _write(
        tmp_path / "docs" / "architecture" / "MEMORY_STORAGE.md",
        "`${GOODQ_DATA_ROOT}/qdrant_storage` and "
        "`${GOODQ_DATA_ROOT}/GoodQ_Data/qdrant_storage`\n",
    )
    findings = lint.check_qdrant_storage_parity(tmp_path)
    assert [item.code for item in findings] == ["QDRANT_STORAGE_DRIFT"]


@pytest.mark.parametrize("tree_entry", ("└── qdrant_storage/", "└── qdrant_storage"))
def test_qdrant_storage_parity_rejects_nested_goodq_data_tree(
    tmp_path: Path,
    tree_entry: str,
) -> None:
    _write(
        tmp_path / "configs" / "config.yaml",
        "paths:\n  qdrant_storage: ${GOODQ_DATA_ROOT}/qdrant_storage\n",
    )
    relative_paths = [
        "docs/architecture/MEMORY_STORAGE.md",
        "docs/architecture/ARCHITECTURE_REFERENCE.md",
        "docs/architecture/SYSTEM_ARCHITECTURE.md",
    ]
    for relative in relative_paths:
        _write(
            tmp_path / relative,
            "`${GOODQ_DATA_ROOT}/qdrant_storage`\n",
        )
    _write(
        tmp_path / "docs" / "architecture" / "SYSTEM_ARCHITECTURE.md",
        "`${GOODQ_DATA_ROOT}/qdrant_storage`\n\n"
        "```text\n"
        "${GOODQ_DATA_ROOT}/GoodQ_Data/\n"
        f"{tree_entry}\n"
        "```\n",
    )

    findings = lint.check_qdrant_storage_parity(tmp_path)

    assert [item.code for item in findings] == ["QDRANT_STORAGE_DRIFT"]


@pytest.mark.parametrize(
    "correct_literal",
    ("${GOODQ_DATA_ROOT}/qdrant_storage", "${GOODQ_DATA_ROOT}/qdrant_storage/"),
)
def test_qdrant_storage_parity_allows_plain_correct_literal_in_same_fence(
    tmp_path: Path,
    correct_literal: str,
) -> None:
    _write(
        tmp_path / "configs" / "config.yaml",
        "paths:\n  qdrant_storage: ${GOODQ_DATA_ROOT}/qdrant_storage\n",
    )
    relative_paths = (
        "docs/architecture/MEMORY_STORAGE.md",
        "docs/architecture/ARCHITECTURE_REFERENCE.md",
        "docs/architecture/SYSTEM_ARCHITECTURE.md",
    )
    for relative in relative_paths:
        _write(
            tmp_path / relative,
            "```text\n"
            "${GOODQ_DATA_ROOT}/GoodQ_Data/\n"
            f"{correct_literal}\n"
            "```\n",
        )

    assert lint.check_qdrant_storage_parity(tmp_path) == []


_GOVERNED_MATERIALIZATION_LINES = (
    ("isolation policy", "`ingestion_isolation: true` governs isolated ingest."),
    (
        "scene manifest artifact evidence",
        "`scene_manifest.json` is per-video artifact evidence.",
    ),
    ("lifecycle ledger", "`ucf_ledger.db` is lifecycle and evidence authority."),
    (
        "staged UCF and Qdrant",
        "Isolated ingest stages UCF and Qdrant with exact "
        "`ucf_promotion_status = staged`.",
    ),
    (
        "explicit validation",
        "Explicit `validate_ucf_frames` validation precedes promotion.",
    ),
    (
        "human-gated exact promotion scope",
        "Human-gated exact `promote_ucf_to_memory` acts on `video_hash` plus "
        "`epoch_id`.",
    ),
    (
        "active SQLite materialization",
        "Promotion materializes active `memory.db` and `knowledge_graph.db`.",
    ),
    (
        "transactional transition and outbox",
        "The transition audit and durable Qdrant outbox enqueue share one "
        "SQLite transaction.",
    ),
    (
        "compensating active-view cleanup",
        "Active-view cleanup is compensating and recoverable.",
    ),
    ("no cross-store ACID", "There is no cross-store ACID guarantee."),
    (
        "post-commit Qdrant reconciliation",
        "Post-commit Qdrant status delivery and reconciliation are separate "
        "durable, recoverable obligations.",
    ),
    (
        "pending delivery meaning",
        "`promotion_committed_sync_pending` means the active commit succeeded "
        "while durable Qdrant delivery remains pending.",
    ),
    (
        "promoted-only default retrieval",
        "Default active retrieval is promoted-only.",
    ),
    (
        "raw audit distinction",
        "A raw audit may inspect non-active lifecycle states.",
    ),
)
_GOVERNED_MATERIALIZATION_PATHS = (
        "docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md",
        "docs/architecture/MEMORY_STORAGE.md",
        "docs/architecture/ARCHITECTURE_REFERENCE.md",
        "docs/architecture/SYSTEM_ARCHITECTURE.md",
)


def _governed_materialization_contract(*, omit: str | None = None) -> str:
    lines = [
        line
        for name, line in _GOVERNED_MATERIALIZATION_LINES
        if name != omit
    ]
    return "## Governed Materialization Contract\n\n" + "\n".join(lines) + "\n"


def _write_governed_materialization_docs(tmp_path: Path, text: str) -> None:
    for relative in _GOVERNED_MATERIALIZATION_PATHS:
        _write(tmp_path / relative, text)


def test_governed_materialization_contract_requires_named_section(
    tmp_path: Path,
) -> None:
    token_complete_body = "\n".join(
        line for _, line in _GOVERNED_MATERIALIZATION_LINES
    )
    _write_governed_materialization_docs(
        tmp_path,
        "## Unrelated Storage Notes\n\n" + token_complete_body + "\n",
    )

    findings = lint.check_governed_materialization_contract(tmp_path)

    assert [item.path for item in findings] == sorted(
        _GOVERNED_MATERIALIZATION_PATHS
    )
    assert all("section" in item.detail for item in findings)


def test_governed_materialization_contract_accepts_complete_section(
    tmp_path: Path,
) -> None:
    _write_governed_materialization_docs(
        tmp_path,
        _governed_materialization_contract(),
    )

    assert lint.check_governed_materialization_contract(tmp_path) == []


@pytest.mark.parametrize(
    "missing_semantic",
    [name for name, _ in _GOVERNED_MATERIALIZATION_LINES],
)
def test_governed_materialization_contract_requires_each_semantic_family(
    tmp_path: Path,
    missing_semantic: str,
) -> None:
    complete = _governed_materialization_contract()
    _write_governed_materialization_docs(tmp_path, complete)
    _write(
        tmp_path / "docs" / "architecture" / "SYSTEM_ARCHITECTURE.md",
        _governed_materialization_contract(omit=missing_semantic),
    )

    findings = lint.check_governed_materialization_contract(tmp_path)

    assert [(item.code, item.path, item.detail) for item in findings] == [
        (
            "MATERIALIZATION_CONTRACT_DRIFT",
            "docs/architecture/SYSTEM_ARCHITECTURE.md",
            f"missing governed materialization semantics: {missing_semantic}",
        )
    ]


@pytest.mark.parametrize(
    ("semantic_name", "mutated_line"),
    (
        ("lifecycle ledger", "`ucf_ledger.db` is present."),
        (
            "compensating active-view cleanup",
            "Active-view cleanup is compensating.",
        ),
        (
            "post-commit Qdrant reconciliation",
            "Post-commit Qdrant reconciliation is mentioned.",
        ),
        (
            "raw audit distinction",
            "A raw audit may not inspect non-active lifecycle states.",
        ),
    ),
)
def test_governed_materialization_contract_rejects_qualifier_mutation(
    tmp_path: Path,
    semantic_name: str,
    mutated_line: str,
) -> None:
    complete = _governed_materialization_contract()
    _write_governed_materialization_docs(tmp_path, complete)
    mutated_lines = [
        mutated_line if name == semantic_name else line
        for name, line in _GOVERNED_MATERIALIZATION_LINES
    ]
    _write(
        tmp_path / "docs" / "architecture" / "SYSTEM_ARCHITECTURE.md",
        "## Governed Materialization Contract\n\n"
        + "\n".join(mutated_lines)
        + "\n",
    )

    findings = lint.check_governed_materialization_contract(tmp_path)

    assert [(item.code, item.path, item.detail) for item in findings] == [
        (
            "MATERIALIZATION_CONTRACT_DRIFT",
            "docs/architecture/SYSTEM_ARCHITECTURE.md",
            f"missing governed materialization semantics: {semantic_name}",
        )
    ]


def test_current_state_projection_rejects_evidence_path_escape(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "agent" / "current_state.json",
        json.dumps({"generated_from": "../../outside.json"}),
    )
    _write(tmp_path.parent / "outside.json", "{}")

    findings = lint.check_current_state_projection(tmp_path)

    assert [item.code for item in findings] == ["CURRENT_STATE_DRIFT"]
    assert "docs/diagnostics/evidence" in findings[0].detail


def test_index_publication_rolls_back_both_files_on_replace_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first = tmp_path / "docs" / "first.md"
    second = tmp_path / "docs" / "second.md"
    _write(first, "old first\n")
    _write(second, "old second\n")
    real_replace = os.replace
    failed = False

    def fail_second_once(source, destination):
        nonlocal failed
        if Path(destination) == second and not failed:
            failed = True
            raise OSError("injected second replace failure")
        return real_replace(source, destination)

    monkeypatch.setattr(lint.os, "replace", fail_second_once)

    try:
        lint.publish_indexes({first: "new first\n", second: "new second\n"})
    except OSError as exc:
        assert "injected" in str(exc)
    else:
        raise AssertionError("expected publication failure")

    assert first.read_text(encoding="utf-8") == "old first\n"
    assert second.read_text(encoding="utf-8") == "old second\n"
    assert not list((tmp_path / "docs").glob("*.tmp"))
