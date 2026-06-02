<script setup lang="ts">
import DocumentChunkPreviewPane from "@/features/knowledge/DocumentChunkPreviewPane.vue";
import DocumentIndexVersionPane from "@/features/knowledge/DocumentIndexVersionPane.vue";
import DocumentVersionPane from "@/features/knowledge/DocumentVersionPane.vue";
import type { KnowledgeBaseAdminContext } from "@/features/knowledge/knowledgeAdminContext";

const props = defineProps<{
  model: KnowledgeBaseAdminContext;
}>();

const {
  closeDocumentModal,
  formatDocumentCurrentVersion,
  formatStatusText,
  selectedDocumentForDisplay,
} = props.model;
</script>

<template>
  <div v-if="selectedDocumentForDisplay">
    <div class="modal__body modal__body--document-details">
      <dl class="summary summary--compact modal-summary document-detail-summary">
        <div class="summary__row">
          <dt>文档</dt>
          <dd>{{ selectedDocumentForDisplay.title || "未命名文档" }}</dd>
        </div>
        <div class="summary__row">
          <dt>当前版本</dt>
          <dd>{{ formatDocumentCurrentVersion(selectedDocumentForDisplay) }}</dd>
        </div>
        <div class="summary__row">
          <dt>生命周期</dt>
          <dd>{{ formatStatusText(selectedDocumentForDisplay.lifecycle_status) }}</dd>
        </div>
        <div class="summary__row">
          <dt>索引状态</dt>
          <dd>{{ formatStatusText(selectedDocumentForDisplay.index_status) }}</dd>
        </div>
      </dl>

      <section class="document-version-index-grid">
        <DocumentVersionPane :model="model" />
        <DocumentIndexVersionPane :model="model" />
      </section>

      <DocumentChunkPreviewPane :model="model" />
    </div>
    <footer class="modal__footer">
      <button class="button button--secondary" type="button" @click="closeDocumentModal">
        关闭
      </button>
    </footer>
  </div>
</template>
