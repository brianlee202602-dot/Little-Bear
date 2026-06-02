import {
  asRecord,
  cloneJsonRecord,
  isRecord,
} from "@/features/config/configValueCoercion";

export function mergeConfigSectionValue(
  key: string,
  baseValue: Record<string, unknown> | undefined,
  formValue: Record<string, unknown>,
): Record<string, unknown> {
  const base = baseValue ? cloneJsonRecord(baseValue) : {};
  if (key === "model_gateway") {
    return mergeModelGatewayConfig(base, formValue);
  }
  if (key === "model") {
    return mergeModelConfig(base, formValue);
  }
  if (key === "cache") {
    return mergeCacheConfig(base, formValue);
  }
  return deepMerge(base, formValue);
}

function mergeModelGatewayConfig(
  base: Record<string, unknown>,
  formValue: Record<string, unknown>,
): Record<string, unknown> {
  const merged = deepMerge(base, formValue);
  preserveOptionalSecretRef(merged, base, formValue, "auth_token_ref");
  const formProviders = asRecord(formValue.providers);
  const providers = asRecord(merged.providers);
  const baseProviders = asRecord(base.providers);
  for (const key of ["embedding", "rerank", "llm"]) {
    const provider = asRecord(providers?.[key]);
    const formProvider = asRecord(formProviders?.[key]);
    const baseProvider = asRecord(baseProviders?.[key]);
    if (provider && formProvider) {
      preserveOptionalSecretRef(provider, baseProvider, formProvider, "auth_token_ref");
      provider.base_url = formProvider.base_url;
    }
  }
  const routes = asRecord(merged.routes);
  const formRoutes = asRecord(formValue.routes);
  const embeddingRoute = asRecord(routes?.embedding);
  const formEmbeddingRoute = asRecord(formRoutes?.embedding);
  if (embeddingRoute && formEmbeddingRoute) {
    embeddingRoute.online_default = formEmbeddingRoute.online_default;
    embeddingRoute.batch_default = formEmbeddingRoute.batch_default;
  }
  const rerankRoute = asRecord(routes?.rerank);
  const formRerankRoute = asRecord(formRoutes?.rerank);
  if (rerankRoute && formRerankRoute) {
    rerankRoute.default = formRerankRoute.default;
  }
  const llmRoute = asRecord(routes?.llm);
  const formLlmRoute = asRecord(formRoutes?.llm);
  if (llmRoute && formLlmRoute) {
    llmRoute.default = formLlmRoute.default;
    llmRoute.fallback = formLlmRoute.fallback;
  }
  return merged;
}

function preserveOptionalSecretRef(
  target: Record<string, unknown>,
  base: Record<string, unknown> | null,
  patch: Record<string, unknown> | null,
  key: string,
): void {
  const baseValue = base?.[key];
  const patchValue = patch?.[key];
  if (
    typeof baseValue === "string" &&
    baseValue.trim().length > 0 &&
    (patchValue === null || patchValue === undefined || patchValue === "")
  ) {
    target[key] = baseValue;
  }
}

function mergeModelConfig(
  base: Record<string, unknown>,
  formValue: Record<string, unknown>,
): Record<string, unknown> {
  const merged = deepMerge(base, formValue);
  for (const key of [
    "embedding_model",
    "embedding_dimension",
    "rerank_model",
    "llm_model",
    "llm_fallback_model",
  ]) {
    merged[key] = formValue[key];
  }
  return merged;
}

function mergeCacheConfig(
  base: Record<string, unknown>,
  formValue: Record<string, unknown>,
): Record<string, unknown> {
  const merged = deepMerge(base, formValue);
  merged.final_answer_ttl_seconds = formValue.final_answer_enabled === true ? 300 : 0;
  return merged;
}

function deepMerge(
  base: Record<string, unknown>,
  patch: Record<string, unknown>,
): Record<string, unknown> {
  const result = cloneJsonRecord(base);
  for (const [key, value] of Object.entries(patch)) {
    const baseChild = asRecord(result[key]);
    if (baseChild && isRecord(value) && !Array.isArray(value)) {
      result[key] = deepMerge(baseChild, value);
    } else {
      result[key] = value;
    }
  }
  return result;
}
