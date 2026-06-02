<script setup lang="ts">
import type { ChatConversation } from "./types";

const props = defineProps<{
  records: ChatConversation[];
  activeRecordId: string;
  deletingConversationId?: string;
}>();

const emit = defineEmits<{
  (event: "new"): void;
  (event: "select", record: ChatConversation): void;
  (event: "remove", record: ChatConversation): void;
}>();

function formatTime(value: number): string {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(value);
}

function formatStatus(record: ChatConversation): string {
  if (!record.messages.length) {
    return "新对话";
  }
  const lastMessage = record.messages[record.messages.length - 1];
  if (lastMessage?.status === "running") {
    return "生成中";
  }
  if (lastMessage?.status === "error") {
    return "异常";
  }
  if (lastMessage?.status === "cancelled") {
    return "已取消";
  }
  return "已完成";
}
</script>

<template>
  <section class="sidebar-section">
    <div class="section-title">
      <span>对话记录</span>
      <small>{{ props.records.length }}</small>
    </div>
    <button class="new-chat" type="button" @click="emit('new')">新对话</button>
    <div class="history-list">
      <div
        v-for="record in props.records"
        :key="record.id"
        :class="['history-item-row', { active: props.activeRecordId === record.id }]"
      >
        <button class="history-item" type="button" @click="emit('select', record)">
          <strong>{{ record.title }}</strong>
          <span>{{ formatStatus(record) }} · {{ formatTime(record.updatedAt) }}</span>
        </button>
        <button
          class="history-delete"
          type="button"
          title="删除会话"
          :disabled="Boolean(props.deletingConversationId)"
          @click.stop="emit('remove', record)"
        >
          ×
        </button>
      </div>
      <p v-if="!props.records.length" class="muted">暂无对话记录。</p>
    </div>
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

.new-chat,
.history-item {
  width: 100%;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #171717;
  cursor: pointer;
  font: inherit;
  text-align: left;
}

.new-chat {
  min-height: 42px;
  padding: 10px 12px;
  font-weight: 700;
}

.new-chat:hover,
.history-item-row:hover,
.history-item-row.active {
  background: #ededeb;
}

.history-list {
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 4px;
  overflow: auto;
  padding: 0 2px 4px;
}

.history-item-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 30px;
  align-items: center;
  border-radius: 8px;
}

.history-item {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
}

.history-delete {
  width: 26px;
  height: 26px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #737373;
  cursor: pointer;
  font: inherit;
  font-size: 18px;
  line-height: 1;
  opacity: 0;
}

.history-item-row:hover .history-delete,
.history-item-row.active .history-delete {
  opacity: 1;
}

.history-delete:hover {
  background: #dededb;
  color: #171717;
}

.history-delete:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.history-item strong {
  overflow: hidden;
  font-size: 14px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-item span,
.muted {
  color: #737373;
  font-size: 12px;
}

@media (max-width: 920px) {
  .history-list {
    max-height: 220px;
  }
}
</style>
