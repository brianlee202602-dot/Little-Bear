<script setup lang="ts">
import type { ChunkData, CitationSourceData } from "@/api/documents";
import { formatSourceTextStatus } from "@/utils/display";

const props = defineProps<{
  detail: CitationSourceData | null;
  chunks: ChunkData[];
  title: string;
  feedback: string;
  highlightedChunkId: string;
  hasMore: boolean;
  loading: boolean;
  total: number;
}>();

const emit = defineEmits<{
  (event: "loadMore"): void;
}>();
</script>

<template>
  <section v-if="props.detail || props.chunks.length || props.feedback" class="source-panel">
    <header>
      <h2>来源内容</h2>
      <span v-if="props.title">{{ props.title }}</span>
    </header>
    <p v-if="props.feedback" class="inline-error">{{ props.feedback }}</p>
    <article v-if="props.detail" class="source-detail">
      <header>
        <div>
          <strong>{{ props.detail.title }}</strong>
          <span>
            页 {{ props.detail.page_start ?? 0 }}-{{
              props.detail.page_end ?? props.detail.page_start ?? 0
            }}
            · 片段 {{ props.detail.ordinal }}
          </span>
        </div>
        <span :class="['pill', props.detail.text_status === 'object' ? 'pill--success' : 'pill--warning']">
          {{ formatSourceTextStatus(props.detail.text_status) }}
        </span>
      </header>
      <dl class="source-proof">
        <div>
          <dt>标题路径</dt>
          <dd>{{ props.detail.heading_path || "无" }}</dd>
        </div>
      </dl>
      <p>{{ props.detail.text }}</p>
    </article>
    <article
      v-for="(chunk, index) in props.chunks"
      :key="chunk.id"
      :class="['source-chunk', { active: chunk.id === props.highlightedChunkId }]"
    >
      <header>
        <strong>片段 {{ chunk.ordinal || index + 1 }}</strong>
        <span>页 {{ chunk.page_start ?? 0 }}-{{ chunk.page_end ?? chunk.page_start ?? 0 }}</span>
      </header>
      <p>{{ chunk.text_preview }}</p>
    </article>
    <button
      v-if="props.chunks.length && props.hasMore"
      class="text-button kb-load-more"
      type="button"
      :disabled="props.loading"
      @click="emit('loadMore')"
    >
      {{ props.loading ? "加载中" : `加载更多片段（${props.chunks.length}/${props.total}）` }}
    </button>
  </section>
</template>

<style scoped>
.source-panel {
  max-width: 920px;
  display: grid;
  gap: 10px;
  border-top: 1px solid #eeeeee;
  padding-top: 16px;
}

.source-panel > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.source-panel h2 {
  margin: 0;
  font-size: 16px;
}

.source-panel > header span {
  color: #737373;
  font-size: 13px;
}

.source-detail {
  border: 1px solid #d9e8e1;
  border-radius: 8px;
  background: #fbfefd;
  padding: 14px;
}

.source-detail > header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.source-detail > header div {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.source-detail > header strong {
  overflow-wrap: anywhere;
}

.source-detail > header span {
  color: #737373;
  font-size: 12px;
}

.source-proof {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 14px;
  margin: 12px 0;
  font-size: 12px;
}

.source-proof div {
  min-width: 0;
}

.source-proof dt {
  color: #737373;
  margin-bottom: 3px;
}

.source-proof dd {
  margin: 0;
  color: #333333;
  overflow-wrap: anywhere;
}

.source-detail p {
  line-height: 1.72;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.source-chunk {
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  background: #ffffff;
  padding: 12px;
}

.source-chunk.active {
  border-color: #f0d29c;
  background: #fff8e8;
}

.source-chunk header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.source-chunk strong {
  color: #525252;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.source-chunk span {
  color: #737373;
  font-size: 12px;
  white-space: nowrap;
}

.source-chunk p {
  margin: 0;
  line-height: 1.65;
  overflow-wrap: anywhere;
}

.pill {
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  border: 1px solid #d4d4d4;
  border-radius: 999px;
  background: #ffffff;
  color: #525252;
  font-size: 12px;
  padding: 5px 10px;
}

.pill--success {
  border-color: #a8d5c4;
  background: #eefaf5;
  color: #116149;
}

.pill--warning {
  border-color: #f0d29c;
  background: #fff8e8;
  color: #8a5a00;
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

.inline-error {
  border: 1px solid #f0b6aa;
  border-radius: 8px;
  background: #fff1ee;
  color: #8f2f22;
  font-size: 13px;
  line-height: 1.5;
  padding: 9px 11px;
}
</style>
