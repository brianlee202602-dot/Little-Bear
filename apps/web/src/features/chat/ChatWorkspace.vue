<script setup lang="ts">
import LoginPanel from "@/features/auth/LoginPanel.vue";
import ChatComposer from "@/features/chat/ChatComposer.vue";
import ChatMessageList from "@/features/chat/ChatMessageList.vue";
import ConversationList from "@/features/chat/ConversationList.vue";
import { useChatWorkspaceRuntime } from "@/features/chat/useChatWorkspaceRuntime";
import KnowledgeBaseSelector from "@/features/knowledge/KnowledgeBaseSelector.vue";
import SourcePreviewPanel from "@/features/sources/SourcePreviewPanel.vue";

const {
  activeMessages,
  activeRecord,
  authBusy,
  authFeedback,
  authenticated,
  busy,
  canSubmit,
  chatRecords,
  currentUser,
  deletingConversationId,
  form,
  hasMoreConversationMessages,
  hasMoreKnowledgeBases,
  hasMoreSourceChunks,
  highlightedSourceId,
  knowledgeBaseSelectorFeedback,
  knowledgeBases,
  loadingKnowledgeBases,
  loadingOlderMessages,
  loadingSource,
  loginForm,
  selectedKbIds,
  selectedKbLabel,
  selectedKnowledgeBases,
  sourceChunks,
  sourceChunkTotal,
  sourceDetail,
  sourceFeedback,
  sourceTitle,
  statusText,
  submitHint,
  cancelQuery,
  clearKnowledgeBaseSelection,
  loadMoreKnowledgeBases,
  loadMoreSourceChunks,
  loadOlderConversationMessages,
  logout,
  openCitation,
  refreshKnowledgeBases,
  removeChatRecord,
  selectAllKnowledgeBases,
  selectChatRecord,
  startNewChat,
  submitLogin,
  submitQuery,
  toggleKnowledgeBase,
} = useChatWorkspaceRuntime();
</script>

<template>
  <main class="chat-shell">
    <aside class="sidebar">
      <header class="brand-row">
        <div>
          <p class="eyebrow">Little Bear</p>
          <h1>知识库助手</h1>
        </div>
        <button class="icon-button" type="button" title="新建对话" @click="startNewChat">
          +
        </button>
      </header>

      <ConversationList
        :records="chatRecords"
        :active-record-id="activeRecord?.id ?? ''"
        :deleting-conversation-id="deletingConversationId"
        @new="startNewChat"
        @select="selectChatRecord"
        @remove="removeChatRecord"
      />

      <KnowledgeBaseSelector
        :authenticated="authenticated"
        :label="selectedKbLabel"
        :items="knowledgeBases"
        :selected-ids="selectedKbIds"
        :has-more="hasMoreKnowledgeBases"
        :loading="loadingKnowledgeBases"
        :feedback="knowledgeBaseSelectorFeedback"
        @refresh="refreshKnowledgeBases()"
        @select-all="selectAllKnowledgeBases"
        @clear="clearKnowledgeBaseSelection"
        @toggle="toggleKnowledgeBase"
        @load-more="loadMoreKnowledgeBases"
      />

      <footer class="account-area">
        <div v-if="authenticated && currentUser" class="account-card">
          <div class="avatar">{{ (currentUser.name || currentUser.username).slice(0, 1) }}</div>
          <div>
            <strong>{{ currentUser.name || currentUser.username }}</strong>
            <span>{{ currentUser.username }}</span>
          </div>
          <button
            class="text-button"
            type="button"
            :disabled="authBusy.loggingOut"
            @click="logout"
          >
            退出
          </button>
        </div>
      </footer>
    </aside>

    <section class="chat-panel">
      <header class="chat-topbar">
        <div>
          <span class="scope-badge">{{ selectedKbLabel }}</span>
          <strong>{{ statusText }}</strong>
        </div>
        <div class="query-options">
          <div class="segmented" aria-label="查询模式">
            <button
              type="button"
              :class="{ active: form.mode === 'answer' }"
              @click="form.mode = 'answer'"
            >
              问答
            </button>
            <button
              type="button"
              :class="{ active: form.mode === 'search' }"
              @click="form.mode = 'search'"
            >
              检索
            </button>
          </div>
          <label class="small-input">
            <span>Top K</span>
            <input v-model.number="form.topK" type="number" min="1" max="50" />
          </label>
        </div>
      </header>

      <LoginPanel
        v-if="!authenticated"
        v-model:username="loginForm.username"
        v-model:password="loginForm.password"
        :busy="authBusy.loggingIn"
        :restoring="authBusy.restoring"
        :feedback="authFeedback"
        @submit="submitLogin"
      />

      <template v-else>
        <ChatMessageList
          :messages="activeMessages"
          :has-more="hasMoreConversationMessages"
          :loading-older="loadingOlderMessages"
          :message-total="activeRecord?.messageTotal ?? 0"
          :knowledge-base-count="knowledgeBases.length"
          :selected-knowledge-base-count="selectedKnowledgeBases.length"
          @load-older="loadOlderConversationMessages"
          @open-citation="openCitation"
        >
          <SourcePreviewPanel
            :detail="sourceDetail"
            :chunks="sourceChunks"
            :title="sourceTitle"
            :feedback="sourceFeedback"
            :highlighted-chunk-id="highlightedSourceId"
            :has-more="hasMoreSourceChunks"
            :loading="loadingSource"
            :total="sourceChunkTotal"
            @load-more="loadMoreSourceChunks"
          />
        </ChatMessageList>

        <ChatComposer
          v-model:query="form.query"
          v-model:streaming="form.streaming"
          v-model:include-sources="form.includeSources"
          :disabled="!knowledgeBases.length"
          :busy="busy"
          :can-submit="canSubmit"
          :hint="submitHint"
          @submit="submitQuery"
          @cancel="cancelQuery"
        />
      </template>
    </section>
  </main>
</template>
