"""创建初始化、配置、认证与组织相关表。

迁移 ID: 0002_setup_config_auth_org
前置版本: 0001_extensions
创建日期: 2026-05-03
"""

from __future__ import annotations

from alembic import op

revision = "0002_setup_config_auth_org"
down_revision = "0001_extensions"
branch_labels = None
depends_on = None


def _run(sql: str) -> None:
    # 迁移中大量使用 PostgreSQL 专有能力，保留原生 SQL 便于审查约束和索引。
    # 这里直接走驱动层执行，避免 SQLAlchemy 将 JSON 文本中的冒号误判为绑定参数。
    op.get_bind().exec_driver_sql(sql)


def upgrade() -> None:
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


def downgrade() -> None:
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
