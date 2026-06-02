import type { ComputedRef, Ref } from "vue";

import {
  archiveConfigVersion,
  createConfigVersion,
  getConfigVersion,
  listConfigVersions,
  publishConfigVersion,
  updateConfigVersion,
  validateAdminConfig,
  type ConfigVersionData,
  type ConfigVersionListItemData,
  type SetupValidationData,
} from "@/api/config";
import { isArchivableConfigVersion } from "@/features/config/configDisplay";
import type { ConfigModalMode } from "@/features/config/useConfigManagement";
import type { PaginationState } from "@/utils/pagination";

interface UseConfigVersionActionsOptions {
  activeConfigVersion: ComputedRef<number>;
  activeConfigVersionRecord: ComputedRef<ConfigVersionData | null>;
  buildEditedActiveConfigBundle: () => Record<string, unknown> | null;
  canManageConfig: Ref<boolean>;
  canReadConfig: Ref<boolean>;
  clearConfigManagementState: () => void;
  closeConfigModal: () => void;
  configBusy: {
    deleting: boolean;
    loading: boolean;
    publishing: boolean;
    saving: boolean;
    validating: boolean;
  };
  configDetailModalOpen: Ref<boolean>;
  configEditorParseError: ComputedRef<string | null>;
  configEditorText: Ref<string>;
  configFeedback: Ref<{ tone: "success" | "error" | "neutral"; message: string } | null>;
  configFormSignature: () => string;
  configModalMode: Ref<ConfigModalMode>;
  configValidationResult: Ref<SetupValidationData | null>;
  configVersionDetails: Ref<Record<number, ConfigVersionData>>;
  configVersionPagination: PaginationState;
  configVersions: Ref<ConfigVersionListItemData[]>;
  confirmAction?: (message: string) => boolean;
  ensureAccessToken: () => Promise<string | null>;
  lastConfigValidatedText: Ref<string | null>;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  onConfigChanged?: () => Promise<void>;
  resetConfigModalState: () => void;
  selectedConfigDetailVersion: Ref<number | null>;
  selectedConfigVersionNumber: Ref<number | null>;
  setupActiveConfigVersion: Ref<number | null | undefined>;
  syncConfigFormFromVersion: (version: ConfigVersionData | null) => void;
  syncPaginationState: (
    state: PaginationState,
    pagination: { page: number; page_size: number; total: number },
  ) => void;
}

