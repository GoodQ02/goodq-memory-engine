"""Regression and production-caller smoke tests for Area 6 (Operator/UI) audit repairs.

Covers OU-01 through OU-09 plus cross-slice hooks RS-01, VS-01, and RS-07 using
isolated temporary directories and TestClient(api.main.app) without live ports or media.
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import sqlite3
import subprocess
import time
import types
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import api.main as api_main
import api.server as api_server
import cli.watchdog as watchdog_mod
from api.library import EPOCH_HEADER, SavedLibraryMiddleware
from api.routes import runtime as runtime_routes
from api.routes import scenes as scenes_routes
from api.routes import summary as summary_routes
from api.routes import timeline as timeline_routes
from api.utils.ingest_requests import SUPPORTED_DOCUMENT as API_SUPPORTED_DOCUMENT
from api.utils.ingest_requests import is_supported_ingest_path
from api.utils.loaders import DataLoader
from cli.watchdog import SUPPORTED_DOCUMENT as WATCHDOG_SUPPORTED_DOCUMENT
from cli.watchdog import FileState, WatchdogProcessor
from scripts.docs import doc_drift_lint
from tests.unit.test_audio_engine_consumers import decoded, recording
from tests.unit.test_watchdog_processed_prefix_idempotent import _watchdog_cfg
from wsl2_audio.scene_consumers import publish_scene_audio


REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_watchdog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> WatchdogProcessor:
    monkeypatch.setattr(watchdog_mod, "CONTROL_AGENT_AVAILABLE", False)
    cfg = _watchdog_cfg(tmp_path)
    return WatchdogProcessor(cfg)


def test_ou01_watchdog_cleanup_preserves_retained_processing_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    processor = _make_watchdog(tmp_path, monkeypatch)
    assert processor.staging_dir == processor.processing_dir / ".watchdog_staging"

    stale_ts = time.time() - (48 * 3600)
    retained_dirs = []
    manifest_map = {
        "video_1111aaaa": "temporal_index.json",
        "audio_2222bbbb": "audio_result.json",
        "image_3333cccc": "image_ingest_result.json",
        "doc_4444dddd": "document_ingest_result.json",
    }
    for folder_name, manifest_name in manifest_map.items():
        retained = processor.processing_dir / folder_name
        retained.mkdir(parents=True, exist_ok=True)
        manifest = retained / manifest_name
        manifest.write_text(json.dumps({"video_id": folder_name, "segments": []}), encoding="utf-8")
        os.utime(manifest, (stale_ts, stale_ts))
        os.utime(retained, (stale_ts, stale_ts))
        retained_dirs.append((retained, manifest_name))

    # Interrupted mid-run progressive ingestion checkpoints & keyframes (without temporal_index/scene_manifest)
    progressive_dir = processor.processing_dir / "video_001"
    progressive_dir.mkdir(parents=True, exist_ok=True)
    progressive_state = progressive_dir / "progressive_ingestion_state.json"
    progressive_state.write_text(json.dumps({"completed_windows": [0]}), encoding="utf-8")
    os.utime(progressive_state, (stale_ts, stale_ts))
    os.utime(progressive_dir, (stale_ts, stale_ts))

    root_video_keyframes = processor.processing_dir / "video" / "keyframes"
    root_video_keyframes.mkdir(parents=True, exist_ok=True)
    kf_file = root_video_keyframes / "kf_0001.jpg"
    kf_file.write_bytes(b"keyframe")
    os.utime(kf_file, (stale_ts, stale_ts))

    video_frames_dir = processor.processing_dir / "video_002" / "video" / "frames"
    video_frames_dir.mkdir(parents=True, exist_ok=True)
    frame_file = video_frames_dir / "frame_0001.jpg"
    frame_file.write_bytes(b"frame")
    os.utime(frame_file, (stale_ts, stale_ts))

    # Unmanifested partial folder in processing/ and items in .watchdog_staging/ must be cleaned
    aborted_dir = processor.processing_dir / "video_aborted_999"
    aborted_dir.mkdir(parents=True, exist_ok=True)
    (aborted_dir / "frame.jpg").write_bytes(b"orphan")

    stale_staged_file = processor.staging_dir / "copy_old.mp4"
    stale_staged_file.write_bytes(b"stale")

    stale_staged_dir = processor.staging_dir / "video_1111aaaa"
    stale_staged_dir.mkdir(parents=True, exist_ok=True)
    (stale_staged_dir / "partial.bin").write_bytes(b"partial")

    stale_root_tmp = processor.processing_dir / "orphan_write.tmp"
    stale_root_tmp.write_bytes(b"tmp")

    processor.cleanup_stale_processing_files()

    for retained, manifest_name in retained_dirs:
        assert retained.is_dir(), f"Retained directory deleted: {retained}"
        assert (retained / manifest_name).is_file()

    assert progressive_state.is_file()
    assert kf_file.is_file()
    assert frame_file.is_file()

    assert not aborted_dir.exists()
    assert not stale_staged_file.exists()
    assert not stale_staged_dir.exists()
    assert not stale_root_tmp.exists()


def test_ou02_audio_evidence_cold_start_and_exception_scoping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "cold_root"
    processing_root = data_root / "processing"
    video_id = "video_abc12345"
    video_dir = processing_root / video_id
    video_dir.mkdir(parents=True, exist_ok=True)

    evidence = recording()
    pcm = decoded(tmp_path, evidence)
    projection = publish_scene_audio(
        evidence, [{"scene_id": "0", "start": 0.0, "end": 2.0}], pcm, processing_root
    )["0"]

    (video_dir / "temporal_index.json").write_text(
        json.dumps(
            {
                "video_id": video_id,
                "duration": 2.0,
                "total_scenes": 1,
                "segments": [
                    {
                        "scene_id": "0",
                        "start": 0.0,
                        "end": 2.0,
                        "transcript": "hello world",
                        "audio_evidence": projection,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    loader = DataLoader(data_root=str(data_root), processing_root=str(processing_root))
    loader._ucf_scope = None
    monkeypatch.setattr(scenes_routes, "_config", None)
    monkeypatch.setattr(scenes_routes, "_data_loader", loader)
    monkeypatch.setattr(scenes_routes, "load_configs", lambda _overrides=None: {"paths": {}})

    view = scenes_routes._build_scene_response(
        video_id, {"scene_id": "0", "start": 0.0, "end": 2.0, "audio_evidence": projection}
    ).model_dump()["audio_evidence"]
    url = view["reviews"][0]["url"]

    client = TestClient(api_main.app, raise_server_exceptions=False)
    ok_resp = client.get(url)
    assert ok_resp.status_code == 200
    assert ok_resp.content[:4] == b"RIFF"

    # Corrupt retained WAV bytes -> ValueError integrity mismatch maps to 409
    rel_clip = projection["voice_reviews"][0]["relative_path"]
    (processing_root / rel_clip).write_bytes(b"corrupted")
    mismatch_resp = client.get(url)
    assert mismatch_resp.status_code == 409

    # Internal TypeError must NOT be swallowed as 409
    def _broken_review_media(*_args, **_kwargs):
        raise TypeError("unexpected internal type bug")

    monkeypatch.setattr(scenes_routes, "review_media", _broken_review_media)
    bug_resp = client.get(url)
    assert bug_resp.status_code == 500


def test_ou03_saved_library_routes_summary_video_and_guards_collection_epoch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    remote_app = FastAPI()

    @remote_app.get("/api/summary/video/{video_id}")
    async def remote_summary(video_id: str):
        return {"video_id": video_id, "summary": "Remote Movie 2 summary", "source": "two"}

    @remote_app.get("/api/summary/video/{video_id}/status")
    async def remote_status(video_id: str):
        return {"video_id": video_id, "status": "not_started"}

    @remote_app.post("/api/summary/video/{video_id}/generate")
    async def remote_generate(video_id: str):
        return {"video_id": video_id, "proxied": True}

    remote_with_epoch = SavedLibraryMiddleware(
        remote_app,
        cfg={"epoch_id": "epoch_two", "paths": {"db_path": "unused"}, "ui": {}},
        routes=lambda: remote_app.routes,
    )

    local_app = FastAPI()

    @local_app.get("/api/summary/video/{video_id}")
    async def local_summary(video_id: str):
        return {"video_id": video_id, "summary": "Local Movie 1 summary", "source": "local"}

    @local_app.get("/api/summary/video/{video_id}/status")
    async def local_status(video_id: str):
        return {"video_id": video_id, "status": "succeeded"}

    @local_app.post("/api/summary/video/{video_id}/generate")
    async def local_generate(video_id: str):
        return {"video_id": video_id, "proxied": False}

    cfg = {
        "epoch_id": "epoch_one",
        "paths": {"db_path": str(tmp_path / "epoch_one" / "memory.db"), "data_root": str(tmp_path)},
        "ui": {
            "library_port": 30000,
            "library_sources": [
                {
                    "id": "two",
                    "name": "Movie two",
                    "api_origin": "http://127.0.0.1:30041",
                    "epoch_id": "epoch_two",
                    "video_ids": ["video_two_hash"],
                }
            ],
        },
    }
    combined_app = SavedLibraryMiddleware(local_app, cfg=cfg, routes=lambda: local_app.routes)

    real_async_client = httpx.AsyncClient

    def _mock_async_client(**kwargs):
        kwargs.pop("follow_redirects", None)
        kwargs.pop("trust_env", None)
        return real_async_client(transport=httpx.ASGITransport(app=remote_with_epoch), **kwargs)

    monkeypatch.setattr("api.library.httpx.AsyncClient", _mock_async_client)

    with TestClient(combined_app, base_url="http://127.0.0.1:30000") as client:
        resp_two = client.get("/api/summary/video/video_two_hash")
        assert resp_two.status_code == 200
        assert resp_two.json()["source"] == "two"
        assert resp_two.headers.get(EPOCH_HEADER) == "epoch_two"

        resp_status = client.get("/api/summary/video/video_two_hash/status")
        assert resp_status.status_code == 200
        assert resp_status.json()["status"] == "not_started"

        resp_gen = client.post("/api/summary/video/video_two_hash/generate")
        assert resp_gen.status_code == 200
        assert resp_gen.json()["proxied"] is True

        resp_mismatch = client.get("/api/summary/video/video_two_hash?library_source=local")
        assert resp_mismatch.status_code == 409

    # Validate collection scene_refs reader-epoch ownership guard
    mem_dir = tmp_path / "epoch_one"
    mem_dir.mkdir(parents=True, exist_ok=True)
    mem_db = mem_dir / "memory.db"
    with sqlite3.connect(str(mem_db)) as conn:
        conn.execute("CREATE TABLE scenes (scene_id TEXT, video_id TEXT)")
        conn.execute("INSERT INTO scenes VALUES ('0', 'video_one_hash')")
        conn.commit()

    monkeypatch.setattr(summary_routes, "_data_loader", None)
    summary_routes._validate_collection_scene_refs_belong_to_reader(
        cfg, [{"video_id": "video_one_hash", "scene_id": "0"}]
    )
    with pytest.raises(HTTPException) as exc_foreign:
        summary_routes._validate_collection_scene_refs_belong_to_reader(
            cfg, [{"video_id": "video_two_hash", "scene_id": "0"}]
        )
    assert exc_foreign.value.status_code == 409
    assert "Movie two" in exc_foreign.value.detail

    with pytest.raises(HTTPException) as exc_unknown:
        summary_routes._validate_collection_scene_refs_belong_to_reader(
            cfg, [{"video_id": "video_unowned_hash", "scene_id": "0"}]
        )
    assert exc_unknown.value.status_code == 409


def test_ou04_library_context_deduplication_isolation_and_console_wiring() -> None:
    lib_js = (REPO_ROOT / "ui" / "retro_console_v1" / "static" / "js" / "library-context.js").read_text(
        encoding="utf-8"
    )
    harness = r"""
