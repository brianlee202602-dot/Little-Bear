"""为配置版本增加 inactive 状态。

迁移 ID: 0010_config_inactive_status
前置版本: 0009_config_version_updated_at
创建日期: 2026-05-22
"""

from __future__ import annotations

from alembic import op

revision = "0010_config_inactive_status"
down_revision = "0009_config_version_updated_at"
branch_labels = None
depends_on = None


def _run(sql: str) -> None:
    op.get_bind().exec_driver_sql(sql)


def upgrade() -> None:
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


def downgrade() -> None:
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
