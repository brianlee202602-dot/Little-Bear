import type { AdminDepartmentOptionData } from "@/api/departments";

export type DepartmentLike = {
  id: string;
  name: string;
  status: string;
  is_default?: boolean | null;
};

export function uniqueById<T extends { id: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  const result: T[] = [];
  for (const item of items) {
    if (seen.has(item.id)) {
      continue;
    }
    seen.add(item.id);
    result.push(item);
  }
  return result;
}

export function departmentOptionFromDepartment(
  department: DepartmentLike | null | undefined,
): AdminDepartmentOptionData | null {
  if (!department) {
    return null;
  }
  return {
    id: department.id,
    name: department.name,
    status: department.status,
    is_default: "is_default" in department ? Boolean(department.is_default) : false,
  };
}

export function mergeDepartmentOptions(
  incomingOptions: AdminDepartmentOptionData[],
  pinnedDepartments: Array<DepartmentLike | null | undefined>,
): AdminDepartmentOptionData[] {
  const pinned = pinnedDepartments
    .map(departmentOptionFromDepartment)
    .filter((department): department is AdminDepartmentOptionData => Boolean(department));
  return uniqueById([...incomingOptions, ...pinned]);
}
