"""PDF parser resolution and diagnostics through the production JSON dispatcher."""
import json
import os
from pathlib import Path
import subprocess
import sys
import types

import pytest
from tests.unit.test_standalone_lifecycle_producer import standalone_runtime
from tests.unit.test_watchdog_safety import standalone_audio_dispatch


@pytest.mark.parametrize("succeeds", [False, True])
def test_watchdog_pdf_keeps_parser_provenance_in_retained_evidence(standalone_runtime, monkeypatch, tmp_path, succeeds):
    from cli import step_runner
    import hashlib

    processor, _calls, _cfg, _bridge = standalone_runtime
    compute = step_runner.run_step
    meta = {"engine": "pdftotext", "status": "ok" if succeeds else "error", "tool_path": "registered-parser",
            "returncode": 0 if succeeds else 3, "stderr": "fixture parser diagnostic"}
    def dispatch(step, item, cfg):
        if step == "pdf_text":
            return {"pdf_text": "Actual extracted document text" if succeeds else None, "document_meta": meta}
        return compute(step, item, cfg)
    monkeypatch.setattr(step_runner, "run_step", dispatch)
    source = tmp_path / "document.pdf"
    source.write_bytes(b"PDF fixture; parser compute replaced")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert processor.process_file(source, digest) is succeeds
    root = processor.processing_dir / digest
    if succeeds:
        evidence = json.loads((root / "video/scene_manifest.json").read_text(encoding="utf-8"))["scenes"][0]
    else:
        evidence = json.loads((root / "failed_result.json").read_text(encoding="utf-8"))["item"]
    assert evidence["document_meta"] == meta


