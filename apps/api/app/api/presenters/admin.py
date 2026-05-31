"""管理后台响应 DTO 映射。"""

from __future__ import annotations

from app.api.schemas.admin import (
    AcceptedData,
    AdminChunkData,
    AdminDocumentPreviewChunkData,
    AdminDocumentPreviewData,
    AdminDocumentVersionData,
    AssignableRoleOptionData,
    DepartmentData,
    DepartmentListItemData,
    DepartmentOptionData,
    DocumentData,
    DocumentListItemData,
    FolderData,
    FolderOptionData,
    IndexCollectionHealthData,
    IndexCollectionOperationData,
    IndexCollectionSnapshotData,
    IndexVersionData,
    KnowledgeBaseAccessRuleData,
    KnowledgeBaseData,
    KnowledgeBaseListItemData,
    KnowledgeBaseOptionData,
    RoleBindingData,
    RoleData,
    RoleListItemData,
    UserData,
    UserListItemData,
)
from app.modules.admin.schemas import (
    AdminAcceptedResult,
    AdminAssignableRoleOption,
    AdminChunk,
    AdminDepartment,
    AdminDepartmentListItem,
    AdminDepartmentOption,
    AdminDocument,
    AdminDocumentPreview,
    AdminDocumentPreviewChunk,
    AdminDocumentVersion,
    AdminFolder,
    AdminFolderOption,
    AdminIndexVersion,
    AdminKnowledgeBase,
    AdminKnowledgeBaseAccessRule,
    AdminKnowledgeBaseListItem,
    AdminKnowledgeBaseOption,
    AdminRole,
    AdminRoleBinding,
    AdminRoleListItem,
    AdminUser,
    AdminUserListItem,
)
from app.modules.indexing.schemas import (
    IndexCollectionHealth,
    IndexCollectionOperationResult,
    IndexCollectionSnapshot,
)


def user_data(user: AdminUser) -> UserData:
    return UserData(
        id=user.id,
        username=user.username,
        name=user.name,
        status=user.status,
        enterprise_id=user.enterprise_id,
        email=user.email,
        phone=user.phone,
        departments=[department_data(department) for department in user.departments],
        roles=[role_data(role) for role in user.roles],
        scopes=list(user.scopes),
    )


def user_list_item_data(user: AdminUserListItem) -> UserListItemData:
    return UserListItemData(
        id=user.id,
        username=user.username,
        name=user.name,
        status=user.status,
        department_names=list(user.department_names),
        role_names=list(user.role_names),
    )


def department_data(department: AdminDepartment) -> DepartmentData:
    return DepartmentData(
        id=department.id,
        code=department.code,
        name=department.name,
        status=department.status,
        is_primary=department.is_primary,
        is_default=department.is_default,
    )


def department_list_item_data(department: AdminDepartmentListItem) -> DepartmentListItemData:
    return DepartmentListItemData(
        id=department.id,
        name=department.name,
        status=department.status,
        is_default=department.is_default,
    )


def department_option_data(department: AdminDepartmentOption) -> DepartmentOptionData:
    return DepartmentOptionData(
        id=department.id,
        name=department.name,
        status=department.status,
        is_default=department.is_default,
    )


def knowledge_base_data(knowledge_base: AdminKnowledgeBase) -> KnowledgeBaseData:
    return KnowledgeBaseData(
        id=knowledge_base.id,
        name=knowledge_base.name,
        status=knowledge_base.status,
        owner_department_id=knowledge_base.owner_department_id,
        owner_department=(
            department_data(knowledge_base.owner_department)
            if knowledge_base.owner_department
            else None
        ),
        kb_visibility=knowledge_base.kb_visibility,
        default_document_visibility=knowledge_base.default_document_visibility,
        default_document_owner_department_id=knowledge_base.default_document_owner_department_id,
        default_document_owner_department=(
            department_data(knowledge_base.default_document_owner_department)
            if knowledge_base.default_document_owner_department
            else None
        ),
        access_rules=[
            knowledge_base_access_rule_data(rule) for rule in knowledge_base.access_rules
        ],
        config_scope_id=knowledge_base.config_scope_id,
        policy_version=knowledge_base.policy_version,
    )


def knowledge_base_list_item_data(
    knowledge_base: AdminKnowledgeBaseListItem,
) -> KnowledgeBaseListItemData:
    return KnowledgeBaseListItemData(
        id=knowledge_base.id,
        name=knowledge_base.name,
        status=knowledge_base.status,
        owner_department_id=knowledge_base.owner_department_id,
        owner_department_name=knowledge_base.owner_department_name,
        kb_visibility=knowledge_base.kb_visibility,
        default_document_visibility=knowledge_base.default_document_visibility,
        default_document_owner_department_id=(
            knowledge_base.default_document_owner_department_id
        ),
        default_document_owner_department_name=(
            knowledge_base.default_document_owner_department_name
        ),
    )


def knowledge_base_option_data(
    knowledge_base: AdminKnowledgeBaseOption,
) -> KnowledgeBaseOptionData:
    return KnowledgeBaseOptionData(
        id=knowledge_base.id,
        name=knowledge_base.name,
        status=knowledge_base.status,
    )


def knowledge_base_access_rule_data(
    rule: AdminKnowledgeBaseAccessRule,
) -> KnowledgeBaseAccessRuleData:
    return KnowledgeBaseAccessRuleData(
        subject_type=rule.subject_type,
        subject_id=rule.subject_id,
        permission=rule.permission,
    )


