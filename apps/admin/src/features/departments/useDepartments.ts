import { type ComputedRef, type Ref } from "vue";

import {
  type AdminDepartmentData,
  type AdminDepartmentListItemData,
  type AdminDepartmentOptionData,
  createAdminDepartment,
  deleteAdminDepartment,
  getAdminDepartment,
  listAdminDepartmentOptions,
  listAdminDepartments,
  patchAdminDepartment,
} from "@/api/departments";
import {
  mergeDepartmentOptions,
  type DepartmentLike,
} from "@/features/departments/departmentOptionHelpers";
import { clearPaginationState, syncPaginationState, type PaginationState } from "@/utils/pagination";

type Feedback = {
  tone: "success" | "error" | "neutral";
  message: string;
};

type DepartmentSearchForm = {
  keyword: string;
  status: string;
};

type DepartmentCreateForm = {
  code: string;
  name: string;
};

type DepartmentEditForm = {
  name: string;
  status: "active" | "disabled";
};

type DepartmentDangerForm = {
  confirmedDelete: boolean;
};

type DepartmentModalMode = "create" | "edit" | "delete" | null;

type DepartmentBusyState = {
  loading: boolean;
  creating: boolean;
  updating: boolean;
  deleting: boolean;
};

type UseDepartmentsOptions = {
  adminDepartments: Ref<AdminDepartmentListItemData[]>;
  adminDepartmentOptions: Ref<AdminDepartmentOptionData[]>;
  busy: DepartmentBusyState;
  canLoadDepartmentAdmin: ComputedRef<boolean>;
  canReadDepartments: ComputedRef<boolean>;
  createForm: DepartmentCreateForm;
  dangerForm: DepartmentDangerForm;
  editForm: DepartmentEditForm;
  ensureAccessToken: () => Promise<string | null>;
  feedback: Ref<Feedback | null>;
  getPinnedDepartments: () => Array<DepartmentLike | null | undefined>;
  modalMode: Ref<DepartmentModalMode>;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  optionKeyword: () => string;
  onDepartmentOptionsChanged?: () => void;
  pagination: PaginationState;
  searchForm: DepartmentSearchForm;
  selectedDepartment: ComputedRef<AdminDepartmentListItemData | null>;
  selectedDepartmentId: Ref<string>;
  selectorPageSize: number;
};

