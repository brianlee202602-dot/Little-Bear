"""普通用户知识库响应 DTO 映射。"""

from __future__ import annotations

from app.api.schemas.knowledge import (
    ChunkData,
    CitationSourceData,
    DocumentData,
    DocumentListItemData,
    DocumentVersionData,
    FolderData,
    KnowledgeBaseData,
)
from app.modules.knowledge import (
    AccessibleChunk,
    AccessibleCitationSource,
    AccessibleDocument,
    AccessibleDocumentListItem,
    AccessibleDocumentVersion,
    AccessibleFolder,
    AccessibleKnowledgeBase,
)


def knowledge_base_data(item: AccessibleKnowledgeBase) -> KnowledgeBaseData:
    return KnowledgeBaseData(
        id=item.id,
        name=item.name,
        status=item.status,
    )


def folder_data(item: AccessibleFolder) -> FolderData:
    return FolderData(
        id=item.id,
        kb_id=item.kb_id,
        parent_id=item.parent_id,
        name=item.name,
        status=item.status,
    )


def document_data(item: AccessibleDocument) -> DocumentData:
    return DocumentData(
        id=item.id,
        title=item.title,
        lifecycle_status=item.lifecycle_status,
        index_status=item.index_status,
        updated_at=item.updated_at,
        can_view=item.can_view,
        can_cite=item.can_cite,
    )


def document_list_item_data(item: AccessibleDocumentListItem) -> DocumentListItemData:
    return DocumentListItemData(
        id=item.id,
        title=item.title,
        lifecycle_status=item.lifecycle_status,
        index_status=item.index_status,
        updated_at=item.updated_at,
        can_view=item.can_view,
        can_cite=item.can_cite,
    )


def document_version_data(item: AccessibleDocumentVersion) -> DocumentVersionData:
    return DocumentVersionData(
        id=item.id,
        document_id=item.document_id,
        version_no=item.version_no,
        status=item.status,
    )


def chunk_data(item: AccessibleChunk) -> ChunkData:
    return ChunkData(
        id=item.id,
        document_id=item.document_id,
        document_version_id=item.document_version_id,
        text_preview=item.text_preview,
        page_start=item.page_start,
        page_end=item.page_end,
        status=item.status,
        ordinal=item.ordinal,
    )


def citation_source_data(item: AccessibleCitationSource) -> CitationSourceData:
    return CitationSourceData(
        source_id=item.source_id,
        doc_id=item.doc_id,
        document_version_id=item.document_version_id,
        title=item.title,
        text=item.text,
        text_preview=item.text_preview,
        page_start=item.page_start,
        page_end=item.page_end,
        ordinal=item.ordinal,
        heading_path=item.heading_path,
        source_offsets=item.source_offsets,
        text_status=item.text_status,
    )
