import { computed, type ComputedRef, type Ref } from "vue";

import type { ApiErrorPayload } from "@/api/http";
import type { SetupInitializationData, SetupStateData, SetupValidationData } from "@/api/setup";
import {
  extractBootstrapChecks,
  extractDatabaseError,
  extractStructuredIssues,
} from "@/features/setup/setupErrors";
import type { SetupBusyState, SetupTone } from "@/features/setup/setupFlowTypes";
import { sections } from "@/features/setup/setupFields";
import type { SetupFormModel } from "@/features/setup/setupModel";
import { formatSetupStatus, setupStateTone } from "@/features/setup/setupStatus";
import {
  validateLocalForm,
  type LocalValidationIssue,
} from "@/features/setup/setupValidation";

type UseSetupDerivedStateOptions = {
  busy: SetupBusyState;
  form: SetupFormModel;
  initializationErrorPayload: Ref<ApiErrorPayload | null>;
  initializationResult: Ref<SetupInitializationData | null>;
  lastValidatedPayload: Ref<string | null>;
  payloadSignature: ComputedRef<string>;
  setupState: Ref<SetupStateData | null>;
  submitConfirmed: Ref<boolean>;
  validationErrorPayload: Ref<ApiErrorPayload | null>;
  validationResult: Ref<SetupValidationData | null>;
};

