<script setup lang="ts">
import type { AdminCurrentUserCapabilitiesData } from "@/api/auth";
import AuditLogPage from "@/features/audit/AuditLogPage.vue";
import type { AuditLogsRuntime } from "@/features/audit/useAuditLogs";
import { configSectionDefinitions } from "@/features/config/configFields";
import ConfigEditorModal from "@/features/config/ConfigEditorModal.vue";
import ConfigVersionDetailModal from "@/features/config/ConfigVersionDetailModal.vue";
import ConfigVersionList from "@/features/config/ConfigVersionList.vue";
import type { ConfigManagementRuntime } from "@/features/config/useConfigManagement";
import { formatStatusText, toneClass } from "@/utils/display";
import { changePaginationPage, changePaginationPageSize } from "@/utils/pagination";

const props = defineProps<{
  audit: AuditLogsRuntime;
  authenticated: boolean;
  canManageConfig: boolean;
  canReadAudit: boolean;
  canReadConfig: boolean;
  currentUser: AdminCurrentUserCapabilitiesData | null;
  pageSizeOptions: number[];
  refreshConfigAdminState: () => Promise<void>;
  runtime: ConfigManagementRuntime;
  userRoleLabels: string;
}>();

const {
  activeConfigVersion,
  activeConfigVersionRecord,
  archiveConfigVersionFromUi,
  canSaveSelectedConfigDraft,
  canValidateSelectedConfig,
  closeConfigModal,
  closeConfigVersionDetail,
  configBusy,
  configDetailModalOpen,
  configDraftItems,
  configEditorParseError,
  configFeedback,
  configForm,
  configModalMode,
  configModalTitle,
  configValidationResult,
  configVersionPagination,
  openConfigVersionDetail,
  openCreateConfigModal,
  openEditConfigVersion,
  paginatedConfigVersions,
  publishDraftVersion,
  saveSelectedDraft,
  selectedConfigDetailRecord,
  selectedConfigVersionRecord,
  updateConfigFieldFromCheckbox,
  updateConfigFieldFromInput,
  updateConfigFieldFromSelect,
  validateSelectedConfig,
} = props.runtime;
</script>

<template>
  <section class="panel">
    <header class="panel__header">
      <h3>当前用户</h3>
      <span :class="toneClass(props.authenticated ? 'success' : 'neutral')">
        {{ props.authenticated ? "已登录" : "未登录" }}
      </span>
    </header>
    <dl v-if="props.currentUser" class="summary">
      <div class="summary__row">
        <dt>登录名</dt>
        <dd>{{ props.currentUser.username }}</dd>
      </div>
      <div class="summary__row">
        <dt>显示名</dt>
        <dd>{{ props.currentUser.name }}</dd>
      </div>
      <div class="summary__row">
        <dt>账号状态</dt>
        <dd>{{ formatStatusText(props.currentUser.status) }}</dd>
      </div>
      <div class="summary__row">
        <dt>角色</dt>
        <dd>{{ props.userRoleLabels }}</dd>
      </div>
    </dl>
  </section>

  <section class="panel panel--wide">
    <header class="panel__header">
      <div>
        <h3>配置管理</h3>
        <p :class="toneClass(props.canReadConfig || props.canManageConfig ? 'success' : 'warning')">
          {{ props.canManageConfig ? "可管理配置" : props.canReadConfig ? "可读取配置" : "缺少配置权限" }}
        </p>
      </div>
      <div class="panel__actions">
        <button
          class="button button--secondary"
          type="button"
          @click="props.refreshConfigAdminState"
          :disabled="configBusy.loading || (!props.canReadConfig && !props.canManageConfig)"
        >
          {{ configBusy.loading ? "刷新中" : "刷新配置" }}
        </button>
        <button class="button" type="button" @click="openCreateConfigModal" :disabled="!props.canManageConfig">
          新建版本
        </button>
      </div>
    </header>
    <div class="admin-list-panel">
      <div v-if="configFeedback" :class="['feedback feedback--wide', `feedback--${configFeedback.tone}`]">
        {{ configFeedback.message }}
      </div>

      <ConfigVersionList
        :active-config-version="activeConfigVersion"
        :can-manage-config="props.canManageConfig"
        :deleting="configBusy.deleting"
        :draft-count="configDraftItems.length"
        :loading="configBusy.loading"
        :page-size-options="props.pageSizeOptions"
        :pagination="configVersionPagination"
        :publishing="configBusy.publishing"
        :versions="paginatedConfigVersions"
        @archive="archiveConfigVersionFromUi"
        @detail="openConfigVersionDetail"
        @edit="openEditConfigVersion"
        @page="(page) => changePaginationPage(configVersionPagination, props.refreshConfigAdminState, page)"
        @page-size="(pageSize) => changePaginationPageSize(configVersionPagination, props.refreshConfigAdminState, pageSize)"
        @publish="publishDraftVersion"
      />

      <AuditLogPage
        :audit-feedback="props.audit.auditFeedback.value"
        :audit-log-pagination="props.audit.auditLogPagination"
        :audit-logs="props.audit.auditLogs.value"
        :busy="configBusy"
        :can-read-audit="props.canReadAudit"
        :page-size-options="props.pageSizeOptions"
        :refresh-audit-logs="props.audit.refreshConfigAuditLogs"
      />
    </div>
  </section>

  <ConfigEditorModal
    v-if="configModalMode === 'create' || configModalMode === 'edit'"
    :active-config-version="activeConfigVersion"
    :active-version-record="activeConfigVersionRecord"
    :can-save="canSaveSelectedConfigDraft"
    :can-validate="canValidateSelectedConfig"
    :config-form="configForm"
    :feedback="configFeedback"
    :mode="configModalMode"
    :parse-error="configEditorParseError"
    :saving="configBusy.saving"
    :sections="configSectionDefinitions"
    :selected-version-record="selectedConfigVersionRecord"
    :title="configModalTitle()"
    :validating="configBusy.validating"
    :validation-result="configValidationResult"
    @checkbox="updateConfigFieldFromCheckbox"
    @close="closeConfigModal"
    @input="updateConfigFieldFromInput"
    @save="saveSelectedDraft"
    @select="updateConfigFieldFromSelect"
    @validate="validateSelectedConfig"
  />

  <ConfigVersionDetailModal
    v-if="configDetailModalOpen && selectedConfigDetailRecord"
    :sections="configSectionDefinitions"
    :version="selectedConfigDetailRecord"
    @close="closeConfigVersionDetail"
  />
</template>
