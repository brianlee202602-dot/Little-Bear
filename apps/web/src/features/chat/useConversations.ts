import { computed, ref } from "vue";

import {
  deleteQueryConversation,
  getQueryConversation,
  listQueryConversations,
} from "@/api/conversations";

import { buildHistoryMessages } from "./conversationHistory";
import {
  CONVERSATION_MESSAGE_PAGE_SIZE,
  isLocalConversationId,
  isServerConversationId,
} from "./conversationIdentity";
import {
  conversationFromData,
  createLocalConversation,
  createLocalMessage,
  messageFromData,
} from "./conversationMappers";
import { statusForConversation } from "./conversationTimeline";
import type { ChatConversation, ChatMessage } from "./types";

type UseConversationsOptions = {
  formatError: (error: unknown) => string;
};

export function useConversations(options: UseConversationsOptions) {
  const records = ref<ChatConversation[]>([]);
  const activeRecordId = ref("");
  const feedback = ref("");
  const loading = ref(false);
  const loadingOlder = ref(false);
  const deletingConversationId = ref("");

  const activeRecord = computed(
    () => records.value.find((record) => record.id === activeRecordId.value) ?? null,
  );
  const activeMessages = computed(() => activeRecord.value?.messages ?? []);
  const activeAssistantMessage = computed(() => {
    const messages = activeMessages.value.filter((message) => message.role === "assistant");
    return messages[messages.length - 1] ?? null;
  });
  const hasMoreMessages = computed(() =>
    Boolean(activeRecord.value && activeMessages.value.length < activeRecord.value.messageTotal),
  );

  function ensureActiveConversation(query: string, kbIds: string[]): ChatConversation {
    if (activeRecord.value) {
      return activeRecord.value;
    }
    const conversation = createLocalConversation(query, kbIds);
    records.value = [conversation, ...records.value].slice(0, 50);
    activeRecordId.value = conversation.id;
    return conversation;
  }

  async function refresh(accessToken: string, selectFirst: boolean): Promise<ChatConversation | null> {
    loading.value = true;
    feedback.value = "";
    try {
      const response = await listQueryConversations(accessToken);
      const existingRecords = new Map(records.value.map((conversation) => [conversation.id, conversation]));
      records.value = response.data.map((item) =>
        conversationFromData(item, existingRecords.get(item.id)?.messages ?? [], existingRecords.get(item.id)),
      );
      if (activeRecordId.value && !records.value.some((item) => item.id === activeRecordId.value)) {
        activeRecordId.value = "";
      }
      if (!activeRecordId.value && selectFirst && records.value.length) {
        return select(records.value[0], accessToken);
      }
      return activeRecord.value;
    } catch (error) {
      feedback.value = options.formatError(error);
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function select(record: ChatConversation, accessToken: string | null): Promise<ChatConversation> {
    activeRecordId.value = record.id;
    if (isLocalConversationId(record.id) || !accessToken) {
      return record;
    }
    loading.value = true;
    feedback.value = "";
    try {
      const response = await getQueryConversation(record.id, accessToken, {
        page: 1,
        page_size: CONVERSATION_MESSAGE_PAGE_SIZE,
      });
      const conversation = conversationFromData(
        response.data,
        response.messages.map(messageFromData),
        response.messages_pagination,
      );
      upsert(conversation);
      return conversation;
    } catch (error) {
      feedback.value = options.formatError(error);
      return record;
    } finally {
      loading.value = false;
    }
  }

  async function loadOlder(accessToken: string): Promise<void> {
    const record = activeRecord.value;
    if (!record || isLocalConversationId(record.id) || loadingOlder.value || !hasMoreMessages.value) {
      return;
    }
    loadingOlder.value = true;
    feedback.value = "";
    try {
      const response = await getQueryConversation(record.id, accessToken, {
        page: record.messagePage + 1,
        page_size: record.messagePageSize,
      });
      const olderMessages = response.messages.map(messageFromData);
      const existingIds = new Set(record.messages.map((message) => message.id));
      const mergedMessages = [
        ...olderMessages.filter((message) => !existingIds.has(message.id)),
        ...record.messages,
      ];
      upsert(conversationFromData(response.data, mergedMessages, response.messages_pagination));
    } catch (error) {
      feedback.value = options.formatError(error);
    } finally {
      loadingOlder.value = false;
    }
  }

  async function remove(record: ChatConversation, accessToken: string | null): Promise<boolean> {
    deletingConversationId.value = record.id;
    feedback.value = "";
    const activeRemoved = activeRecordId.value === record.id;
    try {
      if (isServerConversationId(record.id)) {
        if (!accessToken) {
          throw new Error("请先登录。");
        }
        await deleteQueryConversation(record.id, accessToken);
      }
      records.value = records.value.filter((item) => item.id !== record.id);
      if (activeRemoved) {
        activeRecordId.value = "";
      }
      return activeRemoved;
    } catch (error) {
      feedback.value = options.formatError(error);
      return false;
    } finally {
      deletingConversationId.value = "";
    }
  }

  function startNew(): void {
    activeRecordId.value = "";
  }

  function reset(): void {
    records.value = [];
    activeRecordId.value = "";
    feedback.value = "";
    loading.value = false;
    loadingOlder.value = false;
    deletingConversationId.value = "";
  }

  function appendMessages(conversationId: string, messages: ChatMessage[], kbIds: string[]): void {
    const now = Date.now();
    records.value = records.value.map((conversation) =>
      conversation.id === conversationId
        ? {
            ...conversation,
            kbIds,
            messages: [...conversation.messages, ...messages],
            messageTotal: conversation.messageTotal + messages.length,
            updatedAt: now,
            lastMessageAt: now,
          }
        : conversation,
    );
  }

  function updateMessage(
    messageId: string,
    patch: Partial<ChatMessage> | ((message: ChatMessage) => Partial<ChatMessage>),
  ): void {
    records.value = records.value.map((conversation) => ({
      ...conversation,
      messages: conversation.messages.map((message) =>
        message.id === messageId
          ? {
              ...message,
              ...(typeof patch === "function" ? patch(message) : patch),
            }
          : message,
      ),
      updatedAt: conversation.messages.some((message) => message.id === messageId)
        ? Date.now()
        : conversation.updatedAt,
    }));
  }

  function replaceConversationId(oldId: string, newId: string): void {
    if (!newId || oldId === newId) {
      return;
    }
    records.value = records.value.map((conversation) =>
      conversation.id === oldId ? { ...conversation, id: newId } : conversation,
    );
    if (activeRecordId.value === oldId) {
      activeRecordId.value = newId;
    }
  }

  function upsert(conversation: ChatConversation): void {
    const exists = records.value.some((item) => item.id === conversation.id);
    records.value = exists
      ? records.value.map((item) => (item.id === conversation.id ? conversation : item))
      : [conversation, ...records.value];
  }

  return {
    activeAssistantMessage,
    activeMessages,
    activeRecord,
    activeRecordId,
    deletingConversationId,
    feedback,
    hasMoreMessages,
    loading,
    loadingOlder,
    records,
    appendMessages,
    buildHistoryMessages,
    createLocalMessage,
    ensureActiveConversation,
    isServerConversationId,
    loadOlder,
    remove,
    replaceConversationId,
    reset,
    refresh,
    select,
    startNew,
    statusForConversation,
    updateMessage,
  };
}
