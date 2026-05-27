"""允许部门管理员管理本部门用户。

迁移 ID: 0011_dept_admin_user_manage
前置版本: 0010_config_inactive_status
创建日期: 2026-05-24
"""

from __future__ import annotations

from alembic import op

revision = "0011_dept_admin_user_manage"
down_revision = "0010_config_inactive_status"
branch_labels = None
depends_on = None


def _run(sql: str) -> None:
    op.get_bind().exec_driver_sql(sql)


def upgrade() -> None:
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


def downgrade() -> None:
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