const fs = require("fs");
const input = JSON.parse(fs.readFileSync(0, "utf8"));

function runScenario(search, videos, unavailableHeader) {
  let assignedUrl = null;
  const elementsById = new Map();
  class Node {
    constructor(tag) {
      this.tag = tag;
      this.children = [];
      this.options = [];
      this.hidden = false;
      this.disabled = false;
      this.selected = false;
      this.value = "";
      this.textContent = "";
      this.style = {};
      this.attrs = {};
      this.listeners = {};
    }
    set innerHTML(v) { this.children = []; this.options = []; }
    appendChild(child) {
      this.children.push(child);
      if (child.tag === "option") {
        this.options.push(child);
        if (child.selected || this.options.length === 1) this.value = child.value;
      }
      if (child.id) elementsById.set(child.id, child);
    }
    prepend(child) {
      this.children.unshift(child);
      if (child.id) elementsById.set(child.id, child);
    }
    setAttribute(k, v) { this.attrs[k] = v; }
    getAttribute(k) { return this.attrs[k] || ""; }
    hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k); }
    addEventListener(k, fn) { this.listeners[k] = fn; }
  }
  const switcher = new Node("select");
  switcher.id = "collection-source-select";
  Object.defineProperty(switcher, "selectedIndex", {
    get() { return Math.max(0, this.options.findIndex(o => o.value === this.value)); }
  });
  const pill = new Node("label");
  pill.id = "collection-switcher-pill";
  pill.hidden = true;
  const main = new Node("div");
  elementsById.set("collection-source-select", switcher);
  elementsById.set("collection-switcher-pill", pill);

  const window = {
    location: {
      origin: "http://127.0.0.1:30000",
      href: "http://127.0.0.1:30000/ui/summary_console/" + search,
      search: search,
      pathname: "/ui/summary_console/",
      hash: "",
      assign(u) { assignedUrl = u; }
    }
  };
  const document = {
    body: main,
    getElementById(id) { return elementsById.get(id) || null; },
    createElement(tag) { return new Node(tag); },
    querySelector(sel) { return sel === ".crt-screen" ? main : null; },
    querySelectorAll() { return []; }
  };
  const fetch = async () => ({
    ok: true,
    headers: { get(k) { return k === "x-goodq-unavailable-sources" ? unavailableHeader : null; } },
    json: async () => videos
  });
  const fn = new Function("window", "document", "fetch", input.code);
  fn(window, document, fetch);
  return new Promise(resolve => setTimeout(() => {
    const opts = switcher.options.map(o => ({ value: o.value, text: o.textContent, disabled: o.disabled, selected: o.selected }));
    switcher.value = "local";
    if (switcher.listeners.change) switcher.listeners.change();
    const localNav = assignedUrl;
    switcher.value = "";
    if (switcher.listeners.change) switcher.listeners.change();
    const allNav = assignedUrl;
    const notice = elementsById.get("library-availability");
    resolve({
      pillHidden: pill.hidden,
      opts,
      localNav,
      allNav,
      noticeText: notice ? notice.textContent : "",
      scopedDashboard: window.GoodQLibrary.url("/api/summary/dashboard")
    });
  }, 20));
}

