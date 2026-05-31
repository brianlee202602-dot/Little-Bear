"""权限策略管理 API。"""

from __future__ import annotations

from functools import partial

from fastapi import APIRouter, Header
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from app.api.dependencies.auth import (
    authenticate_required_scope as _authenticate,
)
from app.api.dependencies.auth import (
    current_request_id as _request_id,
)
from app.api.dependencies.auth import (
    extract_bearer_token as _extract_bearer_token,
)
from app.api.errors import database_error_response, service_error_response
from app.api.schemas.permissions import (
    KnowledgeBaseAccessRuleData,
    KnowledgeBasePermissionPolicyData,
    KnowledgeBasePermissionPolicyResponse,
    KnowledgeBasePermissionPutRequest,
    PermissionPolicyData,
    PermissionPolicyResponse,
    ResourcePermissionPutRequest,
)
from app.db.session import session_scope
from app.modules.auth.errors import AuthServiceError
from app.modules.auth.schemas import AuthContext
from app.modules.permissions.admin_schemas import (
    PermissionAdminActorContext,
    PermissionKnowledgeBaseAccessRule,
    PermissionKnowledgeBaseAccessRuleInput,
    PermissionKnowledgeBasePolicy,
    PermissionPolicy,
)
from app.modules.permissions.admin_service import PermissionAdminService
from app.modules.permissions.errors import PermissionServiceError

router = APIRouter(prefix="/internal/v1", tags=["permissions"])

_auth_error_response = service_error_response
_admin_error_response = service_error_response
_database_error_response = partial(
    database_error_response,
    error_code="PERMISSION_DATABASE_ERROR",
    message="permission database operation failed",
)


@router.put(
    "/knowledge-bases/{kb_id}/permissions",
    response_model=KnowledgeBasePermissionPolicyResponse,
)
async def put_knowledge_base_permissions(
    kb_id: str,
    payload: KnowledgeBasePermissionPutRequest,
    authorization: str | None = Header(default=None),
    x_permission_confirm: str | None = Header(default=None),
) -> KnowledgeBasePermissionPolicyResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = PermissionAdminService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="permission:manage")
            policy = service.replace_knowledge_base_permissions(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                kb_id=kb_id,
                kb_visibility=payload.kb_visibility,
                default_document_visibility=payload.default_document_visibility,
                default_document_owner_department_id=(
                    payload.default_document_owner_department_id
                ),
                access_rules=[
                    PermissionKnowledgeBaseAccessRuleInput(
                        subject_type=rule.subject_type,
                        subject_id=rule.subject_id,
                        permission=rule.permission,
                    )
                    for rule in payload.access_rules
                ],
                confirmed=x_permission_confirm == "replace",
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="knowledge_base_permission_put")
    except PermissionServiceError as exc:
        return _admin_error_response(exc, stage="knowledge_base_permission_put")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="knowledge_base_permission_put")
    return KnowledgeBasePermissionPolicyResponse(
        request_id=_request_id(),
        data=_knowledge_base_permission_policy_data(policy),
    )


@router.put("/documents/{doc_id}/permissions", response_model=PermissionPolicyResponse)
async def put_document_permissions(
    doc_id: str,
    payload: ResourcePermissionPutRequest,
    authorization: str | None = Header(default=None),
    x_permission_confirm: str | None = Header(default=None),
) -> PermissionPolicyResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = PermissionAdminService()
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
    except PermissionServiceError as exc:
        return _admin_error_response(exc, stage="document_permission_put")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="document_permission_put")
    return PermissionPolicyResponse(request_id=_request_id(), data=_permission_policy_data(policy))


def _actor_context(auth_context: AuthContext) -> PermissionAdminActorContext:
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
    return PermissionAdminActorContext(
        user_id=auth_context.user.id,
        scopes=auth_context.user.scopes,
        department_ids=tuple(department.id for department in auth_context.user.departments),
        role_ids=tuple(role.id for role in auth_context.user.roles),
        knowledge_base_ids=knowledge_base_ids,
        can_manage_all_knowledge_bases=can_manage_all_knowledge_bases,
    )


def _permission_policy_data(policy: PermissionPolicy) -> PermissionPolicyData:
    return PermissionPolicyData(
        resource_type=policy.resource_type,
        resource_id=policy.resource_id,
        visibility=policy.visibility,
        permission_version=policy.permission_version,
    )


def _knowledge_base_permission_policy_data(
    policy: PermissionKnowledgeBasePolicy,
) -> KnowledgeBasePermissionPolicyData:
    return KnowledgeBasePermissionPolicyData(
        resource_type=policy.resource_type,
        resource_id=policy.resource_id,
        kb_visibility=policy.kb_visibility,
        default_document_visibility=policy.default_document_visibility,
        default_document_owner_department_id=policy.default_document_owner_department_id,
        access_rules=[_knowledge_base_access_rule_data(rule) for rule in policy.access_rules],
        permission_version=policy.permission_version,
    )


def _knowledge_base_access_rule_data(
    rule: PermissionKnowledgeBaseAccessRule,
) -> KnowledgeBaseAccessRuleData:
    return KnowledgeBaseAccessRuleData(
        subject_type=rule.subject_type,
        subject_id=rule.subject_id,
        permission=rule.permission,
    )
