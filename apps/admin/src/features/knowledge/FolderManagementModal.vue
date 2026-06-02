<script setup lang="ts">
import type { KnowledgeBaseAdminContext } from "@/features/knowledge/knowledgeAdminContext";

const props = defineProps<{
  model: KnowledgeBaseAdminContext;
}>();

const {
  activeFolders,
  canCreateFolder,
  canDeleteSelectedFolder,
  canUpdateSelectedFolder,
  closeFolderModal,
  deleteSelectedFolder,
  folderCreateForm,
  folderDangerForm,
  folderEditForm,
  folderModalMode,
  folderParentOptions,
  formatFolderById,
  formatFolderLabel,
  formatKnowledgeBaseLabel,
  formatStatusOption,
  importAdminBusy,
  importAdminFeedback,
  optionSearchForm,
  refreshFolderOptionsFromSearch,
  selectedFolder,
  selectedKnowledgeBase,
  submitCreateFolder,
  submitPatchFolder,
} = props.model;
</script>

<template>
      <div
        v-if="folderModalMode"
        class="modal-backdrop"
        role="presentation"
        @click.self="closeFolderModal"
      >
        <section class="modal" role="dialog" aria-modal="true" aria-labelledby="folder-modal-title">
          <header class="modal__header">
            <div>
              <p class="eyebrow">文件夹管理</p>
              <h3 id="folder-modal-title">
                {{
                  folderModalMode === "create"
                    ? "新增文件夹"
                    : folderModalMode === "edit"
                      ? "编辑文件夹"
                      : "删除文件夹"
                }}
              </h3>
            </div>
            <button class="button button--secondary button--small" type="button" @click="closeFolderModal">
              关闭
            </button>
          </header>

          <form v-if="folderModalMode === 'create' && selectedKnowledgeBase" @submit.prevent="submitCreateFolder">
            <div class="modal__body">
              <dl class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>知识库</dt>
                  <dd>{{ formatKnowledgeBaseLabel(selectedKnowledgeBase) }}</dd>
                </div>
              </dl>
              <div v-if="importAdminFeedback" :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]">
                {{ importAdminFeedback.message }}
              </div>
              <div class="form-grid form-grid--compact form-grid--modal">
                <label class="field">
                  <span class="field__label">文件夹名称</span>
                  <p class="field__hint">同一父级下不能创建重名文件夹。</p>
                  <input v-model.trim="folderCreateForm.name" class="control" type="text" required />
                </label>
                <label class="field">
                  <span class="field__label">上级文件夹</span>
                  <p class="field__hint">留空表示根目录。</p>
                  <div class="selector-search">
                    <input
                      v-model.trim="optionSearchForm.folderKeyword"
                      class="control control--compact"
                      type="search"
                      placeholder="搜索文件夹"
                    />
                    <button class="button button--secondary button--small" type="button" @click="refreshFolderOptionsFromSearch">
                      查询文件夹
                    </button>
                  </div>
                  <select v-model="folderCreateForm.parentId" class="control">
                    <option value="">根目录</option>
                    <option v-for="folder in activeFolders" :key="folder.id" :value="folder.id">
                      {{ formatFolderLabel(folder) }}
                    </option>
                  </select>
                </label>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeFolderModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canCreateFolder">
                {{ importAdminBusy.managingFolder ? "创建中..." : "创建文件夹" }}
              </button>
            </footer>
          </form>

          <form v-else-if="folderModalMode === 'edit' && selectedFolder" @submit.prevent="submitPatchFolder">
            <div class="modal__body">
              <dl class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>文件夹</dt>
                  <dd>{{ formatFolderLabel(selectedFolder) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>当前上级</dt>
                  <dd>{{ formatFolderById(selectedFolder.parent_id) }}</dd>
                </div>
              </dl>
              <div v-if="importAdminFeedback" :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]">
                {{ importAdminFeedback.message }}
              </div>
              <div class="form-grid form-grid--compact form-grid--modal">
                <label class="field">
                  <span class="field__label">文件夹名称</span>
                  <p class="field__hint">重命名不会改变已导入文档内容。</p>
                  <input v-model.trim="folderEditForm.name" class="control" type="text" required />
                </label>
                <label class="field">
                  <span class="field__label">状态</span>
                  <p class="field__hint">禁用或归档会阻止后续文档导入到该目录。</p>
                  <select v-model="folderEditForm.status" class="control">
                    <option value="active">{{ formatStatusOption("active") }}</option>
                    <option value="disabled">{{ formatStatusOption("disabled") }}</option>
                    <option value="archived">{{ formatStatusOption("archived") }}</option>
                  </select>
                </label>
                <label class="field field--full">
                  <span class="field__label">上级文件夹</span>
                  <p class="field__hint">不能移动到自身或自身的子目录；后端会再次校验。</p>
                  <div class="selector-search">
                    <input
                      v-model.trim="optionSearchForm.folderKeyword"
                      class="control control--compact"
                      type="search"
                      placeholder="搜索文件夹"
                    />
                    <button class="button button--secondary button--small" type="button" @click="refreshFolderOptionsFromSearch">
                      查询文件夹
                    </button>
                  </div>
                  <select v-model="folderEditForm.parentId" class="control">
                    <option value="">根目录</option>
                    <option v-for="folder in folderParentOptions" :key="folder.id" :value="folder.id">
                      {{ formatFolderLabel(folder) }}
                    </option>
                  </select>
                </label>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeFolderModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canUpdateSelectedFolder">
                {{ importAdminBusy.managingFolder ? "保存中..." : "保存文件夹" }}
              </button>
            </footer>
          </form>

          <div v-else-if="folderModalMode === 'delete' && selectedFolder">
            <div class="modal__body">
              <div class="danger-panel">
                <h4>确认删除文件夹</h4>
                <p>
                  将删除 {{ formatFolderLabel(selectedFolder) }}，并写入 access block；该文件夹下文档的清理影响由后端任务处理。
                </p>
                <label class="confirm confirm--inline">
                  <input v-model="folderDangerForm.confirmedDelete" type="checkbox" />
                  <span>确认删除该文件夹</span>
                </label>
              </div>
              <div v-if="importAdminFeedback" :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]">
                {{ importAdminFeedback.message }}
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeFolderModal">
                取消
              </button>
              <button
                class="button button--danger"
                type="button"
                @click="deleteSelectedFolder"
                :disabled="!canDeleteSelectedFolder"
              >
                {{ importAdminBusy.managingFolder ? "删除中..." : "删除文件夹" }}
              </button>
            </footer>
          </div>
        </section>
      </div>


</template>
