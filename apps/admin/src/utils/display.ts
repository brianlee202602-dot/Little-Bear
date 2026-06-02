export type DisplayTone = "success" | "error" | "warning" | "neutral";

export function formatStatusText(status: string | null | undefined): string {
  if (!status) {
    return "-";
  }
  const labels: Record<string, string> = {
    active: "启用",
    archived: "已归档",
    cancelled: "已取消",
    deleted: "已删除",
    denied: "拒绝",
    disabled: "禁用",
    done: "完成",
    draft: "草稿",
    failed: "失败",
    inactive: "未启用",
    indexed: "已索引",
    indexing: "索引中",
    index_failed: "索引失败",
    locked: "锁定",
    metadata_batch: "元数据批量任务",
    none: "未索引",
    pending: "等待中",
    pending_delete: "待清理",
    permission_refresh: "权限刷新",
    processing: "处理中",
    published: "已发布",
    queued: "排队中",
    ready: "就绪",
    retrying: "重试中",
    running: "运行中",
    success: "成功",
    partial_success: "部分成功",
    upload: "文件导入",
    url: "链接导入",
    validating: "校验中",
    blocked: "已阻断",
    degraded: "已降级",
    embedding: "向量化",
    green: "正常",
    yellow: "告警",
    red: "异常",
    index_rebuild: "索引重建",
    llm: "大模型",
    rerank: "重排",
    unknown: "未知",
    unreachable: "不可达",
  };
  return labels[status] ?? status;
}

export function formatStatusOption(status: string): string {
  return formatStatusText(status);
}

export function toneForStatus(status: string | null | undefined): DisplayTone {
  if (["active", "done", "indexed", "success"].includes(status ?? "")) {
    return "success";
  }
  if (["deleted", "denied", "disabled", "failed", "locked"].includes(status ?? "")) {
    return "error";
  }
  if (["archived", "draft", "pending", "queued", "running", "validating"].includes(status ?? "")) {
    return "warning";
  }
  return "neutral";
}

export function formatBoolean(value: boolean | null | undefined): string {
  if (value === true) {
    return "是";
  }
  if (value === false) {
    return "否";
  }
  return "-";
}

export function toneClass(tone: DisplayTone): string {
  return `tone tone--${tone}`;
}

export function formatLatency(value: number): string {
  return `${value} ms`;
}

export function formatTokenUsage(value: Record<string, unknown> | null): string {
  if (!value) {
    return "-";
  }
  const entries = Object.entries(value).slice(0, 4);
  return entries.map(([key, entryValue]) => `${key}: ${String(entryValue)}`).join(" / ");
}
