<script setup lang="ts">
import { computed } from "vue";

import type { AdminDepartmentOptionData } from "@/api/departments";
import type { AdminKnowledgeBaseOptionData } from "@/api/knowledgeBases";
import type { AdminAssignableRoleOptionData, AdminRoleBindingData } from "@/api/roles";
import type { AdminUserData } from "@/api/users";
import PaginationBar from "@/components/PaginationBar.vue";

type Feedback = {
  tone: "success" | "error" | "neutral";
  message: string;
};

type BusyState = {
  loading: boolean;
  updatingRoles: boolean;
};

type PaginationState = {
  page: number;
  pageSize: number;
  total: number;
};

type RoleBindingForm = {
  roleId: string;
  scopeId: string;
  confirmedHighRisk: boolean;
  confirmedRemoveAdmin: boolean;
};

type RoleScopeType = AdminAssignableRoleOptionData["scope_type"];

const props = defineProps<{
  open: boolean;
  selectedUser: AdminUserData | null;
  bindings: AdminRoleBindingData[];
  assignableRoles: AdminAssignableRoleOptionData[];
  activeDepartments: AdminDepartmentOptionData[];
  activeKnowledgeBases: AdminKnowledgeBaseOptionData[];
  roleKeyword: string;
  departmentKeyword: string;
  knowledgeBaseKeyword: string;
  selectedScopeType: RoleScopeType;
  roleBindingForm: RoleBindingForm;
  canManageRoles: boolean;
  canManageKnowledgeBases: boolean;
  canAdd: boolean;
  disabledReason: string;
  busy: BusyState;
  feedback: Feedback | null;
  pagination: PaginationState;
  pageSizeOptions: number[];
  formatRoleCodeLabel: (roleCode: string | null | undefined, fallback?: string) => string;
  formatRoleBindingScope: (binding: AdminRoleBindingData) => string;
  formatRoleLabel: (role: AdminAssignableRoleOptionData | null | undefined) => string;
  formatRoleScopeType: (scopeType: string | null | undefined) => string;
  formatDepartmentLabel: (department: AdminDepartmentOptionData | null | undefined) => string;
  formatKnowledgeBaseLabel: (knowledgeBase: AdminKnowledgeBaseOptionData | null | undefined) => string;
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "revoke", binding: AdminRoleBindingData): void;
  (event: "add"): void;
  (event: "roleChange", roleId: string): void;
  (event: "searchRoles"): void;
  (event: "searchDepartments"): void;
  (event: "searchKnowledgeBases"): void;
  (event: "update:roleKeyword", value: string): void;
  (event: "update:departmentKeyword", value: string): void;
  (event: "update:knowledgeBaseKeyword", value: string): void;
  (event: "update:scopeId", value: string): void;
  (event: "update:confirmedHighRisk", value: boolean): void;
  (event: "update:confirmedRemoveAdmin", value: boolean): void;
  (event: "update:page", value: number): void;
  (event: "update:pageSize", value: number): void;
}>();

const roleKeywordModel = computed({
  get: () => props.roleKeyword,
  set: (value: string) => emit("update:roleKeyword", value),
});
const departmentKeywordModel = computed({
  get: () => props.departmentKeyword,
  set: (value: string) => emit("update:departmentKeyword", value),
});
const knowledgeBaseKeywordModel = computed({
  get: () => props.knowledgeBaseKeyword,
  set: (value: string) => emit("update:knowledgeBaseKeyword", value),
});
const scopeId = computed({
  get: () => props.roleBindingForm.scopeId,
  set: (value: string) => emit("update:scopeId", value),
});
const confirmedHighRisk = computed({
  get: () => props.roleBindingForm.confirmedHighRisk,
  set: (value: boolean) => emit("update:confirmedHighRisk", value),
});
const confirmedRemoveAdmin = computed({
  get: () => props.roleBindingForm.confirmedRemoveAdmin,
  set: (value: boolean) => emit("update:confirmedRemoveAdmin", value),
});
</script>

