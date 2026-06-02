import type { SetupFormModel } from "@/features/setup/setupModel";

export function cloneJsonRecord(value: Record<string, unknown>): Record<string, unknown> {
  return JSON.parse(JSON.stringify(value)) as Record<string, unknown>;
}

export function asNumber(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function asRecord(value: unknown): Record<string, unknown> | null {
  return isRecord(value) ? value : null;
}

export function isBlankFieldValue(value: unknown): boolean {
  return value === null || value === undefined || (typeof value === "string" && value.trim() === "");
}

export function asString(value: unknown, fallback: string): string {
  return typeof value === "string" ? value : fallback;
}

export function asBoolean(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

export function asVectorDistance(
  value: unknown,
  fallback: SetupFormModel["vectorDistance"],
): SetupFormModel["vectorDistance"] {
  return value === "cosine" || value === "dot" || value === "euclidean" ? value : fallback;
}

export function asModelGatewayMode(
  value: unknown,
  fallback: SetupFormModel["modelGatewayMode"],
): SetupFormModel["modelGatewayMode"] {
  return value === "external" ? value : fallback;
}

export function asChunkStrategyMode(
  value: unknown,
  fallback: SetupFormModel["chunkStrategyMode"],
): SetupFormModel["chunkStrategyMode"] {
  return value === "heading_paragraph" || value === "fixed_tokens" ? value : fallback;
}

export function asAuditQueryTextMode(
  value: unknown,
  fallback: SetupFormModel["auditQueryTextMode"],
): SetupFormModel["auditQueryTextMode"] {
  return value === "none" || value === "hash" || value === "plain" ? value : fallback;
}

export function asPermissionVisibility(
  value: unknown,
  fallback: SetupFormModel["permissionDefaultVisibility"],
): SetupFormModel["permissionDefaultVisibility"] {
  return value === "department" || value === "enterprise" ? value : fallback;
}
