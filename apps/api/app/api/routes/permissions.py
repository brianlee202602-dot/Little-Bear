"""权限策略管理 API。"""

from __future__ import annotations

from fastapi import APIRouter, Header
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from app.api.schemas.permissions import (
    PermissionPolicyData,
    PermissionPolicyResponse,
    ResourcePermissionPutRequest,
)
from app.db.session import session_scope
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.schemas import AdminPermissionPolicy
from app.modules.admin.service import AdminActorContext, AdminService
from app.modules.auth.errors import AuthServiceError
from app.modules.auth.schemas import AuthContext
from app.modules.auth.service import AuthService
from app.shared.context import get_request_context

router = APIRouter(prefix="/internal/v1", tags=["permissions"])


@router.put(
    "/knowledge-bases/{kb_id}/permissions",
    response_model=PermissionPolicyResponse,
)
async def put_knowledge_base_permissions(
    kb_id: str,
    payload: ResourcePermissionPutRequest,
    authorization: str | None = Header(default=None),
    x_permission_confirm: str | None = Header(default=None),
) -> PermissionPolicyResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="permission:manage")
            policy = service.replace_knowledge_base_permissions(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                kb_id=kb_id,
                visibility=payload.visibility,
                owner_department_id=payload.owner_department_id,
                confirmed=x_permission_confirm == "replace",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="knowledge_base_permission_put")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="knowledge_base_permission_put")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="knowledge_base_permission_put")
    return PermissionPolicyResponse(request_id=_request_id(), data=_permission_policy_data(policy))


@router.put("/documents/{doc_id}/permissions", response_model=PermissionPolicyResponse)
async def put_document_permissions(
    doc_id: str,
    payload: ResourcePermissionPutRequest,
    authorization: str | None = Header(default=None),
    x_permission_confirm: str | None = Header(default=None),
) -> PermissionPolicyResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="permission:manage")
            policy = service.replace_document_permissions(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                doc_id=doc_id,
                visibility=payload.visibility,
                owner_department_id=payload.owner_department_id,
                confirmed=x_permission_confirm == "replace",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="document_permission_put")
    except AdminServiceError as exc:
        return _admin_error_response(exc, stage="document_permission_put")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="document_permission_put")
    return PermissionPolicyResponse(request_id=_request_id(), data=_permission_policy_data(policy))


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
            scope in {"*", "knowledge_base:*", "knowledge_base:manage", "permission:*"}
            or scope == "permission:manage"
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


def _permission_policy_data(policy: AdminPermissionPolicy) -> PermissionPolicyData:
    return PermissionPolicyData(
        resource_type=policy.resource_type,
        resource_id=policy.resource_id,
        visibility=policy.visibility,
        permission_version=policy.permission_version,
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
            "error_code": "PERMISSION_DATABASE_ERROR",
            "message": "permission database operation failed",
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
