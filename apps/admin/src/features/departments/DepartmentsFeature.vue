<script setup lang="ts">
import { onMounted } from "vue";

import { useAdminCapabilityProvider } from "@/app/providers/adminCapabilityProvider";
import { useAdminEventBus } from "@/app/providers/adminEventBus";
import { useAdminSessionProvider } from "@/app/providers/adminSessionProvider";
import DepartmentFormModal from "@/features/departments/DepartmentFormModal.vue";
import { formatDepartmentLabel } from "@/features/departments/departmentDisplay";
import DepartmentListPage from "@/features/departments/DepartmentListPage.vue";
import { useDepartmentAdminRuntime } from "@/features/departments/useDepartmentAdminRuntime";
import { normalizeErrorMessage } from "@/utils/errors";
import {
  changePaginationPage,
  changePaginationPageSize,
  refreshFirstPage,
} from "@/utils/pagination";

const pageSizeOptions = [10, 20, 50, 100, 200];
const selectorPageSize = 20;
const capabilities = useAdminCapabilityProvider();
const session = useAdminSessionProvider();
const eventBus = useAdminEventBus();

const runtime = useDepartmentAdminRuntime({
  canLoadDepartmentAdmin: capabilities.canLoadDepartmentAdmin,
  canManageDepartments: capabilities.canManageDepartments,
  canReadDepartments: capabilities.canReadDepartments,
  ensureAccessToken: session.ensureAccessToken,
  getOptionKeyword: () => "",
  getPinnedDepartments: () => session.currentUser.value?.departments ?? [],
  normalizeErrorMessage,
  onDepartmentOptionsChanged: () => {
    eventBus.emit({ type: "department.changed" });
  },
  selectorPageSize,
});

function searchDepartments(): void {
  void refreshFirstPage(runtime.departmentPagination, runtime.refreshDepartmentAdminState);
}

function updatePage(page: number): void {
  void changePaginationPage(runtime.departmentPagination, runtime.refreshDepartmentAdminState, page);
}

function updatePageSize(pageSize: number): void {
  void changePaginationPageSize(
    runtime.departmentPagination,
    runtime.refreshDepartmentAdminState,
    pageSize,
  );
}

async function submitCreateDepartment(): Promise<void> {
  await runtime.submitCreateDepartment();
  eventBus.emit({ type: "department.changed" });
}

async function submitPatchDepartment(): Promise<void> {
  await runtime.submitPatchDepartment();
  eventBus.emit({ type: "department.changed", departmentId: runtime.selectedDepartmentId.value });
}

async function deleteSelectedDepartment(): Promise<void> {
  const departmentId = runtime.selectedDepartmentId.value || undefined;
  await runtime.deleteSelectedDepartment();
  eventBus.emit({ type: "department.changed", departmentId });
}

onMounted(() => {
  void runtime.refreshDepartmentAdminState();
});
</script>

<template>
  <DepartmentListPage
    :busy="runtime.departmentAdminBusy"
    :can-load-department-admin="capabilities.canLoadDepartmentAdmin.value"
    :can-manage-departments="capabilities.canManageDepartments.value"
    :can-read-departments="capabilities.canReadDepartments.value"
    :departments="runtime.adminDepartments.value"
    :feedback="runtime.departmentAdminFeedback.value"
    :page-size-options="pageSizeOptions"
    :pagination="runtime.departmentPagination"
    :search-form="runtime.departmentSearchForm"
    @create="runtime.openCreateDepartmentModal"
    @delete="runtime.openDeleteDepartmentModal"
    @edit="runtime.openEditDepartmentModal"
    @refresh="runtime.refreshDepartmentAdminState"
    @search="searchDepartments"
    @update:keyword="(value) => (runtime.departmentSearchForm.keyword = value)"
    @update:page="updatePage"
    @update:page-size="updatePageSize"
    @update:status="(value) => (runtime.departmentSearchForm.status = value)"
  />

  <DepartmentFormModal
    :busy="runtime.departmentAdminBusy"
    :can-create="runtime.canCreateDepartment.value"
    :can-delete="runtime.canDeleteSelectedDepartment.value"
    :can-update="runtime.canUpdateSelectedDepartment.value"
    :create-form="runtime.departmentCreateForm"
    :danger-form="runtime.departmentDangerForm"
    :edit-form="runtime.departmentEditForm"
    :feedback="runtime.departmentAdminFeedback.value"
    :format-department-label="formatDepartmentLabel"
    :mode="runtime.departmentModalMode.value"
    :selected-department="runtime.selectedDepartment.value"
    @close="runtime.closeDepartmentModal"
    @create="submitCreateDepartment"
    @delete="deleteSelectedDepartment"
    @update="submitPatchDepartment"
    @update:confirmed-delete="(value) => (runtime.departmentDangerForm.confirmedDelete = value)"
    @update:create-code="(value) => (runtime.departmentCreateForm.code = value)"
    @update:create-name="(value) => (runtime.departmentCreateForm.name = value)"
    @update:edit-name="(value) => (runtime.departmentEditForm.name = value)"
    @update:edit-status="(value) => (runtime.departmentEditForm.status = value)"
  />
</template>
