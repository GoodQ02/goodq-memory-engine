from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "cli" / "ucf_promotion.py"
SUPERSEDED_RUNNERS = (
    REPO_ROOT / "scripts" / "ucf" / "validate_and_promote_epoch.py",
    REPO_ROOT / "scripts" / "run_lifecycle.py",
    REPO_ROOT / "scripts" / "ucf" / "promote_pilot.py",
    REPO_ROOT / "scripts" / "build_handoff.py",
)


def _load_module():
    assert MODULE_PATH.is_file(), "portable UCF promotion CLI has not been implemented"
    spec = importlib.util.spec_from_file_location("ucf_promotion_cli", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_epoch(tmp_path: Path, rows: list[tuple[str, str, str]]):
    epoch_id = "epoch_temp_promotion_proof"
    epoch_root = tmp_path / "GoodQ_Data" / "epochs" / epoch_id
    ledger_path = epoch_root / "ucf" / "ucf_ledger.db"
    ledger_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(ledger_path)
    conn.execute(
        "CREATE TABLE context_frames ("
        "video_hash TEXT NOT NULL, epoch_id TEXT NOT NULL, "
        "promotion_status TEXT NOT NULL)"
    )
    conn.executemany(
        "INSERT INTO context_frames(video_hash, epoch_id, promotion_status) "
        "VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    config = {
        "paths": {
            "db_dir": str(epoch_root),
            "db_path": str(epoch_root / "memory.db"),
            "knowledge_graph_db": str(epoch_root / "knowledge_graph.db"),
            "processing": str(epoch_root / "processing"),
        }
    }
    return epoch_id, epoch_root, ledger_path, config


def _make_real_epoch(tmp_path: Path):
    from scripts.ucf.ucf_ledger import UCFLedgerClient

    epoch_id = "epoch_temp_promotion_process_proof"
    video_hash = "video-process-proof"
    epoch_root = tmp_path / "GoodQ_Data" / "epochs" / epoch_id
    ledger_path = epoch_root / "ucf" / "ucf_ledger.db"
    ledger_path.parent.mkdir(parents=True)
    ledger = UCFLedgerClient(str(ledger_path))
    ledger.init_schema()
    ledger.register_media(
        video_hash=video_hash,
        file_path="process-proof.mp4",
        duration=1.0,
        fps=30.0,
        width=640,
        height=480,
    )
    ledger.log_frame(
        video_hash=video_hash,
        epoch_id=epoch_id,
        run_id="run-process-proof",
        t_start=0.0,
        t_end=1.0,
        modality="video",
        worker_name="image_embed_clip",
        model_tag="test/model",
        payload={"label": "process-proof"},
        promotion_status="validated",
    )
    ledger.close()
    config = {
        "paths": {
            "db_dir": str(epoch_root),
            "db_path": str(epoch_root / "memory.db"),
            "knowledge_graph_db": str(epoch_root / "knowledge_graph.db"),
            "processing": str(epoch_root / "processing"),
        },
        "agent": {"execution_mode": "in_process"},
    }
    config_path = tmp_path / "promotion-config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return epoch_id, video_hash, ledger_path, config_path


def _write_process_runner(tmp_path: Path) -> Path:
    runner = tmp_path / "run_promotion_process.py"
    runner.write_text(
        textwrap.dedent(
            """
            import json
            import os
            import sys
            import time
            from pathlib import Path

            from agents.mini_agent_client import MiniAgentClient
            from cli.ucf_promotion import main

            mode, config_path, epoch_id, video_hash, token, ready_path, release_path = sys.argv[1:]
            config = json.loads(Path(config_path).read_text(encoding="utf-8"))

            def client_factory(**kwargs):
                client = MiniAgentClient(**kwargs)
                ledger_path = Path(config["paths"]["db_dir"]) / "ucf" / "ucf_ledger.db"
                client._get_ucf_db_path = lambda: ledger_path
                sync_recovery_marker = os.environ.get(
                    "GOODQ_TEST_QDRANT_SYNC_RECOVERY_MARKER"
                )
                sync_available = (
                    not sync_recovery_marker
                    or Path(sync_recovery_marker).exists()
                )
                client._sync_ucf_status_to_qdrant = lambda *_args, **_kwargs: {
                    "status": "ok" if sync_available else "warning",
                    "points_attempted": 1,
                    "points_verified": 1 if sync_available else 0,
                    "collections_attempted": ["test"],
                    "failed_collections": [] if sync_available else ["test"],
                }
                client._sync_qdrant_by_scope = lambda **_kwargs: {
                    "status": "ok" if sync_available else "error",
                    "points_verified": 1 if sync_available else 0,
                    "failed_collections": [] if sync_available else ["test"],
                }
                client._execute_validate_ucf_epoch = lambda _args: {"success": True, "errors": []}
                failure_marker = os.environ.get("GOODQ_TEST_PROMOTION_FAILURE_MARKER")
                if failure_marker and not Path(failure_marker).exists():
                    def fail_first_promotion(_args):
                        Path(failure_marker).write_text("failed", encoding="utf-8")
                        raise RuntimeError("simulated promotion execution failure")

                    client._execute_promote_ucf_to_memory = fail_first_promotion
                if ready_path != "-":
                    original_validate_impl = client._validate_action_impl

                    def synchronized_validate_impl(*args, **kwargs):
                        result = original_validate_impl(*args, **kwargs)
                        if kwargs.get("confirmation_token") and result[1] == 0:
                            Path(ready_path).write_text("ready", encoding="utf-8")
                            deadline = time.monotonic() + 15.0
                            while not Path(release_path).exists():
                                if time.monotonic() >= deadline:
                                    raise TimeoutError("test release barrier timed out")
                                time.sleep(0.01)
                        return result

                    client._validate_action_impl = synchronized_validate_impl
                return client

            argv = [mode, "--epoch-id", epoch_id, "--video-hash", video_hash]
            if mode in {"execute", "reconcile-execute"} and token != "-":
                argv.extend(["--confirmation-token", token])
            raise SystemExit(main(argv, config=config, client_factory=client_factory))
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return runner


def _process_env(agent_home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["GOODQ_MINI_AGENT_HOME"] = str(agent_home)
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _run_process(
    runner: Path,
    mode: str,
    config_path: Path,
    epoch_id: str,
    video_hash: str,
    token: str,
    env: dict[str, str],
    *,
    ready_path: str = "-",
    release_path: str = "-",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(runner),
            mode,
            str(config_path),
            epoch_id,
            video_hash,
            token,
            ready_path,
            release_path,
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def _last_json_line(text: str) -> dict[str, object]:
    return json.loads(text.strip().splitlines()[-1])


def _approve_in_process(
    runner: Path,
    config_path: Path,
    epoch_id: str,
    video_hash: str,
    env: dict[str, str],
    mode: str = "approve",
) -> str:
    completed = _run_process(
        runner,
        mode,
        config_path,
        epoch_id,
        video_hash,
        "-",
        env,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)["confirmation_token"]


def _outbox_row(ledger_path: Path, epoch_id: str, video_hash: str):
    conn = sqlite3.connect(ledger_path)
    try:
        return conn.execute(
            "SELECT delivery_state, attempt_count, last_error "
            "FROM ucf_qdrant_sync_outbox "
            "WHERE epoch_id = ? AND video_hash = ? AND target_status = 'promoted'",
            (epoch_id, video_hash),
        ).fetchone()
    finally:
        conn.close()


class _FakeClient:
    def __init__(self, response, rc):
        self.response = response
        self.rc = rc
        self.calls = []

    def execute_tool(self, **kwargs):
        self.calls.append(kwargs)
        return self.response, self.rc


def test_inspect_uses_configured_temporary_epoch_and_is_read_only(tmp_path):
    mod = _load_module()
    epoch_id, _, ledger_path, config = _make_epoch(
        tmp_path,
        [
            ("video-ready", "epoch_temp_promotion_proof", "validated"),
            ("video-ready", "epoch_temp_promotion_proof", "validated"),
            ("video-blocked", "epoch_temp_promotion_proof", "staged"),
        ],
    )
    before = hashlib.sha256(ledger_path.read_bytes()).hexdigest()

    report = mod.inspect_epoch(config, epoch_id)

    after = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    scopes = {item["video_hash"]: item for item in report["scopes"]}
    assert before == after
    assert report["status"] == "ready"
    assert scopes["video-ready"]["counts"] == {"validated": 2}
    assert scopes["video-ready"]["promotable"] is True
    assert scopes["video-blocked"]["counts"] == {"staged": 1}
    assert scopes["video-blocked"]["promotable"] is False


def test_inspect_rejects_epoch_that_does_not_match_configured_runtime(tmp_path):
    mod = _load_module()
    epoch_id, _, _, config = _make_epoch(tmp_path, [])

    with pytest.raises(mod.PromotionCommandError, match="configured runtime epoch"):
        mod.inspect_epoch(config, f"{epoch_id}_other")


def test_approve_only_issues_token_for_exact_ready_scope(tmp_path):
    mod = _load_module()
    epoch_id, _, _, config = _make_epoch(
        tmp_path,
        [("video-ready", "epoch_temp_promotion_proof", "validated")],
    )
    fake = _FakeClient(
        {
            "status": "needs_confirmation",
            "result": {"confirmation_token": "token-scope-bound"},
        },
        3,
    )

    result = mod.approve_scope(
        config,
        epoch_id,
        "video-ready",
        client_factory=lambda **_: fake,
    )

    assert result["status"] == "approval_issued"
    assert result["confirmation_token"] == "token-scope-bound"
    assert fake.calls == [
        {
            "tool_name": "promote_ucf_to_memory",
            "tool_args": {"video_hash": "video-ready", "epoch_id": epoch_id},
            "confirm": False,
        }
    ]


def test_approve_refuses_staged_scope_before_requesting_token(tmp_path):
    mod = _load_module()
    epoch_id, _, _, config = _make_epoch(
        tmp_path,
        [("video-staged", "epoch_temp_promotion_proof", "staged")],
    )
    fake = _FakeClient({}, 0)

    with pytest.raises(mod.PromotionCommandError, match="not ready for promotion"):
        mod.approve_scope(
            config,
            epoch_id,
            "video-staged",
            client_factory=lambda **_: fake,
        )

    assert fake.calls == []


def test_execute_only_consumes_separately_supplied_token_for_exact_scope(tmp_path):
    mod = _load_module()
    epoch_id, _, _, config = _make_epoch(
        tmp_path,
        [("video-ready", "epoch_temp_promotion_proof", "validated")],
    )
    fake = _FakeClient(
        {
            "status": "success",
            "output": {"status": "promoted_complete", "promoted_count": 1},
        },
        0,
    )

    result = mod.execute_scope(
        config,
        epoch_id,
        "video-ready",
        "token-scope-bound",
        client_factory=lambda **_: fake,
    )

    assert result["status"] == "promotion_executed"
    assert fake.calls == [
        {
            "tool_name": "promote_ucf_to_memory",
            "tool_args": {"video_hash": "video-ready", "epoch_id": epoch_id},
            "confirm": True,
            "confirmation_token": "token-scope-bound",
        }
    ]


def test_approve_and_execute_work_across_separate_processes(tmp_path):
    epoch_id, video_hash, ledger_path, config_path = _make_real_epoch(tmp_path)
    runner = _write_process_runner(tmp_path)
    env = _process_env(tmp_path / "agent-home")
    token = _approve_in_process(runner, config_path, epoch_id, video_hash, env)

    executed = _run_process(
        runner,
        "execute",
        config_path,
        epoch_id,
        video_hash,
        token,
        env,
    )

    assert executed.returncode == 0, executed.stderr
    assert json.loads(executed.stdout)["status"] == "promotion_executed"
    conn = sqlite3.connect(ledger_path)
    status = conn.execute("SELECT promotion_status FROM context_frames").fetchone()[0]
    conn.close()
    assert status == "promoted"

    replay = _run_process(
        runner,
        "execute",
        config_path,
        epoch_id,
        video_hash,
        token,
        env,
    )
    assert replay.returncode != 0


def test_failed_execute_is_visible_and_recoverable_with_new_approval(tmp_path):
    epoch_id, video_hash, ledger_path, config_path = _make_real_epoch(tmp_path)
    runner = _write_process_runner(tmp_path)
    env = _process_env(tmp_path / "agent-home")
    failure_marker = tmp_path / "fail-first-promotion"
    env["GOODQ_TEST_PROMOTION_FAILURE_MARKER"] = str(failure_marker)
    first_token = _approve_in_process(runner, config_path, epoch_id, video_hash, env)

    failed = _run_process(
        runner,
        "execute",
        config_path,
        epoch_id,
        video_hash,
        first_token,
        env,
    )

    assert failed.returncode == 1
    assert _last_json_line(failed.stderr)["status"] == "error"
    conn = sqlite3.connect(ledger_path)
    status_after_failure = conn.execute(
        "SELECT promotion_status FROM context_frames"
    ).fetchone()[0]
    conn.close()
    assert status_after_failure == "validated"

    replay = _run_process(
        runner,
        "execute",
        config_path,
        epoch_id,
        video_hash,
        first_token,
        env,
    )
    assert replay.returncode == 1

    replacement_token = _approve_in_process(
        runner,
        config_path,
        epoch_id,
        video_hash,
        env,
    )
    assert replacement_token != first_token
    recovered = _run_process(
        runner,
        "execute",
        config_path,
        epoch_id,
        video_hash,
        replacement_token,
        env,
    )

    assert recovered.returncode == 0, recovered.stderr
    assert json.loads(recovered.stdout)["status"] == "promotion_executed"
    conn = sqlite3.connect(ledger_path)
    final_status = conn.execute(
        "SELECT promotion_status FROM context_frames"
    ).fetchone()[0]
    conn.close()
    assert final_status == "promoted"


def test_post_commit_sync_failure_requires_fresh_gated_reconciliation(tmp_path):
    epoch_id, video_hash, ledger_path, config_path = _make_real_epoch(tmp_path)
    runner = _write_process_runner(tmp_path)
    env = _process_env(tmp_path / "agent-home")
    recovery_marker = tmp_path / "qdrant-recovered"
    env["GOODQ_TEST_QDRANT_SYNC_RECOVERY_MARKER"] = str(recovery_marker)
    promotion_token = _approve_in_process(
        runner, config_path, epoch_id, video_hash, env
    )

    pending = _run_process(
        runner,
        "execute",
        config_path,
        epoch_id,
        video_hash,
        promotion_token,
        env,
    )

    assert pending.returncode == 1
    pending_result = _last_json_line(pending.stderr)
    assert pending_result["code"] == "promotion_committed_sync_pending"
    assert pending_result["result"]["status"] == "promotion_committed_sync_pending"
    conn = sqlite3.connect(ledger_path)
    local_status = conn.execute(
        "SELECT promotion_status FROM context_frames"
    ).fetchone()[0]
    conn.close()
    assert local_status == "promoted"
    assert _outbox_row(ledger_path, epoch_id, video_hash)[:2] == ("pending", 1)

    replay = _run_process(
        runner,
        "execute",
        config_path,
        epoch_id,
        video_hash,
        promotion_token,
        env,
    )
    assert replay.returncode != 0
    assert _outbox_row(ledger_path, epoch_id, video_hash)[:2] == ("pending", 1)

    recovery_marker.write_text("ready", encoding="utf-8")
    reconcile_token = _approve_in_process(
        runner,
        config_path,
        epoch_id,
        video_hash,
        env,
        mode="reconcile-approve",
    )
    assert reconcile_token != promotion_token
    reconciled = _run_process(
        runner,
        "reconcile-execute",
        config_path,
        epoch_id,
        video_hash,
        reconcile_token,
        env,
    )

    assert reconciled.returncode == 0, reconciled.stderr
    assert json.loads(reconciled.stdout)["status"] == "qdrant_sync_reconciled"
    assert _outbox_row(ledger_path, epoch_id, video_hash)[:2] == ("complete", 2)


def test_execute_accepts_confirmation_token_from_environment(tmp_path):
    epoch_id, video_hash, ledger_path, config_path = _make_real_epoch(tmp_path)
    runner = _write_process_runner(tmp_path)
    env = _process_env(tmp_path / "agent-home")
    token = _approve_in_process(runner, config_path, epoch_id, video_hash, env)
    env["GOODQ_CONFIRMATION_TOKEN"] = token

    executed = _run_process(
        runner,
        "execute",
        config_path,
        epoch_id,
        video_hash,
        "-",
        env,
    )

    assert executed.returncode == 0, executed.stderr
    assert json.loads(executed.stdout)["status"] == "promotion_executed"
    conn = sqlite3.connect(ledger_path)
    status = conn.execute("SELECT promotion_status FROM context_frames").fetchone()[0]
    conn.close()
    assert status == "promoted"


def test_cross_process_scope_mismatch_reports_stable_code(tmp_path):
    from scripts.ucf.ucf_ledger import UCFLedgerClient

    epoch_id, video_hash, ledger_path, config_path = _make_real_epoch(tmp_path)
    other_video_hash = "video-other-scope"
    ledger = UCFLedgerClient(str(ledger_path))
    ledger.register_media(
        video_hash=other_video_hash,
        file_path="other-scope.mp4",
        duration=1.0,
        fps=30.0,
        width=640,
        height=480,
    )
    ledger.log_frame(
        video_hash=other_video_hash,
        epoch_id=epoch_id,
        run_id="run-other-scope",
        t_start=0.0,
        t_end=1.0,
        modality="video",
        worker_name="image_embed_clip",
        model_tag="test/model",
        payload={"label": "other-scope"},
        promotion_status="validated",
    )
    ledger.close()
    runner = _write_process_runner(tmp_path)
    env = _process_env(tmp_path / "agent-home")
    token = _approve_in_process(runner, config_path, epoch_id, video_hash, env)

    mismatched = _run_process(
        runner,
        "execute",
        config_path,
        epoch_id,
        other_video_hash,
        token,
        env,
    )

    assert mismatched.returncode == 1
    assert _last_json_line(mismatched.stderr)["code"] == "token_scope_mismatch"
    conn = sqlite3.connect(ledger_path)
    statuses = {
        row[0]: row[1]
        for row in conn.execute(
            "SELECT video_hash, promotion_status FROM context_frames"
        ).fetchall()
    }
    conn.close()
    assert statuses == {
        video_hash: "validated",
        other_video_hash: "validated",
    }


def test_cross_process_expired_token_reports_stable_code(tmp_path):
    epoch_id, video_hash, ledger_path, config_path = _make_real_epoch(tmp_path)
    runner = _write_process_runner(tmp_path)
    agent_home = tmp_path / "agent-home"
    env = _process_env(agent_home)
    token = _approve_in_process(runner, config_path, epoch_id, video_hash, env)
    token_store_path = agent_home / "confirmation_tokens.json"
    token_store = json.loads(token_store_path.read_text(encoding="utf-8"))
    token_store[token]["timestamp"] = "2000-01-01T00:00:00Z"
    token_store_path.write_text(json.dumps(token_store), encoding="utf-8")

    expired = _run_process(
        runner,
        "execute",
        config_path,
        epoch_id,
        video_hash,
        token,
        env,
    )

    assert expired.returncode == 1
    assert _last_json_line(expired.stderr)["code"] == "token_expired"
    conn = sqlite3.connect(ledger_path)
    status = conn.execute("SELECT promotion_status FROM context_frames").fetchone()[0]
    conn.close()
    assert status == "validated"


def test_concurrent_execute_processes_claim_confirmation_token_once(tmp_path):
    epoch_id, video_hash, ledger_path, config_path = _make_real_epoch(tmp_path)
    runner = _write_process_runner(tmp_path)
    env = _process_env(tmp_path / "agent-home")
    token = _approve_in_process(runner, config_path, epoch_id, video_hash, env)
    release_path = tmp_path / "release"
    ready_paths = [tmp_path / "ready-one", tmp_path / "ready-two"]
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                str(runner),
                "execute",
                str(config_path),
                epoch_id,
                video_hash,
                token,
                str(ready_path),
                str(release_path),
            ],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for ready_path in ready_paths
    ]
    try:
        deadline = time.monotonic() + 20.0
        while not all(path.exists() for path in ready_paths):
            if time.monotonic() >= deadline:
                raise TimeoutError("execute processes did not reach the validation barrier")
            time.sleep(0.02)
        assert all(path.exists() for path in ready_paths)
        release_path.write_text("release", encoding="utf-8")
        results = [process.communicate(timeout=30) for process in processes]
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)

    return_codes = sorted(process.returncode for process in processes)
    assert return_codes == [0, 1], results
    conn = sqlite3.connect(ledger_path)
    status = conn.execute("SELECT promotion_status FROM context_frames").fetchone()[0]
    conn.close()
    assert status == "promoted"


def test_portable_cli_has_no_fixed_drive_root_or_self_confirmation_loop():
    _load_module()
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "L:/" not in source
    assert "L:\\" not in source
    assert "C:/" not in source
    assert "C:\\" not in source
    assert "EPOCH_ID =" not in source
    assert "confirmation_token=token" not in source


def test_superseded_self_confirming_promotion_workflow_is_removed():
    remaining = [path.relative_to(REPO_ROOT).as_posix() for path in SUPERSEDED_RUNNERS if path.exists()]

    assert remaining == []


def test_active_scripts_have_no_self_confirming_promotion_runner():
    offenders = []
    for path in (REPO_ROOT / "scripts").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        self_confirms_promotion = all(
            marker in source
            for marker in (
                "MiniAgentClient",
                "promote_ucf_to_memory",
                "confirmation_token",
                "confirm=False",
                "confirm=True",
            )
        )
        if self_confirms_promotion:
            offenders.append(path.relative_to(REPO_ROOT).as_posix())

    assert offenders == []
