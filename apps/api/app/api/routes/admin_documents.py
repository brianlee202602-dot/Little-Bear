"""管理后台文档 API。"""

from __future__ import annotations

from app.api.routes.admin_shared import (
    AcceptedResponse,
    AdminChunkListResponse,
    AdminDocumentPreviewResponse,
    AdminDocumentVersionListResponse,
    AdminService,
    AdminServiceError,
    APIRouter,
    AuthServiceError,
    DocumentListResponse,
    DocumentPatchRequest,
    DocumentResponse,
    Header,
    JSONResponse,
    PaginationData,
    Query,
    SQLAlchemyError,
    _accepted_data,
    _actor_context,
    _admin_chunk_data,
    _admin_document_preview_data,
    _admin_error_response,
    _auth_error_response,
    _authenticate,
    _database_error_response,
    _document_data,
    _document_list_item_data,
    _document_version_data,
    _extract_bearer_token,
    _request_id,
    session_scope,
    status,
)

router = APIRouter(prefix="/internal/v1/admin", tags=["admin-documents"])


@router.get(
    "/knowledge-bases/{kb_id}/documents",
    response_model=DocumentListResponse,
)
async def list_documents(
    kb_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    status_filter: str | None = Query(default=None, alias="status"),
    authorization: str | None = Header(default=None),
) -> DocumentListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:manage")
            result = service.list_documents(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                kb_id=kb_id,
                page=page,
                page_size=page_size,
                lifecycle_status=status_filter,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_document_list")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_document_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_document_list")
    return DocumentListResponse(
        request_id=_request_id(),
        data=[_document_list_item_data(document) for document in result.items],
        pagination=PaginationData(page=page, page_size=page_size, total=result.total),
    )


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    authorization: str | None = Header(default=None),
) -> DocumentResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:manage")
            document = service.get_document(
                session,
                doc_id,
                enterprise_id=auth_context.user.enterprise_id,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_document_get")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_document_get")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_document_get")
    return DocumentResponse(request_id=_request_id(), data=_document_data(document))


@router.get("/documents/{doc_id}/versions", response_model=AdminDocumentVersionListResponse)
async def list_document_versions(
    doc_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    authorization: str | None = Header(default=None),
) -> AdminDocumentVersionListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:manage")
            versions = service.list_document_versions(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                doc_id=doc_id,
                page=page,
                page_size=page_size,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_document_version_list")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_document_version_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_document_version_list")
    return AdminDocumentVersionListResponse(
        request_id=_request_id(),
        data=[_document_version_data(version) for version in versions.items],
        pagination={"page": page, "page_size": page_size, "total": versions.total},
    )


@router.get("/documents/{doc_id}/chunks", response_model=AdminChunkListResponse)
async def list_document_chunks(
    doc_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    authorization: str | None = Header(default=None),
) -> AdminChunkListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:manage")
            chunks = service.list_document_chunks(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                doc_id=doc_id,
                page=page,
                page_size=page_size,
                keyword=keyword,
                status=status_filter,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_document_chunk_list")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_document_chunk_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_document_chunk_list")
    return AdminChunkListResponse(
        request_id=_request_id(),
        data=[_admin_chunk_data(chunk) for chunk in chunks.items],
        pagination={"page": page, "page_size": page_size, "total": chunks.total},
    )


@router.get("/documents/{doc_id}/preview", response_model=AdminDocumentPreviewResponse)
async def get_document_preview(
    doc_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    authorization: str | None = Header(default=None),
) -> AdminDocumentPreviewResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:manage")
            preview = service.get_document_preview(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                doc_id=doc_id,
                page=page,
                page_size=page_size,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_document_preview")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_document_preview")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_document_preview")
    return AdminDocumentPreviewResponse(
        request_id=_request_id(),
        data=_admin_document_preview_data(preview),
        pagination={"page": page, "page_size": page_size, "total": preview.total},
    )



@router.patch("/documents/{doc_id}", response_model=DocumentResponse)
async def patch_document(
    doc_id: str,
    payload: DocumentPatchRequest,
    authorization: str | None = Header(default=None),
    x_document_confirm: str | None = Header(default=None),
) -> DocumentResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:manage")
            document = service.patch_document(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                doc_id=doc_id,
                title=payload.title,
                folder_id=payload.folder_id,
                folder_id_provided="folder_id" in payload.model_fields_set,
                tags=payload.tags,
                tags_provided="tags" in payload.model_fields_set,
                owner_department_id=payload.owner_department_id,
                visibility=payload.visibility,
                lifecycle_status=payload.lifecycle_status,
                confirmed_visibility_expand=x_document_confirm == "visibility-expand",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_document_patch")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_document_patch")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_document_patch")
    return DocumentResponse(request_id=_request_id(), data=_document_data(document))


@router.delete(
    "/documents/{doc_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AcceptedResponse,
)
async def delete_document(
    doc_id: str,
    authorization: str | None = Header(default=None),
    x_document_confirm: str | None = Header(default=None),
) -> AcceptedResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:manage")
            result = service.delete_document(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                doc_id=doc_id,
                confirmed=x_document_confirm == "delete",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_document_delete")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_document_delete")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_document_delete")
    return AcceptedResponse(request_id=_request_id(), data=_accepted_data(result))
