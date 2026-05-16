<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import {
  ApiRequestError,
  createSession,
  createQuery,
  deleteCurrentSession,
  getCurrentUser,
  listDocumentChunks,
  listKnowledgeBases,
  refreshSession,
  streamQuery,
  type CitationData,
  type ChunkData,
  type CurrentUserData,
  type KnowledgeBaseData,
  type QueryConfidence,
  type QueryMode,
  type QueryRequest,
  type QueryResponse,
  type QueryStreamMetadata,
  type TokenResponse,
} from "@/api/client";

type QueryStatus = "idle" | "running" | "done" | "error" | "cancelled";
type ChatRecordStatus = "running" | "done" | "error" | "cancelled";

type AuthTokenState = {
  accessToken: string;
  refreshToken: string;
  accessTokenExpiresAt: number;
};

type ChatRecord = {
  id: string;
  title: string;
  query: string;
  answer: string;
  citations: CitationData[];
  status: ChatRecordStatus;
  confidence: QueryConfidence;
  degraded: boolean;
  degradeReason: string | null;
  requestId: string;
  traceId: string;
  kbIds: string[];
  createdAt: number;
};

const AUTH_STORAGE_KEY = "little-bear.web.auth";
const KB_STORAGE_KEY = "little-bear.web.kb-ids";
const HISTORY_STORAGE_KEY = "little-bear.web.chat-history";
const TOKEN_REFRESH_SKEW_MS = 60_000;

const form = reactive({
  kbIds: "",
  query: "",
  mode: "answer" as QueryMode,
  topK: 8,
  includeSources: true,
  streaming: true,
});
const loginForm = reactive({
  username: "",
  password: "",
});

const status = ref<QueryStatus>("idle");
const currentQuestion = ref("");
const answer = ref("");
const citations = ref<CitationData[]>([]);
const metadata = ref<QueryStreamMetadata | null>(null);
const errorMessage = ref("");
const lastResponse = ref<QueryResponse | null>(null);
const abortController = ref<AbortController | null>(null);
const authTokens = ref<AuthTokenState | null>(loadStoredAuthTokens());
const currentUser = ref<CurrentUserData | null>(null);
const authFeedback = ref("");
const knowledgeBases = ref<KnowledgeBaseData[]>([]);
const sourceChunks = ref<ChunkData[]>([]);
const highlightedSourceId = ref("");
const sourceTitle = ref("");
const browserFeedback = ref("");
const sourceFeedback = ref("");
const chatRecords = ref<ChatRecord[]>(loadStoredChatRecords());
const activeRecordId = ref(chatRecords.value[0]?.id ?? "");
const authBusy = reactive({
  restoring: true,
  loggingIn: false,
  refreshing: false,
  loggingOut: false,
});
const browserBusy = reactive({
  loadingKnowledgeBases: false,
  loadingSource: false,
});

const canSubmit = computed(() => {
  return Boolean(currentUser.value && selectedKbIds.value.length && form.query.trim());
});
const authenticated = computed(() => Boolean(currentUser.value && authTokens.value?.accessToken));
const busy = computed(() => status.value === "running");
const userScopes = computed(() => currentUser.value?.scopes.join(", ") ?? "");
const selectedKbIds = computed(() => parseKbIds(form.kbIds));
const selectedKbSet = computed(() => new Set(parseKbIds(form.kbIds)));
const selectedKnowledgeBases = computed(() =>
  knowledgeBases.value.filter((kb) => selectedKbSet.value.has(kb.id)),
);
const selectedKbLabel = computed(() => {
  if (!authenticated.value) {
    return "登录后选择知识库";
  }
  if (!knowledgeBases.value.length) {
    return "暂无可查询知识库";
  }
  if (!selectedKnowledgeBases.value.length) {
    return "请选择知识库";
  }
  return `${selectedKnowledgeBases.value.length} 个知识库`;
});
const submitHint = computed(() => {
  if (!authenticated.value) {
    return "请先登录后再查询。";
  }
  if (!knowledgeBases.value.length) {
    return "当前账号暂无可查询的知识库。";
  }
  if (!selectedKbIds.value.length) {
    return "请至少选择一个知识库。";
  }
  if (!form.query.trim()) {
    return "输入问题后开始查询。";
  }
  return "";
});
const statusText = computed(() => {
  if (status.value === "running") {
    return form.streaming ? "流式生成中" : "查询中";
  }
  if (status.value === "done") {
    return metadata.value?.degraded ? "已降级完成" : "已完成";
  }
  if (status.value === "error") {
    return "查询失败";
  }
  if (status.value === "cancelled") {
    return "已取消";
  }
  return "待查询";
});
const degraded = computed(() => Boolean(metadata.value?.degraded ?? lastResponse.value?.degraded));
const degradeReason = computed(() => metadata.value?.degrade_reason ?? lastResponse.value?.degrade_reason);
const confidence = computed<QueryConfidence>(() => {
  return metadata.value?.confidence ?? lastResponse.value?.confidence ?? "low";
});
const confidenceText = computed(() => formatConfidence(confidence.value));
const traceId = computed(() => metadata.value?.trace_id ?? lastResponse.value?.trace_id ?? "");
const requestId = computed(() => metadata.value?.request_id ?? lastResponse.value?.request_id ?? "");
const activeRecord = computed(
  () => chatRecords.value.find((record) => record.id === activeRecordId.value) ?? null,
);