(async () => {
  const multi = await runScenario(
    "",
    [
      { video_id: "v1", library_source: "local", title: "Clip One" },
      { video_id: "v2", library_source: "local", title: "Clip Two" },
      { video_id: "v3", library_source: "two", title: "Movie Two" }
    ],
    "[]"
  );
  const emptyWithOffline = await runScenario(
    "?library_source=local",
    [],
    JSON.stringify([{ id: "three", name: "Movie three" }])
  );
  process.stdout.write(JSON.stringify({ multi, emptyWithOffline }));
})();
"""
    proc = subprocess.run(
        ["node", "-e", harness],
        input=json.dumps({"code": lib_js}),
        text=True,
        capture_output=True,
        timeout=15,
        check=True,
    )
    out = json.loads(proc.stdout)
    multi_opts = out["multi"]["opts"]
    assert [o["value"] for o in multi_opts] == ["", "local", "two"]
    assert multi_opts[1]["text"] == "Clip One (+1 more)"
    assert out["multi"]["localNav"] == "/ui/summary_console/?library_source=local"
    assert out["multi"]["allNav"] == "/ui/summary_console/"

    offline = out["emptyWithOffline"]
    assert offline["pillHidden"] is False
    assert any(o["value"] == "three" and o["disabled"] is True for o in offline["opts"])
    assert "Movie three unavailable" in offline["noticeText"]
    assert offline["scopedDashboard"] == "/api/summary/dashboard?library_source=local"

    summary_html = (REPO_ROOT / "ui" / "summary_console" / "index.html").read_text(encoding="utf-8")
    operator_html = (REPO_ROOT / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    operator_js = (REPO_ROOT / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "/ui/retro_console_v1/static/js/library-context.js" in summary_html
    assert "collection-source-select" in summary_html
    assert "/ui/retro_console_v1/static/js/library-context.js" in operator_html
    assert "retrieval-library-source" in operator_html
    assert "x-goodq-unavailable-sources" in operator_js


def test_ou05_watchdog_move_failure_withholds_completed_status_and_reconciles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    processor = _make_watchdog(tmp_path, monkeypatch)
    inbox_file = processor.watch_dir / "sample_clip.wav"
    inbox_file.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00@\x1f\x00\x00\x80>\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
    file_hash = FileState(inbox_file).compute_hash()

    monkeypatch.setattr(processor, "ingest_audio", lambda _p, _run_id: True)
    observed_status_during_move: list[str | None] = []
    real_safe_move = watchdog_mod.safe_move_file

    def _failing_move(_src: Path, _dst: Path) -> Path:
        rec = processor.registry.processed.get(file_hash)
        observed_status_during_move.append(rec.get("status") if rec else None)
        raise OSError("simulated archive lock failure")

    tracked_state = FileState(inbox_file)
    tracked_state.stable = True
    processor.file_states[str(inbox_file)] = tracked_state

    monkeypatch.setattr(watchdog_mod, "safe_move_file", _failing_move)
    ok = processor.process_file(inbox_file, file_hash)
    assert ok is False
    assert observed_status_during_move == ["finalizing"]
    assert processor.file_states[str(inbox_file)].stable is False

    rec_after_fail = processor.registry.processed.get(file_hash)
    assert rec_after_fail is not None
    assert rec_after_fail["status"] == "finalizing"
    assert processor.registry.is_processed(file_hash) is False
    assert inbox_file.is_file()

    # Live monitor_loop next scan retries finalization without re-ingesting or queueing
    monkeypatch.setattr(watchdog_mod, "safe_move_file", real_safe_move)
    monkeypatch.setattr(
        processor,
        "ingest_audio",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not re-ingest finalizing artifact")),
    )
    monkeypatch.setattr(watchdog_mod.FileState, "is_stable", lambda self: True)
    monkeypatch.setattr(processor, "_resume_retained_finalizations", lambda: set())
    monkeypatch.setattr(
        watchdog_mod,
        "time",
        types.SimpleNamespace(time=__import__("time").time, sleep=lambda _s: processor.shutdown.set()),
    )
    processor.monitor_loop()

    rec_recovered = processor.registry.processed.get(file_hash)
    assert rec_recovered is not None
    assert rec_recovered["status"] == "success"
    assert processor.registry.is_processed(file_hash) is True
    assert processor.queue.empty()
    assert not inbox_file.exists()
    assert (processor.processed_dir / f"PROCESSED_{inbox_file.name}").is_file()


def test_ou06_legacy_binary_doc_extension_rejected_everywhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert ".doc" not in API_SUPPORTED_DOCUMENT
    assert ".doc" not in WATCHDOG_SUPPORTED_DOCUMENT
    assert is_supported_ingest_path(Path("legacy.doc")) is False
    assert is_supported_ingest_path(Path("modern.docx")) is True
    assert is_supported_ingest_path(Path("report.pdf")) is True

    processor = _make_watchdog(tmp_path, monkeypatch)
    assert processor.get_file_type(Path("legacy.doc")) is None
    assert processor.get_file_type(Path("modern.docx")) == "document"

    retro_html = (REPO_ROOT / "ui" / "retro_console_v1" / "index.html").read_text(encoding="utf-8")
    accept_line = next(line for line in retro_html.splitlines() if "droppad-file-input" in line)
    exts = {token.strip().lower() for token in accept_line.split('accept="')[1].split('"')[0].split(",")}
    assert ".doc" not in exts
    assert ".docx" in exts


def test_ou07_airgap_egress_gating_and_diarization_engine_truth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    just_html = (REPO_ROOT / "ui" / "justification_v1" / "index.html").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in just_html
    assert "fonts.gstatic.com" not in just_html

    op_html = (REPO_ROOT / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    assert "data.elevenlabs_widget_enabled === true" in op_html
    assert 'localStorage.getItem("goodq_operator_api_base")' in op_html

    # Ambient ELEVENLABS_AGENT_ID must NOT be exposed unless widget is explicitly opted into
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", "agent_ambient_secret_id")
    monkeypatch.delenv("GOODQ_ENABLE_ELEVENLABS_WIDGET", raising=False)
    monkeypatch.setattr(runtime_routes, "_CFG", {"ui": {}, "paths": {}, "llm": {}, "audio": {}, "wsl": {}})
    monkeypatch.setattr(
        runtime_routes.requests,
        "get",
        lambda *_a, **_k: (_ for _ in ()).throw(ConnectionError("isolated")),
    )
    monkeypatch.setattr(
        runtime_routes,
        "build_qdrant_session",
        lambda _url: type(
            "_OfflineQdrant",
            (),
            {"get": lambda *_a, **_k: (_ for _ in ()).throw(ConnectionError("isolated"))},
        )(),
    )
    monkeypatch.setattr(
        runtime_routes,
        "_shared_wsl_status",
        lambda: {"available": False, "status": "not_installed", "audio_processing": "unavailable"},
    )
    monkeypatch.setattr(
        runtime_routes,
        "_database_status",
        lambda *_a, **_k: {"exists": False, "scenes": 0, "db_name": "memory.db", "epoch": "test"},
    )
    monkeypatch.setattr(
        runtime_routes,
        "_collect_cli_progress",
        lambda **_k: {"available": False, "reason": "isolated"},
    )
    monkeypatch.setattr(
        runtime_routes.subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("isolated")),
    )

    client = TestClient(api_main.app)
    status_default = client.get("/api/status").json()
    assert status_default["elevenlabs_agent_id"] is None
    assert status_default["elevenlabs_widget_enabled"] is False

    monkeypatch.setenv("GOODQ_ENABLE_ELEVENLABS_WIDGET", "1")
    status_opted_in = client.get("/api/status").json()
    assert status_opted_in["elevenlabs_agent_id"] == "agent_ambient_secret_id"
    assert status_opted_in["elevenlabs_widget_enabled"] is True

    # Diarization engine truth must reflect disabled WSL instead of hardcoded "ready"
    monkeypatch.setenv("GOODQ_ENABLE_WSL", "0")
    engines_payload = client.get("/api/engines").json()
    assert engines_payload["engines"]["audio_diarization"]["status"] == "disabled"


def test_ou08_ui_walkthrough_and_doc_drift_lint_check(tmp_path: Path) -> None:
    assert doc_drift_lint.check_ui_walkthrough_drift(REPO_ROOT) == []

    # Synthetic repo with an undocumented UI mount and false blanket zero-mutation claim
    (tmp_path / "api").mkdir(parents=True)
    (tmp_path / "docs" / "guides" / "ui").mkdir(parents=True)
    (tmp_path / "api" / "main.py").write_text(
        'app.mount("/ui/retro_console_v1", StaticFiles(directory="x", html=True), name="retro")\n'
        'app.mount("/ui/identity_workbench", StaticFiles(directory="y", html=True), name="id")\n',
        encoding="utf-8",
    )
    (tmp_path / "docs" / "guides" / "ui" / "USER_INTERFACE_WALKTHROUGH.md").write_text(
        "<!-- DOC_BADGE: OPERATIONAL -->\n"
        "<!-- DOC_STATUS: ACTIVE_GUIDE -->\n\n"
        "# Walkthrough\n"
        "Serves `/ui/retro_console_v1/` without offering any database-mutation capabilities.\n",
        encoding="utf-8",
    )
    violations = doc_drift_lint.check_ui_walkthrough_drift(tmp_path)
    messages = [detail for _, detail in violations]
    assert any("/ui/identity_workbench" in m for m in messages)
    assert any("blanket zero-mutation" in m for m in messages)
    assert doc_drift_lint.main(tmp_path) == 1


def test_ou09_server_refuses_silent_port_fallback_for_pinned_or_library_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
        blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        busy_port = blocker.getsockname()[1]

        monkeypatch.setenv("GOODQ_API_PORT", str(busy_port))
        monkeypatch.setattr(api_server, "_has_configured_saved_library_sources", lambda: False)
        with pytest.raises(OSError, match="refusing silent port fallback"):
            api_server._find_available_port("127.0.0.1", busy_port)

        monkeypatch.delenv("GOODQ_API_PORT", raising=False)
        monkeypatch.setattr(api_server, "_has_configured_saved_library_sources", lambda: True)
        with pytest.raises(OSError, match="refusing silent port fallback"):
            api_server._find_available_port("127.0.0.1", busy_port)

        monkeypatch.setattr(api_server, "_has_configured_saved_library_sources", lambda: False)
        fallback = api_server._find_available_port("127.0.0.1", busy_port)
        assert fallback > busy_port


def test_rs01_similar_scenes_enforces_ucf_promoted_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "rs01_root"
    processing_root = data_root / "processing"
    staged_hash = "a" * 64
    promoted_hash = "b" * 64
    staged_vid = f"video_{staged_hash[:8]}"
    promoted_vid = f"video_{promoted_hash[:8]}"

    for vid, vhash in ((staged_vid, staged_hash), (promoted_vid, promoted_hash)):
        vdir = processing_root / vid
        vdir.mkdir(parents=True, exist_ok=True)
        (vdir / "temporal_index.json").write_text(
            json.dumps(
                {
                    "video_id": vid,
                    "video_hash": vhash,
                    "duration": 10.0,
                    "total_scenes": 2,
                    "segments": [
                        {"scene_id": "0", "start": 0.0, "end": 5.0, "transcript": "alpha"},
                        {"scene_id": "1", "start": 5.0, "end": 10.0, "transcript": "beta"},
                    ],
                }
            ),
            encoding="utf-8",
        )

    ucf_db = tmp_path / "ucf_ledger.db"
    with sqlite3.connect(str(ucf_db)) as conn:
        conn.execute(
            "CREATE TABLE context_frames (epoch_id TEXT, video_hash TEXT, promotion_status TEXT)"
        )
        conn.executemany(
            "INSERT INTO context_frames VALUES (?, ?, ?)",
            [
                ("epoch_test", staged_hash, "staged"),
                ("epoch_test", promoted_hash, "promoted"),
            ],
        )
        conn.execute(
            "CREATE TABLE scene_retirements ("
            "retirement_id TEXT PRIMARY KEY, video_hash TEXT, epoch_id TEXT, "
            "scene_id TEXT, start_sec REAL, end_sec REAL, reason TEXT, retired_at_utc TEXT)"
        )
        conn.commit()

    class _FakeSearchEngine:
        def search_similar_scene(self, **_kwargs):
            return [
                {
                    "payload": {"video_id": promoted_vid, "video_hash": promoted_hash, "scene_id": "1"},
                    "scene_context": {
                        "video_id": promoted_vid,
                        "video_hash": promoted_hash,
                        "scene_id": "1",
                        "start": 5.0,
                        "end": 10.0,
                        "transcript": "beta",
                    },
                },
                {
                    "payload": {"video_id": staged_vid, "video_hash": staged_hash, "scene_id": "0"},
                    "scene_context": {
                        "video_id": staged_vid,
                        "video_hash": staged_hash,
                        "scene_id": "0",
                        "start": 0.0,
                        "end": 5.0,
                        "transcript": "alpha",
                    },
                },
            ]

    loader = DataLoader(data_root=str(data_root), processing_root=str(processing_root))
    loader._ucf_scope = (processing_root.resolve(), ucf_db, "epoch_test")
    monkeypatch.setattr(scenes_routes, "_data_loader", loader)
    monkeypatch.setattr(scenes_routes, "get_search_engine", lambda: _FakeSearchEngine())

    client = TestClient(api_main.app)

    # Staged seed must return 404
    staged_resp = client.get(f"/api/videos/{staged_vid}/scenes/0/similar")
    assert staged_resp.status_code == 404

    # Promoted seed returns 200 and filters out unpromoted candidate from staged_vid
    promoted_resp = client.get(f"/api/videos/{promoted_vid}/scenes/0/similar")
    assert promoted_resp.status_code == 200
    rows = promoted_resp.json()
    assert [(r["video_id"], r["scene_id"]) for r in rows] == [(promoted_vid, "1")]

    # Zero UCF rows for (video_hash, epoch_id) must also return 404
    loader._ucf_scope = (processing_root.resolve(), ucf_db, "epoch_empty")
    empty_resp = client.get(f"/api/videos/{promoted_vid}/scenes/0/similar")
    assert empty_resp.status_code == 404


def test_vs01_scenes_and_timeline_project_stage_accounting_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "vs01_root"
    video_id = "video_99887766"
    video_dir = data_root / "processing" / video_id
    video_dir.mkdir(parents=True, exist_ok=True)
    (video_dir / "temporal_index.json").write_text(
        json.dumps(
            {
                "video_id": video_id,
                "duration": 12.0,
                "total_scenes": 1,
                "segments": [
                    {
                        "segment_id": 0,
                        "scene_id": "0",
                        "start": 0.0,
                        "end": 12.0,
                        "transcript": "birthday toast",
                        "ocr_meta": {"status": "ok", "text_blocks": 1, "raw_path": r"C:\secret_dir\ocr.json"},
                        "faces_meta": {"status": "ok", "detected_faces": 2},
                        "errors": ["recoverable_warning"],
                        "optional_stage_errors": {"caption": "vllm_offline"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    loader = DataLoader(data_root=str(data_root), processing_root=str(data_root / "processing"))
    loader._ucf_scope = None
    monkeypatch.setattr(scenes_routes, "_data_loader", loader)
    monkeypatch.setattr(timeline_routes, "_data_loader", loader)

    client = TestClient(api_main.app)
    list_resp = client.get(f"/api/videos/{video_id}/scenes")
    assert list_resp.status_code == 200
    scene_row = list_resp.json()[0]
    assert scene_row["ocr_meta"]["status"] == "ok"
    assert "secret_dir" not in json.dumps(scene_row["ocr_meta"])
    assert scene_row["faces_meta"] == {"status": "ok", "detected_faces": 2}
    assert scene_row["errors"] == ["recoverable_warning"]
    assert scene_row["optional_stage_errors"] == {"caption": "vllm_offline"}

    detail_resp = client.get(f"/api/videos/{video_id}/scenes/0")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["optional_stage_errors"] == {"caption": "vllm_offline"}

    tl_resp = client.get(f"/api/videos/{video_id}/timeline")
    assert tl_resp.status_code == 200
    seg = tl_resp.json()["segments"][0]
    assert seg["ocr_meta"]["status"] == "ok"
    assert "secret_dir" not in json.dumps(seg["ocr_meta"])
    assert seg["faces_meta"] == {"status": "ok", "detected_faces": 2}
    assert seg["errors"] == ["recoverable_warning"]
    assert seg["optional_stage_errors"] == {"caption": "vllm_offline"}

    tl_full_resp = client.get(f"/api/videos/{video_id}/timeline/full")
    assert tl_full_resp.status_code == 200
    assert tl_full_resp.json()["segments"][0]["faces_meta"] == {"status": "ok", "detected_faces": 2}

    # Verify legacy temporal_index.json (lacking faces_meta / errors / optional_stage_errors)
    # hydrates read-only from scene_manifest.json without mutating temporal_index.json on disk.
    legacy_vid = "vid_vs01_legacy"
    legacy_dir = data_root / "processing" / legacy_vid
    (legacy_dir / "video").mkdir(parents=True)
    ti_path = legacy_dir / "temporal_index.json"
    ti_bytes_before = json.dumps(
        {
            "video_id": legacy_vid,
            "duration": 10.0,
            "total_scenes": 1,
            "segments": [{"segment_id": 0, "scene_id": "s_58", "start": 0.0, "end": 10.0}],
        }
    ).encode("utf-8")
    ti_path.write_bytes(ti_bytes_before)
    (legacy_dir / "video" / "scene_manifest.json").write_text(
        json.dumps(
            {
                "video_id": legacy_vid,
                "scenes": [
                    {
                        "scene_id": "s_58",
                        "start": 0.0,
                        "end": 10.0,
                        "errors": {"frame_processing": "VRAM allocation failed"},
                        "keyframe": {
                            "faces_meta": {"status": "ok", "engine": "opencv-yunet-sface"},
                            "ocr_sampling_errors": ["ocr sample timeout"],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    legacy_scenes = client.get(f"/api/videos/{legacy_vid}/scenes").json()
    assert legacy_scenes[0]["faces_meta"] == {"status": "ok", "engine": "opencv-yunet-sface"}
    assert legacy_scenes[0]["errors"] == {"frame_processing": "VRAM allocation failed"}
    assert legacy_scenes[0]["optional_stage_errors"] == {"ocr_sampling_errors": ["ocr sample timeout"]}
    assert ti_path.read_bytes() == ti_bytes_before


def test_rs07_runtime_qdrant_helpers_use_loopback_session(monkeypatch: pytest.MonkeyPatch) -> None:
    real_transport = runtime_routes._qdrant_transport("http://127.0.0.1:6333")
    assert getattr(real_transport, "trust_env", None) is False
    real_transport.close()

    calls: list[tuple[str, str, str]] = []

    class _FakeResp:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict:
            return self._payload

    class _FakeSession:
        trust_env = False

        def __init__(self, base_url: str):
            self.base_url = base_url

        def get(self, url: str, timeout: float = 5.0):
            calls.append(("GET", self.base_url, url))
            return _FakeResp(
                200,
                {"result": {"collections": [{"name": "goodq_audio_ep1"}, {"name": "goodq_clip_ep1"}]}},
            )

        def post(self, url: str, json: dict | None = None, timeout: float = 5.0):
            calls.append(("POST", self.base_url, url))
            return _FakeResp(
                200,
                {"result": {"points": [{"payload": {"scene_id": "0", "run_id": "run_1"}}], "next_page_offset": None}},
            )

    monkeypatch.setattr(runtime_routes, "build_qdrant_session", lambda base_url: _FakeSession(base_url))
    monkeypatch.setattr(
        runtime_routes.requests,
        "get",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("raw requests.get must not be called")),
    )
    monkeypatch.setattr(
        runtime_routes.requests,
        "post",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("raw requests.post must not be called")),
    )

    base = "http://127.0.0.1:6333"
    monkeypatch.setattr(runtime_routes, "_qdrant_base_url", lambda: base)

    names_res = runtime_routes._qdrant_audio_collection_names()
    assert names_res["status"] == "ok"
    assert names_res["collections"] == ["goodq_audio_ep1"]

    scrolled_res = runtime_routes._scroll_qdrant_audio_collection_payloads("goodq_audio_ep1")
    assert scrolled_res["status"] == "ok"
    assert scrolled_res["payloads"] == [{"scene_id": "0", "run_id": "run_1"}]

    sampled_res = runtime_routes._sample_qdrant_audio_payloads(["goodq_audio_ep1"])
    assert sampled_res["status"] == "ok"
    assert sampled_res["sample_count"] == 1
    assert [c[0] for c in calls] == ["GET", "POST", "POST"]