@pytest.mark.parametrize("outcome", ["text", "empty", "missing_tool", "parser_error", "timeout"])
def test_pdf_dispatch_preserves_resolved_parser_output_and_diagnostics(monkeypatch, tmp_path, outcome):
    from cli import step_runner
    from steps.common import step_logger
    from steps.common.tool_resolver import ToolResolver
    from steps.pdf_text import step

    pdf = tmp_path / "input.pdf"
    pdf.write_bytes(b"parser fixture; external parser is replaced")
    exe = str(tmp_path / "registered-tool/pdftotext.exe")
    monkeypatch.setattr(ToolResolver, "resolve_tool", lambda name: {
        "found": outcome != "missing_tool", "path": exe if outcome != "missing_tool" else None})
    calls = []
    def parser(cmd, **kwargs):
        calls.append(cmd)
        assert cmd == [exe, "-raw", "-enc", "UTF-8", str(pdf), "-"]
        assert kwargs["encoding"] == "utf-8"
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(cmd, 45)
        return subprocess.CompletedProcess(cmd, 3 if outcome == "parser_error" else 0,
            "caf\u00e9 \u5bb6" if outcome == "text" else "", "fixture parser diagnostic")
    monkeypatch.setattr(step.subprocess, "run", parser)
    cfg = {"paths": {"log_dir": str(tmp_path / "logs")}, "gpu": {"clear_cache_before_step": False}}
    monkeypatch.setattr(step_runner, "load_step_config", lambda *_: cfg)
    monkeypatch.setattr(step_logger, "MISSION_LOGGER_AVAILABLE", False)
    gpu = types.ModuleType("common.gpu_manager")
    gpu.initialize_gpu_for_step = lambda **_: None
    monkeypatch.setitem(sys.modules, "common.gpu_manager", gpu)
    source, result = tmp_path / "input.json", tmp_path / "result.json"
    source.write_text(json.dumps({"source_path": str(pdf)}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["step_runner", "--step", "pdf_text", "--in", str(source), "--out", str(result)])
    step_runner.main()
    output = json.loads(result.read_text(encoding="utf-8"))
    meta = output["document_meta"]
    row = json.loads((tmp_path / "logs/step_runs.jsonl").read_text(encoding="utf-8"))
    assert row["extra"]["result_meta"]["document_meta"] == meta
    assert meta["engine"] == "pdftotext"
    if outcome == "text":
        assert output["pdf_text"] == "caf\u00e9 \u5bb6"
        assert meta["status"] == row["status"] == "ok"
    elif outcome == "missing_tool":
        assert not calls
        assert output["pdf_text"] is None
        assert meta["status"] == "unavailable" and row["status"] == "skipped"
    else:
        assert not output["pdf_text"]
        assert meta["status"] == row["status"] == "error"
    if outcome in {"text", "empty", "parser_error"}:
        assert meta["stderr"] == "fixture parser diagnostic"
        assert meta["returncode"] == (3 if outcome == "parser_error" else 0)
    if outcome != "missing_tool":
        assert meta["tool_path"] == exe
    assert pdf.read_bytes() == b"parser fixture; external parser is replaced"


def test_pdf_dispatch_preserves_explicit_poppler_override(monkeypatch, tmp_path):
    from steps.pdf_text import step
    from steps.common.tool_resolver import ToolResolver

    binary = tmp_path / ("pdftotext.exe" if sys.platform == "win32" else "pdftotext")
    binary.write_bytes(b"fixture")
    source = tmp_path / "input.pdf"
    source.write_bytes(b"fixture")
    monkeypatch.setattr(ToolResolver, "resolve_tool", lambda _: pytest.fail("explicit valid override must win"))
    def parser(cmd, **kwargs):
        assert Path(cmd[0]) == binary
        return subprocess.CompletedProcess(cmd, 0, "Explicit parser text", "")
    monkeypatch.setattr(step.subprocess, "run", parser)
    result = step.pdf_to_text({"source_path": str(source)}, {"config": {"tools": {"poppler_bin": str(tmp_path)}}})
    assert result["document_meta"]["tool_resolution"] == "configured_poppler_bin"


def test_pdf_caller_preserves_two_column_paragraph_reading_order(tmp_path):
    from steps.common.tool_resolver import ToolResolver
    from steps.pdf_text.step import pdf_to_text

    configured_bin = os.environ.get("GOODQ_TEST_POPPLER_BIN")
    if configured_bin:
        binary = Path(configured_bin) / ("pdftotext.exe" if os.name == "nt" else "pdftotext")
        assert binary.is_file(), "Explicit test Poppler directory must contain pdftotext"
    else:
        tool = ToolResolver.resolve_tool("pdftotext")
        if not tool.get("found"):
            pytest.skip("Installed pdftotext is required for the real PDF reading-order regression")
        configured_bin = str(Path(tool["path"]).parent)

    left = ["First column introduces the research.", "Its next sentence stays in this column.",
            "Its final line closes the research point."]
    right = ["Second column starts a separate topic.", "Its next sentence belongs to this topic.",
             "Its final line closes the second topic."]
    commands = []
    for x, lines in ((54, left), (330, right)):
        commands.append(f"BT /F1 11 Tf 1 0 0 1 {x} 720 Tm")
        for index, line in enumerate(lines):
            if index:
                commands.append("0 -16 Td")
            commands.append(f"({line}) Tj")
        commands.append("ET")
    stream = "\n".join(commands).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    source = tmp_path / "two-columns.pdf"
    source.write_bytes(pdf)

    result = pdf_to_text({"source_path": str(source)}, {"config": {"tools": {"poppler_bin": configured_bin}}})

    assert result["document_meta"]["status"] == "ok"
    assert result["document_meta"]["tool_resolution"] == "configured_poppler_bin"
    assert " ".join(result["pdf_text"].split()) == " ".join(left + right)
    assert source.read_bytes() == pdf


@pytest.mark.skipif(os.name != "nt", reason="Windows parser long-path boundary")
def test_pdf_worker_passes_extended_retained_path_to_installed_parser(monkeypatch, tmp_path):
    from steps.pdf_text import step
    from steps.common.tool_resolver import ToolResolver
    source = tmp_path / ("retained-" + "a" * 150) / ("b" * 70) / ("c" * 64 + ".pdf")
    source.parent.mkdir(parents=True)
    source.write_bytes(b"long path fixture")
    assert len(str(source.resolve())) >= 260
    monkeypatch.setattr(ToolResolver, "resolve_tool", lambda _: {"found": True, "path": "registered-pdftotext"})
    def parser(cmd, **kwargs):
        assert cmd[-2] == "\\\\?\\" + str(source.resolve())
        return subprocess.CompletedProcess(cmd, 0, "Extracted", "")
    monkeypatch.setattr(step.subprocess, "run", parser)
    assert step.pdf_to_text({"source_path": str(source)}, {})["pdf_text"] == "Extracted"
