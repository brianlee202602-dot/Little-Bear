import { computed, type ComputedRef, type Ref } from "vue";

import type { ImportJobListItemData, ImportJobStage } from "@/api/imports";
import { importJobStageLabel } from "@/features/knowledge/knowledgeDisplay";

export function useKnowledgeFailedIndexJobs(options: {
  canIndexDocuments: ComputedRef<boolean>;
  failedIndexJobs: Ref<ImportJobListItemData[]>;
  importAdminBusy: { retryingIndexJobs: boolean };
  indexRetryForm: { confirmedRetry: boolean };
  selectedFailedIndexJobIds: Ref<string[]>;
}) {
  const selectedFailedIndexJobSet = computed(() => new Set(options.selectedFailedIndexJobIds.value));
  const failedIndexJobStageSummary = computed(() => {
    const counts = new Map<string, number>();
    for (const job of options.failedIndexJobs.value) {
      counts.set(job.stage, (counts.get(job.stage) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .sort(([leftStage], [rightStage]) => leftStage.localeCompare(rightStage))
      .map(([stage, count]) => `${importJobStageLabel(stage as ImportJobStage)} ${count}`);
  });
  const failedIndexJobDocumentCount = computed(() =>
    options.failedIndexJobs.value.reduce((total, job) => total + job.document_count, 0),
  );
  const canRetrySelectedFailedIndexJobs = computed(
    () =>
      options.canIndexDocuments.value &&
      options.selectedFailedIndexJobIds.value.length > 0 &&
      options.indexRetryForm.confirmedRetry &&
      !options.importAdminBusy.retryingIndexJobs,
  );

  return {
    canRetrySelectedFailedIndexJobs,
    failedIndexJobDocumentCount,
    failedIndexJobStageSummary,
    selectedFailedIndexJobSet,
  };
}
