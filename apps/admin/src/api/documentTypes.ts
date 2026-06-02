import type { PaginationData } from "./commonTypes";

export interface AdminDocumentData {
  id: string;
  kb_id: string;
  folder_id: string | null;
  title: string;
  lifecycle_status: "draft" | "active" | "archived" | "deleted";
  index_status: "none" | "indexing" | "indexed" | "index_failed" | "blocked";
  owner_department_id: string;
  visibility: "department" | "enterprise";
  current_version_id: string | null;
  current_version_no: number | null;
}

export interface AdminDocumentListItemData {
  id: string;
  title: string;
  folder_name: string | null;
  lifecycle_status: "draft" | "active" | "archived" | "deleted";
  index_status: "none" | "indexing" | "indexed" | "index_failed" | "blocked";
  visibility: "department" | "enterprise";
  owner_department_name: string | null;
  current_version_no: number | null;
  can_rebuild_index: boolean;
}

export interface AdminDocumentListResponse {
  request_id: string;
  data: AdminDocumentListItemData[];
  pagination: PaginationData;
}

export interface AdminDocumentResponse {
  request_id: string;
  data: AdminDocumentData;
}

export interface DocumentVersionData {
  id: string;
  document_id: string;
  version_no: number;
  status: string;
}

export interface DocumentVersionListResponse {
  request_id: string;
  data: DocumentVersionData[];
  pagination: PaginationData;
}

export interface IndexVersionData {
  id: string;
  document_id: string;
  document_version_id: string;
  embedding_model: string;
  model_version: string;
  dimension: number;
  collection_name: string;
  status: "draft" | "ready" | "active" | "archived" | "pending_delete" | "failed";
  chunk_count: number;
  created_at: string | null;
  activated_at: string | null;
}

export interface IndexVersionListResponse {
  request_id: string;
  data: IndexVersionData[];
  pagination: PaginationData;
}

export interface ChunkData {
  id: string;
  document_id: string;
  document_version_id: string;
  text_preview: string;
  page_start: number | null;
  page_end: number | null;
  status: string;
  ordinal: number;
}

export interface ChunkListResponse {
  request_id: string;
  data: ChunkData[];
  pagination: PaginationData;
}

export interface AdminDocumentPreviewChunkData {
  id: string;
  document_id: string;
  document_version_id: string;
  text: string;
  text_preview: string;
  page_start: number | null;
  page_end: number | null;
  status: string;
  ordinal: number;
  heading_path: string | null;
  source_offsets: Record<string, unknown> | null;
  text_status: "object" | "preview_only" | "object_unavailable";
}

export interface AdminDocumentPreviewData {
  doc_id: string;
  title: string;
  chunks: AdminDocumentPreviewChunkData[];
}

export interface AdminDocumentPreviewResponse {
  request_id: string;
  data: AdminDocumentPreviewData;
  pagination: PaginationData;
}

export interface ResourcePermissionPutRequest {
  visibility: "department" | "enterprise";
  owner_department_id?: string | null;
}

export interface PermissionPolicyResponse {
  request_id: string;
  data: {
    resource_type: "document";
    resource_id: string;
    visibility: "department" | "enterprise";
    permission_version: number;
  };
}