onMounted(async () => {
  form.kbIds = window.sessionStorage.getItem(KB_STORAGE_KEY) ?? "";
  await restoreAuthenticatedSession();
});

async function submitQuery(): Promise<void> {
  if (!canSubmit.value || busy.value) {
    return;
  }
  const queryText = form.query.trim();
  const kbIds = [...selectedKbIds.value];
  resetResult();
  currentQuestion.value = queryText;
  status.value = "running";
  window.sessionStorage.setItem(KB_STORAGE_KEY, form.kbIds.trim());
  const record = createChatRecord(queryText, kbIds);
  activeRecordId.value = record.id;
  chatRecords.value = [record, ...chatRecords.value].slice(0, 50);
  persistChatRecords();
  const payload = buildPayload(queryText, kbIds);
  form.query = "";

  try {
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      throw new Error("请先登录。");
    }
    if (form.streaming) {
      const controller = new AbortController();
      abortController.value = controller;
      await streamQuery(
        payload,
        accessToken,
        {
          onMetadata: (event) => {
            metadata.value = event;
            updateChatRecord(record.id, {
              confidence: event.confidence,
              degraded: event.degraded,
              degradeReason: event.degrade_reason,
              requestId: event.request_id,
              traceId: event.trace_id,
            });
          },
          onToken: (delta) => {
            answer.value += delta;
            updateChatRecord(record.id, { answer: answer.value }, false);
          },
          onCitation: (citation) => {
            citations.value = mergeCitation(citations.value, citation);
            updateChatRecord(record.id, { citations: citations.value }, false);
          },
          onDone: (event) => {
            metadata.value = {
              request_id: event.request_id,
              trace_id: event.trace_id,
              confidence: event.confidence,
              degraded: event.degraded,
              degrade_reason: event.degrade_reason,
            };
            citations.value = event.citations;
            updateChatRecord(record.id, {
              status: "done",
              citations: event.citations,
              confidence: event.confidence,
              degraded: event.degraded,
              degradeReason: event.degrade_reason,
              requestId: event.request_id,
              traceId: event.trace_id,
            });
          },
        },
        controller.signal,
      );
      status.value = "done";
      updateChatRecord(record.id, { status: "done", answer: answer.value, citations: citations.value });
    } else {
      const result = await createQuery(payload, accessToken);
      lastResponse.value = result;
      answer.value = result.answer;
      citations.value = result.citations;
      status.value = "done";
      updateChatRecord(record.id, {
        status: "done",
        answer: result.answer,
        citations: result.citations,
        confidence: result.confidence,
        degraded: result.degraded,
        degradeReason: result.degrade_reason,
        requestId: result.request_id,
        traceId: result.trace_id,
      });
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      status.value = "cancelled";
      updateChatRecord(record.id, { status: "cancelled" });
      return;
    }
    status.value = "error";
    errorMessage.value = readableError(error);
    updateChatRecord(record.id, {
      status: "error",
      answer: errorMessage.value,
      degraded: true,
      degradeReason: errorMessage.value,
    });
  } finally {
    abortController.value = null;
    persistChatRecords();
  }
}

async function submitLogin(): Promise<void> {
  const username = loginForm.username.trim();
  const password = loginForm.password;
  if (!username || !password) {
    authFeedback.value = "请输入用户名和密码。";
    return;
  }
  authBusy.loggingIn = true;
  authFeedback.value = "";
  try {
    const tokenResponse = await createSession({
      username,
      password,
    });
    saveAuthTokens(tokenResponse);
    const userResponse = await getCurrentUser(tokenResponse.access_token);
    currentUser.value = userResponse.data;
    loginForm.password = "";
    await refreshKnowledgeBases();
  } catch (error) {
    clearAuthSession();
    authFeedback.value = readableError(error);
  } finally {
    authBusy.loggingIn = false;
  }
}

async function restoreAuthenticatedSession(): Promise<void> {
  authBusy.restoring = true;
  try {
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      clearAuthSession();
      return;
    }
    const userResponse = await getCurrentUser(accessToken);
    currentUser.value = userResponse.data;
    await refreshKnowledgeBases();
  } catch {
    clearAuthSession();
  } finally {
    authBusy.restoring = false;
  }
}

