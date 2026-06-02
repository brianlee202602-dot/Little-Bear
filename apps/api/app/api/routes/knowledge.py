"""普通用户知识库浏览 API。"""

from __future__ import annotations

from functools import partial

from fastapi import APIRouter, Header, Query
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from app.api.dependencies.auth import (
    authenticate_required_scope as _authenticate,
)
from app.api.dependencies.auth import (
    current_request_id as _request_id,
)
from app.api.dependencies.auth import (
    extract_bearer_token as _extract_bearer_token,
)
from app.api.errors import database_error_response, service_error_response
from app.api.presenters.knowledge import (
    chunk_data as _chunk_data,
)
from app.api.presenters.knowledge import (
    citation_source_data as _citation_source_data,
)
from app.api.presenters.knowledge import (
    document_data as _document_data,
)
from app.api.presenters.knowledge import (
    document_list_item_data as _document_list_item_data,
)
from app.api.presenters.knowledge import (
    document_version_data as _document_version_data,
)
from app.api.presenters.knowledge import (
    folder_data as _folder_data,
)
from app.api.presenters.knowledge import (
    knowledge_base_data as _knowledge_base_data,
)
from app.api.schemas.common import PaginationData
from app.api.schemas.knowledge import (
    ChunkListResponse,
    CitationSourceResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentVersionListResponse,
    FolderListResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
)
from app.db.session import session_scope
from app.modules.auth.errors import AuthServiceError
from app.modules.knowledge import (
    KnowledgeService,
    KnowledgeServiceError,
)

router = APIRouter(prefix="/internal/v1", tags=["knowledge"])

_auth_error_response = service_error_response
_knowledge_error_response = service_error_response
_database_error_response = partial(
    database_error_response,
    error_code="KNOWLEDGE_DATABASE_ERROR",
    message="knowledge database operation failed",
)


@router.get("/knowledge-bases", response_model=KnowledgeBaseListResponse)
async def list_knowledge_bases(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    keyword: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    authorization: str | None = Header(default=None),
) -> KnowledgeBaseListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = KnowledgeService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="knowledge_base:read")
            result = service.list_knowledge_bases(
                session,
                user_id=auth_context.user.id,
                enterprise_id=auth_context.user.enterprise_id,
                page=page,
                page_size=page_size,
                keyword=keyword,
                status=status_filter,
                request_id=_request_id(),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="knowledge_base_list")
    except KnowledgeServiceError as exc:
        return _knowledge_error_response(exc, stage="knowledge_base_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="knowledge_base_list")
    return KnowledgeBaseListResponse(
        request_id=_request_id(),
        data=[_knowledge_base_data(item) for item in result.items],
        pagination=PaginationData(page=page, page_size=page_size, total=result.total),
    )


@router.get("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: str,
    authorization: str | None = Header(default=None),
) -> KnowledgeBaseResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = KnowledgeService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="knowledge_base:read")
            item = service.get_knowledge_base(
                session,
                user_id=auth_context.user.id,
                enterprise_id=auth_context.user.enterprise_id,
                kb_id=kb_id,
                request_id=_request_id(),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="knowledge_base_get")
    except KnowledgeServiceError as exc:
        return _knowledge_error_response(exc, stage="knowledge_base_get")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="knowledge_base_get")
    return KnowledgeBaseResponse(request_id=_request_id(), data=_knowledge_base_data(item))


