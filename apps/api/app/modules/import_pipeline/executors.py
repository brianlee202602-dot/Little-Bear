"""导入 parse / clean / chunk 执行器。"""

from __future__ import annotations

import importlib
import re
import zipfile
from dataclasses import dataclass, field, replace
from io import BytesIO
from typing import Any, Literal, Protocol
from xml.etree import ElementTree

from app.modules.import_pipeline.errors import ImportServiceError

BlockType = Literal["heading", "paragraph", "list_item", "table", "code", "page_break"]


@dataclass(frozen=True)
class SourceDocument:
    title: str
    url: str | None = None
    object_key: str | None = None
    content: bytes | None = None
    content_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedBlock:
    text: str
    block_type: BlockType
    heading_level: int | None = None
    page_number: int | None = None
    ordinal: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    parser_version: str
    metadata: dict[str, Any] = field(default_factory=dict)
    blocks: tuple[ParsedBlock, ...] = ()


@dataclass(frozen=True)
class CleanedDocument:
    text: str
    cleaner_version: str
    metadata: dict[str, Any] = field(default_factory=dict)
    blocks: tuple[ParsedBlock, ...] = ()


@dataclass(frozen=True)
class ChunkDocument:
    text: str
    ordinal: int
    heading_path: str | None
    token_count: int
    source_offsets: dict[str, Any]
    page_start: int | None = None
    page_end: int | None = None


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
    version = "plain-text-structure-v1"

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
        file_type = _source_file_type(source) or "txt"
        blocks = _extract_blocks_from_text(
            normalized,
            default_parser=self.version,
            markdown=file_type == "md",
        )
        return ParsedDocument(
            text=normalized,
            parser_version=self.version,
            metadata={
                "title": source.title,
                "url": source.url,
                "object_key": source.object_key,
                "content_type": source.content_type,
                "file_type": file_type,
                "block_count": len(blocks),
            },
            blocks=blocks,
        )


class PdfParser:
    version = "pdf-structure-v1"

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
        parsed_text = "\n\n".join(pages)
        blocks = _extract_blocks_from_text(
            parsed_text,
            default_parser=self.version,
            markdown=False,
        )
        return ParsedDocument(
            text=parsed_text,
            parser_version=self.version,
            metadata={
                "title": source.title,
                "object_key": source.object_key,
                "content_type": source.content_type,
                "page_count": len(reader.pages),
                "file_type": "pdf",
                "block_count": len(blocks),
            },
            blocks=blocks,
        )


class DocxParser:
    version = "docx-structure-v1"
    word_namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    def parse(self, source: SourceDocument) -> ParsedDocument:
        if not source.content:
            raise _empty_source(source)
        try:
            with zipfile.ZipFile(BytesIO(source.content)) as archive:
                document_xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(document_xml)
            paragraph_elements = root.findall(f".//{self.word_namespace}p")
            table_elements = root.findall(f".//{self.word_namespace}tbl")
            blocks = _docx_blocks(root, self.word_namespace)
            text_blocks = [block.text for block in blocks if block.block_type != "page_break"]
            table_count = len(table_elements)
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
                "file_type": "docx",
                "block_count": len(blocks),
            },
            blocks=blocks,
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
    version = "plain-text-cleaner-structure-v1"

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
        blocks = _clean_blocks(parsed.blocks)
        if not blocks:
            blocks = _extract_blocks_from_text(
                compact,
                default_parser=parsed.parser_version,
                markdown=_metadata_file_type(parsed.metadata) == "md",
            )
        return CleanedDocument(
            text=compact,
            cleaner_version=self.version,
            metadata={
                **parsed.metadata,
                "parser_version": parsed.parser_version,
                "cleaned_block_count": len(blocks),
            },
            blocks=blocks,
        )


