import {
  asAuditQueryTextMode,
  asBoolean,
  asChunkStrategyMode,
  asModelGatewayMode,
  asNumber,
  asPermissionVisibility,
  asRecord,
  asString,
  asVectorDistance,
} from "@/features/config/configValueCoercion";
import type { SetupFormModel } from "@/features/setup/setupModel";

export function hydrateConfigForm(target: SetupFormModel, config: Record<string, unknown>): void {
  const secretProvider = asRecord(config.secret_provider);
  const redis = asRecord(config.redis);
  const storage = asRecord(config.storage);
  const vectorStore = asRecord(config.vector_store);
  const keywordSearch = asRecord(config.keyword_search);
  const modelGateway = asRecord(config.model_gateway);
  const providers = asRecord(modelGateway?.providers);
  const embeddingProvider = asRecord(providers?.embedding);
  const rerankProvider = asRecord(providers?.rerank);
  const llmProvider = asRecord(providers?.llm);
  const model = asRecord(config.model);
  const auth = asRecord(config.auth);
  const retrieval = asRecord(config.retrieval);
  const chunk = asRecord(config.chunk);
  const chunkStrategy = asRecord(chunk?.strategy);
  const importConfig = asRecord(config.import);
  const cache = asRecord(config.cache);
  const rateLimit = asRecord(config.rate_limit);
  const audit = asRecord(config.audit);
  const llm = asRecord(config.llm);
  const llmRetryPolicy = asRecord(llm?.retry_policy);
  const llmExtraBody = asRecord(llm?.openai_extra_body);
  const llmChatTemplateKwargs = asRecord(llmExtraBody?.chat_template_kwargs);
  const permission = asRecord(config.permission);
  const tighteningPolicy = asRecord(permission?.tightening_block_policy);
  const security = asRecord(config.security);
  const promptLeakagePolicy = asRecord(security?.prompt_leakage_policy);
  const piiRedactionPolicy = asRecord(security?.pii_redaction_policy);
  const timeout = asRecord(config.timeout);
  const degrade = asRecord(config.degrade);
  const observability = asRecord(config.observability);
  const alertThresholds = asRecord(observability?.alert_thresholds);

  target.secretProviderEndpoint = asString(secretProvider?.endpoint, target.secretProviderEndpoint);
  target.redisUrl = asString(redis?.url, target.redisUrl);
  target.minioEndpoint = asString(storage?.minio_endpoint, target.minioEndpoint);
  target.minioBucket = asString(storage?.bucket, target.minioBucket);
  target.minioRegion = asString(storage?.region, target.minioRegion);
  target.objectKeyPrefix = asString(storage?.object_key_prefix, target.objectKeyPrefix);
  target.minioAccessKeyRef = asString(storage?.access_key_ref, target.minioAccessKeyRef);
  target.minioSecretKeyRef = asString(storage?.secret_key_ref, target.minioSecretKeyRef);
  target.qdrantBaseUrl = asString(vectorStore?.qdrant_base_url, target.qdrantBaseUrl);
  target.qdrantApiKeyRef = asString(vectorStore?.api_key_ref, target.qdrantApiKeyRef);
  target.collectionPrefix = asString(vectorStore?.collection_prefix, target.collectionPrefix);
  target.vectorDistance = asVectorDistance(vectorStore?.distance, target.vectorDistance);
  target.keywordLanguage = asString(keywordSearch?.language, target.keywordLanguage);
  target.keywordAnalyzer = asString(keywordSearch?.keyword_analyzer, target.keywordAnalyzer);
  target.modelGatewayMode = asModelGatewayMode(modelGateway?.mode, target.modelGatewayMode);
  target.embeddingProviderBaseUrl = asString(
    embeddingProvider?.base_url,
    target.embeddingProviderBaseUrl,
  );
  target.rerankProviderBaseUrl = asString(rerankProvider?.base_url, target.rerankProviderBaseUrl);
  target.llmProviderBaseUrl = asString(llmProvider?.base_url, target.llmProviderBaseUrl);
  target.embeddingDimension = asNumber(model?.embedding_dimension, target.embeddingDimension);
  target.embeddingModel = asString(model?.embedding_model, target.embeddingModel);
  target.rerankModel = asString(model?.rerank_model, target.rerankModel);
  target.llmModel = asString(model?.llm_model, target.llmModel);
  target.llmFallbackModel = asString(model?.llm_fallback_model, target.llmFallbackModel);
  target.passwordMinLength = asNumber(auth?.password_min_length, target.passwordMinLength);
  target.accessTokenTtlMinutes = asNumber(auth?.access_token_ttl_minutes, target.accessTokenTtlMinutes);
  target.refreshTokenTtlMinutes = asNumber(auth?.refresh_token_ttl_minutes, target.refreshTokenTtlMinutes);
  target.jwtIssuer = asString(auth?.jwt_issuer, target.jwtIssuer);
  target.jwtAudience = asString(auth?.jwt_audience, target.jwtAudience);
  target.jwtSigningKeyRef = asString(auth?.jwt_signing_key_ref, target.jwtSigningKeyRef);
  target.vectorTopK = asNumber(retrieval?.vector_top_k, target.vectorTopK);
  target.keywordTopK = asNumber(retrieval?.keyword_top_k, target.keywordTopK);
  target.rerankInputTopK = asNumber(retrieval?.rerank_input_top_k, target.rerankInputTopK);
  target.rerankMinScore = asNumber(retrieval?.rerank_min_score, target.rerankMinScore);
  target.finalContextTopK = asNumber(retrieval?.final_context_top_k, target.finalContextTopK);
  target.maxContextTokens = asNumber(retrieval?.max_context_tokens, target.maxContextTokens);
  target.chunkDefaultSizeTokens = asNumber(chunk?.default_size_tokens, target.chunkDefaultSizeTokens);
  target.chunkOverlapTokens = asNumber(chunk?.overlap_tokens, target.chunkOverlapTokens);
  target.chunkStrategyMode = asChunkStrategyMode(chunkStrategy?.mode, target.chunkStrategyMode);
  target.chunkPreserveTables = asBoolean(chunkStrategy?.preserve_tables, target.chunkPreserveTables);
  target.chunkPreserveCodeBlocks = asBoolean(
    chunkStrategy?.preserve_code_blocks,
    target.chunkPreserveCodeBlocks,
  );
  target.chunkPreserveContractClauses = asBoolean(
    chunkStrategy?.preserve_contract_clauses,
    target.chunkPreserveContractClauses,
  );
  target.maxFileMb = asNumber(importConfig?.max_file_mb, target.maxFileMb);
  target.maxConcurrentJobs = asNumber(importConfig?.max_concurrent_jobs, target.maxConcurrentJobs);
  target.embeddingBatchSize = asNumber(importConfig?.embedding_batch_size, target.embeddingBatchSize);
  target.indexBatchSize = asNumber(importConfig?.index_batch_size, target.indexBatchSize);
  target.queryEmbeddingEnabled = asBoolean(
    cache?.query_embedding_enabled,
    target.queryEmbeddingEnabled,
  );
  target.retrievalResultEnabled = asBoolean(
    cache?.retrieval_result_enabled,
    target.retrievalResultEnabled,
  );
  target.finalAnswerEnabled = asBoolean(cache?.final_answer_enabled, target.finalAnswerEnabled);
  target.crossUserFinalAnswerAllowed = asBoolean(
    cache?.cross_user_final_answer_allowed,
    target.crossUserFinalAnswerAllowed,
  );
  target.queryQpsPerUser = asNumber(rateLimit?.query_qps_per_user, target.queryQpsPerUser);
  target.auditRetentionDays = asNumber(audit?.retention_days, target.auditRetentionDays);
  target.auditQueryTextMode = asAuditQueryTextMode(audit?.query_text_mode, target.auditQueryTextMode);
  target.llmTemperature = asNumber(llm?.temperature, target.llmTemperature);
  target.llmMaxTokens = asNumber(llm?.max_tokens, target.llmMaxTokens);
  target.llmFirstTokenTimeoutMs = asNumber(llm?.first_token_timeout_ms, target.llmFirstTokenTimeoutMs);
  target.llmTotalTimeoutMs = asNumber(llm?.total_timeout_ms, target.llmTotalTimeoutMs);
  target.llmMaxRetries = asNumber(llmRetryPolicy?.max_retries, target.llmMaxRetries);
  target.llmRetryBackoffMs = asNumber(llmRetryPolicy?.backoff_ms, target.llmRetryBackoffMs);
  target.llmEnableThinking = asBoolean(
    llmChatTemplateKwargs?.enable_thinking,
    target.llmEnableThinking,
  );
  target.permissionDefaultVisibility = asPermissionVisibility(
    permission?.default_visibility,
    target.permissionDefaultVisibility,
  );
  target.permissionCacheTtlSeconds = asNumber(
    permission?.cache_ttl_seconds,
    target.permissionCacheTtlSeconds,
  );
  target.permissionWriteAccessBlockFirst = asBoolean(
    tighteningPolicy?.write_access_block_first,
    target.permissionWriteAccessBlockFirst,
  );
  target.permissionBlockOldIndexRefs = asBoolean(
    tighteningPolicy?.block_old_index_refs,
    target.permissionBlockOldIndexRefs,
  );
  target.permissionFailClosed = asBoolean(tighteningPolicy?.fail_closed, target.permissionFailClosed);
  target.securityRequireCitation = asBoolean(security?.require_citation, target.securityRequireCitation);
  target.securityBlockInternalPromptLeakage = asBoolean(
    promptLeakagePolicy?.block_internal_prompt_leakage,
    target.securityBlockInternalPromptLeakage,
  );
  target.securityBlockSecretRefLeakage = asBoolean(
    promptLeakagePolicy?.block_secret_ref_leakage,
    target.securityBlockSecretRefLeakage,
  );
  target.securityPiiRedactionEnabled = asBoolean(
    piiRedactionPolicy?.enabled,
    target.securityPiiRedactionEnabled,
  );
  target.securityRedactLogs = asBoolean(piiRedactionPolicy?.redact_logs, target.securityRedactLogs);
  target.securityRedactAuditSummary = asBoolean(
    piiRedactionPolicy?.redact_audit_summary,
    target.securityRedactAuditSummary,
  );
  target.timeoutQueryTotalMs = asNumber(timeout?.query_total_ms, target.timeoutQueryTotalMs);
  target.timeoutAuthPermissionMs = asNumber(timeout?.auth_permission_ms, target.timeoutAuthPermissionMs);
  target.timeoutRewriteMs = asNumber(timeout?.rewrite_ms, target.timeoutRewriteMs);
  target.timeoutEmbeddingMs = asNumber(timeout?.embedding_ms, target.timeoutEmbeddingMs);
  target.timeoutVectorSearchMs = asNumber(timeout?.vector_search_ms, target.timeoutVectorSearchMs);
  target.timeoutKeywordSearchMs = asNumber(timeout?.keyword_search_ms, target.timeoutKeywordSearchMs);
  target.timeoutRerankMs = asNumber(timeout?.rerank_ms, target.timeoutRerankMs);
  target.timeoutContextMs = asNumber(timeout?.context_ms, target.timeoutContextMs);
  target.timeoutPostprocessMs = asNumber(timeout?.postprocess_ms, target.timeoutPostprocessMs);
  target.degradeRewriteTimeout = asString(degrade?.rewrite_timeout, target.degradeRewriteTimeout);
  target.degradeEmbeddingTimeout = asString(degrade?.embedding_timeout, target.degradeEmbeddingTimeout);
  target.degradeVectorUnavailable = asString(degrade?.vector_unavailable, target.degradeVectorUnavailable);
  target.degradeKeywordUnavailable = asString(degrade?.keyword_unavailable, target.degradeKeywordUnavailable);
  target.degradeRerankTimeout = asString(degrade?.rerank_timeout, target.degradeRerankTimeout);
  target.degradeLlmTimeout = asString(degrade?.llm_timeout, target.degradeLlmTimeout);
  target.degradeModelPoolOverloaded = asString(
    degrade?.model_pool_overloaded,
    target.degradeModelPoolOverloaded,
  );
  target.degradeImportBacklog = asString(degrade?.import_backlog, target.degradeImportBacklog);
  target.observabilityMetricsEnabled = asBoolean(
    observability?.metrics_enabled,
    target.observabilityMetricsEnabled,
  );
  target.observabilityTraceEnabled = asBoolean(
    observability?.trace_enabled,
    target.observabilityTraceEnabled,
  );
  target.alertActiveConfigLoadFailed = asNumber(
    alertThresholds?.active_config_load_failed,
    target.alertActiveConfigLoadFailed,
  );
  target.alertPermissionViolationRate = asNumber(
    alertThresholds?.permission_violation_rate,
    target.alertPermissionViolationRate,
  );
  target.alertDraftIndexExposureCount = asNumber(
    alertThresholds?.draft_index_exposure_count,
    target.alertDraftIndexExposureCount,
  );
  target.alertImportFailureRate = asNumber(alertThresholds?.import_failure_rate, target.alertImportFailureRate);
  target.alertWorkerQueueBacklog = asNumber(alertThresholds?.worker_queue_backlog, target.alertWorkerQueueBacklog);
  target.alertLlmTimeoutRate = asNumber(alertThresholds?.llm_timeout_rate, target.alertLlmTimeoutRate);
}
