<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import {
  ApiRequestError,
  getSetupState,
  initializeSetup,
  validateSetupConfig,
  type SetupInitializationData,
  type SetupIssue,
  type SetupStateData,
  type SetupValidationData,
} from "@/api/client";
import {
  buildSetupPayload,
  createDefaultSetupForm,
  type SetupFormModel,
} from "@/setup/defaults";

type StringFieldKey = {
  [K in keyof SetupFormModel]: SetupFormModel[K] extends string ? K : never;
}[keyof SetupFormModel];
type NumberFieldKey = {
  [K in keyof SetupFormModel]: SetupFormModel[K] extends number ? K : never;
}[keyof SetupFormModel];
type BooleanFieldKey = {
  [K in keyof SetupFormModel]: SetupFormModel[K] extends boolean ? K : never;
}[keyof SetupFormModel];

type FieldInput = "text" | "email" | "password" | "number" | "select" | "checkbox";

type FieldOption = {
  label: string;
  value: string;
};

type FieldDefinition = {
  key: keyof SetupFormModel;
  label: string;
  input: FieldInput;
  placeholder?: string;
  min?: number;
  step?: number;
  span?: "full" | "half";
  options?: FieldOption[];
};

type FieldSection = {
  title: string;
  fields: FieldDefinition[];
};

const form = reactive<SetupFormModel>(createDefaultSetupForm());

const busy = reactive({
  refreshing: false,
  validating: false,
  submitting: false,
  copying: false,
});

const setupState = ref<SetupStateData | null>(null);
const validationResult = ref<SetupValidationData | null>(null);
const initializationResult = ref<SetupInitializationData | null>(null);
const feedback = ref<{ tone: "success" | "error" | "neutral"; message: string } | null>(null);
const submitConfirmed = ref(false);

const statusLabels: Record<string, string> = {
  not_initialized: "未初始化",
  setup_required: "等待初始化",
  validating_config: "校验中",
  testing_dependencies: "依赖测试中",
  creating_admin: "创建管理员中",
  publishing_config: "发布配置中",
  initialized: "已初始化",
  validation_failed: "校验失败",
  dependency_test_failed: "依赖测试失败",
  initialization_failed: "初始化失败",
  recovery_required: "需要恢复初始化",
  recovery_validating_config: "恢复校验中",
  recovery_publishing_config: "恢复发布中",
};

const accessSection: FieldSection = {
  title: "访问凭证",
  fields: [
    {
      key: "setupToken",
      label: "Setup Token",
      input: "password",
      placeholder: "可选，后端接入 setup JWT 后填写",
      span: "full",
    },
  ],
};

const adminSection: FieldSection = {
  title: "首个管理员",
  fields: [
    { key: "adminUsername", label: "登录名", input: "text" },
    { key: "adminDisplayName", label: "显示名", input: "text" },
    { key: "adminPassword", label: "初始密码", input: "password" },
    { key: "adminEmail", label: "邮箱", input: "email" },
    { key: "adminPhone", label: "手机号", input: "text" },
  ],
};

const organizationSection: FieldSection = {
  title: "组织初始化",
  fields: [
    { key: "enterpriseName", label: "企业名称", input: "text" },
    { key: "enterpriseCode", label: "企业编码", input: "text" },
    { key: "departmentName", label: "默认部门名称", input: "text" },
    { key: "departmentCode", label: "默认部门编码", input: "text" },
  ],
};

const infraSection: FieldSection = {
  title: "基础设施",
  fields: [
    { key: "secretProviderEndpoint", label: "Secret Provider Endpoint", input: "text", span: "full" },
    { key: "redisUrl", label: "Redis URL", input: "text", span: "full" },
    { key: "minioEndpoint", label: "MinIO Endpoint", input: "text" },
    { key: "minioBucket", label: "Bucket", input: "text" },
    { key: "minioRegion", label: "Region", input: "text" },
    { key: "objectKeyPrefix", label: "Object Prefix", input: "text" },
    { key: "minioAccessKeyRef", label: "MinIO Access Key Ref", input: "text", span: "full" },
    { key: "minioSecretKeyRef", label: "MinIO Secret Key Ref", input: "text", span: "full" },
    { key: "qdrantBaseUrl", label: "Qdrant URL", input: "text" },
    { key: "collectionPrefix", label: "Collection Prefix", input: "text" },
    {
      key: "vectorDistance",
      label: "向量距离",
      input: "select",
      options: [
        { label: "cosine", value: "cosine" },
        { label: "dot", value: "dot" },
        { label: "euclid", value: "euclid" },
      ],
    },
  ],
};

