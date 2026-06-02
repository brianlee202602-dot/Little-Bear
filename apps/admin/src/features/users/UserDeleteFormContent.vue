<script setup lang="ts">
import { computed } from "vue";

import type { AdminUserData } from "@/api/users";
import type { Feedback, UserBusyState, UserDangerForm } from "@/features/users/userActionTypes";

const props = defineProps<{
  busy: Pick<UserBusyState, "updating">;
  canDelete: boolean;
  dangerForm: UserDangerForm;
  feedback: Feedback | null;
  selectedUser: AdminUserData;
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "delete"): void;
  (event: "update:confirmedDelete", value: boolean): void;
}>();

const confirmedDelete = computed({
  get: () => props.dangerForm.confirmedDelete,
  set: (value: boolean) => emit("update:confirmedDelete", value),
});
</script>

<template>
  <div>
    <div class="modal__body">
      <div class="danger-panel">
        <h4>确认删除用户</h4>
        <p>
          将删除用户 {{ props.selectedUser.name || props.selectedUser.username }}，并由后端吊销相关会话。删除后该账号不能再登录。
        </p>
        <label class="confirm confirm--inline">
          <input v-model="confirmedDelete" type="checkbox" />
          <span>确认删除该用户</span>
        </label>
      </div>
      <div v-if="props.feedback" :class="['feedback feedback--wide', `feedback--${props.feedback.tone}`]">
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
        {{ props.busy.updating ? "删除中..." : "删除用户" }}
      </button>
    </footer>
  </div>
</template>
