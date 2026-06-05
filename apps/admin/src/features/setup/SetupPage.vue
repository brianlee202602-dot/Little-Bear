<script setup lang="ts">
import "@/styles/setup-layout.css";
import "@/styles/setup-forms.css";
import "@/styles/setup-feedback.css";
import type { SetupIssue } from "@/api/setup";
import BaseModal from "@/components/BaseModal.vue";
import SetupForm from "@/features/setup/SetupForm.vue";
import {
  bootstrapCheckHint,
  formatBootstrapCheckName,
  type BootstrapCheckIssue,
} from "@/features/setup/setupErrors";
import { formatSetupStatus } from "@/features/setup/setupStatus";
import type { SetupPageFlow } from "@/features/setup/useSetupFlow";

type Tone = "success" | "error" | "warning" | "neutral";
type SectionCheckItem = {
  title: string;
  errors: number;
  warnings: number;
  tone: Tone;
};

const props = defineProps<{
  flow: SetupPageFlow;
}>();

function toneClass(tone: Tone): string {
  return `tone tone--${tone}`;
}

function sectionToneText(item: Pick<SectionCheckItem, "errors" | "warnings">): string {
  if (item.errors > 0) {
    return `${item.errors} 错误`;
  }
  if (item.warnings > 0) {
    return `${item.warnings} 提醒`;
  }
  return "通过";
}

function issueToneText(tone: "error" | "warning"): string {
  return tone === "error" ? "错误" : "提醒";
}

function normalizeIssueCode(issue: SetupIssue): string {
  return issue.error_code ?? issue.code ?? "SETUP_ISSUE";
}

function formatBoolean(value: boolean): string {
  return value ? "是" : "否";
}

function checkRequiredText(check: Pick<BootstrapCheckIssue, "required">): string {
  return check.required ? "必需" : "可选";
}

function checkStatusText(check: Pick<BootstrapCheckIssue, "status">): string {
  if (check.status === "failed") {
    return "失败";
  }
  if (check.status === "skipped") {
    return "跳过";
  }
  return check.status;
}

</script>

