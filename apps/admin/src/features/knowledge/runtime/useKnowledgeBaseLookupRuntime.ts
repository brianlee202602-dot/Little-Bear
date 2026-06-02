import { computed, ref, type ComputedRef } from "vue";

import {
  listAdminKnowledgeBaseOptions,
  type AdminKnowledgeBaseOptionData,
} from "@/api/knowledgeBases";

type UseKnowledgeBaseLookupRuntimeOptions = {
  canManageKnowledgeBases: ComputedRef<boolean>;
  ensureAccessToken: () => Promise<string | null>;
  getOptionKeyword: () => string;
  getPinnedKnowledgeBases?: () => AdminKnowledgeBaseOptionData[];
  onKnowledgeBaseOptionsChanged?: () => void;
  selectorPageSize: number;
};

export function useKnowledgeBaseLookupRuntime(options: UseKnowledgeBaseLookupRuntimeOptions) {
  const adminKnowledgeBaseOptions = ref<AdminKnowledgeBaseOptionData[]>([]);
  const activeKnowledgeBases = computed(() =>
    adminKnowledgeBaseOptions.value.filter((knowledgeBase) => knowledgeBase.status === "active"),
  );

  function clearKnowledgeBaseOptions(): void {
    adminKnowledgeBaseOptions.value = [];
    options.onKnowledgeBaseOptionsChanged?.();
  }

  async function refreshKnowledgeBaseOptions(existingAccessToken?: string): Promise<void> {
    if (!options.canManageKnowledgeBases.value) {
      clearKnowledgeBaseOptions();
      return;
    }
    const accessToken = existingAccessToken ?? (await options.ensureAccessToken());
    if (!accessToken) {
      return;
    }
    const response = await listAdminKnowledgeBaseOptions(accessToken, {
      keyword: options.getOptionKeyword().trim() || undefined,
      status: "active",
      page_size: options.selectorPageSize,
    });
    adminKnowledgeBaseOptions.value = mergeKnowledgeBaseOptions([
      ...response.data,
      ...(options.getPinnedKnowledgeBases?.() ?? []),
    ]);
    options.onKnowledgeBaseOptionsChanged?.();
  }

  function refreshKnowledgeBaseOptionsFromSearch(): void {
    void refreshKnowledgeBaseOptions();
  }

  function mergeKnowledgeBaseOptions(
    incomingOptions: AdminKnowledgeBaseOptionData[],
  ): AdminKnowledgeBaseOptionData[] {
    const seen = new Set<string>();
    return incomingOptions.filter((knowledgeBase) => {
      if (seen.has(knowledgeBase.id)) {
        return false;
      }
      seen.add(knowledgeBase.id);
      return true;
    });
  }

  return {
    activeKnowledgeBases,
    adminKnowledgeBaseOptions,
    clearKnowledgeBaseOptions,
    refreshKnowledgeBaseOptions,
    refreshKnowledgeBaseOptionsFromSearch,
  };
}
