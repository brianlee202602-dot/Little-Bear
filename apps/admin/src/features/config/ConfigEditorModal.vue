<script setup lang="ts">
import type { ConfigVersionData, SetupIssue, SetupValidationData } from "@/api/config";
import type { ConfigSectionFormDefinition } from "@/features/config/configFields";
import { configCheckboxFields, configNormalFields } from "@/features/config/configFields";
import type { FieldDefinition } from "@/features/setup/setupFields";
import type { SetupFormModel } from "@/features/setup/setupModel";
import { formatDateTime } from "@/utils/date";
import { formatStatusText } from "@/utils/display";

type ConfigModalMode = "create" | "edit";
type Feedback = {
  tone: "success" | "error" | "neutral";
  message: string;
};

const props = defineProps<{
  activeConfigVersion: number;
  activeVersionRecord: ConfigVersionData | null;
  canSave: boolean;
  canValidate: boolean;
  configForm: SetupFormModel;
  feedback: Feedback | null;
  mode: ConfigModalMode;
  parseError: string | null;
  saving: boolean;
  sections: ConfigSectionFormDefinition[];
  selectedVersionRecord: ConfigVersionData | null;
  title: string;
  validating: boolean;
  validationResult: SetupValidationData | null;
}>();

const emit = defineEmits<{
  (event: "checkbox", field: FieldDefinition, value: boolean): void;
  (event: "close"): void;
  (event: "input", field: FieldDefinition, value: string): void;
  (event: "save"): void;
  (event: "select", field: FieldDefinition, value: string): void;
  (event: "validate"): void;
}>();

function issueCode(issue: SetupIssue): string {
  return issue.error_code ?? issue.code ?? "CONFIG_ISSUE";
}
</script>

<template>
  <div class="modal-backdrop" role="presentation" @click.self="emit('close')">
    <section class="modal modal--wide" role="dialog" aria-modal="true" aria-labelledby="config-modal-title">
      <header class="modal__header">
        <div>
          <p class="eyebrow">配置管理</p>
          <h3 id="config-modal-title">{{ props.title }}</h3>
        </div>
        <button class="button button--secondary button--small" type="button" @click="emit('close')">
          关闭
        </button>
      </header>

      <form @submit.prevent="emit('save')">
        <div class="modal__body">
          <div v-if="props.feedback" :class="['feedback feedback--wide', `feedback--${props.feedback.tone}`]">
            {{ props.feedback.message }}
          </div>
          <dl class="summary summary--compact modal-summary">
            <div class="summary__row">
              <dt>{{ props.mode === "create" ? "基线版本" : "编辑版本" }}</dt>
              <dd>
                {{
                  props.mode === "create"
                    ? `当前 active_config v${props.activeConfigVersion}`
                    : `v${props.selectedVersionRecord?.version ?? "-"} / ${formatStatusText(props.selectedVersionRecord?.status)}`
                }}
              </dd>
            </div>
            <div class="summary__row">
              <dt>创建时间</dt>
              <dd>
                {{
                  props.mode === "create"
                    ? formatDateTime(props.activeVersionRecord?.created_at ?? null)
                    : formatDateTime(props.selectedVersionRecord?.created_at ?? null)
                }}
              </dd>
            </div>
            <div class="summary__row">
              <dt>更新时间</dt>
              <dd>
                {{
                  props.mode === "create"
                    ? formatDateTime(props.activeVersionRecord?.updated_at ?? null)
                    : formatDateTime(props.selectedVersionRecord?.updated_at ?? null)
                }}
              </dd>
            </div>
          </dl>
          <div class="config-form-sections">
            <section
              v-for="section in props.sections"
              :key="`config-form-${section.key}`"
              class="config-form-section"
            >
              <header>
                <div>
                  <h4>{{ section.label }}</h4>
                  <p>{{ section.description }}</p>
                </div>
                <span>{{ section.key }}</span>
              </header>
              <div class="form-grid form-grid--compact form-grid--modal">
                <label
                  v-for="field in configNormalFields(section)"
                  :key="`config-field-${String(field.key)}`"
                  class="field"
                  :class="{ 'field--full': field.span === 'full' }"
                >
                  <span class="field__label">
                    {{ field.label }}
                    <span v-if="field.required" class="required-mark">必填</span>
                  </span>
                  <p class="field__hint" :class="{ 'field__hint--empty': !field.hint }" :aria-hidden="!field.hint">
                    {{ field.hint }}
                  </p>
                  <select
                    v-if="field.input === 'select'"
                    class="control"
                    :value="String(props.configForm[field.key])"
                    @change="emit('select', field, ($event.target as HTMLSelectElement).value)"
                  >
                    <option v-for="option in field.options ?? []" :key="option.value" :value="option.value">
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
                    :value="String(props.configForm[field.key] ?? '')"
                    @input="emit('input', field, ($event.target as HTMLInputElement).value)"
                  />
                </label>
              </div>
              <div v-if="configCheckboxFields(section).length" class="checkbox-grid">
                <label
                  v-for="field in configCheckboxFields(section)"
                  :key="`config-field-${String(field.key)}`"
                  class="field field--checkbox"
                >
                  <input
                    class="checkbox"
                    type="checkbox"
                    :checked="Boolean(props.configForm[field.key])"
                    @change="emit('checkbox', field, ($event.target as HTMLInputElement).checked)"
                  />
                  <span>{{ field.label }}</span>
                  <p class="field__hint" :class="{ 'field__hint--empty': !field.hint }" :aria-hidden="!field.hint">
                    {{ field.hint }}
                  </p>
                </label>
              </div>
            </section>
          </div>
          <p v-if="props.parseError" class="field-issue field-issue--error">
            {{ props.parseError }}
          </p>
          <div class="config-actions">
            <button
              class="button button--secondary"
              type="button"
              @click="emit('validate')"
              :disabled="!props.canValidate"
            >
              {{ props.validating ? "校验中..." : "校验配置" }}
            </button>
            <button class="button" type="submit" :disabled="!props.canSave">
              {{ props.saving ? "保存中..." : "保存配置" }}
            </button>
          </div>
          <div v-if="props.validationResult" class="result-block result-block--compact">
            <p :class="props.validationResult.valid ? 'tone tone--success' : 'tone tone--error'">
              {{ props.validationResult.valid ? "后端校验通过" : "后端校验未通过" }}
            </p>
            <ul v-if="props.validationResult.errors.length" class="issue-list">
              <li
                v-for="issue in props.validationResult.errors"
                :key="`${issue.error_code ?? issue.code}-${issue.path}`"
              >
                <strong>{{ issueCode(issue) }}</strong>
                <span>{{ issue.path }}</span>
                <p>{{ issue.message }}</p>
              </li>
            </ul>
            <ul v-if="props.validationResult.warnings.length" class="issue-list issue-list--warning">
              <li
                v-for="issue in props.validationResult.warnings"
                :key="`${issue.error_code ?? issue.code}-${issue.path}`"
              >
                <strong>{{ issueCode(issue) }}</strong>
                <span>{{ issue.path }}</span>
                <p>{{ issue.message }}</p>
              </li>
            </ul>
          </div>
        </div>
        <footer class="modal__footer">
          <button class="button button--secondary" type="button" @click="emit('close')">
            取消
          </button>
          <button class="button" type="submit" :disabled="!props.canSave">
            {{ props.saving ? "保存中..." : "保存配置" }}
          </button>
        </footer>
      </form>
    </section>
  </div>
</template>
