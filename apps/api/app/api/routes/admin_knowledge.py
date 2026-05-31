"""管理后台知识库与文件夹 API。"""

from __future__ import annotations

from app.api.routes.admin_shared import (
    AcceptedResponse,
    AdminKnowledgeBaseAccessRuleInput,
    AdminService,
    AdminServiceError,
    APIRouter,
    AuthServiceError,
    FolderCreateRequest,
    FolderListResponse,
    FolderOptionListResponse,
    FolderPatchRequest,
    FolderResponse,
    Header,
    JSONResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseListResponse,
    KnowledgeBaseOptionListResponse,
    KnowledgeBasePatchRequest,
    KnowledgeBaseResponse,
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
    _folder_data,
    _folder_option_data,
    _knowledge_base_data,
    _knowledge_base_list_item_data,
    _knowledge_base_option_data,
    _request_id,
    status,
)

router = APIRouter(prefix="/internal/v1/admin", tags=["admin-knowledge"])


@router.get("/knowledge-bases", response_model=KnowledgeBaseListResponse)
async def list_knowledge_bases(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    keyword: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    authorization: str | None = Header(default=None),
) -> KnowledgeBaseListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="knowledge_base:manage")
            result = service.list_knowledge_bases(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                page=page,
                page_size=page_size,
                keyword=keyword,
                status=status_filter,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_knowledge_base_list")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_knowledge_base_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_knowledge_base_list")
    return KnowledgeBaseListResponse(
        request_id=_request_id(),
        data=[
            _knowledge_base_list_item_data(knowledge_base) for knowledge_base in result.items
        ],
        pagination=PaginationData(page=page, page_size=page_size, total=result.total),
    )


@router.get("/knowledge-base-options", response_model=KnowledgeBaseOptionListResponse)
async def list_knowledge_base_options(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    authorization: str | None = Header(default=None),
) -> KnowledgeBaseOptionListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="knowledge_base:manage")
            result = service.list_knowledge_base_options(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                page=page,
                page_size=page_size,
                keyword=keyword,
                status=status_filter,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_knowledge_base_options")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_knowledge_base_options")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_knowledge_base_options")
    return KnowledgeBaseOptionListResponse(
        request_id=_request_id(),
        data=[_knowledge_base_option_data(knowledge_base) for knowledge_base in result.items],
        pagination=PaginationData(page=page, page_size=page_size, total=result.total),
    )


@router.post(
    "/knowledge-bases",
    status_code=status.HTTP_201_CREATED,
    response_model=KnowledgeBaseResponse,
)
async def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    authorization: str | None = Header(default=None),
    x_knowledge_base_confirm: str | None = Header(default=None),
) -> KnowledgeBaseResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="knowledge_base:manage")
            knowledge_base = service.create_knowledge_base(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                name=payload.name,
                owner_department_id=payload.owner_department_id,
                kb_visibility=payload.kb_visibility,
                default_document_visibility=payload.default_document_visibility,
                default_document_owner_department_id=(
                    payload.default_document_owner_department_id
                ),
                access_rules=[
                    AdminKnowledgeBaseAccessRuleInput(
                        subject_type=rule.subject_type,
                        subject_id=rule.subject_id,
                        permission=rule.permission,
                    )
                    for rule in payload.access_rules
                ],
                config_scope_id=payload.config_scope_id,
                confirmed_enterprise_visibility=(
                    x_knowledge_base_confirm == "enterprise-visible"
                ),
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_knowledge_base_create")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_knowledge_base_create")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_knowledge_base_create")
    return KnowledgeBaseResponse(
        request_id=_request_id(),
        data=_knowledge_base_data(knowledge_base),
    )


@router.get("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: str,
    authorization: str | None = Header(default=None),
) -> KnowledgeBaseResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="knowledge_base:manage")
            knowledge_base = service.get_knowledge_base(
                session,
                kb_id,
                enterprise_id=auth_context.user.enterprise_id,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_knowledge_base_get")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_knowledge_base_get")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_knowledge_base_get")
    return KnowledgeBaseResponse(
        request_id=_request_id(),
        data=_knowledge_base_data(knowledge_base),
    )


