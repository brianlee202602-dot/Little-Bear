"""管理后台部门 API。"""

from __future__ import annotations

from app.api.routes.admin_shared import (
    AdminService,
    AdminServiceError,
    APIRouter,
    AuthServiceError,
    DepartmentCreateRequest,
    DepartmentListResponse,
    DepartmentOptionListResponse,
    DepartmentPatchRequest,
    DepartmentResponse,
    Header,
    JSONResponse,
    PaginationData,
    Query,
    Response,
    SQLAlchemyError,
    _actor_context,
    _admin_error_response,
    _auth_error_response,
    _authenticate,
    _compat,
    _database_error_response,
    _department_data,
    _department_list_item_data,
    _department_option_data,
    _extract_bearer_token,
    _request_id,
    status,
)

router = APIRouter(prefix="/internal/v1/admin", tags=["admin-departments"])


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
        with _compat().session_scope() as session:
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
        data=[_department_list_item_data(department) for department in result.items],
        pagination=PaginationData(page=page, page_size=page_size, total=result.total),
    )


@router.get("/department-options", response_model=DepartmentOptionListResponse)
async def list_department_options(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    authorization: str | None = Header(default=None),
) -> DepartmentOptionListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with _compat().session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="org:read")
            result = service.list_department_options(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                page=page,
                page_size=page_size,
                keyword=keyword,
                status=status_filter,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_department_options")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="admin_department_options")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_department_options")
    return DepartmentOptionListResponse(
        request_id=_request_id(),
        data=[_department_option_data(department) for department in result.items],
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
        with _compat().session_scope() as session:
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
        with _compat().session_scope() as session:
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
        with _compat().session_scope() as session:
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
        with _compat().session_scope() as session:
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

