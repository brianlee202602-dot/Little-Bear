from __future__ import annotations

import sys
import zipfile
from io import BytesIO
from types import SimpleNamespace

from app.modules.import_pipeline.executors import MultiFormatDocumentParser, SourceDocument


def test_multi_format_parser_extracts_pdf_text(monkeypatch) -> None:
    class _Page:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class _PdfReader:
        def __init__(self, _stream) -> None:
            self.pages = [_Page("第一页"), _Page("第二页")]

    monkeypatch.setitem(
        sys.modules,
        "pypdf",
        SimpleNamespace(PdfReader=_PdfReader),
    )

    parsed = MultiFormatDocumentParser().parse(
        SourceDocument(
            title="handbook.pdf",
            content=b"%PDF",
            content_type="application/pdf",
        )
    )

    assert parsed.parser_version == "pdf-p0"
    assert "[page 1]\n第一页" in parsed.text
    assert "[page 2]\n第二页" in parsed.text
    assert parsed.metadata["page_count"] == 2


def test_multi_format_parser_extracts_docx_text() -> None:
    parsed = MultiFormatDocumentParser().parse(
        SourceDocument(
            title="handbook.docx",
            content=_docx_bytes(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    )

    assert parsed.parser_version == "docx-p0"
    assert "标题" in parsed.text
    assert "正文" in parsed.text
    assert "字段" in parsed.text
    assert parsed.metadata["paragraph_count"] == 3
    assert parsed.metadata["table_count"] == 1


def test_multi_format_parser_keeps_text_and_markdown_as_plain_text() -> None:
    parsed = MultiFormatDocumentParser().parse(
        SourceDocument(
            title="handbook.md",
            content=b"# Handbook\n\nHello",
            content_type="text/markdown",
        )
    )

    assert parsed.parser_version == "plain-text-p0"
    assert parsed.text == "# Handbook\n\nHello"


def _docx_bytes() -> bytes:
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>标题</w:t></w:r></w:p>
    <w:p><w:r><w:t>正文</w:t></w:r></w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>字段</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>
"""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()
