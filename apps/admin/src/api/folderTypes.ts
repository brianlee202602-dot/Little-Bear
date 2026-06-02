import type { PaginationData } from "./commonTypes";

export interface AdminFolderData {
  id: string;
  kb_id: string;
  parent_id: string | null;
  name: string;
  status: "active" | "disabled" | "archived";
}

export interface AdminFolderOptionData {
  id: string;
  name: string;
  status: "active" | "disabled" | "archived";
}

export interface AdminFolderCreateRequest {
  name: string;
  parent_id?: string | null;
}

export interface AdminFolderPatchRequest {
  name?: string;
  parent_id?: string | null;
  status?: "active" | "disabled" | "archived";
}

export interface AdminFolderListResponse {
  request_id: string;
  data: AdminFolderData[];
  pagination: PaginationData;
}

export interface AdminFolderOptionListResponse {
  request_id: string;
  data: AdminFolderOptionData[];
  pagination: PaginationData;
}

export interface AdminFolderResponse {
  request_id: string;
  data: AdminFolderData;
}
