"""创建角色与权限相关表。

迁移 ID: 0003_roles_permissions
前置版本: 0002_setup_config_auth_org
创建日期: 2026-05-03
"""

from __future__ import annotations

from alembic import op

revision = "0003_roles_permissions"
down_revision = "0002_setup_config_auth_org"
branch_labels = None
depends_on = None


def _run(sql: str) -> None:
    # 权限迁移使用原生 SQL，便于显式表达 partial unique 和 CHECK 约束。
    # 这里直接走驱动层执行，避免 SQLAlchemy 误解析原始 SQL 中的 JSON/类型转换语法。
    op.get_bind().exec_driver_sql(sql)


def upgrade() -> None:
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


def downgrade() -> None:
    # 权限快照依赖策略、策略依赖角色绑定，回滚时按反向顺序删除。
    for table in (
        "permission_snapshots",
        "resource_policies",
        "role_bindings",
        "roles",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
