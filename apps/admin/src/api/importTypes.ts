import type { PaginationData } from "./commonTypes";

export type ImportJobStatus =
  | "queued"
  | "running"
  | "retrying"
  | "partial_success"
  | "success"
  | "failed"
  | "cancelled";

export type ImportJobStage =
  | "validate"
  | "parse"
  | "clean"
  | "chunk"
  | "embed"
  | "index"
  | "publish"
  | "cleanup"
  | "finished";

export interface ImportJobData {
  id: string;
  kb_id: string | null;
  job_type: string | null;
  status: ImportJobStatus;
  stage: ImportJobStage;
  document_ids: string[];
  error_summary: string | null;
}

export interface ImportJobListItemData {
  id: string;
  kb_id: string | null;
  job_type: string | null;
  status: ImportJobStatus;
  stage: ImportJobStage;
  document_count: number;
  error_summary: string | null;
}

export interface ImportJobResponse {
  request_id: string;
  data: ImportJobData;
}

export interface ImportJobListResponse {
  request_id: string;
  data: ImportJobListItemData[];
  pagination: PaginationData;
}
