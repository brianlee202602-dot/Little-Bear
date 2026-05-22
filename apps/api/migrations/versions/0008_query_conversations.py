"""新增普通用户查询会话与消息表。

迁移 ID: 0008_query_conversations
前置版本: 0007_dept_admin_read_scopes
创建日期: 2026-05-21
"""

from __future__ import annotations

from alembic import op

revision = "0008_query_conversations"
down_revision = "0007_dept_admin_read_scopes"
branch_labels = None
depends_on = None


def _run(sql: str) -> None:
    op.get_bind().exec_driver_sql(sql)


def upgrade() -> None:
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


def downgrade() -> None:
    _run("DROP TABLE IF EXISTS query_messages")
    _run("DROP TABLE IF EXISTS query_conversations")
