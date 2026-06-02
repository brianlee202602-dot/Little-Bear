import type { PaginationData } from "./commonTypes";

export type ConfigStatus = "draft" | "validating" | "active" | "inactive" | "archived" | "failed";
export type ConfigRiskLevel = "low" | "medium" | "high" | "critical";

export interface ConfigItemData {
  key: string;
  value_json: Record<string, unknown>;
  scope_type: string;
  status: ConfigStatus;
  version: number;
}

export interface ConfigItemListItemData {
  key: string;
  scope_type: string;
  status: ConfigStatus;
  version: number;
}

export interface ConfigItemResponse {
  request_id: string;
  data: ConfigItemData;
}

export interface ConfigItemListResponse {
  request_id: string;
  data: ConfigItemListItemData[];
  pagination: PaginationData;
}

export interface ConfigVersionData {
  version: number;
  status: ConfigStatus;
  risk_level: ConfigRiskLevel;
  created_by: string | null;
  config: Record<string, unknown> | null;
  created_at: string | null;
  updated_at: string | null;
  activated_at: string | null;
}

export interface ConfigVersionListItemData {
  version: number;
  status: ConfigStatus;
  risk_level: ConfigRiskLevel;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
  activated_at: string | null;
}

export interface ConfigVersionResponse {
  request_id: string;
  data: ConfigVersionData;
}

export interface ConfigVersionListResponse {
  request_id: string;
  data: ConfigVersionListItemData[];
  pagination: PaginationData;
}
