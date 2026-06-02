import type { PaginationData } from "./commonTypes";

export interface IndexCollectionHealthData {
  collection_name: string;
  expected_dimension: number | null;
  qdrant_reachable: boolean;
  qdrant_exists: boolean | null;
  qdrant_status: string | null;
  qdrant_vector_size: number | null;
  qdrant_points_count: number | null;
  db_index_version_count: number;
  active_index_version_count: number;
  pending_delete_index_version_count: number;
  failed_index_version_count: number;
  active_ref_count: number;
  draft_ref_count: number;
  deleted_ref_count: number;
  pending_delete_ref_count: number;
  active_ref_mismatch_count: number;
  issues: string[];
}

export interface IndexHealthResponse {
  request_id: string;
  data: IndexCollectionHealthData[];
  pagination: PaginationData;
}

export interface IndexCollectionSnapshotData {
  collection_name: string;
  name: string;
  size: number | null;
  creation_time: string | null;
  checksum: string | null;
}

export interface IndexCollectionSnapshotResponse {
  request_id: string;
  data: IndexCollectionSnapshotData;
}

export interface IndexCollectionSnapshotListResponse {
  request_id: string;
  data: IndexCollectionSnapshotData[];
  pagination: PaginationData;
}

export interface IndexCollectionSnapshotRecoverRequest {
  location: string;
  priority?: "Snapshot" | "Replica" | null;
  checksum?: string | null;
}

export interface IndexCollectionOperationData {
  collection_name: string;
  operation: "snapshot_recover";
  accepted: boolean;
  result: boolean | null;
}

export interface IndexCollectionOperationResponse {
  request_id: string;
  data: IndexCollectionOperationData;
}

export interface IndexJobCreateRequest {
  kb_id?: string | null;
  document_ids?: string[];
}

export interface IndexVersionCleanupJobCreateRequest {
  index_version_ids: string[];
}

export interface IndexJobRetryRequest {
  job_ids: string[];
}
