<script setup lang="ts">
import { onMounted } from "vue";

import "@/features/diagnostics/diagnosticsFeature.css";
import { useAdminCapabilityProvider } from "@/app/providers/adminCapabilityProvider";
import { useAdminSessionProvider } from "@/app/providers/adminSessionProvider";
import DiagnosticsPage from "@/features/diagnostics/DiagnosticsPage.vue";
import { useDiagnostics } from "@/features/diagnostics/useDiagnostics";
import { normalizeErrorMessage } from "@/utils/errors";
import {
  clearPaginationState,
  paginationTotalPages,
  syncPaginationState,
} from "@/utils/pagination";

const pageSizeOptions = [10, 20, 50, 100, 200];
const capabilities = useAdminCapabilityProvider();
const session = useAdminSessionProvider();

const runtime = useDiagnostics({
  canLoadDiagnostics: capabilities.canLoadDiagnostics,
  canLoadIndexOps: capabilities.canLoadIndexOps,
  clearPaginationState,
  ensureAccessToken: session.ensureAccessToken,
  normalizeErrorMessage,
  paginationTotalPages,
  syncPaginationState,
});

onMounted(async () => {
  await runtime.refreshDiagnosticsState();
});
</script>

<template>
  <DiagnosticsPage
    :runtime="runtime"
    :page-size-options="pageSizeOptions"
  />
</template>
