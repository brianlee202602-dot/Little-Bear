"""管理后台角色 API。"""

from __future__ import annotations

from app.api.routes.admin_shared import (
    AdminService,
    AdminServiceError,
    APIRouter,
    AssignableRoleOptionListResponse,
    AuthServiceError,
    Header,
    JSONResponse,
    PaginationData,
    Query,
    Response,
    RoleBindingCreateRequest,
    RoleBindingListResponse,
    RoleListResponse,
    RoleResponse,
    SQLAlchemyError,
    _actor_context,
    _admin_error_response,
    _assignable_role_option_data,
    _auth_error_response,
    _authenticate,
    _binding_input,
    _compat,
    _database_error_response,
    _extract_bearer_token,
    _request_id,
    _role_binding_data,
    _role_data,
    _role_list_item_data,
    status,
)

router = APIRouter(prefix="/internal/v1/admin", tags=["admin-roles"])


@router.get("/roles", response_model=RoleListResponse)
async def list_roles(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    keyword: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    scope_type: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> RoleListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="role:read")
            result = service.list_roles(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                page=page,
                page_size=page_size,
                keyword=keyword,
                status=status_filter,
                scope_type=scope_type,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_role_list")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_role_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_role_list")
    return RoleListResponse(
        request_id=_request_id(),
        data=[_role_list_item_data(role) for role in result.items],
        pagination=PaginationData(page=page, page_size=page_size, total=result.total),
    )


@router.get("/assignable-role-options", response_model=AssignableRoleOptionListResponse)
async def list_assignable_role_options(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = Query(default=None),
    status_filter: str | None = Query(default="active", alias="status"),
    scope_type: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> AssignableRoleOptionListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="role:read")
            result = service.list_assignable_role_options(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                page=page,
                page_size=page_size,
                keyword=keyword,
                status=status_filter,
                scope_type=scope_type,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_assignable_role_options")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_assignable_role_options")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_assignable_role_options")
    return AssignableRoleOptionListResponse(
        request_id=_request_id(),
        data=[_assignable_role_option_data(role) for role in result.items],
        pagination=PaginationData(page=page, page_size=page_size, total=result.total),
    )


@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: str,
    authorization: str | None = Header(default=None),
) -> RoleResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="role:read")
            role = service.get_role(session, role_id, enterprise_id=auth_context.user.enterprise_id)
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_role_get")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_role_get")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_role_get")
    return RoleResponse(request_id=_request_id(), data=_role_data(role))


@router.get("/users/{user_id}/role-bindings", response_model=RoleBindingListResponse)
async def list_user_role_bindings(
    user_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    authorization: str | None = Header(default=None),
) -> RoleBindingListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="role:read")
            bindings = service.list_role_bindings(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                user_id=user_id,
                page=page,
                page_size=page_size,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_role_binding_list")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_role_binding_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_role_binding_list")
    return RoleBindingListResponse(
        request_id=_request_id(),
        data=[_role_binding_data(binding) for binding in bindings.items],
        pagination=PaginationData(page=page, page_size=page_size, total=bindings.total),
    )


@router.post(
    "/users/{user_id}/role-bindings",
    status_code=status.HTTP_201_CREATED,
    response_model=RoleBindingListResponse,
)
async def create_user_role_bindings(
    user_id: str,
    payload: RoleBindingCreateRequest,
    authorization: str | None = Header(default=None),
    x_role_binding_confirm: str | None = Header(default=None),
) -> RoleBindingListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="role:manage")
            bindings = service.create_role_bindings(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                user_id=user_id,
                bindings=[_binding_input(item) for item in payload.bindings],
                confirmed_high_risk=x_role_binding_confirm == "high-risk",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_role_binding_create")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_role_binding_create")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_role_binding_create")
    return RoleBindingListResponse(
        request_id=_request_id(),
        data=[_role_binding_data(binding) for binding in bindings],
        pagination=PaginationData(
            page=1,
            page_size=max(len(bindings), 1),
            total=len(bindings),
        ),
    )


@router.put("/users/{user_id}/role-bindings", response_model=RoleBindingListResponse)
async def replace_user_role_bindings(
    user_id: str,
    payload: RoleBindingCreateRequest,
    authorization: str | None = Header(default=None),
    x_role_binding_confirm: str | None = Header(default=None),
) -> RoleBindingListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="role:manage")
            bindings = service.replace_role_bindings(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                user_id=user_id,
                bindings=[_binding_input(item) for item in payload.bindings],
                confirmed=x_role_binding_confirm == "replace",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_role_binding_replace")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_role_binding_replace")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_role_binding_replace")
    return RoleBindingListResponse(
        request_id=_request_id(),
        data=[_role_binding_data(binding) for binding in bindings],
        pagination=PaginationData(
            page=1,
            page_size=max(len(bindings), 1),
            total=len(bindings),
        ),
    )


@router.delete(
    "/users/{user_id}/role-bindings/{binding_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_user_role_binding(
    user_id: str,
    binding_id: str,
    authorization: str | None = Header(default=None),
    x_role_binding_confirm: str | None = Header(default=None),
) -> Response | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="role:manage")
            service.revoke_role_binding(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                user_id=user_id,
                binding_id=binding_id,
                confirmed_remove_admin=x_role_binding_confirm == "remove-admin",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_role_binding_delete")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_role_binding_delete")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_role_binding_delete")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

