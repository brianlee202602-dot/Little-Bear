"""创建知识库、文档、chunk 与索引相关表。

迁移 ID: 0004_knowledge_document_index
前置版本: 0003_roles_permissions
创建日期: 2026-05-03
"""

from __future__ import annotations

from alembic import op

revision = "0004_knowledge_document_index"
down_revision = "0003_roles_permissions"
branch_labels = None
depends_on = None


def _run(sql: str) -> None:
    # 索引和可见性约束依赖 PostgreSQL partial index / GIN，使用原生 SQL 更直观。
    # 这里直接走驱动层执行，避免 SQLAlchemy 误解析原始 SQL 中的 JSON/类型转换语法。
    op.get_bind().exec_driver_sql(sql)


def upgrade() -> None:
    # knowledge_bases 是文档组织边界，也承载默认可见性和归属部门。
    _run(
        """
        CREATE TABLE knowledge_bases (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            name text NOT NULL,
            status text NOT NULL CHECK (status IN ('active','disabled','archived','deleted')),
            owner_department_id uuid NOT NULL REFERENCES departments(id),
            default_visibility text NOT NULL CHECK (default_visibility IN ('department','enterprise')),
            policy_version integer NOT NULL DEFAULT 1,
            config_scope_id text NULL,
            created_by uuid NULL REFERENCES users(id),
            updated_by uuid NULL REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            deleted_at timestamptz NULL
        )
        """
    )
    _run("CREATE INDEX idx_kb_enterprise_id ON knowledge_bases(enterprise_id)")
    _run("CREATE INDEX idx_kb_name ON knowledge_bases(name)")
    _run("CREATE INDEX idx_kb_status ON knowledge_bases(status)")
    _run("CREATE INDEX idx_kb_owner_department_id ON knowledge_bases(owner_department_id)")
    _run("CREATE INDEX idx_kb_policy_version ON knowledge_bases(policy_version)")
    _run("CREATE INDEX idx_kb_config_scope_id ON knowledge_bases(config_scope_id)")
    _run("CREATE INDEX idx_kb_deleted_at ON knowledge_bases(deleted_at)")
    _run("CREATE INDEX idx_kb_enterprise_status ON knowledge_bases(enterprise_id, status)")
    _run(
        """
        CREATE INDEX idx_kb_owner_visibility
        ON knowledge_bases(enterprise_id, owner_department_id, default_visibility)
        """
    )

    # 文件夹只负责知识库内层级组织；权限继承模式 P0 固定为 inherit。
    _run(
        """
        CREATE TABLE folders (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            kb_id uuid NOT NULL REFERENCES knowledge_bases(id),
            parent_id uuid NULL REFERENCES folders(id),
            name text NOT NULL,
            path text NOT NULL,
            policy_inherit_mode text NOT NULL DEFAULT 'inherit',
            status text NOT NULL CHECK (status IN ('active','disabled','archived','deleted')),
            created_by uuid NULL REFERENCES users(id),
            updated_by uuid NULL REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            deleted_at timestamptz NULL
        )
        """
    )
    _run("CREATE INDEX idx_folders_enterprise_id ON folders(enterprise_id)")
    _run("CREATE INDEX idx_folders_kb_id ON folders(kb_id)")
    _run("CREATE INDEX idx_folders_parent_id ON folders(parent_id)")
    _run("CREATE INDEX idx_folders_name ON folders(name)")
    _run("CREATE INDEX idx_folders_path ON folders(path)")
    _run("CREATE INDEX idx_folders_status ON folders(status)")
    # 根文件夹和子文件夹分别建唯一索引，避免 NULL parent_id 破坏同级唯一语义。
    _run(
        """
        CREATE UNIQUE INDEX uq_folders_root_name
        ON folders(enterprise_id, kb_id, lower(name))
        WHERE parent_id IS NULL AND deleted_at IS NULL
        """
    )
    _run(
        """
        CREATE UNIQUE INDEX uq_folders_child_name
        ON folders(enterprise_id, kb_id, parent_id, lower(name))
        WHERE parent_id IS NOT NULL AND deleted_at IS NULL
        """
    )

    # documents 是查询可见性的核心事实表；只有 active + indexed 的文档允许进入候选上下文。
    _run(
        """
        CREATE TABLE documents (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            kb_id uuid NOT NULL REFERENCES knowledge_bases(id),
            folder_id uuid NULL REFERENCES folders(id),
            title text NOT NULL,
            source_type text NOT NULL CHECK (source_type IN ('upload','api','connector','manual')),
            source_uri text NULL,
            current_version_id uuid NULL,
            lifecycle_status text NOT NULL CHECK (lifecycle_status IN ('draft','active','archived','deleted')),
            index_status text NOT NULL CHECK (index_status IN ('none','indexing','indexed','index_failed','blocked')),
            owner_department_id uuid NOT NULL REFERENCES departments(id),
            visibility text NOT NULL CHECK (visibility IN ('department','enterprise')),
            content_hash text NULL,
            permission_snapshot_id uuid NULL REFERENCES permission_snapshots(id),
            tags text[] NOT NULL DEFAULT ARRAY[]::text[],
            created_by uuid NULL REFERENCES users(id),
            updated_by uuid NULL REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            deleted_at timestamptz NULL
        )
        """
    )
    _run("CREATE INDEX idx_documents_enterprise_id ON documents(enterprise_id)")
    _run("CREATE INDEX idx_documents_kb_id ON documents(kb_id)")
    _run("CREATE INDEX idx_documents_folder_id ON documents(folder_id)")
    _run("CREATE INDEX idx_documents_title ON documents(title)")
    _run("CREATE INDEX idx_documents_lifecycle_status ON documents(lifecycle_status)")
    _run("CREATE INDEX idx_documents_index_status ON documents(index_status)")
    _run("CREATE INDEX idx_documents_owner_department_id ON documents(owner_department_id)")
    _run("CREATE INDEX idx_documents_visibility ON documents(visibility)")
    _run("CREATE INDEX idx_documents_content_hash_raw ON documents(content_hash)")
    _run("CREATE INDEX idx_documents_permission_snapshot_id ON documents(permission_snapshot_id)")
    _run("CREATE INDEX idx_documents_tags ON documents USING gin(tags)")
    _run("CREATE INDEX idx_documents_deleted_at ON documents(deleted_at)")
    # 支撑查询入口按知识库、状态、可见性和部门进行权限过滤。
    _run(
        """
        CREATE INDEX idx_documents_query_visible
        ON documents(
            enterprise_id, kb_id, lifecycle_status, index_status, visibility, owner_department_id
        )
        """
    )
    _run(
        """
        CREATE INDEX idx_documents_folder
        ON documents(enterprise_id, kb_id, folder_id, lifecycle_status)
        """
    )
    _run("CREATE INDEX idx_documents_content_hash ON documents(enterprise_id, content_hash)")

    # document_versions 记录文档内容版本；active version 是 citation 回溯的重要锚点。
    _run(
        """
        CREATE TABLE document_versions (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            document_id uuid NOT NULL REFERENCES documents(id),
            version_no integer NOT NULL,
            object_key text NULL,
            parsed_object_key text NULL,
            cleaned_object_key text NULL,
            parser_version text NULL,
            chunker_version text NULL,
            content_hash text NOT NULL,
            status text NOT NULL CHECK (
                status IN ('draft','parsed','chunked','indexed','active','archived','failed')
            ),
            created_by uuid NULL REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            activated_at timestamptz NULL,
            CONSTRAINT uq_document_versions_no UNIQUE (enterprise_id, document_id, version_no)
        )
        """
    )
    _run("CREATE INDEX idx_document_versions_enterprise_id ON document_versions(enterprise_id)")
    _run("CREATE INDEX idx_document_versions_document_id ON document_versions(document_id)")
    _run("CREATE INDEX idx_document_versions_version_no ON document_versions(version_no)")
    _run("CREATE INDEX idx_document_versions_content_hash ON document_versions(content_hash)")
    _run("CREATE INDEX idx_document_versions_status ON document_versions(status)")
    _run("CREATE INDEX idx_document_versions_created_at ON document_versions(created_at)")
    _run("CREATE INDEX idx_document_versions_activated_at ON document_versions(activated_at)")
    # 同一文档只能有一个 active 版本，避免 citation 回溯出现多义性。
    _run(
        """
        CREATE UNIQUE INDEX uq_document_versions_active
        ON document_versions(enterprise_id, document_id)
        WHERE status = 'active'
        """
    )
    # documents 和 document_versions 存在循环引用，先建表再补当前版本外键。
    _run(
        """
        ALTER TABLE documents
        ADD CONSTRAINT fk_documents_current_version_id
        FOREIGN KEY (current_version_id) REFERENCES document_versions(id)
        """
    )

    # chunks 是 RAG 上下文最小引用单元，必须保存预览、页码、hash 和权限快照。
    _run(
        """
        CREATE TABLE chunks (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            kb_id uuid NOT NULL REFERENCES knowledge_bases(id),
            document_id uuid NOT NULL REFERENCES documents(id),
            document_version_id uuid NOT NULL REFERENCES document_versions(id),
            ordinal integer NOT NULL,
            text_object_key text NULL,
            text_preview text NOT NULL,
            heading_path text NULL,
            page_start integer NULL,
            page_end integer NULL,
            source_offsets jsonb NULL,
            content_hash text NOT NULL,
            token_count integer NOT NULL,
            quality_flags text[] NOT NULL DEFAULT ARRAY[]::text[],
            status text NOT NULL CHECK (status IN ('draft','active','archived','deleted')),
            permission_snapshot_id uuid NULL REFERENCES permission_snapshots(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            deleted_at timestamptz NULL,
            CONSTRAINT uq_chunks_version_ordinal UNIQUE (enterprise_id, document_version_id, ordinal)
        )
        """
    )
    _run("CREATE INDEX idx_chunks_enterprise_id ON chunks(enterprise_id)")
    _run("CREATE INDEX idx_chunks_kb_id ON chunks(kb_id)")
    _run("CREATE INDEX idx_chunks_document_id ON chunks(document_id)")
    _run("CREATE INDEX idx_chunks_document_version_id ON chunks(document_version_id)")
    _run("CREATE INDEX idx_chunks_ordinal ON chunks(ordinal)")
    _run("CREATE INDEX idx_chunks_source_offsets ON chunks USING gin(source_offsets)")
    _run("CREATE INDEX idx_chunks_content_hash ON chunks(content_hash)")
    _run("CREATE INDEX idx_chunks_quality_flags ON chunks USING gin(quality_flags)")
    _run("CREATE INDEX idx_chunks_status ON chunks(status)")
    _run("CREATE INDEX idx_chunks_permission_snapshot_id ON chunks(permission_snapshot_id)")
    _run("CREATE INDEX idx_chunks_active_doc ON chunks(enterprise_id, document_id, document_version_id, status)")

    # index_versions 管理 draft/ready/active 索引发布；新索引失败不得影响旧 active 索引。
    _run(
        """
        CREATE TABLE index_versions (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            kb_id uuid NOT NULL REFERENCES knowledge_bases(id),
            document_id uuid NOT NULL REFERENCES documents(id),
            document_version_id uuid NOT NULL REFERENCES document_versions(id),
            embedding_model text NOT NULL,
            model_version text NOT NULL,
            dimension integer NOT NULL,
            collection_name text NOT NULL,
            status text NOT NULL CHECK (
                status IN ('draft','ready','active','archived','pending_delete','failed')
            ),
            chunk_count integer NOT NULL,
            permission_snapshot_hash text NOT NULL,
            payload_hash text NOT NULL,
            created_by uuid NULL REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            activated_at timestamptz NULL
        )
        """
    )
    _run("CREATE INDEX idx_index_versions_enterprise_id ON index_versions(enterprise_id)")
    _run("CREATE INDEX idx_index_versions_kb_id ON index_versions(kb_id)")
    _run("CREATE INDEX idx_index_versions_document_id ON index_versions(document_id)")
    _run("CREATE INDEX idx_index_versions_document_version_id ON index_versions(document_version_id)")
    _run("CREATE INDEX idx_index_versions_embedding_model ON index_versions(embedding_model)")
    _run("CREATE INDEX idx_index_versions_model_version ON index_versions(model_version)")
    _run("CREATE INDEX idx_index_versions_collection_name ON index_versions(collection_name)")
    _run("CREATE INDEX idx_index_versions_status ON index_versions(status)")
    _run("CREATE INDEX idx_index_versions_permission_snapshot_hash ON index_versions(permission_snapshot_hash)")
    _run("CREATE INDEX idx_index_versions_payload_hash ON index_versions(payload_hash)")
    _run("CREATE INDEX idx_index_versions_created_at ON index_versions(created_at)")
    _run("CREATE INDEX idx_index_versions_activated_at ON index_versions(activated_at)")
    # 同一文档只能有一个 active index，查询链路只读取 active 索引版本。
    _run(
        """
        CREATE UNIQUE INDEX uq_index_versions_active_doc
        ON index_versions(enterprise_id, document_id)
        WHERE status = 'active'
        """
    )

    # keyword_index_entries 是 PostgreSQL Full Text 派生索引，同时携带权限过滤字段。
    _run(
        """
        CREATE TABLE keyword_index_entries (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            chunk_id uuid NOT NULL REFERENCES chunks(id),
            document_id uuid NOT NULL REFERENCES documents(id),
            index_version_id uuid NOT NULL REFERENCES index_versions(id),
            search_text text NOT NULL,
            search_tsv tsvector NOT NULL,
            owner_department_id uuid NOT NULL REFERENCES departments(id),
            visibility text NOT NULL CHECK (visibility IN ('department','enterprise')),
            visibility_state text NOT NULL CHECK (visibility_state IN ('draft','active','blocked','deleted')),
            indexed_permission_version integer NOT NULL,
            payload_hash text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    _run("CREATE INDEX idx_keyword_entries_enterprise_id ON keyword_index_entries(enterprise_id)")
    _run("CREATE INDEX idx_keyword_entries_chunk_id ON keyword_index_entries(chunk_id)")
    _run("CREATE INDEX idx_keyword_entries_document_id ON keyword_index_entries(document_id)")
    _run("CREATE INDEX idx_keyword_entries_index_version_id_raw ON keyword_index_entries(index_version_id)")
    _run("CREATE INDEX idx_keyword_entries_search ON keyword_index_entries USING gin(search_tsv)")
    _run("CREATE INDEX idx_keyword_entries_owner_department_id ON keyword_index_entries(owner_department_id)")
    _run("CREATE INDEX idx_keyword_entries_visibility ON keyword_index_entries(visibility)")
    _run("CREATE INDEX idx_keyword_entries_visibility_state ON keyword_index_entries(visibility_state)")
    _run("CREATE INDEX idx_keyword_entries_indexed_permission_version ON keyword_index_entries(indexed_permission_version)")
    _run("CREATE INDEX idx_keyword_entries_payload_hash ON keyword_index_entries(payload_hash)")
    # 关键词召回必须先下推企业、可见性、部门和 visibility_state。
    _run(
        """
        CREATE INDEX idx_keyword_entries_permission
        ON keyword_index_entries(enterprise_id, visibility, owner_department_id, visibility_state)
        """
    )
    # 同一个 index_version 下只查询 active 可见的关键词索引记录。
    _run(
        """
        CREATE INDEX idx_keyword_entries_index_version
        ON keyword_index_entries(index_version_id, visibility_state)
        """
    )

    # chunk_index_refs 是 Qdrant point、关键词索引和 chunk 之间的事实账本。
    _run(
        """
        CREATE TABLE chunk_index_refs (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            chunk_id uuid NOT NULL REFERENCES chunks(id),
            index_version_id uuid NOT NULL REFERENCES index_versions(id),
            vector_id text NOT NULL UNIQUE,
            keyword_id uuid NULL REFERENCES keyword_index_entries(id),
            visibility_state text NOT NULL CHECK (visibility_state IN ('draft','active','blocked','deleted')),
            indexed_permission_version integer NOT NULL,
            payload_hash text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    _run("CREATE INDEX idx_chunk_index_refs_enterprise_id ON chunk_index_refs(enterprise_id)")
    _run("CREATE INDEX idx_chunk_index_refs_chunk_id ON chunk_index_refs(chunk_id)")
    _run("CREATE INDEX idx_chunk_index_refs_index_version_id ON chunk_index_refs(index_version_id)")
    _run("CREATE INDEX idx_chunk_index_refs_keyword_id ON chunk_index_refs(keyword_id)")
    _run("CREATE INDEX idx_chunk_index_refs_visibility_state ON chunk_index_refs(visibility_state)")
    _run("CREATE INDEX idx_chunk_index_refs_indexed_permission_version ON chunk_index_refs(indexed_permission_version)")
    _run("CREATE INDEX idx_chunk_index_refs_payload_hash ON chunk_index_refs(payload_hash)")
    # 查询只允许命中 active visibility_state，且需要校验索引权限版本。
    _run(
        """
        CREATE INDEX idx_chunk_index_refs_visible
        ON chunk_index_refs(index_version_id, visibility_state, indexed_permission_version)
        """
    )
    _run(
        """
        CREATE INDEX idx_chunk_index_refs_chunk
        ON chunk_index_refs(chunk_id, visibility_state)
        """
    )

    # access_blocks 是删除和权限收紧的 fail closed 边界，必须先阻断再异步清理派生索引。
    _run(
        """
        CREATE TABLE access_blocks (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            resource_type text NOT NULL CHECK (
                resource_type IN (
                    'enterprise','department','user','role','role_binding','permission',
                    'knowledge_base','folder','document','chunk','import_job','config',
                    'query','setup','model_call'
                )
            ),
            resource_id uuid NOT NULL,
            reason text NOT NULL CHECK (
                reason IN ('deleted','permission_tightened','legal_hold','security_incident')
            ),
            block_level text NOT NULL CHECK (block_level IN ('query','citation','all')),
            status text NOT NULL CHECK (status IN ('active','released')),
            created_by uuid NULL REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NULL,
            released_at timestamptz NULL,
            metadata_json jsonb NULL
        )
        """
    )
    _run("CREATE INDEX idx_access_blocks_enterprise_id ON access_blocks(enterprise_id)")
    _run("CREATE INDEX idx_access_blocks_resource_type ON access_blocks(resource_type)")
    _run("CREATE INDEX idx_access_blocks_resource_id ON access_blocks(resource_id)")
    _run("CREATE INDEX idx_access_blocks_reason ON access_blocks(reason)")
    _run("CREATE INDEX idx_access_blocks_block_level ON access_blocks(block_level)")
    _run("CREATE INDEX idx_access_blocks_status ON access_blocks(status)")
    _run("CREATE INDEX idx_access_blocks_created_at ON access_blocks(created_at)")
    _run("CREATE INDEX idx_access_blocks_expires_at ON access_blocks(expires_at)")
    # 查询和 citation 校验都需要快速判断资源是否存在 active 阻断。
    _run(
        """
        CREATE INDEX idx_access_blocks_active
        ON access_blocks(enterprise_id, resource_type, resource_id, status, expires_at)
        """
    )


def downgrade() -> None:
    # 文档、chunk、索引之间外键较多，回滚时按依赖反向顺序删除。
    for table in (
        "access_blocks",
        "chunk_index_refs",
        "keyword_index_entries",
        "index_versions",
        "chunks",
        "document_versions",
        "documents",
        "folders",
        "knowledge_bases",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
