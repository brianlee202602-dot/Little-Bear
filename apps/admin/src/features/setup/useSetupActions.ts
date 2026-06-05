import type { ComputedRef, Ref } from "vue";

import { ApiRequestError, type ApiErrorPayload } from "@/api/http";
import {
  initializeSetup,
  validateSetupConfig,
  type SetupInitializationData,
  type SetupValidationData,
} from "@/api/setup";
import { createDefaultSetupForm } from "@/features/setup/setupDefaultValues";
import { buildInitializationFailureMessage } from "@/features/setup/setupErrors";
import type { SetupFormModel, SetupRequestPayload } from "@/features/setup/setupModel";
import type { SetupBusyState, SetupFeedback } from "@/features/setup/setupFlowTypes";

type UseSetupActionsOptions = {
  busy: SetupBusyState;
  canSubmit: ComputedRef<boolean>;
  canValidate: ComputedRef<boolean>;
  feedback: Ref<SetupFeedback | null>;
  form: SetupFormModel;
  initializationErrorDialogOpen: Ref<boolean>;
  initializationErrorPayload: Ref<ApiErrorPayload | null>;
  initializationResult: Ref<SetupInitializationData | null>;
  lastValidatedPayload: Ref<string | null>;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  payload: ComputedRef<SetupRequestPayload>;
  payloadSignature: ComputedRef<string>;
  refreshSetupState: () => Promise<void>;
  submitConfirmed: Ref<boolean>;
  validationErrorPayload: Ref<ApiErrorPayload | null>;
  validationGateMessage: ComputedRef<string>;
  validationResult: Ref<SetupValidationData | null>;
};

export function useSetupActions(options: UseSetupActionsOptions) {
  const {
    busy,
    canSubmit,
    canValidate,
    feedback,
    form,
    initializationErrorDialogOpen,
    initializationErrorPayload,
    initializationResult,
    lastValidatedPayload,
    normalizeErrorMessage,
    payload,
    payloadSignature,
    refreshSetupState,
    submitConfirmed,
    validationErrorPayload,
    validationGateMessage,
    validationResult,
  } = options;

  async function refreshState(): Promise<void> {
    await refreshSetupState();
  }

  async function runValidation(): Promise<void> {
    if (!canValidate.value) {
      feedback.value = {
        tone: "error",
        message: validationGateMessage.value,
      };
      return;
    }
    busy.validating = true;
    try {
      const response = await validateSetupConfig(payload.value, form.setupToken || undefined);
      validationResult.value = response.data;
      validationErrorPayload.value = null;
      // 只记录“已通过”的请求签名，防止表单变更后误放行初始化提交。
      lastValidatedPayload.value = response.data.valid ? payloadSignature.value : null;
      feedback.value = {
        tone: response.data.valid ? "success" : "error",
        message: response.data.valid ? "配置校验通过" : "配置校验未通过",
      };
      await refreshSetupState();
    } catch (error) {
      validationResult.value = null;
      lastValidatedPayload.value = null;
      validationErrorPayload.value = error instanceof ApiRequestError ? error.payload : null;
      feedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "配置校验失败"),
      };
    } finally {
      busy.validating = false;
    }
  }

  async function runInitialization(): Promise<void> {
    if (!canSubmit.value) {
      feedback.value = {
        tone: "error",
        message: validationGateMessage.value,
      };
      return;
    }
    busy.submitting = true;
    initializationErrorDialogOpen.value = false;
    try {
      // initializeSetup 会自动带 x-setup-confirm；后端仍会二次校验确认头和请求体。
      const response = await initializeSetup(payload.value, form.setupToken || undefined);
      initializationResult.value = response.data;
      initializationErrorPayload.value = null;
      initializationErrorDialogOpen.value = false;
      feedback.value = {
        tone: "success",
        message: "初始化提交成功",
      };
      submitConfirmed.value = false;
      await refreshSetupState();
    } catch (error) {
      initializationResult.value = null;
      initializationErrorPayload.value = error instanceof ApiRequestError ? error.payload : null;
      initializationErrorDialogOpen.value = true;
      feedback.value = {
        tone: "error",
        message:
          error instanceof ApiRequestError
            ? buildInitializationFailureMessage(error.payload, "初始化提交失败")
            : normalizeErrorMessage(error, "初始化提交失败"),
      };
    } finally {
      busy.submitting = false;
    }
  }

  function resetForm(): void {
    // 恢复默认值时同步清空校验和提交结果，避免旧反馈误导当前表单。
    Object.assign(form, createDefaultSetupForm());
    validationResult.value = null;
    lastValidatedPayload.value = null;
    initializationResult.value = null;
    initializationErrorDialogOpen.value = false;
    validationErrorPayload.value = null;
    initializationErrorPayload.value = null;
    feedback.value = {
      tone: "neutral",
      message: "已恢复本地默认初始化配置",
    };
    submitConfirmed.value = false;
  }

  return {
    refreshState,
    resetForm,
    runInitialization,
    runValidation,
  };
}