const modelSection: FieldSection = {
  title: "模型与检索",
  fields: [
    {
      key: "modelGatewayMode",
      label: "网关模式",
      input: "select",
      options: [{ label: "mock", value: "mock" }],
    },
    { key: "modelGatewayBaseUrl", label: "Model Gateway URL", input: "text", span: "full" },
    { key: "embeddingDimension", label: "Embedding 维度", input: "number", min: 1, step: 1 },
    { key: "embeddingModel", label: "Embedding 模型", input: "text" },
    { key: "rerankModel", label: "Rerank 模型", input: "text" },
    { key: "llmModel", label: "主 LLM 模型", input: "text" },
    { key: "llmFallbackModel", label: "回退 LLM 模型", input: "text" },
    { key: "keywordLanguage", label: "关键词语言", input: "text" },
    { key: "keywordAnalyzer", label: "分词器", input: "text" },
    { key: "vectorTopK", label: "向量 Top K", input: "number", min: 1, step: 1 },
    { key: "keywordTopK", label: "关键词 Top K", input: "number", min: 1, step: 1 },
    { key: "rerankInputTopK", label: "Rerank 输入 Top K", input: "number", min: 1, step: 1 },
    { key: "finalContextTopK", label: "最终上下文 Top K", input: "number", min: 1, step: 1 },
    { key: "maxContextTokens", label: "最大上下文 Token", input: "number", min: 1, step: 1 },
  ],
};

const policySection: FieldSection = {
  title: "认证与运行策略",
  fields: [
    { key: "passwordMinLength", label: "密码最小长度", input: "number", min: 8, step: 1 },
    { key: "accessTokenTtlMinutes", label: "Access Token TTL", input: "number", min: 1, step: 1 },
    { key: "refreshTokenTtlMinutes", label: "Refresh Token TTL", input: "number", min: 1, step: 1 },
    { key: "jwtIssuer", label: "JWT Issuer", input: "text" },
    { key: "jwtAudience", label: "JWT Audience", input: "text" },
    { key: "jwtSigningKeyRef", label: "JWT Signing Key Ref", input: "text", span: "full" },
    { key: "maxFileMb", label: "文件大小上限 MB", input: "number", min: 1, step: 1 },
    { key: "maxConcurrentJobs", label: "最大并发任务数", input: "number", min: 1, step: 1 },
    { key: "embeddingBatchSize", label: "Embedding Batch Size", input: "number", min: 1, step: 1 },
    { key: "indexBatchSize", label: "Index Batch Size", input: "number", min: 1, step: 1 },
    { key: "queryQpsPerUser", label: "单用户 Query QPS", input: "number", min: 1, step: 1 },
    { key: "auditRetentionDays", label: "审计保留天数", input: "number", min: 1, step: 1 },
    {
      key: "auditQueryTextMode",
      label: "查询文本记录方式",
      input: "select",
      options: [
        { label: "hash", value: "hash" },
        { label: "masked", value: "masked" },
        { label: "plain", value: "plain" },
      ],
    },
  ],
};

const cacheSection: FieldSection = {
  title: "缓存开关",
  fields: [
    { key: "queryEmbeddingEnabled", label: "查询向量缓存", input: "checkbox" },
    { key: "retrievalResultEnabled", label: "召回结果缓存", input: "checkbox" },
    { key: "finalAnswerEnabled", label: "最终答案缓存", input: "checkbox" },
    { key: "crossUserFinalAnswerAllowed", label: "允许跨用户最终答案缓存", input: "checkbox", span: "full" },
  ],
};

const sections = [
  accessSection,
  adminSection,
  organizationSection,
  infraSection,
  modelSection,
  policySection,
  cacheSection,
];

