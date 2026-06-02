import { computed, reactive, ref, type ComputedRef, type Ref } from "vue";

import type { AdminDepartmentListItemData } from "@/api/departments";

export type DepartmentModalMode = "create" | "edit" | "delete" | null;

export type DepartmentCreateForm = {
  code: string;
  name: string;
};

export type DepartmentEditForm = {
  name: string;
  status: "active" | "disabled";
};

export type DepartmentDangerForm = {
  confirmedDelete: boolean;
};

type DepartmentBusyState = {
  creating: boolean;
  updating: boolean;
  deleting: boolean;
};

export function useDepartmentModals(options: {
  adminDepartments: Ref<AdminDepartmentListItemData[]>;
  busy: DepartmentBusyState;
  canManageDepartments: ComputedRef<boolean>;
}) {
  const selectedDepartmentId = ref("");
  const departmentModalMode = ref<DepartmentModalMode>(null);
  const departmentCreateForm = reactive<DepartmentCreateForm>({
    code: "",
    name: "",
  });
  const departmentEditForm = reactive<DepartmentEditForm>({
    name: "",
    status: "active",
  });
  const departmentDangerForm = reactive<DepartmentDangerForm>({
    confirmedDelete: false,
  });

  const selectedDepartment = computed(
    () =>
      options.adminDepartments.value.find(
        (department) => department.id === selectedDepartmentId.value,
      ) ?? null,
  );

  const canCreateDepartment = computed(
    () =>
      options.canManageDepartments.value &&
      departmentCreateForm.code.trim().length > 0 &&
      departmentCreateForm.name.trim().length > 0 &&
      !options.busy.creating,
  );
  const canUpdateSelectedDepartment = computed(
    () =>
      Boolean(selectedDepartment.value) &&
      options.canManageDepartments.value &&
      departmentEditForm.name.trim().length > 0 &&
      !options.busy.updating,
  );
  const canDeleteSelectedDepartment = computed(
    () =>
      Boolean(selectedDepartment.value) &&
      options.canManageDepartments.value &&
      selectedDepartment.value?.is_default !== true &&
      departmentDangerForm.confirmedDelete &&
      !options.busy.deleting,
  );

  return {
    canCreateDepartment,
    canDeleteSelectedDepartment,
    canUpdateSelectedDepartment,
    departmentCreateForm,
    departmentDangerForm,
    departmentEditForm,
    departmentModalMode,
    selectedDepartment,
    selectedDepartmentId,
  };
}