async function ensureAccessToken(): Promise<string | null> {
  const tokenState = authTokens.value;
  if (!tokenState) {
    return null;
  }
  if (Date.now() < tokenState.accessTokenExpiresAt - TOKEN_REFRESH_SKEW_MS) {
    return tokenState.accessToken;
  }
  return refreshAccessToken();
}

async function refreshAccessToken(): Promise<string | null> {
  const tokenState = authTokens.value;
  if (!tokenState?.refreshToken) {
    return null;
  }
  authBusy.refreshing = true;
  try {
    const response = await refreshSession(tokenState.refreshToken);
    saveAuthTokens(response);
    return response.access_token;
  } catch {
    clearAuthSession();
    return null;
  } finally {
    authBusy.refreshing = false;
  }
}

async function logout(): Promise<void> {
  const accessToken = authTokens.value?.accessToken;
  authBusy.loggingOut = true;
  try {
    if (accessToken) {
      await deleteCurrentSession(accessToken);
    }
  } catch {
    // 本地退出必须可靠，后端吊销失败不能阻塞清理页面登录态。
  } finally {
    clearAuthSession();
    resetResult();
    authBusy.loggingOut = false;
  }
}

async function refreshKnowledgeBases(): Promise<void> {
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }
  browserBusy.loadingKnowledgeBases = true;
  browserFeedback.value = "";
  try {
    const response = await listKnowledgeBases(accessToken);
    knowledgeBases.value = response.data;
    reconcileSelectedKnowledgeBases(response.data);
  } catch (error) {
    browserFeedback.value = readableError(error);
  } finally {
    browserBusy.loadingKnowledgeBases = false;
  }
}

function toggleKnowledgeBase(kbId: string): void {
  const selected = selectedKbSet.value;
  if (selected.has(kbId)) {
    selected.delete(kbId);
  } else {
    selected.add(kbId);
  }
  form.kbIds = Array.from(selected).join("\n");
  window.sessionStorage.setItem(KB_STORAGE_KEY, form.kbIds.trim());
}

function selectAllKnowledgeBases(): void {
  form.kbIds = knowledgeBases.value.map((kb) => kb.id).join("\n");
  window.sessionStorage.setItem(KB_STORAGE_KEY, form.kbIds.trim());
}

function clearKnowledgeBaseSelection(): void {
  form.kbIds = "";
  window.sessionStorage.setItem(KB_STORAGE_KEY, "");
}

async function openCitationSource(citation: CitationData): Promise<void> {
  await openDocumentSource(citation.doc_id, citation.title, citation.source_id);
}

async function openDocumentSource(
  documentId: string,
  title: string,
  sourceId = "",
): Promise<void> {
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    sourceFeedback.value = "请先登录。";
    return;
  }
  browserBusy.loadingSource = true;
  sourceFeedback.value = "";
  highlightedSourceId.value = sourceId;
  sourceTitle.value = title;
  try {
    const response = await listDocumentChunks(documentId, accessToken);
    sourceChunks.value = response.data;
  } catch (error) {
    sourceChunks.value = [];
    sourceFeedback.value = readableError(error);
  } finally {
    browserBusy.loadingSource = false;
  }
}

function cancelQuery(): void {
  abortController.value?.abort();
}

function resetResult(): void {
  currentQuestion.value = "";
  answer.value = "";
  citations.value = [];
  metadata.value = null;
  lastResponse.value = null;
  errorMessage.value = "";
}

function buildPayload(queryText: string, kbIds: string[]): QueryRequest {
  return {
    kb_ids: kbIds,
    query: queryText,
    mode: form.mode,
    filters: {},
    top_k: form.topK,
    include_sources: form.includeSources,
  };
}

function reconcileSelectedKnowledgeBases(items: KnowledgeBaseData[]): void {
  if (!items.length) {
    form.kbIds = "";
    window.sessionStorage.setItem(KB_STORAGE_KEY, "");
    return;
  }
  const availableIds = new Set(items.map((item) => item.id));
  const validStoredIds = selectedKbIds.value.filter((id) => availableIds.has(id));
  const nextIds = validStoredIds.length ? validStoredIds : items.map((item) => item.id);
  form.kbIds = nextIds.join("\n");
  window.sessionStorage.setItem(KB_STORAGE_KEY, form.kbIds.trim());
}

