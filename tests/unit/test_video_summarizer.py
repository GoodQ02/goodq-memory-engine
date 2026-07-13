from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from steps.video_summarizer import step as video_summarizer


TARGET_HASH = "target-video-hash"
OTHER_HASH = "other-video-hash"
TARGET_SCENE_ID = "target-scene-1"
OTHER_SCENE_ID = "other-scene-1"


class StubResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "memory.db"
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE scenes (
                id TEXT PRIMARY KEY,
                video_hash TEXT,
                start REAL,
                end REAL,
                meta TEXT,
                created_at TEXT
            );
            CREATE TABLE summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary_type TEXT NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO scenes (id, video_hash, start, end, meta, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    TARGET_SCENE_ID,
                    TARGET_HASH,
                    0.0,
                    12.5,
                    json.dumps({"video_path": "target.mp4"}),
                    "2026-07-12 00:00:00",
                ),
                (
                    OTHER_SCENE_ID,
                    OTHER_HASH,
                    0.0,
                    99.0,
                    json.dumps({"video_path": "other.mp4"}),
                    "2026-07-12 00:00:00",
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return path


def _cfg(db_path: Path, *, isolation: bool = False) -> dict:
    return {
        "paths": {"db_path": str(db_path)},
        "ingestion_isolation": isolation,
        "llm": {
            "api_url": "http://127.0.0.1:1234/v1/chat/completions",
            "model": "test-model",
            "timeout": 1,
            "features": {"video_summarization": True},
        },
    }


def _insert_target_scene(db_path: Path, scene_id: str, end: float) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO scenes (id, video_hash, start, end, meta, created_at)
            VALUES (?, ?, 0, ?, ?, '2026-07-12 00:00:00')
            """,
            (scene_id, TARGET_HASH, end, json.dumps({"video_path": "target.mp4"})),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_summary(
    db_path: Path,
    summary_id: int,
    content: str | dict,
    *,
    category: str = "scene_summary",
) -> None:
    encoded = content if isinstance(content, str) else json.dumps(content)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO summaries (id, summary_type, category, content, created_at)
            VALUES (?, 'scene', ?, ?, ?)
            """,
            (summary_id, category, encoded, f"2026-07-12 00:00:{summary_id:02d}"),
        )
        conn.commit()
    finally:
        conn.close()


def _ok_response(text: str) -> StubResponse:
    return StubResponse(
        200,
        {"choices": [{"message": {"content": text}}]},
    )


def _persisted_video_payload(db_path: Path) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT content FROM summaries
            WHERE category='video_summary'
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    return json.loads(row[0])


def test_target_prompt_and_provenance_share_exact_scene_summary_selection(
    db_path: Path,
) -> None:
    _insert_summary(
        db_path,
        11,
        {"scene_id": TARGET_SCENE_ID, "summary": "TARGET SUMMARY TEXT"},
    )
    _insert_summary(
        db_path,
        22,
        {"scene_id": OTHER_SCENE_ID, "summary": "CROSS VIDEO TEXT"},
    )
    _insert_summary(db_path, 33, "{malformed-json")
    _insert_summary(db_path, 44, {"summary": "MISSING SCENE ID TEXT"})
    _insert_summary(
        db_path,
        55,
        {"scene_id": TARGET_SCENE_ID, "summary": ""},
    )

    with patch.object(
        video_summarizer.requests,
        "post",
        return_value=_ok_response("MODEL SUMMARY"),
    ) as post:
        result = video_summarizer.run_step(_cfg(db_path), TARGET_HASH)

    prompt = post.call_args.kwargs["json"]["messages"][1]["content"]
    assert "TARGET SUMMARY TEXT" in prompt
    assert "CROSS VIDEO TEXT" not in prompt
    assert "MISSING SCENE ID TEXT" not in prompt
    assert result["method"] == "llm"
    assert result["provenance"]["source_artifact_versions"] == [
        {
            "summary_id": 11,
            "scene_id": TARGET_SCENE_ID,
            "created_at": "2026-07-12 00:00:11",
        }
    ]

    persisted = _persisted_video_payload(db_path)
    assert persisted["method"] == "llm"
    assert (
        persisted["provenance"]["source_artifact_versions"]
        == result["provenance"]["source_artifact_versions"]
    )


def test_provenance_contains_only_records_included_by_prompt_cap(
    db_path: Path,
) -> None:
    for index in range(1, 22):
        scene_id = f"target-scene-{index}"
        if index > 1:
            _insert_target_scene(db_path, scene_id, float(index))
        _insert_summary(
            db_path,
            index,
            {
                "scene_id": scene_id,
                "summary": f"TARGET_MARKER_{index:02d}",
            },
        )

    with patch.object(
        video_summarizer.requests,
        "post",
        return_value=_ok_response("MODEL SUMMARY"),
    ) as post:
        result = video_summarizer.run_step(_cfg(db_path), TARGET_HASH)

    prompt = post.call_args.kwargs["json"]["messages"][1]["content"]
    assert "TARGET_MARKER_20" in prompt
    assert "TARGET_MARKER_21" not in prompt
    assert [
        source["summary_id"]
        for source in result["provenance"]["source_artifact_versions"]
    ] == list(range(1, 21))
    persisted = _persisted_video_payload(db_path)
    assert (
        persisted["provenance"]["source_artifact_versions"]
        == result["provenance"]["source_artifact_versions"]
    )