const payload = computed(() => buildSetupPayload(form));
const payloadPreview = computed(() => JSON.stringify(payload.value, null, 2));
const statusLabel = computed(() => {
  if (!setupState.value) {
    return "状态未知";
  }
  return statusLabels[setupState.value.setup_status] ?? setupState.value.setup_status;
});
const statusTone = computed(() => {
  if (!setupState.value) {
    return "neutral";
  }
  if (setupState.value.initialized) {
    return "success";
  }
  if (setupState.value.error_code || setupState.value.setup_status.includes("failed")) {
    return "error";
  }
  return "warning";
});
const canValidate = computed(() => !busy.validating && !busy.submitting);
const canSubmit = computed(() => {
  return (
    !busy.submitting &&
    !busy.validating &&
    submitConfirmed.value &&
    !(setupState.value?.initialized ?? false)
  );
});
const summaryItems = computed(() => [
  { label: "企业编码", value: form.enterpriseCode },
  { label: "默认部门", value: form.departmentCode },
  { label: "配置版本", value: "1" },
  { label: "Embedding 维度", value: String(form.embeddingDimension) },
  { label: "Model Gateway", value: form.modelGatewayBaseUrl },
  { label: "Qdrant", value: form.qdrantBaseUrl },
]);

onMounted(async () => {
  await refreshState();
});

async function refreshState(): Promise<void> {
  busy.refreshing = true;
  try {
    const response = await getSetupState(form.setupToken || undefined);
    setupState.value = response.data;
    feedback.value = null;
  } catch (error) {
    feedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取 setup 状态失败"),
    };
  } finally {
    busy.refreshing = false;
  }
}

async function runValidation(): Promise<void> {
  busy.validating = true;
  try {
    const response = await validateSetupConfig(payload.value, form.setupToken || undefined);
    validationResult.value = response.data;
    feedback.value = {
      tone: response.data.valid ? "success" : "error",
      message: response.data.valid ? "配置校验通过" : "配置校验未通过",
    };
    await refreshState();
  } catch (error) {
    validationResult.value = null;
    feedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "配置校验失败"),
    };
  } finally {
    busy.validating = false;
  }
}

async function runInitialization(): Promise<void> {
  busy.submitting = true;
  try {
    const response = await initializeSetup(payload.value, form.setupToken || undefined);
    initializationResult.value = response.data;
    feedback.value = {
      tone: "success",
      message: "初始化提交成功",
    };
    submitConfirmed.value = false;
    await refreshState();
  } catch (error) {
    initializationResult.value = null;
    feedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "初始化提交失败"),
    };
  } finally {
    busy.submitting = false;
  }
}

function resetForm(): void {
  Object.assign(form, createDefaultSetupForm());
  validationResult.value = null;
  initializationResult.value = null;
  feedback.value = {
    tone: "neutral",
    message: "已恢复本地默认初始化配置",
  };
  submitConfirmed.value = false;
}

async function copyPayload(): Promise<void> {
  busy.copying = true;
  try {
    await navigator.clipboard.writeText(payloadPreview.value);
    feedback.value = {
      tone: "success",
      message: "请求体已复制到剪贴板",
    };
  } catch {
    feedback.value = {
      tone: "error",
      message: "复制请求体失败",
    };
  } finally {
    busy.copying = false;
  }
}

function updateStringField(key: StringFieldKey, value: string): void {
  setFormValue(key, value);
}

function updateNumberField(key: NumberFieldKey, value: string): void {
  const parsed = Number(value);
  setFormValue(key, Number.isFinite(parsed) ? parsed : 0);
}

function updateBooleanField(key: BooleanFieldKey, value: boolean): void {
  setFormValue(key, value);
}

function updateFieldFromInput(field: FieldDefinition, value: string): void {
  if (field.input === "number") {
    updateNumberField(field.key as NumberFieldKey, value);
    return;
  }
  updateStringField(field.key as StringFieldKey, value);
}

function updateFieldFromSelect(field: FieldDefinition, value: string): void {
  updateStringField(field.key as StringFieldKey, value);
}

function updateFieldFromCheckbox(field: FieldDefinition, value: boolean): void {
  updateBooleanField(field.key as BooleanFieldKey, value);
}

