<script setup lang="ts">
import type { KnowledgeBaseAdminContext } from "@/features/knowledge/knowledgeAdminContext";

const props = defineProps<{
  model: KnowledgeBaseAdminContext;
}>();

const {
  activeFolders,
  canImportDocuments,
  canUploadImportFiles,
  clearImportFiles,
  closeKnowledgeBaseModal,
  formatDepartmentById,
  formatFileSize,
  formatFolderLabel,
  formatKnowledgeBaseLabel,
  importAdminBusy,
  importAdminFeedback,
  importFileInputKey,
  importUploadForm,
  importUploadPermissionParentConflict,
  onImportFilesChange,
  optionSearchForm,
  refreshFolderOptionsFromSearch,
  selectedImportFiles,
  selectedImportKnowledgeBase,
  submitDocumentUpload,
  toneClass,
} = props.model;
</script>

<template>
  <form
    v-if="selectedImportKnowledgeBase"
    @submit.prevent="submitDocumentUpload"
  >
    <div class="modal__body">
      <dl class="summary summary--compact modal-summary">
        <div class="summary__row">
          <dt>目标知识库</dt>
          <dd>{{ formatKnowledgeBaseLabel(selectedImportKnowledgeBase) }}</dd>
        </div>
        <div class="summary__row">
          <dt>默认文档部门</dt>
          <dd>{{ formatDepartmentById(selectedImportKnowledgeBase.default_document_owner_department_id) }}</dd>
        </div>
      </dl>
      <div v-if="importAdminFeedback" :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]">
        {{ importAdminFeedback.message }}
      </div>
      <div class="upload-panel upload-panel--modal">
        <section class="upload-panel__main">
          <label class="field">
            <span class="field__label">文档可见性</span>
            <p class="field__hint">默认继承知识库的默认文档权限；department 会按默认文档所属部门可见。</p>
            <select
              v-model="importUploadForm.visibility"
              class="control"
              :disabled="!canImportDocuments || importAdminBusy.uploading"
            >
              <option value="department">部门可见</option>
              <option value="enterprise">企业可见</option>
            </select>
            <p v-if="importUploadPermissionParentConflict" :class="toneClass('warning')">
              {{ importUploadPermissionParentConflict }}
            </p>
          </label>
          <label class="field">
            <span class="field__label">目标文件夹</span>
            <p class="field__hint">留空表示导入到根目录；文件夹需要先在当前知识库中创建。</p>
            <div class="selector-search">
              <input
                v-model.trim="optionSearchForm.folderKeyword"
                class="control control--compact"
                type="search"
                placeholder="搜索文件夹"
                :disabled="!canImportDocuments || importAdminBusy.uploading"
              />
              <button
                class="button button--secondary button--small"
                type="button"
                :disabled="!canImportDocuments || importAdminBusy.uploading"
                @click="refreshFolderOptionsFromSearch"
              >
                查询文件夹
              </button>
            </div>
            <select
              v-if="activeFolders.length"
              v-model="importUploadForm.folderId"
              class="control"
              :disabled="!canImportDocuments || importAdminBusy.uploading"
            >
              <option value="">根目录</option>
              <option v-for="folder in activeFolders" :key="folder.id" :value="folder.id">
                {{ formatFolderLabel(folder) }}
              </option>
            </select>
            <input
              v-else
              v-model.trim="importUploadForm.folderId"
              class="control"
              type="text"
              placeholder="可选目标文件夹"
              :disabled="!canImportDocuments || importAdminBusy.uploading"
            />
          </label>
          <label class="field">
            <span class="field__label">幂等键</span>
            <p class="field__hint">重复测试同一文件时可留空；需要防重提交时填写稳定键。</p>
            <input
              v-model.trim="importUploadForm.idempotencyKey"
              class="control"
              type="text"
              :disabled="!canImportDocuments || importAdminBusy.uploading"
            />
          </label>
          <label class="field field--full">
            <span class="field__label">选择文件</span>
            <p class="field__hint">支持 PDF、DOCX、UTF-8 文本和 Markdown；大小限制由 active_config.import 控制。</p>
            <input
              :key="importFileInputKey"
              class="control control--file"
              type="file"
              multiple
              accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
              :disabled="!canImportDocuments || importAdminBusy.uploading"
              @change="onImportFilesChange"
            />
          </label>
        </section>

        <section class="upload-panel__side">
          <h4>待上传文件</h4>
          <div v-if="selectedImportFiles.length" class="file-list">
            <article
              v-for="file in selectedImportFiles"
              :key="`${file.name}-${file.size}-${file.lastModified}`"
              class="file-row"
            >
              <strong>{{ file.name }}</strong>
              <span>{{ formatFileSize(file.size) }}</span>
            </article>
          </div>
          <p v-else class="empty-state empty-state--plain">尚未选择文件。</p>
          <dl class="summary summary--compact upload-summary">
            <div class="summary__row">
              <dt>文件数</dt>
              <dd>{{ selectedImportFiles.length }}</dd>
            </div>
          </dl>
          <div class="upload-actions">
            <button
              class="button button--secondary"
              type="button"
              @click="clearImportFiles"
              :disabled="!selectedImportFiles.length || importAdminBusy.uploading"
            >
              清空文件
            </button>
            <button class="button" type="submit" :disabled="!canUploadImportFiles">
              {{ importAdminBusy.uploading ? "上传中..." : "创建导入任务" }}
            </button>
          </div>
        </section>
      </div>
    </div>
    <footer class="modal__footer">
      <button class="button button--secondary" type="button" @click="closeKnowledgeBaseModal">
        取消
      </button>
      <button class="button" type="submit" :disabled="!canUploadImportFiles">
        {{ importAdminBusy.uploading ? "上传中..." : "创建导入任务" }}
      </button>
    </footer>
  </form>
</template>
