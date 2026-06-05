<script setup lang="ts">
import type { ConfigVersionListItemData } from "@/api/config";
import PaginationBar from "@/components/PaginationBar.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import {
  configStatusTone,
  configChangeImpactText,
  configVersionPreview,
  isActivatableConfigVersion,
  isArchivableConfigVersion,
  isEditableConfigVersion,
} from "@/features/config/configDisplay";
import { formatDateTime } from "@/utils/date";
import { formatStatusText } from "@/utils/display";

type PaginationState = {
  page: number;
  pageSize: number;
  total: number;
};

const props = defineProps<{
  activeConfigVersion: number;
  canManageConfig: boolean;
  deleting: boolean;
  draftCount: number;
  loading: boolean;
  pageSizeOptions: number[];
  pagination: PaginationState;
  publishing: boolean;
  versions: ConfigVersionListItemData[];
}>();

const emit = defineEmits<{
  (event: "archive", version: ConfigVersionListItemData): void;
  (event: "detail", version: ConfigVersionListItemData): void;
  (event: "edit", version: ConfigVersionListItemData): void;
  (event: "page", page: number): void;
  (event: "pageSize", pageSize: number): void;
  (event: "publish", version: number): void;
}>();
</script>

<template>
  <section class="config-version-strip">
    <article class="config-version-card">
      <span>当前配置版本</span>
      <strong>v{{ props.activeConfigVersion }}</strong>
    </article>
    <article class="config-version-card">
      <span>版本数量</span>
      <strong>{{ props.pagination.total }}</strong>
    </article>
    <article class="config-version-card">
      <span>本页可激活</span>
      <strong>{{ props.draftCount }}</strong>
    </article>
  </section>

  <div v-if="props.versions.length" class="entity-table entity-table--configs">
    <div class="entity-table__row entity-table__row--header">
      <span>版本</span>
      <span>状态</span>
      <span>创建时间</span>
      <span>更新时间</span>
      <span>变更影响</span>
      <span>操作</span>
    </div>
    <article
      v-for="version in props.versions"
      :key="`config-version-${version.version}`"
      class="entity-table__row"
    >
      <div class="entity-main">
        <strong>v{{ version.version }}</strong>
        <span>{{ configVersionPreview(version) }}</span>
      </div>
      <div class="entity-cell">
        <StatusBadge
          :label="formatStatusText(version.status)"
          :tone="configStatusTone(version.status)"
        />
      </div>
      <div class="entity-cell">{{ formatDateTime(version.created_at) }}</div>
      <div class="entity-cell">{{ formatDateTime(version.updated_at) }}</div>
      <div class="entity-cell">
        <span>{{ configChangeImpactText(version.risk_level) }}</span>
      </div>
      <div class="row-actions">
        <button
          class="button button--secondary button--small"
          type="button"
          @click="emit('detail', version)"
        >
          详情
        </button>
        <button
          class="button button--secondary button--small"
          type="button"
          @click="emit('edit', version)"
          :disabled="!props.canManageConfig || !isEditableConfigVersion(version)"
        >
          编辑
        </button>
        <button
          v-if="isActivatableConfigVersion(version)"
          class="button button--secondary button--small"
          type="button"
          @click="emit('publish', version.version)"
          :disabled="!props.canManageConfig || props.publishing"
        >
          激活
        </button>
        <button
          v-if="isArchivableConfigVersion(version)"
          class="button button--danger button--small"
          type="button"
          @click="emit('archive', version)"
          :disabled="!props.canManageConfig || props.deleting"
        >
          归档
        </button>
      </div>
    </article>
  </div>
  <p v-else class="empty-state empty-state--plain">当前尚未读取到配置版本。</p>

  <PaginationBar
    v-if="props.pagination.total > 0"
    label="配置列表分页"
    :page="props.pagination.page"
    :page-size="props.pagination.pageSize"
    :total="props.pagination.total"
    :page-size-options="props.pageSizeOptions"
    :disabled="props.loading"
    @update:page="(page) => emit('page', page)"
    @update:page-size="(pageSize) => emit('pageSize', pageSize)"
  />
</template>
