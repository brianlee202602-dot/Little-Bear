<script setup lang="ts">
import type { KnowledgeBaseAdminContext } from "@/features/knowledge/knowledgeAdminContext";
import KnowledgeBaseCreateForm from "@/features/knowledge/KnowledgeBaseCreateForm.vue";
import KnowledgeBaseDeletePanel from "@/features/knowledge/KnowledgeBaseDeletePanel.vue";
import KnowledgeBaseIndexRebuildPanel from "@/features/knowledge/KnowledgeBaseIndexRebuildPanel.vue";
import KnowledgeBaseUploadForm from "@/features/knowledge/KnowledgeBaseUploadForm.vue";

const props = defineProps<{
  model: KnowledgeBaseAdminContext;
}>();

const model = props.model;
const {
  activeDepartments,
  activeFolders,
  canCreateKnowledgeBase,
  canDeleteSelectedKnowledgeBase,
  canImportDocuments,
  canReplaceSelectedKnowledgeBasePermissions,
  canRebuildSelectedKnowledgeBaseIndex,
  canUpdateSelectedKnowledgeBase,
  canUploadImportFiles,
  clearImportFiles,
  closeKnowledgeBaseModal,
  deleteSelectedKnowledgeBase,
  documentVisibilityLabel,
  formatDepartmentById,
  formatDepartmentLabel,
  formatFileSize,
  formatFolderLabel,
  formatKnowledgeBaseLabel,
  formatStatusOption,
  importAdminBusy,
  importAdminFeedback,
  importFileInputKey,
  importUploadForm,
  importUploadPermissionParentConflict,
  knowledgeBaseCreateForm,
  knowledgeBaseDangerForm,
  knowledgeBaseEditForm,
  knowledgeBaseIndexForm,
  knowledgeBaseModalMode,
  knowledgeBasePermissionForm,
  knowledgeBaseVisibilityLabel,
  onImportFilesChange,
  onKnowledgeBaseCreateAccessDepartmentChange,
  onKnowledgeBasePermissionAccessDepartmentChange,
  optionSearchForm,
  rebuildSelectedKnowledgeBaseIndex,
  refreshDepartmentOptionsFromSearch,
  refreshFolderOptionsFromSearch,
  selectedImportFiles,
  selectedImportKnowledgeBase,
  selectedKnowledgeBase,
  submitCreateKnowledgeBase,
  submitDocumentUpload,
  submitKnowledgeBasePermissions,
  submitPatchKnowledgeBase,
  toneClass,
} = props.model;
</script>

