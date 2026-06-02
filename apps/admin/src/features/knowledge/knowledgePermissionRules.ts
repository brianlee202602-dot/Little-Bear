import type {
  AdminKnowledgeBaseData,
  KnowledgeBaseAccessRuleData,
} from "@/api/knowledgeBases";

export function queryDepartmentIdsForKnowledgeBase(knowledgeBase: AdminKnowledgeBaseData): string[] {
  const ids = new Set<string>();
  for (const rule of knowledgeBase.access_rules ?? []) {
    if (
      rule.subject_type === "department" &&
      (rule.permission === "query" || rule.permission === "manage")
    ) {
      ids.add(rule.subject_id);
    }
  }
  return Array.from(ids);
}

export function departmentCanQueryKnowledgeBase(
  knowledgeBase: AdminKnowledgeBaseData,
  departmentId: string,
): boolean {
  if (knowledgeBase.kb_visibility === "enterprise") {
    return true;
  }
  return queryDepartmentIdsForKnowledgeBase(knowledgeBase).includes(departmentId);
}

export function buildDepartmentKnowledgeBaseAccessRules(
  departmentIds: string[],
): KnowledgeBaseAccessRuleData[] {
  const rules: KnowledgeBaseAccessRuleData[] = [];
  for (const departmentId of new Set(departmentIds.filter(Boolean))) {
    rules.push(
      { subject_type: "department", subject_id: departmentId, permission: "discover" },
      { subject_type: "department", subject_id: departmentId, permission: "query" },
      { subject_type: "department", subject_id: departmentId, permission: "manage" },
    );
  }
  return rules;
}
