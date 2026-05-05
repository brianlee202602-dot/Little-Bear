export interface SetupFormModel {
  setupToken: string;
  adminUsername: string;
  adminDisplayName: string;
  adminPassword: string;
  adminPasswordConfirm: string;
  adminEmail: string;
  adminPhone: string;
  enterpriseName: string;
  enterpriseCode: string;
  departmentName: string;
  departmentCode: string;
  secretProviderEndpoint: string;
  redisUrl: string;
  minioEndpoint: string;
  minioBucket: string;
  minioRegion: string;
  minioAccessKeyRef: string;
  minioSecretKeyRef: string;
  objectKeyPrefix: string;
  qdrantBaseUrl: string;
  collectionPrefix: string;
  vectorDistance: "cosine" | "dot" | "euclid";
  keywordLanguage: string;
  keywordAnalyzer: string;
  modelGatewayMode: "external";
  embeddingProviderBaseUrl: string;
  rerankProviderBaseUrl: string;
  llmProviderBaseUrl: string;
  embeddingDimension: number;
  embeddingModel: string;
  rerankModel: string;
  llmModel: string;
  llmFallbackModel: string;
  passwordMinLength: number;
  accessTokenTtlMinutes: number;
  refreshTokenTtlMinutes: number;
  jwtIssuer: string;
  jwtAudience: string;
  jwtSigningKeyRef: string;
  vectorTopK: number;
  keywordTopK: number;
  rerankInputTopK: number;
  finalContextTopK: number;
  maxContextTokens: number;
  chunkDefaultSizeTokens: number;
  chunkOverlapTokens: number;
  chunkStrategyMode: "heading_paragraph" | "fixed_tokens";
  chunkPreserveTables: boolean;
  chunkPreserveCodeBlocks: boolean;
  chunkPreserveContractClauses: boolean;
  maxFileMb: number;
  maxConcurrentJobs: number;
  embeddingBatchSize: number;
  indexBatchSize: number;
  queryEmbeddingEnabled: boolean;
  retrievalResultEnabled: boolean;
  finalAnswerEnabled: boolean;
  crossUserFinalAnswerAllowed: boolean;
  queryQpsPerUser: number;
  auditRetentionDays: number;
  auditQueryTextMode: "none" | "hash" | "plain";
}

export type SetupRequestPayload = {
  setup: Record<string, unknown>;
  config: Record<string, unknown>;
};

const BUILTIN_ROLES = [
  "system_admin",
  "security_admin",
  "audit_admin",
  "department_admin",
  "knowledge_base_admin",
  "employee",
];

export function createDefaultSetupForm(): SetupFormModel {
  return {
    setupToken: "",
    adminUsername: "admin",
    adminDisplayName: "系统管理员",
    adminPassword: "",
    adminPasswordConfirm: "",
    adminEmail: "admin@example.com",
    adminPhone: "",
    enterpriseName: "默认企业",
    enterpriseCode: "default",
    departmentName: "默认部门",
    departmentCode: "default",
    secretProviderEndpoint: "postgres://local-secrets",
    redisUrl: "redis://redis:6379/0",
    minioEndpoint: "http://minio:9000",
    minioBucket: "little-bear-rag",
    minioRegion: "local",
    minioAccessKeyRef: "secret://rag/minio/access-key",
    minioSecretKeyRef: "secret://rag/minio/secret-key",
    objectKeyPrefix: "p0/",
    qdrantBaseUrl: "http://qdrant:6333",
    collectionPrefix: "little_bear_p0",
    vectorDistance: "cosine",
    keywordLanguage: "zh",
    keywordAnalyzer: "zhparser",
    modelGatewayMode: "external",
    embeddingProviderBaseUrl: "http://tei-embedding:80",
    rerankProviderBaseUrl: "http://tei-rerank:80",
    llmProviderBaseUrl: "",
    embeddingDimension: 768,
    embeddingModel: "jina‑embeddings‑v2‑base‑zh",
    rerankModel: "bge-reranker-base",
    llmModel: "qwen3-4b",
    llmFallbackModel: "qwen3-4b",
    passwordMinLength: 12,
    accessTokenTtlMinutes: 30,
    refreshTokenTtlMinutes: 10080,
    jwtIssuer: "little-bear-rag",
    jwtAudience: "little-bear-internal",
    jwtSigningKeyRef: "secret://rag/auth/jwt-signing-key",
    vectorTopK: 20,
    keywordTopK: 20,
    rerankInputTopK: 20,
    finalContextTopK: 8,
    maxContextTokens: 6000,
    chunkDefaultSizeTokens: 800,
    chunkOverlapTokens: 120,
    chunkStrategyMode: "heading_paragraph",
    chunkPreserveTables: true,
    chunkPreserveCodeBlocks: true,
    chunkPreserveContractClauses: true,
    maxFileMb: 50,
    maxConcurrentJobs: 4,
    embeddingBatchSize: 32,
    indexBatchSize: 128,
    queryEmbeddingEnabled: true,
    retrievalResultEnabled: true,
    finalAnswerEnabled: false,
    crossUserFinalAnswerAllowed: false,
    queryQpsPerUser: 2,
    auditRetentionDays: 180,
    auditQueryTextMode: "hash",
  };
}

export function buildSetupPayload(form: SetupFormModel): SetupRequestPayload {
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
        api_key_ref: null,
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
            healthcheck_path: "/health",
            embeddings_path: "/v1/embeddings",
          },
          rerank: {
            type: "tei",
            base_url: form.rerankProviderBaseUrl,
            healthcheck_path: "/health",
            rerank_path: "/rerank",
          },
          llm: {
            type: "openai_compatible",
            base_url: form.llmProviderBaseUrl,
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
        temperature: 0.1,
        max_tokens: 800,
        first_token_timeout_ms: 3000,
        total_timeout_ms: 20000,
        retry_policy: {
          max_retries: 0,
          backoff_ms: 0,
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
        default_visibility: "department",
        cache_ttl_seconds: 300,
        tightening_block_policy: {
          write_access_block_first: true,
          block_old_index_refs: true,
          fail_closed: true,
        },
      },
      security: {
        require_citation: true,
        prompt_leakage_policy: {
          block_internal_prompt_leakage: true,
          block_secret_ref_leakage: true,
        },
        pii_redaction_policy: {
          enabled: true,
          redact_logs: true,
          redact_audit_summary: true,
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
        query_total_ms: 8000,
        auth_permission_ms: 100,
        rewrite_ms: 300,
        embedding_ms: 500,
        vector_search_ms: 500,
        keyword_search_ms: 500,
        rerank_ms: 800,
        context_ms: 200,
        postprocess_ms: 300,
      },
      degrade: {
        rewrite_timeout: "use_original_query",
        embedding_timeout: "keyword_only",
        vector_unavailable: "keyword_and_metadata",
        keyword_unavailable: "vector_and_metadata",
        rerank_timeout: "fusion_score",
        llm_timeout: "return_retrieval_with_citations",
        model_pool_overloaded: "return_retryable_degraded_response",
        import_backlog: "slow_down_import",
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
        metrics_enabled: true,
        trace_enabled: true,
        alert_thresholds: {
          active_config_load_failed: 1,
          permission_violation_rate: 0,
          draft_index_exposure_count: 0,
          import_failure_rate: 0.1,
          worker_queue_backlog: 100,
          llm_timeout_rate: 0.2,
        },
      },
    },
  };
}