export function useConfigVersionActions(options: UseConfigVersionActionsOptions) {
  async function refreshConfigVersions(): Promise<void> {
    if (!options.canReadConfig.value && !options.canManageConfig.value) {
      options.clearConfigManagementState();
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.configBusy.loading = true;
    try {
      const versionsResponse = await listConfigVersions(accessToken, {
        page: options.configVersionPagination.page,
        page_size: options.configVersionPagination.pageSize,
      });
      options.configVersions.value = versionsResponse.data;
      options.syncPaginationState(options.configVersionPagination, versionsResponse.pagination);
      const activeVersionNumber =
        options.configVersions.value.find(
          (version: ConfigVersionListItemData) => version.status === "active",
        )?.version ??
        options.setupActiveConfigVersion.value ??
        options.activeConfigVersion.value;
      if (activeVersionNumber) {
        await ensureConfigVersionDetail(activeVersionNumber, accessToken);
      }
      options.syncConfigFormFromVersion(options.activeConfigVersionRecord.value);
      options.configFeedback.value = {
        tone: "success",
        message: "配置管理数据已刷新。",
      };
    } catch (error) {
      options.configFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "读取配置管理数据失败"),
      };
    } finally {
      options.configBusy.loading = false;
    }
  }

  async function ensureConfigVersionDetail(
    version: number,
    existingAccessToken?: string,
  ): Promise<ConfigVersionData | null> {
    const cached = options.configVersionDetails.value[version];
    if (cached?.config) {
      return cached;
    }
    const accessToken = existingAccessToken ?? (await options.ensureAccessToken());
    if (!accessToken) {
      return null;
    }
    const response = await getConfigVersion(version, accessToken);
    options.configVersionDetails.value = {
      ...options.configVersionDetails.value,
      [response.data.version]: response.data,
    };
    return response.data;
  }

  async function openCreateConfigModal(): Promise<void> {
    options.selectedConfigVersionNumber.value = null;
    try {
      await ensureConfigVersionDetail(options.activeConfigVersion.value);
      options.syncConfigFormFromVersion(options.activeConfigVersionRecord.value);
      options.resetConfigModalState();
      options.configModalMode.value = "create";
    } catch (error) {
      options.configFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "读取当前配置详情失败"),
      };
    }
  }

  async function openEditConfigVersion(version: ConfigVersionListItemData): Promise<void> {
    try {
      const detail = await ensureConfigVersionDetail(version.version);
      if (!detail) {
        return;
      }
      options.selectedConfigVersionNumber.value = detail.version;
      options.syncConfigFormFromVersion(detail);
      options.resetConfigModalState();
      options.configModalMode.value = "edit";
    } catch (error) {
      options.configFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "读取配置版本详情失败"),
      };
    }
  }

  async function openConfigVersionDetail(version: ConfigVersionListItemData): Promise<void> {
    try {
      const detail = await ensureConfigVersionDetail(version.version);
      if (!detail) {
        return;
      }
      options.selectedConfigDetailVersion.value = detail.version;
      options.configDetailModalOpen.value = true;
    } catch (error) {
      options.configFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "读取配置版本详情失败"),
      };
    }
  }

  async function validateSelectedConfig(): Promise<void> {
    const configBundle = options.buildEditedActiveConfigBundle();
    if (!configBundle) {
      options.configFeedback.value = {
        tone: "error",
        message: options.configEditorParseError.value ?? "请先完成配置表单。",
      };
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.configBusy.validating = true;
    try {
      const response = await validateAdminConfig(configBundle, accessToken);
      options.configValidationResult.value = response.data;
      options.configEditorText.value = options.configFormSignature();
      options.lastConfigValidatedText.value = response.data.valid
        ? options.configEditorText.value
        : null;
      options.configFeedback.value = {
        tone: response.data.valid ? "success" : "error",
        message: response.data.valid ? "配置校验通过。" : "配置校验未通过。",
      };
    } catch (error) {
      options.configValidationResult.value = null;
      options.lastConfigValidatedText.value = null;
      options.configFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "配置校验失败"),
      };
    } finally {
      options.configBusy.validating = false;
    }
  }

  async function saveSelectedDraft(): Promise<void> {
    const configBundle = options.buildEditedActiveConfigBundle();
    if (!configBundle) {
      options.configFeedback.value = {
        tone: "error",
        message: options.configEditorParseError.value ?? "请填写需要保存的完整配置。",
      };
      return;
    }
    if (
      options.configModalMode.value === "edit" &&
      options.selectedConfigVersionNumber.value === null
    ) {
      options.configFeedback.value = {
        tone: "error",
        message: "请选择需要编辑的配置版本。",
      };
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.configBusy.saving = true;
    try {
      const response =
        options.configModalMode.value === "create"
          ? await createConfigVersion(configBundle, accessToken)
          : await updateConfigVersion(
              options.selectedConfigVersionNumber.value ?? 0,
              configBundle,
              accessToken,
            );
      options.selectedConfigVersionNumber.value = response.data.version;
      options.configVersionDetails.value = {
        ...options.configVersionDetails.value,
        [response.data.version]: response.data,
      };
      options.configFeedback.value = {
        tone: "success",
        message: `已保存配置版本 v${response.data.version}。`,
      };
      await refreshConfigVersions();
      await options.onConfigChanged?.();
      options.closeConfigModal();
    } catch (error) {
      options.configFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "保存配置草稿失败"),
      };
    } finally {
      options.configBusy.saving = false;
    }
  }

  async function publishDraftVersion(version?: number | null): Promise<void> {
    const targetVersion = version ?? options.selectedConfigVersionNumber.value;
    if (!targetVersion) {
      options.configFeedback.value = {
        tone: "error",
        message: "请选择需要发布的配置草稿版本。",
      };
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.configBusy.publishing = true;
    try {
      const response = await publishConfigVersion(targetVersion, accessToken);
      options.configValidationResult.value = null;
      options.lastConfigValidatedText.value = null;
      options.configFeedback.value = {
        tone: "success",
        message: `已激活配置版本 v${response.data.version}。`,
      };
      await refreshConfigVersions();
      await options.onConfigChanged?.();
      options.closeConfigModal();
    } catch (error) {
      options.configFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "激活配置版本失败"),
      };
    } finally {
      options.configBusy.publishing = false;
    }
  }

  async function archiveConfigVersionFromUi(
    version: ConfigVersionListItemData,
  ): Promise<void> {
    if (!isArchivableConfigVersion(version)) {
      options.configFeedback.value = {
        tone: "error",
        message: "只能归档非 active 且未归档的配置版本。",
      };
      return;
    }
    const confirmed = (options.confirmAction ?? (() => true))(
      `确认归档配置版本 v${version.version}？归档后将不能直接激活该版本。`,
    );
    if (!confirmed) {
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.configBusy.deleting = true;
    try {
      await archiveConfigVersion(version.version, accessToken);
      options.configFeedback.value = {
        tone: "success",
        message: `已归档配置版本 v${version.version}。`,
      };
      await refreshConfigVersions();
      await options.onConfigChanged?.();
    } catch (error) {
      options.configFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "归档配置版本失败"),
      };
    } finally {
      options.configBusy.deleting = false;
    }
  }

  return {
    archiveConfigVersionFromUi,
    ensureConfigVersionDetail,
    openConfigVersionDetail,
    openCreateConfigModal,
    openEditConfigVersion,
    publishDraftVersion,
    refreshConfigVersions,
    saveSelectedDraft,
    validateSelectedConfig,
  };
}
