<script setup lang="ts">
import DocumentDetailsContent from "@/features/knowledge/DocumentDetailsContent.vue";
import DocumentPermissionEditor from "@/features/knowledge/DocumentPermissionEditor.vue";
import type { KnowledgeBaseAdminContext } from "@/features/knowledge/knowledgeAdminContext";

const props = defineProps<{
  model: KnowledgeBaseAdminContext;
}>();

const { closeDocumentModal, documentModalMode, selectedDocumentForDisplay } = props.model;
</script>

<template>
  <div
    v-if="documentModalMode"
    class="modal-backdrop"
    role="presentation"
    @click.self="closeDocumentModal"
  >
    <section
      :class="['modal', documentModalMode === 'details' ? 'modal--document-details' : 'modal--wide']"
      role="dialog"
      aria-modal="true"
      aria-labelledby="document-modal-title"
    >
      <header class="modal__header">
        <div>
          <p class="eyebrow">文档管理</p>
          <h3 id="document-modal-title">
            {{ documentModalMode === "details" ? "版本与片段" : "文档权限策略" }}
          </h3>
          <p v-if="selectedDocumentForDisplay">
            {{ selectedDocumentForDisplay.title || "未命名文档" }}
          </p>
        </div>
        <button class="button button--secondary button--small" type="button" @click="closeDocumentModal">
          关闭
        </button>
      </header>

      <DocumentPermissionEditor v-if="documentModalMode === 'permissions'" :model="model" />
      <DocumentDetailsContent v-else-if="documentModalMode === 'details'" :model="model" />
    </section>
  </div>
</template>
