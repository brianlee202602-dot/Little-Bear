<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";

import "@/features/config/configFeature.css";
import { useAdminCapabilityProvider } from "@/app/providers/adminCapabilityProvider";
import { useAdminEventBus } from "@/app/providers/adminEventBus";
import { useAdminSessionProvider } from "@/app/providers/adminSessionProvider";
import { useAuditLogs } from "@/features/audit/useAuditLogs";
import ConfigManagementContainer from "@/features/config/ConfigManagementContainer.vue";
import { useConfigManagement } from "@/features/config/useConfigManagement";
import { normalizeErrorMessage } from "@/utils/errors";
import { clearPaginationState, syncPaginationState } from "@/utils/pagination";

const pageSizeOptions = [10, 20, 50, 100, 200];
const capabilities = useAdminCapabilityProvider();
const eventBus = useAdminEventBus();
const session = useAdminSessionProvider();
const setupActiveConfigVersion = ref<number | null>(null);

const audit = useAuditLogs({
  canReadAudit: capabilities.canReadAudit,
  clearPaginationState,
  ensureAccessToken: session.ensureAccessToken,
  normalizeErrorMessage,
  syncPaginationState,
});

const config = useConfigManagement({
  canManageConfig: capabilities.canManageConfig,
  canReadConfig: capabilities.canReadConfig,
  confirmAction: (message) => window.confirm(message),
  ensureAccessToken: session.ensureAccessToken,
  normalizeErrorMessage,
  onConfigChanged: async () => {
    eventBus.emit({ type: "config.changed" });
  },
  setupActiveConfigVersion,
});

async function refreshConfigAdminState(): Promise<void> {
  await config.refreshConfigVersions();
  await audit.refreshConfigAuditLogs();
}

const stopConfigChangedListener = eventBus.on("config.changed", () => {
  void audit.refreshConfigAuditLogs();
});

onMounted(() => {
  void refreshConfigAdminState();
});

onUnmounted(() => {
  stopConfigChangedListener();
});
</script>

<template>
  <ConfigManagementContainer
    :audit="audit"
    :authenticated="session.authenticated.value"
    :can-manage-config="capabilities.canManageConfig.value"
    :can-read-audit="capabilities.canReadAudit.value"
    :can-read-config="capabilities.canReadConfig.value"
    :current-user="session.currentUser.value"
    :page-size-options="pageSizeOptions"
    :refresh-config-admin-state="refreshConfigAdminState"
    :runtime="config"
    :user-role-labels="session.userRoleLabels.value"
  />
</template>
