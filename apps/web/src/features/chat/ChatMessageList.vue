<script setup lang="ts">
import type { CitationData } from "@/api/query";
import { displayMessageContent, formatConfidence } from "@/utils/display";

import type { ChatMessage } from "./types";

const props = defineProps<{
  messages: ChatMessage[];
  hasMore: boolean;
  loadingOlder: boolean;
  messageTotal: number;
  knowledgeBaseCount: number;
  selectedKnowledgeBaseCount: number;
}>();

const emit = defineEmits<{
  (event: "loadOlder"): void;
  (event: "openCitation", citation: CitationData): void;
}>();
</script>

<template>
  <div class="message-scroll">
    <button
      v-if="props.messages.length && props.hasMore"
      class="conversation-load-more"
      type="button"
      :disabled="props.loadingOlder"
      @click="emit('loadOlder')"
    >
      {{
        props.loadingOlder
          ? "加载中"
          : `加载更早消息（${props.messages.length}/${props.messageTotal}）`
      }}
    </button>

    <section v-if="!props.messages.length" class="welcome">
      <h2>今天想查询什么？</h2>
      <p v-if="props.knowledgeBaseCount">
        已选择 {{ props.selectedKnowledgeBaseCount }} 个知识库，可以直接输入问题。
      </p>
      <p v-else>当前账号暂无可查询知识库，请联系管理员授权或创建知识库。</p>
    </section>

    <article
      v-for="message in props.messages"
      :key="message.id"
      :class="['message', message.role === 'user' ? 'message--user' : 'message--assistant']"
    >
      <div v-if="message.role === 'user'" class="bubble">{{ message.content }}</div>
      <template v-else>
        <div class="assistant-avatar">LB</div>
        <div class="assistant-content">
          <div class="answer-text">
            <p v-if="message.content" :class="{ 'error-text': message.status === 'error' }">
              {{ displayMessageContent(message.content) }}
            </p>
            <p v-else class="muted">正在生成回答...</p>
          </div>

          <div v-if="message.degradeReason || message.confidence" class="result-meta">
            <span :class="['pill', message.degraded ? 'pill--warning' : 'pill--success']">
              {{ message.degraded ? "已降级" : "正常" }}
            </span>
            <span v-if="message.confidence" class="pill">
              置信度 {{ formatConfidence(message.confidence) }}
            </span>
            <span v-if="message.degradeReason" class="pill pill--warning">
              {{ message.degradeReason }}
            </span>
          </div>

          <section v-if="message.citations.length" class="citation-strip">
            <button
              v-for="citation in message.citations"
              :key="citation.source_id"
              class="citation-chip"
              type="button"
              @click="emit('openCitation', citation)"
            >
              <strong>{{ citation.title }}</strong>
              <span>页 {{ citation.page_start }}-{{ citation.page_end }}</span>
            </button>
          </section>
        </div>
      </template>
    </article>

    <slot />
  </div>
</template>

<style scoped>
.message-scroll {
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 24px;
  overflow: auto;
  padding: 48px clamp(20px, 7vw, 96px) 28px;
}

.conversation-load-more {
  display: block;
  width: fit-content;
  margin: 18px auto 8px;
  border: 1px solid #d4d4d4;
  border-radius: 999px;
  background: #ffffff;
  color: #525252;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  padding: 8px 14px;
}

.conversation-load-more:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.welcome {
  min-height: 42vh;
  display: grid;
  place-content: center;
  gap: 12px;
  text-align: center;
}

.welcome h2,
.welcome p {
  margin: 0;
}

.welcome h2 {
  font-size: 28px;
  line-height: 1.2;
}

.welcome p {
  color: #666666;
  line-height: 1.6;
}

.message {
  display: flex;
  gap: 14px;
}

.message--user {
  justify-content: flex-end;
}

.bubble {
  max-width: min(720px, 82%);
  border-radius: 18px;
  background: #f3f3f3;
  padding: 12px 16px;
  line-height: 1.65;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.message--assistant {
  max-width: 920px;
}

.assistant-avatar {
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  margin-top: 4px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #111111;
  color: #ffffff;
  font-size: 13px;
  font-weight: 800;
}

.assistant-content {
  min-width: 0;
  display: grid;
  gap: 14px;
}

.answer-text {
  line-height: 1.78;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.error-text {
  color: #8f2f22;
}

.muted {
  color: #737373;
  font-size: 12px;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
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

.citation-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.citation-chip {
  max-width: 280px;
  border: 1px solid #dcdcdc;
  border-radius: 8px;
  background: #ffffff;
  color: #171717;
  cursor: pointer;
  display: grid;
  gap: 3px;
  font: inherit;
  padding: 9px 11px;
  text-align: left;
}

.citation-chip:hover {
  background: #f7f7f7;
}

.citation-chip strong {
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.citation-chip span {
  color: #737373;
  font-size: 12px;
}

@media (max-width: 560px) {
  .message-scroll {
    padding-left: 14px;
    padding-right: 14px;
  }

  .bubble {
    max-width: 94%;
  }
}
</style>