function parseKbIds(value: string): string[] {
  return value
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function mergeCitation(current: CitationData[], citation: CitationData): CitationData[] {
  if (current.some((item) => item.source_id === citation.source_id)) {
    return current;
  }
  return [...current, citation];
}

function loadStoredAuthTokens(): AuthTokenState | null {
  try {
    const raw = window.sessionStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    if (
      typeof parsed.accessToken === "string" &&
      typeof parsed.refreshToken === "string" &&
      typeof parsed.accessTokenExpiresAt === "number"
    ) {
      return parsed;
    }
  } catch {
    window.sessionStorage.removeItem(AUTH_STORAGE_KEY);
  }
  return null;
}

function saveAuthTokens(response: TokenResponse): void {
  const tokenState: AuthTokenState = {
    accessToken: response.access_token,
    refreshToken: response.refresh_token,
    accessTokenExpiresAt: Date.now() + response.expires_in * 1000,
  };
  authTokens.value = tokenState;
  window.sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(tokenState));
}

function clearAuthSession(): void {
  authTokens.value = null;
  currentUser.value = null;
  knowledgeBases.value = [];
  sourceChunks.value = [];
  highlightedSourceId.value = "";
  sourceTitle.value = "";
  browserFeedback.value = "";
  sourceFeedback.value = "";
  chatRecords.value = [];
  activeRecordId.value = "";
  window.sessionStorage.removeItem(AUTH_STORAGE_KEY);
  window.sessionStorage.removeItem(HISTORY_STORAGE_KEY);
}

function startNewChat(): void {
  resetResult();
  status.value = "idle";
  activeRecordId.value = "";
}

function selectChatRecord(record: ChatRecord): void {
  activeRecordId.value = record.id;
  currentQuestion.value = record.query;
  answer.value = record.answer;
  citations.value = record.citations;
  errorMessage.value = record.status === "error" ? record.answer : "";
  metadata.value = {
    request_id: record.requestId,
    trace_id: record.traceId,
    confidence: record.confidence,
    degraded: record.degraded,
    degrade_reason: record.degradeReason,
  };
  lastResponse.value = null;
  status.value = record.status;
  sourceChunks.value = [];
  highlightedSourceId.value = "";
  sourceTitle.value = "";
}

function createChatRecord(query: string, kbIds: string[]): ChatRecord {
  const now = Date.now();
  return {
    id: `${now}-${Math.random().toString(16).slice(2)}`,
    title: query.length > 28 ? `${query.slice(0, 28)}...` : query,
    query,
    answer: "",
    citations: [],
    status: "running",
    confidence: "low",
    degraded: false,
    degradeReason: null,
    requestId: "",
    traceId: "",
    kbIds,
    createdAt: now,
  };
}

function updateChatRecord(
  id: string,
  patch: Partial<ChatRecord>,
  persist = true,
): void {
  chatRecords.value = chatRecords.value.map((record) =>
    record.id === id ? { ...record, ...patch } : record,
  );
  if (persist) {
    persistChatRecords();
  }
}

function persistChatRecords(): void {
  try {
    window.sessionStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(chatRecords.value));
  } catch {
    // 历史记录只是本地体验增强，写入失败不影响查询主流程。
  }
}

function loadStoredChatRecords(): ChatRecord[] {
  try {
    const raw = window.sessionStorage.getItem(HISTORY_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter(isChatRecord).slice(0, 50);
  } catch {
    window.sessionStorage.removeItem(HISTORY_STORAGE_KEY);
    return [];
  }
}

function isChatRecord(value: unknown): value is ChatRecord {
  if (!value || typeof value !== "object") {
    return false;
  }
  const item = value as Partial<ChatRecord>;
  return (
    typeof item.id === "string" &&
    typeof item.query === "string" &&
    typeof item.title === "string" &&
    Array.isArray(item.kbIds) &&
    typeof item.createdAt === "number"
  );
}

function readableError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    return error.payload?.error_code
      ? `${error.payload.error_code}: ${error.message}`
      : error.message;
  }
  return error instanceof Error ? error.message : "查询请求失败";
}

function formatConfidence(value: QueryConfidence): string {
  const labels: Record<QueryConfidence, string> = {
    low: "低",
    medium: "中",
    high: "高",
  };
  return labels[value] ?? value;
}

function formatVisibility(value: string): string {
  const labels: Record<string, string> = {
    department: "部门可见",
    enterprise: "企业可见",
  };
  return labels[value] ?? value;
}

