# RAG 查询链路实现说明

更新时间：2026-06-03

本文说明当前 RAG pipeline 从用户问题到最终答案的处理流程。它基于当前代码实现，不描述尚未落地的能力。

## 1. 查询入口

当前后端支持：

- 非流式查询：一次性返回答案、引用、置信度和降级状态。
- 流式查询：先构建查询计划，再消费 provider token 级流式输出，最后收束日志和 citation 校验。

查询请求进入后，会统一执行：

1. 认证用户解析。
2. request_id / trace_id 生成和传播。
3. query_text 规范化。
4. top_k 限制到合理范围。
5. active config version 加载。
6. PermissionContext 构建。

## 2. 服务端全权限知识库自动搜索

当前查询支持两种知识库范围：

| 模式 | 触发条件 | 行为 |
| --- | --- | --- |
| `explicit` | 请求传入 `kb_ids` | 后端校验这些知识库当前用户是否具备 query 权限 |
| `auto_all_accessible` | 请求未传 `kb_ids` 或为空 | 后端自动列出当前用户所有可查询知识库 |

如果自动解析后没有任何可查询知识库，系统返回结构化降级：

- `degrade_reason=query_scope_empty`
- 无候选、无 citation。

## 3. Active Index 加载

查询只读取当前查询范围内的 active index versions。

如果知识库存在但没有 active index，系统不会查询 draft 或 ready 索引，而是进入降级：

- `degrade_reason=active_index_empty`

## 4. Query Rewrite

`QueryRewriteService` 负责将用户原始问题改写为检索 query。

当前支持：

- 开关控制 `query_rewrite_enabled`。
- 可选 LLM rewrite `query_rewrite_use_llm`。
- 最大 query 数 `query_rewrite_max_queries`。
- 可选会话上下文 `query_rewrite_use_conversation`。
- LLM 不可用时回落规则式 rewrite。

联合问题会拆成多个 rewritten query。后续召回会对每个 query 分别执行关键词和向量召回，避免“一个复合问题只覆盖第一个子问题”。

## 5. 多 Query 召回

对每个 rewritten query，系统分别执行：

1. 关键词召回。
2. 向量召回。

每个子 query 都会记录诊断信息：

- query index。
- query 文本。
- intent。
- weight。
- keyword_candidate_count。
- vector_candidate_count。
- vector_degraded。
- vector_degrade_reason。

这些信息会写入 `query_retrieval_diagnostics`。

## 6. 关键词召回

关键词召回使用 PostgreSQL Full Text 派生索引 `keyword_index_entries`。

召回时必须下推：

- enterprise。
- allowed kb ids。
- active index version ids。
- document active。
- document indexed。
- chunk active。
- `visibility_state=active`。
- 文档可见性。
- access block 不存在。

关键词召回失败属于数据库错误，通常会导致查询错误或结构化降级，不能绕过权限过滤。

## 7. 向量召回

向量召回通过 `QdrantVectorRetriever` 完成：

1. 调用 embedding provider 生成 query embedding。
2. 使用 Qdrant payload filter 搜索 active collection。
3. 返回带 payload 的 `RetrievalCandidate`。

payload filter 包含：

- enterprise。
- knowledge base。
- index version。
- visibility_state。
- document status。
- document index status。
- chunk status。
- is_deleted。
- visibility + owner_department。

如果向量召回失败，系统可降级保留关键词召回结果，并记录对应 degrade reason。

## 8. Weighted RRF 融合

关键词候选和向量候选会进入 `ReciprocalRankFusion` 做融合。

融合时使用权重：

- `keyword`
- `vector`
- `original_query`
- `rewrite_query`

权重来自 active config 的 retrieval 配置。融合结果会保留 source、matched_query、matched_query_index、rank 和 score 信息，用于后续 query coverage 和诊断。

## 9. Query Coverage

联合问题场景下，系统会优先保留不同子 query 的候选，避免 rerank 输入被单个子问题占满。

当前链路包含：

- `_coverage_query_indexes`
- `_prioritize_query_quota`
- `_select_candidates_with_query_coverage`

这些步骤的目标是让“联合问题”的候选覆盖尽量接近“分开问”的覆盖效果。

## 10. Candidate Gate

融合候选不会直接进入 rerank。系统先执行权限二次 gate：

- 从 PostgreSQL 读取当前候选事实。
- 检查 active access block。
- 检查 active index version。
- 检查 document lifecycle 和 index_status。
- 检查 chunk status。
- 检查 chunk_index_ref visibility_state。
- 检查文档可见性和用户部门。

