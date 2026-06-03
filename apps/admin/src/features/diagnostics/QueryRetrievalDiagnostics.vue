<script setup lang="ts">
import type {
  QueryRetrievalDiagnosticsData,
  QueryRetrievalGateData,
  QueryRetrievalSelectedChunkData,
  QueryRetrievalStageCountsData,
} from "@/api/diagnostics";
import { formatDiagnosticReasonList } from "@/utils/status";

defineProps<{
  diagnostics: QueryRetrievalDiagnosticsData | null | undefined;
}>();

const stageItems: Array<{
  key: keyof QueryRetrievalStageCountsData;
  label: string;
}> = [
  { key: "resolved_kb_count", label: "可查询知识库" },
  { key: "keyword_candidate_count", label: "关键词召回" },
  { key: "vector_candidate_count", label: "向量召回" },
  { key: "fused_candidate_count", label: "融合后候选" },
  { key: "gated_candidate_count", label: "权限通过" },
  { key: "relevant_candidate_count", label: "相关性通过" },
  { key: "quality_rejected_count", label: "质量拒绝" },
  { key: "context_candidate_count", label: "上下文候选" },
  { key: "context_chunk_count", label: "最终片段" },
  { key: "citation_count", label: "引用数量" },
];

function countValue(
  stageCounts: QueryRetrievalStageCountsData | null | undefined,
  key: keyof QueryRetrievalStageCountsData,
): string {
  const value = stageCounts?.[key];
  return typeof value === "number" ? String(value) : "-";
}

function formatIntent(value: string | null | undefined): string {
  if (!value) {
    return "检索";
  }
  const labels: Record<string, string> = {
    original: "原始问题",
    rewritten: "改写问题",
    sub_question: "子问题",
    fallback: "规则兜底",
  };
  return labels[value] ?? value;
}

function formatWeight(value: number | undefined): string {
  return typeof value === "number" ? value.toFixed(2) : "-";
}

function formatScore(value: number | undefined | null): string {
  if (typeof value !== "number") {
    return "-";
  }
  if (value >= 1) {
    return value.toFixed(2);
  }
  return value.toFixed(4);
}

function formatChunkTitle(chunk: QueryRetrievalSelectedChunkData): string {
  return chunk.title?.trim() || "未知文档";
}

function formatChunkMeta(chunk: QueryRetrievalSelectedChunkData): string {
  const parts = [
    chunk.heading_path?.trim(),
    chunk.matched_query ? `命中 ${chunk.matched_query}` : "",
    typeof chunk.rank === "number" ? `排序 ${chunk.rank}` : "",
    typeof chunk.score === "number" ? `分数 ${formatScore(chunk.score)}` : "",
  ].filter(Boolean);
  return parts.join(" / ") || "-";
}

function formatCount(value: number | undefined | null): string {
  return typeof value === "number" ? String(value) : "-";
}

function formatGateReasons(reasons: QueryRetrievalGateData["rejection_reasons"]): string {
  if (!Array.isArray(reasons) || reasons.length === 0) {
    return "无";
  }
  return reasons
    .map((item) => {
      if (!item || typeof item !== "object") {
        return "";
      }
      const reason = "reason" in item && typeof item.reason === "string" ? item.reason : "未知";
      const count = "count" in item && typeof item.count === "number" ? item.count : 0;
      return `${formatDiagnosticReasonList(reason, reason)} ${count}`;
    })
    .filter(Boolean)
    .join("，");
}
</script>

