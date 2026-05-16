"""导入 parse / clean / chunk 执行器。"""

from __future__ import annotations

import importlib
import re
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Protocol
from xml.etree import ElementTree

from app.modules.import_pipeline.errors import ImportServiceError


@dataclass(frozen=True)
class SourceDocument:
    title: str
    url: str | None = None
    object_key: str | None = None
    content: bytes | None = None
    content_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    parser_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CleanedDocument:
    text: str
    cleaner_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChunkDocument:
    text: str
    ordinal: int
    heading_path: str | None
    token_count: int
    source_offsets: dict[str, Any]


class DocumentParser(Protocol):
    version: str

    def parse(self, source: SourceDocument) -> ParsedDocument:
        ...


class DocumentCleaner(Protocol):
    version: str

    def clean(self, parsed: ParsedDocument) -> CleanedDocument:
        ...


class DocumentChunker(Protocol):
    version: str

    def chunk(self, cleaned: CleanedDocument, *, title: str) -> list[ChunkDocument]:
        ...


class PlainTextParser:
    version = "plain-text-p0"

    def parse(self, source: SourceDocument) -> ParsedDocument:
        text = _metadata_text(source.metadata)
        if text is None and source.content is not None:
            text = _decode_text(source.content, title=source.title)
        if text is None and source.url:
            text = f"{source.title}\n{source.url}"
        if text is None:
            text = source.title
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip("\ufeff")
        if not normalized.strip():
            raise ImportServiceError(
                "IMPORT_SOURCE_EMPTY",
                "import source document has no readable text",
                status_code=422,
                retryable=False,
                details={"title": source.title, "object_key": source.object_key},
            )
        return ParsedDocument(
            text=normalized,
            parser_version=self.version,
            metadata={
                "title": source.title,
                "url": source.url,
                "object_key": source.object_key,
                "content_type": source.content_type,
            },
        )


class PdfParser:
    version = "pdf-p0"

    def parse(self, source: SourceDocument) -> ParsedDocument:
        if not source.content:
            raise _empty_source(source)
        try:
            pypdf = importlib.import_module("pypdf")
        except ImportError as exc:
            raise ImportServiceError(
                "IMPORT_PDF_PARSER_UNAVAILABLE",
                "PDF parser dependency is not installed",
                status_code=503,
                retryable=False,
                details={"dependency": "pypdf"},
            ) from exc
        try:
            reader = pypdf.PdfReader(BytesIO(source.content))
            pages = [
                f"[page {index + 1}]\n{text.strip()}"
                for index, page in enumerate(reader.pages)
                if (text := page.extract_text() or "").strip()
            ]
        except Exception as exc:
            raise ImportServiceError(
                "IMPORT_PDF_PARSE_FAILED",
                "PDF document cannot be parsed",
                status_code=422,
                retryable=False,
                details={"title": source.title, "object_key": source.object_key},
            ) from exc
        if not pages:
            raise ImportServiceError(
                "IMPORT_PDF_TEXT_EMPTY",
                "PDF document has no extractable text",
                status_code=422,
                retryable=False,
                details={"title": source.title, "object_key": source.object_key},
            )
        return ParsedDocument(
            text="\n\n".join(pages),
            parser_version=self.version,
            metadata={
                "title": source.title,
                "object_key": source.object_key,
                "content_type": source.content_type,
                "page_count": len(reader.pages),
            },
        )


class DocxParser:
    version = "docx-p0"
    word_namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    def parse(self, source: SourceDocument) -> ParsedDocument:
        if not source.content:
            raise _empty_source(source)
        try:
            with zipfile.ZipFile(BytesIO(source.content)) as archive:
                document_xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(document_xml)
            paragraph_elements = root.findall(f".//{self.word_namespace}p")
            text_blocks = [
                "".join(
                    text_node.text or ""
                    for text_node in paragraph.findall(f".//{self.word_namespace}t")
                ).strip()
                for paragraph in paragraph_elements
            ]
            text_blocks = [block for block in text_blocks if block]
            table_count = len(root.findall(f".//{self.word_namespace}tbl"))
        except Exception as exc:
            raise ImportServiceError(
                "IMPORT_DOCX_PARSE_FAILED",
                "DOCX document cannot be parsed",
                status_code=422,
                retryable=False,
                details={"title": source.title, "object_key": source.object_key},
            ) from exc
        if not text_blocks:
            raise ImportServiceError(
                "IMPORT_DOCX_TEXT_EMPTY",
                "DOCX document has no extractable text",
                status_code=422,
                retryable=False,
                details={"title": source.title, "object_key": source.object_key},
            )
        return ParsedDocument(
            text="\n\n".join(text_blocks),
            parser_version=self.version,
            metadata={
                "title": source.title,
                "object_key": source.object_key,
                "content_type": source.content_type,
                "paragraph_count": len(paragraph_elements),
                "table_count": table_count,
            },
        )


class MultiFormatDocumentParser:
    version = "multi-format-p0"

    def __init__(self) -> None:
        self.plain_text_parser = PlainTextParser()
        self.pdf_parser = PdfParser()
        self.docx_parser = DocxParser()

    def parse(self, source: SourceDocument) -> ParsedDocument:
        file_type = _source_file_type(source)
        if file_type == "pdf":
            return self.pdf_parser.parse(source)
        if file_type == "docx":
            return self.docx_parser.parse(source)
        return self.plain_text_parser.parse(source)


