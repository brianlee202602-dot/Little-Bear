<script setup lang="ts">
import AdminFeatureOutlet from "@/app/AdminFeatureOutlet.vue";
import AdminShell from "@/app/AdminShell.vue";
import { useAdminNavigationProvider } from "@/app/providers/adminNavigationProvider";
import { useAdminSessionProvider } from "@/app/providers/adminSessionProvider";

const navigation = useAdminNavigationProvider();
const session = useAdminSessionProvider();
const { selectedAdminTab, switchAdminTab, visibleAdminTabs } = navigation;
const { authBusy, logout, userDisplayName, userRoleLabels } = session;
</script>

<template>
  <AdminShell
    :tabs="visibleAdminTabs"
    :active-tab="selectedAdminTab"
    :user-display-name="userDisplayName"
    :user-role-labels="userRoleLabels"
    :logging-out="authBusy.loggingOut"
    @switch-tab="switchAdminTab"
    @logout="logout"
  >
    <AdminFeatureOutlet />
  </AdminShell>
</template>
