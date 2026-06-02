<script setup lang="ts">
import PaginationBar from "@/components/PaginationBar.vue";
import type { DiagnosticsRuntime } from "@/features/diagnostics/useDiagnostics";
import {
  changePaginationPage,
  changePaginationPageSize,
} from "@/utils/pagination";

const props = defineProps<{
  pageSizeOptions: number[];
  runtime: DiagnosticsRuntime;
}>();

const { pageSizeOptions } = props;
const {
  canCreateIndexCollectionSnapshot,
  canLoadIndexOps,
  canRecoverIndexCollectionSnapshot,
  canRebuildIndexCollection,
  createSelectedIndexCollectionSnapshot,
  diagnosticsBusy,
  indexCollectionOpsForm,
  indexCollectionSnapshots,
  indexHealth,
  indexSnapshotPagination,
  onIndexCollectionSelectionChange,
  rebuildSelectedIndexCollection,
  recoverSelectedIndexCollectionSnapshot,
  refreshIndexCollectionSnapshots,
  selectedIndexCollectionHealth,
} = props.runtime;
</script>

<template>
  <section class="resource-block index-ops-panel">
    <header class="resource-section__header">
      <div>
        <h4>Qdrant 恢复入口</h4>
        <p>对选中的 collection 创建快照、从快照恢复，或把该 collection 的 active 文档重新排入索引重建任务。</p>
      </div>
      <span>{{ diagnosticsBusy.loadingIndexSnapshots ? "读取快照中" : `${indexSnapshotPagination.total} 个快照` }}</span>
    </header>

    <div class="index-ops-layout">
      <div class="index-ops-composite">
        <form class="index-ops-selector" @submit.prevent="refreshIndexCollectionSnapshots()">
          <header>
            <div>
              <h5>Collection 选择</h5>
              <p>切换后会读取对应 Qdrant 快照列表。</p>
            </div>
          </header>
          <div class="index-ops-row">
            <label class="field">
              <span class="field__label">Collection</span>
              <select
                v-model="indexCollectionOpsForm.selectedCollectionName"
                class="control"
                @change="onIndexCollectionSelectionChange"
              >
                <option
                  v-for="item in indexHealth"
                  :key="item.collection_name"
                  :value="item.collection_name"
                >
                  {{ item.collection_name }}
                </option>
              </select>
            </label>
            <button
              class="button button--secondary"
              type="submit"
              :disabled="!canLoadIndexOps || diagnosticsBusy.loadingIndexSnapshots"
            >
              {{ diagnosticsBusy.loadingIndexSnapshots ? "刷新中" : "刷新快照" }}
            </button>
          </div>
        </form>

        <div class="index-ops-actions-stack">
          <section class="index-ops-action-panel">
            <header>
              <div>
                <h5>创建快照</h5>
                <p>为当前 collection 创建 Qdrant 快照。</p>
              </div>
            </header>
            <div class="index-ops-action-row">
              <label class="confirm confirm--inline">
                <input
                  v-model="indexCollectionOpsForm.confirmedSnapshot"
                  type="checkbox"
                  :disabled="!selectedIndexCollectionHealth"
                />
                <span>确认创建快照</span>
              </label>
              <button
                class="button"
                type="button"
                @click="createSelectedIndexCollectionSnapshot"
                :disabled="!canCreateIndexCollectionSnapshot"
              >
                {{ diagnosticsBusy.creatingIndexSnapshot ? "创建中..." : "创建快照" }}
              </button>
            </div>
          </section>

          <section class="index-ops-action-panel">
            <header>
              <div>
                <h5>重建索引</h5>
                <p>把 active 文档重新排入索引任务。</p>
              </div>
            </header>
            <div class="index-ops-action-row">
              <label class="confirm confirm--inline">
                <input
                  v-model="indexCollectionOpsForm.confirmedRebuild"
                  type="checkbox"
                  :disabled="!selectedIndexCollectionHealth"
                />
                <span>确认重建索引</span>
              </label>
              <button
                class="button"
                type="button"
                @click="rebuildSelectedIndexCollection"
                :disabled="!canRebuildIndexCollection"
              >
                {{ diagnosticsBusy.rebuildingIndexCollection ? "创建中..." : "重建索引" }}
              </button>
            </div>
          </section>
        </div>
      </div>

      <form class="index-ops-card index-ops-card--restore" @submit.prevent="recoverSelectedIndexCollectionSnapshot">
        <header>
          <div>
            <h5>从快照恢复</h5>
            <p>恢复会覆盖当前 Qdrant collection 数据。</p>
          </div>
        </header>
        <label class="field">
          <span class="field__label">Snapshot URL / File URI</span>
          <input
            v-model.trim="indexCollectionOpsForm.snapshotLocation"
            class="control"
            type="text"
            placeholder="https://example.com/snapshot.snapshot 或 file:///qdrant/snapshots/name.snapshot"
          />
        </label>
        <div class="index-ops-row">
          <label class="field">
            <span class="field__label">Priority</span>
            <select v-model="indexCollectionOpsForm.recoverPriority" class="control">
              <option value="Snapshot">Snapshot</option>
              <option value="Replica">Replica</option>
            </select>
          </label>
          <label class="field">
            <span class="field__label">Checksum</span>
            <input v-model.trim="indexCollectionOpsForm.snapshotChecksum" class="control" type="text" />
          </label>
        </div>
        <div class="index-ops-row index-ops-row--actions">
          <label class="confirm confirm--inline">
            <input
              v-model="indexCollectionOpsForm.confirmedRestore"
              type="checkbox"
              :disabled="!selectedIndexCollectionHealth || !indexCollectionOpsForm.snapshotLocation.trim()"
            />
            <span>确认覆盖当前数据</span>
          </label>
          <button
            class="button button--danger"
            type="submit"
            :disabled="!canRecoverIndexCollectionSnapshot"
          >
            {{ diagnosticsBusy.recoveringIndexSnapshot ? "恢复中..." : "恢复快照" }}
          </button>
        </div>
      </form>
    </div>

    <div v-if="indexCollectionSnapshots.length" class="entity-table entity-table--snapshots">
      <div class="entity-table__row entity-table__row--header">
        <span>快照</span>
        <span>大小</span>
        <span>创建时间</span>
        <span>Checksum</span>
      </div>
      <article v-for="snapshot in indexCollectionSnapshots" :key="snapshot.name" class="entity-table__row">
        <div class="entity-main">
          <strong>{{ snapshot.name }}</strong>
          <span>{{ snapshot.collection_name }}</span>
        </div>
        <div class="entity-cell">{{ snapshot.size ?? "-" }}</div>
        <div class="entity-cell">{{ snapshot.creation_time ?? "-" }}</div>
        <div class="entity-cell">{{ snapshot.checksum ?? "-" }}</div>
      </article>
    </div>
    <p v-else class="empty-state empty-state--plain">当前 collection 尚未读取到 Qdrant 快照。</p>
    <PaginationBar
      v-if="indexSnapshotPagination.total > 0"
      label="Qdrant 快照分页"
      :page="indexSnapshotPagination.page"
      :page-size="indexSnapshotPagination.pageSize"
      :total="indexSnapshotPagination.total"
      :page-size-options="pageSizeOptions"
      :disabled="diagnosticsBusy.loadingIndexSnapshots"
      @update:page="(page) => changePaginationPage(indexSnapshotPagination, () => refreshIndexCollectionSnapshots(), page)"
      @update:page-size="(pageSize) => changePaginationPageSize(indexSnapshotPagination, () => refreshIndexCollectionSnapshots(), pageSize)"
    />
  </section>
</template>
