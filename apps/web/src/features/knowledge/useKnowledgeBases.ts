import { computed, reactive, ref } from "vue";

import { listKnowledgeBases, type KnowledgeBaseData } from "@/api/knowledge";
import {
  readStringFromStorage,
  writeStringToStorage,
} from "@/utils/storage";

const KB_STORAGE_KEY = "little-bear.web.kb-ids";
const KNOWLEDGE_BASE_PAGE_SIZE = 50;

type UseKnowledgeBasesOptions = {
  formatError: (error: unknown) => string;
};

export function useKnowledgeBases(options: UseKnowledgeBasesOptions) {
  const items = ref<KnowledgeBaseData[]>([]);
  const selectedText = ref("");
  const feedback = ref("");
  const loading = ref(false);
  const pagination = reactive({
    page: 1,
    pageSize: KNOWLEDGE_BASE_PAGE_SIZE,
    total: 0,
  });

  const selectedIds = computed(() => parseKnowledgeBaseIds(selectedText.value));
  const selectedIdSet = computed(() => new Set(selectedIds.value));
  const selectedItems = computed(() =>
    items.value.filter((knowledgeBase) => selectedIdSet.value.has(knowledgeBase.id)),
  );
  const hasMore = computed(() => items.value.length < pagination.total);

  function restoreSelection(): void {
    selectedText.value = readStringFromStorage(KB_STORAGE_KEY, "session") ?? "";
  }

  async function refresh(accessToken: string, append = false): Promise<void> {
    loading.value = true;
    feedback.value = "";
    try {
      const nextPage = append ? pagination.page + 1 : 1;
      const response = await listKnowledgeBases(accessToken, {
        page: nextPage,
        page_size: pagination.pageSize,
      });
      pagination.page = response.pagination.page;
      pagination.pageSize = response.pagination.page_size;
      pagination.total = response.pagination.total;
      if (append) {
        const existing = new Map(items.value.map((knowledgeBase) => [knowledgeBase.id, knowledgeBase]));
        for (const knowledgeBase of response.data) {
          existing.set(knowledgeBase.id, knowledgeBase);
        }
        items.value = Array.from(existing.values());
      } else {
        items.value = response.data;
      }
      reconcileSelection(items.value);
    } catch (error) {
      feedback.value = options.formatError(error);
    } finally {
      loading.value = false;
    }
  }

  async function loadMore(accessToken: string): Promise<void> {
    if (loading.value || !hasMore.value) {
      return;
    }
    await refresh(accessToken, true);
  }

  function toggle(knowledgeBaseId: string): void {
    const selected = selectedIdSet.value;
    if (selected.has(knowledgeBaseId)) {
      selected.delete(knowledgeBaseId);
    } else {
      selected.add(knowledgeBaseId);
    }
    selectedText.value = Array.from(selected).join("\n");
    persistSelection();
  }

  function selectAll(): void {
    selectedText.value = items.value.map((knowledgeBase) => knowledgeBase.id).join("\n");
    persistSelection();
  }

  function clearSelection(): void {
    selectedText.value = "";
    persistSelection();
  }

  function setSelectedIds(knowledgeBaseIds: string[]): void {
    selectedText.value = knowledgeBaseIds.join("\n");
    persistSelection();
  }

  function reset(options: { clearSelection?: boolean } = {}): void {
    items.value = [];
    pagination.page = 1;
    pagination.total = 0;
    feedback.value = "";
    if (options.clearSelection) {
      selectedText.value = "";
      persistSelection();
    }
  }

  function persistSelection(): void {
    writeStringToStorage(KB_STORAGE_KEY, selectedText.value.trim(), "session");
  }

  function reconcileSelection(availableItems: KnowledgeBaseData[]): void {
    if (!availableItems.length) {
      selectedText.value = "";
      persistSelection();
      return;
    }
    const availableIds = new Set(availableItems.map((item) => item.id));
    const validStoredIds = selectedIds.value.filter((id) => availableIds.has(id));
    const nextIds = validStoredIds.length
      ? validStoredIds
      : availableItems.map((knowledgeBase) => knowledgeBase.id);
    selectedText.value = nextIds.join("\n");
    persistSelection();
  }

  return {
    feedback,
    hasMore,
    items,
    loading,
    pagination,
    selectedIds,
    selectedIdSet,
    selectedItems,
    selectedText,
    clearSelection,
    loadMore,
    refresh,
    reset,
    restoreSelection,
    selectAll,
    setSelectedIds,
    toggle,
  };
}

function parseKnowledgeBaseIds(value: string): string[] {
  return value
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}
