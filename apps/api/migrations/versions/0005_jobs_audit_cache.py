"""创建任务、审计、查询日志、模型调用日志与缓存表。

迁移 ID: 0005_jobs_audit_cache
前置版本: 0004_knowledge_document_index
创建日期: 2026-05-03
"""

from __future__ import annotations

from alembic import op

revision = "0005_jobs_audit_cache"
down_revision = "0004_knowledge_document_index"
branch_labels = None
depends_on = None


def _run(sql: str) -> None:
    # 任务、审计和缓存表包含表达式索引与 JSON/数组字段，使用原生 SQL 保持约束清晰。
    # 这里直接走驱动层执行，避免 SQLAlchemy 误解析原始 SQL 中的 JSON/类型转换语法。
    op.get_bind().exec_driver_sql(sql)


def upgrade() -> None:
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


def downgrade() -> None:
    # 日志和缓存依赖业务表，回滚时先删除这些派生事实表。
    for table in (
        "model_call_logs",
        "query_logs",
        "audit_logs",
        "query_cache_entries",
        "import_jobs",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