<template>
  <div v-if="props.open" class="modal-backdrop" role="presentation" @click.self="emit('close')">
    <section class="modal modal--wide" role="dialog" aria-modal="true" aria-labelledby="role-binding-modal-title">
      <header class="modal__header">
        <div>
          <p class="eyebrow">用户管理</p>
          <h3 id="role-binding-modal-title">维护角色绑定</h3>
        </div>
        <button class="button button--secondary button--small" type="button" @click="emit('close')">
          关闭
        </button>
      </header>

      <div v-if="props.selectedUser">
        <div class="modal__body modal__body--split">
          <section class="modal-pane">
            <h4>当前角色</h4>
            <div v-if="props.bindings.length" class="role-binding-list">
              <article v-for="binding in props.bindings" :key="binding.id" class="role-binding-row">
                <div>
                  <strong>{{ props.formatRoleCodeLabel(binding.role_code, binding.role_name ?? binding.role_id) }}</strong>
                  <span>{{ props.formatRoleBindingScope(binding) }}</span>
                </div>
                <button
                  class="button button--secondary button--small"
                  type="button"
                  :disabled="!props.canManageRoles || props.busy.updatingRoles"
                  @click="emit('revoke', binding)"
                >
                  撤销
                </button>
              </article>
            </div>
            <p v-else class="empty-state empty-state--plain">当前用户尚无可展示的角色绑定。</p>
            <PaginationBar
              v-if="props.pagination.total > 0"
              class="pagination-bar--compact"
              label="用户角色绑定分页"
              :page="props.pagination.page"
              :page-size="props.pagination.pageSize"
              :total="props.pagination.total"
              :page-size-options="props.pageSizeOptions"
              :disabled="props.busy.loading || props.busy.updatingRoles"
              @update:page="(page) => emit('update:page', page)"
              @update:page-size="(pageSize) => emit('update:pageSize', pageSize)"
            />
          </section>

          <section class="modal-pane">
            <h4>授予角色</h4>
            <div class="selector-search selector-search--stacked">
              <input
                v-model.trim="roleKeywordModel"
                class="control control--compact"
                type="search"
                placeholder="搜索角色"
              />
              <button class="button button--secondary button--small" type="button" @click="emit('searchRoles')">
                查询角色
              </button>
            </div>
            <label class="field field--full modal-field">
              <span class="field__label">角色</span>
              <p class="field__hint">企业级角色作用于全企业；部门管理员和知识库管理员必须选择具体作用域。</p>
              <select
                class="control"
                :value="props.roleBindingForm.roleId"
                :disabled="!props.canManageRoles"
                @change="emit('roleChange', ($event.target as HTMLSelectElement).value)"
              >
                <option value="">请选择角色</option>
                <option v-for="role in props.assignableRoles" :key="role.id" :value="role.id">
                  {{ props.formatRoleLabel(role) }} / {{ props.formatRoleScopeType(role.scope_type) }}
                </option>
              </select>
            </label>
            <label v-if="props.selectedScopeType === 'department'" class="field field--full modal-field">
              <span class="field__label">部门作用域</span>
              <p class="field__hint">该用户只会在选定部门范围内获得部门管理员权限。</p>
              <div class="selector-search">
                <input
                  v-model.trim="departmentKeywordModel"
                  class="control control--compact"
                  type="search"
                  placeholder="搜索部门"
                />
                <button class="button button--secondary button--small" type="button" @click="emit('searchDepartments')">
                  查询部门
                </button>
              </div>
              <select v-model="scopeId" class="control" :disabled="!props.canManageRoles">
                <option value="">请选择部门</option>
                <option v-for="department in props.activeDepartments" :key="department.id" :value="department.id">
                  {{ props.formatDepartmentLabel(department) }}
                </option>
              </select>
            </label>
            <label
              v-else-if="props.selectedScopeType === 'knowledge_base'"
              class="field field--full modal-field"
            >
              <span class="field__label">知识库作用域</span>
              <p class="field__hint">该用户只会在选定知识库范围内获得知识库、文档和导入管理权限。</p>
              <div class="selector-search">
                <input
                  v-model.trim="knowledgeBaseKeywordModel"
                  class="control control--compact"
                  type="search"
                  placeholder="搜索知识库"
                />
                <button class="button button--secondary button--small" type="button" @click="emit('searchKnowledgeBases')">
                  查询知识库
                </button>
              </div>
              <select v-model="scopeId" class="control" :disabled="!props.canManageRoles">
                <option value="">请选择知识库</option>
                <option v-for="knowledgeBase in props.activeKnowledgeBases" :key="knowledgeBase.id" :value="knowledgeBase.id">
                  {{ props.formatKnowledgeBaseLabel(knowledgeBase) }}
                </option>
              </select>
            </label>
            <p
              v-if="props.selectedScopeType === 'knowledge_base' && !props.canManageKnowledgeBases"
              class="empty-state empty-state--plain"
            >
              当前账号缺少 knowledge_base:manage，无法读取可绑定的知识库列表。
            </p>
            <label class="confirm confirm--inline modal-confirm">
              <input v-model="confirmedHighRisk" type="checkbox" />
              <span>确认授予高风险角色</span>
            </label>
            <label class="confirm confirm--inline modal-confirm">
              <input v-model="confirmedRemoveAdmin" type="checkbox" />
              <span>确认撤销系统管理员角色</span>
            </label>
            <button class="button" type="button" :disabled="!props.canAdd" @click="emit('add')">
              {{ props.busy.updatingRoles ? "处理中..." : "授予角色" }}
            </button>
            <p v-if="props.disabledReason" class="empty-state empty-state--plain">
              {{ props.disabledReason }}
            </p>
          </section>
          <div
            v-if="props.feedback"
            :class="['feedback feedback--wide', `feedback--${props.feedback.tone}`]"
          >
            {{ props.feedback.message }}
          </div>
        </div>
        <footer class="modal__footer">
          <button class="button button--secondary" type="button" @click="emit('close')">
            完成
          </button>
        </footer>
      </div>
    </section>
  </div>
</template>
