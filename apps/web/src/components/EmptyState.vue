<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    title: string;
    description?: string;
    actionLabel?: string;
  }>(),
  {
    description: "",
    actionLabel: "",
  },
);

const emit = defineEmits<{
  (event: "action"): void;
}>();
</script>

<template>
  <section class="empty-state">
    <h3>{{ props.title }}</h3>
    <p v-if="props.description">{{ props.description }}</p>
    <button v-if="props.actionLabel" type="button" @click="emit('action')">
      {{ props.actionLabel }}
    </button>
  </section>
</template>

<style scoped>
.empty-state {
  display: grid;
  justify-items: center;
  gap: 10px;
  padding: 32px 20px;
  color: #667085;
  text-align: center;
}

.empty-state h3 {
  margin: 0;
  color: #182230;
  font-size: 17px;
}

.empty-state p {
  max-width: 520px;
  margin: 0;
  line-height: 1.6;
}

.empty-state button {
  min-height: 40px;
  padding: 0 16px;
  border: 1px solid #cfd8e3;
  border-radius: 8px;
  background: #fff;
  color: #182230;
  cursor: pointer;
}
</style>
