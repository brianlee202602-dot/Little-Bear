import type { SetupFormModel, SetupRequestPayload } from "@/features/setup/setupModel";
import { BUILTIN_ROLES } from "@/features/setup/setupDefaultValues";

export function buildSetupPayload(form: SetupFormModel): SetupRequestPayload {
  // 表单模型偏 UI 友好，请求体必须映射为后端配置契约中的 setup/config 两段结构。
  return {
    setup: {
      admin: {
        username: form.adminUsername,
        display_name: form.adminDisplayName,
        initial_password: form.adminPassword,
        email: form.adminEmail || null,
        phone: form.adminPhone || null,
      },
      organization: {
        enterprise: {
          name: form.enterpriseName,
          code: form.enterpriseCode,
        },
        departments: [
          {
            name: form.departmentName,
            code: form.departmentCode,
            is_default: true,
          },
        ],
      },
      roles: {
        builtin_roles: BUILTIN_ROLES,
        admin_role: "system_admin",
        default_user_role: "employee",
      },
      model_provider_secrets: {
        embedding_auth_token: normalizeOptionalSecretValue(form.embeddingProviderApiKey),
        rerank_auth_token: normalizeOptionalSecretValue(form.rerankProviderApiKey),
        llm_auth_token: normalizeOptionalSecretValue(form.llmProviderApiKey),
      },
    },
    config: {
      schema_version: 1,
      config_version: 1,
      scope: {
        type: "global",
        id: "global",
      },
      secret_provider: {
        type: "postgres_encrypted",
        endpoint: form.secretProviderEndpoint,
        auth_method: "database",
        secret_ref_policy: {
          allowed_namespaces: ["rag"],
          required_prefix: "secret://rag/",
        },
      },
      redis: {
        url: form.redisUrl,
        pool: {
          max_connections: 32,
          connect_timeout_ms: 500,
          socket_timeout_ms: 1000,
          retry_on_timeout: true,
        },
        cache_strategy: {
          permission_context_enabled: true,
          query_cache_enabled: true,
          rate_limit_enabled: true,
          lock_enabled: true,
          config_notify_enabled: true,
        },
      },
      storage: {
        provider: "minio",
        minio_endpoint: form.minioEndpoint,
        bucket: form.minioBucket,
        region: form.minioRegion,
        tls_enabled: false,
        access_key_ref: form.minioAccessKeyRef,
        secret_key_ref: form.minioSecretKeyRef,
        object_key_prefix: form.objectKeyPrefix,
      },
      vector_store: {
        provider: "qdrant",
        qdrant_base_url: form.qdrantBaseUrl,
        api_key_ref: normalizeOptionalSecretValue(form.qdrantApiKeyRef),
        collection_prefix: form.collectionPrefix,
        distance: form.vectorDistance,
        write_check_enabled: true,
        delete_check_enabled: true,
      },
      keyword_search: {
        provider: "postgres_full_text",
        language: form.keywordLanguage,
        keyword_analyzer: form.keywordAnalyzer,
        dictionary_version: "dict-p0-v1",
        synonym_version: "syn-p0-v1",
        stopwords_version: "stop-p0-v1",
        boosts: {
          title: 2,
          heading_path: 1.5,
          body: 1,
          tags: 1.2,
        },
      },
      model_gateway: {
        mode: form.modelGatewayMode,
        auth_token_ref: null,
        providers: {
          embedding: {
            type: "tei",
            base_url: form.embeddingProviderBaseUrl,
            auth_token_ref: null,
            healthcheck_path: "/health",
            embeddings_path: "/v1/embeddings",
          },
          rerank: {
            type: "tei",
            base_url: form.rerankProviderBaseUrl,
            auth_token_ref: null,
            healthcheck_path: "/health",
            rerank_path: "/rerank",
          },
          llm: {
            type: "openai_compatible",
            base_url: form.llmProviderBaseUrl,
            auth_token_ref: null,
            healthcheck_path: "/health",
            chat_completions_path: "/v1/chat/completions",
          },
        },
        routes: {
          embedding: {
            online_default: form.embeddingModel,
            batch_default: form.embeddingModel,
          },
          rerank: {
            default: form.rerankModel,
          },
          llm: {
            default: form.llmModel,
            fallback: form.llmFallbackModel,
          },
        },
        healthcheck: {
          path: "/health",
          timeout_ms: 2000,
          failure_threshold: 3,
        },
      },
      model: {
        embedding_model: form.embeddingModel,
        embedding_version: "2026-04-30",
        embedding_dimension: form.embeddingDimension,
        embedding_normalize: true,
        embedding_tokenizer_version: "jina‑embeddings‑v2‑base‑zh-tokenizer",
        rerank_model: form.rerankModel,
        llm_model: form.llmModel,
        llm_fallback_model: form.llmFallbackModel,
      },
      llm: {
        temperature: form.llmTemperature,
        max_tokens: form.llmMaxTokens,
        first_token_timeout_ms: form.llmFirstTokenTimeoutMs,
        total_timeout_ms: form.llmTotalTimeoutMs,
        retry_policy: {
          max_retries: form.llmMaxRetries,
          backoff_ms: form.llmRetryBackoffMs,
        },
        openai_extra_body: {
          chat_template_kwargs: {
            enable_thinking: form.llmEnableThinking,
          },
        },
      },
      auth: {
        password_min_length: form.passwordMinLength,
        password_require_uppercase: true,
        password_require_lowercase: true,
        password_require_digit: true,
        password_require_symbol: false,
        login_failure_limit: 5,
        lock_minutes: 15,
        access_token_ttl_minutes: form.accessTokenTtlMinutes,
        refresh_token_ttl_minutes: form.refreshTokenTtlMinutes,
        jwt_issuer: form.jwtIssuer,
        jwt_audience: form.jwtAudience,
        jwt_signing_key_ref: form.jwtSigningKeyRef,
      },
      retrieval: {
        vector_top_k: form.vectorTopK,
        keyword_top_k: form.keywordTopK,
        fusion_method: "rrf",
        fusion_params: {
          rrf_k: 60,
          title_boost: 1.2,
          freshness_boost: 1,
          low_ocr_penalty: 0.8,
        },
        rerank_input_top_k: form.rerankInputTopK,
        rerank_min_score: form.rerankMinScore,
        final_context_top_k: form.finalContextTopK,
        max_context_tokens: form.maxContextTokens,
        rewrite_enabled: false,
        expansion_enabled: false,
      },
      chunk: {
        default_size_tokens: form.chunkDefaultSizeTokens,
        overlap_tokens: form.chunkOverlapTokens,
        strategy: {
          mode: form.chunkStrategyMode,
          preserve_tables: form.chunkPreserveTables,
          preserve_code_blocks: form.chunkPreserveCodeBlocks,
          preserve_contract_clauses: form.chunkPreserveContractClauses,
        },
      },
      import: {
        max_file_mb: form.maxFileMb,
        allowed_file_types: ["pdf", "docx", "txt", "md"],
        max_concurrent_jobs: form.maxConcurrentJobs,
        department_concurrent_jobs: 2,
        user_concurrent_jobs: 1,
        file_concurrency_per_job: 2,
        embedding_batch_size: form.embeddingBatchSize,
        index_batch_size: form.indexBatchSize,
        retry_policy: {
          max_retries: 3,
          initial_delay_seconds: 30,
          max_delay_seconds: 600,
          dead_letter_enabled: true,
        },
      },
      permission: {
        default_user_role: "employee",
        default_visibility: form.permissionDefaultVisibility,
        cache_ttl_seconds: form.permissionCacheTtlSeconds,
        tightening_block_policy: {
          write_access_block_first: form.permissionWriteAccessBlockFirst,
          block_old_index_refs: form.permissionBlockOldIndexRefs,
          fail_closed: form.permissionFailClosed,
        },
      },
      security: {
        require_citation: form.securityRequireCitation,
        prompt_leakage_policy: {
          block_internal_prompt_leakage: form.securityBlockInternalPromptLeakage,
          block_secret_ref_leakage: form.securityBlockSecretRefLeakage,
        },
        pii_redaction_policy: {
          enabled: form.securityPiiRedactionEnabled,
          redact_logs: form.securityRedactLogs,
          redact_audit_summary: form.securityRedactAuditSummary,
        },
      },
      cache: {
        permission_context_ttl_seconds: 300,
        query_embedding_enabled: form.queryEmbeddingEnabled,
        query_embedding_ttl_seconds: 3600,
        retrieval_result_enabled: form.retrievalResultEnabled,
        retrieval_result_ttl_seconds: 300,
        final_answer_enabled: form.finalAnswerEnabled,
        final_answer_ttl_seconds: form.finalAnswerEnabled ? 300 : 0,
        cross_user_final_answer_allowed: form.crossUserFinalAnswerAllowed,
      },
      rate_limit: {
        query_qps_per_user: form.queryQpsPerUser,
        ip: {
          qps: 20,
          burst: 40,
        },
        department: {
          query_qps: 20,
          import_concurrency: 2,
        },
        kb: {
          query_qps: 50,
        },
        api_key: {
          qps: 10,
        },
        model_pool: {
          qps: 10,
        },
      },
      timeout: {
        query_total_ms: form.timeoutQueryTotalMs,
        auth_permission_ms: form.timeoutAuthPermissionMs,
        rewrite_ms: form.timeoutRewriteMs,
        embedding_ms: form.timeoutEmbeddingMs,
        vector_search_ms: form.timeoutVectorSearchMs,
        keyword_search_ms: form.timeoutKeywordSearchMs,
        rerank_ms: form.timeoutRerankMs,
        context_ms: form.timeoutContextMs,
        postprocess_ms: form.timeoutPostprocessMs,
      },
      degrade: {
        rewrite_timeout: form.degradeRewriteTimeout,
        embedding_timeout: form.degradeEmbeddingTimeout,
        vector_unavailable: form.degradeVectorUnavailable,
        keyword_unavailable: form.degradeKeywordUnavailable,
        rerank_timeout: form.degradeRerankTimeout,
        llm_timeout: form.degradeLlmTimeout,
        model_pool_overloaded: form.degradeModelPoolOverloaded,
        import_backlog: form.degradeImportBacklog,
      },
      audit: {
        sink: "postgres",
        retention_days: form.auditRetentionDays,
        query_text_mode: form.auditQueryTextMode,
        record_full_prompt: false,
        snippet_max_chars: 300,
        pii_redaction_enabled: true,
      },
      observability: {
        metrics_enabled: form.observabilityMetricsEnabled,
        trace_enabled: form.observabilityTraceEnabled,
        alert_thresholds: {
          active_config_load_failed: form.alertActiveConfigLoadFailed,
          permission_violation_rate: form.alertPermissionViolationRate,
          draft_index_exposure_count: form.alertDraftIndexExposureCount,
          import_failure_rate: form.alertImportFailureRate,
          worker_queue_backlog: form.alertWorkerQueueBacklog,
          llm_timeout_rate: form.alertLlmTimeoutRate,
        },
      },
    },
  };
}

function normalizeOptionalSecretValue(value: string): string | null {
  // 空字符串在请求体中统一转为 null，避免后端误判为已配置的密钥值。
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}
