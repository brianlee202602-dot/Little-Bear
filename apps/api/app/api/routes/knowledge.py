"""普通用户知识库浏览 API。"""

from __future__ import annotations

from fastapi import APIRouter, Header, Query
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from app.api.schemas.knowledge import (
    ChunkData,
    ChunkListResponse,
    DocumentData,
    DocumentListResponse,
    DocumentPreviewData,
    DocumentPreviewResponse,
    DocumentResponse,
    DocumentVersionData,
    DocumentVersionListResponse,
    KnowledgeBaseData,
    KnowledgeBaseListResponse,
    PaginationData,
)
from app.api.schemas.query import CitationData
from app.db.session import session_scope
from app.modules.auth.errors import AuthServiceError
from app.modules.auth.service import AuthService
from app.modules.knowledge import (
    AccessibleChunk,
    AccessibleDocument,
    AccessibleDocumentPreview,
    AccessibleDocumentVersion,
    AccessibleKnowledgeBase,
    KnowledgeService,
    KnowledgeServiceError,
)
from app.shared.context import get_request_context

router = APIRouter(prefix="/internal/v1", tags=["knowledge"])


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
        data=[_document_data(item) for item in result.items],
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
        data=[_document_version_data(item) for item in versions],
    )


@router.get("/documents/{doc_id}/chunks", response_model=ChunkListResponse)
async def list_document_chunks(
    doc_id: str,
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
        data=[_chunk_data(item) for item in chunks],
    )


@router.get("/documents/{doc_id}/preview", response_model=DocumentPreviewResponse)
async def get_document_preview(
    doc_id: str,
    authorization: str | None = Header(default=None),
) -> DocumentPreviewResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = KnowledgeService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:read")
            preview = service.get_document_preview(
                session,
                user_id=auth_context.user.id,
                enterprise_id=auth_context.user.enterprise_id,
                document_id=doc_id,
                request_id=_request_id(),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="document_preview")
    except KnowledgeServiceError as exc:
        return _knowledge_error_response(exc, stage="document_preview")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="document_preview")
    return DocumentPreviewResponse(request_id=_request_id(), data=_document_preview_data(preview))


def _authenticate(session: object, token: str | None, *, required_scope: str):
    return AuthService().authenticate_access_token(
        session,
        access_token=token or "",
        required_scope=required_scope,
    )


def _knowledge_base_data(item: AccessibleKnowledgeBase) -> KnowledgeBaseData:
    return KnowledgeBaseData(
        id=item.id,
        name=item.name,
        status=item.status,
        owner_department_id=item.owner_department_id,
        default_visibility=item.default_visibility,
        config_scope_id=item.config_scope_id,
        policy_version=item.policy_version,
    )


def _document_data(item: AccessibleDocument) -> DocumentData:
    return DocumentData(
        id=item.id,
        kb_id=item.kb_id,
        folder_id=item.folder_id,
        title=item.title,
        lifecycle_status=item.lifecycle_status,
        index_status=item.index_status,
        owner_department_id=item.owner_department_id,
        visibility=item.visibility,
        current_version_id=item.current_version_id,
    )


def _document_version_data(item: AccessibleDocumentVersion) -> DocumentVersionData:
    return DocumentVersionData(
        id=item.id,
        document_id=item.document_id,
        version_no=item.version_no,
        status=item.status,
    )


def _chunk_data(item: AccessibleChunk) -> ChunkData:
    return ChunkData(
        id=item.id,
        document_id=item.document_id,
        document_version_id=item.document_version_id,
        text_preview=item.text_preview,
        page_start=item.page_start,
        page_end=item.page_end,
        status=item.status,
    )


def _document_preview_data(item: AccessibleDocumentPreview) -> DocumentPreviewData:
    return DocumentPreviewData(
        doc_id=item.doc_id,
        title=item.title,
        preview=item.preview,
        citations=[
            CitationData(
                source_id=citation.source_id,
                doc_id=citation.doc_id,
                document_version_id=citation.document_version_id,
                title=citation.title,
                page_start=citation.page_start,
                page_end=citation.page_end,
                score=citation.score,
            )
            for citation in item.citations
        ],
    )


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def _request_id() -> str:
    request_context = get_request_context()
    return request_context.request_id if request_context else "req_unknown"


def _auth_error_response(exc: AuthServiceError, *, stage: str) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "request_id": _request_id(),
            "error_code": exc.error_code,
            "message": exc.message,
            "stage": stage,
            "retryable": exc.retryable,
            "details": exc.details,
        },
    )


def _knowledge_error_response(exc: KnowledgeServiceError, *, stage: str) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "request_id": _request_id(),
            "error_code": exc.error_code,
            "message": exc.message,
            "stage": stage,
            "retryable": exc.retryable,
            "details": exc.details,
        },
    )


def _database_error_response(exc: SQLAlchemyError, *, stage: str) -> JSONResponse:
    original = getattr(exc, "orig", None) or exc.__cause__
    return JSONResponse(
        status_code=500,
        content={
            "request_id": _request_id(),
            "error_code": "KNOWLEDGE_DATABASE_ERROR",
            "message": "knowledge database operation failed",
            "stage": stage,
            "retryable": True,
            "details": {
                "database_error": {
                    "type": exc.__class__.__name__,
                    "driver": original.__class__.__name__ if original is not None else None,
                }
            },
        },
    )
