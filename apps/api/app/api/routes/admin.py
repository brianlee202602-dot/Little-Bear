"""用户与角色管理 API。"""

from __future__ import annotations

from fastapi import APIRouter, Header, Query
from sqlalchemy.exc import SQLAlchemyError
from starlette import status
from starlette.responses import JSONResponse, Response

from app.api.schemas.admin import (
    AcceptedData,
    AcceptedResponse,
    AdminPasswordResetRequest,
    DepartmentCreateRequest,
    DepartmentData,
    DepartmentListResponse,
    DepartmentPatchRequest,
    DepartmentResponse,
    DocumentData,
    DocumentListResponse,
    DocumentPatchRequest,
    DocumentResponse,
    FolderCreateRequest,
    FolderData,
    FolderListResponse,
    FolderPatchRequest,
    FolderResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseData,
    KnowledgeBaseListResponse,
    KnowledgeBasePatchRequest,
    KnowledgeBaseResponse,
    RoleBindingCreateRequest,
    RoleBindingData,
    RoleBindingListResponse,
    RoleData,
    RoleListResponse,
    RoleResponse,
    UserCreateRequest,
    UserData,
    UserDepartmentsPutRequest,
    UserDepartmentsResponse,
    UserListResponse,
    UserPatchRequest,
    UserResponse,
)
from app.api.schemas.config import PaginationData
from app.api.schemas.knowledge import (
    ChunkData,
    ChunkListResponse,
    DocumentVersionData,
    DocumentVersionListResponse,
)
from app.db.session import session_scope
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.schemas import (
    AdminAcceptedResult,
    AdminChunk,
    AdminDepartment,
    AdminDocument,
    AdminDocumentVersion,
    AdminFolder,
    AdminKnowledgeBase,
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


@router.get("/departments/{department_id}", response_model=DepartmentResponse)
async def get_department(
    department_id: str,
    authorization: str | None = Header(default=None),
) -> DepartmentResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="org:read")
            department = service.get_department(
                session,
                department_id,
                enterprise_id=auth_context.user.enterprise_id,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_department_get")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_department_get")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_department_get")
    return DepartmentResponse(request_id=_request_id(), data=_department_data(department))


@router.patch("/departments/{department_id}", response_model=DepartmentResponse)
async def patch_department(
    department_id: str,
    payload: DepartmentPatchRequest,
    authorization: str | None = Header(default=None),
) -> DepartmentResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="org:manage")
            department = service.patch_department(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                department_id=department_id,
                name=payload.name,
                status=payload.status,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_department_patch")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_department_patch")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_department_patch")
    return DepartmentResponse(request_id=_request_id(), data=_department_data(department))


@router.delete(
    "/departments/{department_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_department(
    department_id: str,
    authorization: str | None = Header(default=None),
    x_department_confirm: str | None = Header(default=None),
) -> Response | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="org:manage")
            service.delete_department(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                department_id=department_id,
                confirmed=x_department_confirm == "delete",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_department_delete")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_department_delete")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_department_delete")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.get("/users/{user_id}/departments", response_model=UserDepartmentsResponse)
async def list_user_departments(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> UserDepartmentsResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="org:read")
            departments = service.list_user_departments(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                user_id=user_id,
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
        data=[_department_data(department) for department in departments],
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
        with session_scope() as session:
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
        with session_scope() as session:
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
        data=[_knowledge_base_data(knowledge_base) for knowledge_base in result.items],
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
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="knowledge_base:manage")
            knowledge_base = service.create_knowledge_base(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                name=payload.name,
                owner_department_id=payload.owner_department_id,
                default_visibility=payload.default_visibility,
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
        with session_scope() as session:
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
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="knowledge_base:manage")
            knowledge_base = service.patch_knowledge_base(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                kb_id=kb_id,
                name=payload.name,
                status=payload.status,
                default_visibility=payload.default_visibility,
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
        with session_scope() as session:
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
        with session_scope() as session:
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
        with session_scope() as session:
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
        with session_scope() as session:
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
        with session_scope() as session:
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
        with session_scope() as session:
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


@router.get(
    "/knowledge-bases/{kb_id}/documents",
    response_model=DocumentListResponse,
)
async def list_documents(
    kb_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
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
        data=[_document_data(document) for document in result.items],
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


@router.get("/documents/{doc_id}/versions", response_model=DocumentVersionListResponse)
async def list_document_versions(
    doc_id: str,
    authorization: str | None = Header(default=None),
) -> DocumentVersionListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:manage")
            versions = service.list_document_versions(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                doc_id=doc_id,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_document_version_list")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_document_version_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_document_version_list")
    return DocumentVersionListResponse(
        request_id=_request_id(),
        data=[_document_version_data(version) for version in versions],
    )


@router.get("/documents/{doc_id}/chunks", response_model=ChunkListResponse)
async def list_document_chunks(
    doc_id: str,
    authorization: str | None = Header(default=None),
) -> ChunkListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:manage")
            chunks = service.list_document_chunks(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                doc_id=doc_id,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_document_chunk_list")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_document_chunk_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_document_chunk_list")
    return ChunkListResponse(
        request_id=_request_id(),
        data=[_admin_chunk_data(chunk) for chunk in chunks],
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
    knowledge_base_ids = tuple(
        role.scope_id
        for role in auth_context.user.roles
        if role.scope_type == "knowledge_base" and role.scope_id
    )
    can_manage_all_knowledge_bases = any(
        role.scope_type == "enterprise"
        and any(
            scope in {"*", "knowledge_base:*", "knowledge_base:manage"}
            for scope in role.scopes
        )
        for role in auth_context.user.roles
    )
    return AdminActorContext(
        user_id=auth_context.user.id,
        scopes=auth_context.user.scopes,
        department_ids=tuple(department.id for department in auth_context.user.departments),
        knowledge_base_ids=knowledge_base_ids,
        can_manage_all_knowledge_bases=can_manage_all_knowledge_bases,
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


def _knowledge_base_data(knowledge_base: AdminKnowledgeBase) -> KnowledgeBaseData:
    return KnowledgeBaseData(
        id=knowledge_base.id,
        name=knowledge_base.name,
        status=knowledge_base.status,
        owner_department_id=knowledge_base.owner_department_id,
        default_visibility=knowledge_base.default_visibility,
        config_scope_id=knowledge_base.config_scope_id,
        policy_version=knowledge_base.policy_version,
    )


def _accepted_data(result: AdminAcceptedResult) -> AcceptedData:
    return AcceptedData(accepted=result.accepted, job_id=result.job_id)


def _folder_data(folder: AdminFolder) -> FolderData:
    return FolderData(
        id=folder.id,
        kb_id=folder.kb_id,
        parent_id=folder.parent_id,
        name=folder.name,
        status=folder.status,
    )


def _document_data(document: AdminDocument) -> DocumentData:
    return DocumentData(
        id=document.id,
        kb_id=document.kb_id,
        folder_id=document.folder_id,
        title=document.title,
        lifecycle_status=document.lifecycle_status,
        index_status=document.index_status,
        owner_department_id=document.owner_department_id,
        visibility=document.visibility,
        current_version_id=document.current_version_id,
    )


def _document_version_data(version: AdminDocumentVersion) -> DocumentVersionData:
    return DocumentVersionData(
        id=version.id,
        document_id=version.document_id,
        version_no=version.version_no,
        status=version.status,
    )


def _admin_chunk_data(chunk: AdminChunk) -> ChunkData:
    return ChunkData(
        id=chunk.id,
        document_id=chunk.document_id,
        document_version_id=chunk.document_version_id,
        text_preview=chunk.text_preview,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        status=chunk.status,
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