def accepted_data(result: AdminAcceptedResult) -> AcceptedData:
    return AcceptedData(accepted=result.accepted, job_id=result.job_id)


def folder_data(folder: AdminFolder) -> FolderData:
    return FolderData(
        id=folder.id,
        kb_id=folder.kb_id,
        parent_id=folder.parent_id,
        name=folder.name,
        status=folder.status,
    )


def folder_option_data(folder: AdminFolderOption) -> FolderOptionData:
    return FolderOptionData(
        id=folder.id,
        name=folder.name,
        status=folder.status,
    )


def document_data(document: AdminDocument) -> DocumentData:
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
        current_version_no=document.current_version_no,
    )


def document_list_item_data(document: AdminDocument) -> DocumentListItemData:
    return DocumentListItemData(
        id=document.id,
        title=document.title,
        folder_name=document.folder_name,
        lifecycle_status=document.lifecycle_status,
        index_status=document.index_status,
        visibility=document.visibility,
        owner_department_name=document.owner_department_name,
        current_version_no=document.current_version_no,
        can_rebuild_index=(
            document.lifecycle_status == "active" and document.current_version_id is not None
        ),
    )


def document_version_data(version: AdminDocumentVersion) -> AdminDocumentVersionData:
    return AdminDocumentVersionData(
        id=version.id,
        document_id=version.document_id,
        version_no=version.version_no,
        status=version.status,
    )


def index_version_data(version: AdminIndexVersion) -> IndexVersionData:
    return IndexVersionData(
        id=version.id,
        document_id=version.document_id,
        document_version_id=version.document_version_id,
        embedding_model=version.embedding_model,
        model_version=version.model_version,
        dimension=version.dimension,
        collection_name=version.collection_name,
        status=version.status,
        chunk_count=version.chunk_count,
        created_at=version.created_at,
        activated_at=version.activated_at,
    )


def index_collection_health_data(item: IndexCollectionHealth) -> IndexCollectionHealthData:
    return IndexCollectionHealthData(
        collection_name=item.collection_name,
        expected_dimension=item.expected_dimension,
        qdrant_reachable=item.qdrant_reachable,
        qdrant_exists=item.qdrant_exists,
        qdrant_status=item.qdrant_status,
        qdrant_vector_size=item.qdrant_vector_size,
        qdrant_points_count=item.qdrant_points_count,
        db_index_version_count=item.db_index_version_count,
        active_index_version_count=item.active_index_version_count,
        pending_delete_index_version_count=item.pending_delete_index_version_count,
        failed_index_version_count=item.failed_index_version_count,
        active_ref_count=item.active_ref_count,
        draft_ref_count=item.draft_ref_count,
        deleted_ref_count=item.deleted_ref_count,
        pending_delete_ref_count=item.pending_delete_ref_count,
        active_ref_mismatch_count=item.active_ref_mismatch_count,
        issues=list(item.issues),
    )


def index_collection_snapshot_data(
    item: IndexCollectionSnapshot,
) -> IndexCollectionSnapshotData:
    return IndexCollectionSnapshotData(
        collection_name=item.collection_name,
        name=item.name,
        size=item.size,
        creation_time=item.creation_time,
        checksum=item.checksum,
    )


def index_collection_operation_data(
    item: IndexCollectionOperationResult,
) -> IndexCollectionOperationData:
    return IndexCollectionOperationData(
        collection_name=item.collection_name,
        operation="snapshot_recover",
        accepted=item.accepted,
        result=item.result,
    )


def admin_chunk_data(chunk: AdminChunk) -> AdminChunkData:
    return AdminChunkData(
        id=chunk.id,
        document_id=chunk.document_id,
        document_version_id=chunk.document_version_id,
        text_preview=chunk.text_preview,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        status=chunk.status,
        ordinal=chunk.ordinal,
    )


def admin_document_preview_data(preview: AdminDocumentPreview) -> AdminDocumentPreviewData:
    return AdminDocumentPreviewData(
        doc_id=preview.doc_id,
        title=preview.title,
        chunks=[admin_document_preview_chunk_data(chunk) for chunk in preview.chunks],
    )


def admin_document_preview_chunk_data(
    chunk: AdminDocumentPreviewChunk,
) -> AdminDocumentPreviewChunkData:
    return AdminDocumentPreviewChunkData(
        id=chunk.id,
        document_id=chunk.document_id,
        document_version_id=chunk.document_version_id,
        text=chunk.text,
        text_preview=chunk.text_preview,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        status=chunk.status,
        ordinal=chunk.ordinal,
        heading_path=chunk.heading_path,
        source_offsets=chunk.source_offsets,
        text_status=chunk.text_status,
    )


def role_data(role: AdminRole) -> RoleData:
    return RoleData(
        id=role.id,
        code=role.code,
        name=role.name,
        scope_type=role.scope_type,
        is_builtin=role.is_builtin,
        status=role.status,
        scopes=list(role.scopes),
    )


def role_list_item_data(role: AdminRoleListItem) -> RoleListItemData:
    return RoleListItemData(
        id=role.id,
        code=role.code,
        name=role.name,
        scope_type=role.scope_type,
        is_builtin=role.is_builtin,
        status=role.status,
    )


def assignable_role_option_data(
    role: AdminAssignableRoleOption,
) -> AssignableRoleOptionData:
    return AssignableRoleOptionData(
        id=role.id,
        code=role.code,
        name=role.name,
        scope_type=role.scope_type,
        status=role.status,
        risk_level=role.risk_level,
    )


def role_binding_data(binding: AdminRoleBinding) -> RoleBindingData:
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

