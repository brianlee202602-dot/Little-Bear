"""当前 schema 基线迁移。

迁移 ID: 0013_query_log_scope_summary
前置版本: 无
创建日期: 2026-06-03

本迁移由 0001-0013 的增量迁移压缩而来，用于空库一次性建立当前版本
Schema。已经升级到 0013_query_log_scope_summary 的现有数据库无需重复执行。
低于 0013 的旧库应先使用旧迁移链升级到 head，或重建数据库后执行本基线迁移。
"""

from __future__ import annotations

from alembic import op

revision = "0013_query_log_scope_summary"
down_revision = None
branch_labels = None
depends_on = None


def _run(sql: str) -> None:
    # 迁移中大量使用 PostgreSQL 专有能力，保留原生 SQL 便于审查约束和索引。
    # 这里直接走驱动层执行，避免 SQLAlchemy 将 JSON 文本中的冒号误判为绑定参数。
    op.get_bind().exec_driver_sql(sql)


def upgrade() -> None:
    _install_postgres_extensions()
    _create_identity_config_and_org_schema()
    _create_rbac_and_permission_schema()
    _create_knowledge_document_and_index_schema()
    _create_jobs_audit_query_and_model_log_schema()
    _apply_builtin_role_scope_backfills()
    _create_query_conversation_schema()
    _apply_config_lifecycle_updates()
    _create_retrieval_diagnostics_schema()


def downgrade() -> None:
    _drop_retrieval_diagnostics_schema()
    _revert_config_lifecycle_updates()
    _drop_query_conversation_schema()
    _revert_builtin_role_scope_backfills()
    _drop_jobs_audit_query_and_model_log_schema()
    _drop_knowledge_document_and_index_schema()
    _drop_rbac_and_permission_schema()
    _drop_identity_config_and_org_schema()
    _drop_postgres_extensions()


def _install_postgres_extensions() -> None:
    _upgrade_0001_extensions()


def _drop_postgres_extensions() -> None:
    _downgrade_0001_extensions()


def _create_identity_config_and_org_schema() -> None:
    _upgrade_0002_setup_config_auth_org()


def _drop_identity_config_and_org_schema() -> None:
    _downgrade_0002_setup_config_auth_org()


def _create_rbac_and_permission_schema() -> None:
    _upgrade_0003_roles_permissions()


def _drop_rbac_and_permission_schema() -> None:
    _downgrade_0003_roles_permissions()


def _create_knowledge_document_and_index_schema() -> None:
    _upgrade_0004_knowledge_document_index()


def _drop_knowledge_document_and_index_schema() -> None:
    _downgrade_0004_knowledge_document_index()


def _create_jobs_audit_query_and_model_log_schema() -> None:
    _upgrade_0005_jobs_audit_cache()


def _drop_jobs_audit_query_and_model_log_schema() -> None:
    _downgrade_0005_jobs_audit_cache()


def _apply_builtin_role_scope_backfills() -> None:
    _upgrade_0006_employee_knowledge_base_read_scope()
    _upgrade_0007_department_admin_read_scopes()
    _upgrade_0011_department_admin_user_manage_scope()


def _revert_builtin_role_scope_backfills() -> None:
    _downgrade_0011_department_admin_user_manage_scope()
    _downgrade_0007_department_admin_read_scopes()
    _downgrade_0006_employee_knowledge_base_read_scope()


def _create_query_conversation_schema() -> None:
    _upgrade_0008_query_conversations()


def _drop_query_conversation_schema() -> None:
    _downgrade_0008_query_conversations()


def _apply_config_lifecycle_updates() -> None:
    _upgrade_0009_config_version_updated_at()
    _upgrade_0010_config_inactive_status()


def _revert_config_lifecycle_updates() -> None:
    _downgrade_0010_config_inactive_status()
    _downgrade_0009_config_version_updated_at()


def _create_retrieval_diagnostics_schema() -> None:
    _upgrade_0012_query_retrieval_diagnostics()
    _upgrade_0013_query_log_scope_summary()


def _drop_retrieval_diagnostics_schema() -> None:
    _downgrade_0013_query_log_scope_summary()
    _downgrade_0012_query_retrieval_diagnostics()

# ---- 0001_extensions.py ----
def _upgrade_0001_extensions() -> None:
    # pgcrypto 提供数据库侧摘要和随机能力；当前 UUID 仍优先由应用层生成。
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    # btree_gin 支持普通类型和 GIN 场景的组合索引能力，服务权限过滤与数组查询。
    op.execute('CREATE EXTENSION IF NOT EXISTS "btree_gin"')
    # zhparser 是 P0 中文 PostgreSQL Full Text 的默认分词插件。
    op.execute('CREATE EXTENSION IF NOT EXISTS "zhparser"')

    # 使用项目自有配置名，避免业务 SQL 直接依赖扩展默认配置。
    op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS little_bear_zh")
    op.execute("CREATE TEXT SEARCH CONFIGURATION little_bear_zh (PARSER = zhparser)")
    # P0 先映射常见中文词性到 simple 字典；企业词库和停用词治理后续通过配置版本演进。
    op.execute(
        """
        ALTER TEXT SEARCH CONFIGURATION little_bear_zh
        ADD MAPPING FOR n,v,a,i,e,l WITH simple
        """
    )


def _downgrade_0001_extensions() -> None:
    # 先删除依赖 zhparser 的 text search configuration，再删除扩展本身。
    op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS little_bear_zh")
    op.execute('DROP EXTENSION IF EXISTS "zhparser"')
    op.execute('DROP EXTENSION IF EXISTS "btree_gin"')
    op.execute('DROP EXTENSION IF EXISTS "pgcrypto"')


