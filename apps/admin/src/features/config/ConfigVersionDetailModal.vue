<script setup lang="ts">
import { computed } from "vue";
import type { ConfigVersionData } from "@/api/config";
import StatusBadge from "@/components/StatusBadge.vue";
import type { ConfigSectionFormDefinition } from "@/features/config/configFields";
import { configChangeImpactText, configStatusTone } from "@/features/config/configDisplay";
import { formatDateTime } from "@/utils/date";
import { formatStatusText } from "@/utils/display";

const props = defineProps<{
  sections: ConfigSectionFormDefinition[];
  version: ConfigVersionData;
}>();

const emit = defineEmits<{
  (event: "close"): void;
}>();

const visibleSectionRows = computed(() => {
  const config = props.version.config ?? {};
  const knownRows = props.sections
    .filter((section) => Object.prototype.hasOwnProperty.call(config, section.key))
    .map((section) => ({
      key: section.key,
      label: section.label,
      description: section.description,
      fieldCount: section.fields.length,
      known: true,
    }));
  const knownKeys = new Set(props.sections.map((section) => section.key));
  const extraRows = Object.keys(config)
    .filter((key) => !["schema_version", "config_version", "scope"].includes(key) && !knownKeys.has(key))
    .map((key) => ({
      key,
      label: key,
      description: "当前配置分组来自后端版本详情，前端暂未配置可视化字段定义。",
      fieldCount: 0,
      known: false,
    }));
  return [...knownRows, ...extraRows];
});
</script>

<template>
  <div class="modal-backdrop" role="presentation" @click.self="emit('close')">
    <section class="modal modal--wide" role="dialog" aria-modal="true" aria-labelledby="config-version-detail-title">
      <header class="modal__header">
        <div>
          <p class="eyebrow">配置管理</p>
          <h3 id="config-version-detail-title">配置版本详情</h3>
          <p>v{{ props.version.version }}</p>
        </div>
        <button class="button button--secondary button--small" type="button" @click="emit('close')">
          关闭
        </button>
      </header>

      <div class="modal__body">
        <dl class="summary summary--compact modal-summary">
          <div class="summary__row">
            <dt>版本状态</dt>
            <dd>
              <StatusBadge
                :label="formatStatusText(props.version.status)"
                :tone="configStatusTone(props.version.status)"
              />
            </dd>
          </div>
          <div class="summary__row">
            <dt>变更影响</dt>
            <dd>{{ configChangeImpactText(props.version.risk_level) }}</dd>
          </div>
          <div class="summary__row">
            <dt>创建时间</dt>
            <dd>{{ formatDateTime(props.version.created_at) }}</dd>
          </div>
          <div class="summary__row">
            <dt>更新时间</dt>
            <dd>{{ formatDateTime(props.version.updated_at) }}</dd>
          </div>
          <div class="summary__row">
            <dt>激活时间</dt>
            <dd>{{ formatDateTime(props.version.activated_at) }}</dd>
          </div>
        </dl>

        <section class="modal-pane">
          <h4>配置分组</h4>
          <div v-if="visibleSectionRows.length" class="config-form-sections">
            <article
              v-for="section in visibleSectionRows"
              :key="`config-detail-section-${section.key}`"
              class="config-form-section"
            >
              <header>
                <div>
                  <h4>{{ section.label }}</h4>
                  <p>{{ section.description }}</p>
                </div>
                <span>{{ section.known ? `${section.fieldCount} 个可视化字段` : "未定义字段" }}</span>
              </header>
            </article>
          </div>
          <p v-else class="empty-state empty-state--plain">当前版本没有可展示的配置分组。</p>
        </section>
      </div>

      <footer class="modal__footer">
        <button class="button button--secondary" type="button" @click="emit('close')">
          关闭
        </button>
      </footer>
    </section>
  </div>
</template>
