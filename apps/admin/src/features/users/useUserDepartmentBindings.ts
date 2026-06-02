import { computed, reactive, ref, type ComputedRef, type Ref } from "vue";

import type { AdminDepartmentData } from "@/api/departments";
import type { PaginationData } from "@/api/commonTypes";
import { listAdminUserDepartments, type AdminUserData, type AdminUserListItemData } from "@/api/users";
import type { UserModalMode } from "@/features/users/useUserModals";

type Feedback = {
  tone: "success" | "error" | "neutral";
  message: string;
};

type PaginationState = {
  page: number;
  pageSize: number;
  total: number;
};

type UserBusyState = {
  updatingDepartments: boolean;
};

export type UserDepartmentForm = {
  departmentIds: string[];
  confirmedReplacePrimary: boolean;
};

function syncPaginationState(state: PaginationState, pagination?: PaginationData | null): void {
  if (!pagination) {
    return;
  }
  state.page = pagination.page;
  state.pageSize = pagination.page_size;
  state.total = pagination.total;
}

function clearPaginationState(state: PaginationState): void {
  state.page = 1;
  state.total = 0;
}

function paginationTotalPages(state: PaginationState): number {
  return Math.max(1, Math.ceil(state.total / Math.max(state.pageSize, 1)));
}

export function useUserDepartmentBindings(options: {
  adminUsers: Ref<AdminUserListItemData[]>;
  busy: UserBusyState;
  canManageDepartments: ComputedRef<boolean>;
  canReadDepartments: ComputedRef<boolean>;
  ensureAccessToken: () => Promise<string | null>;
  feedback: Ref<Feedback | null>;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  selectedAdminUser: ComputedRef<AdminUserData | null>;
  selectedAdminUserDetail: Ref<AdminUserData | null>;
  selectedAdminUserId: Ref<string>;
  userModalMode: Ref<UserModalMode>;
}) {
  const selectedUserDepartments = ref<AdminDepartmentData[]>([]);
  const selectedUserDepartmentPagination = reactive<PaginationState>({
    page: 1,
    pageSize: 10,
    total: 0,
  });
  const userDepartmentForm = reactive<UserDepartmentForm>({
    departmentIds: [],
    confirmedReplacePrimary: false,
  });

  const selectedUserDepartmentsForDisplay = computed(() => {
    if (selectedUserDepartments.value.length > 0) {
      return selectedUserDepartments.value;
    }
    return options.selectedAdminUser.value?.departments ?? [];
  });
  const selectedUserDepartmentsForForm = computed(
    () => options.selectedAdminUser.value?.departments ?? selectedUserDepartments.value,
  );
  const selectedUserDepartmentIds = computed(() => new Set(userDepartmentForm.departmentIds));
  const currentSelectedUserPrimaryDepartmentId = computed(() => {
    const departments = selectedUserDepartmentsForForm.value;
    return departments.find((department) => department.is_primary)?.id ?? departments[0]?.id ?? "";
  });
  const nextSelectedUserPrimaryDepartmentId = computed(
    () => userDepartmentForm.departmentIds[0] ?? "",
  );
  const selectedUserPrimaryDepartmentWillChange = computed(
    () =>
      Boolean(currentSelectedUserPrimaryDepartmentId.value) &&
      Boolean(nextSelectedUserPrimaryDepartmentId.value) &&
      currentSelectedUserPrimaryDepartmentId.value !== nextSelectedUserPrimaryDepartmentId.value,
  );
  const canSaveSelectedUserDepartments = computed(
    () =>
      Boolean(options.selectedAdminUser.value) &&
      options.canManageDepartments.value &&
      userDepartmentForm.departmentIds.length > 0 &&
      (!selectedUserPrimaryDepartmentWillChange.value ||
        userDepartmentForm.confirmedReplacePrimary) &&
      !options.busy.updatingDepartments,
  );

  function toggleSelectedUserDepartment(departmentId: string, checked: boolean): void {
    const next = new Set(userDepartmentForm.departmentIds);
    if (checked) {
      next.add(departmentId);
    } else {
      next.delete(departmentId);
    }
    userDepartmentForm.departmentIds = Array.from(next);
    if (!selectedUserPrimaryDepartmentWillChange.value) {
      userDepartmentForm.confirmedReplacePrimary = false;
    }
  }

  function syncSelectedUserDepartmentForm(): void {
    userDepartmentForm.departmentIds = selectedUserDepartmentsForForm.value.map(
      (department) => department.id,
    );
    userDepartmentForm.confirmedReplacePrimary = false;
  }

  function updateSelectedAdminUserDepartments(departments: AdminDepartmentData[]): void {
    if (options.selectedAdminUserDetail.value?.id === options.selectedAdminUserId.value) {
      options.selectedAdminUserDetail.value = {
        ...options.selectedAdminUserDetail.value,
        departments,
      };
    }
    const index = options.adminUsers.value.findIndex(
      (user) => user.id === options.selectedAdminUserId.value,
    );
    if (index < 0) {
      return;
    }
    options.adminUsers.value[index] = {
      ...options.adminUsers.value[index],
      department_names: departments.map((department) => department.name),
    };
  }

  async function refreshSelectedUserDepartments(existingAccessToken?: string): Promise<void> {
    if (!options.selectedAdminUserId.value) {
      selectedUserDepartments.value = [];
      clearPaginationState(selectedUserDepartmentPagination);
      syncSelectedUserDepartmentForm();
      return;
    }
    if (!options.canReadDepartments.value) {
      selectedUserDepartments.value = options.selectedAdminUser.value?.departments ?? [];
      selectedUserDepartmentPagination.page = 1;
      selectedUserDepartmentPagination.total = selectedUserDepartments.value.length;
      syncSelectedUserDepartmentForm();
      return;
    }
    const accessToken = existingAccessToken ?? (await options.ensureAccessToken());
    if (!accessToken) {
      return;
    }
    try {
      const response = await listAdminUserDepartments(
        options.selectedAdminUserId.value,
        accessToken,
        {
          page: selectedUserDepartmentPagination.page,
          page_size: selectedUserDepartmentPagination.pageSize,
        },
      );
      selectedUserDepartments.value = response.data;
      syncPaginationState(selectedUserDepartmentPagination, response.pagination);
      if (
        selectedUserDepartments.value.length === 0 &&
        selectedUserDepartmentPagination.total > 0 &&
        selectedUserDepartmentPagination.page > 1
      ) {
        selectedUserDepartmentPagination.page = paginationTotalPages(
          selectedUserDepartmentPagination,
        );
        await refreshSelectedUserDepartments(accessToken);
        return;
      }
      syncSelectedUserDepartmentForm();
    } catch (error) {
      options.feedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "读取用户部门归属失败"),
      };
      throw error;
    }
  }

  async function refreshSelectedUserDepartmentsPage(): Promise<void> {
    await refreshSelectedUserDepartments();
  }

  async function openUserDepartmentsModal(
    user: AdminUserListItemData,
    selectAdminUser: (userId: string) => Promise<void>,
  ): Promise<void> {
    await selectAdminUser(user.id);
    options.userModalMode.value = "departments";
  }

  function clearUserDepartmentBindingState(): void {
    selectedUserDepartments.value = [];
    clearPaginationState(selectedUserDepartmentPagination);
    userDepartmentForm.departmentIds = [];
    userDepartmentForm.confirmedReplacePrimary = false;
  }

  return {
    canSaveSelectedUserDepartments,
    clearUserDepartmentBindingState,
    openUserDepartmentsModal,
    refreshSelectedUserDepartments,
    refreshSelectedUserDepartmentsPage,
    selectedUserDepartmentIds,
    selectedUserDepartmentPagination,
    selectedUserDepartments,
    selectedUserDepartmentsForDisplay,
    selectedUserDepartmentsForForm,
    selectedUserPrimaryDepartmentWillChange,
    syncSelectedUserDepartmentForm,
    toggleSelectedUserDepartment,
    updateSelectedAdminUserDepartments,
    userDepartmentForm,
  };
}
