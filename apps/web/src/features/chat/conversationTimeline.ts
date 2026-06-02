import type { ChatConversation, ChatMessage, QueryStatus } from "./types";

export function sortMessagesForTimeline(messages: ChatMessage[]): ChatMessage[] {
  const indexedMessages = messages.map((message, index) => ({
    groupKey: messageTimelineGroupKey(message, index),
    index,
    message,
  }));
  const firstIndexByGroup = new Map<string, number>();
  for (const item of indexedMessages) {
    if (!firstIndexByGroup.has(item.groupKey)) {
      firstIndexByGroup.set(item.groupKey, item.index);
    }
  }
  return indexedMessages
    .sort((left, right) => {
      const createdAtDiff = left.message.createdAt - right.message.createdAt;
      if (createdAtDiff !== 0) {
        return createdAtDiff;
      }
      const groupDiff =
        (firstIndexByGroup.get(left.groupKey) ?? left.index) -
        (firstIndexByGroup.get(right.groupKey) ?? right.index);
      if (groupDiff !== 0) {
        return groupDiff;
      }
      const roleDiff = messageRoleOrder(left.message) - messageRoleOrder(right.message);
      if (roleDiff !== 0) {
        return roleDiff;
      }
      return left.index - right.index;
    })
    .map((item) => item.message);
}

export function statusForConversation(conversation: ChatConversation | null): QueryStatus {
  if (!conversation || !conversation.messages.length) {
    return "idle";
  }
  const assistants = conversation.messages.filter((message) => message.role === "assistant");
  const latest = assistants[assistants.length - 1] ?? conversation.messages[conversation.messages.length - 1];
  return latest.status === "done" ? "done" : latest.status;
}

function messageTimelineGroupKey(message: ChatMessage, index: number): string {
  if (message.debugId) {
    return `${message.createdAt}:${message.debugId}`;
  }
  return `${message.createdAt}:${index}`;
}

function messageRoleOrder(message: ChatMessage): number {
  return message.role === "user" ? 0 : 1;
}