function setFormValue<K extends keyof SetupFormModel>(key: K, value: SetupFormModel[K]): void {
  form[key] = value;
}

function toneClass(tone: "success" | "error" | "warning" | "neutral"): string {
  return `tone tone--${tone}`;
}

function normalizeIssueCode(issue: SetupIssue): string {
  return issue.error_code ?? issue.code ?? "ISSUE";
}

function normalizeErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    const code = error.payload?.error_code ? `${error.payload.error_code}: ` : "";
    return `${code}${error.payload?.message ?? error.message}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}
</script>

<template>
  <main class="shell">
    <aside class="sidebar">
      <div class="sidebar__block">
        <p class="brand">Little Bear Admin</p>
        <h1 class="title">首次初始化配置</h1>
        <p :class="toneClass(statusTone)">{{ statusLabel }}</p>
      </div>

      <div class="sidebar__block">
        <h2 class="section-title">当前摘要</h2>
        <dl class="summary">
          <div v-for="item in summaryItems" :key="item.label" class="summary__row">
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>
      </div>

      <div class="sidebar__block">
        <h2 class="section-title">接口动作</h2>
        <div class="stack">
          <button class="button button--secondary" type="button" @click="refreshState" :disabled="busy.refreshing">
            {{ busy.refreshing ? "刷新中..." : "刷新状态" }}
          </button>
          <button class="button button--secondary" type="button" @click="copyPayload" :disabled="busy.copying">
            {{ busy.copying ? "复制中..." : "复制请求体" }}
          </button>
          <button class="button button--secondary" type="button" @click="resetForm">
            恢复默认值
          </button>
        </div>
      </div>
    </aside>

    <section class="workspace">
      <header class="toolbar">
        <div>
          <p class="eyebrow">/admin</p>
          <h2>Setup Initialization Workspace</h2>
        </div>
        <div v-if="feedback" :class="['feedback', `feedback--${feedback.tone}`]">
          {{ feedback.message }}
        </div>
      </header>

      <div class="content-grid">
        <section class="editor">
          <section v-for="section in sections" :key="section.title" class="panel">
            <header class="panel__header">
              <h3>{{ section.title }}</h3>
            </header>
            <div class="form-grid">
              <label
                v-for="field in section.fields"
                :key="String(field.key)"
                class="field"
                :class="{
                  'field--full': field.span === 'full',
                  'field--checkbox': field.input === 'checkbox',
                }"
              >
                <template v-if="field.input === 'checkbox'">
                  <input
                    class="checkbox"
                    type="checkbox"
                    :checked="Boolean(form[field.key])"
                    @change="updateFieldFromCheckbox(field, ($event.target as HTMLInputElement).checked)"
                  />
                  <span>{{ field.label }}</span>
                </template>

                <template v-else>
                  <span class="field__label">{{ field.label }}</span>
                  <select
                    v-if="field.input === 'select'"
                    class="control"
                    :value="String(form[field.key])"
                    @change="updateFieldFromSelect(field, ($event.target as HTMLSelectElement).value)"
                  >
                    <option v-for="option in field.options" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                  <input
                    v-else
                    class="control"
                    :type="field.input"
                    :min="field.min"
                    :step="field.step"
                    :placeholder="field.placeholder"
                    :value="String(form[field.key] ?? '')"
                    @input="
                      updateFieldFromInput(field, ($event.target as HTMLInputElement).value)
                    "
                  />
                </template>
              </label>
            </div>
          </section>

          <section class="panel">
            <header class="panel__header">
              <h3>请求预览</h3>
            </header>
            <textarea class="preview" readonly :value="payloadPreview" />
          </section>
        </section>

        <aside class="rail">
          <section class="panel">
            <header class="panel__header">
              <h3>Setup State</h3>
            </header>
            <dl v-if="setupState" class="summary">
              <div class="summary__row">
                <dt>initialized</dt>
                <dd>{{ String(setupState.initialized) }}</dd>
              </div>
              <div class="summary__row">
                <dt>setup_status</dt>
                <dd>{{ setupState.setup_status }}</dd>
              </div>
              <div class="summary__row">
                <dt>active_config_version</dt>
                <dd>{{ setupState.active_config_version ?? "-" }}</dd>
              </div>
              <div class="summary__row">
                <dt>setup_required</dt>
                <dd>{{ String(setupState.setup_required) }}</dd>
              </div>
              <div class="summary__row">
                <dt>active_config_present</dt>
                <dd>{{ String(setupState.active_config_present) }}</dd>
              </div>
              <div class="summary__row">
                <dt>recovery_setup_allowed</dt>
                <dd>{{ String(setupState.recovery_setup_allowed) }}</dd>
              </div>
            </dl>
            <p v-else class="empty-state">尚未获取状态。</p>
          </section>

          <section class="panel">
            <header class="panel__header">
              <h3>校验结果</h3>
            </header>
            <div v-if="validationResult" class="result-block">
              <p :class="toneClass(validationResult.valid ? 'success' : 'error')">
                {{ validationResult.valid ? "valid" : "invalid" }}
              </p>
              <ul v-if="validationResult.errors.length" class="issue-list">
                <li v-for="issue in validationResult.errors" :key="`${normalizeIssueCode(issue)}-${issue.path}`">
                  <strong>{{ normalizeIssueCode(issue) }}</strong>
                  <span>{{ issue.path }}</span>
                  <p>{{ issue.message }}</p>
                </li>
              </ul>
              <ul v-if="validationResult.warnings.length" class="issue-list issue-list--warning">
                <li v-for="issue in validationResult.warnings" :key="`${normalizeIssueCode(issue)}-${issue.path}`">
                  <strong>{{ normalizeIssueCode(issue) }}</strong>
                  <span>{{ issue.path }}</span>
                  <p>{{ issue.message }}</p>
                </li>
              </ul>
            </div>
            <p v-else class="empty-state">尚未执行配置校验。</p>
          </section>

          <section class="panel">
            <header class="panel__header">
              <h3>提交结果</h3>
            </header>
            <dl v-if="initializationResult" class="summary">
              <div class="summary__row">
                <dt>initialized</dt>
                <dd>{{ String(initializationResult.initialized) }}</dd>
              </div>
              <div class="summary__row">
                <dt>active_config_version</dt>
                <dd>{{ initializationResult.active_config_version }}</dd>
              </div>
              <div class="summary__row">
                <dt>enterprise_id</dt>
                <dd class="summary__value--break">{{ initializationResult.enterprise_id }}</dd>
              </div>
              <div class="summary__row">
                <dt>admin_user_id</dt>
                <dd class="summary__value--break">{{ initializationResult.admin_user_id }}</dd>
              </div>
            </dl>
            <p v-else class="empty-state">尚未提交初始化。</p>
          </section>
        </aside>
      </div>

      <footer class="action-bar">
        <label class="confirm">
          <input v-model="submitConfirmed" type="checkbox" />
          <span>确认写入首个管理员、默认组织和 active_config v1</span>
        </label>
        <div class="action-bar__buttons">
          <button class="button button--secondary" type="button" @click="runValidation" :disabled="!canValidate">
            {{ busy.validating ? "校验中..." : "校验配置" }}
          </button>
          <button class="button" type="button" @click="runInitialization" :disabled="!canSubmit">
            {{ busy.submitting ? "提交中..." : "执行初始化" }}
          </button>
        </div>
      </footer>
    </section>
  </main>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  color: #18202a;
  background: #f3f5f7;
}

.sidebar {
  background: #20252d;
  color: #f4f6f8;
  padding: 24px 20px;
  display: grid;
  align-content: start;
  gap: 18px;
  border-right: 1px solid #303744;
}

.sidebar__block {
  display: grid;
  gap: 12px;
}

.brand {
  margin: 0;
  font-size: 12px;
  text-transform: uppercase;
  color: #98a4b5;
}

.title {
  margin: 0;
  font-size: 24px;
  line-height: 1.2;
}

.section-title {
  margin: 0;
  font-size: 14px;
  color: #d6dce5;
}

.stack {
  display: grid;
  gap: 10px;
}

.workspace {
  min-width: 0;
  padding: 24px;
  display: grid;
  gap: 20px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 16px;
}

.eyebrow {
  margin: 0 0 6px;
  font-size: 12px;
  color: #667182;
}

.toolbar h2,
.panel h3 {
  margin: 0;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 20px;
  min-height: 0;
}

.editor,
.rail {
  min-width: 0;
  display: grid;
  gap: 16px;
  align-content: start;
}

.panel {
  background: #ffffff;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  overflow: hidden;
}

.panel__header {
  padding: 16px 18px;
  border-bottom: 1px solid #e7ebf0;
  background: #fbfcfd;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 16px;
  padding: 18px;
}

.field {
  min-width: 0;
  display: grid;
  gap: 8px;
}

.field--full {
  grid-column: 1 / -1;
}

.field__label {
  font-size: 13px;
  color: #516072;
}

.field--checkbox {
  padding: 12px 14px;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #fafbfd;
  display: flex;
  align-items: center;
  gap: 10px;
}

.control,
.preview {
  width: 100%;
  border: 1px solid #cdd5df;
  border-radius: 8px;
  background: #ffffff;
  color: #18202a;
  padding: 10px 12px;
  font: inherit;
}

.control:focus,
.preview:focus {
  outline: 2px solid #8ec5b1;
  outline-offset: 1px;
  border-color: #8ec5b1;
}

.checkbox {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: #2f7d66;
}

.preview {
  min-height: 520px;
  resize: vertical;
  border: 0;
  border-top: 1px solid #e7ebf0;
  border-radius: 0;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  font-size: 12px;
  line-height: 1.5;
}

.summary {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 16px 18px 18px;
}

.summary__row {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.summary dt {
  color: #667182;
}

.summary dd {
  margin: 0;
  text-align: right;
  color: #1d2935;
}

.summary__value--break {
  word-break: break-all;
}

.issue-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 12px;
}

.issue-list li {
  padding: 12px;
  border: 1px solid #eed6d6;
  border-radius: 8px;
  background: #fff8f8;
  display: grid;
  gap: 4px;
}

.issue-list li span {
  font-size: 12px;
  color: #6c7788;
}

.issue-list li p {
  margin: 0;
}

.issue-list--warning li {
  border-color: #e8dcba;
  background: #fffaf0;
}

.result-block {
  padding: 16px 18px 18px;
  display: grid;
  gap: 14px;
}

.empty-state {
  margin: 0;
  padding: 16px 18px 18px;
  color: #6c7788;
}

.feedback {
  max-width: 420px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
}

.feedback--success {
  background: #eefaf5;
  border: 1px solid #b9e1cf;
  color: #225d4b;
}

.feedback--error {
  background: #fff5f5;
  border: 1px solid #f0c6c6;
  color: #8a3030;
}

.feedback--neutral {
  background: #f6f8fb;
  border: 1px solid #d8dee6;
  color: #445163;
}

.action-bar {
  position: sticky;
  bottom: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px 18px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #d8dee6;
  border-radius: 8px;
  backdrop-filter: blur(10px);
}

.confirm {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #445163;
}

.action-bar__buttons {
  display: flex;
  gap: 10px;
}

.button {
  appearance: none;
  border: 1px solid #2f7d66;
  border-radius: 8px;
  background: #2f7d66;
  color: #ffffff;
  font: inherit;
  padding: 10px 14px;
  cursor: pointer;
}

.button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.button--secondary {
  border-color: #cdd5df;
  background: #ffffff;
  color: #21303d;
}

.tone {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
}

.tone--success {
  background: #e9f8ef;
  color: #1f6748;
}

.tone--error {
  background: #fff0f0;
  color: #9a2f2f;
}

.tone--warning {
  background: #fff6e9;
  color: #8d5a14;
}

.tone--neutral {
  background: #eef2f5;
  color: #516072;
}

@media (max-width: 1200px) {
  .shell {
    grid-template-columns: 1fr;
  }

  .sidebar {
    border-right: 0;
    border-bottom: 1px solid #303744;
  }

  .content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .workspace {
    padding: 16px;
  }

  .toolbar,
  .action-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .field--full {
    grid-column: auto;
  }

  .summary__row {
    grid-template-columns: 1fr;
  }

  .summary dd {
    text-align: left;
  }

  .action-bar__buttons {
    width: 100%;
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
}
</style>
