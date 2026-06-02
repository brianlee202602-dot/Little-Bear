import { computed, reactive, ref, type Ref } from "vue";

import type {
  ConfigVersionData,
  ConfigVersionListItemData,
  SetupValidationData,
} from "@/api/config";
import {
  asNumber,
  asRecord,
  cloneJsonRecord,
  isBlankFieldValue,
  isRecord,
} from "@/features/config/configValueCoercion";
import { hydrateConfigForm } from "@/features/config/configFormHydration";
import {
  configEditableFields,
  configSectionDefinitions,
} from "@/features/config/configFields";
import { mergeConfigSectionValue } from "@/features/config/configSectionMerge";
import { useConfigVersionActions } from "@/features/config/useConfigVersionActions";
import { createDefaultSetupForm } from "@/features/setup/setupDefaultValues";
import type { FieldDefinition } from "@/features/setup/setupFields";
import type { SetupFormModel } from "@/features/setup/setupModel";
import { buildSetupPayload } from "@/features/setup/setupPayloadBuilder";
import {
  clearPaginationState,
  syncPaginationState,
  type PaginationState,
} from "@/utils/pagination";

export type ConfigModalMode = "create" | "edit" | null;

type Feedback = {
  tone: "success" | "error" | "neutral";
  message: string;
};

type UseConfigManagementOptions = {
  canManageConfig: Ref<boolean>;
  canReadConfig: Ref<boolean>;
  confirmAction?: (message: string) => boolean;
  ensureAccessToken: () => Promise<string | null>;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  onConfigChanged?: () => Promise<void>;
  setupActiveConfigVersion: Ref<number | null | undefined>;
};

