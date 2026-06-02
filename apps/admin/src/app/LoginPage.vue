<script setup lang="ts">
type AuthFeedback = {
  tone: "success" | "error" | "neutral";
  message: string;
};

const props = defineProps<{
  username: string;
  password: string;
  feedback: AuthFeedback | null;
  loggingIn: boolean;
}>();

const emit = defineEmits<{
  (event: "submit"): void;
  (event: "update:username", value: string): void;
  (event: "update:password", value: string): void;
}>();

function inputValue(event: Event): string {
  return (event.target as HTMLInputElement).value;
}
</script>

<template>
  <main class="auth-screen">
    <section class="login-card">
      <div class="login-card__header">
        <p class="brand">Little Bear 管理后台</p>
        <h1 class="title">登录管理后台</h1>
        <p class="auth-copy">当前为单企业部署，请使用系统管理员账号进入管理后台。</p>
      </div>

      <form class="login-form" @submit.prevent="emit('submit')">
        <label class="field field--full">
          <span class="field__label">登录名</span>
          <p class="field__hint">请输入初始化时创建的管理员登录名。</p>
          <input
            :value="props.username"
            class="control"
            type="text"
            autocomplete="username"
            required
            @input="emit('update:username', inputValue($event).trim())"
          />
        </label>
        <label class="field field--full">
          <span class="field__label">密码</span>
          <p class="field__hint">密码只用于本次登录请求，不会保存在前端状态中。</p>
          <input
            :value="props.password"
            class="control"
            type="password"
            autocomplete="current-password"
            required
            @input="emit('update:password', inputValue($event))"
          />
        </label>

        <div v-if="props.feedback" :class="['feedback', `feedback--${props.feedback.tone}`]">
          {{ props.feedback.message }}
        </div>

        <button class="button" type="submit" :disabled="props.loggingIn">
          {{ props.loggingIn ? "登录中..." : "登录" }}
        </button>
      </form>
    </section>
  </main>
</template>