export function useDepartments(options: UseDepartmentsOptions) {
  function syncDepartmentEditForm(): void {
    const department = options.selectedDepartment.value;
    options.editForm.name = department?.name ?? "";
    options.editForm.status =
      department?.status === "disabled" || department?.status === "active"
        ? department.status
        : "active";
  }

  function upsertDepartmentOption(department: AdminDepartmentData): void {
    const option: AdminDepartmentOptionData = {
      id: department.id,
      name: department.name,
      status: department.status,
      is_default: department.is_default,
    };
    const index = options.adminDepartmentOptions.value.findIndex((item) => item.id === department.id);
    if (index >= 0) {
      options.adminDepartmentOptions.value[index] = option;
      return;
    }
    if (option.status === "active") {
      options.adminDepartmentOptions.value = [option, ...options.adminDepartmentOptions.value];
    }
  }

  function upsertDepartment(department: AdminDepartmentData): void {
    const index = options.adminDepartments.value.findIndex((item) => item.id === department.id);
    const listItem: AdminDepartmentListItemData = {
      id: department.id,
      name: department.name,
      status: department.status,
      is_default: department.is_default,
    };
    if (index >= 0) {
      options.adminDepartments.value[index] = listItem;
    } else {
      options.adminDepartments.value = [listItem, ...options.adminDepartments.value];
    }
    upsertDepartmentOption(department);
  }

  async function refreshDepartmentOptions(existingAccessToken?: string): Promise<void> {
    if (!options.canReadDepartments.value) {
      options.adminDepartmentOptions.value = [];
      options.onDepartmentOptionsChanged?.();
      return;
    }
    const accessToken = existingAccessToken ?? (await options.ensureAccessToken());
    if (!accessToken) {
      return;
    }
    const response = await listAdminDepartmentOptions(accessToken, {
      keyword: options.optionKeyword().trim() || undefined,
      status: "active",
      page_size: options.selectorPageSize,
    });
    options.adminDepartmentOptions.value = mergeDepartmentOptions(response.data, [
      ...options.getPinnedDepartments(),
      ...options.adminDepartments.value,
    ]);
    options.onDepartmentOptionsChanged?.();
  }

  function refreshDepartmentOptionsFromSearch(): void {
    void refreshDepartmentOptions();
  }

  async function refreshDepartmentAdminState(): Promise<void> {
    if (!options.canLoadDepartmentAdmin.value) {
      options.adminDepartments.value = [];
      clearPaginationState(options.pagination);
      options.selectedDepartmentId.value = "";
      syncDepartmentEditForm();
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.busy.loading = true;
    try {
      const response = await listAdminDepartments(accessToken, {
        keyword: options.searchForm.keyword.trim() || undefined,
        status: options.searchForm.status || undefined,
        page: options.pagination.page,
        page_size: options.pagination.pageSize,
      });
      options.adminDepartments.value = response.data;
      syncPaginationState(options.pagination, response.pagination);
      if (
        !options.selectedDepartmentId.value ||
        !options.adminDepartments.value.some((department) => department.id === options.selectedDepartmentId.value)
      ) {
        options.selectedDepartmentId.value = options.adminDepartments.value[0]?.id ?? "";
      }
      syncDepartmentEditForm();
      options.feedback.value = {
        tone: "success",
        message: "部门数据已刷新。",
      };
    } catch (error) {
      options.feedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "读取部门数据失败"),
      };
    } finally {
      options.busy.loading = false;
    }
  }

  async function selectDepartment(departmentId: string): Promise<void> {
    options.selectedDepartmentId.value = departmentId;
    options.dangerForm.confirmedDelete = false;
    syncDepartmentEditForm();

    const accessToken = await options.ensureAccessToken();
    if (!accessToken || !options.canReadDepartments.value) {
      return;
    }
    try {
      const response = await getAdminDepartment(departmentId, accessToken);
      upsertDepartment(response.data);
      syncDepartmentEditForm();
    } catch (error) {
      options.feedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "读取部门详情失败"),
      };
    }
  }

  function openCreateDepartmentModal(): void {
    options.createForm.code = "";
    options.createForm.name = "";
    options.feedback.value = null;
    options.modalMode.value = "create";
  }

  async function openEditDepartmentModal(department: AdminDepartmentListItemData): Promise<void> {
    options.modalMode.value = "edit";
    await selectDepartment(department.id);
  }

  async function openDeleteDepartmentModal(department: AdminDepartmentListItemData): Promise<void> {
    options.dangerForm.confirmedDelete = false;
    options.modalMode.value = "delete";
    await selectDepartment(department.id);
  }

  function closeDepartmentModal(): void {
    options.modalMode.value = null;
    options.dangerForm.confirmedDelete = false;
  }

  async function submitCreateDepartment(): Promise<void> {
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.busy.creating = true;
    try {
      const response = await createAdminDepartment(
        {
          code: options.createForm.code.trim(),
          name: options.createForm.name.trim(),
        },
        accessToken,
      );
      options.createForm.code = "";
      options.createForm.name = "";
      options.searchForm.status = "";
      options.selectedDepartmentId.value = response.data.id;
      upsertDepartment(response.data);
      syncDepartmentEditForm();
      options.onDepartmentOptionsChanged?.();
      await refreshDepartmentAdminState();
      options.feedback.value = {
        tone: "success",
        message: "部门已创建。",
      };
      closeDepartmentModal();
    } catch (error) {
      options.feedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "创建部门失败"),
      };
    } finally {
      options.busy.creating = false;
    }
  }

  async function submitPatchDepartment(): Promise<void> {
    const department = options.selectedDepartment.value;
    if (!department) {
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.busy.updating = true;
    try {
      const response = await patchAdminDepartment(
        department.id,
        {
          name: options.editForm.name.trim(),
          status: options.editForm.status,
        },
        accessToken,
      );
      upsertDepartment(response.data);
      syncDepartmentEditForm();
      await refreshDepartmentAdminState();
      options.feedback.value = {
        tone: "success",
        message: "部门已更新。",
      };
      closeDepartmentModal();
    } catch (error) {
      options.feedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "更新部门失败"),
      };
    } finally {
      options.busy.updating = false;
    }
  }

  async function deleteSelectedDepartment(): Promise<void> {
    const department = options.selectedDepartment.value;
    if (!department || !options.dangerForm.confirmedDelete) {
      options.feedback.value = {
        tone: "error",
        message: "删除部门前必须勾选确认项。",
      };
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.busy.deleting = true;
    try {
      await deleteAdminDepartment(department.id, accessToken, true);
      options.selectedDepartmentId.value = "";
      options.adminDepartmentOptions.value = options.adminDepartmentOptions.value.filter(
        (item) => item.id !== department.id,
      );
      options.dangerForm.confirmedDelete = false;
      await refreshDepartmentAdminState();
      options.onDepartmentOptionsChanged?.();
      options.feedback.value = {
        tone: "success",
        message: "部门已删除。",
      };
      closeDepartmentModal();
    } catch (error) {
      options.feedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "删除部门失败"),
      };
    } finally {
      options.busy.deleting = false;
    }
  }

  return {
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
  };
}
