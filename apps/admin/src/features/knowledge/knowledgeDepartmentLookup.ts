import type { Ref } from "vue";

import type { AdminCurrentUserCapabilitiesData } from "@/api/auth";
import type { AdminDepartmentListItemData, AdminDepartmentOptionData } from "@/api/departments";
import type {
  AdminKnowledgeBaseData,
  AdminKnowledgeBaseListItemData,
} from "@/api/knowledgeBases";
import { formatDepartmentLabel } from "@/features/departments/departmentDisplay";

export function createKnowledgeDepartmentFormatter(options: {
  adminDepartmentOptions: Ref<AdminDepartmentOptionData[]>;
  adminDepartments: Ref<AdminDepartmentListItemData[]>;
  adminKnowledgeBases: Ref<AdminKnowledgeBaseListItemData[]>;
  currentUser: Ref<AdminCurrentUserCapabilitiesData | null>;
  selectedKnowledgeBaseDetail: Ref<AdminKnowledgeBaseData | null>;
}) {
  return function formatDepartmentById(departmentId: string | null | undefined): string {
    if (!departmentId) {
      return "-";
    }
    const knowledgeBaseOwner = options.adminKnowledgeBases.value.find(
      (item) => item.owner_department_id === departmentId,
    );
    const knowledgeBaseDefaultOwner = options.adminKnowledgeBases.value.find(
      (item) => item.default_document_owner_department_id === departmentId,
    );
    const department =
      options.adminDepartmentOptions.value.find((item) => item.id === departmentId) ??
      options.adminDepartments.value.find((item) => item.id === departmentId) ??
      options.currentUser.value?.departments.find((item) => item.id === departmentId) ??
      (options.selectedKnowledgeBaseDetail.value?.owner_department?.id === departmentId
        ? options.selectedKnowledgeBaseDetail.value.owner_department
        : null) ??
      (options.selectedKnowledgeBaseDetail.value?.default_document_owner_department?.id ===
      departmentId
        ? options.selectedKnowledgeBaseDetail.value.default_document_owner_department
        : null) ??
      (knowledgeBaseOwner?.owner_department_name
        ? { name: knowledgeBaseOwner.owner_department_name }
        : null) ??
      (knowledgeBaseDefaultOwner?.default_document_owner_department_name
        ? { name: knowledgeBaseDefaultOwner.default_document_owner_department_name }
        : null) ??
      null;
    return department ? formatDepartmentLabel(department) : "未读取到部门";
  };
}
