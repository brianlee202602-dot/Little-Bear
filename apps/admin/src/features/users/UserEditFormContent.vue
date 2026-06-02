<script setup lang="ts">
import { computed } from "vue";

import type { AdminUserData } from "@/api/users";
import type { Feedback, UserBusyState, UserEditForm } from "@/features/users/userActionTypes";
import { formatStatusText } from "@/utils/display";

const props = defineProps<{
  busy: Pick<UserBusyState, "updating">;
  canUpdate: boolean;
  editForm: UserEditForm;
  feedback: Feedback | null;
  formatRoleList: (roles: AdminUserData["roles"]) => string;
  selectedUser: AdminUserData;
  selectedUserIsSystemAdmin: boolean;
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "update"): void;
  (event: "update:editName", value: string): void;
  (event: "update:editStatus", value: "active" | "disabled" | "locked"): void;
  (event: "update:confirmedDisableAdmin", value: boolean): void;
}>();

const editName = computed({
  get: () => props.editForm.name,
  set: (value: string) => emit("update:editName", value),
});
const editStatus = computed<"active" | "disabled" | "locked">({
  get: () => props.editForm.status,
  set: (value) => emit("update:editStatus", value),
});
const confirmedDisableAdmin = computed({
  get: () => props.editForm.confirmedDisableAdmin,
  set: (value: boolean) => emit("update:confirmedDisableAdmin", value),
});

function formatStatusOption(value: string): string {
  return formatStatusText(value);
}
</script>

<template>
  <form @submit.prevent="emit('update')">
    <div class="modal__body">
      <dl class="summary summary--compact modal-summary">
        <div class="summary__row">
          <dt>登录名</dt>
          <dd>{{ props.selectedUser.username }}</dd>
        </div>
        <div class="summary__row">
          <dt>当前角色</dt>
          <dd>{{ props.formatRoleList(props.selectedUser.roles) }}</dd>
        </div>
      </dl>
      <div v-if="props.feedback" :class="['feedback feedback--wide', `feedback--${props.feedback.tone}`]">
        {{ props.feedback.message }}
      </div>
      <div class="form-grid form-grid--compact form-grid--modal">
        <label class="field">
          <span class="field__label">显示名</span>
          <p class="field__hint">用于页面展示、操作记录归属和审计事件摘要。</p>
          <input v-model.trim="editName" class="control" type="text" />
        </label>
        <label class="field">
          <span class="field__label">账号状态</span>
          <p class="field__hint">禁用会吊销用户会话；锁定状态通常由登录失败策略触发。</p>
          <select v-model="editStatus" class="control">
            <option value="active">{{ formatStatusOption("active") }}</option>
            <option value="disabled">{{ formatStatusOption("disabled") }}</option>
            <option value="locked">{{ formatStatusOption("locked") }}</option>
          </select>
        </label>
        <label
          v-if="props.editForm.status === 'disabled' && props.selectedUserIsSystemAdmin"
          class="confirm confirm--inline modal-confirm"
        >
          <input v-model="confirmedDisableAdmin" type="checkbox" />
          <span>确认禁用系统管理员账号</span>
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
</template>
