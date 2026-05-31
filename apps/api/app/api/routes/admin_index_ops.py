"""管理后台索引运维 API。"""

from __future__ import annotations

from app.api.routes.admin_shared import (
    AcceptedResponse,
    AdminService,
    AdminServiceError,
    APIRouter,
    AuthServiceError,
    Header,
    IndexCollectionOperationResponse,
    IndexCollectionSnapshotListResponse,
    IndexCollectionSnapshotRecoverRequest,
    IndexCollectionSnapshotResponse,
    IndexHealthResponse,
    IndexingServiceError,
    IndexJobCreateRequest,
    IndexVersionCleanupJobCreateRequest,
    IndexVersionListResponse,
    JSONResponse,
    PaginationData,
    Query,
    SQLAlchemyError,
    _accepted_data,
    _actor_context,
    _admin_error_response,
    _auth_error_response,
    _authenticate,
    _compat,
    _database_error_response,
    _extract_bearer_token,
    _index_collection_health_data,
    _index_collection_operation_data,
    _index_collection_snapshot_data,
    _index_version_data,
    _indexing_error_response,
    _request_id,
    status,
)

router = APIRouter(prefix="/internal/v1/admin", tags=["admin-index-ops"])


@router.get("/documents/{doc_id}/index-versions", response_model=IndexVersionListResponse)
async def list_document_index_versions(
    doc_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    authorization: str | None = Header(default=None),
) -> IndexVersionListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:index")
            versions = service.list_document_index_versions(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                doc_id=doc_id,
                page=page,
                page_size=page_size,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_document_index_version_list")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_document_index_version_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_document_index_version_list")
    return IndexVersionListResponse(
        request_id=_request_id(),
        data=[_index_version_data(version) for version in versions.items],
        pagination=PaginationData(page=page, page_size=page_size, total=versions.total),
    )


@router.post(
    "/documents/{doc_id}/index-jobs",
    response_model=AcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_document_index_job(
    doc_id: str,
    authorization: str | None = Header(default=None),
    x_index_confirm: str | None = Header(default=None),
) -> AcceptedResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:index")
            result = service.create_document_index_rebuild_job(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                doc_id=doc_id,
                confirmed=x_index_confirm == "rebuild",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_document_index_job_create")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_document_index_job_create")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_document_index_job_create")
    return AcceptedResponse(request_id=_request_id(), data=_accepted_data(result))


@router.get("/index-health", response_model=IndexHealthResponse)
async def get_index_health(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    authorization: str | None = Header(default=None),
) -> IndexHealthResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:index")
            collections = _compat().build_index_ops_service(session).list_collection_health(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                page=page,
                page_size=page_size,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_index_health")
    except IndexingServiceError as exc:
        return _admin_error_response(
            AdminServiceError(
                exc.error_code,
                exc.message,
                status_code=exc.status_code,
                retryable=exc.retryable,
                details=exc.details,
            ),
            stage="admin_index_health",
        )
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_index_health")
    return IndexHealthResponse(
        request_id=_request_id(),
        data=[_index_collection_health_data(item) for item in collections.items],
        pagination=PaginationData(page=page, page_size=page_size, total=collections.total),
    )


@router.get(
    "/index-collections/{collection_name}/snapshots",
    response_model=IndexCollectionSnapshotListResponse,
)
async def list_index_collection_snapshots(
    collection_name: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    authorization: str | None = Header(default=None),
) -> IndexCollectionSnapshotListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:index")
            snapshots = _compat().build_index_ops_service(session).list_collection_snapshots(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                collection_name=collection_name,
                page=page,
                page_size=page_size,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_index_collection_snapshot_list")
    except IndexingServiceError as exc:
        return _indexing_error_response(exc, stage="admin_index_collection_snapshot_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_index_collection_snapshot_list")
    return IndexCollectionSnapshotListResponse(
        request_id=_request_id(),
        data=[_index_collection_snapshot_data(item) for item in snapshots.items],
        pagination=PaginationData(page=page, page_size=page_size, total=snapshots.total),
    )


@router.post(
    "/index-collections/{collection_name}/snapshots",
    response_model=IndexCollectionSnapshotResponse,
)
async def create_index_collection_snapshot(
    collection_name: str,
    authorization: str | None = Header(default=None),
    x_index_confirm: str | None = Header(default=None),
) -> IndexCollectionSnapshotResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:index")
            snapshot = _compat().build_index_ops_service(session).create_collection_snapshot(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                collection_name=collection_name,
                confirmed=x_index_confirm == "snapshot",
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_index_collection_snapshot_create")
    except IndexingServiceError as exc:
        return _indexing_error_response(exc, stage="admin_index_collection_snapshot_create")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_index_collection_snapshot_create")
    return IndexCollectionSnapshotResponse(
        request_id=_request_id(),
        data=_index_collection_snapshot_data(snapshot),
    )


@router.put(
    "/index-collections/{collection_name}/snapshot-recoveries",
    response_model=IndexCollectionOperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def recover_index_collection_snapshot(
    collection_name: str,
    payload: IndexCollectionSnapshotRecoverRequest,
    authorization: str | None = Header(default=None),
    x_index_confirm: str | None = Header(default=None),
) -> IndexCollectionOperationResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:index")
            result = _compat().build_index_ops_service(session).recover_collection_snapshot(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                collection_name=collection_name,
                location=payload.location,
                priority=payload.priority,
                checksum=payload.checksum,
                confirmed=x_index_confirm == "restore",
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_index_collection_snapshot_recover")
    except IndexingServiceError as exc:
        return _indexing_error_response(exc, stage="admin_index_collection_snapshot_recover")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_index_collection_snapshot_recover")
    return IndexCollectionOperationResponse(
        request_id=_request_id(),
        data=_index_collection_operation_data(result),
    )


@router.post(
    "/index-collections/{collection_name}/rebuild-jobs",
    response_model=AcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_index_collection_rebuild_job(
    collection_name: str,
    authorization: str | None = Header(default=None),
    x_index_confirm: str | None = Header(default=None),
) -> AcceptedResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:index")
            result = service.create_collection_index_rebuild_job(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                collection_name=collection_name,
                confirmed=x_index_confirm == "rebuild",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_index_collection_rebuild")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_index_collection_rebuild")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_index_collection_rebuild")
    return AcceptedResponse(request_id=_request_id(), data=_accepted_data(result))


@router.post(
    "/index-jobs",
    response_model=AcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_index_job(
    payload: IndexJobCreateRequest,
    authorization: str | None = Header(default=None),
    x_index_confirm: str | None = Header(default=None),
) -> AcceptedResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:index")
            result = service.create_index_rebuild_job(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                kb_id=payload.kb_id,
                document_ids=payload.document_ids,
                confirmed=x_index_confirm == "rebuild",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_index_job_create")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_index_job_create")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_index_job_create")
    return AcceptedResponse(request_id=_request_id(), data=_accepted_data(result))


@router.post(
    "/index-versions/cleanup-jobs",
    response_model=AcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_index_version_cleanup_job(
    payload: IndexVersionCleanupJobCreateRequest,
    authorization: str | None = Header(default=None),
    x_index_confirm: str | None = Header(default=None),
) -> AcceptedResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:index")
            result = service.create_index_version_cleanup_job(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                index_version_ids=payload.index_version_ids,
                confirmed=x_index_confirm == "cleanup",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_index_version_cleanup_job_create")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_index_version_cleanup_job_create")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_index_version_cleanup_job_create")
    return AcceptedResponse(request_id=_request_id(), data=_accepted_data(result))
