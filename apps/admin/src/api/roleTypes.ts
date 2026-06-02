import type { PaginationData } from "./commonTypes";

export interface AdminRoleData {
  id: string;
  code: string;
  name: string;
  scope_type: "enterprise" | "department" | "knowledge_base";
  is_builtin: boolean;
  status: "active" | "disabled" | "archived";
  scopes: string[];
}

export interface AdminRoleListItemData {
  id: string;
  code: string;
  name: string;
  scope_type: "enterprise" | "department" | "knowledge_base";
  is_builtin: boolean;
  status: "active" | "disabled" | "archived";
}

export interface AdminAssignableRoleOptionData {
  id: string;
  code: string;
  name: string;
  scope_type: "enterprise" | "department" | "knowledge_base";
  status: "active" | "disabled" | "archived";
  risk_level: "low" | "high";
}

export interface AdminRoleListResponse {
  request_id: string;
  data: AdminRoleListItemData[];
  pagination: PaginationData;
}

export interface AdminAssignableRoleOptionListResponse {
  request_id: string;
  data: AdminAssignableRoleOptionData[];
  pagination: PaginationData;
}

export interface AdminRoleBindingData {
  id: string;
  role_id: string;
  subject_type: "user" | "department";
  subject_id: string;
  scope_type: "enterprise" | "department" | "knowledge_base";
  scope_id: string | null;
  role_code: string | null;
  role_name: string | null;
}

export interface AdminRoleBindingListResponse {
  request_id: string;
  data: AdminRoleBindingData[];
  pagination: PaginationData;
}

export interface AdminRoleBindingInputData {
  role_id: string;
  scope_type: "enterprise" | "department" | "knowledge_base";
  scope_id?: string | null;
}
