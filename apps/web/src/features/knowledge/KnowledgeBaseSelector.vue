<script setup lang="ts">
import type { KnowledgeBaseData } from "@/api/knowledge";

const props = defineProps<{
  authenticated: boolean;
  label: string;
  items: KnowledgeBaseData[];
  selectedIds: string[];
  hasMore: boolean;
  loading: boolean;
  feedback: string;
}>();

const emit = defineEmits<{
  (event: "refresh"): void;
  (event: "selectAll"): void;
  (event: "clear"): void;
  (event: "toggle", kbId: string): void;
  (event: "loadMore"): void;
}>();

function isSelected(kbId: string): boolean {
  return props.selectedIds.includes(kbId);
}

function formatStatus(value: KnowledgeBaseData["status"]): string {
  const labels: Record<KnowledgeBaseData["status"], string> = {
    active: "启用",
    archived: "归档",
    disabled: "停用",
  };
  return labels[value] ?? value;
}
</script>

<template>
  <section class="sidebar-section knowledge-section">
    <div class="section-title">
      <span>知识库</span>
      <small>{{ props.label }}</small>
    </div>

    <div v-if="!props.authenticated" class="empty-state compact">
      <strong>请先登录</strong>
      <p>登录后显示当前账号可访问的知识库。</p>
    </div>
    <template v-else>
      <div class="kb-actions">
        <button class="text-button" type="button" :disabled="props.loading" @click="emit('refresh')">
          刷新
        </button>
        <button class="text-button" type="button" :disabled="!props.items.length" @click="emit('selectAll')">
          全选
        </button>
        <button class="text-button" type="button" :disabled="!props.selectedIds.length" @click="emit('clear')">
          清空
        </button>
      </div>

      <div class="kb-list">
        <label v-for="kb in props.items" :key="kb.id" class="kb-item">
          <input type="checkbox" :checked="isSelected(kb.id)" @change="emit('toggle', kb.id)" />
          <span>
            <strong>{{ kb.name }}</strong>
            <small>{{ formatStatus(kb.status) }}</small>
          </span>
        </label>
        <div v-if="!props.items.length" class="empty-state compact warning">
          <strong>暂无可查询知识库</strong>
          <p>当前账号没有可访问的知识库，无法发起查询。</p>
        </div>
      </div>
      <button
        v-if="props.hasMore"
        class="text-button kb-load-more"
        type="button"
        :disabled="props.loading"
        @click="emit('loadMore')"
      >
        {{ props.loading ? "加载中" : "加载更多知识库" }}
      </button>
      <p v-if="props.feedback" class="inline-error">{{ props.feedback }}</p>
    </template>
  </section>
</template>

<style scoped>
.sidebar-section {
  min-height: 0;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 8px;
  padding: 0 4px;
}

.knowledge-section {
  grid-template-rows: auto auto minmax(0, auto) auto;
}

.section-title {
  min-height: 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 6px;
  color: #171717;
  font-size: 13px;
  font-weight: 800;
}

.section-title small {
  color: #737373;
  font-size: 12px;
  font-weight: 600;
  text-align: right;
}

.kb-actions {
  display: flex;
  gap: 8px;
  padding: 0 6px;
}

.text-button {
  border: 0;
  background: transparent;
  color: #404040;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  padding: 2px 0;
}

.text-button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.kb-load-more {
  margin: 6px;
  text-align: left;
}

.kb-list {
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 4px;
  overflow: auto;
  padding: 0 2px 4px;
}

.kb-item {
  width: 100%;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #171717;
  cursor: pointer;
  font: inherit;
  padding: 9px 10px;
  text-align: left;
}

.kb-item:hover {
  background: #ededeb;
}

.kb-item input {
  margin-top: 3px;
}

.kb-item strong {
  display: block;
  overflow: hidden;
  font-size: 14px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-item small {
  display: block;
  margin-top: 3px;
  color: #737373;
  font-size: 12px;
}

.empty-state {
  display: grid;
  gap: 6px;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  background: #ffffff;
  padding: 14px;
}

.empty-state.compact {
  margin: 0 6px;
  padding: 12px;
}

.empty-state.warning {
  border-color: #f0d29c;
  background: #fff8e8;
}

.empty-state strong {
  font-size: 14px;
}

.empty-state p {
  margin: 0;
  color: #737373;
  font-size: 13px;
  line-height: 1.5;
}

.inline-error {
  border: 1px solid #f0b6aa;
  border-radius: 8px;
  background: #fff1ee;
  color: #8f2f22;
  font-size: 13px;
  line-height: 1.5;
  padding: 9px 11px;
}

@media (max-width: 920px) {
  .kb-list {
    max-height: 220px;
  }
}
</style>