function formatRecordTime(value: number): string {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatRecordStatus(value: ChatRecordStatus): string {
  const labels: Record<ChatRecordStatus, string> = {
    running: "生成中",
    done: "已完成",
    error: "失败",
    cancelled: "已取消",
  };
  return labels[value] ?? value;
}
</script>

<template>
  <main class="chat-shell">
    <aside class="sidebar">
      <header class="brand-row">
        <div>
          <p class="eyebrow">Little Bear</p>
          <h1>知识库助手</h1>
        </div>
        <button class="icon-button" type="button" title="新建对话" @click="startNewChat">
          +
        </button>
      </header>

      <section class="sidebar-section">
        <div class="section-title">
          <span>对话记录</span>
          <small>{{ chatRecords.length }}</small>
        </div>
        <button class="new-chat" type="button" @click="startNewChat">新对话</button>
        <div class="history-list">
          <button
            v-for="record in chatRecords"
            :key="record.id"
            :class="['history-item', { active: activeRecord?.id === record.id }]"
            type="button"
            @click="selectChatRecord(record)"
          >
            <strong>{{ record.title }}</strong>
            <span>{{ formatRecordStatus(record.status) }} · {{ formatRecordTime(record.createdAt) }}</span>
          </button>
          <p v-if="!chatRecords.length" class="muted">暂无对话记录。</p>
        </div>
      </section>

      <section class="sidebar-section knowledge-section">
        <div class="section-title">
          <span>知识库</span>
          <small>{{ selectedKbLabel }}</small>
        </div>

        <div v-if="!authenticated" class="empty-state compact">
          <strong>请先登录</strong>
          <p>登录后显示当前账号可访问的知识库。</p>
        </div>
        <template v-else>
          <div class="kb-actions">
            <button
              class="text-button"
              type="button"
              :disabled="browserBusy.loadingKnowledgeBases"
              @click="refreshKnowledgeBases"
            >
              刷新
            </button>
            <button
              class="text-button"
              type="button"
              :disabled="!knowledgeBases.length"
              @click="selectAllKnowledgeBases"
            >
              全选
            </button>
            <button
              class="text-button"
              type="button"
              :disabled="!selectedKbIds.length"
              @click="clearKnowledgeBaseSelection"
            >
              清空
            </button>
          </div>

          <div class="kb-list">
            <label v-for="kb in knowledgeBases" :key="kb.id" class="kb-item">
              <input
                type="checkbox"
                :checked="selectedKbSet.has(kb.id)"
                @change="toggleKnowledgeBase(kb.id)"
              />
              <span>
                <strong>{{ kb.name }}</strong>
                <small>{{ formatVisibility(kb.default_visibility) }}</small>
              </span>
            </label>
            <div v-if="!knowledgeBases.length" class="empty-state compact warning">
              <strong>暂无可查询知识库</strong>
              <p>当前账号没有可访问的知识库，无法发起查询。</p>
            </div>
          </div>
          <p v-if="browserFeedback" class="inline-error">{{ browserFeedback }}</p>
        </template>
      </section>

      <footer class="account-area">
        <div v-if="authenticated && currentUser" class="account-card">
          <div class="avatar">{{ (currentUser.name || currentUser.username).slice(0, 1) }}</div>
          <div>
            <strong>{{ currentUser.name || currentUser.username }}</strong>
            <span>{{ currentUser.username }}</span>
          </div>
          <button
            class="text-button"
            type="button"
            :disabled="authBusy.loggingOut"
            @click="logout"
          >
            退出
          </button>
        </div>
        <p v-if="authenticated && userScopes" class="scope-line">{{ userScopes }}</p>
      </footer>
    </aside>

    <section class="chat-panel">
      <header class="chat-topbar">
        <div>
          <span class="scope-badge">{{ selectedKbLabel }}</span>
          <strong>{{ statusText }}</strong>
        </div>
        <div class="query-options">
          <div class="segmented" aria-label="查询模式">
            <button
              type="button"
              :class="{ active: form.mode === 'answer' }"
              @click="form.mode = 'answer'"
            >
              问答
            </button>
            <button
              type="button"
              :class="{ active: form.mode === 'search' }"
              @click="form.mode = 'search'"
            >
              检索
            </button>
          </div>
          <label class="small-input">
            <span>Top K</span>
            <input v-model.number="form.topK" type="number" min="1" max="50" />
          </label>
        </div>
      </header>

      <div v-if="!authenticated" class="login-view">
        <form class="login-panel" @submit.prevent="submitLogin">
          <h2>登录后开始查询</h2>
          <p>当前查询需要你的身份和知识库权限，登录成功后左侧会显示可访问知识库。</p>
          <label class="field">
            <span>用户名</span>
            <input v-model.trim="loginForm.username" type="text" autocomplete="username" />
          </label>
          <label class="field">
            <span>密码</span>
            <input v-model="loginForm.password" type="password" autocomplete="current-password" />
          </label>
          <button
            class="primary-button"
            type="submit"
            :disabled="authBusy.loggingIn || authBusy.restoring"
          >
            {{ authBusy.loggingIn ? "登录中" : "登录" }}
          </button>
          <p v-if="authFeedback" class="inline-error">{{ authFeedback }}</p>
        </form>
      </div>

      <template v-else>
        <div class="message-scroll">
          <section v-if="!currentQuestion && !answer && !errorMessage" class="welcome">
            <h2>今天想查询什么？</h2>
            <p v-if="knowledgeBases.length">
              已选择 {{ selectedKnowledgeBases.length }} 个知识库，可以直接输入问题。
            </p>
            <p v-else>当前账号暂无可查询知识库，请联系管理员授权或创建知识库。</p>
          </section>

          <article v-if="currentQuestion" class="message message--user">
            <div class="bubble">{{ currentQuestion }}</div>
          </article>

          <article v-if="answer || errorMessage || busy" class="message message--assistant">
            <div class="assistant-avatar">LB</div>
            <div class="assistant-content">
              <div class="answer-text">
                <p v-if="answer">{{ answer }}</p>
                <p v-else-if="errorMessage" class="error-text">{{ errorMessage }}</p>
                <p v-else class="muted">正在生成回答...</p>
              </div>

              <div v-if="degradeReason || requestId || traceId" class="result-meta">
                <span :class="['pill', degraded ? 'pill--warning' : 'pill--success']">
                  {{ degraded ? "已降级" : "正常" }}
                </span>
                <span class="pill">置信度 {{ confidenceText }}</span>
                <span v-if="degradeReason" class="pill pill--warning">{{ degradeReason }}</span>
                <span v-if="requestId" class="trace">请求 {{ requestId }}</span>
                <span v-if="traceId" class="trace">追踪 {{ traceId }}</span>
              </div>

              <section v-if="citations.length" class="citation-strip">
                <button
                  v-for="citation in citations"
                  :key="citation.source_id"
                  class="citation-chip"
                  type="button"
                  @click="openCitationSource(citation)"
                >
                  <strong>{{ citation.title }}</strong>
                  <span>页 {{ citation.page_start }}-{{ citation.page_end }}</span>
                </button>
              </section>
            </div>
          </article>

          <section v-if="sourceChunks.length || sourceFeedback" class="source-panel">
            <header>
              <h2>来源内容</h2>
              <span v-if="sourceTitle">{{ sourceTitle }}</span>
            </header>
            <p v-if="sourceFeedback" class="inline-error">{{ sourceFeedback }}</p>
            <article
              v-for="chunk in sourceChunks"
              :key="chunk.id"
              :class="['source-chunk', { active: chunk.id === highlightedSourceId }]"
            >
              <header>
                <strong>{{ chunk.id }}</strong>
                <span>页 {{ chunk.page_start ?? 0 }}-{{ chunk.page_end ?? chunk.page_start ?? 0 }}</span>
              </header>
              <p>{{ chunk.text_preview }}</p>
            </article>
          </section>
        </div>

        <form class="composer" @submit.prevent="submitQuery">
          <p v-if="submitHint" class="submit-hint">{{ submitHint }}</p>
          <div class="composer-box">
            <textarea
              v-model.trim="form.query"
              rows="1"
              placeholder="有问题，尽管问"
              :disabled="!knowledgeBases.length"
              @keydown.enter.exact.prevent="submitQuery"
            />
            <div class="composer-actions">
              <label class="toggle">
                <input v-model="form.streaming" type="checkbox" />
                <span>流式</span>
              </label>
              <label class="toggle">
                <input v-model="form.includeSources" type="checkbox" />
                <span>来源</span>
              </label>
              <button v-if="busy" class="secondary-button" type="button" @click="cancelQuery">
                取消
              </button>
              <button class="send-button" type="submit" :disabled="!canSubmit || busy" title="发送">
                ↑
              </button>
            </div>
          </div>
        </form>
      </template>
    </section>
  </main>
</template>

<style scoped>
.chat-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  background: #ffffff;
  color: #171717;
}

