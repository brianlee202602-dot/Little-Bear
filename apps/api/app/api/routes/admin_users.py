"""管理后台用户 API。"""

from __future__ import annotations

from app.api.routes.admin_shared import (
    AdminPasswordResetRequest,
    AdminService,
    AdminServiceError,
    APIRouter,
    AuthServiceError,
    Header,
    JSONResponse,
    PaginationData,
    Query,
    Response,
    SQLAlchemyError,
    UserCreateRequest,
    UserDepartmentsPutRequest,
    UserDepartmentsResponse,
    UserListResponse,
    UserPatchRequest,
    UserResponse,
    _actor_context,
    _admin_error_response,
    _auth_error_response,
    _authenticate,
    _compat,
    _database_error_response,
    _department_data,
    _extract_bearer_token,
    _request_id,
    _user_data,
    _user_list_item_data,
    status,
)

router = APIRouter(prefix="/internal/v1/admin", tags=["admin-users"])


@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    keyword: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    authorization: str | None = Header(default=None),
) -> UserListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="user:read")
            result = service.list_users(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                page=page,
                page_size=page_size,
                keyword=keyword,
                status=status_filter,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_user_list")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_user_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_user_list")
    return UserListResponse(
        request_id=_request_id(),
        data=[_user_list_item_data(user) for user in result.items],
        pagination=PaginationData(page=page, page_size=page_size, total=result.total),
    )


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def create_user(
    payload: UserCreateRequest,
    authorization: str | None = Header(default=None),
    x_user_confirm: str | None = Header(default=None),
) -> UserResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="user:manage")
            user = service.create_user(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                username=payload.username,
                name=payload.name,
                initial_password=payload.initial_password,
                department_ids=payload.department_ids,
                role_ids=payload.role_ids,
                confirmed_high_risk=x_user_confirm == "create-admin",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_user_create")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_user_create")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_user_create")
    return UserResponse(request_id=_request_id(), data=_user_data(user))



@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> UserResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="user:read")
            user = service.get_user(
                session,
                user_id,
                enterprise_id=auth_context.user.enterprise_id,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_user_get")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_user_get")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_user_get")
    return UserResponse(request_id=_request_id(), data=_user_data(user))


@router.patch("/users/{user_id}", response_model=UserResponse)
async def patch_user(
    user_id: str,
    payload: UserPatchRequest,
    authorization: str | None = Header(default=None),
    x_user_confirm: str | None = Header(default=None),
) -> UserResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="user:manage")
            user = service.patch_user(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                user_id=user_id,
                name=payload.name,
                status=payload.status,
                confirmed_disable_admin=x_user_confirm == "disable-admin",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_user_patch")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_user_patch")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_user_patch")
    return UserResponse(request_id=_request_id(), data=_user_data(user))


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_user(
    user_id: str,
    authorization: str | None = Header(default=None),
    x_user_confirm: str | None = Header(default=None),
) -> Response | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="user:manage")
            service.delete_user(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                user_id=user_id,
                confirmed=x_user_confirm == "delete",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_user_delete")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_user_delete")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_user_delete")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/{user_id}/departments", response_model=UserDepartmentsResponse)
async def list_user_departments(
    user_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    authorization: str | None = Header(default=None),
) -> UserDepartmentsResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="org:read")
            departments = service.list_user_departments(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                user_id=user_id,
                page=page,
                page_size=page_size,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_user_department_list")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_user_department_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_user_department_list")
    return UserDepartmentsResponse(
        request_id=_request_id(),
        data=[_department_data(department) for department in departments.items],
        pagination=PaginationData(page=page, page_size=page_size, total=departments.total),
    )


@router.put("/users/{user_id}/departments", response_model=UserDepartmentsResponse)
async def replace_user_departments(
    user_id: str,
    payload: UserDepartmentsPutRequest,
    authorization: str | None = Header(default=None),
    x_department_confirm: str | None = Header(default=None),
) -> UserDepartmentsResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="org:manage")
            departments = service.replace_user_departments(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                user_id=user_id,
                department_ids=payload.department_ids,
                confirmed_remove_primary=x_department_confirm == "replace-primary",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_user_department_replace")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_user_department_replace")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_user_department_replace")
    return UserDepartmentsResponse(
        request_id=_request_id(),
        data=[_department_data(department) for department in departments],
        pagination=PaginationData(
            page=1,
            page_size=max(len(departments), 1),
            total=len(departments),
        ),
    )


@router.put(
    "/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def reset_user_password(
    user_id: str,
    payload: AdminPasswordResetRequest,
    authorization: str | None = Header(default=None),
    x_user_confirm: str | None = Header(default=None),
) -> Response | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="user:manage")
            service.reset_user_password(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                user_id=user_id,
                new_password=payload.new_password,
                force_change_password=payload.force_change_password,
                confirmed=x_user_confirm == "reset-password",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_user_password_reset")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_user_password_reset")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_user_password_reset")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/users/{user_id}/lock", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def unlock_user(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> Response | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="user:manage")
            service.unlock_user(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                user_id=user_id,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_user_unlock")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_user_unlock")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_user_unlock")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

