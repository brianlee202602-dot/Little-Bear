<script setup lang="ts">
import type { FieldDefinition, FieldSection } from "@/features/setup/setupFields";
import type { SetupFormModel } from "@/features/setup/setupModel";

type Tone = "success" | "error" | "warning" | "neutral";
type LocalValidationIssue = {
  field?: keyof SetupFormModel;
  section: string;
  tone: "error" | "warning";
  message: string;
};
type SectionCheckItem = {
  title: string;
  errors: number;
  warnings: number;
  tone: Tone;
};

const props = defineProps<{
  checkboxFieldsBySection: Map<string, FieldDefinition[]>;
  fieldIssues: (key: keyof SetupFormModel) => LocalValidationIssue[];
  form: SetupFormModel;
  normalFieldsBySection: Map<string, FieldDefinition[]>;
  sectionCheckItems: SectionCheckItem[];
  sections: FieldSection[];
}>();

const emit = defineEmits<{
  (event: "checkbox", field: FieldDefinition, value: boolean): void;
  (event: "input", field: FieldDefinition, value: string): void;
  (event: "select", field: FieldDefinition, value: string): void;
}>();

function toneClass(tone: Tone): string {
  return `tone tone--${tone}`;
}

function sectionStatus(section: FieldSection): SectionCheckItem {
  return props.sectionCheckItems.find((item) => item.title === section.title) ?? {
    title: section.title,
    errors: 0,
    warnings: 0,
    tone: "neutral",
  };
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

function hasFieldError(field: keyof SetupFormModel): boolean {
  return props.fieldIssues(field).some((issue) => issue.tone === "error");
}

function hasFieldWarning(field: keyof SetupFormModel): boolean {
  return props.fieldIssues(field).some((issue) => issue.tone === "warning");
}
</script>

<template>
  <section v-for="section in props.sections" :key="section.title" class="panel">
    <header class="panel__header">
      <h3>{{ section.title }}</h3>
      <span :class="toneClass(sectionStatus(section).tone)">
        {{ sectionToneText(sectionStatus(section)) }}
      </span>
    </header>
    <div class="form-grid">
      <label
        v-for="field in props.normalFieldsBySection.get(section.title) ?? []"
        :key="String(field.key)"
        class="field"
        :class="{
          'field--full': field.span === 'full',
          'field--checkbox': field.input === 'checkbox',
          'field--error': hasFieldError(field.key),
          'field--warning': hasFieldWarning(field.key),
        }"
      >
        <template v-if="field.input === 'checkbox'">
          <input
            class="checkbox"
            type="checkbox"
            :checked="Boolean(props.form[field.key])"
            @change="emit('checkbox', field, ($event.target as HTMLInputElement).checked)"
          />
          <span>{{ field.label }}</span>
        </template>

        <template v-else>
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
            :value="String(props.form[field.key])"
            @change="emit('select', field, ($event.target as HTMLSelectElement).value)"
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
            :value="String(props.form[field.key] ?? '')"
            @input="emit('input', field, ($event.target as HTMLInputElement).value)"
          />
        </template>
        <ul v-if="props.fieldIssues(field.key).length" class="field-issues">
          <li
            v-for="issue in props.fieldIssues(field.key)"
            :key="`${issue.tone}-${issue.message}`"
            :class="`field-issue field-issue--${issue.tone}`"
          >
            {{ issue.message }}
          </li>
        </ul>
      </label>
    </div>
    <div
      v-if="(props.checkboxFieldsBySection.get(section.title) ?? []).length"
      class="checkbox-grid"
    >
      <label
        v-for="field in props.checkboxFieldsBySection.get(section.title) ?? []"
        :key="String(field.key)"
        class="field field--checkbox"
        :class="{
          'field--error': hasFieldError(field.key),
          'field--warning': hasFieldWarning(field.key),
        }"
      >
        <input
          class="checkbox"
          type="checkbox"
          :checked="Boolean(props.form[field.key])"
          @change="emit('checkbox', field, ($event.target as HTMLInputElement).checked)"
        />
        <span>{{ field.label }}</span>
        <p class="field__hint" :class="{ 'field__hint--empty': !field.hint }" :aria-hidden="!field.hint">
          {{ field.hint }}
        </p>
        <ul v-if="props.fieldIssues(field.key).length" class="field-issues">
          <li
            v-for="issue in props.fieldIssues(field.key)"
            :key="`${issue.tone}-${issue.message}`"
            :class="`field-issue field-issue--${issue.tone}`"
          >
            {{ issue.message }}
          </li>
        </ul>
      </label>
    </div>
  </section>
</template>
