<script setup lang="ts">
import type { KnowledgeBaseAdminContext } from "@/features/knowledge/knowledgeAdminContext";

const props = defineProps<{
  model: KnowledgeBaseAdminContext;
}>();

const {
  canDeleteSelectedKnowledgeBase,
  closeKnowledgeBaseModal,
  deleteSelectedKnowledgeBase,
  formatKnowledgeBaseLabel,
  importAdminBusy,
  importAdminFeedback,
  knowledgeBaseDangerForm,
  selectedKnowledgeBase,
} = props.model;
</script>

<template>
  <div v-if="selectedKnowledgeBase">
    <div class="modal__body">
      <div class="danger-panel">
        <h4>确认删除知识库</h4>
        <p>
          将删除 {{ formatKnowledgeBaseLabel(selectedKnowledgeBase) }}，并写入 access block，后续由索引清理任务处理相关索引。
        </p>
        <label class="confirm confirm--inline">
          <input v-model="knowledgeBaseDangerForm.confirmedDelete" type="checkbox" />
          <span>确认删除该知识库</span>
        </label>
      </div>
      <div v-if="importAdminFeedback" :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]">
        {{ importAdminFeedback.message }}
      </div>
    </div>
    <footer class="modal__footer">
      <button class="button button--secondary" type="button" @click="closeKnowledgeBaseModal">
        取消
      </button>
      <button
        class="button button--danger"
        type="button"
        @click="deleteSelectedKnowledgeBase"
        :disabled="!canDeleteSelectedKnowledgeBase"
      >
        {{ importAdminBusy.deleting ? "删除中..." : "删除知识库" }}
      </button>
    </footer>
  </div>
</template>
