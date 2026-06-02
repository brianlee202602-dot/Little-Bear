import { computed, onMounted, reactive } from "vue";

import { ApiRequestError } from "@/api/http";
import type { QueryMode } from "@/api/query";
import { useAuthSession } from "@/features/auth/useAuthSession";
import type { ChatConversation } from "@/features/chat/types";
import { useConversations } from "@/features/chat/useConversations";
import { useQueryStream } from "@/features/chat/useQueryStream";
import { useKnowledgeBases } from "@/features/knowledge/useKnowledgeBases";
import { useSourcePreview } from "@/features/sources/useSourcePreview";

export function useChatWorkspaceRuntime() {
  const form = reactive({
    query: "",
    mode: "answer" as QueryMode,
    topK: 8,
    includeSources: true,
    streaming: true,
  });
  const loginForm = reactive({
    username: "",
    password: "",
  });

  const knowledgeBaseState = useKnowledgeBases({ formatError: readableError });
  const conversationState = useConversations({ formatError: readableError });
  const authState = useAuthSession({
    formatError: readableError,
    onSessionCleared: clearAuthenticatedContext,
  });
  const queryState = useQueryStream({
    conversationPort: conversationState,
    ensureAccessToken: authState.ensureAccessToken,
    formatError: readableError,
    onBeforeSubmit: resetSourceState,
    onAfterSubmit: () => {
      void refreshConversations(false);
    },
  });
  const sourceState = useSourcePreview({
    ensureAccessToken: authState.ensureAccessToken,
    formatError: readableError,
  });

  const canSubmit = computed(() => {
    return Boolean(
      authState.currentUser.value &&
      knowledgeBaseState.selectedIds.value.length &&
      form.query.trim(),
    );
  });
  const selectedKbLabel = computed(() => {
    if (!authState.authenticated.value) {
      return "登录后选择知识库";
    }
    if (!knowledgeBaseState.items.value.length) {
      return "暂无可查询知识库";
    }
    if (!knowledgeBaseState.selectedItems.value.length) {
      return "请选择知识库";
    }
    return `${knowledgeBaseState.selectedItems.value.length} 个知识库`;
  });
  const submitHint = computed(() => {
    if (!authState.authenticated.value) {
      return "请先登录后再查询。";
    }
    if (!knowledgeBaseState.items.value.length) {
      return "当前账号暂无可查询的知识库。";
    }
    if (!knowledgeBaseState.selectedIds.value.length) {
      return "请至少选择一个知识库。";
    }
    if (!form.query.trim()) {
      return "输入问题后开始查询。";
    }
    return "";
  });
  const knowledgeBaseSelectorFeedback = computed(
    () => knowledgeBaseState.feedback.value || conversationState.feedback.value,
  );
  const statusText = computed(() => {
    if (queryState.status.value === "running") {
      return form.streaming ? "流式生成中" : "查询中";
    }
    if (queryState.status.value === "done") {
      return conversationState.activeAssistantMessage.value?.degraded ? "已降级完成" : "已完成";
    }
    if (queryState.status.value === "error") {
      return "查询失败";
    }
    if (queryState.status.value === "cancelled") {
      return "已取消";
    }
    return "待查询";
  });
  const sourceChunkTotal = computed(() => sourceState.pagination.total);

  onMounted(async () => {
    knowledgeBaseState.restoreSelection();
    await restoreAuthenticatedSession();
  });

  async function submitQuery(): Promise<void> {
    if (!canSubmit.value || queryState.busy.value) {
      return;
    }
    await queryState.submit({
      query: form.query,
      kbIds: [...knowledgeBaseState.selectedIds.value],
      mode: form.mode,
      topK: form.topK,
      includeSources: form.includeSources,
      streaming: form.streaming,
      onAccepted: () => {
        form.query = "";
      },
    });
  }

  async function submitLogin(): Promise<void> {
    const accessToken = await authState.login(loginForm.username, loginForm.password);
    if (!accessToken) {
      return;
    }
    loginForm.password = "";
    await refreshKnowledgeBases();
    await refreshConversations(true);
  }

  async function restoreAuthenticatedSession(): Promise<void> {
    const accessToken = await authState.restore();
    if (!accessToken) {
      return;
    }
    await refreshKnowledgeBases();
    await refreshConversations(true);
  }

  async function logout(): Promise<void> {
    await authState.logout();
    resetResult();
  }

  async function refreshKnowledgeBases(append = false): Promise<void> {
    const accessToken = await authState.ensureAccessToken();
    if (!accessToken) {
      return;
    }
    await knowledgeBaseState.refresh(accessToken, append);
  }

  async function loadMoreKnowledgeBases(): Promise<void> {
    const accessToken = await authState.ensureAccessToken();
    if (!accessToken) {
      return;
    }
    await knowledgeBaseState.loadMore(accessToken);
  }

  async function refreshConversations(selectFirst: boolean): Promise<void> {
    const accessToken = await authState.ensureAccessToken();
    if (!accessToken) {
      return;
    }
    const selected = await conversationState.refresh(accessToken, selectFirst);
    if (selected && selectFirst) {
      knowledgeBaseState.setSelectedIds(selected.kbIds);
      queryState.setStatus(conversationState.statusForConversation(selected));
    }
  }

  function cancelQuery(): void {
    queryState.cancel();
  }

  function resetResult(): void {
    queryState.reset();
    resetSourceState();
  }

  function resetSourceState(): void {
    sourceState.reset();
  }

  function clearAuthenticatedContext(): void {
    knowledgeBaseState.reset();
    conversationState.reset();
    resetSourceState();
  }

  function startNewChat(): void {
    resetResult();
    queryState.setStatus("idle");
    conversationState.startNew();
  }

  async function selectChatRecord(record: ChatConversation): Promise<void> {
    knowledgeBaseState.setSelectedIds(record.kbIds);
    resetSourceState();
    const accessToken = conversationState.isServerConversationId(record.id)
      ? await authState.ensureAccessToken()
      : null;
    const selected = await conversationState.select(record, accessToken);
    queryState.setStatus(conversationState.statusForConversation(selected));
  }

  async function loadOlderConversationMessages(): Promise<void> {
    if (
      !conversationState.activeRecord.value ||
      !conversationState.isServerConversationId(conversationState.activeRecord.value.id) ||
      !conversationState.hasMoreMessages.value
    ) {
      return;
    }
    const accessToken = await authState.ensureAccessToken();
    if (!accessToken) {
      return;
    }
    await conversationState.loadOlder(accessToken);
  }

  async function removeChatRecord(record: ChatConversation): Promise<void> {
    if (queryState.busy.value || conversationState.deletingConversationId.value) {
      return;
    }
    const confirmed = window.confirm("删除后此会话将不再显示，历史问答不会用于后续查询。");
    if (!confirmed) {
      return;
    }
    const accessToken = conversationState.isServerConversationId(record.id)
      ? await authState.ensureAccessToken()
      : null;
    const activeRemoved = await conversationState.remove(record, accessToken);
    if (activeRemoved) {
      startNewChat();
    }
  }

  return {
    activeMessages: conversationState.activeMessages,
    activeRecord: conversationState.activeRecord,
    authBusy: authState.busy,
    authFeedback: authState.feedback,
    authenticated: authState.authenticated,
    busy: queryState.busy,
    canSubmit,
    chatRecords: conversationState.records,
    currentUser: authState.currentUser,
    deletingConversationId: conversationState.deletingConversationId,
    form,
    hasMoreConversationMessages: conversationState.hasMoreMessages,
    hasMoreKnowledgeBases: knowledgeBaseState.hasMore,
    hasMoreSourceChunks: sourceState.hasMore,
    highlightedSourceId: sourceState.highlightedChunkId,
    knowledgeBaseSelectorFeedback,
    knowledgeBases: knowledgeBaseState.items,
    loadingKnowledgeBases: knowledgeBaseState.loading,
    loadingOlderMessages: conversationState.loadingOlder,
    loadingSource: sourceState.loading,
    loginForm,
    selectedKbIds: knowledgeBaseState.selectedIds,
    selectedKbLabel,
    selectedKnowledgeBases: knowledgeBaseState.selectedItems,
    sourceChunks: sourceState.chunks,
    sourceChunkTotal,
    sourceDetail: sourceState.detail,
    sourceFeedback: sourceState.feedback,
    sourceTitle: sourceState.title,
    statusText,
    submitHint,
    cancelQuery,
    clearKnowledgeBaseSelection: knowledgeBaseState.clearSelection,
    loadMoreKnowledgeBases,
    loadMoreSourceChunks: sourceState.loadMore,
    loadOlderConversationMessages,
    openCitation: sourceState.openCitation,
    refreshKnowledgeBases,
    removeChatRecord,
    selectAllKnowledgeBases: knowledgeBaseState.selectAll,
    selectChatRecord,
    startNewChat,
    submitLogin,
    submitQuery,
    toggleKnowledgeBase: knowledgeBaseState.toggle,
    logout,
  };
}

function readableError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    return error.payload?.error_code
      ? `${error.payload.error_code}: ${error.message}`
      : error.message;
  }
  return error instanceof Error ? error.message : "查询请求失败";
}

export type ChatWorkspaceRuntime = ReturnType<typeof useChatWorkspaceRuntime>;
