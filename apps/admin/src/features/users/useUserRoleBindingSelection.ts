import { computed, type ComputedRef, type Ref } from "vue";

import type { AdminDepartmentData, AdminDepartmentOptionData } from "@/api/departments";
import type { AdminKnowledgeBaseOptionData } from "@/api/knowledgeBases";
import type { AdminAssignableRoleOptionData, AdminRoleBindingData } from "@/api/roles";
import type { AdminUserData } from "@/api/users";
import type { RoleBindingForm, UserCreateForm } from "@/features/users/userActionTypes";
import {
  roleBindingKey,
  roleBindingKeyFromParts,
} from "@/features/users/userDisplay";

export type RoleScopeType = AdminAssignableRoleOptionData["scope_type"];

type RoleBindingCandidate = {
  role: AdminAssignableRoleOptionData;
  scopeType: RoleScopeType;
  scopeId: string | null;
};

type UserRoleBindingSelectionOptions = {
  activeDepartments: ComputedRef<AdminDepartmentOptionData[]>;
  activeKnowledgeBases: ComputedRef<AdminKnowledgeBaseOptionData[]>;
  adminRoles: Ref<AdminAssignableRoleOptionData[]>;
  busy: { updatingRoles: boolean };
  canManageRoles: ComputedRef<boolean>;
  roleBindingForm: RoleBindingForm;
  selectedAdminUser: ComputedRef<AdminUserData | null>;
  selectedUserDepartmentsForForm: ComputedRef<AdminDepartmentData[]>;
  selectedUserRoleBindings: Ref<AdminRoleBindingData[]>;
  userCreateForm: UserCreateForm;
};