class PlainTextCleaner:
    version = "plain-text-cleaner-p0"

    def clean(self, parsed: ParsedDocument) -> CleanedDocument:
        text = parsed.text.replace("\u00a0", " ")
        text = _CONTROL_CHARS.sub("", text)
        lines = [re.sub(r"[ \t]+", " ", line).rstrip() for line in text.splitlines()]
        compact = "\n".join(lines)
        compact = re.sub(r"\n{3,}", "\n\n", compact).strip()
        if not compact:
            raise ImportServiceError(
                "IMPORT_CLEANED_EMPTY",
                "cleaned document has no text",
                status_code=422,
                retryable=False,
                details={"parser_version": parsed.parser_version},
            )
        return CleanedDocument(
            text=compact,
            cleaner_version=self.version,
            metadata={**parsed.metadata, "parser_version": parsed.parser_version},
        )


class HeadingParagraphChunker:
    version = "heading-paragraph-p0"

    def __init__(self, *, max_chars: int = 1600, overlap_chars: int = 0) -> None:
        self.max_chars = max(max_chars, 200)
        self.overlap_chars = min(max(overlap_chars, 0), self.max_chars // 3)

    def chunk(self, cleaned: CleanedDocument, *, title: str) -> list[ChunkDocument]:
        blocks = _blocks_with_headings(cleaned.text)
        chunks: list[ChunkDocument] = []
        current = ""
        current_heading: str | None = None
        start_block = 0
        for block_index, (heading, block) in enumerate(blocks):
            heading_path = heading or current_heading
            if not current:
                current = block
                current_heading = heading_path
                start_block = block_index
                continue
            if len(current) + len(block) + 2 <= self.max_chars:
                current = f"{current}\n\n{block}"
                current_heading = current_heading or heading_path
                continue
            chunks.extend(
                self._split_chunk(
                    current,
                    title=title,
                    heading_path=current_heading,
                    start_block=start_block,
                    start_ordinal=len(chunks) + 1,
                )
            )
            current = block
            current_heading = heading_path
            start_block = block_index
        if current:
            chunks.extend(
                self._split_chunk(
                    current,
                    title=title,
                    heading_path=current_heading,
                    start_block=start_block,
                    start_ordinal=len(chunks) + 1,
                )
            )
        if not chunks:
            chunks = [
                ChunkDocument(
                    text=cleaned.text,
                    ordinal=1,
                    heading_path=title,
                    token_count=_estimate_token_count(cleaned.text),
                    source_offsets={"block_start": 0, "block_end": 0},
                )
            ]
        return chunks

    def _split_chunk(
        self,
        text: str,
        *,
        title: str,
        heading_path: str | None,
        start_block: int,
        start_ordinal: int,
    ) -> list[ChunkDocument]:
        parts: list[str] = []
        if len(text) <= self.max_chars:
            parts = [text]
        else:
            step = self.max_chars - self.overlap_chars
            for index in range(0, len(text), step):
                part = text[index : index + self.max_chars].strip()
                if part:
                    parts.append(part)
        return [
            ChunkDocument(
                text=part,
                ordinal=start_ordinal + offset,
                heading_path=heading_path or title,
                token_count=_estimate_token_count(part),
                source_offsets={
                    "block_start": start_block,
                    "part_index": offset,
                    "char_count": len(part),
                },
            )
            for offset, part in enumerate(parts)
        ]


_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_CONTENT_TYPE_TO_FILE_TYPE = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/x-markdown": "md",
}
_EXTENSION_TO_FILE_TYPE = {
    "pdf": "pdf",
    "docx": "docx",
    "txt": "txt",
    "text": "txt",
    "md": "md",
    "markdown": "md",
}


def _metadata_text(metadata: dict[str, Any]) -> str | None:
    for key in ("content", "text", "markdown"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _source_file_type(source: SourceDocument) -> str | None:
    metadata_file_type = source.metadata.get("file_type")
    if isinstance(metadata_file_type, str) and metadata_file_type.strip():
        return _normalize_file_type(metadata_file_type)
    extension = _extension_from_name(source.title)
    if extension:
        return _EXTENSION_TO_FILE_TYPE.get(extension)
    if source.content_type:
        return _CONTENT_TYPE_TO_FILE_TYPE.get(source.content_type.lower().split(";")[0].strip())
    return None


def _extension_from_name(name: str | None) -> str | None:
    if not name or "." not in name:
        return None
    extension = name.rsplit(".", 1)[1].strip().lower()
    return extension or None


def _normalize_file_type(value: str) -> str | None:
    normalized = value.strip().lower().lstrip(".")
    return _EXTENSION_TO_FILE_TYPE.get(normalized, normalized or None)


def _empty_source(source: SourceDocument) -> ImportServiceError:
    return ImportServiceError(
        "IMPORT_SOURCE_EMPTY",
        "import source document has no readable content",
        status_code=422,
        retryable=False,
        details={"title": source.title, "object_key": source.object_key},
    )


def _decode_text(content: bytes, *, title: str) -> str:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportServiceError(
        "IMPORT_SOURCE_ENCODING_UNSUPPORTED",
        "source document is not valid UTF-8 text",
        status_code=422,
        retryable=False,
        details={"title": title},
    )


def _blocks_with_headings(text: str) -> list[tuple[str | None, str]]:
    heading: str | None = None
    blocks: list[tuple[str | None, str]] = []
    for raw_block in re.split(r"\n\s*\n", text):
        block = raw_block.strip()
        if not block:
            continue
        first_line = block.splitlines()[0].strip()
        markdown_heading = re.match(r"^(#{1,6})\s+(.+)$", first_line)
        if markdown_heading:
            heading = markdown_heading.group(2).strip()
        blocks.append((heading, block))
    return blocks


def _estimate_token_count(text: str) -> int:
    return max(1, len(text) // 4)
