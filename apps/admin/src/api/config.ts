import { requestJson, requestVoid } from "./http";
import type {
  ConfigItemListResponse,
  ConfigItemResponse,
  ConfigVersionListResponse,
  ConfigVersionResponse,
} from "./configTypes";
import type { SetupValidationResponse } from "./setupTypes";

export type {
  ConfigItemData,
  ConfigItemListItemData,
  ConfigItemListResponse,
  ConfigItemResponse,
  ConfigRiskLevel,
  ConfigStatus,
  ConfigVersionData,
  ConfigVersionListItemData,
  ConfigVersionListResponse,
  ConfigVersionResponse,
} from "./configTypes";
export type { SetupIssue, SetupValidationData, SetupValidationResponse } from "./setupTypes";

export async function listConfigs(
  accessToken: string,
  filters: { page?: number; page_size?: number } = {},
): Promise<ConfigItemListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 20),
  });
  return requestJson<ConfigItemListResponse>(
    `/internal/v1/admin/configs?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function getConfigItem(
  key: string,
  accessToken: string,
): Promise<ConfigItemResponse> {
  return requestJson<ConfigItemResponse>(
    `/internal/v1/admin/configs/${encodeURIComponent(key)}`,
    { method: "GET" },
    accessToken,
  );
}

export async function saveConfigDraft(
  key: string,
  valueJson: Record<string, unknown>,
  accessToken: string,
): Promise<ConfigItemResponse> {
  return requestJson<ConfigItemResponse>(
    `/internal/v1/admin/configs/${encodeURIComponent(key)}`,
    {
      method: "PUT",
      body: JSON.stringify({ value_json: valueJson }),
      headers: { "x-config-confirm": "save-draft" },
    },
    accessToken,
  );
}

export async function validateAdminConfig(
  config: Record<string, unknown>,
  accessToken: string,
): Promise<SetupValidationResponse> {
  return requestJson<SetupValidationResponse>(
    "/internal/v1/admin/config-validations",
    {
      method: "POST",
      body: JSON.stringify({ config }),
    },
    accessToken,
  );
}

export async function listConfigVersions(
  accessToken: string,
  filters: { page?: number; page_size?: number } = {},
): Promise<ConfigVersionListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 50),
  });
  return requestJson<ConfigVersionListResponse>(
    `/internal/v1/admin/config-versions?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function getConfigVersion(
  version: number,
  accessToken: string,
): Promise<ConfigVersionResponse> {
  return requestJson<ConfigVersionResponse>(
    `/internal/v1/admin/config-versions/${version}`,
    { method: "GET" },
    accessToken,
  );
}

export async function createConfigVersion(
  config: Record<string, unknown>,
  accessToken: string,
): Promise<ConfigVersionResponse> {
  return requestJson<ConfigVersionResponse>(
    "/internal/v1/admin/config-versions",
    {
      method: "POST",
      body: JSON.stringify({ config }),
      headers: { "x-config-confirm": "save-draft" },
    },
    accessToken,
  );
}

export async function updateConfigVersion(
  version: number,
  config: Record<string, unknown>,
  accessToken: string,
): Promise<ConfigVersionResponse> {
  return requestJson<ConfigVersionResponse>(
    `/internal/v1/admin/config-versions/${version}`,
    {
      method: "PUT",
      body: JSON.stringify({ config }),
      headers: { "x-config-confirm": "save-draft" },
    },
    accessToken,
  );
}

export async function publishConfigVersion(
  version: number,
  accessToken: string,
): Promise<ConfigVersionResponse> {
  return requestJson<ConfigVersionResponse>(
    `/internal/v1/admin/config-versions/${version}`,
    {
      method: "PATCH",
      body: JSON.stringify({ status: "active" }),
      headers: { "x-config-confirm": "publish" },
    },
    accessToken,
  );
}

export async function archiveConfigVersion(version: number, accessToken: string): Promise<void> {
  await requestVoid(
    `/internal/v1/admin/config-versions/${version}`,
    {
      method: "DELETE",
      headers: { "x-config-confirm": "archive" },
    },
    accessToken,
  );
}