h1,
h2,
h3,
p {
  margin: 0;
}

.sidebar {
  height: 100vh;
  position: sticky;
  top: 0;
  display: grid;
  grid-template-rows: auto minmax(150px, 1fr) minmax(180px, auto) auto;
  gap: 14px;
  border-right: 1px solid #e5e5e5;
  background: #f7f7f5;
  padding: 18px 10px 12px;
  overflow: hidden;
}

.brand-row,
.section-title,
.chat-topbar,
.account-card,
.source-panel > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.brand-row {
  padding: 0 10px;
}

.eyebrow {
  color: #737373;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
}

h1 {
  margin-top: 2px;
  font-size: 23px;
  line-height: 1.2;
}

.icon-button,
.send-button {
  width: 36px;
  height: 36px;
  border: 0;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #111111;
  color: #ffffff;
  cursor: pointer;
  font: inherit;
  font-size: 22px;
  line-height: 1;
}

.icon-button {
  border: 1px solid #d4d4d4;
  background: #ffffff;
  color: #171717;
}

.sidebar-section {
  min-height: 0;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 8px;
  padding: 0 4px;
}

.knowledge-section {
  grid-template-rows: auto auto minmax(0, auto) auto;
}

.section-title {
  min-height: 28px;
  padding: 0 6px;
  color: #171717;
  font-size: 13px;
  font-weight: 800;
}