<template>
      <div
        v-if="knowledgeBaseModalMode"
        class="modal-backdrop"
        role="presentation"
        @click.self="closeKnowledgeBaseModal"
      >
        <section class="modal modal--wide" role="dialog" aria-modal="true" aria-labelledby="knowledge-base-modal-title">
          <header class="modal__header">
            <div>
              <p class="eyebrow">知识库管理</p>
              <h3 id="knowledge-base-modal-title">
                {{
                  knowledgeBaseModalMode === "create"
                    ? "新增知识库"
                    : knowledgeBaseModalMode === "edit"
                      ? "编辑知识库"
                      : knowledgeBaseModalMode === "permissions"
                        ? "权限策略"
                        : knowledgeBaseModalMode === "upload"
                          ? "添加文件"
                          : knowledgeBaseModalMode === "rebuildIndex"
                            ? "重建索引"
                            : "删除知识库"
                }}
              </h3>
            </div>
            <button class="button button--secondary button--small" type="button" @click="closeKnowledgeBaseModal">
              关闭
            </button>
          </header>

          <KnowledgeBaseCreateForm
            v-if="knowledgeBaseModalMode === 'create'"
            :model="model"
          />

          <form v-else-if="knowledgeBaseModalMode === 'edit' && selectedKnowledgeBase" @submit.prevent="submitPatchKnowledgeBase">
            <div class="modal__body">
              <dl class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>知识库</dt>
                  <dd>{{ formatKnowledgeBaseLabel(selectedKnowledgeBase) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>所属部门</dt>
                  <dd>{{ formatDepartmentById(selectedKnowledgeBase.owner_department_id) }}</dd>
                </div>
              </dl>
              <div v-if="importAdminFeedback" :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]">
                {{ importAdminFeedback.message }}
              </div>
              <div class="form-grid form-grid--compact form-grid--modal">
                <div class="field field--full">
                  <span class="field__label">部门选项</span>
                  <p class="field__hint">按部门名称搜索，当前已选部门会保留在列表中。</p>
                  <div class="selector-search">
                    <input
                      v-model.trim="optionSearchForm.departmentKeyword"
                      class="control control--compact"
                      type="search"
                      placeholder="搜索部门"
                    />
                    <button class="button button--secondary button--small" type="button" @click="refreshDepartmentOptionsFromSearch">
                      查询部门
                    </button>
                  </div>
                </div>
                <label class="field">
                  <span class="field__label">知识库名称</span>
                  <p class="field__hint">修改不会影响已有文档内容和索引版本。</p>
                  <input v-model.trim="knowledgeBaseEditForm.name" class="control" type="text" required />
                </label>
                <label class="field">
                  <span class="field__label">状态</span>
                  <p class="field__hint">禁用或归档会影响后续查询和导入可用性。</p>
                  <select v-model="knowledgeBaseEditForm.status" class="control">
                    <option value="active">{{ formatStatusOption("active") }}</option>
                    <option value="disabled">{{ formatStatusOption("disabled") }}</option>
                    <option value="archived">{{ formatStatusOption("archived") }}</option>
                  </select>
                </label>
                <label class="field">
                  <span class="field__label">知识库可见性</span>
                  <p class="field__hint">从受限可见扩大到 enterprise 需要显式确认。</p>
                  <select v-model="knowledgeBaseEditForm.kbVisibility" class="control">
                    <option value="enterprise">企业可见</option>
                    <option value="department_acl">指定部门可见</option>
                    <option value="private">私密可见</option>
                  </select>
                </label>
                <label class="field">
                  <span class="field__label">默认文档权限</span>
                  <p class="field__hint">只影响后续导入文件，不批量修改已有文档。</p>
                  <select v-model="knowledgeBaseEditForm.defaultDocumentVisibility" class="control">
                    <option value="department">部门可见</option>
                    <option value="enterprise">企业可见</option>
                  </select>
                </label>
                <label class="field">
                  <span class="field__label">默认文档所属部门</span>
                  <p class="field__hint">默认文档权限为 department 时使用。</p>
                  <select
                    v-if="activeDepartments.length"
                    v-model="knowledgeBaseEditForm.defaultDocumentOwnerDepartmentId"
                    class="control"
                  >
                    <option value="">请选择部门</option>
                    <option v-for="department in activeDepartments" :key="department.id" :value="department.id">
                      {{ formatDepartmentLabel(department) }}
                    </option>
                  </select>
                  <input
                    v-else
                    v-model.trim="knowledgeBaseEditForm.defaultDocumentOwnerDepartmentId"
                    class="control"
                    type="text"
                    placeholder="请选择或输入部门"
                  />
                </label>
                <label class="field">
                  <span class="field__label">配置作用域</span>
                  <p class="field__hint">可留空；仅保存配置作用域，不直接发布配置。</p>
                  <input v-model.trim="knowledgeBaseEditForm.configScopeId" class="control" type="text" />
                </label>
                <label
                  v-if="
                    selectedKnowledgeBase.kb_visibility !== 'enterprise' &&
                    knowledgeBaseEditForm.kbVisibility === 'enterprise'
                  "
                  class="confirm confirm--inline modal-confirm"
                >
                  <input v-model="knowledgeBaseEditForm.confirmedVisibilityExpand" type="checkbox" />
                  <span>确认将知识库可见性扩大到企业</span>
                </label>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeKnowledgeBaseModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canUpdateSelectedKnowledgeBase">
                {{ importAdminBusy.updating ? "保存中..." : "保存知识库" }}
              </button>
            </footer>
          </form>

          <form
            v-else-if="knowledgeBaseModalMode === 'permissions' && selectedKnowledgeBase"
            @submit.prevent="submitKnowledgeBasePermissions"
          >
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
                    默认文档{{ documentVisibilityLabel(selectedKnowledgeBase.default_document_visibility) }} /
                    {{ formatDepartmentById(selectedKnowledgeBase.default_document_owner_department_id) }}
                  </dd>
                </div>
              </dl>
              <div v-if="importAdminFeedback" :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]">
                {{ importAdminFeedback.message }}
              </div>
              <div class="form-grid form-grid--compact form-grid--modal">
                <div class="field field--full">
                  <span class="field__label">部门选项</span>
                  <p class="field__hint">按部门名称搜索，当前已选部门会保留在列表中。</p>
                  <div class="selector-search">
                    <input
                      v-model.trim="optionSearchForm.departmentKeyword"
                      class="control control--compact"
                      type="search"
                      placeholder="搜索部门"
                    />
                    <button class="button button--secondary button--small" type="button" @click="refreshDepartmentOptionsFromSearch">
                      查询部门
                    </button>
                  </div>
                </div>
                <label class="field">
                  <span class="field__label">知识库可见性</span>
                  <p class="field__hint">控制知识库是否出现在用户列表中，以及是否可被选择查询。</p>
                  <select v-model="knowledgeBasePermissionForm.kbVisibility" class="control">
                    <option value="enterprise">企业可见</option>
                    <option value="department_acl">指定部门可见</option>
                    <option value="private">私密可见</option>
                  </select>
                </label>
                <label class="field">
                  <span class="field__label">默认文档权限</span>
                  <p class="field__hint">只影响后续导入文件；已有文档权限请在文档权限弹窗中修改。</p>
                  <select v-model="knowledgeBasePermissionForm.defaultDocumentVisibility" class="control">
                    <option value="department">部门可见</option>
                    <option value="enterprise">企业可见</option>
                  </select>
                </label>
                <label class="field">
                  <span class="field__label">默认文档所属部门</span>
                  <p class="field__hint">当默认文档权限为 department 时，该部门必须具备知识库查询权限。</p>
                  <select
                    v-if="activeDepartments.length"
                    v-model="knowledgeBasePermissionForm.defaultDocumentOwnerDepartmentId"
                    class="control"
                  >
                    <option value="">请选择部门</option>
                    <option v-for="department in activeDepartments" :key="department.id" :value="department.id">
                      {{ formatDepartmentLabel(department) }}
                    </option>
                  </select>
                  <input
                    v-else
                    v-model.trim="knowledgeBasePermissionForm.defaultDocumentOwnerDepartmentId"
                    class="control"
                    type="text"
                    placeholder="请选择或输入部门"
                  />
                </label>
                <fieldset
                  v-if="knowledgeBasePermissionForm.kbVisibility !== 'enterprise'"
                  class="field field--full checkbox-list"
                >
                  <legend class="field__label">可访问部门</legend>
                  <label v-for="department in activeDepartments" :key="department.id" class="check-row">
                    <input
                      type="checkbox"
                      :checked="knowledgeBasePermissionForm.accessDepartmentIds.includes(department.id)"
                      @change="onKnowledgeBasePermissionAccessDepartmentChange(department.id, $event)"
                    />
                    <span>{{ formatDepartmentLabel(department) }}</span>
                  </label>
                </fieldset>
                <label class="confirm confirm--inline modal-confirm">
                  <input v-model="knowledgeBasePermissionForm.confirmedReplace" type="checkbox" />
                  <span>确认替换知识库权限策略</span>
                </label>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeKnowledgeBaseModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canReplaceSelectedKnowledgeBasePermissions">
                {{ importAdminBusy.updatingPermissions ? "保存中..." : "保存权限" }}
              </button>
            </footer>
          </form>

          <KnowledgeBaseIndexRebuildPanel
            v-else-if="knowledgeBaseModalMode === 'rebuildIndex'"
            :model="model"
          />

          <KnowledgeBaseUploadForm
            v-else-if="knowledgeBaseModalMode === 'upload'"
            :model="model"
          />

          <KnowledgeBaseDeletePanel
            v-else-if="knowledgeBaseModalMode === 'delete'"
            :model="model"
          />
        </section>
      </div>


</template>