@router.get("/knowledge-bases/{kb_id}/folders", response_model=FolderListResponse)
async def list_folders(
    kb_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    authorization: str | None = Header(default=None),
) -> FolderListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = KnowledgeService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="knowledge_base:read")
            result = service.list_folders(
                session,
                user_id=auth_context.user.id,
                enterprise_id=auth_context.user.enterprise_id,
                kb_id=kb_id,
                page=page,
                page_size=page_size,
                request_id=_request_id(),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="folder_list")
    except KnowledgeServiceError as exc:
        return _knowledge_error_response(exc, stage="folder_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="folder_list")
    return FolderListResponse(
        request_id=_request_id(),
        data=[_folder_data(item) for item in result.items],
        pagination=PaginationData(page=page, page_size=page_size, total=result.total),
    )


@router.get("/knowledge-bases/{kb_id}/documents", response_model=DocumentListResponse)
async def list_documents(
    kb_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    keyword: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    authorization: str | None = Header(default=None),
) -> DocumentListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = KnowledgeService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:read")
            result = service.list_documents(
                session,
                user_id=auth_context.user.id,
                enterprise_id=auth_context.user.enterprise_id,
                kb_id=kb_id,
                page=page,
                page_size=page_size,
                keyword=keyword,
                status=status_filter,
                request_id=_request_id(),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="document_list")
    except KnowledgeServiceError as exc:
        return _knowledge_error_response(exc, stage="document_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="document_list")
    return DocumentListResponse(
        request_id=_request_id(),
        data=[_document_list_item_data(item) for item in result.items],
        pagination=PaginationData(page=page, page_size=page_size, total=result.total),
    )


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    authorization: str | None = Header(default=None),
) -> DocumentResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = KnowledgeService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:read")
            document = service.get_document(
                session,
                user_id=auth_context.user.id,
                enterprise_id=auth_context.user.enterprise_id,
                document_id=doc_id,
                request_id=_request_id(),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="document_get")
    except KnowledgeServiceError as exc:
        return _knowledge_error_response(exc, stage="document_get")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="document_get")
    return DocumentResponse(request_id=_request_id(), data=_document_data(document))


@router.get("/documents/{doc_id}/versions", response_model=DocumentVersionListResponse)
async def list_document_versions(
    doc_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    authorization: str | None = Header(default=None),
) -> DocumentVersionListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = KnowledgeService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:read")
            versions = service.list_document_versions(
                session,
                user_id=auth_context.user.id,
                enterprise_id=auth_context.user.enterprise_id,
                document_id=doc_id,
                page=page,
                page_size=page_size,
                request_id=_request_id(),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="document_version_list")
    except KnowledgeServiceError as exc:
        return _knowledge_error_response(exc, stage="document_version_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="document_version_list")
    return DocumentVersionListResponse(
        request_id=_request_id(),
        data=[_document_version_data(item) for item in versions.items],
        pagination=PaginationData(page=page, page_size=page_size, total=versions.total),
    )


@router.get("/documents/{doc_id}/chunks", response_model=ChunkListResponse)
async def list_document_chunks(
    doc_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    authorization: str | None = Header(default=None),
) -> ChunkListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = KnowledgeService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:read")
            chunks = service.list_document_chunks(
                session,
                user_id=auth_context.user.id,
                enterprise_id=auth_context.user.enterprise_id,
                document_id=doc_id,
                page=page,
                page_size=page_size,
                keyword=keyword,
                status=status_filter,
                request_id=_request_id(),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="document_chunk_list")
    except KnowledgeServiceError as exc:
        return _knowledge_error_response(exc, stage="document_chunk_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="document_chunk_list")
    return ChunkListResponse(
        request_id=_request_id(),
        data=[_chunk_data(item) for item in chunks.items],
        pagination=PaginationData(page=page, page_size=page_size, total=chunks.total),
    )


@router.get(
    "/documents/{doc_id}/sources/{source_id}",
    response_model=CitationSourceResponse,
)
async def get_document_source(
    doc_id: str,
    source_id: str,
    authorization: str | None = Header(default=None),
) -> CitationSourceResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = KnowledgeService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:read")
            source = service.get_document_source(
                session,
                user_id=auth_context.user.id,
                enterprise_id=auth_context.user.enterprise_id,
                document_id=doc_id,
                source_id=source_id,
                request_id=_request_id(),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="document_source")
    except KnowledgeServiceError as exc:
        return _knowledge_error_response(exc, stage="document_source")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="document_source")
    return CitationSourceResponse(request_id=_request_id(), data=_citation_source_data(source))
