"""Bounded local text extraction for the main body of ordinary DOCX packages."""
from pathlib import Path
import re
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile


MAX_DOCX_XML_BYTES = 8 * 1024 * 1024
MAX_DOCX_MEMBERS = 2048
_MAIN_PART = "word/document.xml"
_WORD_NAMESPACES = (
    "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "http://purl.oclc.org/ooxml/wordprocessingml/main",
)
_SUPPLEMENTARY_PART = re.compile(r"word/(?:header[^/]*|footer[^/]*|footnotes|endnotes|comments)\.xml$")
_ALTERNATE_CONTENT = "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"


def extract_docx_text(path: Path) -> dict:
    """Read only document.xml; never extract files or follow package relationships."""
    try:
        with ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > MAX_DOCX_MEMBERS:
                raise ValueError("DOCX package exceeds member count limit")
            if any(member.flag_bits & 1 for member in members):
                raise ValueError("Encrypted DOCX archives are unsupported")
            documents = [member for member in members if member.filename == _MAIN_PART]
            if len(documents) != 1:
                raise ValueError("DOCX requires exactly one word/document.xml part")
            if documents[0].file_size > MAX_DOCX_XML_BYTES:
                raise ValueError("DOCX document XML exceeds decompressed size limit")
            with archive.open(documents[0]) as stream:
                payload = stream.read(MAX_DOCX_XML_BYTES + 1)
            if len(payload) > MAX_DOCX_XML_BYTES:
                raise ValueError("DOCX document XML exceeds decompressed size limit")
            omitted_parts = sorted({member.filename for member in members
                                    if _SUPPLEMENTARY_PART.fullmatch(member.filename)})
    except BadZipFile as error:
        raise ValueError("DOCX is not a readable ZIP package; encrypted or malformed input is unsupported") from error

    # Removing NULs also detects declarations in UTF-16/32 XML before parsing.
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", payload.replace(b"\0", b""), re.IGNORECASE):
        raise ValueError("DOCX XML DTD and entity declarations are unsupported")
    try:
        document = ElementTree.fromstring(payload)
    except (ElementTree.ParseError, ValueError) as error:
        raise ValueError(f"Malformed DOCX document XML: {error}") from error
    namespace = next((ns for ns in _WORD_NAMESPACES if document.tag == f"{{{ns}}}document"), None)
    if namespace is None:
        raise ValueError("Unsupported DOCX document XML namespace or root")
    prefix = f"{{{namespace}}}"
    body = document.find(prefix + "body")
    if body is None:
        raise ValueError("DOCX document XML has no body")

    omitted_tags = {
        prefix + "drawing": "drawings_and_image_text", prefix + "pict": "drawings_and_image_text",
        prefix + "object": "embedded_objects", prefix + "altChunk": "embedded_document_content",
        prefix + "del": "deleted_revision_text", prefix + "moveFrom": "moved_from_revision_text",
        _ALTERNATE_CONTENT: "alternate_content",
    }

    def inline_text(element):
        if element.tag in omitted_tags:
            return ""
        if element.tag == prefix + "t":
            return element.text or ""
        if element.tag == prefix + "tab":
            return "\t"
        if element.tag in {prefix + "br", prefix + "cr"}:
            return "\n"
        if element.tag == prefix + "noBreakHyphen":
            return "\u2011"
        if element.tag == prefix + "softHyphen":
            return "\u00ad"
        return "".join(inline_text(child) for child in element)

    def block_text(element):
        if element.tag in omitted_tags:
            return ""
        if element.tag == prefix + "p":
            return inline_text(element)
        if element.tag == prefix + "tr":
            return "\t".join(block_text(child) for child in element if child.tag == prefix + "tc")
        return "\n".join(text for child in element if (text := block_text(child)))

    text = block_text(body).strip()
    if not text:
        raise ValueError("DOCX extraction produced no usable text in the main document body")
    return {"document_text": text, "document_meta": {
        "engine": "python_docx_xml", "status": "ok", "text_scope": "main_document_body",
        "parts_read": [_MAIN_PART], "omitted_parts": omitted_parts,
        "omitted_features": sorted({omitted_tags[node.tag] for node in body.iter() if node.tag in omitted_tags}),
        "limitations": ["supplementary_parts_not_extracted", "image_text_ocr", "layout_reconstruction",
                        "automatic_numbering_and_field_evaluation"],
        "max_xml_bytes": MAX_DOCX_XML_BYTES,
    }}
