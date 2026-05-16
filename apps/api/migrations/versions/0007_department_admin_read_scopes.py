"""补齐 department_admin 知识库读取与查询权限。

迁移 ID: 0007_dept_admin_read_scopes
前置版本: 0006_employee_kb_read
创建日期: 2026-05-15
"""

from __future__ import annotations

from alembic import op

revision = "0007_dept_admin_read_scopes"
down_revision = "0006_employee_kb_read"
branch_labels = None
depends_on = None

READ_SCOPES = "ARRAY['knowledge_base:read','document:read','rag:query']::text[]"


def _run(sql: str) -> None:
    op.get_bind().exec_driver_sql(sql)


def upgrade() -> None:
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


def downgrade() -> None:
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
