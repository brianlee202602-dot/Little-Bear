import { computed, ref } from "vue";

import {
  createQuery,
  streamQuery,
  type CitationData,
  type QueryHistoryMessage,
  type QueryMode,
  type QueryRequest,
  type QueryResponse,
  type QueryStreamMetadata,
} from "@/api/query";

import type { ChatConversation, ChatMessage, ChatMessageStatus, QueryStatus } from "./types";

export interface QueryConversationPort {
  appendMessages: (conversationId: string, messages: ChatMessage[], kbIds: string[]) => void;
  buildHistoryMessages: (messages: ChatMessage[]) => QueryHistoryMessage[];
  createLocalMessage: (
    role: ChatMessage["role"],
    content: string,
    statusValue: ChatMessageStatus,
  ) => ChatMessage;
  ensureActiveConversation: (query: string, kbIds: string[]) => ChatConversation;
  isServerConversationId: (value: string) => boolean;
  replaceConversationId: (oldId: string, newId: string) => void;
  updateMessage: (
    messageId: string,
    patch: Partial<ChatMessage> | ((message: ChatMessage) => Partial<ChatMessage>),
  ) => void;
}

type UseQueryStreamOptions = {
  conversationPort: QueryConversationPort;
  ensureAccessToken: () => Promise<string | null>;
  formatError: (error: unknown) => string;
  onBeforeSubmit?: () => void;
  onAfterSubmit?: () => void;
};

type SubmitQueryOptions = {
  query: string;
  kbIds: string[];
  mode: QueryMode;
  topK: number;
  includeSources: boolean;
  streaming: boolean;
  onAccepted?: () => void;
};

export function useQueryStream(options: UseQueryStreamOptions) {
  const status = ref<QueryStatus>("idle");
  const metadata = ref<QueryStreamMetadata | null>(null);
  const errorMessage = ref("");
  const lastResponse = ref<QueryResponse | null>(null);
  const abortController = ref<AbortController | null>(null);
  const busy = computed(() => status.value === "running");

  async function submit(submitOptions: SubmitQueryOptions): Promise<void> {
    if (busy.value) {
      return;
    }
    const queryText = submitOptions.query.trim();
    if (!queryText) {
      return;
    }
    options.onBeforeSubmit?.();
    status.value = "running";
    const conversation = options.conversationPort.ensureActiveConversation(
      queryText,
      submitOptions.kbIds,
    );
    const history = options.conversationPort.buildHistoryMessages(conversation.messages);
    const userMessage = options.conversationPort.createLocalMessage("user", queryText, "done");
    const assistantMessage = options.conversationPort.createLocalMessage("assistant", "", "running");
    let assistantMessageId = assistantMessage.id;
    options.conversationPort.appendMessages(
      conversation.id,
      [userMessage, assistantMessage],
      submitOptions.kbIds,
    );
    const payload = buildPayload(
      queryText,
      submitOptions,
      options.conversationPort.isServerConversationId(conversation.id) ? conversation.id : null,
      history,
    );
    submitOptions.onAccepted?.();

    try {
      const accessToken = await options.ensureAccessToken();
      if (!accessToken) {
        throw new Error("请先登录。");
      }
      if (submitOptions.streaming) {
        const controller = new AbortController();
        abortController.value = controller;
        await streamQuery(
          payload,
          accessToken,
          {
            onMetadata: (event) => {
              metadata.value = event;
              if (event.conversation_id) {
                options.conversationPort.replaceConversationId(conversation.id, event.conversation_id);
              }
              const nextMessageId = event.message_id || assistantMessageId;
              options.conversationPort.updateMessage(assistantMessageId, {
                id: nextMessageId,
                confidence: event.confidence,
                degraded: event.degraded,
                degradeReason: event.degrade_reason,
                debugId: event.debug_id,
              });
              assistantMessageId = nextMessageId;
            },
            onToken: (delta) => {
              options.conversationPort.updateMessage(assistantMessageId, (message) => ({
                content: message.content + delta,
              }));
            },
            onCitation: (citation) => {
              options.conversationPort.updateMessage(assistantMessageId, (message) => ({
                citations: mergeCitation(message.citations, citation),
              }));
            },
            onDone: (event) => {
              metadata.value = {
                debug_id: event.debug_id,
                conversation_id: event.conversation_id,
                message_id: event.message_id,
                confidence: event.confidence,
                degraded: event.degraded,
                degrade_reason: event.degrade_reason,
                query_scope: event.query_scope,
              };
              if (event.conversation_id) {
                options.conversationPort.replaceConversationId(conversation.id, event.conversation_id);
              }
              const nextMessageId = event.message_id || assistantMessageId;
              options.conversationPort.updateMessage(assistantMessageId, {
                id: nextMessageId,
                status: "done",
                content: event.answer,
                citations: event.citations,
                confidence: event.confidence,
                degraded: event.degraded,
                degradeReason: event.degrade_reason,
                debugId: event.debug_id,
              });
              assistantMessageId = nextMessageId;
            },
          },
          controller.signal,
        );
        status.value = "done";
        options.conversationPort.updateMessage(assistantMessageId, { status: "done" });
      } else {
        const result = await createQuery(payload, accessToken);
        lastResponse.value = result;
        if (result.conversation_id) {
          options.conversationPort.replaceConversationId(conversation.id, result.conversation_id);
        }
        status.value = "done";
        const nextMessageId = result.message_id || assistantMessageId;
        options.conversationPort.updateMessage(assistantMessageId, {
          id: nextMessageId,
          status: "done",
          content: result.answer,
          citations: result.citations,
          confidence: result.confidence,
          degraded: result.degraded,
          degradeReason: result.degrade_reason,
          debugId: result.debug_id,
        });
        assistantMessageId = nextMessageId;
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        status.value = "cancelled";
        options.conversationPort.updateMessage(assistantMessageId, { status: "cancelled" });
        return;
      }
      status.value = "error";
      errorMessage.value = options.formatError(error);
      options.conversationPort.updateMessage(assistantMessageId, {
        status: "error",
        content: errorMessage.value,
        degraded: true,
        degradeReason: errorMessage.value,
      });
    } finally {
      abortController.value = null;
      options.onAfterSubmit?.();
    }
  }

  function cancel(): void {
    abortController.value?.abort();
  }

  function reset(): void {
    metadata.value = null;
    lastResponse.value = null;
    errorMessage.value = "";
  }

  function setStatus(nextStatus: QueryStatus): void {
    status.value = nextStatus;
  }

  return {
    busy,
    errorMessage,
    lastResponse,
    metadata,
    status,
    cancel,
    reset,
    setStatus,
    submit,
  };
}

function buildPayload(
  queryText: string,
  options: SubmitQueryOptions,
  conversationId: string | null,
  history: QueryHistoryMessage[],
): QueryRequest {
  return {
    kb_ids: options.kbIds,
    query: queryText,
    conversation_id: conversationId,
    history,
    mode: options.mode,
    filters: {},
    top_k: options.topK,
    include_sources: options.includeSources,
  };
}

function mergeCitation(current: CitationData[], citation: CitationData): CitationData[] {
  if (current.some((item) => item.source_id === citation.source_id)) {
    return current;
  }
  return [...current, citation];
}
