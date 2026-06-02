export type DisplayTone = "success" | "error" | "warning" | "neutral";

export function formatConfidence(value: string | null | undefined): string {
  if (value === "high") {
    return "高";
  }
  if (value === "medium") {
    return "中";
  }
  if (value === "low") {
    return "低";
  }
  return "-";
}

export function formatKnowledgeBaseStatus(value: string | null | undefined): string {
  if (value === "active") {
    return "启用";
  }
  if (value === "disabled") {
    return "停用";
  }
  if (value === "archived") {
    return "归档";
  }
  return value || "-";
}

export function formatSourceTextStatus(value: string | null | undefined): string {
  if (value === "object") {
    return "完整内容";
  }
  if (value === "preview_only") {
    return "仅预览";
  }
  if (value === "object_unavailable") {
    return "内容不可用";
  }
  return value || "-";
}

export function displayMessageContent(value: string): string {
  return value
    .replace(/(?:\n\s*)?参考来源：\s*(?:\[source:[^\]\s]+\]\s*)+/g, "")
    .replace(/\s*\[source:[^\]\s]+\]/g, "")
    .replace(/\s*\[source:[^\]]*$/g, "")
    .trim();
}

export function toneForStatus(value: string | null | undefined): DisplayTone {
  if (["active", "done", "success", "indexed"].includes(value ?? "")) {
    return "success";
  }
  if (["failed", "error", "deleted", "disabled"].includes(value ?? "")) {
    return "error";
  }
  if (["running", "queued", "draft", "archived"].includes(value ?? "")) {
    return "warning";
  }
  return "neutral";
}
