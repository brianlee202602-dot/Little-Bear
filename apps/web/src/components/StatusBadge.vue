<script setup lang="ts">
import type { DisplayTone } from "@/utils/display";

const props = withDefaults(
  defineProps<{
    label: string;
    tone?: DisplayTone;
  }>(),
  {
    tone: "neutral",
  },
);
</script>

<template>
  <span class="status-badge" :class="`status-badge--${props.tone}`">
    {{ props.label }}
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
}

.status-badge--success {
  background: #e7f6ee;
  color: #067647;
}

.status-badge--warning {
  background: #fff4df;
  color: #b54708;
}

.status-badge--error {
  background: #fdecec;
  color: #b42318;
}

.status-badge--neutral {
  background: #eef2f6;
  color: #475467;
}
</style>