export function useSetupDerivedState(options: UseSetupDerivedStateOptions) {
  const {
    busy,
    form,
    initializationErrorPayload,
    lastValidatedPayload,
    payloadSignature,
    setupState,
    submitConfirmed,
    validationErrorPayload,
    validationResult,
  } = options;

  // 本地校验用于拦截明显输入错误；后端校验仍是最终准入标准。
  const localValidationIssues = computed(() => validateLocalForm(form, setupState.value));
  const localBlockingIssues = computed(() =>
    localValidationIssues.value.filter((issue) => issue.tone === "error"),
  );
  const localWarningIssues = computed(() =>
    localValidationIssues.value.filter((issue) => issue.tone === "warning"),
  );
  const localChecksPassed = computed(() => localBlockingIssues.value.length === 0);
  const backendValidationFresh = computed(
    () => validationResult.value?.valid === true && lastValidatedPayload.value === payloadSignature.value,
  );
  // 正常初始化完成后写接口应关闭；只有后端显式允许 recovery 时才重新开放。
  const setupWritable = computed(
    () => !(setupState.value?.initialized ?? false) || setupState.value?.recovery_setup_allowed === true,
  );
  const fieldIssueMap = computed(() => {
    const result = new Map<keyof SetupFormModel, LocalValidationIssue[]>();
    for (const issue of localValidationIssues.value) {
      if (!issue.field) {
        continue;
      }
      const issues = result.get(issue.field) ?? [];
      issues.push(issue);
      result.set(issue.field, issues);
    }
    return result;
  });
  const sectionCheckItems = computed<
    Array<{ title: string; errors: number; warnings: number; tone: SetupTone }>
  >(() =>
    sections.map((section) => {
      const issues = localValidationIssues.value.filter((issue) => issue.section === section.title);
      const errors = issues.filter((issue) => issue.tone === "error").length;
      const warnings = issues.filter((issue) => issue.tone === "warning").length;
      return {
        title: section.title,
        errors,
        warnings,
        tone: errors > 0 ? "error" : warnings > 0 ? "warning" : "success",
      };
    }),
  );
  const statusLabel = computed(() => {
    if (!setupState.value) {
      return "状态未知";
    }
    return formatSetupStatus(setupState.value.setup_status);
  });
  const statusTone = computed(() => setupStateTone(setupState.value));
  const recoveryMode = computed(() => setupState.value?.recovery_setup_allowed === true);
  const canValidate = computed(
    () => !busy.validating && !busy.submitting && localChecksPassed.value && setupWritable.value,
  );
  const canSubmit = computed(() => {
    return (
      !busy.submitting &&
      !busy.validating &&
      submitConfirmed.value &&
      setupWritable.value &&
      localChecksPassed.value &&
      backendValidationFresh.value
    );
  });
  const validationGateMessage = computed(() => {
    if (!setupWritable.value) {
      return "当前系统已初始化，初始化写接口应保持关闭。";
    }
    if (!localChecksPassed.value) {
      return `还有 ${localBlockingIssues.value.length} 个本地阻断项需要处理。`;
    }
    if (backendValidationFresh.value) {
      return "后端配置校验已通过，且请求体未变化。";
    }
    if (validationResult.value?.valid === true) {
      return "请求体已变化，需要重新执行配置校验。";
    }
    return "本地核查通过后，先执行后端配置校验。";
  });
  const flowItems = computed<Array<{ label: string; value: string; tone: SetupTone }>>(() => [
    {
      label: "初始化令牌",
      value: form.setupToken.trim() ? "已填写" : "缺失",
      tone: form.setupToken.trim() ? "success" : "error",
    },
    {
      label: "本地核查",
      value: localChecksPassed.value ? "通过" : `${localBlockingIssues.value.length} 个阻断项`,
      tone: localChecksPassed.value ? "success" : "error",
    },
    {
      label: "后端校验",
      value: backendValidationFresh.value ? "通过" : "待校验",
      tone: backendValidationFresh.value ? "success" : "neutral",
    },
    {
      label: "初始化提交",
      value: canSubmit.value ? "可提交" : "受控",
      tone: canSubmit.value ? "success" : "neutral",
    },
  ]);
  const submitConfirmationText = computed(() =>
    recoveryMode.value ? "确认恢复当前生效配置" : "确认写入首个管理员、默认组织和当前生效配置",
  );
  const submitButtonText = computed(() => {
    if (busy.submitting) {
      return "提交中...";
    }
    return recoveryMode.value ? "执行恢复初始化" : "执行初始化";
  });
  const summaryItems = computed(() => [
    { label: "企业编码", value: form.enterpriseCode },
    { label: "默认部门", value: form.departmentCode },
    { label: "配置版本", value: "1" },
    { label: "向量维度", value: String(form.embeddingDimension) },
    { label: "向量模型服务", value: form.embeddingProviderBaseUrl },
    { label: "重排模型服务", value: form.rerankProviderBaseUrl },
    { label: "大模型服务", value: form.llmProviderBaseUrl },
    { label: "切片策略", value: form.chunkStrategyMode },
    { label: "切片大小", value: `${form.chunkDefaultSizeTokens} tokens` },
    { label: "向量库", value: form.qdrantBaseUrl },
  ]);
  const normalFieldsBySection = computed(() =>
    new Map(
      sections.map((section) => [
        section.title,
        section.fields.filter((field) => !field.group),
      ]),
    ),
  );
  const checkboxFieldsBySection = computed(() =>
    new Map(
      sections.map((section) => [
        section.title,
        section.fields.filter((field) => field.group === "chunk-preserve" || field.group === "cache-switch"),
      ]),
    ),
  );
  const validationErrorItems = computed(() => extractStructuredIssues(validationErrorPayload.value));
  const initializationErrorItems = computed(() =>
    extractStructuredIssues(initializationErrorPayload.value),
  );
  const initializationFailedChecks = computed(() =>
    extractBootstrapChecks(initializationErrorPayload.value).filter((item) => item.status !== "passed"),
  );
  const initializationDatabaseError = computed(() =>
    extractDatabaseError(initializationErrorPayload.value),
  );

  function fieldIssues(key: keyof SetupFormModel): LocalValidationIssue[] {
    return fieldIssueMap.value.get(key) ?? [];
  }

  return {
    backendValidationFresh,
    canSubmit,
    canValidate,
    checkboxFieldsBySection,
    fieldIssues,
    flowItems,
    initializationDatabaseError,
    initializationErrorItems,
    initializationFailedChecks,
    localBlockingIssues,
    localChecksPassed,
    localValidationIssues,
    localWarningIssues,
    normalFieldsBySection,
    recoveryMode,
    sectionCheckItems,
    setupWritable,
    statusLabel,
    statusTone,
    submitButtonText,
    submitConfirmationText,
    summaryItems,
    validationErrorItems,
    validationGateMessage,
  };
}
