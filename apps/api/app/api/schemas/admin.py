"""用户与角色管理 API 的请求和响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.config import PaginationData


class DepartmentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    code: str
    name: str
    status: Literal["active", "disabled", "deleted"]
    is_primary: bool = False
    is_default: bool = False


class DepartmentListItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    status: Literal["active", "disabled", "deleted"]
    is_default: bool = False


class DepartmentOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    status: Literal["active", "disabled", "deleted"]
    is_default: bool = False


class DepartmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=128)


class DepartmentPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: Literal["active", "disabled"] | None = None


class RoleData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    code: str
    name: str
    scope_type: Literal["enterprise", "department", "knowledge_base"]
    is_builtin: bool
    status: Literal["active", "disabled", "archived"]
    scopes: list[str] = Field(default_factory=list)


class RoleListItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    code: str
    name: str
    scope_type: Literal["enterprise", "department", "knowledge_base"]
    is_builtin: bool
    status: Literal["active", "disabled", "archived"]


class AssignableRoleOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    code: str
    name: str
    scope_type: Literal["enterprise", "department", "knowledge_base"]
    status: Literal["active", "disabled", "archived"]
    risk_level: Literal["low", "high"]


class UserData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    username: str
    name: str
    status: Literal["active", "disabled", "locked", "deleted"]
    enterprise_id: str
    email: str | None = None
    phone: str | None = None
    departments: list[DepartmentData] = Field(default_factory=list)
    roles: list[RoleData] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)


class UserListItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    username: str
    name: str
    status: Literal["active", "disabled", "locked", "deleted"]
    department_names: list[str] = Field(default_factory=list)
    role_names: list[str] = Field(default_factory=list)


class UserCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=128)
    initial_password: str = Field(min_length=1)
    department_ids: list[str] = Field(default_factory=list)
    role_ids: list[str] = Field(default_factory=list)


class UserPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: Literal["active", "disabled", "locked"] | None = None


class UserDepartmentsPutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_ids: list[str] = Field(min_length=1)


class AdminPasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_password: str = Field(min_length=1)
    force_change_password: bool = True


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: UserData


class UserListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[UserListItemData]
    pagination: PaginationData


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: DepartmentData


class DepartmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[DepartmentListItemData]
    pagination: PaginationData


class DepartmentOptionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[DepartmentOptionData]
    pagination: PaginationData


class KnowledgeBaseData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    status: Literal["active", "disabled", "archived"]
    owner_department_id: str
    owner_department: DepartmentData | None = None
    kb_visibility: Literal["enterprise", "department_acl", "private"]
    default_document_visibility: Literal["department", "enterprise"]
    default_document_owner_department_id: str
    default_document_owner_department: DepartmentData | None = None
    access_rules: list[KnowledgeBaseAccessRuleData] = Field(default_factory=list)
    config_scope_id: str | None = None
    policy_version: int = 1


class KnowledgeBaseListItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    status: Literal["active", "disabled", "archived"]
    owner_department_id: str
    owner_department_name: str | None = None
    kb_visibility: Literal["enterprise", "department_acl", "private"]
    default_document_visibility: Literal["department", "enterprise"]
    default_document_owner_department_id: str
    default_document_owner_department_name: str | None = None


class KnowledgeBaseOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    status: Literal["active", "disabled", "archived"]


class KnowledgeBaseAccessRuleData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_type: Literal["department", "user", "role"]
    subject_id: str
    permission: Literal["discover", "query", "manage"]


class KnowledgeBaseAccessRuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_type: Literal["department", "user", "role"]
    subject_id: str = Field(min_length=1)
    permission: Literal["discover", "query", "manage"]


class KnowledgeBaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    owner_department_id: str = Field(min_length=1)
    kb_visibility: Literal["enterprise", "department_acl", "private"] = "enterprise"
    default_document_visibility: Literal["department", "enterprise"] = "department"
    default_document_owner_department_id: str | None = Field(default=None, min_length=1)
    access_rules: list[KnowledgeBaseAccessRuleInput] = Field(default_factory=list)
    config_scope_id: str | None = Field(default=None, min_length=1, max_length=128)


class KnowledgeBasePatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: Literal["active", "disabled", "archived"] | None = None
    kb_visibility: Literal["enterprise", "department_acl", "private"] | None = None
    default_document_visibility: Literal["department", "enterprise"] | None = None
    default_document_owner_department_id: str | None = Field(default=None, min_length=1)
    config_scope_id: str | None = Field(default=None, min_length=1, max_length=128)


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: KnowledgeBaseData


class KnowledgeBaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[KnowledgeBaseListItemData]
    pagination: PaginationData


class KnowledgeBaseOptionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[KnowledgeBaseOptionData]
    pagination: PaginationData


class AcceptedData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    job_id: str | None = None


class AcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: AcceptedData


class FolderData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kb_id: str
    parent_id: str | None = None
    name: str
    status: Literal["active", "disabled", "archived"]


class FolderOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    status: Literal["active", "disabled", "archived"]


class FolderCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    parent_id: str | None = Field(default=None, min_length=1)


class FolderPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    parent_id: str | None = Field(default=None, min_length=1)
    status: Literal["active", "disabled", "archived"] | None = None


class FolderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: FolderData


class FolderListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[FolderData]
    pagination: PaginationData


class FolderOptionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[FolderOptionData]
    pagination: PaginationData


class DocumentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kb_id: str
    folder_id: str | None = None
    title: str
    lifecycle_status: Literal["draft", "active", "archived", "deleted"]
    index_status: Literal["none", "indexing", "indexed", "index_failed", "blocked"]
    owner_department_id: str
    visibility: Literal["department", "enterprise"]
    current_version_id: str | None = None
    current_version_no: int | None = None


class DocumentPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=256)
    folder_id: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None
    owner_department_id: str | None = Field(default=None, min_length=1)
    visibility: Literal["department", "enterprise"] | None = None
    lifecycle_status: Literal["active", "archived", "deleted"] | None = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: DocumentData


class AdminDocumentPreviewChunkData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    document_version_id: str
    text: str
    text_preview: str
    page_start: int | None = None
    page_end: int | None = None
    status: str
    ordinal: int
    heading_path: str | None = None
    source_offsets: dict[str, Any] | None = None
    text_status: Literal["object", "preview_only", "object_unavailable"]


class AdminDocumentPreviewData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    title: str
    chunks: list[AdminDocumentPreviewChunkData]


class AdminDocumentPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: AdminDocumentPreviewData
    pagination: PaginationData


class IndexVersionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    document_version_id: str
    embedding_model: str
    model_version: str
    dimension: int
    collection_name: str
    status: Literal["draft", "ready", "active", "archived", "pending_delete", "failed"]
    chunk_count: int
    created_at: datetime | None = None
    activated_at: datetime | None = None


class IndexVersionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[IndexVersionData]


class IndexCollectionHealthData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection_name: str
    expected_dimension: int | None = None
    qdrant_reachable: bool
    qdrant_exists: bool | None = None
    qdrant_status: str | None = None
    qdrant_vector_size: int | None = None
    qdrant_points_count: int | None = None
    db_index_version_count: int
    active_index_version_count: int
    pending_delete_index_version_count: int
    failed_index_version_count: int
    active_ref_count: int
    draft_ref_count: int
    deleted_ref_count: int
    pending_delete_ref_count: int
    active_ref_mismatch_count: int
    issues: list[str]


class IndexHealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[IndexCollectionHealthData]


class IndexCollectionSnapshotData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection_name: str
    name: str
    size: int | None = None
    creation_time: str | None = None
    checksum: str | None = None


class IndexCollectionSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: IndexCollectionSnapshotData


class IndexCollectionSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[IndexCollectionSnapshotData]


class IndexCollectionSnapshotRecoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str = Field(min_length=1, max_length=2048)
    priority: Literal["Snapshot", "Replica"] | None = "Snapshot"
    checksum: str | None = Field(default=None, min_length=1, max_length=128)


class IndexCollectionOperationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection_name: str
    operation: Literal["snapshot_recover"]
    accepted: bool
    result: bool | None = None


class IndexCollectionOperationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: IndexCollectionOperationData


class IndexJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kb_id: str | None = None
    document_ids: list[str] = Field(default_factory=list, max_length=200)


class IndexVersionCleanupJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index_version_ids: list[str] = Field(min_length=1, max_length=200)


class DocumentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[DocumentData]
    pagination: PaginationData


class UserDepartmentsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[DepartmentData]


class RoleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: RoleData


class RoleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[RoleListItemData]
    pagination: PaginationData


class AssignableRoleOptionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[AssignableRoleOptionData]
    pagination: PaginationData


class RoleBindingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    role_id: str
    subject_type: Literal["user", "department"] = "user"
    subject_id: str
    scope_type: Literal["enterprise", "department", "knowledge_base"]
    scope_id: str | None = None
    role_code: str | None = None
    role_name: str | None = None


class RoleBindingInputData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_id: str
    scope_type: Literal["enterprise", "department", "knowledge_base"]
    scope_id: str | None = None


class RoleBindingCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bindings: list[RoleBindingInputData] = Field(min_length=1)


class RoleBindingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[RoleBindingData]
