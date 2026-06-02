<script setup lang="ts">
import { defineAsyncComponent } from "vue";

import AdminDashboard from "@/app/AdminDashboard.vue";
import LoginPage from "@/app/LoginPage.vue";
import {
  createAdminEventBus,
  provideAdminEventBus,
} from "@/app/providers/adminEventBus";
import { provideAdminCapabilities } from "@/app/providers/adminCapabilityProvider";
import { provideAdminNavigation } from "@/app/providers/adminNavigationProvider";
import { provideAdminSession } from "@/app/providers/adminSessionProvider";
import { useAdminAppRuntime } from "@/app/useAdminAppRuntime";

const SetupPage = defineAsyncComponent(() => import("@/features/setup/SetupPage.vue"));

const runtime = useAdminAppRuntime();
provideAdminSession(runtime.adminSessionProvider);
provideAdminCapabilities(runtime.adminCapabilityProvider);
provideAdminNavigation(runtime.adminNavigationProvider);
provideAdminEventBus(createAdminEventBus());

const {
  activeView,
  authBusy,
  authFeedback,
  loginForm,
  setupFlow,
  submitLogin,
} = runtime;
</script>

<template>
  <main v-if="activeView === 'loading'" class="auth-screen">
    <section class="login-card">
      <p class="brand">Little Bear 管理后台</p>
      <h1 class="title">正在检查系统状态</h1>
      <p class="auth-copy">正在读取初始化状态和本地登录态。</p>
    </section>
  </main>

  <LoginPage
    v-else-if="activeView === 'login'"
    :feedback="authFeedback"
    :logging-in="authBusy.loggingIn"
    :password="loginForm.password"
    :username="loginForm.username"
    @submit="submitLogin"
    @update:password="(value) => (loginForm.password = value)"
    @update:username="(value) => (loginForm.username = value)"
  />

  <AdminDashboard
    v-else-if="activeView === 'dashboard'"
  />

  <SetupPage v-else :flow="setupFlow.page" />
</template>
