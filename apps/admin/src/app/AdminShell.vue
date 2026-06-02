<script setup lang="ts">
import type { ActiveAdminTab, AdminTabDefinition } from "./navigation";

const props = defineProps<{
  tabs: AdminTabDefinition[];
  activeTab: ActiveAdminTab;
  userDisplayName: string;
  userRoleLabels: string;
  loggingOut: boolean;
}>();

const emit = defineEmits<{
  (event: "switchTab", tab: ActiveAdminTab): void;
  (event: "logout"): void;
}>();
</script>

<template>
  <main class="admin-shell">
    <aside class="admin-sidebar">
      <div class="sidebar__block">
        <p class="brand">Little Bear 管理后台</p>
        <h1 class="title">运行控制台</h1>
      </div>
      <nav class="admin-nav" aria-label="管理后台导航">
        <button
          v-for="tab in props.tabs"
          :key="tab.key"
          :class="['admin-nav__item', { 'admin-nav__item--active': props.activeTab === tab.key }]"
          type="button"
          @click="emit('switchTab', tab.key)"
        >
          {{ tab.label }}
        </button>
      </nav>
    </aside>

    <section class="admin-workspace">
      <header class="admin-toolbar">
        <div>
          <p class="eyebrow">/admin</p>
          <h2>管理后台</h2>
        </div>
        <div class="user-menu">
          <div>
            <strong>{{ props.userDisplayName }}</strong>
            <span>{{ props.userRoleLabels }}</span>
          </div>
          <button
            class="button button--secondary"
            type="button"
            :disabled="props.loggingOut"
            @click="emit('logout')"
          >
            {{ props.loggingOut ? "退出中..." : "退出登录" }}
          </button>
        </div>
      </header>

      <slot />
    </section>
  </main>
</template>

<style scoped>
.admin-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  color: #18202a;
  background: #f3f5f7;
}

.admin-sidebar {
  background: #20252d;
  color: #f4f6f8;
  padding: 24px 20px;
  display: grid;
  align-content: start;
  gap: 22px;
  border-right: 1px solid #303744;
}

.sidebar__block {
  display: grid;
  gap: 12px;
}

.brand {
  margin: 0;
  color: #98a4b5;
  font-size: 12px;
  text-transform: uppercase;
}

.title {
  margin: 0;
  font-size: 24px;
  line-height: 1.2;
}

.admin-nav {
  display: grid;
  gap: 8px;
}

.admin-nav__item {
  width: 100%;
  border: 1px solid #3a4350;
  border-radius: 8px;
  background: transparent;
  color: #d6dce5;
  cursor: pointer;
  padding: 10px 12px;
  text-align: left;
}

.admin-nav__item--active {
  border-color: #80b6a4;
  background: #2a403a;
  color: #ffffff;
}

.admin-workspace {
  min-width: 0;
  display: grid;
  align-content: start;
  gap: 20px;
  padding: 24px;
}

.admin-toolbar {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 16px;
}

.admin-toolbar h2 {
  margin: 0;
}

.eyebrow {
  margin: 0;
  color: #667182;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.user-menu {
  display: flex;
  align-items: center;
  gap: 14px;
}

.user-menu > div {
  display: grid;
  justify-items: end;
  gap: 2px;
}

.user-menu span {
  color: #667182;
  font-size: 12px;
}

.button {
  appearance: none;
  border: 1px solid #2f7d66;
  border-radius: 8px;
  background: #2f7d66;
  color: #ffffff;
  cursor: pointer;
  font: inherit;
  padding: 10px 14px;
}

.button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.button--secondary {
  border-color: #cdd5df;
  background: #ffffff;
  color: #21303d;
}

@media (max-width: 1200px) {
  .admin-shell {
    grid-template-columns: 1fr;
  }

  .admin-sidebar {
    border-right: 0;
    border-bottom: 1px solid #303744;
  }
}

@media (max-width: 768px) {
  .admin-workspace {
    padding: 16px;
  }

  .admin-toolbar {
    display: grid;
    grid-template-columns: 1fr;
  }

  .user-menu {
    align-items: stretch;
    display: grid;
  }

  .user-menu > div {
    justify-items: start;
  }
}
</style>
