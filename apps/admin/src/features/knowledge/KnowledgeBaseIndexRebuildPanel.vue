<script setup lang="ts">
import type { KnowledgeBaseAdminContext } from "@/features/knowledge/knowledgeAdminContext";

const props = defineProps<{
  model: KnowledgeBaseAdminContext;
}>();

const {
  canRebuildSelectedKnowledgeBaseIndex,
  closeKnowledgeBaseModal,
  documentVisibilityLabel,
  formatKnowledgeBaseLabel,
  importAdminBusy,
  importAdminFeedback,
  knowledgeBaseIndexForm,
  knowledgeBaseVisibilityLabel,
  rebuildSelectedKnowledgeBaseIndex,
  selectedKnowledgeBase,
} = props.model;
</script>

<template>
  <div v-if="selectedKnowledgeBase">
    <div class="modal__body">
      <dl class="summary summary--compact modal-summary">
        <div class="summary__row">
          <dt>知识库</dt>
          <dd>{{ formatKnowledgeBaseLabel(selectedKnowledgeBase) }}</dd>
        </div>
        <div class="summary__row">
          <dt>当前策略</dt>
          <dd>
            {{ knowledgeBaseVisibilityLabel(selectedKnowledgeBase.kb_visibility) }} /
            默认文档{{ documentVisibilityLabel(selectedKnowledgeBase.default_document_visibility) }}
          </dd>
        </div>
      </dl>
      <div class="danger-panel">
        <h4>确认重建知识库索引</h4>
        <p>
          将为该知识库下 active 且已有当前版本的文档创建批量 index_rebuild 任务。任务会从 embed 阶段重新生成向量并发布新索引版本。
        </p>
        <label class="confirm confirm--inline">
          <input v-model="knowledgeBaseIndexForm.confirmedRebuild" type="checkbox" />
          <span>确认重建该知识库索引</span>
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
        class="button"
        type="button"
        @click="rebuildSelectedKnowledgeBaseIndex"
        :disabled="!canRebuildSelectedKnowledgeBaseIndex"
      >
        {{ importAdminBusy.rebuildingIndex ? "创建中..." : "创建重建任务" }}
      </button>
    </footer>
  </div>
</template>
