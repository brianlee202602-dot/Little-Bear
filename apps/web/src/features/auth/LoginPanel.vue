<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    username: string;
    password: string;
    busy?: boolean;
    restoring?: boolean;
    feedback?: string;
  }>(),
  {
    busy: false,
    restoring: false,
    feedback: "",
  },
);

const emit = defineEmits<{
  (event: "update:username", value: string): void;
  (event: "update:password", value: string): void;
  (event: "submit"): void;
}>();
</script>

<template>
  <div class="login-view">
    <form class="login-panel" @submit.prevent="emit('submit')">
      <h2>登录后开始查询</h2>
      <p>当前查询需要你的身份和知识库权限，登录成功后左侧会显示可访问知识库。</p>
      <label class="field">
        <span>用户名</span>
        <input
          :value="props.username"
          type="text"
          autocomplete="username"
          @input="emit('update:username', ($event.target as HTMLInputElement).value.trim())"
        />
      </label>
      <label class="field">
        <span>密码</span>
        <input
          :value="props.password"
          type="password"
          autocomplete="current-password"
          @input="emit('update:password', ($event.target as HTMLInputElement).value)"
        />
      </label>
      <button class="primary-button" type="submit" :disabled="props.busy || props.restoring">
        {{ props.busy ? "登录中" : "登录" }}
      </button>
      <p v-if="props.feedback" class="inline-error">{{ props.feedback }}</p>
    </form>
  </div>
</template>

<style scoped>
.login-view {
  min-height: 0;
  display: grid;
  place-items: center;
  overflow: auto;
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
.login-panel p {
  margin: 0;
}

.login-panel h2 {
  font-size: 28px;
  line-height: 1.2;
}

.login-panel p {
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

input {
  width: 100%;
  border: 1px solid #d4d4d4;
  border-radius: 8px;
  background: #ffffff;
  color: #171717;
  font: inherit;
  line-height: 1.5;
  outline: none;
  padding: 9px 11px;
}

input:focus {
  border-color: #9ca3af;
  box-shadow: 0 0 0 3px rgba(17, 17, 17, 0.08);
}

.primary-button {
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

.primary-button:disabled {
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
</style>
