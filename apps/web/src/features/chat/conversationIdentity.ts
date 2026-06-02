const LOCAL_CONVERSATION_PREFIX = "local-";

export const CONVERSATION_MESSAGE_PAGE_SIZE = 50;

export function createLocalId(prefix = ""): string {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${LOCAL_CONVERSATION_PREFIX}${prefix}${suffix}`;
}

export function isServerConversationId(value: string): boolean {
  return Boolean(value && !isLocalConversationId(value));
}

export function isLocalConversationId(value: string): boolean {
  return value.startsWith(LOCAL_CONVERSATION_PREFIX);
}
