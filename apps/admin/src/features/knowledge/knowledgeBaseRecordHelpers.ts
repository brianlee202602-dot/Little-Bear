import type {
  AdminKnowledgeBaseData,
  AdminKnowledgeBaseListItemData,
  AdminKnowledgeBaseOptionData,
} from "@/api/knowledgeBases";

export function knowledgeBaseListItemFromDetail(
  knowledgeBase: AdminKnowledgeBaseData,
): AdminKnowledgeBaseListItemData {
  return {
    id: knowledgeBase.id,
    name: knowledgeBase.name,
    status: knowledgeBase.status,
    owner_department_id: knowledgeBase.owner_department_id,
    owner_department_name: knowledgeBase.owner_department?.name ?? null,
    kb_visibility: knowledgeBase.kb_visibility,
    default_document_visibility: knowledgeBase.default_document_visibility,
    default_document_owner_department_id: knowledgeBase.default_document_owner_department_id,
    default_document_owner_department_name:
      knowledgeBase.default_document_owner_department?.name ?? null,
  };
}

export function knowledgeBaseOptionFromDetail(
  knowledgeBase: AdminKnowledgeBaseData,
): AdminKnowledgeBaseOptionData {
  return {
    id: knowledgeBase.id,
    name: knowledgeBase.name,
    status: knowledgeBase.status,
  };
}
