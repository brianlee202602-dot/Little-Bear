from __future__ import annotations

import sys
import zipfile
from io import BytesIO
from types import SimpleNamespace

from app.modules.import_pipeline.executors import (
    MultiFormatDocumentParser,
    PlainTextCleaner,
    SourceDocument,
    StructureAwareChunker,
)


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

    assert parsed.parser_version == "pdf-structure-v1"
    assert "[page 1]\n第一页" in parsed.text
    assert "[page 2]\n第二页" in parsed.text
    assert parsed.metadata["page_count"] == 2
    paragraph_blocks = [block for block in parsed.blocks if block.block_type == "paragraph"]
    assert [block.page_number for block in paragraph_blocks] == [1, 2]


def test_multi_format_parser_extracts_docx_text() -> None:
    parsed = MultiFormatDocumentParser().parse(
        SourceDocument(
            title="handbook.docx",
            content=_docx_bytes(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    )

    assert parsed.parser_version == "docx-structure-v1"
    assert "标题" in parsed.text
    assert "正文" in parsed.text
    assert "字段" in parsed.text
    assert parsed.metadata["paragraph_count"] == 3
    assert parsed.metadata["table_count"] == 1
    assert any(block.block_type == "table" and "字段" in block.text for block in parsed.blocks)


def test_multi_format_parser_keeps_text_and_markdown_as_plain_text() -> None:
    parsed = MultiFormatDocumentParser().parse(
        SourceDocument(
            title="handbook.md",
            content=b"# Handbook\n\nHello",
            content_type="text/markdown",
        )
    )

    assert parsed.parser_version == "plain-text-structure-v1"
    assert parsed.text == "# Handbook\n\nHello"
    assert parsed.blocks[0].block_type == "heading"
    assert parsed.blocks[0].heading_level == 1


def test_structure_aware_chunker_builds_heading_path_and_offsets() -> None:
    parsed = MultiFormatDocumentParser().parse(
        SourceDocument(
            title="采购制度.md",
            content=(
                "# 采购管理\n\n"
                "## 项目启动\n\n"
                "需要提交立项材料。\n\n"
                "- 预算审批\n"
                "- 供应商准入"
            ).encode(),
            content_type="text/markdown",
        )
    )
    cleaned = PlainTextCleaner().clean(parsed)

    chunks = StructureAwareChunker(max_chars=500).chunk(cleaned, title="采购制度.md")

    assert len(chunks) == 1
    assert chunks[0].heading_path == "采购管理 / 项目启动"
    assert chunks[0].source_offsets["block_start"] == 2
    assert chunks[0].source_offsets["block_end"] == 4
    assert chunks[0].source_offsets["block_types"] == ["paragraph", "list_item"]
    assert chunks[0].source_offsets["section_id"] == "采购管理/项目启动"


def test_structure_aware_chunker_propagates_pdf_pages_to_chunks(monkeypatch) -> None:
    class _Page:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class _PdfReader:
        def __init__(self, _stream) -> None:
            self.pages = [_Page("第一页内容。"), _Page("第二页内容。")]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=_PdfReader))
    parsed = MultiFormatDocumentParser().parse(
        SourceDocument(title="制度.pdf", content=b"%PDF", content_type="application/pdf")
    )
    cleaned = PlainTextCleaner().clean(parsed)

    chunks = StructureAwareChunker(max_chars=500).chunk(cleaned, title="制度.pdf")

    assert [chunk.page_start for chunk in chunks] == [1]
    assert [chunk.page_end for chunk in chunks] == [2]
    assert chunks[0].source_offsets["page_start"] == 1
    assert chunks[0].source_offsets["page_end"] == 2


def test_structure_aware_chunker_splits_long_paragraph_by_sentence() -> None:
    parsed = MultiFormatDocumentParser().parse(
        SourceDocument(
            title="长文.md",
            content=(
                "# 说明\n\n"
                + "第一句内容比较长但应该完整保留。" * 10
                + "第二句内容比较长但也应该完整保留。" * 10
                + "第三句内容比较长但也应该完整保留。" * 10
            ).encode(),
            content_type="text/markdown",
        )
    )
    cleaned = PlainTextCleaner().clean(parsed)

    chunks = StructureAwareChunker(max_chars=42).chunk(cleaned, title="长文.md")

    assert len(chunks) >= 2
    assert all(chunk.text.endswith("。") for chunk in chunks)


def test_structure_aware_chunker_keeps_table_as_atomic_chunk() -> None:
    parsed = MultiFormatDocumentParser().parse(
        SourceDocument(
            title="table.docx",
            content=_docx_bytes(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    )
    cleaned = PlainTextCleaner().clean(parsed)

    chunks = StructureAwareChunker(max_chars=20).chunk(cleaned, title="table.docx")

    table_chunks = [chunk for chunk in chunks if "table" in chunk.source_offsets["block_types"]]
    assert len(table_chunks) == 1
    assert "字段" in table_chunks[0].text


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