class StructureAwareChunker:
    version = "structure-aware-v1"

    def __init__(self, *, max_chars: int = 1600, overlap_chars: int = 0) -> None:
        self.max_chars = max(max_chars, 400)
        self.overlap_chars = min(max(overlap_chars, 0), self.max_chars // 3)

    def chunk(self, cleaned: CleanedDocument, *, title: str) -> list[ChunkDocument]:
        source_blocks = cleaned.blocks or _extract_blocks_from_text(
            cleaned.text,
            default_parser=cleaned.metadata.get("parser_version", "cleaned-text"),
            markdown=_metadata_file_type(cleaned.metadata) == "md",
        )
        chunks: list[ChunkDocument] = []
        section_path: list[str] = []
        pending: list[_ChunkBlock] = []
        heading_only_blocks: list[_ChunkBlock] = []

        for block in source_blocks:
            if block.block_type == "page_break":
                continue
            if block.block_type == "heading":
                if pending:
                    chunks.extend(self._emit_blocks(pending, start_ordinal=len(chunks) + 1))
                    pending = []
                heading_only_blocks.append(_chunk_block(block, tuple(section_path), title))
                section_path = _updated_heading_path(section_path, block)
                continue

            chunk_block = _chunk_block(block, tuple(section_path), title)
            if block.block_type in {"table", "code"}:
                if pending:
                    chunks.extend(self._emit_blocks(pending, start_ordinal=len(chunks) + 1))
                    pending = []
                chunks.extend(self._emit_blocks([chunk_block], start_ordinal=len(chunks) + 1))
                continue

            if not pending:
                pending = [chunk_block]
                continue
            same_section = pending[-1].heading_path == chunk_block.heading_path
            pending_text_len = len(_join_block_text(pending))
            if same_section and pending_text_len + len(chunk_block.text) + 2 <= self.max_chars:
                pending.append(chunk_block)
                continue
            chunks.extend(self._emit_blocks(pending, start_ordinal=len(chunks) + 1))
            pending = [chunk_block]

        if pending:
            chunks.extend(self._emit_blocks(pending, start_ordinal=len(chunks) + 1))
        if not chunks and heading_only_blocks:
            chunks.extend(self._emit_blocks(heading_only_blocks, start_ordinal=1))
        if not chunks and cleaned.text.strip():
            chunks.extend(
                self._emit_blocks(
                    [
                        _ChunkBlock(
                            text=cleaned.text.strip(),
                            block_type="paragraph",
                            ordinal=0,
                            heading_path=(title,),
                            page_number=None,
                            char_start=0,
                            char_end=len(cleaned.text),
                        )
                    ],
                    start_ordinal=1,
                )
            )
        return chunks

    def _emit_blocks(
        self,
        blocks: list[_ChunkBlock],
        *,
        start_ordinal: int,
    ) -> list[ChunkDocument]:
        text = _join_block_text(blocks)
        if len(text) <= self.max_chars or _is_atomic_block_group(blocks):
            return [self._chunk_document(text, blocks, ordinal=start_ordinal)]

        parts = _split_text_by_sentence(text, max_chars=self.max_chars)
        return [
            self._chunk_document(
                part,
                blocks,
                ordinal=start_ordinal + offset,
                part_index=offset,
                char_start_override=_safe_char_start(blocks, text, part),
                char_end_override=_safe_char_start(blocks, text, part) + len(part),
            )
            for offset, part in enumerate(parts)
            if part
        ]

    def _chunk_document(
        self,
        text: str,
        blocks: list[_ChunkBlock],
        *,
        ordinal: int,
        part_index: int = 0,
        char_start_override: int | None = None,
        char_end_override: int | None = None,
    ) -> ChunkDocument:
        heading_path = _dominant_heading_path(blocks)
        page_start, page_end = _page_range(blocks)
        char_start = (
            char_start_override
            if char_start_override is not None
            else min(
                (block.char_start for block in blocks if block.char_start is not None),
                default=None,
            )
        )
        char_end = (
            char_end_override
            if char_end_override is not None
            else max(
                (block.char_end for block in blocks if block.char_end is not None),
                default=None,
            )
        )
        block_types = tuple(dict.fromkeys(block.block_type for block in blocks))
        source_offsets: dict[str, Any] = {
            "block_start": min(block.ordinal for block in blocks),
            "block_end": max(block.ordinal for block in blocks),
            "block_types": list(block_types),
            "heading_path": list(heading_path),
            "section_id": _section_id(heading_path),
            "chunk_strategy": "structure_aware",
            "chunker_version": self.version,
            "part_index": part_index,
            "char_count": len(text),
        }
        if char_start is not None:
            source_offsets["char_start"] = char_start
        if char_end is not None:
            source_offsets["char_end"] = char_end
        if page_start is not None:
            source_offsets["page_start"] = page_start
        if page_end is not None:
            source_offsets["page_end"] = page_end
        return ChunkDocument(
            text=text,
            ordinal=ordinal,
            heading_path=_heading_path_text(heading_path),
            token_count=_estimate_token_count(text),
            source_offsets=source_offsets,
            page_start=page_start,
            page_end=page_end,
        )


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
_PAGE_MARKER_PATTERN = re.compile(r"^\[page\s+(\d+)]$", re.IGNORECASE)
_MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")
_LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.+)$")
_SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[。！？!?；;])\s*")


