<script setup lang="ts">
import { computed } from "vue";

import { getAdminFeatureDefinition } from "@/app/featureRegistry";
import { useAdminCapabilityProvider } from "@/app/providers/adminCapabilityProvider";
import { useAdminNavigationProvider } from "@/app/providers/adminNavigationProvider";

const capabilities = useAdminCapabilityProvider();
const navigation = useAdminNavigationProvider();

const activeFeature = computed(() => {
  const feature = getAdminFeatureDefinition(navigation.selectedAdminTab.value);
  if (!feature || !feature.canAccess(capabilities)) {
    return null;
  }
  return feature;
});
</script>

<template>
  <section class="dashboard-grid">
    <component
      :is="activeFeature.component"
      v-if="activeFeature"
    />
  </section>
</template>
