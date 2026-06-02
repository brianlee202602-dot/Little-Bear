import { requestJson } from "./http";
import type { ImportJobListResponse, ImportJobResponse } from "./importTypes";

export type {
  ImportJobData,
  ImportJobListItemData,
  ImportJobListResponse,
  ImportJobResponse,
  ImportJobStage,
  ImportJobStatus,
} from "./importTypes";

export async function uploadKnowledgeBaseDocuments(
  kbId: string,
  payload: {
    files: File[];
    visibility?: "department" | "enterprise";
    owner_department_id?: string;
    folder_id?: string;
    idempotency_key?: string;
  },
  accessToken: string,
): Promise<ImportJobResponse> {
  const form = new FormData();
  for (const file of payload.files) {
    form.append("files", file);
  }
  if (payload.visibility) {
    form.append("visibility", payload.visibility);
  }
  if (payload.owner_department_id) {
    form.append("owner_department_id", payload.owner_department_id);
  }
  if (payload.folder_id) {
    form.append("folder_id", payload.folder_id);
  }
  if (payload.idempotency_key) {
    form.append("idempotency_key", payload.idempotency_key);
  }
  return requestJson<ImportJobResponse>(
    `/internal/v1/knowledge-bases/${encodeURIComponent(kbId)}/documents`,
    {
      method: "POST",
      body: form,
    },
    accessToken,
  );
}

export async function listAdminImportJobs(
  accessToken: string,
  filters: {
    page?: number;
    page_size?: number;
    status?: string;
    stage?: string;
    kb_id?: string;
    job_type?: string;
  } = {},
): Promise<ImportJobListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 20),
  });
  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.stage) {
    params.set("stage", filters.stage);
  }
  if (filters.kb_id) {
    params.set("kb_id", filters.kb_id);
  }
  if (filters.job_type) {
    params.set("job_type", filters.job_type);
  }
  return requestJson<ImportJobListResponse>(
    `/internal/v1/admin/import-jobs?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}
