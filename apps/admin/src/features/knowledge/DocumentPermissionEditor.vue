<script setup lang="ts">
import type { KnowledgeBaseAdminContext } from "@/features/knowledge/knowledgeAdminContext";

const props = defineProps<{
  model: KnowledgeBaseAdminContext;
}>();

const {
  activeDepartments,
  canReplaceSelectedDocumentPermissions,
  closeDocumentModal,
  documentPermissionForm,
  documentPermissionParentConflict,
  documentVisibilityLabel,
  formatDepartmentById,
  formatDepartmentLabel,
  formatKnowledgeBaseLabel,
  importAdminBusy,
  importAdminFeedback,
  knowledgeBaseVisibilityLabel,
  optionSearchForm,
  refreshDepartmentOptionsFromSearch,
  selectedAdminDocument,
  selectedDocumentParentKnowledgeBase,
  submitDocumentPermissions,
  toneClass,
} = props.model;
</script>

<template>
  <form v-if="selectedAdminDocument" @submit.prevent="submitDocumentPermissions">
    <div class="modal__body">
      <dl class="summary summary--compact modal-summary">
        <div class="summary__row">
          <dt>文档</dt>
          <dd>{{ selectedAdminDocument.title }}</dd>
        </div>
        <div class="summary__row">
          <dt>当前策略</dt>
          <dd>
            {{ documentVisibilityLabel(selectedAdminDocument.visibility) }} /
            {{ formatDepartmentById(selectedAdminDocument.owner_department_id) }}
          </dd>
        </div>
        <div v-if="selectedDocumentParentKnowledgeBase" class="summary__row">
          <dt>父知识库</dt>
          <dd>
            {{ formatKnowledgeBaseLabel(selectedDocumentParentKnowledgeBase) }}，
            {{ knowledgeBaseVisibilityLabel(selectedDocumentParentKnowledgeBase.kb_visibility) }} /
            默认文档{{
              documentVisibilityLabel(selectedDocumentParentKnowledgeBase.default_document_visibility)
            }}
          </dd>
        </div>
      </dl>
      <div
        v-if="importAdminFeedback"
        :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]"
      >
        {{ importAdminFeedback.message }}
      </div>
      <p v-if="documentPermissionParentConflict" :class="toneClass('warning')">
        {{ documentPermissionParentConflict }}
      </p>
      <div class="form-grid form-grid--compact form-grid--modal">
        <label class="field">
          <span class="field__label">可见性</span>
          <p class="field__hint">修改文档权限会触发权限快照更新；收紧时会写 access block。</p>
          <select v-model="documentPermissionForm.visibility" class="control">
            <option value="department">部门可见</option>
            <option value="enterprise">企业可见</option>
          </select>
        </label>
        <label class="field">
          <span class="field__label">所属部门</span>
          <p class="field__hint">部门可见时只有该部门成员可检索。</p>
          <div class="selector-search">
            <input
              v-model.trim="optionSearchForm.departmentKeyword"
              class="control control--compact"
              type="search"
              placeholder="搜索部门"
            />
            <button
              class="button button--secondary button--small"
              type="button"
              @click="refreshDepartmentOptionsFromSearch"
            >
              查询部门
            </button>
          </div>
          <select
            v-if="activeDepartments.length"
            v-model="documentPermissionForm.ownerDepartmentId"
            class="control"
          >
            <option value="">请选择部门</option>
            <option v-for="department in activeDepartments" :key="department.id" :value="department.id">
              {{ formatDepartmentLabel(department) }}
            </option>
          </select>
          <input
            v-else
            v-model.trim="documentPermissionForm.ownerDepartmentId"
            class="control"
            type="text"
            placeholder="请选择或输入部门"
          />
        </label>
        <label class="confirm confirm--inline modal-confirm">
          <input v-model="documentPermissionForm.confirmedReplace" type="checkbox" />
          <span>确认替换文档权限策略</span>
        </label>
      </div>
    </div>
    <footer class="modal__footer">
      <button class="button button--secondary" type="button" @click="closeDocumentModal">
        取消
      </button>
      <button class="button" type="submit" :disabled="!canReplaceSelectedDocumentPermissions">
        {{ importAdminBusy.updatingPermissions ? "保存中..." : "保存权限" }}
      </button>
    </footer>
  </form>

  <p v-else class="empty-state empty-state--plain">
    正在读取文档权限详情。
  </p>
</template>
