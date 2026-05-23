"""为配置版本增加更新时间字段。

迁移 ID: 0009_config_version_updated_at
前置版本: 0008_query_conversations
创建日期: 2026-05-22
"""

from __future__ import annotations

from alembic import op

revision = "0009_config_version_updated_at"
down_revision = "0008_query_conversations"
branch_labels = None
depends_on = None


def _run(sql: str) -> None:
    op.get_bind().exec_driver_sql(sql)


def upgrade() -> None:
    _run(
        """
        ALTER TABLE config_versions
        ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now()
        """
    )
    _run("CREATE INDEX idx_config_versions_updated_at ON config_versions(updated_at)")


def downgrade() -> None:
    _run("DROP INDEX IF EXISTS idx_config_versions_updated_at")
    _run("ALTER TABLE config_versions DROP COLUMN IF EXISTS updated_at")
