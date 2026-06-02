export type DepartmentDisplayLike = {
  code?: string | null;
  name?: string | null;
};

export function formatDepartmentLabel(
  department: DepartmentDisplayLike | null | undefined,
): string {
  if (!department) {
    return "-";
  }
  const name = department.name?.trim();
  const code = department.code?.trim();
  if (name) {
    return name;
  }
  return code ? "未命名部门" : "-";
}

export function formatDepartmentList(departments: DepartmentDisplayLike[]): string {
  const labels = departments
    .map((department) => formatDepartmentLabel(department))
    .filter((label) => label !== "-");
  return labels.length ? labels.join(" / ") : "-";
}
