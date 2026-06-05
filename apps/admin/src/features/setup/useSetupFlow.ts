import { computed, reactive, ref } from "vue";

import type { ApiErrorPayload } from "@/api/http";
import type {
  SetupInitializationData,
  SetupStateData,
  SetupValidationData,
} from "@/api/setup";
import { createDefaultSetupForm } from "@/features/setup/setupDefaultValues";
import type { SetupBusyState, SetupFeedback } from "@/features/setup/setupFlowTypes";
import { sections } from "@/features/setup/setupFields";
import type { SetupFormModel } from "@/features/setup/setupModel";
import { buildSetupPayload } from "@/features/setup/setupPayloadBuilder";
import { useSetupActions } from "@/features/setup/useSetupActions";
import { useSetupDerivedState } from "@/features/setup/useSetupDerivedState";
import { useSetupFieldUpdates } from "@/features/setup/useSetupFieldUpdates";

type UseSetupFlowOptions = {
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
};

export function useSetupFlow(options: UseSetupFlowOptions) {
  const form = reactive<SetupFormModel>(createDefaultSetupForm());
  const busy = reactive<SetupBusyState>({
    refreshing: false,
    validating: false,
    submitting: false,
  });
  const setupState = ref<SetupStateData | null>(null);
  const validationResult = ref<SetupValidationData | null>(null);
  const initializationResult = ref<SetupInitializationData | null>(null);
  const feedback = ref<SetupFeedback | null>(null);
  const validationErrorPayload = ref<ApiErrorPayload | null>(null);
  const initializationErrorPayload = ref<ApiErrorPayload | null>(null);
  const initializationErrorDialogOpen = ref(false);
  const submitConfirmed = ref(false);
  const lastValidatedPayload = ref<string | null>(null);
  let refreshSetupState: () => Promise<void> = async () => {};

  // payload 是真正提交给 setup-config-validations / setup-initialization 的请求体。
  const payload = computed(() => buildSetupPayload(form));
  const payloadSignature = computed(() => JSON.stringify(payload.value));

  const derivedState = useSetupDerivedState({
    busy,
    form,
    initializationErrorPayload,
    initializationResult,
    lastValidatedPayload,
    payloadSignature,
    setupState,
    submitConfirmed,
    validationErrorPayload,
    validationResult,
  });
  const {
    canSubmit,
    canValidate,
    checkboxFieldsBySection,
    fieldIssues,
    flowItems,
    initializationDatabaseError,
    initializationErrorSummary,
    initializationErrorItems,
    initializationFailedChecks,
    localBlockingIssues,
    localChecksPassed,
    localValidationIssues,
    localWarningIssues,
    normalFieldsBySection,
    sectionCheckItems,
    statusLabel,
    statusTone,
    submitButtonText,
    submitConfirmationText,
    summaryItems,
    validationErrorItems,
    validationGateMessage,
  } = derivedState;
  const actions = useSetupActions({
    busy,
    canSubmit,
    canValidate,
    feedback,
    form,
    initializationErrorDialogOpen,
    initializationErrorPayload,
    initializationResult,
    lastValidatedPayload,
    normalizeErrorMessage: options.normalizeErrorMessage,
    payload,
    payloadSignature,
    refreshSetupState: () => refreshSetupState(),
    submitConfirmed,
    validationErrorPayload,
    validationGateMessage,
    validationResult,
  });
  const fieldUpdates = useSetupFieldUpdates(form, submitConfirmed);

  function setRefreshStateHandler(handler: () => Promise<void>): void {
    refreshSetupState = handler;
  }

  const page = reactive({
    busy,
    canSubmit,
    canValidate,
    checkboxFieldsBySection,
    closeInitializationErrorDialog,
    feedback,
    fieldIssues,
    flowItems,
    form,
    initializationDatabaseError,
    initializationErrorDialogOpen,
    initializationErrorSummary,
    initializationErrorItems,
    initializationErrorPayload,
    initializationFailedChecks,
    initializationResult,
    localBlockingIssues,
    localChecksPassed,
    localValidationIssues,
    localWarningIssues,
    normalFieldsBySection,
    refreshState: actions.refreshState,
    resetForm: actions.resetForm,
    runInitialization: actions.runInitialization,
    runValidation: actions.runValidation,
    sectionCheckItems,
    sections,
    setupState,
    statusLabel,
    statusTone,
    submitButtonText,
    submitConfirmationText,
    submitConfirmed,
    summaryItems,
    updateFieldFromCheckbox: fieldUpdates.updateFieldFromCheckbox,
    updateFieldFromInput: fieldUpdates.updateFieldFromInput,
    updateFieldFromSelect: fieldUpdates.updateFieldFromSelect,
    updateSubmitConfirmed: fieldUpdates.updateSubmitConfirmed,
    validationErrorItems,
    validationErrorPayload,
    validationGateMessage,
    validationResult,
  });

  function closeInitializationErrorDialog(): void {
    initializationErrorDialogOpen.value = false;
  }

  return {
    busy,
    feedback,
    form,
    page,
    setRefreshStateHandler,
    setupState,
  };
}

export type SetupPageFlow = ReturnType<typeof useSetupFlow>["page"];
