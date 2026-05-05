"""启用 PostgreSQL 扩展。

迁移 ID: 0001_extensions
前置版本:
创建日期: 2026-05-03
"""

from __future__ import annotations

from alembic import op

revision = "0001_extensions"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    # 先删除依赖 zhparser 的 text search configuration，再删除扩展本身。
    op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS little_bear_zh")
    op.execute('DROP EXTENSION IF EXISTS "zhparser"')
    op.execute('DROP EXTENSION IF EXISTS "btree_gin"')
    op.execute('DROP EXTENSION IF EXISTS "pgcrypto"')
