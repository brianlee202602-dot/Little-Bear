<script setup lang="ts">
import type { KnowledgeBaseAdminContext } from "@/features/knowledge/knowledgeAdminContext";

const props = defineProps<{
  model: KnowledgeBaseAdminContext;
}>();

const {
  activeDepartments,
  canCreateKnowledgeBase,
  closeKnowledgeBaseModal,
  formatDepartmentLabel,
  importAdminBusy,
  importAdminFeedback,
  knowledgeBaseCreateForm,
  onKnowledgeBaseCreateAccessDepartmentChange,
  optionSearchForm,
  refreshDepartmentOptionsFromSearch,
  submitCreateKnowledgeBase,
} = props.model;
</script>

<template>
          <form @submit.prevent="submitCreateKnowledgeBase">
            <div class="modal__body">
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
                  <p class="field__hint">用于管理后台和用户查询入口展示。</p>
                  <input v-model.trim="knowledgeBaseCreateForm.name" class="control" type="text" required />
                </label>
                <label class="field">
                  <span class="field__label">管理部门</span>
                  <p class="field__hint">仅表示管理归属，不等于访问边界。</p>
                  <select
                    v-if="activeDepartments.length"
                    v-model="knowledgeBaseCreateForm.ownerDepartmentId"
                    class="control"
                    required
                  >
                    <option value="">请选择部门</option>
                    <option v-for="department in activeDepartments" :key="department.id" :value="department.id">
                      {{ formatDepartmentLabel(department) }}
                    </option>
                  </select>
                  <input
                    v-else
                    v-model.trim="knowledgeBaseCreateForm.ownerDepartmentId"
                    class="control"
                    type="text"
                    placeholder="请选择或输入部门"
                    required
                  />
                </label>
                <label class="field">
                  <span class="field__label">知识库可见性</span>
                  <p class="field__hint">董事会、法务等敏感知识库应使用指定部门可见。</p>
                  <select v-model="knowledgeBaseCreateForm.kbVisibility" class="control">
                    <option value="enterprise">企业可见</option>
                    <option value="department_acl">指定部门可见</option>
                    <option value="private">私密可见</option>
                  </select>
                </label>
                <label class="field">
                  <span class="field__label">默认文档权限</span>
                  <p class="field__hint">新导入文件默认使用该文档权限，可在导入后单独调整。</p>
                  <select v-model="knowledgeBaseCreateForm.defaultDocumentVisibility" class="control">
                    <option value="department">部门可见</option>
                    <option value="enterprise">企业可见</option>
                  </select>
                </label>
                <label class="field">
                  <span class="field__label">默认文档所属部门</span>
                  <p class="field__hint">当默认文档权限为 department 时，该部门必须能查询此知识库。</p>
                  <select
                    v-if="activeDepartments.length"
                    v-model="knowledgeBaseCreateForm.defaultDocumentOwnerDepartmentId"
                    class="control"
                  >
                    <option value="">请选择部门</option>
                    <option v-for="department in activeDepartments" :key="department.id" :value="department.id">
                      {{ formatDepartmentLabel(department) }}
                    </option>
                  </select>
                  <input
                    v-else
                    v-model.trim="knowledgeBaseCreateForm.defaultDocumentOwnerDepartmentId"
                    class="control"
                    type="text"
                    placeholder="请选择或输入部门"
                  />
                </label>
                <fieldset
                  v-if="knowledgeBaseCreateForm.kbVisibility !== 'enterprise'"
                  class="field field--full checkbox-list"
                >
                  <legend class="field__label">可访问部门</legend>
                  <label v-for="department in activeDepartments" :key="department.id" class="check-row">
                    <input
                      type="checkbox"
                      :checked="knowledgeBaseCreateForm.accessDepartmentIds.includes(department.id)"
                      @change="onKnowledgeBaseCreateAccessDepartmentChange(department.id, $event)"
                    />
                    <span>{{ formatDepartmentLabel(department) }}</span>
                  </label>
                </fieldset>
                <label class="field">
                  <span class="field__label">配置作用域</span>
                  <p class="field__hint">可留空；后续用于按知识库覆盖模型或索引配置。</p>
                  <input v-model.trim="knowledgeBaseCreateForm.configScopeId" class="control" type="text" />
                </label>
                <label
                  v-if="knowledgeBaseCreateForm.kbVisibility === 'enterprise'"
                  class="confirm confirm--inline modal-confirm"
                >
                  <input v-model="knowledgeBaseCreateForm.confirmedEnterpriseVisibility" type="checkbox" />
                  <span>确认创建企业可见知识库</span>
                </label>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeKnowledgeBaseModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canCreateKnowledgeBase">
                {{ importAdminBusy.creating ? "创建中..." : "创建知识库" }}
              </button>
            </footer>
          </form>
</template>