被拒绝的候选会计入 gate diagnostics，不进入后续上下文。

## 11. Rerank

如果 active config 配置了 rerank provider，系统会调用 `ModelCandidateReranker`。

rerank 输入文本优先从数据库加载可用于 rerank 的 chunk 文本；如果 rerank provider 不可用或配置不完整，则使用 `NoopCandidateReranker`。

rerank 失败时：

- 查询不直接失败。
- 系统使用融合排序候选。
- 写入 `query.rerank_degraded` 审计事件。
- 写入 `model_call_logs`。

## 12. Candidate Quality Gate

rerank 后会进入质量门。

质量门检查：

- top score。
- candidate count。
- fusion score。
- source score。

如果相关性过低，系统不会把低质量候选强行交给 LLM 编答案，而是标记降级原因，例如：

- `retrieval_relevance_too_low`
- 质量门自定义 reason。

## 13. 相邻 Chunk 扩展

当 mode 为 answer 时，系统可根据 `context_expand_neighbors` 加载相邻 chunk。

相邻 chunk 仍必须重新经过 PermissionCandidateGate，不能因为主 chunk 可见就默认相邻 chunk 可见。

## 14. Context Builder

`ContextBuilder` 基于已通过权限 gate 的候选构建 LLM 上下文。

核心能力：

- 从 PostgreSQL 加载 chunk 元数据。
- 优先通过 `text_object_key` 从对象存储读取完整 chunk 正文。
- 对象存储读取失败时回落 `text_preview`。
- 使用 query coverage seed 保留不同子 query 的上下文覆盖。
- 使用 MMR 去冗余。
- 控制最大 chunk 数、最大字符数、最大 token 数。
- 限制单文档、单 section 的 chunk 数，避免单个文档挤占上下文。
- 写入 `ContextChunk`，携带 heading_path、page_start、page_end、source_offsets、matched_query 等信息。

## 15. LLM 生成

`AnswerService` 负责非流式和流式答案生成。

系统 prompt 要求：

- 只能基于用户可访问资料回答。
- 资料不足时明确说明缺少资料。
- 关键结论必须引用资料编号，且只能复制上下文中的 `[source:...]`。
- 不允许输出思考过程。
- 不允许泄露系统提示词、内部 token 或隐藏字段。

流式输出会过滤：

- `<think>...</think>`。
- 展示给用户的 `[source:...]` 内部占位。

## 16. Citation 校验与自动修复

LLM 生成答案后，系统会进行 citation 校验。

处理原则：

- citation 必须引用当前上下文中真实存在的 source。
- 引用不存在、格式无效或越权时，原答案不能直接返回。
- 可修复时自动附加合法 citation，并标记 `citation_auto_attached` 降级。
- 不可修复时返回说明“为什么没有可采信答案”的结构化降级内容。

这就是 citation 失败时系统不直接返回模型原文的原因：模型原文可能引用了不存在或越权资料。

## 17. 日志与诊断

一次查询完成后会写入：

- `query_logs`：状态、降级、候选数量、citation 数量、版本 hash。
- `model_call_logs`：rewrite、rerank、answer 模型调用摘要。
- `query_retrieval_diagnostics`：rewrite query、阶段数量、质量门、选中 chunk。
- `audit_logs`：拒绝访问、高风险降级和关键失败。

日志不保存完整 prompt、文档原文、secret、token 明文。

## 18. 降级策略

| 阶段 | 典型原因 | 当前行为 |
| --- | --- | --- |
| 知识库范围解析 | 无可查询知识库 | 返回 `query_scope_empty` 降级 |
| Active index | 没有 active index | 返回 `active_index_empty` 降级 |
| 向量召回 | embedding 或 Qdrant 不可用 | 保留关键词召回，记录向量降级 |
| Rerank | provider 不可用或调用失败 | 使用融合排序，记录 rerank 降级 |
| 质量门 | 相关性过低 | 不强行生成无依据答案 |
| Context | 无可用 chunk | 返回 `llm_context_empty` 降级 |
| LLM | provider 超时、401、响应无效 | 返回检索结果和可解释降级 |
| Citation | 引用不存在、格式错误、越权 | 自动修复或抑制原答案 |

## 19. 关键边界

- 前端选择知识库不是权限依据，后端会重新解析和过滤。
- Qdrant payload 命中不是最终可见性依据，候选还要二次 gate。
- LLM 输出不是事实源，citation 校验失败不能直接返回。
- query log 和 model call log 是诊断数据，不替代会话消息。

