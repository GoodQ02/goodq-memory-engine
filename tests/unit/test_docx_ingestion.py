"""DOCX text reaches the existing Watchdog persistence path without a converter."""
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from tests.unit.test_standalone_lifecycle_producer import standalone_runtime, ledger_rows
from tests.unit.test_watchdog_safety import standalone_audio_dispatch


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
STRICT_NS = "http://purl.oclc.org/ooxml/wordprocessingml/main"
BODY = """<w:p><w:r><w:t>Family library notes</w:t></w:r></w:p>
<w:p><w:r><w:t>Morning</w:t><w:tab/><w:t>walk</w:t><w:br/><w:t>with friends</w:t></w:r></w:p>
<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Place</w:t></w:r></w:p></w:tc>
<w:tc><w:p><w:r><w:t>River park</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
<w:p><w:hyperlink><w:r><w:t>Final marker</w:t></w:r></w:hyperlink></w:p>"""
EXPECTED_TEXT = "Family library notes\nMorning\twalk\nwith friends\nPlace\tRiver park\nFinal marker"


def write_docx(path, body=BODY, namespace=WORD_NS, extra_parts=None, xml=None):
    document = xml if xml is not None else (
        f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{namespace}">'
        f"<w:body>{body}</w:body></w:document>"
    ).encode("utf-8")
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", """<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")
        archive.writestr("_rels/.rels", """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""")
        archive.writestr("word/document.xml", document)
        for name, content in (extra_parts or {}).items():
            archive.writestr(name, content)
    return path


@pytest.mark.parametrize("namespace", [WORD_NS, STRICT_NS])
def test_docx_reaches_watchdog_persistence_with_explicit_text_scope(standalone_runtime, tmp_path, namespace):
    from steps.common import progress_tracker

    processor, calls, cfg, _bridge = standalone_runtime
    omitted = ["word/header1.xml", "word/footer1.xml", "word/footnotes.xml", "word/endnotes.xml"]
    source = write_docx(tmp_path / "Family notes.docx", namespace=namespace,
                        extra_parts={name: "<omitted>Supplementary marker</omitted>" for name in omitted})
    content = source.read_bytes()
    digest = hashlib.sha256(content).hexdigest()

    assert processor.process_file(source, digest) is True
    root = processor.processing_dir / digest
    raw = json.loads((root / "raw_result.json").read_text(encoding="utf-8"))
    assert raw["document_text"] == raw["frame_text"] == EXPECTED_TEXT
    assert raw["original_filename"] == "Family notes.docx"
    assert Path(raw["source_path"]).read_bytes() == content
    assert raw["worker_results"]["docx_text"]["document_text"] == EXPECTED_TEXT
    meta = raw["document_meta"]
    assert meta["engine"] == "python_docx_xml" and meta["status"] == "ok"
    assert meta["text_scope"] == "main_document_body"
    assert meta["parts_read"] == ["word/document.xml"]
    assert meta["omitted_parts"] == sorted(omitted)
    assert "image_text_ocr" in meta["limitations"]
    assert [(step, item["frame_text"]) for step, item, _ in calls if step == "text_embed"] == [("text_embed", EXPECTED_TEXT)]
    temporal = json.loads((root / "temporal_index.json").read_text(encoding="utf-8"))
    assert temporal["segments"][0]["document_text"] == EXPECTED_TEXT
    assert temporal["segments"][0]["document_meta"] == meta
    assert all(row["promotion_status"] == "staged" for row in ledger_rows(cfg))
    progress = progress_tracker.get_tracker().get_state()
    assert progress["status"] == "completed" and progress["progress_percent"] == 100
    assert progress["total_steps"] == 7
    assert [step["name"] for step in progress["steps_completed"]] == [
        "retain_source", "docx_text", "text_embed", "sentiment", "emotion_classify", "tagger", "persist_result",
    ]


@pytest.mark.parametrize("failure,reason", [
    ("not_zip", "ZIP"), ("missing_part", "word/document.xml"), ("empty", "no usable text"),
    ("malformed_xml", "XML"), ("dtd", "DTD"), ("utf16_dtd", "DTD"),
    ("encrypted", "Encrypted"), ("oversize", "size limit"),
])
def test_docx_failures_retain_source_without_claiming_completion(standalone_runtime, tmp_path, monkeypatch, failure, reason):
    from cli import document_text
    from steps.common import progress_tracker

    processor, calls, _cfg, _bridge = standalone_runtime
    source = tmp_path / "broken.docx"
    if failure == "not_zip":
        source.write_bytes(b"not a DOCX package")
    elif failure == "missing_part":
        with ZipFile(source, "w") as archive:
            archive.writestr("other.xml", "<other/>")
    elif failure == "empty":
        write_docx(source, body="<w:p><w:r><w:t> </w:t></w:r></w:p>")
    elif failure == "malformed_xml":
        write_docx(source, xml=b"<broken>")
    elif failure in {"dtd", "utf16_dtd"}:
        xml = f'<!DOCTYPE document [<!ENTITY injected "forbidden">]><w:document xmlns:w="{WORD_NS}"><w:body><w:p><w:r><w:t>&injected;</w:t></w:r></w:p></w:body></w:document>'
        write_docx(source, xml=xml.encode("utf-16" if failure == "utf16_dtd" else "utf-8"))
    else:
        write_docx(source)
        if failure == "oversize":
            monkeypatch.setattr(document_text, "MAX_DOCX_XML_BYTES", 256)
        elif failure == "encrypted":
            content = bytearray(source.read_bytes())
            for marker, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
                start = 0
                while (position := content.find(marker, start)) >= 0:
                    content[position + flag_offset] |= 1
                    start = position + len(marker)
            source.write_bytes(content)
    content = source.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    assert processor.process_file(source, digest) is False
    root = processor.processing_dir / digest
    assert (root / f"{digest}.docx").read_bytes() == content
    failure_record = json.loads((root / "failed_result.json").read_text(encoding="utf-8"))
    assert reason in failure_record["error"]
    assert reason in processor.registry.processed[digest]["error"]
    assert not (root / "temporal_index.json").exists()
    assert calls == []
    state = progress_tracker.get_tracker().get_state()
    assert state["status"] == "failed" and state["progress_percent"] < 100
    assert [step["name"] for step in state["steps_completed"]] == ["retain_source"]


def test_legacy_doc_failure_explains_unsupported_extraction_and_preserves_bytes(standalone_runtime, tmp_path):
    from steps.common import progress_tracker

    processor, calls, _cfg, _bridge = standalone_runtime
    source = tmp_path / "legacy.doc"
    content = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1legacy Word fixture"
    source.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    assert processor.process_file(source, digest) is False
    record = processor.registry.processed[digest]
    assert record["status"] == "failed"
    assert "Document text extraction is unsupported for extension: .doc" in record["error"]
    assert (processor.failed_dir / "FAILED_legacy.doc").read_bytes() == content
    assert not (processor.processing_dir / digest / "temporal_index.json").exists()
    assert calls == []
    state = progress_tracker.get_tracker().get_state()
    assert state["status"] == "failed" and state["progress_percent"] < 100
    assert any("unsupported" in error["message"] and ".doc" in error["message"] for error in state["errors"])