def test_llm_helper_filters_supplied_records_by_canonical_target_scene_ids(
    db_path: Path,
) -> None:
    supplied_records = [
        {
            "summary_id": 1,
            "scene_id": TARGET_SCENE_ID,
            "summary": "SUPPLIED TARGET TEXT",
            "created_at": "2026-07-12 00:00:01",
        },
        {
            "summary_id": 2,
            "scene_id": OTHER_SCENE_ID,
            "summary": "SUPPLIED CROSS VIDEO TEXT",
            "created_at": "2026-07-12 00:00:02",
        },
        {
            "summary_id": 3,
            "summary": "SUPPLIED MISSING SCENE ID TEXT",
            "created_at": "2026-07-12 00:00:03",
        },
    ]

    with patch.object(
        video_summarizer.requests,
        "post",
        return_value=_ok_response("MODEL SUMMARY"),
    ) as post:
        summary = video_summarizer.generate_video_summary_llm(
            _cfg(db_path),
            TARGET_HASH,
            str(db_path),
            supplied_records,
        )

    assert summary == "MODEL SUMMARY"
    prompt = post.call_args.kwargs["json"]["messages"][1]["content"]
    assert "SUPPLIED TARGET TEXT" in prompt
    assert "SUPPLIED CROSS VIDEO TEXT" not in prompt
    assert "SUPPLIED MISSING SCENE ID TEXT" not in prompt


def test_no_target_summary_uses_template_without_borrowing_cross_video_text(
    db_path: Path,
) -> None:
    _insert_summary(
        db_path,
        21,
        {"scene_id": OTHER_SCENE_ID, "summary": "CROSS VIDEO TEXT"},
    )
    _insert_summary(db_path, 22, {"summary": "MISSING SCENE ID TEXT"})

    with patch.object(
        video_summarizer.requests,
        "post",
        return_value=_ok_response("BORROWED MODEL SUMMARY"),
    ) as post:
        result = video_summarizer.run_step(_cfg(db_path), TARGET_HASH)

    post.assert_not_called()
    assert result["method"] == "template"
    assert "target.mp4" in result["summary"]
    assert "CROSS VIDEO TEXT" not in result["summary"]
    assert result["provenance"]["source_artifact_versions"] == []
    assert _persisted_video_payload(db_path)["method"] == "template"


def test_whitespace_only_target_summary_uses_template_without_http(
    db_path: Path,
) -> None:
    _insert_summary(
        db_path,
        11,
        {"scene_id": TARGET_SCENE_ID, "summary": "  \t\n  "},
    )

    with patch.object(
        video_summarizer.requests,
        "post",
        return_value=_ok_response("MODEL SUMMARY"),
    ) as post:
        result = video_summarizer.run_step(_cfg(db_path), TARGET_HASH)

    post.assert_not_called()
    assert result["method"] == "template"
    assert result["provenance"]["source_artifact_versions"] == []
    assert _persisted_video_payload(db_path)["method"] == "template"


@pytest.mark.parametrize(
    "failure_kind",
    ["timeout", "non_200", "empty", "exception"],
)
def test_llm_failures_return_and_persist_template_method(
    db_path: Path,
    failure_kind: str,
) -> None:
    _insert_summary(
        db_path,
        11,
        {"scene_id": TARGET_SCENE_ID, "summary": "TARGET SUMMARY TEXT"},
    )

    if failure_kind == "timeout":
        post_kwargs = {"side_effect": video_summarizer.requests.Timeout("slow")}
    elif failure_kind == "non_200":
        post_kwargs = {"return_value": StubResponse(503, {"error": "unavailable"})}
    elif failure_kind == "empty":
        post_kwargs = {"return_value": _ok_response("   ")}
    else:
        post_kwargs = {"side_effect": RuntimeError("transport failed")}

    with patch.object(video_summarizer.requests, "post", **post_kwargs):
        result = video_summarizer.run_step(_cfg(db_path), TARGET_HASH)

    assert result["success"] is True
    assert result["method"] == "template"
    assert _persisted_video_payload(db_path)["method"] == "template"


def test_isolation_fallback_reports_template_without_persisting(db_path: Path) -> None:
    _insert_summary(
        db_path,
        11,
        {"scene_id": TARGET_SCENE_ID, "summary": "TARGET SUMMARY TEXT"},
    )

    with patch.object(
        video_summarizer.requests,
        "post",
        side_effect=video_summarizer.requests.Timeout("slow"),
    ):
        result = video_summarizer.run_step(
            _cfg(db_path, isolation=True),
            TARGET_HASH,
        )

    assert result["success"] is True
    assert result["method"] == "template"
    conn = sqlite3.connect(db_path)
    try:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM summaries WHERE category='video_summary'"
            ).fetchone()[0]
            == 0
        )
    finally:
        conn.close()


def test_persistence_exception_still_returns_failure(db_path: Path) -> None:
    _insert_summary(
        db_path,
        11,
        {"scene_id": TARGET_SCENE_ID, "summary": "TARGET SUMMARY TEXT"},
    )
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TRIGGER reject_video_summary
            BEFORE INSERT ON summaries
            WHEN NEW.category='video_summary'
            BEGIN
                SELECT RAISE(ABORT, 'blocked video summary write');
            END
            """
        )
        conn.commit()
    finally:
        conn.close()

    with patch.object(
        video_summarizer.requests,
        "post",
        return_value=_ok_response("MODEL SUMMARY"),
    ):
        result = video_summarizer.run_step(_cfg(db_path), TARGET_HASH)

    assert result["success"] is False
    assert result["video_hash"] == TARGET_HASH
    assert "blocked video summary write" in result["error"]
