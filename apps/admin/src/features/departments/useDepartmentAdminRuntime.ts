import { reactive, ref, type ComputedRef } from "vue";

import type {
  AdminDepartmentListItemData,
  AdminDepartmentOptionData,
} from "@/api/departments";
import { useDepartmentModals } from "@/features/departments/useDepartmentModals";
import { useDepartments } from "@/features/departments/useDepartments";
import { clearPaginationState, type PaginationState } from "@/utils/pagination";
import type { Tone } from "@/utils/status";

type DepartmentLike = {
  id: string;
  name: string;
  status: string;
  is_default?: boolean | null;
};

type DepartmentAdminRuntimeOptions = {
  canLoadDepartmentAdmin: ComputedRef<boolean>;
  canManageDepartments: ComputedRef<boolean>;
  canReadDepartments: ComputedRef<boolean>;
  ensureAccessToken: () => Promise<string | null>;
  getOptionKeyword: () => string;
  getPinnedDepartments: () => Array<DepartmentLike | null | undefined>;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  onDepartmentOptionsChanged?: () => void;
  selectorPageSize: number;
};

export function useDepartmentAdminRuntime(options: DepartmentAdminRuntimeOptions) {
  const departmentAdminBusy = reactive({
    loading: false,
    creating: false,
    updating: false,
    deleting: false,
  });
  const departmentSearchForm = reactive({
    keyword: "",
    status: "",
  });
  const departmentPagination = reactive<PaginationState>({
    page: 1,
    pageSize: 20,
    total: 0,
  });
  const departmentAdminFeedback = ref<{
    tone: Exclude<Tone, "warning">;
    message: string;
  } | null>(null);
  const adminDepartments = ref<AdminDepartmentListItemData[]>([]);
  const adminDepartmentOptions = ref<AdminDepartmentOptionData[]>([]);

  const {
    canCreateDepartment,
    canDeleteSelectedDepartment,
    canUpdateSelectedDepartment,
    departmentCreateForm,
    departmentDangerForm,
    departmentEditForm,
    departmentModalMode,
    selectedDepartment,
    selectedDepartmentId,
  } = useDepartmentModals({
    adminDepartments,
    busy: departmentAdminBusy,
    canManageDepartments: options.canManageDepartments,
  });

  const {
    closeDepartmentModal,
    deleteSelectedDepartment,
    openCreateDepartmentModal,
    openDeleteDepartmentModal,
    openEditDepartmentModal,
    refreshDepartmentAdminState,
    refreshDepartmentOptions,
    refreshDepartmentOptionsFromSearch,
    selectDepartment,
    submitCreateDepartment,
    submitPatchDepartment,
    syncDepartmentEditForm,
    upsertDepartment,
  } = useDepartments({
    adminDepartmentOptions,
    adminDepartments,
    busy: departmentAdminBusy,
    canLoadDepartmentAdmin: options.canLoadDepartmentAdmin,
    canReadDepartments: options.canReadDepartments,
    createForm: departmentCreateForm,
    dangerForm: departmentDangerForm,
    editForm: departmentEditForm,
    ensureAccessToken: options.ensureAccessToken,
    feedback: departmentAdminFeedback,
    getPinnedDepartments: options.getPinnedDepartments,
    modalMode: departmentModalMode,
    normalizeErrorMessage: options.normalizeErrorMessage,
    optionKeyword: options.getOptionKeyword,
    onDepartmentOptionsChanged: options.onDepartmentOptionsChanged,
    pagination: departmentPagination,
    searchForm: departmentSearchForm,
    selectedDepartment,
    selectedDepartmentId,
    selectorPageSize: options.selectorPageSize,
  });

  function clearDepartmentAdminState(): void {
    adminDepartments.value = [];
    adminDepartmentOptions.value = [];
    clearPaginationState(departmentPagination);
    selectedDepartmentId.value = "";
    departmentSearchForm.keyword = "";
    departmentSearchForm.status = "";
    departmentModalMode.value = null;
    departmentCreateForm.code = "";
    departmentCreateForm.name = "";
    departmentEditForm.name = "";
    departmentEditForm.status = "active";
    departmentDangerForm.confirmedDelete = false;
    departmentAdminFeedback.value = null;
  }

  function clearDepartmentOptions(): void {
    adminDepartmentOptions.value = [];
  }

  return {
    adminDepartmentOptions,
    adminDepartments,
    canCreateDepartment,
    canDeleteSelectedDepartment,
    canUpdateSelectedDepartment,
    clearDepartmentAdminState,
    clearDepartmentOptions,
    closeDepartmentModal,
    deleteSelectedDepartment,
    departmentAdminBusy,
    departmentAdminFeedback,
    departmentCreateForm,
    departmentDangerForm,
    departmentEditForm,
    departmentModalMode,
    departmentPagination,
    departmentSearchForm,
    openCreateDepartmentModal,
    openDeleteDepartmentModal,
    openEditDepartmentModal,
    refreshDepartmentAdminState,
    refreshDepartmentOptions,
    refreshDepartmentOptionsFromSearch,
    selectDepartment,
    selectedDepartment,
    selectedDepartmentId,
    submitCreateDepartment,
    submitPatchDepartment,
    syncDepartmentEditForm,
    upsertDepartment,
  };
}
