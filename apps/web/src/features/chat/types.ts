import type { CitationData, QueryConfidence } from "@/api/query";

export type QueryStatus = "idle" | "running" | "done" | "error" | "cancelled";

export type ChatMessageStatus = "running" | "done" | "error" | "cancelled";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: ChatMessageStatus;
  citations: CitationData[];
  confidence: QueryConfidence | null;
  degraded: boolean;
  degradeReason: string | null;
  debugId: string;
  createdAt: number;
};

export type ChatConversation = {
  id: string;
  title: string;
  status: "active" | "deleted";
  kbIds: string[];
  messages: ChatMessage[];
  messagePage: number;
  messagePageSize: number;
  messageTotal: number;
  createdAt: number;
  updatedAt: number;
  lastMessageAt: number | null;
};