.section-title small {
  color: #737373;
  font-size: 12px;
  font-weight: 600;
  text-align: right;
}

.new-chat,
.history-item,
.kb-item {
  width: 100%;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #171717;
  cursor: pointer;
  font: inherit;
  text-align: left;
}

.new-chat {
  min-height: 42px;
  padding: 10px 12px;
  font-weight: 700;
}

.new-chat:hover,
.history-item:hover,
.history-item.active {
  background: #ededeb;
}

.history-list,
.kb-list {
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 4px;
  overflow: auto;
  padding: 0 2px 4px;
}

.history-item {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
}

.history-item strong {
  overflow: hidden;
  font-size: 14px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-item span,
.kb-item small,
.scope-line,
.muted,
.submit-hint,
.trace {
  color: #737373;
  font-size: 12px;
}

.kb-actions {
  display: flex;
  gap: 8px;
  padding: 0 6px;
}

.text-button {
  border: 0;
  background: transparent;
  color: #404040;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  padding: 2px 0;
}

.text-button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.kb-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  padding: 9px 10px;
}

.kb-item:hover {
  background: #ededeb;
}

.kb-item input {
  margin-top: 3px;
}

.kb-item strong {
  display: block;
  overflow: hidden;
  font-size: 14px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-item small {
  display: block;
  margin-top: 3px;
}

.empty-state {
  display: grid;
  gap: 6px;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  background: #ffffff;
  padding: 14px;
}

.empty-state.compact {
  margin: 0 6px;
  padding: 12px;
}

.empty-state.warning {
  border-color: #f0d29c;
  background: #fff8e8;
}

.empty-state strong {
  font-size: 14px;
}

.empty-state p {
  color: #737373;
  font-size: 13px;
  line-height: 1.5;
}

.account-area {
  display: grid;
  gap: 8px;
  padding: 0 10px;
}

.account-card {
  min-width: 0;
  justify-content: start;
  grid-template-columns: auto minmax(0, 1fr) auto;
}

.avatar,
.assistant-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #167f67;
  color: #ffffff;
  font-size: 13px;
  font-weight: 800;
}

.account-card strong,
.account-card span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-card span {
  color: #737373;
  font-size: 12px;
}

