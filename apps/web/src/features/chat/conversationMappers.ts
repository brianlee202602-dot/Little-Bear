import type { QueryConversationData, QueryMessageData } from "@/api/conversations";
import type { PaginationData } from "@/api/types";

import {
  CONVERSATION_MESSAGE_PAGE_SIZE,
  createLocalId,
} from "./conversationIdentity";
import { sortMessagesForTimeline } from "./conversationTimeline";
import type { ChatConversation, ChatMessage, ChatMessageStatus } from "./types";

export type MessagePaginationState = Pick<PaginationData, "page" | "page_size" | "total">;

export function createLocalConversation(query: string, kbIds: string[]): ChatConversation {
  const now = Date.now();
  return {
    id: createLocalId(),
    title: query.length > 28 ? `${query.slice(0, 28)}...` : query,
    status: "active",
    kbIds,
    messages: [],
    messagePage: 1,
    messagePageSize: CONVERSATION_MESSAGE_PAGE_SIZE,
    messageTotal: 0,
    createdAt: now,
    updatedAt: now,
    lastMessageAt: null,
  };
}

export function createLocalMessage(
  role: ChatMessage["role"],
  content: string,
  statusValue: ChatMessageStatus,
): ChatMessage {
  const now = Date.now();
  return {
    id: createLocalId("msg-"),
    role,
    content,
    status: statusValue,
    citations: [],
    confidence: null,
    degraded: false,
    degradeReason: null,
    debugId: "",
    createdAt: now,
  };
}

export function conversationFromData(
  data: QueryConversationData,
  messages: ChatMessage[] = [],
  messageState?: MessagePaginationState | ChatConversation,
): ChatConversation {
  const existingState = messageState && "messagePage" in messageState ? messageState : null;
  const paginationState = messageState && "page" in messageState ? messageState : null;
  return {
    id: data.id,
    title: data.title,
    status: data.status,
    kbIds: data.kb_ids,
    messages: sortMessagesForTimeline(messages),
    messagePage: existingState?.messagePage ?? paginationState?.page ?? 1,
    messagePageSize:
      existingState?.messagePageSize ??
      paginationState?.page_size ??
      CONVERSATION_MESSAGE_PAGE_SIZE,
    messageTotal: existingState?.messageTotal ?? paginationState?.total ?? messages.length,
    createdAt: parseDateMs(data.created_at),
    updatedAt: parseDateMs(data.updated_at),
    lastMessageAt: data.last_message_at ? parseDateMs(data.last_message_at) : null,
  };
}

export function messageFromData(data: QueryMessageData): ChatMessage {
  return {
    id: data.id,
    role: data.role,
    content: data.content,
    status: data.status,
    citations: data.citations,
    confidence: data.confidence,
    degraded: data.degraded,
    degradeReason: data.degrade_reason,
    debugId: data.debug_id ?? "",
    createdAt: parseDateMs(data.created_at),
  };
}

function parseDateMs(value: string | null): number {
  if (!value) {
    return Date.now();
  }
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : Date.now();
}
