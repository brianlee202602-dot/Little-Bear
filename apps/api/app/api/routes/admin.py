"""用户与角色管理 API。"""

from __future__ import annotations

from fastapi import APIRouter, Header, Query
from sqlalchemy.exc import SQLAlchemyError
from starlette import status
from starlette.responses import JSONResponse, Response

from app.api.schemas.admin import (
    AdminPasswordResetRequest,
    DepartmentCreateRequest,
    DepartmentData,
    DepartmentListResponse,
    DepartmentResponse,
    RoleBindingCreateRequest,
    RoleBindingData,
    RoleBindingListResponse,
    RoleData,
    RoleListResponse,
    RoleResponse,
    UserCreateRequest,
    UserData,
    UserListResponse,
    UserPatchRequest,
    UserResponse,
)
from app.api.schemas.config import PaginationData
from app.db.session import session_scope
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.schemas import (
    AdminDepartment,
    AdminRole,
    AdminRoleBinding,
    AdminUser,
)
from app.modules.admin.service import AdminActorContext, AdminService, RoleBindingInput
from app.modules.auth.errors import AuthServiceError
from app.modules.auth.schemas import AuthContext
from app.modules.auth.service import AuthService
from app.shared.context import get_request_context

router = APIRouter(prefix="/internal/v1/admin", tags=["admin-user-role"])


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
        with session_scope() as session:
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
        data=[_user_data(user) for user in result.items],
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
        with session_scope() as session:
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


@router.get("/departments", response_model=DepartmentListResponse)
async def list_departments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    keyword: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    authorization: str | None = Header(default=None),
) -> DepartmentListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="org:read")
            result = service.list_departments(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                page=page,
                page_size=page_size,
                keyword=keyword,
                status=status_filter,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_department_list")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_department_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_department_list")
    return DepartmentListResponse(
        request_id=_request_id(),
        data=[_department_data(department) for department in result.items],
        pagination=PaginationData(page=page, page_size=page_size, total=result.total),
    )


@router.post(
    "/departments",
    status_code=status.HTTP_201_CREATED,
    response_model=DepartmentResponse,
)
async def create_department(
    payload: DepartmentCreateRequest,
    authorization: str | None = Header(default=None),
) -> DepartmentResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="org:manage")
            department = service.create_department(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                code=payload.code,
                name=payload.name,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_department_create")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_department_create")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_department_create")
    return DepartmentResponse(request_id=_request_id(), data=_department_data(department))


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> UserResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
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
        with session_scope() as session:
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
        with session_scope() as session:
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
        with session_scope() as session:
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
        with session_scope() as session:
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


@router.get("/roles", response_model=RoleListResponse)
async def list_roles(
    authorization: str | None = Header(default=None),
) -> RoleListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="role:read")
            roles = service.list_roles(session, enterprise_id=auth_context.user.enterprise_id)
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_role_list")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_role_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_role_list")
    return RoleListResponse(request_id=_request_id(), data=[_role_data(role) for role in roles])


@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: str,
    authorization: str | None = Header(default=None),
) -> RoleResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
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
    authorization: str | None = Header(default=None),
) -> RoleBindingListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="role:read")
            bindings = service.list_role_bindings(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                user_id=user_id,
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
        data=[_role_binding_data(binding) for binding in bindings],
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
        with session_scope() as session:
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
        with session_scope() as session:
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
        with session_scope() as session:
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


def _authenticate(session: object, token: str | None, *, required_scope: str) -> AuthContext:
    return AuthService().authenticate_access_token(
        session,
        access_token=token or "",
        required_scope=required_scope,
    )


def _actor_context(auth_context: AuthContext) -> AdminActorContext:
    return AdminActorContext(
        user_id=auth_context.user.id,
        scopes=auth_context.user.scopes,
        department_ids=tuple(department.id for department in auth_context.user.departments),
    )


def _binding_input(item) -> RoleBindingInput:
    return RoleBindingInput(
        role_id=item.role_id,
        scope_type=item.scope_type,
        scope_id=item.scope_id,
    )


def _user_data(user: AdminUser) -> UserData:
    return UserData(
        id=user.id,
        username=user.username,
        name=user.name,
        status=user.status,
        enterprise_id=user.enterprise_id,
        email=user.email,
        phone=user.phone,
        departments=[_department_data(department) for department in user.departments],
        roles=[_role_data(role) for role in user.roles],
        scopes=list(user.scopes),
    )


def _department_data(department: AdminDepartment) -> DepartmentData:
    return DepartmentData(
        id=department.id,
        code=department.code,
        name=department.name,
        status=department.status,
        is_primary=department.is_primary,
        is_default=department.is_default,
    )


def _role_data(role: AdminRole) -> RoleData:
    return RoleData(
        id=role.id,
        code=role.code,
        name=role.name,
        scope_type=role.scope_type,
        is_builtin=role.is_builtin,
        status=role.status,
        scopes=list(role.scopes),
    )


def _role_binding_data(binding: AdminRoleBinding) -> RoleBindingData:
    return RoleBindingData(
        id=binding.id,
        role_id=binding.role_id,
        subject_type=binding.subject_type,
        subject_id=binding.subject_id,
        scope_type=binding.scope_type,
        scope_id=binding.scope_id,
        role_code=binding.role_code,
        role_name=binding.role_name,
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


def _admin_error_response(exc: AdminServiceError, *, stage: str) -> JSONResponse:
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
            "error_code": "ADMIN_DATABASE_ERROR",
            "message": "admin database operation failed",
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
