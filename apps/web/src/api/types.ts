export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: "Bearer";
  expires_in: number;
}

export interface CurrentUserData {
  id: string;
  username: string;
  name: string;
  status: string;
}

export interface CurrentUserResponse {
  request_id: string;
  data: CurrentUserData;
}

export interface PaginationData {
  page: number;
  page_size: number;
  total: number;
}

export interface KnowledgeBaseData {
  id: string;
  name: string;
  status: "active" | "disabled" | "archived";
}

export interface KnowledgeBaseListResponse {
  request_id: string;
  data: KnowledgeBaseData[];
  pagination: PaginationData;
}

export interface DocumentListResponse {
  request_id: string;
  data: DocumentListItemData[];
  pagination: PaginationData;
}

export interface DocumentListItemData {
  id: string;
  title: string;
  lifecycle_status: string;
  index_status: string;
  updated_at: string | null;
  can_view: boolean;
  can_cite: boolean;
}

export interface DocumentVersionData {
  id: string;
  document_id: string;
  version_no: number;
  status: string;
}

export interface DocumentVersionListResponse {
  request_id: string;
  data: DocumentVersionData[];
  pagination: PaginationData;
}

export interface ChunkData {
  id: string;
  document_id: string;
  document_version_id: string;
  text_preview: string;
  page_start: number | null;
  page_end: number | null;
  status: string;
  ordinal: number;
}

export interface ChunkListResponse {
  request_id: string;
  data: ChunkData[];
  pagination: PaginationData;
}

export interface CitationSourceData {
  source_id: string;
  doc_id: string;
  document_version_id: string;
  title: string;
  text: string;
  text_preview: string;
  page_start: number | null;
  page_end: number | null;
  ordinal: number;
  heading_path: string | null;
  source_offsets: Record<string, unknown> | null;
  text_status: "object" | "preview_only" | "object_unavailable";
}

export interface CitationSourceResponse {
  request_id: string;
  data: CitationSourceData;
}

export type QueryMode = "answer" | "search";
export type QueryConfidence = "low" | "medium" | "high";

export interface QueryHistoryMessage {
  role: "user" | "assistant";
  content: string;
}

export interface QueryRequest {
  kb_ids: string[];
  query: string;
  conversation_id?: string | null;
  history?: QueryHistoryMessage[];
  mode: QueryMode;
  filters: Record<string, unknown>;
  top_k: number;
  include_sources: boolean;
}

export interface CitationData {
  source_id: string;
  doc_id: string;
  document_version_id: string;
  title: string;
  page_start: number;
  page_end: number;
  score: number;
}

export interface QueryResponse {
  debug_id: string;
  conversation_id: string | null;
  message_id: string | null;
  answer: string;
  citations: CitationData[];
  confidence: QueryConfidence;
  degraded: boolean;
  degrade_reason: string | null;
}

export type QueryStreamMetadata = Pick<
  QueryResponse,
  | "debug_id"
  | "conversation_id"
  | "message_id"
  | "confidence"
  | "degraded"
  | "degrade_reason"
> & {
  streaming?: boolean;
};

export type QueryStreamDone = QueryResponse;

export interface QueryStreamHandlers {
  onMetadata?: (metadata: QueryStreamMetadata) => void;
  onToken?: (delta: string) => void;
  onCitation?: (citation: CitationData) => void;
  onDone?: (result: QueryStreamDone) => void;
}

export interface QueryConversationData {
  id: string;
  title: string;
  status: "active" | "deleted";
  kb_ids: string[];
  last_message_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface QueryMessageData {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  status: "running" | "done" | "error" | "cancelled";
  citations: CitationData[];
  confidence: QueryConfidence | null;
  degraded: boolean;
  degrade_reason: string | null;
  debug_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface QueryConversationListResponse {
  request_id: string;
  data: QueryConversationData[];
  pagination: PaginationData;
}

export interface QueryConversationResponse {
  request_id: string;
  data: QueryConversationData;
  messages: QueryMessageData[];
  messages_pagination: PaginationData;
}
