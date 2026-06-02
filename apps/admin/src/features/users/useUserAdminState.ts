import { computed, reactive, ref } from "vue";

import type { CurrentUserDepartment } from "@/api/auth";
import type { AdminUserData, AdminUserListItemData } from "@/api/users";
import type {
  DepartmentSelectorItem,
} from "@/features/users/useUserModals";
import type { UserAdminRuntimeOptions } from "@/features/users/userAdminRuntimeTypes";
import type { PaginationState } from "@/utils/pagination";
import type { Tone } from "@/utils/status";

export function useUserAdminState(options: UserAdminRuntimeOptions) {
  const userAdminBusy = reactive({
    loading: false,
    creating: false,
    updating: false,
    updatingDepartments: false,
    resettingPassword: false,
    updatingRoles: false,
  });
  const userSearchForm = reactive({
    keyword: "",
    status: "",
  });
  const userPagination = reactive<PaginationState>({
    page: 1,
    pageSize: 20,
    total: 0,
  });
  const userAdminFeedback = ref<{
    tone: Exclude<Tone, "warning">;
    message: string;
  } | null>(null);
  const adminUsers = ref<AdminUserListItemData[]>([]);
  const selectedAdminUserDetail = ref<AdminUserData | null>(null);

  const currentUserDepartmentIds = computed(
    () => new Set((options.currentUser.value?.departments ?? []).map((department) => department.id)),
  );
  const canSelectAnyDepartmentForUserCreate = computed(
    () => options.canManageDepartments.value,
  );
  const createUserDepartmentOptions = computed<DepartmentSelectorItem[]>(() => {
    if (canSelectAnyDepartmentForUserCreate.value) {
      return options.activeDepartments.value;
    }
    const ownDepartments = ownActiveDepartments(options.currentUser.value?.departments ?? []);
    if (!options.activeDepartments.value.length) {
      return ownDepartments;
    }
    return options.activeDepartments.value.filter((department) =>
      currentUserDepartmentIds.value.has(department.id),
    );
  });

  return {
    adminUsers,
    createUserDepartmentOptions,
    selectedAdminUserDetail,
    userAdminBusy,
    userAdminFeedback,
    userPagination,
    userSearchForm,
  };
}

function ownActiveDepartments(departments: CurrentUserDepartment[]): DepartmentSelectorItem[] {
  return departments
    .filter((department) => department.status === "active")
    .map((department) => ({ ...department, is_default: false }));
}
