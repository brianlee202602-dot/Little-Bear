export interface UseKnowledgeBaseAccessSelectionDependencies {
  knowledgeBaseCreateForm: {
    accessDepartmentIds: string[];
  };
  knowledgeBasePermissionForm: {
    accessDepartmentIds: string[];
  };
}

export function useKnowledgeBaseAccessSelection(
  options: UseKnowledgeBaseAccessSelectionDependencies,
) {
  const { knowledgeBaseCreateForm, knowledgeBasePermissionForm } = options;

  function toggleKnowledgeBaseCreateAccessDepartment(
    departmentId: string,
    checked: boolean,
  ): void {
    const next = new Set(knowledgeBaseCreateForm.accessDepartmentIds);
    if (checked) {
      next.add(departmentId);
    } else {
      next.delete(departmentId);
    }
    knowledgeBaseCreateForm.accessDepartmentIds = Array.from(next);
  }

  function onKnowledgeBaseCreateAccessDepartmentChange(
    departmentId: string,
    event: Event,
  ): void {
    toggleKnowledgeBaseCreateAccessDepartment(
      departmentId,
      (event.target as HTMLInputElement | null)?.checked ?? false,
    );
  }

  function toggleKnowledgeBasePermissionAccessDepartment(
    departmentId: string,
    checked: boolean,
  ): void {
    const next = new Set(knowledgeBasePermissionForm.accessDepartmentIds);
    if (checked) {
      next.add(departmentId);
    } else {
      next.delete(departmentId);
    }
    knowledgeBasePermissionForm.accessDepartmentIds = Array.from(next);
  }

  function onKnowledgeBasePermissionAccessDepartmentChange(
    departmentId: string,
    event: Event,
  ): void {
    toggleKnowledgeBasePermissionAccessDepartment(
      departmentId,
      (event.target as HTMLInputElement | null)?.checked ?? false,
    );
  }

  return {
    onKnowledgeBaseCreateAccessDepartmentChange,
    onKnowledgeBasePermissionAccessDepartmentChange,
  };
}
