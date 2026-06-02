import type { QueryHistoryMessage } from "@/api/query";
import { displayMessageContent } from "@/utils/display";

import type { ChatMessage } from "./types";

export function buildHistoryMessages(messages: ChatMessage[]): QueryHistoryMessage[] {
  return messages
    .filter((message) => message.status === "done" && message.content.trim())
    .slice(-20)
    .map((message) => ({ role: message.role, content: displayMessageContent(message.content) }));
}