@dataclass(frozen=True)
class _ChunkBlock:
    text: str
    block_type: BlockType
    ordinal: int
    heading_path: tuple[str, ...]
    page_number: int | None
    char_start: int | None
    char_end: int | None


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


def _extract_blocks_from_text(
    text: str,
    *,
    default_parser: str,
    markdown: bool,
) -> tuple[ParsedBlock, ...]:
    blocks: list[ParsedBlock] = []
    paragraph_lines: list[str] = []
    paragraph_start: int | None = None
    current_page: int | None = None
    in_code = False
    code_lines: list[str] = []
    code_start: int | None = None
    offset = 0

    for raw_line in text.splitlines():
        line_start = offset
        offset += len(raw_line) + 1
        line = raw_line.rstrip()
        stripped = line.strip()
        page_match = _PAGE_MARKER_PATTERN.match(stripped)
        if page_match:
            _flush_paragraph(
                blocks,
                paragraph_lines,
                paragraph_start,
                current_page=current_page,
                char_end=line_start,
                parser=default_parser,
            )
            paragraph_lines = []
            paragraph_start = None
            current_page = int(page_match.group(1))
            blocks.append(
                ParsedBlock(
                    text=stripped,
                    block_type="page_break",
                    page_number=current_page,
                    ordinal=len(blocks),
                    metadata={
                        "char_start": line_start,
                        "char_end": line_start + len(raw_line),
                        "parser": default_parser,
                    },
                )
            )
            continue

        if markdown and stripped.startswith("```"):
            if in_code:
                code_lines.append(line)
                blocks.append(
                    ParsedBlock(
                        text="\n".join(code_lines).strip(),
                        block_type="code",
                        page_number=current_page,
                        ordinal=len(blocks),
                        metadata={
                            "char_start": code_start,
                            "char_end": line_start + len(raw_line),
                            "parser": default_parser,
                        },
                    )
                )
                in_code = False
                code_lines = []
                code_start = None
            else:
                _flush_paragraph(
                    blocks,
                    paragraph_lines,
                    paragraph_start,
                    current_page=current_page,
                    char_end=line_start,
                    parser=default_parser,
                )
                paragraph_lines = []
                paragraph_start = None
                in_code = True
                code_start = line_start
                code_lines = [line]
            continue

        if in_code:
            code_lines.append(line)
            continue

        heading_match = _MARKDOWN_HEADING_PATTERN.match(stripped)
        if heading_match:
            _flush_paragraph(
                blocks,
                paragraph_lines,
                paragraph_start,
                current_page=current_page,
                char_end=line_start,
                parser=default_parser,
            )
            paragraph_lines = []
            paragraph_start = None
            blocks.append(
                ParsedBlock(
                    text=heading_match.group(2).strip(),
                    block_type="heading",
                    heading_level=len(heading_match.group(1)),
                    page_number=current_page,
                    ordinal=len(blocks),
                    metadata={
                        "raw": stripped,
                        "char_start": line_start,
                        "char_end": line_start + len(raw_line),
                        "parser": default_parser,
                    },
                )
            )
            continue

        list_match = _LIST_ITEM_PATTERN.match(stripped)
        if list_match:
            _flush_paragraph(
                blocks,
                paragraph_lines,
                paragraph_start,
                current_page=current_page,
                char_end=line_start,
                parser=default_parser,
            )
            paragraph_lines = []
            paragraph_start = None
            blocks.append(
                ParsedBlock(
                    text=list_match.group(1).strip(),
                    block_type="list_item",
                    page_number=current_page,
                    ordinal=len(blocks),
                    metadata={
                        "raw": stripped,
                        "char_start": line_start,
                        "char_end": line_start + len(raw_line),
                        "parser": default_parser,
                    },
                )
            )
            continue

        if not stripped:
            _flush_paragraph(
                blocks,
                paragraph_lines,
                paragraph_start,
                current_page=current_page,
                char_end=line_start,
                parser=default_parser,
            )
            paragraph_lines = []
            paragraph_start = None
            continue

        if paragraph_start is None:
            paragraph_start = line_start
        paragraph_lines.append(stripped)

    if in_code and code_lines:
        blocks.append(
            ParsedBlock(
                text="\n".join(code_lines).strip(),
                block_type="code",
                page_number=current_page,
                ordinal=len(blocks),
                metadata={
                    "char_start": code_start,
                    "char_end": len(text),
                    "parser": default_parser,
                },
            )
        )
    _flush_paragraph(
        blocks,
        paragraph_lines,
        paragraph_start,
        current_page=current_page,
        char_end=len(text),
        parser=default_parser,
    )
    return tuple(blocks)


