import type { PaginationData } from "./commonTypes";
import type { AdminDepartmentData } from "./departmentsTypes";

export interface AdminKnowledgeBaseData {
  id: string;
  name: string;
  status: "active" | "disabled" | "archived";
  owner_department_id: string;
  owner_department: AdminDepartmentData | null;
  kb_visibility: "enterprise" | "department_acl" | "private";
  default_document_visibility: "department" | "enterprise";
  default_document_owner_department_id: string;
  default_document_owner_department: AdminDepartmentData | null;
  access_rules: KnowledgeBaseAccessRuleData[];
  config_scope_id: string | null;
  policy_version: number;
}

export interface AdminKnowledgeBaseListItemData {
  id: string;
  name: string;
  status: "active" | "disabled" | "archived";
  owner_department_id: string;
  owner_department_name: string | null;
  kb_visibility: "enterprise" | "department_acl" | "private";
  default_document_visibility: "department" | "enterprise";
  default_document_owner_department_id: string;
  default_document_owner_department_name: string | null;
}

export interface AdminKnowledgeBaseOptionData {
  id: string;
  name: string;
  status: "active" | "disabled" | "archived";
}

export interface KnowledgeBaseAccessRuleData {
  subject_type: "department" | "user" | "role";
  subject_id: string;
  permission: "discover" | "query" | "manage";
}

export interface AdminKnowledgeBaseCreateRequest {
  name: string;
  owner_department_id: string;
  kb_visibility: "enterprise" | "department_acl" | "private";
  default_document_visibility: "department" | "enterprise";
  default_document_owner_department_id?: string | null;
  access_rules?: KnowledgeBaseAccessRuleData[];
  config_scope_id?: string | null;
}

export interface AdminKnowledgeBasePatchRequest {
  name?: string;
  status?: "active" | "disabled" | "archived";
  kb_visibility?: "enterprise" | "department_acl" | "private";
  default_document_visibility?: "department" | "enterprise";
  default_document_owner_department_id?: string | null;
  config_scope_id?: string | null;
}

export interface AdminKnowledgeBaseListResponse {
  request_id: string;
  data: AdminKnowledgeBaseListItemData[];
  pagination: PaginationData;
}

export interface AdminKnowledgeBaseOptionListResponse {
  request_id: string;
  data: AdminKnowledgeBaseOptionData[];
  pagination: PaginationData;
}

export interface AdminKnowledgeBaseResponse {
  request_id: string;
  data: AdminKnowledgeBaseData;
}

export interface KnowledgeBasePermissionPutRequest {
  kb_visibility: "enterprise" | "department_acl" | "private";
  default_document_visibility: "department" | "enterprise";
  default_document_owner_department_id: string;
  access_rules: KnowledgeBaseAccessRuleData[];
}

export interface KnowledgeBasePermissionPolicyResponse {
  request_id: string;
  data: {
    resource_type: "knowledge_base";
    resource_id: string;
    kb_visibility: "enterprise" | "department_acl" | "private";
    default_document_visibility: "department" | "enterprise";
    default_document_owner_department_id: string;
    access_rules: KnowledgeBaseAccessRuleData[];
    permission_version: number;
  };
}