<template>
  <main class="shell">
    <aside class="sidebar">
      <div class="sidebar__block">
        <p class="brand">Little Bear 管理后台</p>
        <h1 class="title">首次初始化配置</h1>
        <p :class="toneClass(props.flow.statusTone)">{{ props.flow.statusLabel }}</p>
      </div>

      <div class="sidebar__block">
        <h2 class="section-title">当前摘要</h2>
        <dl class="summary">
          <div v-for="item in props.flow.summaryItems" :key="item.label" class="summary__row">
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>
      </div>

      <div class="sidebar__block">
        <h2 class="section-title">本地核查</h2>
        <div class="check-counter">
          <span :class="toneClass(props.flow.localChecksPassed ? 'success' : 'error')">
            {{ props.flow.localChecksPassed ? "可校验" : `${props.flow.localBlockingIssues.length} 阻断` }}
          </span>
          <span :class="toneClass(props.flow.localWarningIssues.length ? 'warning' : 'neutral')">
            {{ props.flow.localWarningIssues.length }} 提醒
          </span>
        </div>
        <ul class="section-checks">
          <li v-for="item in props.flow.sectionCheckItems" :key="item.title">
            <span>{{ item.title }}</span>
            <span :class="toneClass(item.tone)">{{ sectionToneText(item) }}</span>
          </li>
        </ul>
      </div>

      <div class="sidebar__block">
        <h2 class="section-title">接口动作</h2>
        <div class="stack">
          <button class="button button--secondary" type="button" @click="props.flow.refreshState" :disabled="props.flow.busy.refreshing">
            {{ props.flow.busy.refreshing ? "刷新中..." : "刷新状态" }}
          </button>
          <button class="button button--secondary" type="button" @click="props.flow.resetForm">
            恢复默认值
          </button>
        </div>
      </div>
    </aside>

    <section class="workspace">
      <header class="toolbar">
        <div>
          <p class="eyebrow">/admin/setup-initialization</p>
          <h2>初始化配置工作台</h2>
        </div>
        <div v-if="props.flow.feedback" :class="['feedback', `feedback--${props.flow.feedback.tone}`]">
          {{ props.flow.feedback.message }}
        </div>
      </header>

      <section class="flow-strip">
        <div v-for="item in props.flow.flowItems" :key="item.label" class="flow-step">
          <span>{{ item.label }}</span>
          <strong :class="toneClass(item.tone)">{{ item.value }}</strong>
        </div>
      </section>

      <div class="content-grid">
        <section class="editor">
          <SetupForm
            :checkbox-fields-by-section="props.flow.checkboxFieldsBySection"
            :field-issues="props.flow.fieldIssues"
            :form="props.flow.form"
            :normal-fields-by-section="props.flow.normalFieldsBySection"
            :section-check-items="props.flow.sectionCheckItems"
            :sections="props.flow.sections"
            @checkbox="props.flow.updateFieldFromCheckbox"
            @input="props.flow.updateFieldFromInput"
            @select="props.flow.updateFieldFromSelect"
          />
        </section>

        <aside class="rail">
          <section class="panel">
            <header class="panel__header">
              <h3>初始化状态</h3>
            </header>
            <dl v-if="props.flow.setupState" class="summary">
              <div class="summary__row">
                <dt>是否已初始化</dt>
                <dd>{{ formatBoolean(props.flow.setupState.initialized) }}</dd>
              </div>
              <div class="summary__row">
                <dt>初始化状态</dt>
                <dd>{{ formatSetupStatus(props.flow.setupState.setup_status) }}</dd>
              </div>
              <div class="summary__row">
                <dt>当前配置版本</dt>
                <dd>{{ props.flow.setupState.active_config_version ?? "-" }}</dd>
              </div>
              <div class="summary__row">
                <dt>需要初始化</dt>
                <dd>{{ formatBoolean(props.flow.setupState.setup_required) }}</dd>
              </div>
              <div class="summary__row">
                <dt>配置是否存在</dt>
                <dd>{{ formatBoolean(props.flow.setupState.active_config_present) }}</dd>
              </div>
              <div class="summary__row">
                <dt>允许恢复初始化</dt>
                <dd>{{ formatBoolean(props.flow.setupState.recovery_setup_allowed) }}</dd>
              </div>
              <div class="summary__row">
                <dt>恢复原因</dt>
                <dd>{{ props.flow.setupState.recovery_reason ?? "-" }}</dd>
              </div>
            </dl>
            <p v-else class="empty-state">尚未获取状态。</p>
          </section>

          <section class="panel">
            <header class="panel__header">
              <h3>本地核查与后端校验</h3>
            </header>
            <div class="result-block">
              <p :class="toneClass(props.flow.localChecksPassed ? 'success' : 'error')">
                {{ props.flow.localChecksPassed ? "本地核查通过" : "本地核查未通过" }}
              </p>
              <ul v-if="props.flow.localValidationIssues.length" class="issue-list">
                <li
                  v-for="issue in props.flow.localValidationIssues"
                  :key="`${issue.section}-${issue.tone}-${issue.message}`"
                  :class="issue.tone === 'warning' ? 'issue-list__warning' : undefined"
                >
                  <strong>{{ issue.section }}</strong>
                  <span>{{ issueToneText(issue.tone) }}</span>
                  <p>{{ issue.message }}</p>
                </li>
              </ul>
            </div>
            <div v-if="props.flow.validationResult" class="result-block">
              <p :class="toneClass(props.flow.validationResult.valid ? 'success' : 'error')">
                {{ props.flow.validationResult.valid ? "后端校验通过" : "后端校验未通过" }}
              </p>
              <ul v-if="props.flow.validationResult.errors.length" class="issue-list">
                <li v-for="issue in props.flow.validationResult.errors" :key="`${normalizeIssueCode(issue)}-${issue.path}`">
                  <strong>{{ normalizeIssueCode(issue) }}</strong>
                  <span>{{ issue.path }}</span>
                  <p>{{ issue.message }}</p>
                </li>
              </ul>
              <ul v-if="props.flow.validationResult.warnings.length" class="issue-list issue-list--warning">
                <li v-for="issue in props.flow.validationResult.warnings" :key="`${normalizeIssueCode(issue)}-${issue.path}`">
                  <strong>{{ normalizeIssueCode(issue) }}</strong>
                  <span>{{ issue.path }}</span>
                  <p>{{ issue.message }}</p>
                </li>
              </ul>
            </div>
            <div v-else-if="props.flow.validationErrorPayload" class="result-block">
              <p class="tone tone--error">后端校验请求失败</p>
              <ul v-if="props.flow.validationErrorItems.length" class="issue-list">
                <li v-for="issue in props.flow.validationErrorItems" :key="`${normalizeIssueCode(issue)}-${issue.path}`">
                  <strong>{{ normalizeIssueCode(issue) }}</strong>
                  <span>{{ issue.path }}</span>
                  <p>{{ issue.message }}</p>
                </li>
              </ul>
              <p v-else class="empty-state">{{ props.flow.validationErrorPayload.message ?? "未返回可解析的校验错误明细。" }}</p>
            </div>
            <p v-else class="empty-state">尚未执行配置校验。</p>
          </section>

          <section class="panel">
            <header class="panel__header">
              <h3>提交结果</h3>
            </header>
            <dl v-if="props.flow.initializationResult" class="summary">
              <div class="summary__row">
                <dt>是否已初始化</dt>
                <dd>{{ formatBoolean(props.flow.initializationResult.initialized) }}</dd>
              </div>
              <div class="summary__row">
                <dt>当前配置版本</dt>
                <dd>{{ props.flow.initializationResult.active_config_version }}</dd>
              </div>
              <div class="summary__row">
                <dt>企业 ID</dt>
                <dd class="summary__value--break">{{ props.flow.initializationResult.enterprise_id }}</dd>
              </div>
              <div class="summary__row">
                <dt>管理员用户 ID</dt>
                <dd class="summary__value--break">{{ props.flow.initializationResult.admin_user_id }}</dd>
              </div>
            </dl>
            <div v-else-if="props.flow.initializationErrorPayload" class="result-block">
              <p class="tone tone--error">初始化提交失败</p>
              <ul v-if="props.flow.initializationFailedChecks.length" class="issue-list">
                <li v-for="check in props.flow.initializationFailedChecks" :key="check.name">
                  <strong>{{ check.name }}</strong>
                  <span>{{ check.required ? "required" : "optional" }}</span>
                  <p>{{ check.message }}</p>
                </li>
              </ul>
              <ul v-else-if="props.flow.initializationErrorItems.length" class="issue-list">
                <li v-for="issue in props.flow.initializationErrorItems" :key="`${normalizeIssueCode(issue)}-${issue.path}`">
                  <strong>{{ normalizeIssueCode(issue) }}</strong>
                  <span>{{ issue.path }}</span>
                  <p>{{ issue.message }}</p>
                </li>
              </ul>
              <dl v-else-if="props.flow.initializationDatabaseError" class="summary">
                <div class="summary__row">
                  <dt>异常类型</dt>
                  <dd>{{ props.flow.initializationDatabaseError.type ?? "-" }}</dd>
                </div>
                <div class="summary__row">
                  <dt>驱动错误</dt>
                  <dd>{{ props.flow.initializationDatabaseError.driver_type ?? "-" }}</dd>
                </div>
                <div class="summary__row">
                  <dt>错误信息</dt>
                  <dd class="summary__value--break">{{ props.flow.initializationDatabaseError.message ?? "-" }}</dd>
                </div>
                <div class="summary__row">
                  <dt>SQLSTATE</dt>
                  <dd>{{ props.flow.initializationDatabaseError.sqlstate ?? "-" }}</dd>
                </div>
                <div class="summary__row">
                  <dt>约束</dt>
                  <dd class="summary__value--break">{{ props.flow.initializationDatabaseError.constraint ?? "-" }}</dd>
                </div>
                <div class="summary__row">
                  <dt>数据表</dt>
                  <dd>{{ props.flow.initializationDatabaseError.table ?? "-" }}</dd>
                </div>
                <div class="summary__row">
                  <dt>字段</dt>
                  <dd>{{ props.flow.initializationDatabaseError.column ?? "-" }}</dd>
                </div>
              </dl>
              <p v-else class="empty-state">{{ props.flow.initializationErrorPayload.message ?? "未返回可解析的初始化错误明细。" }}</p>
            </div>
            <p v-else class="empty-state">尚未提交初始化。</p>
          </section>
        </aside>
      </div>

      <footer class="action-bar">
        <label class="confirm">
          <input
            :checked="props.flow.submitConfirmed"
            type="checkbox"
            @change="props.flow.updateSubmitConfirmed(($event.target as HTMLInputElement).checked)"
          />
          <span>{{ props.flow.submitConfirmationText }}</span>
        </label>
        <p class="gate-message">{{ props.flow.validationGateMessage }}</p>
        <div class="action-bar__buttons">
          <button class="button button--secondary" type="button" @click="props.flow.runValidation" :disabled="!props.flow.canValidate">
            {{ props.flow.busy.validating ? "校验中..." : "校验配置" }}
          </button>
          <button class="button" type="button" @click="props.flow.runInitialization" :disabled="!props.flow.canSubmit">
            {{ props.flow.submitButtonText }}
          </button>
        </div>
      </footer>
    </section>
  </main>

  <BaseModal
    :open="props.flow.initializationErrorDialogOpen"
    title="初始化提交失败"
    size="large"
    @close="props.flow.closeInitializationErrorDialog"
  >
    <section class="result-block result-block--dialog">
      <p class="tone tone--error">{{ props.flow.initializationErrorSummary }}</p>
      <dl v-if="props.flow.initializationErrorPayload" class="summary summary--compact modal-summary">
        <div class="summary__row">
          <dt>错误码</dt>
          <dd>{{ props.flow.initializationErrorPayload.error_code ?? "-" }}</dd>
        </div>
        <div class="summary__row">
          <dt>阶段</dt>
          <dd>{{ props.flow.initializationErrorPayload.stage ?? "-" }}</dd>
        </div>
        <div class="summary__row">
          <dt>请求 ID</dt>
          <dd class="summary__value--break">{{ props.flow.initializationErrorPayload.request_id ?? "-" }}</dd>
        </div>
      </dl>

      <div v-if="props.flow.initializationFailedChecks.length" class="modal-pane">
        <h4>失败检查项</h4>
        <ul class="issue-list">
          <li v-for="check in props.flow.initializationFailedChecks" :key="check.name">
            <strong>{{ formatBootstrapCheckName(check.name) }}</strong>
            <span>{{ checkRequiredText(check) }} / {{ checkStatusText(check) }} / {{ check.name }}</span>
            <p>{{ check.message }}</p>
            <p v-if="bootstrapCheckHint(check.name)" class="issue-list__hint">
              {{ bootstrapCheckHint(check.name) }}
            </p>
          </li>
        </ul>
      </div>

      <div v-else-if="props.flow.initializationErrorItems.length" class="modal-pane">
        <h4>结构化错误</h4>
        <ul class="issue-list">
          <li v-for="issue in props.flow.initializationErrorItems" :key="`${normalizeIssueCode(issue)}-${issue.path}`">
            <strong>{{ normalizeIssueCode(issue) }}</strong>
            <span>{{ issue.path }}</span>
            <p>{{ issue.message }}</p>
          </li>
        </ul>
      </div>

      <dl v-else-if="props.flow.initializationDatabaseError" class="summary summary--compact modal-summary">
        <div class="summary__row">
          <dt>异常类型</dt>
          <dd>{{ props.flow.initializationDatabaseError.type ?? "-" }}</dd>
        </div>
        <div class="summary__row">
          <dt>驱动错误</dt>
          <dd>{{ props.flow.initializationDatabaseError.driver_type ?? "-" }}</dd>
        </div>
        <div class="summary__row">
          <dt>错误信息</dt>
          <dd class="summary__value--break">{{ props.flow.initializationDatabaseError.message ?? "-" }}</dd>
        </div>
        <div class="summary__row">
          <dt>SQLSTATE</dt>
          <dd>{{ props.flow.initializationDatabaseError.sqlstate ?? "-" }}</dd>
        </div>
        <div class="summary__row">
          <dt>约束</dt>
          <dd class="summary__value--break">{{ props.flow.initializationDatabaseError.constraint ?? "-" }}</dd>
        </div>
        <div class="summary__row">
          <dt>数据表</dt>
          <dd>{{ props.flow.initializationDatabaseError.table ?? "-" }}</dd>
        </div>
        <div class="summary__row">
          <dt>字段</dt>
          <dd>{{ props.flow.initializationDatabaseError.column ?? "-" }}</dd>
        </div>
      </dl>

      <p v-else class="empty-state empty-state--plain">
        {{ props.flow.initializationErrorPayload?.message ?? "未返回可解析的初始化错误明细。" }}
      </p>
    </section>

    <template #footer>
      <button class="button button--secondary" type="button" @click="props.flow.closeInitializationErrorDialog">
        关闭
      </button>
    </template>
  </BaseModal>
</template>
