<script setup lang="ts">
import { computed } from "vue";

import type { AdminUserData } from "@/api/users";
import { formatStatusText } from "@/utils/display";

type Feedback = {
  tone: "success" | "error" | "neutral";
  message: string;
};

type BusyState = {
  resettingPassword: boolean;
};

type PasswordResetForm = {
  newPassword: string;
  passwordConfirm: string;
  forceChangePassword: boolean;
  confirmed: boolean;
};

const props = defineProps<{
  open: boolean;
  selectedUser: AdminUserData | null;
  form: PasswordResetForm;
  busy: BusyState;
  feedback: Feedback | null;
  canReset: boolean;
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "submit"): void;
  (event: "update:newPassword", value: string): void;
  (event: "update:passwordConfirm", value: string): void;
  (event: "update:forceChangePassword", value: boolean): void;
  (event: "update:confirmed", value: boolean): void;
}>();

const newPassword = computed({
  get: () => props.form.newPassword,
  set: (value: string) => emit("update:newPassword", value),
});
const passwordConfirm = computed({
  get: () => props.form.passwordConfirm,
  set: (value: string) => emit("update:passwordConfirm", value),
});
const forceChangePassword = computed({
  get: () => props.form.forceChangePassword,
  set: (value: boolean) => emit("update:forceChangePassword", value),
});
const confirmed = computed({
  get: () => props.form.confirmed,
  set: (value: boolean) => emit("update:confirmed", value),
});
</script>

<template>
  <div v-if="props.open" class="modal-backdrop" role="presentation" @click.self="emit('close')">
    <section class="modal modal--wide" role="dialog" aria-modal="true" aria-labelledby="password-reset-modal-title">
      <header class="modal__header">
        <div>
          <p class="eyebrow">用户管理</p>
          <h3 id="password-reset-modal-title">重置密码</h3>
        </div>
        <button class="button button--secondary button--small" type="button" @click="emit('close')">
          关闭
        </button>
      </header>

      <form v-if="props.selectedUser" @submit.prevent="emit('submit')">
        <div class="modal__body">
          <dl class="summary summary--compact modal-summary">
            <div class="summary__row">
              <dt>用户</dt>
              <dd>{{ props.selectedUser.name || props.selectedUser.username }}</dd>
            </div>
            <div class="summary__row">
              <dt>账号状态</dt>
              <dd>{{ formatStatusText(props.selectedUser.status) }}</dd>
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
              <span class="field__label">新密码</span>
              <p class="field__hint">必须满足当前 active_config 中的密码策略。</p>
              <input v-model="newPassword" class="control" type="password" />
            </label>
            <label class="field">
              <span class="field__label">确认新密码</span>
              <p class="field__hint">用于避免误输入。</p>
              <input v-model="passwordConfirm" class="control" type="password" />
            </label>
            <label class="confirm confirm--inline modal-confirm">
              <input v-model="forceChangePassword" type="checkbox" />
              <span>强制下次登录修改密码</span>
            </label>
            <label class="confirm confirm--inline modal-confirm">
              <input v-model="confirmed" type="checkbox" />
              <span>确认重置密码并吊销会话</span>
            </label>
          </div>
        </div>
        <footer class="modal__footer">
          <button class="button button--secondary" type="button" @click="emit('close')">
            取消
          </button>
          <button class="button" type="submit" :disabled="!props.canReset">
            {{ props.busy.resettingPassword ? "重置中..." : "重置密码" }}
          </button>
        </footer>
      </form>
    </section>
  </div>
</template>
