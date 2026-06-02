import { ref, type ComputedRef } from "vue";

import {
  listAdminDepartmentOptions,
  type AdminDepartmentListItemData,
  type AdminDepartmentOptionData,
} from "@/api/departments";
import {
  mergeDepartmentOptions,
  type DepartmentLike,
} from "@/features/departments/departmentOptionHelpers";

interface UseDepartmentLookupRuntimeOptions {
  canReadDepartments: ComputedRef<boolean>;
  ensureAccessToken: () => Promise<string | null>;
  getOptionKeyword: () => string;
  getPinnedDepartments: () => Array<DepartmentLike | null | undefined>;
  onDepartmentOptionsChanged?: () => void;
  selectorPageSize: number;
}

export function useDepartmentLookupRuntime(options: UseDepartmentLookupRuntimeOptions) {
  const adminDepartmentOptions = ref<AdminDepartmentOptionData[]>([]);
  const adminDepartments = ref<AdminDepartmentListItemData[]>([]);

  async function refreshDepartmentOptions(existingAccessToken?: string): Promise<void> {
    if (!options.canReadDepartments.value) {
      adminDepartmentOptions.value = [];
      options.onDepartmentOptionsChanged?.();
      return;
    }
    const accessToken = existingAccessToken ?? (await options.ensureAccessToken());
    if (!accessToken) {
      return;
    }
    const response = await listAdminDepartmentOptions(accessToken, {
      keyword: options.getOptionKeyword().trim() || undefined,
      page_size: options.selectorPageSize,
      status: "active",
    });
    adminDepartmentOptions.value = mergeDepartmentOptions(
      response.data,
      options.getPinnedDepartments(),
    );
    options.onDepartmentOptionsChanged?.();
  }

  function refreshDepartmentOptionsFromSearch(): void {
    void refreshDepartmentOptions();
  }

  function clearDepartmentOptions(): void {
    adminDepartmentOptions.value = [];
    adminDepartments.value = [];
  }

  return {
    adminDepartmentOptions,
    adminDepartments,
    clearDepartmentOptions,
    refreshDepartmentOptions,
    refreshDepartmentOptionsFromSearch,
  };
}
