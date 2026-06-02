import type { ConfigVersionData, ConfigVersionListItemData } from "@/api/config";
import type { DisplayTone } from "@/utils/display";

export function riskLevelText(riskLevel: string | null | undefined): string {
  if (!riskLevel) {
    return "-";
  }
  const labels: Record<string, string> = {
    low: "低",
    medium: "中",
    high: "高",
    critical: "严重",
  };
  return labels[riskLevel] ?? riskLevel;
}

export function configVersionPreview(version: ConfigVersionData | ConfigVersionListItemData): string {
  const config = "config" in version ? version.config : null;
  if (!config) {
    return "配置详情按需加载";
  }
  const keys = Object.keys(config).filter(
    (key) => !["schema_version", "config_version", "scope"].includes(key),
  );
  const head = keys.slice(0, 6).join(" / ");
  return keys.length > 6 ? `${head} / 等 ${keys.length} 项` : head || "无配置项";
}

export function isEditableConfigVersion(
  version: ConfigVersionData | ConfigVersionListItemData,
): boolean {
  return version.status !== "archived";
}

export function isActivatableConfigVersion(
  version: ConfigVersionData | ConfigVersionListItemData,
): boolean {
  return version.status !== "active" && version.status !== "archived";
}

export function isArchivableConfigVersion(
  version: ConfigVersionData | ConfigVersionListItemData,
): boolean {
  return version.status !== "active" && version.status !== "archived";
}

export function configStatusTone(status: string): DisplayTone {
  if (status === "active") {
    return "success";
  }
  if (status === "failed") {
    return "error";
  }
  if (status === "draft" || status === "validating") {
    return "warning";
  }
  return "neutral";
}
