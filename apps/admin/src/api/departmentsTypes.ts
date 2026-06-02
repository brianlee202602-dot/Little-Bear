import type { PaginationData } from "./commonTypes";

export interface AdminDepartmentData {
  id: string;
  code: string;
  name: string;
  status: string;
  is_primary: boolean;
  is_default: boolean;
}

export interface AdminDepartmentListItemData {
  id: string;
  name: string;
  status: string;
  is_primary?: boolean;
  is_default: boolean;
}

export interface AdminDepartmentOptionData {
  id: string;
  name: string;
  status: string;
  is_primary?: boolean;
  is_default: boolean;
}

export interface AdminDepartmentCreateRequest {
  code: string;
  name: string;
}

export interface AdminDepartmentPatchRequest {
  name?: string;
  status?: "active" | "disabled";
}

export interface AdminDepartmentListResponse {
  request_id: string;
  data: AdminDepartmentListItemData[];
  pagination: PaginationData;
}

export interface AdminDepartmentOptionListResponse {
  request_id: string;
  data: AdminDepartmentOptionData[];
  pagination: PaginationData;
}

export interface AdminDepartmentResponse {
  request_id: string;
  data: AdminDepartmentData;
}