def _flush_paragraph(
    blocks: list[ParsedBlock],
    lines: list[str],
    start: int | None,
    *,
    current_page: int | None,
    char_end: int,
    parser: str,
) -> None:
    if not lines:
        return
    text = " ".join(line.strip() for line in lines if line.strip()).strip()
    if not text:
        return
    blocks.append(
        ParsedBlock(
            text=text,
            block_type="paragraph",
            page_number=current_page,
            ordinal=len(blocks),
            metadata={"char_start": start, "char_end": char_end, "parser": parser},
        )
    )


def _docx_blocks(root: ElementTree.Element, word_namespace: str) -> tuple[ParsedBlock, ...]:
    body = root.find(f".//{word_namespace}body")
    children = list(body) if body is not None else list(root)
    blocks: list[ParsedBlock] = []
    char_offset = 0
    for child in children:
        tag = _strip_xml_namespace(child.tag)
        if tag == "p":
            text = _docx_paragraph_text(child, word_namespace)
            if not text:
                continue
            heading_level = _docx_heading_level(child, word_namespace)
            block_type: BlockType = "heading" if heading_level else "paragraph"
            blocks.append(
                ParsedBlock(
                    text=text,
                    block_type=block_type,
                    heading_level=heading_level,
                    ordinal=len(blocks),
                    metadata={
                        "char_start": char_offset,
                        "char_end": char_offset + len(text),
                        "parser": "docx",
                    },
                )
            )
            char_offset += len(text) + 2
            continue
        if tag == "tbl":
            text = _docx_table_text(child, word_namespace)
            if not text:
                continue
            blocks.append(
                ParsedBlock(
                    text=text,
                    block_type="table",
                    ordinal=len(blocks),
                    metadata={
                        "char_start": char_offset,
                        "char_end": char_offset + len(text),
                        "parser": "docx",
                        "row_count": len(child.findall(f".//{word_namespace}tr")),
                    },
                )
            )
            char_offset += len(text) + 2
    return tuple(blocks)


def _docx_paragraph_text(paragraph: ElementTree.Element, word_namespace: str) -> str:
    return "".join(
        text_node.text or "" for text_node in paragraph.findall(f".//{word_namespace}t")
    ).strip()


def _docx_heading_level(paragraph: ElementTree.Element, word_namespace: str) -> int | None:
    style = paragraph.find(f".//{word_namespace}pStyle")
    if style is None:
        return None
    style_value = style.attrib.get(f"{word_namespace}val") or style.attrib.get("val") or ""
    match = re.search(r"heading\s*([1-6])", style_value, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 1 if style_value.lower() in {"title", "subtitle"} else None


def _docx_table_text(table: ElementTree.Element, word_namespace: str) -> str:
    rows: list[str] = []
    for row in table.findall(f".//{word_namespace}tr"):
        cells = []
        for cell in row.findall(f"./{word_namespace}tc"):
            cell_text = " ".join(
                _docx_paragraph_text(paragraph, word_namespace)
                for paragraph in cell.findall(f".//{word_namespace}p")
            ).strip()
            if cell_text:
                cells.append(cell_text)
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows).strip()