.scope-line {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-panel {
  min-height: 100vh;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  background: #ffffff;
}

.chat-topbar {
  min-height: 64px;
  border-bottom: 1px solid #eeeeee;
  padding: 12px 24px;
}

.chat-topbar > div:first-child {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.scope-badge {
  color: #737373;
  font-size: 13px;
}

.chat-topbar strong {
  font-size: 15px;
}

.query-options {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.segmented {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border: 1px solid #dedede;
  border-radius: 8px;
  overflow: hidden;
}

.segmented button {
  min-width: 64px;
  border: 0;
  border-right: 1px solid #dedede;
  background: #ffffff;
  color: #525252;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  padding: 8px 12px;
}

.segmented button:last-child {
  border-right: 0;
}

.segmented button.active {
  background: #111111;
  color: #ffffff;
}

.small-input {
  display: inline-grid;
  grid-template-columns: auto 64px;
  align-items: center;
  gap: 6px;
  color: #737373;
  font-size: 12px;
  font-weight: 700;
}

.small-input input {
  height: 36px;
}

.login-view,
.message-scroll {
  min-height: 0;
  overflow: auto;
}

.login-view {
  display: grid;
  place-items: center;
  padding: 32px;
}

.login-panel {
  width: min(420px, 100%);
  display: grid;
  gap: 14px;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  padding: 24px;
}

.login-panel h2,
.welcome h2 {
  font-size: 28px;
  line-height: 1.2;
}

.login-panel p,
.welcome p {
  color: #666666;
  line-height: 1.6;
}

.field {
  display: grid;
  gap: 7px;
}

.field span {
  color: #525252;
  font-size: 13px;
  font-weight: 700;
}

input[type="text"],
input[type="password"],
input[type="number"],
textarea {
  width: 100%;
  border: 1px solid #d4d4d4;
  border-radius: 8px;
  background: #ffffff;
  color: #171717;
  font: inherit;
  line-height: 1.5;
  outline: none;
}

input[type="text"],
input[type="password"],
input[type="number"] {
  padding: 9px 11px;
}

textarea {
  min-height: 42px;
  max-height: 180px;
  resize: vertical;
  padding: 11px 13px;
}

input:focus,
textarea:focus {
  border-color: #9ca3af;
  box-shadow: 0 0 0 3px rgba(17, 17, 17, 0.08);
}

.primary-button,
.secondary-button {
  min-height: 40px;
  border: 1px solid #111111;
  border-radius: 8px;
  background: #111111;
  color: #ffffff;
  cursor: pointer;
  font: inherit;
  font-weight: 800;
  padding: 8px 14px;
}

.secondary-button {
  border-color: #d4d4d4;
  background: #ffffff;
  color: #171717;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.inline-error {
  border: 1px solid #f0b6aa;
  border-radius: 8px;
  background: #fff1ee;
  color: #8f2f22;
  font-size: 13px;
  line-height: 1.5;
  padding: 9px 11px;
}

.message-scroll {
  display: grid;
  align-content: start;
  gap: 24px;
  padding: 48px clamp(20px, 7vw, 96px) 28px;
}

.welcome {
  min-height: 42vh;
  display: grid;
  place-content: center;
  gap: 12px;
  text-align: center;
}

.message {
  display: flex;
  gap: 14px;
}

.message--user {
  justify-content: flex-end;
}

.bubble {
  max-width: min(720px, 82%);
  border-radius: 18px;
  background: #f3f3f3;
  padding: 12px 16px;
  line-height: 1.65;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.message--assistant {
  max-width: 920px;
}

.assistant-avatar {
  flex: 0 0 auto;
  margin-top: 4px;
  background: #111111;
}

.assistant-content {
  min-width: 0;
  display: grid;
  gap: 14px;
}

.answer-text {
  line-height: 1.78;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.error-text {
  color: #8f2f22;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.pill {
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  border: 1px solid #d4d4d4;
  border-radius: 999px;
  background: #ffffff;
  color: #525252;
  font-size: 12px;
  padding: 5px 10px;
}

.pill--success {
  border-color: #a8d5c4;
  background: #eefaf5;
  color: #116149;
}

.pill--warning {
  border-color: #f0d29c;
  background: #fff8e8;
  color: #8a5a00;
}

.citation-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.citation-chip {
  max-width: 280px;
  border: 1px solid #dcdcdc;
  border-radius: 8px;
  background: #ffffff;
  color: #171717;
  cursor: pointer;
  display: grid;
  gap: 3px;
  font: inherit;
  padding: 9px 11px;
  text-align: left;
}

.citation-chip:hover {
  background: #f7f7f7;
}

.citation-chip strong {
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.citation-chip span {
  color: #737373;
  font-size: 12px;
}

.source-panel {
  max-width: 920px;
  display: grid;
  gap: 10px;
  border-top: 1px solid #eeeeee;
  padding-top: 16px;
}

.source-panel h2 {
  font-size: 16px;
}

.source-panel > header span {
  color: #737373;
  font-size: 13px;
}

.source-chunk {
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  background: #ffffff;
  padding: 12px;
}

.source-chunk.active {
  border-color: #f0d29c;
  background: #fff8e8;
}

.source-chunk header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.source-chunk strong {
  color: #525252;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.source-chunk span {
  color: #737373;
  font-size: 12px;
  white-space: nowrap;
}

.source-chunk p {
  line-height: 1.65;
  overflow-wrap: anywhere;
}

.composer {
  padding: 12px clamp(20px, 7vw, 96px) 24px;
}

.submit-hint {
  max-width: 900px;
  margin: 0 auto 8px;
  text-align: center;
}

.composer-box {
  max-width: 900px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 10px;
  border: 1px solid #d4d4d4;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.08);
  padding: 9px 10px 9px 14px;
}

.composer-box textarea {
  min-height: 44px;
  border: 0;
  box-shadow: none;
  padding: 10px 0;
}

.composer-box textarea:focus {
  box-shadow: none;
}

.composer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toggle {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #525252;
  font-size: 12px;
  font-weight: 700;
}

@media (max-width: 920px) {
  .chat-shell {
    grid-template-columns: 1fr;
  }

  .sidebar {
    height: auto;
    position: static;
    grid-template-rows: auto auto auto auto;
    border-right: 0;
    border-bottom: 1px solid #e5e5e5;
  }

  .history-list,
  .kb-list {
    max-height: 220px;
  }

  .chat-topbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .query-options {
    justify-content: flex-start;
  }
}

@media (max-width: 560px) {
  .message-scroll,
  .composer {
    padding-left: 14px;
    padding-right: 14px;
  }

  .composer-box {
    grid-template-columns: 1fr;
    border-radius: 18px;
  }

  .composer-actions {
    justify-content: space-between;
  }

  .toggle {
    display: none;
  }

  .bubble {
    max-width: 94%;
  }
}
</style>
