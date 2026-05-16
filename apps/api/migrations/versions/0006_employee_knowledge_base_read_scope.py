"""补齐 employee 知识库浏览权限。

迁移 ID: 0006_employee_kb_read
前置版本: 0005_jobs_audit_cache
创建日期: 2026-05-15
"""

from __future__ import annotations

from alembic import op

revision = "0006_employee_kb_read"
down_revision = "0005_jobs_audit_cache"
branch_labels = None
depends_on = None


def _run(sql: str) -> None:
    op.get_bind().exec_driver_sql(sql)


def upgrade() -> None:
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


def downgrade() -> None:
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
