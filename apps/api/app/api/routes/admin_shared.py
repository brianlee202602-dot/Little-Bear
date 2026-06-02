"""管理后台路由共享依赖。"""

# ruff: noqa: F401,F403,F405

from __future__ import annotations

from functools import partial

from fastapi import APIRouter, Header, Query
from sqlalchemy.exc import SQLAlchemyError
from starlette import status
from starlette.responses import JSONResponse, Response

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
from app.api.presenters.admin import (
    accepted_data as _accepted_data,
)
from app.api.presenters.admin import (
    admin_chunk_data as _admin_chunk_data,
)
from app.api.presenters.admin import (
    admin_document_preview_data as _admin_document_preview_data,
)
from app.api.presenters.admin import (
    assignable_role_option_data as _assignable_role_option_data,
)
from app.api.presenters.admin import (
    department_data as _department_data,
)
from app.api.presenters.admin import (
    department_list_item_data as _department_list_item_data,
)
from app.api.presenters.admin import (
    department_option_data as _department_option_data,
)
from app.api.presenters.admin import (
    document_data as _document_data,
)
from app.api.presenters.admin import (
    document_list_item_data as _document_list_item_data,
)
from app.api.presenters.admin import (
    document_version_data as _document_version_data,
)
from app.api.presenters.admin import (
    folder_data as _folder_data,
)
from app.api.presenters.admin import (
    folder_option_data as _folder_option_data,
)
from app.api.presenters.admin import (
    index_collection_health_data as _index_collection_health_data,
)
from app.api.presenters.admin import (
    index_collection_operation_data as _index_collection_operation_data,
)
from app.api.presenters.admin import (
    index_collection_snapshot_data as _index_collection_snapshot_data,
)
from app.api.presenters.admin import (
    index_version_data as _index_version_data,
)
from app.api.presenters.admin import (
    knowledge_base_data as _knowledge_base_data,
)
from app.api.presenters.admin import (
    knowledge_base_list_item_data as _knowledge_base_list_item_data,
)
from app.api.presenters.admin import (
    knowledge_base_option_data as _knowledge_base_option_data,
)
from app.api.presenters.admin import (
    role_binding_data as _role_binding_data,
)
from app.api.presenters.admin import (
    role_data as _role_data,
)
from app.api.presenters.admin import (
    role_list_item_data as _role_list_item_data,
)
from app.api.presenters.admin import (
    user_data as _user_data,
)
from app.api.presenters.admin import (
    user_list_item_data as _user_list_item_data,
)
from app.api.schemas.admin import *
from app.api.schemas.common import PaginationData
from app.db.session import session_scope
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.schemas import *
from app.modules.admin.service import AdminActorContext, AdminService, RoleBindingInput
from app.modules.auth.errors import AuthServiceError
from app.modules.auth.schemas import AuthContext
from app.modules.indexing import build_index_ops_service
from app.modules.indexing.errors import IndexingServiceError
from app.modules.indexing.schemas import *

_auth_error_response = service_error_response
_admin_error_response = service_error_response
_indexing_error_response = service_error_response
_database_error_response = partial(
    database_error_response,
    error_code="ADMIN_DATABASE_ERROR",
    message="admin database operation failed",
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
        role_ids=tuple(role.id for role in auth_context.user.roles),
        knowledge_base_ids=knowledge_base_ids,
        can_manage_all_knowledge_bases=can_manage_all_knowledge_bases,
    )


def _binding_input(item) -> RoleBindingInput:
    return RoleBindingInput(
        role_id=item.role_id,
        scope_type=item.scope_type,
        scope_id=item.scope_id,
    )


__all__ = [name for name in globals() if not name.startswith("__")]
