import type {
  AdminDocumentData,
  AdminDocumentListItemData,
  ChunkData,
  DocumentVersionData,
  IndexVersionData,
} from "@/api/documents";
import type { AdminFolderData } from "@/api/folders";
import type { ImportJobData, ImportJobListItemData, ImportJobStage, ImportJobStatus } from "@/api/imports";
import type { AdminKnowledgeBaseData } from "@/api/knowledgeBases";

export type KnowledgeDisplayTone = "success" | "error" | "warning" | "neutral";

export function formatKnowledgeBaseLabel(
  knowledgeBase: { name?: string | null; id?: string | null } | null | undefined,
): string {
  if (!knowledgeBase) {
    return "-";
  }
  return knowledgeBase.name?.trim() || (knowledgeBase.id?.trim() ? "未命名知识库" : "-");
}

export function formatFolderLabel(
  folder: { name?: string | null; id?: string | null } | null | undefined,
): string {
  if (!folder) {
    return "根目录";
  }
  return folder.name?.trim() || (folder.id?.trim() ? "未命名文件夹" : "根目录");
}

export function folderStatusTone(status: AdminFolderData["status"]): KnowledgeDisplayTone {
  if (status === "active") {
    return "success";
  }
  if (status === "disabled") {
    return "warning";
  }
  return "neutral";
}

export function knowledgeBaseStatusTone(
  status: AdminKnowledgeBaseData["status"],
): KnowledgeDisplayTone {
  if (status === "active") {
    return "success";
  }
  if (status === "disabled") {
    return "warning";
  }
  return "neutral";
}

export function knowledgeBaseVisibilityLabel(
  visibility: AdminKnowledgeBaseData["kb_visibility"],
): string {
  if (visibility === "enterprise") {
    return "企业可见";
  }
  return visibility === "department_acl" ? "指定部门可见" : "私密可见";
}

export function documentVisibilityLabel(visibility: "department" | "enterprise"): string {
  return visibility === "enterprise" ? "企业可见" : "部门可见";
}

export function documentLifecycleStatusTone(
  status: AdminDocumentData["lifecycle_status"],
): KnowledgeDisplayTone {
  if (status === "active") {
    return "success";
  }
  if (status === "draft" || status === "archived") {
    return "warning";
  }
  return "error";
}

export function documentIndexStatusTone(
  status: AdminDocumentData["index_status"],
): KnowledgeDisplayTone {
  if (status === "indexed") {
    return "success";
  }
  if (status === "indexing") {
    return "warning";
  }
  if (status === "index_failed" || status === "blocked") {
    return "error";
  }
  return "neutral";
}

export function documentVersionStatusTone(status: string): KnowledgeDisplayTone {
  if (status === "active" || status === "published" || status === "ready") {
    return "success";
  }
  if (status === "draft" || status === "processing") {
    return "warning";
  }
  if (status === "failed" || status === "deleted") {
    return "error";
  }
  return "neutral";
}

export function indexVersionStatusTone(
  status: IndexVersionData["status"],
): KnowledgeDisplayTone {
  if (status === "active") {
    return "success";
  }
  if (status === "ready" || status === "draft" || status === "pending_delete") {
    return "warning";
  }
  if (status === "failed") {
    return "error";
  }
  return "neutral";
}

export function formatDocumentVersion(version: DocumentVersionData): string {
  return `v${version.version_no}`;
}

export function formatDocumentCurrentVersion(
  document: AdminDocumentData | AdminDocumentListItemData,
  options: {
    selectedDocumentId: string;
    formatDocumentVersionById: (versionId: string | null | undefined) => string;
  },
): string {
  if (typeof document.current_version_no === "number") {
    return `v${document.current_version_no}`;
  }
  if ("current_version_id" in document && document.current_version_id && document.id === options.selectedDocumentId) {
    return options.formatDocumentVersionById(document.current_version_id);
  }
  return "-";
}

export function formatIndexVersionLabel(
  index: number,
  pagination: { page: number; pageSize: number },
): string {
  return `索引版本 ${(pagination.page - 1) * pagination.pageSize + index + 1}`;
}

export function formatChunkOrdinal(
  chunk: ChunkData,
  index: number,
  pagination: { page: number; pageSize: number },
): string {
  return `片段 ${chunk.ordinal || (pagination.page - 1) * pagination.pageSize + index + 1}`;
}

export function formatChunkPageRange(chunk: Pick<ChunkData, "page_start" | "page_end">): string {
  if (chunk.page_start === null && chunk.page_end === null) {
    return "-";
  }
  if (chunk.page_start === chunk.page_end || chunk.page_end === null) {
    return String(chunk.page_start ?? "-");
  }
  return `${chunk.page_start ?? "-"}-${chunk.page_end}`;
}

export function formatDocumentCount(documentCount: number): string {
  return documentCount > 0 ? `${documentCount} 个文档` : "-";
}

export function formatImportJobTitle(job: ImportJobData | ImportJobListItemData): string {
  if (job.job_type === "upload") {
    return "文档导入任务";
  }
  if (job.job_type === "index_rebuild") {
    return "索引重建任务";
  }
  if (job.job_type === "permission_refresh") {
    return "权限刷新任务";
  }
  return "后台任务";
}

export function importJobListItemFromDetail(job: ImportJobData): ImportJobListItemData {
  return {
    id: job.id,
    kb_id: job.kb_id,
    job_type: job.job_type,
    status: job.status,
    stage: job.stage,
    document_count: job.document_ids.length,
    error_summary: job.error_summary,
  };
}

export function formatFileSize(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

export function importJobStatusTone(status: ImportJobStatus): KnowledgeDisplayTone {
  if (status === "success" || status === "partial_success") {
    return "success";
  }
  if (status === "failed" || status === "cancelled") {
    return "error";
  }
  if (status === "retrying") {
    return "warning";
  }
  return "neutral";
}

export function importJobStageLabel(stage: ImportJobStage): string {
  const labels: Record<ImportJobStage, string> = {
    validate: "校验",
    parse: "解析",
    clean: "清洗",
    chunk: "切片",
    embed: "向量化",
    index: "写索引",
    publish: "发布",
    cleanup: "清理",
    finished: "完成",
  };
  return labels[stage];
}
