import { requestJson } from "./http";
import type { AcceptedResponse } from "./commonTypes";
import type { ImportJobListResponse } from "./importTypes";
import type {
  IndexCollectionOperationResponse,
  IndexCollectionSnapshotListResponse,
  IndexCollectionSnapshotRecoverRequest,
  IndexCollectionSnapshotResponse,
  IndexHealthResponse,
  IndexJobCreateRequest,
  IndexJobRetryRequest,
  IndexVersionCleanupJobCreateRequest,
} from "./indexTypes";

export type { AcceptedResponse } from "./commonTypes";
export type { ImportJobListResponse } from "./importTypes";
export type {
  IndexCollectionHealthData,
  IndexCollectionOperationData,
  IndexCollectionOperationResponse,
  IndexCollectionSnapshotData,
  IndexCollectionSnapshotListResponse,
  IndexCollectionSnapshotRecoverRequest,
  IndexCollectionSnapshotResponse,
  IndexHealthResponse,
  IndexJobCreateRequest,
  IndexJobRetryRequest,
  IndexVersionCleanupJobCreateRequest,
} from "./indexTypes";

export async function createAdminIndexJob(
  payload: IndexJobCreateRequest,
  accessToken: string,
  confirmed: boolean,
): Promise<AcceptedResponse> {
  return requestJson<AcceptedResponse>(
    "/internal/v1/admin/index-jobs",
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: confirmed ? { "x-index-confirm": "rebuild" } : undefined,
    },
    accessToken,
  );
}

export async function createAdminIndexVersionCleanupJob(
  payload: IndexVersionCleanupJobCreateRequest,
  accessToken: string,
  confirmed: boolean,
): Promise<AcceptedResponse> {
  return requestJson<AcceptedResponse>(
    "/internal/v1/admin/index-versions/cleanup-jobs",
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: confirmed ? { "x-index-confirm": "cleanup" } : undefined,
    },
    accessToken,
  );
}

export async function getAdminIndexHealth(
  accessToken: string,
  filters: { page?: number; page_size?: number } = {},
): Promise<IndexHealthResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 20),
  });
  return requestJson<IndexHealthResponse>(
    `/internal/v1/admin/index-health?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function listAdminIndexCollectionSnapshots(
  collectionName: string,
  accessToken: string,
  filters: { page?: number; page_size?: number } = {},
): Promise<IndexCollectionSnapshotListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 20),
  });
  return requestJson<IndexCollectionSnapshotListResponse>(
    `/internal/v1/admin/index-collections/${encodeURIComponent(collectionName)}/snapshots?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function createAdminIndexCollectionSnapshot(
  collectionName: string,
  accessToken: string,
  confirmed: boolean,
): Promise<IndexCollectionSnapshotResponse> {
  return requestJson<IndexCollectionSnapshotResponse>(
    `/internal/v1/admin/index-collections/${encodeURIComponent(collectionName)}/snapshots`,
    {
      method: "POST",
      headers: confirmed ? { "x-index-confirm": "snapshot" } : undefined,
    },
    accessToken,
  );
}

export async function recoverAdminIndexCollectionSnapshot(
  collectionName: string,
  payload: IndexCollectionSnapshotRecoverRequest,
  accessToken: string,
  confirmed: boolean,
): Promise<IndexCollectionOperationResponse> {
  return requestJson<IndexCollectionOperationResponse>(
    `/internal/v1/admin/index-collections/${encodeURIComponent(collectionName)}/snapshot-recoveries`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
      headers: confirmed ? { "x-index-confirm": "restore" } : undefined,
    },
    accessToken,
  );
}

export async function createAdminIndexCollectionRebuildJob(
  collectionName: string,
  accessToken: string,
  confirmed: boolean,
): Promise<AcceptedResponse> {
  return requestJson<AcceptedResponse>(
    `/internal/v1/admin/index-collections/${encodeURIComponent(collectionName)}/rebuild-jobs`,
    {
      method: "POST",
      headers: confirmed ? { "x-index-confirm": "rebuild" } : undefined,
    },
    accessToken,
  );
}

export async function retryAdminIndexJobs(
  payload: IndexJobRetryRequest,
  accessToken: string,
  confirmed: boolean,
): Promise<ImportJobListResponse> {
  return requestJson<ImportJobListResponse>(
    "/internal/v1/admin/index-jobs/retries",
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: confirmed ? { "x-index-confirm": "retry" } : undefined,
    },
    accessToken,
  );
}