# ---- 0002_setup_config_auth_org.py ----
def _upgrade_0002_setup_config_auth_org() -> None:
    # P0 当前是单企业部署，但所有业务表保留 enterprise_id，避免后续扩展时重构主键。
    _run(
        """
        CREATE TABLE enterprises (
            id uuid PRIMARY KEY,
            code text NOT NULL UNIQUE,
            name text NOT NULL,
            status text NOT NULL CHECK (status IN ('active','disabled','deleted')),
            org_version integer NOT NULL DEFAULT 1,
            permission_version integer NOT NULL DEFAULT 1,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            deleted_at timestamptz NULL
        )
        """
    )
    _run("CREATE INDEX idx_enterprises_status ON enterprises(status)")
    _run("CREATE INDEX idx_enterprises_org_version ON enterprises(org_version)")
    _run("CREATE INDEX idx_enterprises_permission_version ON enterprises(permission_version)")

    # 用户表只保存账号主体信息；密码凭证拆到 user_credentials，降低敏感字段扩散。
    _run(
        """
        CREATE TABLE users (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            username text NOT NULL,
            display_name text NOT NULL,
            email text NULL,
            phone text NULL,
            status text NOT NULL CHECK (status IN ('active','disabled','locked','deleted')),
            last_login_at timestamptz NULL,
            created_by uuid NULL REFERENCES users(id),
            updated_by uuid NULL REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            deleted_at timestamptz NULL
        )
        """
    )
    _run("CREATE INDEX idx_users_enterprise_id ON users(enterprise_id)")
    _run("CREATE INDEX idx_users_email ON users(email)")
    _run("CREATE INDEX idx_users_status ON users(status)")
    _run("CREATE INDEX idx_users_deleted_at ON users(deleted_at)")
    # 登录名和邮箱都按企业隔离，并排除软删除数据，避免删除后无法重新创建同名用户。
    _run(
        """
        CREATE UNIQUE INDEX uq_users_enterprise_username
        ON users(enterprise_id, lower(username))
        WHERE deleted_at IS NULL
        """
    )
    _run(
        """
        CREATE UNIQUE INDEX uq_users_enterprise_email
        ON users(enterprise_id, lower(email))
        WHERE email IS NOT NULL AND deleted_at IS NULL
        """
    )

    # system_state 是全局控制表，不带 enterprise_id；初始化、配置指针和迁移状态都从这里读取。
    _run(
        """
        CREATE TABLE system_state (
            key text PRIMARY KEY,
            value_json jsonb NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now(),
            updated_by uuid NULL REFERENCES users(id)
        )
        """
    )
    _run("CREATE INDEX idx_system_state_updated_at ON system_state(updated_at)")

    # 空库默认处于未初始化状态；普通业务 API 必须依赖 setup guard 拒绝服务。
    _run(
        """
        INSERT INTO system_state(key, value_json) VALUES
            ('setup_status', '{"status":"not_initialized"}'::jsonb),
            ('initialized', '{"value":false}'::jsonb),
            ('active_config_version', '{"version":null}'::jsonb),
            ('permission_version', '{"version":1}'::jsonb),
            ('schema_migration_version', '{"version":"0002_setup_config_auth_org"}'::jsonb),
            ('recovery_setup_allowed', '{"value":false}'::jsonb),
            ('recovery_reason', '{"reason":null}'::jsonb),
            ('setup_attempt_count', '{"count":0}'::jsonb),
            ('setup_locked_until', '{"until":null}'::jsonb)
        """
    )

    # 密码明文只允许存在于请求生命周期，数据库只保存 hash 和登录失败控制字段。
    _run(
        """
        CREATE TABLE user_credentials (
            user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            password_hash text NOT NULL,
            password_alg text NOT NULL,
            password_updated_at timestamptz NOT NULL DEFAULT now(),
            force_change_password boolean NOT NULL DEFAULT false,
            failed_login_count integer NOT NULL DEFAULT 0,
            locked_until timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    _run("CREATE INDEX idx_user_credentials_locked_until ON user_credentials(locked_until)")

    # 配置版本表保存 active_config 的版本元数据；业务模块只能读取 active 版本。
    _run(
        """
        CREATE TABLE config_versions (
            id uuid PRIMARY KEY,
            version integer NOT NULL UNIQUE,
            scope_type text NOT NULL,
            scope_id text NOT NULL,
            status text NOT NULL CHECK (status IN ('draft','validating','active','archived','failed')),
            config_hash text NOT NULL UNIQUE,
            schema_version integer NOT NULL,
            validation_result_json jsonb NULL,
            risk_level text NOT NULL CHECK (risk_level IN ('low','medium','high','critical')),
            created_by uuid NULL REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            activated_at timestamptz NULL
        )
        """
    )
    _run("CREATE INDEX idx_config_versions_scope_type ON config_versions(scope_type)")
    _run("CREATE INDEX idx_config_versions_scope_id ON config_versions(scope_id)")
    _run("CREATE INDEX idx_config_versions_status ON config_versions(status)")
    _run("CREATE INDEX idx_config_versions_created_at ON config_versions(created_at)")
    _run("CREATE INDEX idx_config_versions_activated_at ON config_versions(activated_at)")
    # 同一时刻只允许一个 active 配置版本，避免模块读取到不一致的业务配置。
    _run(
        """
        CREATE UNIQUE INDEX uq_config_versions_one_active
        ON config_versions((status))
        WHERE status = 'active'
        """
    )
    _run(
        """
        CREATE INDEX idx_config_versions_status_created
        ON config_versions(status, created_at DESC)
        """
    )

    # system_configs 保存版本内的配置项，禁止存放 secret 明文，只能存 secret_ref 或脱敏摘要。
    _run(
        """
        CREATE TABLE system_configs (
            id uuid PRIMARY KEY,
            config_version_id uuid NOT NULL REFERENCES config_versions(id) ON DELETE CASCADE,
            version integer NOT NULL,
            scope_type text NOT NULL,
            scope_id text NOT NULL,
            key text NOT NULL,
            value_json jsonb NOT NULL,
            value_hash text NOT NULL,
            status text NOT NULL CHECK (status IN ('draft','validating','active','archived','failed')),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_system_configs_version_key UNIQUE (config_version_id, key),
            CONSTRAINT uq_system_configs_scope_version_key UNIQUE (scope_type, scope_id, version, key)
        )
        """
    )
    _run("CREATE INDEX idx_system_configs_version ON system_configs(version)")
    _run("CREATE INDEX idx_system_configs_scope_type ON system_configs(scope_type)")
    _run("CREATE INDEX idx_system_configs_scope_id ON system_configs(scope_id)")
    _run("CREATE INDEX idx_system_configs_key ON system_configs(key)")
    _run("CREATE INDEX idx_system_configs_value_json ON system_configs USING gin(value_json)")
    _run("CREATE INDEX idx_system_configs_value_hash ON system_configs(value_hash)")
    _run("CREATE INDEX idx_system_configs_status ON system_configs(status)")

    # P0 Secret Store 使用数据库加密密文承载敏感值，active_config 只引用 secret_ref。
    _run(
        """
        CREATE TABLE secrets (
            id uuid PRIMARY KEY,
            scope_type text NOT NULL,
            scope_id text NOT NULL,
            secret_ref text NOT NULL UNIQUE,
            ciphertext bytea NOT NULL,
            encryption_meta_json jsonb NOT NULL,
            value_hash text NOT NULL,
            status text NOT NULL CHECK (status IN ('active','rotating','revoked','deleted')),
            created_by uuid NULL REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            rotated_at timestamptz NULL
        )
        """
    )
    _run("CREATE INDEX idx_secrets_scope_type ON secrets(scope_type)")
    _run("CREATE INDEX idx_secrets_scope_id ON secrets(scope_id)")
    _run("CREATE INDEX idx_secrets_value_hash ON secrets(value_hash)")
    _run("CREATE INDEX idx_secrets_status ON secrets(status)")

    # JWT 状态表用于吊销、refresh rotation 和 setup JWT 一次性使用；JWT 不保存完整权限上下文。
    _run(
        """
        CREATE TABLE jwt_tokens (
            jti text PRIMARY KEY,
            enterprise_id uuid NULL REFERENCES enterprises(id),
            subject_user_id uuid NULL REFERENCES users(id),
            service_name text NULL,
            token_type text NOT NULL CHECK (token_type IN ('access','refresh','service','setup')),
            status text NOT NULL CHECK (status IN ('active','used','revoked','expired')),
            scopes text[] NOT NULL DEFAULT ARRAY[]::text[],
            issued_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            used_at timestamptz NULL,
            revoked_at timestamptz NULL,
            replaced_by_jti text NULL REFERENCES jwt_tokens(jti),
            metadata_json jsonb NULL
        )
        """
    )
    _run("CREATE INDEX idx_jwt_tokens_enterprise_id ON jwt_tokens(enterprise_id)")
    _run("CREATE INDEX idx_jwt_tokens_subject_user_id ON jwt_tokens(subject_user_id)")
    _run("CREATE INDEX idx_jwt_tokens_service_name ON jwt_tokens(service_name)")
    _run("CREATE INDEX idx_jwt_tokens_token_type ON jwt_tokens(token_type)")
    _run("CREATE INDEX idx_jwt_tokens_status ON jwt_tokens(status)")
    _run("CREATE INDEX idx_jwt_tokens_scopes ON jwt_tokens USING gin(scopes)")
    _run("CREATE INDEX idx_jwt_tokens_issued_at ON jwt_tokens(issued_at)")
    _run("CREATE INDEX idx_jwt_tokens_expires_at ON jwt_tokens(expires_at)")
    _run(
        """
        CREATE INDEX idx_jwt_tokens_subject_status
        ON jwt_tokens(subject_user_id, token_type, status)
        """
    )
    _run("CREATE INDEX idx_jwt_tokens_expires ON jwt_tokens(status, expires_at)")

    # setup token 单独建表，便于强制同一时刻只有一个 active setup JWT。
    _run(
        """
        CREATE TABLE setup_tokens (
            id uuid PRIMARY KEY,
            jwt_jti text NOT NULL UNIQUE REFERENCES jwt_tokens(jti),
            token_hash text NOT NULL UNIQUE,
            status text NOT NULL CHECK (status IN ('active','used','revoked','expired')),
            scopes text[] NOT NULL DEFAULT ARRAY[]::text[],
            issued_by uuid NULL REFERENCES users(id),
            issued_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            used_at timestamptz NULL,
            revoked_at timestamptz NULL,
            revoked_reason text NULL,
            CONSTRAINT ck_setup_tokens_required_scopes CHECK (
                scopes @> ARRAY['setup:validate','setup:initialize']::text[]
            )
        )
        """
    )
    _run("CREATE INDEX idx_setup_tokens_status ON setup_tokens(status)")
    _run("CREATE INDEX idx_setup_tokens_scopes ON setup_tokens USING gin(scopes)")
    _run("CREATE INDEX idx_setup_tokens_issued_at ON setup_tokens(issued_at)")
    _run("CREATE INDEX idx_setup_tokens_expires_at ON setup_tokens(expires_at)")
    _run("CREATE INDEX idx_setup_tokens_status_expires ON setup_tokens(status, expires_at)")
    _run(
        """
        CREATE UNIQUE INDEX uq_setup_tokens_one_active
        ON setup_tokens((status))
        WHERE status = 'active'
        """
    )

    # P0 部门模型不做上下级递归，只保留企业、部门、成员三层。
    _run(
        """
        CREATE TABLE departments (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            code text NOT NULL,
            name text NOT NULL,
            status text NOT NULL CHECK (status IN ('active','disabled','deleted')),
            is_default boolean NOT NULL DEFAULT false,
            org_version integer NOT NULL DEFAULT 1,
            created_by uuid NULL REFERENCES users(id),
            updated_by uuid NULL REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            deleted_at timestamptz NULL,
            CONSTRAINT uq_departments_enterprise_code UNIQUE (enterprise_id, code)
        )
        """
    )
    _run("CREATE INDEX idx_departments_enterprise_id ON departments(enterprise_id)")
    _run("CREATE INDEX idx_departments_name ON departments(name)")
    _run("CREATE INDEX idx_departments_status ON departments(status)")
    _run("CREATE INDEX idx_departments_is_default ON departments(is_default)")
    _run("CREATE INDEX idx_departments_org_version ON departments(org_version)")
    # 每个企业只允许一个 active 默认部门，初始化和兜底分配依赖这个约束。
    _run(
        """
        CREATE UNIQUE INDEX uq_departments_one_default
        ON departments(enterprise_id)
        WHERE is_default = true AND status = 'active'
        """
    )

    # 用户和部门关系支持多部门，但 active 主部门每个用户只能有一个。
    _run(
        """
        CREATE TABLE user_department_memberships (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            user_id uuid NOT NULL REFERENCES users(id),
            department_id uuid NOT NULL REFERENCES departments(id),
            is_primary boolean NOT NULL DEFAULT false,
            status text NOT NULL CHECK (status IN ('active','deleted')),
            created_by uuid NULL REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            deleted_at timestamptz NULL
        )
        """
    )
    _run("CREATE INDEX idx_user_dept_enterprise_id ON user_department_memberships(enterprise_id)")
    _run("CREATE INDEX idx_user_dept_user_id ON user_department_memberships(user_id)")
    _run("CREATE INDEX idx_user_dept_department_id ON user_department_memberships(department_id)")
    _run("CREATE INDEX idx_user_dept_is_primary ON user_department_memberships(is_primary)")
    _run("CREATE INDEX idx_user_dept_status ON user_department_memberships(status)")
    _run(
        """
        CREATE UNIQUE INDEX uq_user_dept_active
        ON user_department_memberships(enterprise_id, user_id, department_id)
        WHERE status = 'active'
        """
    )
    _run(
        """
        CREATE UNIQUE INDEX uq_user_primary_dept
        ON user_department_memberships(enterprise_id, user_id)
        WHERE is_primary = true AND status = 'active'
        """
    )


def _downgrade_0002_setup_config_auth_org() -> None:
    # 按外键依赖的反向顺序删除，避免回滚时触发引用约束失败。
    for table in (
        "user_department_memberships",
        "departments",
        "setup_tokens",
        "jwt_tokens",
        "secrets",
        "system_configs",
        "config_versions",
        "user_credentials",
        "system_state",
        "users",
        "enterprises",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


# ---- 0003_roles_permissions.py ----
def _upgrade_0003_roles_permissions() -> None:
    # roles 定义 RBAC 权限集合；scopes 使用数组便于快速加载和 GIN 查询。
    _run(
        """
        CREATE TABLE roles (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            code text NOT NULL,
            name text NOT NULL,
            scope_type text NOT NULL CHECK (scope_type IN ('enterprise','department','knowledge_base')),
            scopes text[] NOT NULL DEFAULT ARRAY[]::text[],
            is_builtin boolean NOT NULL DEFAULT false,
            status text NOT NULL CHECK (status IN ('active','disabled','archived')),
            created_by uuid NULL REFERENCES users(id),
            updated_by uuid NULL REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_roles_enterprise_code UNIQUE (enterprise_id, code)
        )
        """
    )
    _run("CREATE INDEX idx_roles_enterprise_id ON roles(enterprise_id)")
    _run("CREATE INDEX idx_roles_scopes ON roles USING gin(scopes)")
    _run("CREATE INDEX idx_roles_is_builtin ON roles(is_builtin)")
    _run("CREATE INDEX idx_roles_status ON roles(status)")

    # role_bindings 将角色绑定到企业、部门或知识库作用域，scope_id 约束防止脏授权。
    _run(
        """
        CREATE TABLE role_bindings (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            user_id uuid NOT NULL REFERENCES users(id),
            role_id uuid NOT NULL REFERENCES roles(id),
            scope_type text NOT NULL CHECK (scope_type IN ('enterprise','department','knowledge_base')),
            scope_id uuid NULL,
            status text NOT NULL CHECK (status IN ('active','revoked')),
            created_by uuid NULL REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            revoked_by uuid NULL REFERENCES users(id),
            revoked_at timestamptz NULL,
            CONSTRAINT ck_role_bindings_scope_id CHECK (
                (scope_type = 'enterprise' AND scope_id IS NULL)
                OR (scope_type IN ('department','knowledge_base') AND scope_id IS NOT NULL)
            )
        )
        """
    )
    _run("CREATE INDEX idx_role_bindings_enterprise_id ON role_bindings(enterprise_id)")
    _run("CREATE INDEX idx_role_bindings_user_id ON role_bindings(user_id)")
    _run("CREATE INDEX idx_role_bindings_role_id ON role_bindings(role_id)")
    _run("CREATE INDEX idx_role_bindings_scope_id ON role_bindings(scope_id)")
    _run("CREATE INDEX idx_role_bindings_status ON role_bindings(status)")
    # 企业级绑定没有 scope_id，因此单独使用 partial unique。
    _run(
        """
        CREATE UNIQUE INDEX uq_role_bindings_active_enterprise
        ON role_bindings(enterprise_id, user_id, role_id, scope_type)
        WHERE status = 'active' AND scope_type = 'enterprise' AND scope_id IS NULL
        """
    )
    # 部门级和知识库级绑定必须带 scope_id，避免同一作用域重复授予。
    _run(
        """
        CREATE UNIQUE INDEX uq_role_bindings_active_scoped
        ON role_bindings(enterprise_id, user_id, role_id, scope_type, scope_id)
        WHERE status = 'active' AND scope_id IS NOT NULL
        """
    )

    # resource_policies 保存资源权限策略版本；P0 仅允许 department / enterprise 可见性策略。
    _run(
        """
        CREATE TABLE resource_policies (
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
            version integer NOT NULL,
            policy_json jsonb NOT NULL,
            policy_hash text NOT NULL,
            status text NOT NULL CHECK (status IN ('draft','active','archived')),
            created_by uuid NULL REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            archived_at timestamptz NULL,
            CONSTRAINT uq_resource_policies_version UNIQUE (
                enterprise_id, resource_type, resource_id, version
            )
        )
        """
    )
    _run("CREATE INDEX idx_resource_policies_enterprise_id ON resource_policies(enterprise_id)")
    _run("CREATE INDEX idx_resource_policies_resource_type ON resource_policies(resource_type)")
    _run("CREATE INDEX idx_resource_policies_resource_id ON resource_policies(resource_id)")
    _run("CREATE INDEX idx_resource_policies_version ON resource_policies(version)")
    _run("CREATE INDEX idx_resource_policies_policy_json ON resource_policies USING gin(policy_json)")
    _run("CREATE INDEX idx_resource_policies_policy_hash ON resource_policies(policy_hash)")
    _run("CREATE INDEX idx_resource_policies_status ON resource_policies(status)")
    # 同一资源同一时刻只允许一个 active 策略，权限计算以它为事实源。
    _run(
        """
        CREATE UNIQUE INDEX uq_resource_policies_active
        ON resource_policies(enterprise_id, resource_type, resource_id)
        WHERE status = 'active'
        """
    )

    # permission_snapshots 是写入索引的权限 payload 账本，用于候选回源和权限版本校验。
    _run(
        """
        CREATE TABLE permission_snapshots (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            resource_type text NOT NULL,
            resource_id uuid NOT NULL,
            permission_version integer NOT NULL,
            policy_id uuid NULL REFERENCES resource_policies(id),
            policy_version integer NOT NULL,
            payload_json jsonb NOT NULL,
            payload_hash text NOT NULL,
            owner_department_id uuid NOT NULL REFERENCES departments(id),
            visibility text NOT NULL CHECK (visibility IN ('department','enterprise')),
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    _run("CREATE INDEX idx_permission_snapshots_enterprise_id ON permission_snapshots(enterprise_id)")
    _run("CREATE INDEX idx_permission_snapshots_resource_type ON permission_snapshots(resource_type)")
    _run("CREATE INDEX idx_permission_snapshots_resource_id ON permission_snapshots(resource_id)")
    _run("CREATE INDEX idx_permission_snapshots_permission_version ON permission_snapshots(permission_version)")
    _run("CREATE INDEX idx_permission_snapshots_policy_version ON permission_snapshots(policy_version)")
    _run("CREATE INDEX idx_permission_snapshots_payload_json ON permission_snapshots USING gin(payload_json)")
    _run("CREATE INDEX idx_permission_snapshots_payload_hash ON permission_snapshots(payload_hash)")
    _run("CREATE INDEX idx_permission_snapshots_owner_department_id ON permission_snapshots(owner_department_id)")
    _run("CREATE INDEX idx_permission_snapshots_visibility ON permission_snapshots(visibility)")
    _run("CREATE INDEX idx_permission_snapshots_created_at ON permission_snapshots(created_at)")
    # 查询候选回源时按资源和权限版本取最新快照。
    _run(
        """
        CREATE INDEX idx_permission_snapshots_resource
        ON permission_snapshots(enterprise_id, resource_type, resource_id, permission_version DESC)
        """
    )
    # 检索层权限下推需要按可见性和归属部门快速过滤。
    _run(
        """
        CREATE INDEX idx_permission_snapshots_filter
        ON permission_snapshots(enterprise_id, visibility, owner_department_id)
        """
    )


def _downgrade_0003_roles_permissions() -> None:
    # 权限快照依赖策略、策略依赖角色绑定，回滚时按反向顺序删除。
    for table in (
        "permission_snapshots",
        "resource_policies",
        "role_bindings",
        "roles",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


# ---- 0004_knowledge_document_index.py ----
def _upgrade_0004_knowledge_document_index() -> None:
    # knowledge_bases 是文档组织容器；owner_department_id 仅表示管理归属，不再等同访问边界。
    # kb_visibility 控制知识库是否可发现/可选择，文档可读性由 documents.visibility 继续控制。
    _run(
        """
        CREATE TABLE knowledge_bases (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            name text NOT NULL,
            status text NOT NULL CHECK (status IN ('active','disabled','archived','deleted')),
            owner_department_id uuid NOT NULL REFERENCES departments(id),
            kb_visibility text NOT NULL CHECK (kb_visibility IN ('enterprise','department_acl','private')),
            default_document_visibility text NOT NULL CHECK (default_document_visibility IN ('department','enterprise')),
            default_document_owner_department_id uuid NOT NULL REFERENCES departments(id),
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
    _run("CREATE INDEX idx_kb_visibility ON knowledge_bases(kb_visibility)")
    _run(
        """
        CREATE INDEX idx_kb_default_document_owner_department_id
        ON knowledge_bases(default_document_owner_department_id)
        """
    )
    _run("CREATE INDEX idx_kb_policy_version ON knowledge_bases(policy_version)")
    _run("CREATE INDEX idx_kb_config_scope_id ON knowledge_bases(config_scope_id)")
    _run("CREATE INDEX idx_kb_deleted_at ON knowledge_bases(deleted_at)")
    _run("CREATE INDEX idx_kb_enterprise_status ON knowledge_bases(enterprise_id, status)")
    _run(
        """
        CREATE INDEX idx_kb_owner_visibility
        ON knowledge_bases(enterprise_id, owner_department_id, kb_visibility)
        """
    )

    _run(
        """
        CREATE TABLE knowledge_base_accesses (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            kb_id uuid NOT NULL REFERENCES knowledge_bases(id),
            subject_type text NOT NULL CHECK (subject_type IN ('department','user','role')),
            subject_id uuid NOT NULL,
            permission text NOT NULL CHECK (permission IN ('discover','query','manage')),
            status text NOT NULL CHECK (status IN ('active','revoked')),
            created_by uuid NULL REFERENCES users(id),
            updated_by uuid NULL REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    _run("CREATE INDEX idx_kb_accesses_enterprise_id ON knowledge_base_accesses(enterprise_id)")
    _run("CREATE INDEX idx_kb_accesses_kb_id ON knowledge_base_accesses(kb_id)")
    _run(
        """
        CREATE INDEX idx_kb_accesses_subject
        ON knowledge_base_accesses(enterprise_id, subject_type, subject_id, permission, status)
        """
    )
    _run(
        """
        CREATE UNIQUE INDEX uq_kb_accesses_active
        ON knowledge_base_accesses(enterprise_id, kb_id, subject_type, subject_id, permission)
        WHERE status = 'active'
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


def _downgrade_0004_knowledge_document_index() -> None:
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
        "knowledge_base_accesses",
        "knowledge_bases",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


# ---- 0005_jobs_audit_cache.py ----
def _upgrade_0005_jobs_audit_cache() -> None:
    # import_jobs 是 Worker 领取任务和阶段推进的事实源，HTTP 请求只创建任务。
    _run(
        """
        CREATE TABLE import_jobs (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            job_type text NOT NULL CHECK (
                job_type IN (
                    'upload','url','metadata_batch','index_rebuild',
                    'permission_refresh','index_delete'
                )
            ),
            kb_id uuid NULL REFERENCES knowledge_bases(id),
            document_id uuid NULL REFERENCES documents(id),
            document_version_id uuid NULL REFERENCES document_versions(id),
            status text NOT NULL CHECK (
                status IN (
                    'queued','running','retrying','partial_success',
                    'success','failed','cancelled'
                )
            ),
            stage text NOT NULL CHECK (
                stage IN (
                    'validate','parse','clean','chunk','embed','index',
                    'publish','cleanup','finished'
                )
            ),
            request_json jsonb NOT NULL,
            result_json jsonb NULL,
            error_code text NULL,
            error_message text NULL,
            idempotency_key text NULL,
            attempt_count integer NOT NULL DEFAULT 0,
            max_attempts integer NOT NULL DEFAULT 3,
            locked_by text NULL,
            locked_until timestamptz NULL,
            next_retry_at timestamptz NULL,
            cancel_requested_at timestamptz NULL,
            cancel_requested_by uuid NULL REFERENCES users(id),
            created_by uuid NULL REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz NULL
        )
        """
    )
    _run("CREATE INDEX idx_import_jobs_enterprise_id ON import_jobs(enterprise_id)")
    _run("CREATE INDEX idx_import_jobs_job_type ON import_jobs(job_type)")
    _run("CREATE INDEX idx_import_jobs_kb_id ON import_jobs(kb_id)")
    _run("CREATE INDEX idx_import_jobs_document_id ON import_jobs(document_id)")
    _run("CREATE INDEX idx_import_jobs_document_version_id ON import_jobs(document_version_id)")
    _run("CREATE INDEX idx_import_jobs_status ON import_jobs(status)")
    _run("CREATE INDEX idx_import_jobs_stage ON import_jobs(stage)")
    _run("CREATE INDEX idx_import_jobs_error_code ON import_jobs(error_code)")
    _run("CREATE INDEX idx_import_jobs_idempotency_key ON import_jobs(idempotency_key)")
    _run("CREATE INDEX idx_import_jobs_locked_by ON import_jobs(locked_by)")
    _run("CREATE INDEX idx_import_jobs_locked_until ON import_jobs(locked_until)")
    _run("CREATE INDEX idx_import_jobs_next_retry_at ON import_jobs(next_retry_at)")
    _run("CREATE INDEX idx_import_jobs_cancel_requested_at ON import_jobs(cancel_requested_at)")
    _run("CREATE INDEX idx_import_jobs_cancel_requested_by ON import_jobs(cancel_requested_by)")
    _run("CREATE INDEX idx_import_jobs_created_by ON import_jobs(created_by)")
    _run("CREATE INDEX idx_import_jobs_created_at ON import_jobs(created_at)")
    _run("CREATE INDEX idx_import_jobs_updated_at ON import_jobs(updated_at)")
    _run("CREATE INDEX idx_import_jobs_finished_at ON import_jobs(finished_at)")
    # 幂等键按企业和创建者隔离；系统任务使用 system 作为创建者占位。
    _run(
        """
        CREATE UNIQUE INDEX uq_import_jobs_idempotency
        ON import_jobs(enterprise_id, coalesce(created_by::text, 'system'), idempotency_key)
        WHERE idempotency_key IS NOT NULL
        """
    )
    # Worker 领取任务时优先扫描可运行、锁过期或到达重试时间的任务。
    _run(
        """
        CREATE INDEX idx_import_jobs_claim
        ON import_jobs(status, next_retry_at, locked_until, created_at)
        """
    )
    _run(
        """
        CREATE INDEX idx_import_jobs_admin
        ON import_jobs(enterprise_id, status, stage, created_at DESC)
        """
    )

    # query_cache_entries 统一承载查询 embedding、召回结果和最终答案缓存。
    _run(
        """
        CREATE TABLE query_cache_entries (
            cache_key text PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            user_id uuid NULL REFERENCES users(id),
            entry_type text NOT NULL CHECK (
                entry_type IN ('query_embedding','retrieval_result','final_answer')
            ),
            permission_filter_hash text NOT NULL,
            request_filter_hash text NOT NULL,
            kb_ids_hash text NOT NULL,
            query_hash text NOT NULL,
            config_version integer NOT NULL,
            permission_version integer NOT NULL,
            index_version_hash text NOT NULL,
            model_route_hash text NOT NULL,
            prompt_template_version text NULL,
            value_json jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            CONSTRAINT ck_query_cache_final_answer_user CHECK (
                entry_type <> 'final_answer' OR user_id IS NOT NULL
            )
        )
        """
    )
    # 最终答案缓存默认必须按用户隔离，禁止跨用户复用。
    _run("CREATE INDEX idx_query_cache_enterprise_id ON query_cache_entries(enterprise_id)")
    _run("CREATE INDEX idx_query_cache_user_id ON query_cache_entries(user_id)")
    _run("CREATE INDEX idx_query_cache_entry_type ON query_cache_entries(entry_type)")
    _run("CREATE INDEX idx_query_cache_permission_filter_hash ON query_cache_entries(permission_filter_hash)")
    _run("CREATE INDEX idx_query_cache_request_filter_hash ON query_cache_entries(request_filter_hash)")
    _run("CREATE INDEX idx_query_cache_kb_ids_hash ON query_cache_entries(kb_ids_hash)")
    _run("CREATE INDEX idx_query_cache_query_hash ON query_cache_entries(query_hash)")
    _run("CREATE INDEX idx_query_cache_config_version ON query_cache_entries(config_version)")
    _run("CREATE INDEX idx_query_cache_permission_version ON query_cache_entries(permission_version)")
    _run("CREATE INDEX idx_query_cache_index_version_hash ON query_cache_entries(index_version_hash)")
    _run("CREATE INDEX idx_query_cache_model_route_hash ON query_cache_entries(model_route_hash)")
    _run("CREATE INDEX idx_query_cache_prompt_template_version ON query_cache_entries(prompt_template_version)")
    _run("CREATE INDEX idx_query_cache_expires_at ON query_cache_entries(expires_at)")

    # audit_logs 是高风险操作、拒绝访问、降级和管理动作的审计事实源。
    _run(
        """
        CREATE TABLE audit_logs (
            id uuid PRIMARY KEY,
            enterprise_id uuid NULL REFERENCES enterprises(id),
            request_id text NULL,
            trace_id text NULL,
            event_name text NOT NULL,
            actor_type text NOT NULL,
            actor_id text NULL,
            resource_type text NOT NULL CHECK (
                resource_type IN (
                    'enterprise','department','user','role','role_binding','permission',
                    'knowledge_base','folder','document','chunk','import_job','config',
                    'query','setup','model_call'
                )
            ),
            resource_id text NULL,
            action text NOT NULL,
            result text NOT NULL CHECK (result IN ('success','failure','denied')),
            risk_level text NOT NULL CHECK (risk_level IN ('low','medium','high','critical')),
            config_version integer NULL,
            permission_version integer NULL,
            index_version_hash text NULL,
            summary_json jsonb NOT NULL,
            error_code text NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    _run("CREATE INDEX idx_audit_logs_enterprise_id ON audit_logs(enterprise_id)")
    _run("CREATE INDEX idx_audit_logs_request_id ON audit_logs(request_id)")
    _run("CREATE INDEX idx_audit_logs_trace_id ON audit_logs(trace_id)")
    _run("CREATE INDEX idx_audit_logs_event_name ON audit_logs(event_name)")
    _run("CREATE INDEX idx_audit_logs_actor_type ON audit_logs(actor_type)")
    _run("CREATE INDEX idx_audit_logs_actor_id ON audit_logs(actor_id)")
    _run("CREATE INDEX idx_audit_logs_resource_type ON audit_logs(resource_type)")
    _run("CREATE INDEX idx_audit_logs_resource_id ON audit_logs(resource_id)")
    _run("CREATE INDEX idx_audit_logs_action ON audit_logs(action)")
    _run("CREATE INDEX idx_audit_logs_result ON audit_logs(result)")
    _run("CREATE INDEX idx_audit_logs_risk_level ON audit_logs(risk_level)")
    _run("CREATE INDEX idx_audit_logs_config_version ON audit_logs(config_version)")
    _run("CREATE INDEX idx_audit_logs_permission_version ON audit_logs(permission_version)")
    _run("CREATE INDEX idx_audit_logs_index_version_hash ON audit_logs(index_version_hash)")
    _run("CREATE INDEX idx_audit_logs_summary_json ON audit_logs USING gin(summary_json)")
    _run("CREATE INDEX idx_audit_logs_error_code ON audit_logs(error_code)")
    _run("CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at)")
    # 管理后台按事件、结果、风险等级和时间倒序查询审计。
    _run(
        """
        CREATE INDEX idx_audit_logs_admin
        ON audit_logs(enterprise_id, event_name, result, risk_level, created_at DESC)
        """
    )
    _run(
        """
        CREATE INDEX idx_audit_logs_resource
        ON audit_logs(enterprise_id, resource_type, resource_id, created_at DESC)
        """
    )
    _run(
        """
        CREATE INDEX idx_audit_logs_config_permission
        ON audit_logs(enterprise_id, config_version, permission_version, created_at DESC)
        """
    )

    # query_logs 记录查询链路质量、权限版本、索引版本和降级原因，不保存完整 query 明文。
    _run(
        """
        CREATE TABLE query_logs (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            request_id text NOT NULL,
            trace_id text NOT NULL,
            user_id uuid NOT NULL REFERENCES users(id),
            kb_ids uuid[] NOT NULL DEFAULT ARRAY[]::uuid[],
            query_hash text NOT NULL,
            status text NOT NULL CHECK (status IN ('success','failed','denied')),
            degraded boolean NOT NULL DEFAULT false,
            degrade_reason text NULL,
            config_version integer NOT NULL,
            permission_version integer NOT NULL,
            permission_filter_hash text NOT NULL,
            index_version_hash text NULL,
            model_route_hash text NULL,
            latency_ms integer NOT NULL,
            candidate_count integer NOT NULL,
            citation_count integer NOT NULL,
            error_code text NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    _run("CREATE INDEX idx_query_logs_enterprise_id ON query_logs(enterprise_id)")
    _run("CREATE INDEX idx_query_logs_request_id ON query_logs(request_id)")
    _run("CREATE INDEX idx_query_logs_trace_id ON query_logs(trace_id)")
    _run("CREATE INDEX idx_query_logs_user_id ON query_logs(user_id)")
    _run("CREATE INDEX idx_query_logs_kb_ids ON query_logs USING gin(kb_ids)")
    _run("CREATE INDEX idx_query_logs_query_hash ON query_logs(query_hash)")
    _run("CREATE INDEX idx_query_logs_status ON query_logs(status)")
    _run("CREATE INDEX idx_query_logs_degraded ON query_logs(degraded)")
    _run("CREATE INDEX idx_query_logs_degrade_reason ON query_logs(degrade_reason)")
    _run("CREATE INDEX idx_query_logs_config_version ON query_logs(config_version)")
    _run("CREATE INDEX idx_query_logs_permission_version ON query_logs(permission_version)")
    _run("CREATE INDEX idx_query_logs_permission_filter_hash ON query_logs(permission_filter_hash)")
    _run("CREATE INDEX idx_query_logs_index_version_hash ON query_logs(index_version_hash)")
    _run("CREATE INDEX idx_query_logs_model_route_hash ON query_logs(model_route_hash)")
    _run("CREATE INDEX idx_query_logs_latency_ms ON query_logs(latency_ms)")
    _run("CREATE INDEX idx_query_logs_error_code ON query_logs(error_code)")
    _run("CREATE INDEX idx_query_logs_created_at ON query_logs(created_at)")
    # 审计中心按用户、状态、是否降级和时间倒序查看查询记录。
    _run(
        """
        CREATE INDEX idx_query_logs_admin
        ON query_logs(enterprise_id, user_id, status, degraded, created_at DESC)
        """
    )
    _run(
        """
        CREATE INDEX idx_query_logs_config_permission
        ON query_logs(enterprise_id, config_version, permission_version)
        """
    )

    # model_call_logs 记录模型路由、耗时和 token 摘要，禁止保存完整 prompt 或文档原文。
    _run(
        """
        CREATE TABLE model_call_logs (
            id uuid PRIMARY KEY,
            enterprise_id uuid NULL REFERENCES enterprises(id),
            request_id text NULL,
            trace_id text NOT NULL,
            config_version integer NULL,
            caller text NOT NULL,
            model_type text NOT NULL,
            model_name text NOT NULL,
            model_version text NULL,
            model_route_hash text NOT NULL,
            status text NOT NULL CHECK (status IN ('success','failed','degraded')),
            degraded boolean NOT NULL DEFAULT false,
            latency_ms integer NOT NULL,
            token_usage_json jsonb NULL,
            prompt_hash text NULL,
            input_hash text NULL,
            output_hash text NULL,
            error_code text NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    _run("CREATE INDEX idx_model_call_logs_enterprise_id ON model_call_logs(enterprise_id)")
    _run("CREATE INDEX idx_model_call_logs_request_id ON model_call_logs(request_id)")
    _run("CREATE INDEX idx_model_call_logs_trace_id ON model_call_logs(trace_id)")
    _run("CREATE INDEX idx_model_call_logs_config_version ON model_call_logs(config_version)")
    _run("CREATE INDEX idx_model_call_logs_caller ON model_call_logs(caller)")
    _run("CREATE INDEX idx_model_call_logs_model_type ON model_call_logs(model_type)")
    _run("CREATE INDEX idx_model_call_logs_model_name ON model_call_logs(model_name)")
    _run("CREATE INDEX idx_model_call_logs_model_version ON model_call_logs(model_version)")
    _run("CREATE INDEX idx_model_call_logs_model_route_hash ON model_call_logs(model_route_hash)")
    _run("CREATE INDEX idx_model_call_logs_status ON model_call_logs(status)")
    _run("CREATE INDEX idx_model_call_logs_degraded ON model_call_logs(degraded)")
    _run("CREATE INDEX idx_model_call_logs_latency_ms ON model_call_logs(latency_ms)")
    _run("CREATE INDEX idx_model_call_logs_prompt_hash ON model_call_logs(prompt_hash)")
    _run("CREATE INDEX idx_model_call_logs_input_hash ON model_call_logs(input_hash)")
    _run("CREATE INDEX idx_model_call_logs_output_hash ON model_call_logs(output_hash)")
    _run("CREATE INDEX idx_model_call_logs_error_code ON model_call_logs(error_code)")
    _run("CREATE INDEX idx_model_call_logs_created_at ON model_call_logs(created_at)")
    # migration 完成后更新 system_state 中的 schema 版本，便于 ready 检查和人工排障。
    _run(
        """
        UPDATE system_state
        SET value_json = '{"version":"0005_jobs_audit_cache"}'::jsonb, updated_at = now()
        WHERE key = 'schema_migration_version'
        """
    )


def _downgrade_0005_jobs_audit_cache() -> None:
    # 日志和缓存依赖业务表，回滚时先删除这些派生事实表。
    for table in (
        "model_call_logs",
        "query_logs",
        "audit_logs",
        "query_cache_entries",
        "import_jobs",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


# ---- 0006_employee_knowledge_base_read_scope.py ----
def _upgrade_0006_employee_knowledge_base_read_scope() -> None:
    # 已初始化环境中内置 employee 角色可能缺少 P0-7 新增的知识库浏览 scope。
    _run(
        """
        UPDATE roles
        SET
            scopes = ARRAY(
                SELECT DISTINCT scope
                FROM unnest(scopes || ARRAY['knowledge_base:read']::text[]) AS scope
                ORDER BY scope
            ),
            updated_at = now()
        WHERE code = 'employee'
          AND NOT scopes @> ARRAY['knowledge_base:read']::text[]
        """
    )


def _downgrade_0006_employee_knowledge_base_read_scope() -> None:
    _run(
        """
        UPDATE roles
        SET
            scopes = ARRAY(
                SELECT scope
                FROM unnest(scopes) AS scope
                WHERE scope <> 'knowledge_base:read'
                ORDER BY scope
            ),
            updated_at = now()
        WHERE code = 'employee'
          AND scopes @> ARRAY['knowledge_base:read']::text[]
        """
    )


# ---- 0007_department_admin_read_scopes.py ----
READ_SCOPES = "ARRAY['knowledge_base:read','document:read','rag:query']::text[]"


def _upgrade_0007_department_admin_read_scopes() -> None:
    # 部门管理员可以管理部门成员，也应能在普通用户端读取本部门可见知识库和文档。
    # 实际资源范围仍由 Permission Service 的部门过滤控制。
    _run(
        f"""
        UPDATE roles
        SET
            scopes = ARRAY(
                SELECT DISTINCT scope
                FROM unnest(scopes || {READ_SCOPES}) AS scope
                ORDER BY scope
            ),
            updated_at = now()
        WHERE code = 'department_admin'
          AND NOT scopes @> {READ_SCOPES}
        """
    )


def _downgrade_0007_department_admin_read_scopes() -> None:
    _run(
        f"""
        UPDATE roles
        SET
            scopes = ARRAY(
                SELECT scope
                FROM unnest(scopes) AS scope
                WHERE scope <> ALL({READ_SCOPES})
                ORDER BY scope
            ),
            updated_at = now()
        WHERE code = 'department_admin'
          AND scopes && {READ_SCOPES}
        """
    )


# ---- 0008_query_conversations.py ----
def _upgrade_0008_query_conversations() -> None:
    # query_conversations 是普通用户工作区的会话窗口，不替代 query_logs 审计诊断事实源。
    _run(
        """
        CREATE TABLE query_conversations (
            id uuid PRIMARY KEY,
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            user_id uuid NOT NULL REFERENCES users(id),
            title text NOT NULL,
            status text NOT NULL CHECK (status IN ('active','deleted')),
            kb_ids uuid[] NOT NULL DEFAULT ARRAY[]::uuid[],
            last_message_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            deleted_at timestamptz NULL
        )
        """
    )
    _run("CREATE INDEX idx_query_conversations_enterprise_id ON query_conversations(enterprise_id)")
    _run("CREATE INDEX idx_query_conversations_user_id ON query_conversations(user_id)")
    _run("CREATE INDEX idx_query_conversations_status ON query_conversations(status)")
    _run("CREATE INDEX idx_query_conversations_kb_ids ON query_conversations USING gin(kb_ids)")
    _run(
        """
        CREATE INDEX idx_query_conversations_user_recent
        ON query_conversations(enterprise_id, user_id, status, updated_at DESC)
        """
    )
    _run(
        """
        CREATE INDEX idx_query_conversations_last_message
        ON query_conversations(enterprise_id, user_id, last_message_at DESC NULLS LAST)
        """
    )

    # query_messages 保存用户可见的会话消息；query_logs / model_call_logs 仍负责诊断与审计。
    _run(
        """
        CREATE TABLE query_messages (
            id uuid PRIMARY KEY,
            conversation_id uuid NOT NULL REFERENCES query_conversations(id),
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            user_id uuid NOT NULL REFERENCES users(id),
            role text NOT NULL CHECK (role IN ('user','assistant')),
            content text NOT NULL,
            status text NOT NULL CHECK (status IN ('running','done','error','cancelled')),
            citations_json jsonb NULL,
            confidence text NULL CHECK (confidence IS NULL OR confidence IN ('low','medium','high')),
            degraded boolean NOT NULL DEFAULT false,
            degrade_reason text NULL,
            request_id text NULL,
            trace_id text NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    _run("CREATE INDEX idx_query_messages_conversation_id ON query_messages(conversation_id)")
    _run("CREATE INDEX idx_query_messages_enterprise_id ON query_messages(enterprise_id)")
    _run("CREATE INDEX idx_query_messages_user_id ON query_messages(user_id)")
    _run("CREATE INDEX idx_query_messages_role ON query_messages(role)")
    _run("CREATE INDEX idx_query_messages_status ON query_messages(status)")
    _run("CREATE INDEX idx_query_messages_request_id ON query_messages(request_id)")
    _run("CREATE INDEX idx_query_messages_trace_id ON query_messages(trace_id)")
    _run("CREATE INDEX idx_query_messages_created_at ON query_messages(created_at)")
    _run(
        """
        CREATE INDEX idx_query_messages_conversation_order
        ON query_messages(conversation_id, created_at ASC)
        """
    )


def _downgrade_0008_query_conversations() -> None:
    _run("DROP TABLE IF EXISTS query_messages")
    _run("DROP TABLE IF EXISTS query_conversations")


# ---- 0009_config_version_updated_at.py ----
def _upgrade_0009_config_version_updated_at() -> None:
    _run(
        """
        ALTER TABLE config_versions
        ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now()
        """
    )
    _run("CREATE INDEX idx_config_versions_updated_at ON config_versions(updated_at)")


def _downgrade_0009_config_version_updated_at() -> None:
    _run("DROP INDEX IF EXISTS idx_config_versions_updated_at")
    _run("ALTER TABLE config_versions DROP COLUMN IF EXISTS updated_at")


# ---- 0010_config_inactive_status.py ----
def _upgrade_0010_config_inactive_status() -> None:
    _run("ALTER TABLE config_versions DROP CONSTRAINT IF EXISTS config_versions_status_check")
    _run("ALTER TABLE system_configs DROP CONSTRAINT IF EXISTS system_configs_status_check")
    _run(
        """
        ALTER TABLE config_versions
        ADD CONSTRAINT config_versions_status_check
        CHECK (status IN ('draft','validating','active','inactive','archived','failed'))
        """
    )
    _run(
        """
        ALTER TABLE system_configs
        ADD CONSTRAINT system_configs_status_check
        CHECK (status IN ('draft','validating','active','inactive','archived','failed'))
        """
    )


def _downgrade_0010_config_inactive_status() -> None:
    _run("UPDATE system_configs SET status = 'archived' WHERE status = 'inactive'")
    _run("UPDATE config_versions SET status = 'archived' WHERE status = 'inactive'")
    _run("ALTER TABLE config_versions DROP CONSTRAINT IF EXISTS config_versions_status_check")
    _run("ALTER TABLE system_configs DROP CONSTRAINT IF EXISTS system_configs_status_check")
    _run(
        """
        ALTER TABLE config_versions
        ADD CONSTRAINT config_versions_status_check
        CHECK (status IN ('draft','validating','active','archived','failed'))
        """
    )
    _run(
        """
        ALTER TABLE system_configs
        ADD CONSTRAINT system_configs_status_check
        CHECK (status IN ('draft','validating','active','archived','failed'))
        """
    )


# ---- 0011_department_admin_user_manage_scope.py ----
def _upgrade_0011_department_admin_user_manage_scope() -> None:
    _run(
        """
        UPDATE roles
        SET scopes = ARRAY(
            SELECT DISTINCT scope
            FROM unnest(scopes || ARRAY['user:manage']::text[]) AS s(scope)
            ORDER BY scope
        )
        WHERE code = 'department_admin'
          AND is_builtin = true
        """
    )


def _downgrade_0011_department_admin_user_manage_scope() -> None:
    _run(
        """
        UPDATE roles
        SET scopes = ARRAY(
            SELECT scope
            FROM unnest(scopes) AS s(scope)
            WHERE scope <> 'user:manage'
            ORDER BY scope
        )
        WHERE code = 'department_admin'
          AND is_builtin = true
        """
    )


# ---- 0012_query_retrieval_diagnostics.py ----
def _upgrade_0012_query_retrieval_diagnostics() -> None:
    _run(
        """
        CREATE TABLE query_retrieval_diagnostics (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            enterprise_id uuid NOT NULL REFERENCES enterprises(id),
            query_log_id uuid NOT NULL REFERENCES query_logs(id) ON DELETE CASCADE,
            request_id text NOT NULL,
            trace_id text NOT NULL,
            rewrite_queries jsonb NOT NULL DEFAULT '[]'::jsonb,
            stage_counts jsonb NOT NULL DEFAULT '{}'::jsonb,
            quality_gate jsonb NOT NULL DEFAULT '{}'::jsonb,
            selected_chunks jsonb NOT NULL DEFAULT '[]'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_query_retrieval_diagnostics_log UNIQUE(query_log_id)
        )
        """
    )
    _run(
        """
        CREATE INDEX idx_query_retrieval_diagnostics_enterprise
        ON query_retrieval_diagnostics(enterprise_id, created_at DESC)
        """
    )
    _run(
        """
        CREATE INDEX idx_query_retrieval_diagnostics_request
        ON query_retrieval_diagnostics(request_id)
        """
    )
    _run(
        """
        CREATE INDEX idx_query_retrieval_diagnostics_trace
        ON query_retrieval_diagnostics(trace_id)
        """
    )
    _run(
        """
        CREATE INDEX idx_query_retrieval_diagnostics_stage_counts
        ON query_retrieval_diagnostics USING gin(stage_counts)
        """
    )
    _run(
        """
        CREATE INDEX idx_query_retrieval_diagnostics_quality_gate
        ON query_retrieval_diagnostics USING gin(quality_gate)
        """
    )


def _downgrade_0012_query_retrieval_diagnostics() -> None:
    _run("DROP TABLE IF EXISTS query_retrieval_diagnostics")


# ---- 0013_query_log_scope_summary.py ----
def _upgrade_0013_query_log_scope_summary() -> None:
    _run(
        """
        ALTER TABLE query_logs
            ADD COLUMN query_scope_mode text NOT NULL DEFAULT 'explicit',
            ADD COLUMN resolved_kb_count integer NOT NULL DEFAULT 0,
            ADD COLUMN rewrite_count integer NOT NULL DEFAULT 0
        """
    )
    _run(
        """
        UPDATE query_logs
        SET resolved_kb_count = COALESCE(cardinality(kb_ids), 0),
            rewrite_count = CASE WHEN status = 'success' THEN 1 ELSE 0 END
        """
    )
    _run(
        """
        ALTER TABLE query_logs
            ADD CONSTRAINT ck_query_logs_query_scope_mode
                CHECK (query_scope_mode IN ('explicit', 'auto_all_accessible')),
            ADD CONSTRAINT ck_query_logs_resolved_kb_count
                CHECK (resolved_kb_count >= 0),
            ADD CONSTRAINT ck_query_logs_rewrite_count
                CHECK (rewrite_count >= 0)
        """
    )
    _run(
        """
        CREATE INDEX idx_query_logs_scope_mode_created
        ON query_logs(enterprise_id, query_scope_mode, created_at DESC)
        """
    )


def _downgrade_0013_query_log_scope_summary() -> None:
    _run("DROP INDEX IF EXISTS idx_query_logs_scope_mode_created")
    _run(
        """
        ALTER TABLE query_logs
            DROP CONSTRAINT IF EXISTS ck_query_logs_query_scope_mode,
            DROP CONSTRAINT IF EXISTS ck_query_logs_resolved_kb_count,
            DROP CONSTRAINT IF EXISTS ck_query_logs_rewrite_count,
            DROP COLUMN IF EXISTS query_scope_mode,
            DROP COLUMN IF EXISTS resolved_kb_count,
            DROP COLUMN IF EXISTS rewrite_count
        """
    )