@router.patch("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def patch_knowledge_base(
    kb_id: str,
    payload: KnowledgeBasePatchRequest,
    authorization: str | None = Header(default=None),
    x_knowledge_base_confirm: str | None = Header(default=None),
) -> KnowledgeBaseResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="knowledge_base:manage")
            knowledge_base = service.patch_knowledge_base(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                kb_id=kb_id,
                name=payload.name,
                status=payload.status,
                kb_visibility=payload.kb_visibility,
                default_document_visibility=payload.default_document_visibility,
                default_document_owner_department_id=(
                    payload.default_document_owner_department_id
                ),
                config_scope_id=payload.config_scope_id,
                confirmed_visibility_expand=(
                    x_knowledge_base_confirm == "visibility-expand"
                ),
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_knowledge_base_patch")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_knowledge_base_patch")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_knowledge_base_patch")
    return KnowledgeBaseResponse(
        request_id=_request_id(),
        data=_knowledge_base_data(knowledge_base),
    )


@router.delete(
    "/knowledge-bases/{kb_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AcceptedResponse,
)
async def delete_knowledge_base(
    kb_id: str,
    authorization: str | None = Header(default=None),
    x_knowledge_base_confirm: str | None = Header(default=None),
) -> AcceptedResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="knowledge_base:manage")
            result = service.delete_knowledge_base(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                kb_id=kb_id,
                confirmed=x_knowledge_base_confirm == "delete",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_knowledge_base_delete")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_knowledge_base_delete")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_knowledge_base_delete")
    return AcceptedResponse(request_id=_request_id(), data=_accepted_data(result))


@router.get("/knowledge-bases/{kb_id}/folders", response_model=FolderListResponse)
async def list_folders(
    kb_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    authorization: str | None = Header(default=None),
) -> FolderListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="folder:manage")
            result = service.list_folders(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                kb_id=kb_id,
                page=page,
                page_size=page_size,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_folder_list")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_folder_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_folder_list")
    return FolderListResponse(
        request_id=_request_id(),
        data=[_folder_data(folder) for folder in result.items],
        pagination=PaginationData(page=page, page_size=page_size, total=result.total),
    )


@router.get(
    "/knowledge-bases/{kb_id}/folder-options",
    response_model=FolderOptionListResponse,
)
async def list_folder_options(
    kb_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    authorization: str | None = Header(default=None),
) -> FolderOptionListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="folder:manage")
            result = service.list_folder_options(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                kb_id=kb_id,
                page=page,
                page_size=page_size,
                keyword=keyword,
                status=status_filter,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_folder_options")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_folder_options")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_folder_options")
    return FolderOptionListResponse(
        request_id=_request_id(),
        data=[_folder_option_data(folder) for folder in result.items],
        pagination=PaginationData(page=page, page_size=page_size, total=result.total),
    )


@router.post(
    "/knowledge-bases/{kb_id}/folders",
    status_code=status.HTTP_201_CREATED,
    response_model=FolderResponse,
)
async def create_folder(
    kb_id: str,
    payload: FolderCreateRequest,
    authorization: str | None = Header(default=None),
) -> FolderResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="folder:manage")
            folder = service.create_folder(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                kb_id=kb_id,
                name=payload.name,
                parent_id=payload.parent_id,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_folder_create")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_folder_create")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_folder_create")
    return FolderResponse(request_id=_request_id(), data=_folder_data(folder))


@router.get("/folders/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: str,
    authorization: str | None = Header(default=None),
) -> FolderResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="folder:manage")
            folder = service.get_folder(
                session,
                folder_id,
                enterprise_id=auth_context.user.enterprise_id,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_folder_get")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_folder_get")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_folder_get")
    return FolderResponse(request_id=_request_id(), data=_folder_data(folder))


@router.patch("/folders/{folder_id}", response_model=FolderResponse)
async def patch_folder(
    folder_id: str,
    payload: FolderPatchRequest,
    authorization: str | None = Header(default=None),
) -> FolderResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="folder:manage")
            folder = service.patch_folder(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                folder_id=folder_id,
                name=payload.name,
                parent_id=payload.parent_id,
                parent_id_provided="parent_id" in payload.model_fields_set,
                status=payload.status,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_folder_patch")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_folder_patch")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_folder_patch")
    return FolderResponse(request_id=_request_id(), data=_folder_data(folder))


@router.delete(
    "/folders/{folder_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AcceptedResponse,
)
async def delete_folder(
    folder_id: str,
    authorization: str | None = Header(default=None),
    x_folder_confirm: str | None = Header(default=None),
) -> AcceptedResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="folder:manage")
            result = service.delete_folder(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                folder_id=folder_id,
                confirmed=x_folder_confirm == "delete",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_folder_delete")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_folder_delete")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_folder_delete")
    return AcceptedResponse(request_id=_request_id(), data=_accepted_data(result))