export function useConfigManagement(options: UseConfigManagementOptions) {
  const configBusy = reactive({
    loading: false,
    validating: false,
    saving: false,
    publishing: false,
    deleting: false,
  });
  const configForm = reactive<SetupFormModel>(createDefaultSetupForm());
  const configFeedback = ref<Feedback | null>(null);
  const configVersions = ref<ConfigVersionListItemData[]>([]);
  const configVersionDetails = ref<Record<number, ConfigVersionData>>({});
  const configVersionPagination = reactive<PaginationState>({ page: 1, pageSize: 10, total: 0 });
  const selectedConfigVersionNumber = ref<number | null>(null);
  const selectedConfigDetailVersion = ref<number | null>(null);
  const configDetailModalOpen = ref(false);
  const configEditorText = ref("");
  const configValidationResult = ref<SetupValidationData | null>(null);
  const lastConfigValidatedText = ref<string | null>(null);
  const configModalMode = ref<ConfigModalMode>(null);

  const configDraftItems = computed(() =>
    configVersions.value.filter((item) => item.status !== "active" && item.status !== "archived"),
  );
  const paginatedConfigVersions = computed(() => configVersions.value);
  const activeConfigVersion = computed(() => {
    const activeVersion = configVersions.value.find((version) => version.status === "active");
    return activeVersion?.version ?? options.setupActiveConfigVersion.value ?? 1;
  });
  const activeConfigVersionRecord = computed(
    () => configVersionDetails.value[activeConfigVersion.value] ?? null,
  );
  const selectedConfigVersionRecord = computed(() =>
    selectedConfigVersionNumber.value === null
      ? null
      : (configVersionDetails.value[selectedConfigVersionNumber.value] ?? null),
  );
  const selectedConfigDetailRecord = computed(() =>
    selectedConfigDetailVersion.value === null
      ? null
      : (configVersionDetails.value[selectedConfigDetailVersion.value] ?? null),
  );
  const configEditorParseError = computed(() => validateConfigForm());
  const configValidationFresh = computed(
    () =>
      configValidationResult.value?.valid === true &&
      lastConfigValidatedText.value === configEditorText.value,
  );
  const canValidateSelectedConfig = computed(
    () =>
      Boolean(configModalMode.value) &&
      options.canManageConfig.value &&
      !configBusy.loading &&
      !configBusy.validating &&
      !configBusy.saving &&
      !configBusy.publishing &&
      !configBusy.deleting &&
      configEditorParseError.value === null,
  );
  const canSaveSelectedConfigDraft = computed(
    () =>
      canValidateSelectedConfig.value &&
      !configBusy.validating &&
      configValidationFresh.value,
  );

  const {
    archiveConfigVersionFromUi,
    ensureConfigVersionDetail,
    openConfigVersionDetail,
    openCreateConfigModal,
    openEditConfigVersion,
    publishDraftVersion,
    refreshConfigVersions,
    saveSelectedDraft,
    validateSelectedConfig,
  } = useConfigVersionActions({
    ...options,
    activeConfigVersion,
    activeConfigVersionRecord,
    buildEditedActiveConfigBundle,
    clearConfigManagementState,
    closeConfigModal,
    configBusy,
    configDetailModalOpen,
    configEditorParseError,
    configEditorText,
    configFeedback,
    configFormSignature,
    configModalMode,
    configValidationResult,
    configVersionDetails,
    configVersionPagination,
    configVersions,
    lastConfigValidatedText,
    resetConfigModalState,
    selectedConfigDetailVersion,
    selectedConfigVersionNumber,
    syncConfigFormFromVersion,
    syncPaginationState,
  });

  function closeConfigVersionDetail(): void {
    configDetailModalOpen.value = false;
    selectedConfigDetailVersion.value = null;
  }

  function closeConfigModal(): void {
    configModalMode.value = null;
  }

  function configModalTitle(): string {
    if (configModalMode.value === "create") {
      return "新建配置版本";
    }
    if (configModalMode.value === "edit") {
      return `编辑配置版本 v${selectedConfigVersionNumber.value ?? "-"}`;
    }
    return "配置管理";
  }

  function updateConfigFieldFromInput(field: FieldDefinition, value: string): void {
    if (field.input === "number") {
      const parsed = Number(value);
      setConfigFormValue(field.key, Number.isFinite(parsed) ? parsed : 0);
      resetConfigValidationState();
      return;
    }
    setConfigFormValue(field.key, value);
    resetConfigValidationState();
  }

  function updateConfigFieldFromSelect(field: FieldDefinition, value: string): void {
    setConfigFormValue(field.key, value);
    resetConfigValidationState();
  }

  function updateConfigFieldFromCheckbox(field: FieldDefinition, value: boolean): void {
    setConfigFormValue(field.key, value);
    resetConfigValidationState();
  }

  function clearConfigManagementState(): void {
    configDetailModalOpen.value = false;
    configVersions.value = [];
    configVersionDetails.value = {};
    clearPaginationState(configVersionPagination);
    selectedConfigDetailVersion.value = null;
    selectedConfigVersionNumber.value = null;
    configEditorText.value = "";
    configValidationResult.value = null;
    lastConfigValidatedText.value = null;
    configModalMode.value = null;
  }

  function resetConfigModalState(): void {
    configFeedback.value = null;
    configValidationResult.value = null;
    lastConfigValidatedText.value = null;
    configEditorText.value = configFormSignature();
  }

  function resetConfigValidationState(): void {
    configValidationResult.value = null;
    lastConfigValidatedText.value = null;
    configEditorText.value = configFormSignature();
  }

  function setConfigFormValue(key: keyof SetupFormModel, value: unknown): void {
    (configForm as Record<keyof SetupFormModel, unknown>)[key] = value;
  }

  function syncConfigFormFromVersion(version: ConfigVersionData | null): void {
    const configBundle = version?.config ?? activeConfigVersionRecord.value?.config ?? {};
    const defaults = createDefaultSetupForm();
    Object.assign(configForm, defaults);
    hydrateConfigForm(configForm, configBundle);
    configEditorText.value = configFormSignature();
  }

  function buildEditedActiveConfigBundle(): Record<string, unknown> | null {
    const baseConfig = currentEditableConfigBundle();
    const config = cloneJsonRecord(baseConfig);
    const formConfig = buildSetupPayload(configForm).config;
    for (const definition of configSectionDefinitions) {
      const formValue = asRecord(formConfig[definition.key]);
      if (!formValue) {
        continue;
      }
      config[definition.key] = mergeConfigSectionValue(
        definition.key,
        asRecord(config[definition.key]) ?? {},
        formValue,
      );
    }
    config.schema_version = asNumber(config.schema_version, 1);
    config.config_version = selectedConfigVersionNumber.value ?? activeConfigVersion.value;
    if (!isRecord(config.scope)) {
      config.scope = { type: "global", id: "global" };
    }
    return config;
  }

  function currentEditableConfigBundle(): Record<string, unknown> {
    const source =
      selectedConfigVersionNumber.value === null
        ? activeConfigVersionRecord.value?.config
        : configVersionDetails.value[selectedConfigVersionNumber.value]?.config;
    return source ? cloneJsonRecord(source) : {};
  }

  function configFormSignature(): string {
    const value = buildEditedActiveConfigBundle();
    return JSON.stringify(
      {
        version: selectedConfigVersionNumber.value,
        value,
      },
      null,
      2,
    );
  }

  function validateConfigForm(): string | null {
    for (const field of configEditableFields()) {
      const value = configForm[field.key];
      if (field.required && isBlankFieldValue(value)) {
        return `${field.label} 为必填项。`;
      }
      if (field.input === "number") {
        const numberValue = Number(value);
        if (!Number.isFinite(numberValue)) {
          return `${field.label} 必须是有效数字。`;
        }
        if (field.min !== undefined && numberValue < field.min) {
          return `${field.label} 不能小于 ${field.min}。`;
        }
      }
    }
    return null;
  }

  return {
    activeConfigVersion,
    activeConfigVersionRecord,
    archiveConfigVersionFromUi,
    canSaveSelectedConfigDraft,
    canValidateSelectedConfig,
    clearConfigManagementState,
    closeConfigModal,
    closeConfigVersionDetail,
    configBusy,
    configDetailModalOpen,
    configDraftItems,
    configEditorParseError,
    configFeedback,
    configForm,
    configModalMode,
    configModalTitle,
    configValidationResult,
    configVersionDetails,
    configVersionPagination,
    configVersions,
    openConfigVersionDetail,
    openCreateConfigModal,
    openEditConfigVersion,
    paginatedConfigVersions,
    publishDraftVersion,
    refreshConfigVersions,
    saveSelectedDraft,
    selectedConfigDetailRecord,
    selectedConfigVersionRecord,
    updateConfigFieldFromCheckbox,
    updateConfigFieldFromInput,
    updateConfigFieldFromSelect,
    validateSelectedConfig,
  };
}

export type ConfigManagementRuntime = ReturnType<typeof useConfigManagement>;
