<script setup lang="ts">
import { computed } from "vue";

import type { AdminDepartmentListItemData } from "@/api/departments";
import { formatStatusText } from "@/utils/display";

export type DepartmentModalMode = "create" | "edit" | "delete" | null;

type Feedback = {
  tone: "success" | "error" | "neutral";
  message: string;
};

type BusyState = {
  creating: boolean;
  updating: boolean;
  deleting: boolean;
};

type DepartmentCreateForm = {
  code: string;
  name: string;
};

type DepartmentEditForm = {
  name: string;
  status: "active" | "disabled";
};

type DepartmentDangerForm = {
  confirmedDelete: boolean;
};

const props = defineProps<{
  mode: DepartmentModalMode;
  selectedDepartment: AdminDepartmentListItemData | null;
  createForm: DepartmentCreateForm;
  editForm: DepartmentEditForm;
  dangerForm: DepartmentDangerForm;
  busy: BusyState;
  feedback: Feedback | null;
  canCreate: boolean;
  canUpdate: boolean;
  canDelete: boolean;
  formatDepartmentLabel: (department: AdminDepartmentListItemData | null | undefined) => string;
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "create"): void;
  (event: "update"): void;
  (event: "delete"): void;
  (event: "update:createCode", value: string): void;
  (event: "update:createName", value: string): void;
  (event: "update:editName", value: string): void;
  (event: "update:editStatus", value: "active" | "disabled"): void;
  (event: "update:confirmedDelete", value: boolean): void;
}>();

const createCode = computed({
  get: () => props.createForm.code,
  set: (value: string) => emit("update:createCode", value),
});

const createName = computed({
  get: () => props.createForm.name,
  set: (value: string) => emit("update:createName", value),
});

const editName = computed({
  get: () => props.editForm.name,
  set: (value: string) => emit("update:editName", value),
});

const editStatus = computed<"active" | "disabled">({
  get: () => props.editForm.status,
  set: (value) => emit("update:editStatus", value),
});

const confirmedDelete = computed({
  get: () => props.dangerForm.confirmedDelete,
  set: (value: boolean) => emit("update:confirmedDelete", value),
});

const title = computed(() => {
  if (props.mode === "create") {
    return "新增部门";
  }
  if (props.mode === "edit") {
    return "编辑部门";
  }
  return "删除部门";
});

function formatStatusOption(value: string): string {
  return formatStatusText(value);
}
</script>

<template>
  <div v-if="props.mode" class="modal-backdrop" role="presentation" @click.self="emit('close')">
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="department-modal-title">
      <header class="modal__header">
        <div>
          <p class="eyebrow">部门管理</p>
          <h3 id="department-modal-title">{{ title }}</h3>
        </div>
        <button class="button button--secondary button--small" type="button" @click="emit('close')">
          关闭
        </button>
      </header>

      <form v-if="props.mode === 'create'" @submit.prevent="emit('create')">
        <div class="modal__body">
          <div
            v-if="props.feedback"
            :class="['feedback feedback--wide', `feedback--${props.feedback.tone}`]"
          >
            {{ props.feedback.message }}
          </div>
          <div class="form-grid form-grid--compact form-grid--modal">
            <label class="field">
              <span class="field__label">部门编码</span>
              <p class="field__hint">企业内唯一，建议使用字母、数字、下划线或连字符。</p>
              <input v-model.trim="createCode" class="control" type="text" />
            </label>
            <label class="field">
              <span class="field__label">部门名称</span>
              <p class="field__hint">用于用户归属、权限范围和管理后台展示。</p>
              <input v-model.trim="createName" class="control" type="text" />
            </label>
          </div>
        </div>
        <footer class="modal__footer">
          <button class="button button--secondary" type="button" @click="emit('close')">
            取消
          </button>
          <button class="button" type="submit" :disabled="!props.canCreate">
            {{ props.busy.creating ? "创建中..." : "创建部门" }}
          </button>
        </footer>
      </form>

      <form
        v-else-if="props.mode === 'edit' && props.selectedDepartment"
        @submit.prevent="emit('update')"
      >
        <div class="modal__body">
          <dl class="summary summary--compact modal-summary">
            <div class="summary__row">
              <dt>默认部门</dt>
              <dd>{{ props.selectedDepartment.is_default ? "是" : "否" }}</dd>
            </div>
          </dl>
          <div
            v-if="props.feedback"
            :class="['feedback feedback--wide', `feedback--${props.feedback.tone}`]"
          >
            {{ props.feedback.message }}
          </div>
          <div class="form-grid form-grid--compact form-grid--modal">
            <label class="field">
              <span class="field__label">部门名称</span>
              <p class="field__hint">修改后会刷新组织版本和权限版本。</p>
              <input v-model.trim="editName" class="control" type="text" />
            </label>
            <label class="field">
              <span class="field__label">部门状态</span>
              <p class="field__hint">默认部门不能禁用；禁用会影响用户权限上下文。</p>
              <select
                v-model="editStatus"
                class="control"
                :disabled="props.selectedDepartment.is_default"
              >
                <option value="active">{{ formatStatusOption("active") }}</option>
                <option value="disabled">{{ formatStatusOption("disabled") }}</option>
              </select>
            </label>
          </div>
        </div>
        <footer class="modal__footer">
          <button class="button button--secondary" type="button" @click="emit('close')">
            取消
          </button>
          <button class="button" type="submit" :disabled="!props.canUpdate">
            {{ props.busy.updating ? "保存中..." : "保存修改" }}
          </button>
        </footer>
      </form>

      <div v-else-if="props.mode === 'delete' && props.selectedDepartment">
        <div class="modal__body">
          <div class="danger-panel">
            <h4>确认删除部门</h4>
            <p>
              将删除部门 {{ props.formatDepartmentLabel(props.selectedDepartment) }}。默认部门不能删除，已有关联用户或权限范围时后端会阻止该操作。
            </p>
            <label class="confirm confirm--inline">
              <input
                v-model="confirmedDelete"
                type="checkbox"
                :disabled="props.selectedDepartment.is_default"
              />
              <span>确认删除该部门</span>
            </label>
          </div>
          <div
            v-if="props.feedback"
            :class="['feedback feedback--wide', `feedback--${props.feedback.tone}`]"
          >
            {{ props.feedback.message }}
          </div>
        </div>
        <footer class="modal__footer">
          <button class="button button--secondary" type="button" @click="emit('close')">
            取消
          </button>
          <button
            class="button button--danger"
            type="button"
            :disabled="!props.canDelete"
            @click="emit('delete')"
          >
            {{ props.busy.deleting ? "删除中..." : "删除部门" }}
          </button>
        </footer>
      </div>
    </section>
  </div>
</template>
