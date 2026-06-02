<script setup lang="ts">
import DocumentPermissionModal from "@/features/knowledge/DocumentPermissionModal.vue";
import FolderManagementModal from "@/features/knowledge/FolderManagementModal.vue";
import KnowledgeBaseListPage from "@/features/knowledge/KnowledgeBaseListPage.vue";
import KnowledgeBaseModal from "@/features/knowledge/KnowledgeBaseModal.vue";
import type { KnowledgeBaseAdminContext } from "@/features/knowledge/knowledgeAdminContext";

const props = defineProps<{
  model: KnowledgeBaseAdminContext;
}>();

const model = props.model;
</script>

<template>
  <KnowledgeBaseListPage :model="model" />
  <KnowledgeBaseModal :model="model" />
  <FolderManagementModal :model="model" />
  <DocumentPermissionModal :model="model" />
</template>