<template>
  <section class="modal-pane retrieval-diagnostics">
    <header class="retrieval-diagnostics__header">
      <div>
        <h4>检索诊断</h4>
        <p>展示改写、召回、门控和最终进入上下文的片段摘要，不展示 prompt 或文档原文。</p>
      </div>
      <span v-if="diagnostics">
        {{ diagnostics.selected_chunks?.length ?? 0 }} 个上下文片段
      </span>
    </header>

    <p v-if="!diagnostics" class="empty-state empty-state--plain">
      当前查询没有检索诊断记录。若这是旧日志，请在数据库迁移后重新发起查询。
    </p>

    <template v-else>
      <div class="retrieval-stage-grid" aria-label="检索阶段数量">
        <div
          v-for="item in stageItems"
          :key="item.key"
          class="retrieval-stage-card"
        >
          <span>{{ item.label }}</span>
          <strong>{{ countValue(diagnostics.stage_counts, item.key) }}</strong>
        </div>
      </div>

      <section class="retrieval-section">
        <div class="retrieval-section__title">
          <h5>质量门控</h5>
          <span>
            拒绝 {{ diagnostics.quality_gate?.rejected_count ?? 0 }} 个候选
          </span>
        </div>
        <dl class="summary summary--compact modal-summary retrieval-summary">
          <div class="summary__row">
            <dt>门控原因</dt>
            <dd>
              {{ formatDiagnosticReasonList(diagnostics.quality_gate?.reason, "未触发") }}
            </dd>
          </div>
          <div class="summary__row">
            <dt>最高分</dt>
            <dd>{{ formatScore(diagnostics.quality_gate?.top_score) }}</dd>
          </div>
        </dl>
      </section>

      <section class="retrieval-section">
        <div class="retrieval-section__title">
          <h5>Query Rewrite</h5>
          <span>{{ diagnostics.rewrite_queries?.length ?? 0 }} 条检索 query</span>
        </div>
        <div
          v-if="diagnostics.rewrite_queries?.length"
          class="retrieval-query-list"
        >
          <article
            v-for="(item, index) in diagnostics.rewrite_queries"
            :key="`${item.index ?? index}-${item.query ?? index}`"
            class="retrieval-query-card"
          >
            <strong>{{ item.query || "空 query" }}</strong>
            <span>
              {{ formatIntent(item.intent) }} / 权重 {{ formatWeight(item.weight) }}
            </span>
          </article>
        </div>
        <p v-else class="empty-state empty-state--plain">未记录 query rewrite 摘要。</p>
      </section>

      <section class="retrieval-section">
        <div class="retrieval-section__title">
          <h5>子 Query 召回</h5>
          <span>{{ diagnostics.stage_counts?.per_query?.length ?? 0 }} 组</span>
        </div>
        <div
          v-if="diagnostics.stage_counts?.per_query?.length"
          class="retrieval-query-list"
        >
          <article
            v-for="(item, index) in diagnostics.stage_counts.per_query"
            :key="`${item.index ?? index}-${item.query ?? index}-recall`"
            class="retrieval-query-card"
          >
            <strong>{{ item.query || "空 query" }}</strong>
            <span>
              关键词 {{ formatCount(item.keyword_candidate_count) }} /
              向量 {{ formatCount(item.vector_candidate_count) }} /
              融合 {{ formatCount(item.fused_candidate_count) }} /
              权限通过 {{ formatCount(item.gated_candidate_count) }} /
              上下文 {{ formatCount(item.context_chunk_count) }}
            </span>
            <span v-if="item.vector_degraded">
              向量降级：{{ formatDiagnosticReasonList(item.vector_degrade_reason, "未知") }}
            </span>
          </article>
        </div>
        <p v-else class="empty-state empty-state--plain">未记录子 query 召回明细。</p>
      </section>

      <section class="retrieval-section">
        <div class="retrieval-section__title">
          <h5>权限 Gate</h5>
          <span>
            通过 {{ diagnostics.stage_counts?.gate?.allowed_count ?? 0 }} /
            拒绝 {{ diagnostics.stage_counts?.gate?.rejected_count ?? 0 }}
          </span>
        </div>
        <dl class="summary summary--compact modal-summary retrieval-summary">
          <div class="summary__row">
            <dt>输入候选</dt>
            <dd>{{ formatCount(diagnostics.stage_counts?.gate?.input_count) }}</dd>
          </div>
          <div class="summary__row">
            <dt>缺失元数据</dt>
            <dd>{{ formatCount(diagnostics.stage_counts?.gate?.missing_metadata_count) }}</dd>
          </div>
          <div class="summary__row">
            <dt>拒绝原因</dt>
            <dd>{{ formatGateReasons(diagnostics.stage_counts?.gate?.rejection_reasons) }}</dd>
          </div>
        </dl>
      </section>

      <section class="retrieval-section">
        <div class="retrieval-section__title">
          <h5>Rerank 摘要</h5>
          <span>{{ diagnostics.stage_counts?.rerank?.length ?? 0 }} 次</span>
        </div>
        <div
          v-if="diagnostics.stage_counts?.rerank?.length"
          class="retrieval-query-list"
        >
          <article
            v-for="(item, index) in diagnostics.stage_counts.rerank"
            :key="`${item.query_index ?? index}-${item.query ?? index}-rerank`"
            class="retrieval-query-card"
          >
            <strong>{{ item.query || "原始问题" }}</strong>
            <span>
              输入 {{ formatCount(item.input_candidate_count) }} /
              输出 {{ formatCount(item.output_candidate_count) }} /
              状态 {{ item.model_status || "未调用" }}
            </span>
            <span v-if="item.degraded">
              降级：{{ formatDiagnosticReasonList(item.degrade_reason, "未知") }}
            </span>
            <span v-if="item.scores?.length">
              Top 分数：
              {{
                item.scores
                  .slice(0, 5)
                  .map((score) => `${score.title || "未知文档"} ${formatScore(score.score)}`)
                  .join("，")
              }}
            </span>
          </article>
        </div>
        <p v-else class="empty-state empty-state--plain">未记录 rerank 明细。</p>
      </section>

      <section class="retrieval-section">
        <div class="retrieval-section__title">
          <h5>最终上下文片段</h5>
          <span>{{ diagnostics.selected_chunks?.length ?? 0 }} 个片段</span>
        </div>
        <div
          v-if="diagnostics.selected_chunks?.length"
          class="retrieval-chunk-list"
        >
          <article
            v-for="(chunk, index) in diagnostics.selected_chunks"
            :key="chunk.chunk_id ?? `${chunk.title ?? 'chunk'}-${index}`"
            class="retrieval-chunk-card"
          >
            <span class="retrieval-chunk-card__index">{{ index + 1 }}</span>
            <div>
              <strong>{{ formatChunkTitle(chunk) }}</strong>
              <span>{{ formatChunkMeta(chunk) }}</span>
            </div>
          </article>
        </div>
        <p v-else class="empty-state empty-state--plain">
          没有片段进入最终上下文，通常是无权限、无 active 索引或候选质量过低。
        </p>
      </section>
    </template>
  </section>
</template>