export function useUserRoleBindingSelection(options: UserRoleBindingSelectionOptions) {
  const initialAssignableRoles = computed(() =>
    options.adminRoles.value.filter((role) => role.status === "active" && role.scope_type === "enterprise"),
  );
  const assignableRoles = computed(() =>
    options.adminRoles.value.filter((role) => role.status === "active"),
  );
  const roleBindingCandidates = computed<RoleBindingCandidate[]>(() =>
    assignableRoles.value.flatMap((role): RoleBindingCandidate[] => {
      if (role.scope_type === "enterprise") {
        return [{ role, scopeType: role.scope_type, scopeId: null }];
      }
      if (role.scope_type === "department") {
        return options.activeDepartments.value.map((department) => ({
          role,
          scopeType: role.scope_type,
          scopeId: department.id,
        }));
      }
      return options.activeKnowledgeBases.value.map((knowledgeBase) => ({
        role,
        scopeType: role.scope_type,
        scopeId: knowledgeBase.id,
      }));
    }),
  );
  const selectedUserRoleBindingKeys = computed(
    () => new Set(options.selectedUserRoleBindings.value.map(roleBindingKey)),
  );
  const selectedRoleForBinding = computed(
    () => options.adminRoles.value.find((role) => role.id === options.roleBindingForm.roleId) ?? null,
  );
  const selectedRoleBindingScopeType = computed(
    () => selectedRoleForBinding.value?.scope_type ?? "enterprise",
  );
  const selectedRoleBindingScopeReady = computed(() => {
    const role = selectedRoleForBinding.value;
    if (!role) {
      return false;
    }
    return role.scope_type === "enterprise" || Boolean(options.roleBindingForm.scopeId);
  });
  const selectedRoleBindingKey = computed(() => {
    const role = selectedRoleForBinding.value;
    if (!role) {
      return "";
    }
    return roleBindingKeyFromParts(
      role.id,
      role.scope_type,
      role.scope_type === "enterprise" ? null : options.roleBindingForm.scopeId,
    );
  });
  const availableRoleBindingCandidates = computed(() =>
    roleBindingCandidates.value.filter(
      (candidate) =>
        !selectedUserRoleBindingKeys.value.has(
          roleBindingKeyFromParts(candidate.role.id, candidate.scopeType, candidate.scopeId),
        ),
    ),
  );
  const selectedCreateRoles = computed(() =>
    options.adminRoles.value.filter((role) => options.userCreateForm.roleIds.includes(role.id)),
  );
  const canAddSelectedUserRole = computed(
    () =>
      Boolean(options.selectedAdminUser.value) &&
      Boolean(selectedRoleForBinding.value) &&
      options.canManageRoles.value &&
      selectedRoleBindingScopeReady.value &&
      Boolean(selectedRoleBindingKey.value) &&
      !selectedUserRoleBindingKeys.value.has(selectedRoleBindingKey.value) &&
      !options.busy.updatingRoles,
  );
  const roleBindingDisabledReason = computed(() => {
    if (canAddSelectedUserRole.value || options.busy.updatingRoles) {
      return "";
    }
    if (!options.selectedAdminUser.value) {
      return "请选择需要授权的用户。";
    }
    if (!options.canManageRoles.value) {
      return "当前账号缺少 role:manage，不能授予角色。";
    }
    if (!selectedRoleForBinding.value) {
      return availableRoleBindingCandidates.value.length === 0
        ? "当前没有可授予的角色作用域；请确认部门或知识库作用域已创建且当前账号有读取权限。"
        : "请选择要授予的角色。";
    }
    if (!selectedRoleBindingScopeReady.value) {
      return selectedRoleBindingScopeType.value === "department"
        ? "请选择部门作用域。"
        : "请选择知识库作用域。";
    }
    if (selectedUserRoleBindingKeys.value.has(selectedRoleBindingKey.value)) {
      return "该角色作用域已经绑定，请选择其他角色或作用域。";
    }
    return "";
  });

  function onRoleBindingRoleChange(roleId: string): void {
    options.roleBindingForm.roleId = roleId;
    options.roleBindingForm.confirmedHighRisk = false;
    syncRoleBindingScopeDefault();
  }

  function syncRoleBindingScopeDefault(): void {
    const role = selectedRoleForBinding.value;
    if (!role || role.scope_type === "enterprise") {
      options.roleBindingForm.scopeId = "";
      return;
    }
    const candidates =
      role.scope_type === "department"
        ? options.activeDepartments.value
        : options.activeKnowledgeBases.value;
    const currentScopeExists = candidates.some((item) => item.id === options.roleBindingForm.scopeId);
    if (currentScopeExists) {
      const currentKey = roleBindingKeyFromParts(
        role.id,
        role.scope_type,
        options.roleBindingForm.scopeId,
      );
      if (!selectedUserRoleBindingKeys.value.has(currentKey)) {
        return;
      }
    }
    if (role.scope_type === "department") {
      const preferredDepartment = preferredDepartmentScopeForRole(role);
      if (preferredDepartment) {
        options.roleBindingForm.scopeId = preferredDepartment.id;
        return;
      }
    }
    const nextAvailableScope = candidates.find(
      (item) =>
        !selectedUserRoleBindingKeys.value.has(
          roleBindingKeyFromParts(role.id, role.scope_type, item.id),
        ),
    );
    options.roleBindingForm.scopeId = nextAvailableScope?.id ?? candidates[0]?.id ?? "";
  }

  function selectNextAvailableRoleBindingTarget(): void {
    const currentRoleId = selectedRoleForBinding.value?.id;
    const currentRole = selectedRoleForBinding.value;
    if (currentRole?.scope_type === "department") {
      const preferredDepartment = preferredDepartmentScopeForRole(currentRole);
      if (preferredDepartment) {
        options.roleBindingForm.confirmedHighRisk = false;
        options.roleBindingForm.roleId = currentRole.id;
        options.roleBindingForm.scopeId = preferredDepartment.id;
        return;
      }
    }
    const candidate =
      availableRoleBindingCandidates.value.find((item) => item.role.id === currentRoleId) ??
      availableRoleBindingCandidates.value[0];
    options.roleBindingForm.confirmedHighRisk = false;
    if (!candidate) {
      options.roleBindingForm.roleId = "";
      options.roleBindingForm.scopeId = "";
      return;
    }
    options.roleBindingForm.roleId = candidate.role.id;
    if (candidate.role.scope_type === "department") {
      options.roleBindingForm.scopeId =
        preferredDepartmentScopeForRole(candidate.role)?.id ?? candidate.scopeId ?? "";
      return;
    }
    options.roleBindingForm.scopeId = candidate.scopeId ?? "";
  }

  function preferredDepartmentScopeForRole(
    role: AdminAssignableRoleOptionData,
  ): AdminDepartmentOptionData | null {
    if (role.scope_type !== "department") {
      return null;
    }
    const activeDepartmentIds = new Set(
      options.activeDepartments.value.map((department) => department.id),
    );
    for (const departmentId of selectedUserPreferredDepartmentIds()) {
      if (!activeDepartmentIds.has(departmentId)) {
        continue;
      }
      const bindingKey = roleBindingKeyFromParts(role.id, "department", departmentId);
      if (!selectedUserRoleBindingKeys.value.has(bindingKey)) {
        return (
          options.activeDepartments.value.find((department) => department.id === departmentId) ??
          null
        );
      }
    }
    return null;
  }

  function selectedUserPreferredDepartmentIds(): string[] {
    const departments = options.selectedUserDepartmentsForForm.value;
    const preferredIds: string[] = [];
    const primaryDepartment = departments.find((department) => department.is_primary);
    if (primaryDepartment) {
      preferredIds.push(primaryDepartment.id);
    }
    for (const department of departments) {
      if (!preferredIds.includes(department.id)) {
        preferredIds.push(department.id);
      }
    }
    return preferredIds;
  }

  return {
    assignableRoles,
    availableRoleBindingCandidates,
    canAddSelectedUserRole,
    initialAssignableRoles,
    onRoleBindingRoleChange,
    roleBindingDisabledReason,
    selectedCreateRoles,
    selectedRoleBindingKey,
    selectedRoleBindingScopeType,
    selectedRoleForBinding,
    selectedUserRoleBindingKeys,
    selectNextAvailableRoleBindingTarget,
    syncRoleBindingScopeDefault,
  };
}