def _strip_xml_namespace(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def _clean_blocks(blocks: tuple[ParsedBlock, ...]) -> tuple[ParsedBlock, ...]:
    cleaned: list[ParsedBlock] = []
    for block in blocks:
        text = block.text.replace("\u00a0", " ")
        text = _CONTROL_CHARS.sub("", text)
        text = "\n".join(re.sub(r"[ \t]+", " ", line).rstrip() for line in text.splitlines())
        text = text.strip()
        if text:
            cleaned.append(replace(block, text=text, ordinal=len(cleaned)))
    return tuple(cleaned)


def _metadata_file_type(metadata: dict[str, Any]) -> str | None:
    value = metadata.get("file_type")
    return value.strip().lower() if isinstance(value, str) and value.strip() else None


def _chunk_block(block: ParsedBlock, heading_path: tuple[str, ...], title: str) -> _ChunkBlock:
    return _ChunkBlock(
        text=block.text,
        block_type=block.block_type,
        ordinal=block.ordinal,
        heading_path=heading_path or (title,),
        page_number=block.page_number,
        char_start=_metadata_int(block.metadata, "char_start"),
        char_end=_metadata_int(block.metadata, "char_end"),
    )


def _updated_heading_path(current: list[str], block: ParsedBlock) -> list[str]:
    level = block.heading_level or 1
    next_path = list(current[: max(level - 1, 0)])
    next_path.append(block.text)
    return next_path


def _join_block_text(blocks: list[_ChunkBlock]) -> str:
    return "\n\n".join(block.text for block in blocks if block.text).strip()


def _is_atomic_block_group(blocks: list[_ChunkBlock]) -> bool:
    return len(blocks) == 1 and blocks[0].block_type in {"table", "code"}


def _dominant_heading_path(blocks: list[_ChunkBlock]) -> tuple[str, ...]:
    for block in blocks:
        if block.heading_path:
            return block.heading_path
    return ()


def _page_range(blocks: list[_ChunkBlock]) -> tuple[int | None, int | None]:
    pages = [block.page_number for block in blocks if block.page_number is not None]
    if not pages:
        return None, None
    return min(pages), max(pages)


def _heading_path_text(path: tuple[str, ...]) -> str | None:
    return " / ".join(part for part in path if part) or None


def _section_id(path: tuple[str, ...]) -> str | None:
    return "/".join(part.strip().replace("/", "-") for part in path if part.strip()) or None


def _split_text_by_sentence(text: str, *, max_chars: int) -> list[str]:
    sentences = [part.strip() for part in _SENTENCE_BOUNDARY_PATTERN.split(text) if part.strip()]
    if not sentences:
        return _split_text_by_chars(text, max_chars=max_chars)
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                parts.append(current)
                current = ""
            parts.extend(_split_text_by_chars(sentence, max_chars=max_chars))
            continue
        if not current:
            current = sentence
            continue
        if len(current) + len(sentence) + 1 <= max_chars:
            current = f"{current}{sentence}"
            continue
        parts.append(current)
        current = sentence
    if current:
        parts.append(current)
    return parts


def _split_text_by_chars(text: str, *, max_chars: int) -> list[str]:
    return [
        text[index : index + max_chars].strip()
        for index in range(0, len(text), max_chars)
        if text[index : index + max_chars].strip()
    ]


def _safe_char_start(blocks: list[_ChunkBlock], full_text: str, part: str) -> int:
    base_start = min(
        (block.char_start for block in blocks if block.char_start is not None),
        default=0,
    )
    return base_start + max(full_text.find(part), 0)


def _metadata_int(metadata: dict[str, Any], key: str) -> int | None:
    value = metadata.get(key)
    return value if isinstance(value, int) else None


def _estimate_token_count(text: str) -> int:
    return max(1, len(text) // 4)
