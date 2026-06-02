# RAG 链路增强实现计划

更新时间：2026-06-02

本文用于规划 Little Bear 当前 RAG 主链路的下一阶段增强。计划基于当前代码实现，而不是历史设计草稿。当前系统已经具备导入、解析、清洗、切块、embedding、关键词索引、Qdrant 向量索引、权限过滤、混合召回、RRF 融合、rerank、上下文构建、LLM 生成、citation 校验、查询日志和模型调用日志。下一阶段目标是在不削弱权限安全和可观测性的前提下，提升检索覆盖率、检索精度和用户输入容错能力。

## 1. 当前 RAG 链路基线

当前查询主链路：

```text
用户问题 + 前端选择 kb_ids
-> Query Service normalize query
-> Permission Service build context
-> 校验用户可查询的知识库
-> 加载 active index versions
-> 构建权限 filter
-> keyword search
-> query embedding + Qdrant vector search
-> RRF 融合
-> candidate gate 二次权限校验
-> rerank
-> relevance gate
-> Context Builder
-> LLM answer / stream answer
-> citation validation
-> query_logs / model_call_logs / audit_logs
```

当前导入索引链路：

```text
upload / url / metadata_batch
-> parse
-> clean
-> HeadingParagraphChunker chunk
-> draft chunks
-> create draft index version
-> keyword index + Qdrant draft vector points
-> publish active index
```

已实现但需要增强的点：

- 当前会话历史只用于展示，不参与检索 query 改写。
- 当前查询 API 要求前端传入 `kb_ids`，还不是服务端自动搜索当前用户全部可访问知识库。
- 当前切块器已经按标题/段落聚合，但长块仍按字符长度硬切，页码、段落序号、标题层级、表格等元数据不足。
- 当前检索策略有关键词、向量、RRF、rerank、最低 rerank 分数 gate，但缺少 query rewrite、多 query 召回、字段加权、相邻 chunk 扩展、文档级聚合、MMR 去冗余等精细策略。

## 2. 总体目标

本轮增强目标：

1. 引入 Query Rewrite，把用户自然问题改写为一个或多个可检索 query，覆盖一次性提出多个问题、口语化、省略指代和复合问题。
2. 查询接口支持服务端“全权限知识库自动搜索”，前端不再必须让用户选择知识库才能查询。
3. 升级切块策略，按标题、句段、页码、表格和结构块生成 chunk，并补充稳定可用的元数据。
4. 实现更细的检索策略，提升相关性、减少无关片段进入 LLM。

非目标：

- 不引入多 Agent。
- 不让前端承担权限过滤或检索范围决策。
- 不让 Query Rewrite 绕过权限、知识库可见性或 citation 校验。
- 不把模型改写结果当作可信事实，只把它作为检索提示。

## 3. 推荐实施顺序

推荐顺序：

```text
P0 服务端全权限知识库自动搜索
-> P1 Query Rewrite
-> P2 结构化切块与元数据增强
-> P3 精细化检索策略
```

原因：

- 全权限知识库自动搜索会改变 Query API 的边界，是后续 Query Rewrite 多 query 检索的基础。
- Query Rewrite 依赖明确的检索范围和权限边界，否则复合 query 很容易把前端选择逻辑搞复杂。
- 切块元数据增强需要重建索引，适合在检索编排稳定后推进。
- 精细化检索策略依赖更好的 query 和 chunk 元数据，放到最后收益最大。

## 4. P0 服务端全权限知识库自动搜索

### 4.1 目标

允许普通用户在查询时不传 `kb_ids` 或传空数组。后端根据当前用户权限自动加载其可查询的知识库，并在这些知识库范围内检索。

### 4.2 行为设计

查询请求支持三种范围：

| 输入 | 行为 |
| --- | --- |
| `kb_ids` 有值 | 后端校验这些知识库是否当前用户可查询，只查这些知识库 |
| `kb_ids` 为空或缺省 | 后端自动加载当前用户全部可查询知识库 |
| 自动加载结果为空 | 返回结构化降级答案，提示当前账号没有可查询知识库 |

建议新增内部概念：

```text
QueryScope
- mode: explicit | auto_all_accessible
- requested_kb_ids: tuple[str, ...]
- resolved_kb_ids: tuple[str, ...]
- resolved_kb_count: int
```

### 4.3 后端改动

涉及模块：

- `apps/api/app/api/schemas/query.py`
- `apps/api/app/modules/query/utils.py`
- `apps/api/app/modules/query/orchestrator.py`
- `apps/api/app/modules/permissions/service.py`
- `apps/api/app/modules/permissions/admin_readers.py` 或新增 user-facing KB reader
- `apps/api/app/modules/query/repository.py`

改动点：

1. `QueryRequest.kb_ids` 改为允许缺省或空数组。
2. `normalize_ids` 不再对空 `kb_ids` 直接报错，而是返回空 tuple。
3. QueryOrchestrator 判断：

```text
if normalized_kb_ids:
    require_queryable_knowledge_bases(...)
else:
    list_queryable_knowledge_bases_for_context(...)
```

4. Permission Service 新增或暴露：

```python
list_queryable_knowledge_base_ids(session, context) -> tuple[str, ...]
```

5. 自动范围必须走后端权限 SQL，不允许从前端知识库列表结果复用。
6. query log 增加范围摘要：

```text
query_scope_mode
resolved_kb_count
```

如果不立刻改数据库字段，可先写入 query log 的 summary / details；若 query_logs 已无 details 字段，则需要新增 migration。

### 4.4 前端改动

涉及：

- `apps/web/src/api/query.ts`
- `apps/web/src/features/chat/useChatWorkspaceRuntime.ts`
- `apps/web/src/features/knowledge/*`

行为：

- 知识库选择区域改为“限定搜索范围”，不是必填项。
- 默认状态为“全部可访问知识库”。
- 如果用户勾选部分知识库，则传入这些 `kb_ids`。
- 如果用户清空选择，则传空数组或不传 `kb_ids`。

### 4.5 权限与安全

- 自动搜索范围只能由后端权限上下文计算。
- 管理员、部门管理员、知识库管理员、普通员工都必须按自己的 query 权限解析范围。
- 不允许因为用户能看到知识库名称，就默认能 query。
- query candidate 仍必须经过 Permission Filter 和 Candidate Gate。

### 4.6 测试

新增测试：

- `test_query_auto_scope_uses_all_accessible_kbs`
- `test_query_auto_scope_returns_degraded_when_no_queryable_kbs`
- `test_query_explicit_scope_rejects_inaccessible_kb`
- `test_query_auto_scope_does_not_include_manage_only_kb_without_query_permission`
- 前端 typecheck：默认不选知识库仍可提交查询。

验收：

- 普通员工登录后不选择知识库也能查其所有可查询知识库。
- 无可查询知识库时返回解释性答案，不返回 500。
- 后端日志可看到 resolved kb 数量。

## 5. P1 Query Rewrite

### 5.1 目标

把用户原始问题改写为适合检索的 query 列表，并支持复合问题拆分。例如：

```text
原问题：我想做采购项目，前期要准备什么，审批流程和预算限制分别是什么？
改写：
1. 采购项目启动前需要准备哪些材料
2. 采购项目审批流程
3. 采购项目预算限制和金额规则
```

### 5.2 架构位置

新增模块建议：

```text
apps/api/app/modules/query_rewrite/
  __init__.py
  schemas.py
  service.py
  runtime.py
  prompt.py
  fallback.py
```

也可以放在 `modules/query/rewrite_*` 下，但更推荐独立模块，原因是 Query Rewrite 是模型能力，不应塞进 QueryOrchestrator 继续变大。

### 5.3 数据结构

建议定义：

```python
@dataclass(frozen=True)
class QueryRewriteInput:
    original_query: str
    conversation_messages: tuple[RewriteConversationMessage, ...]
    max_queries: int
    locale: str = "zh-CN"

@dataclass(frozen=True)
class QueryRewriteItem:
    query: str
    intent: str | None
    weight: float

@dataclass(frozen=True)
class QueryRewriteResult:
    original_query: str
    rewritten_queries: tuple[QueryRewriteItem, ...]
    degraded: bool
    degrade_reason: str | None
    model_call: RetrievalModelCall | None
```

### 5.4 Rewrite 策略

优先实现两级策略：

1. 规则 fallback：
   - 去除无意义口语词。
   - 按中文顿号、逗号、分号、“以及”、“分别”、“还有”、“和”等拆分复合问题。
   - 保留原始 query 作为第一检索 query。

2. LLM rewrite：
   - 使用 active config 中 LLM provider 或新增 rewrite provider 配置。
   - 输出严格 JSON。
   - 最多返回 3 到 5 个 rewritten queries。
   - 每个 query 不超过 120 字。
   - 禁止引入用户问题中没有依据的具体实体。

建议 prompt 要求：

```text
你只负责把用户问题改写为检索 query。
不要回答问题。
不要生成事实。
不要扩展到用户没有提到的业务领域。
输出 JSON:
{
  "queries": [
    {"query": "...", "intent": "...", "weight": 1.0}
  ]
}
```

### 5.5 与多轮会话的关系

第一阶段只允许使用最近 N 条会话做“指代补全”，不做长历史总结。

示例：

```text
上一轮：采购项目怎么启动？
当前：预算呢？
rewrite：采购项目启动中的预算要求是什么？
```

限制：

- 只读取当前用户自己的 active conversation。
- 只取最近 4 到 6 条消息。
- 不把 assistant 的降级回答当作事实来源。
- 只用于 rewrite，不直接进入 LLM 答案上下文。

### 5.6 QueryOrchestrator 改动

当前：

```text
normalized_query -> keyword + vector
```

改为：

```text
normalized_query
-> QueryRewriteService.rewrite(...)
-> rewritten_queries
-> 每个 query 做 keyword + vector
-> 合并候选并保留 query source
-> RRF / weighted RRF
```

候选需要记录：

```text
matched_query
matched_query_index
rewrite_weight
```

如果不立刻改 `RetrievalCandidate`，可以先在融合阶段用内部 wrapper；长期建议扩展 schema。

### 5.7 日志与观测

query log / model_call_logs 增加：

- rewrite 是否启用。
- rewrite 是否降级。
- rewrite query 数量。
- rewrite model route hash。
- rewrite input/output hash。

禁止记录完整 rewrite prompt。可以记录 hash 和 query 数量。

### 5.8 配置项

active config 增加：

```json
{
  "retrieval": {
    "query_rewrite_enabled": true,
    "query_rewrite_max_queries": 4,
    "query_rewrite_use_conversation": true,
    "query_rewrite_recent_messages": 6
  },
  "timeout": {
    "query_rewrite_ms": 3000
  }
}
```

如果不想改 schema 太多，也可先把 rewrite 归入 `retrieval` 和 `timeout`。

### 5.9 测试

单元测试：

- 规则拆分复合问题。
- LLM JSON 输出解析。
- LLM 输出非法 JSON 时 fallback。
- rewrite 不会返回空 query。
- rewrite 最多返回配置数量。
- 多轮指代只读取当前用户会话。

查询链路测试：

- 多 query 会触发多次 keyword/vector search。
- rewrite 降级时仍用原始问题检索。
- rewrite model call log 写入 hash，不写完整 prompt。
- 复合问题可以召回来自不同文档的片段。

## 6. P2 结构化切块与元数据增强

### 6.1 目标

升级当前 `HeadingParagraphChunker`。当前它已经按标题/段落聚合，但仍存在：

- 长段落按字符硬切。
- page_start / page_end 经常为空。
- heading_path 只有简单标题。
- 缺少段落序号、section id、block 类型、表格信息。
- chunk 元数据不足以做精细化检索和 citation 定位。

目标是让 chunk 的边界更贴近文档结构，元数据更稳定。

### 6.2 新增结构模型

建议先把 parser 输出从纯文本升级为结构块：

```python
@dataclass(frozen=True)
class ParsedBlock:
    text: str
    block_type: Literal["heading", "paragraph", "list_item", "table", "code", "page_break"]
    heading_level: int | None
    page_number: int | None
    ordinal: int
    metadata: dict[str, Any]

@dataclass(frozen=True)
class ParsedDocument:
    text: str
    parser_version: str
    metadata: dict[str, Any]
    blocks: tuple[ParsedBlock, ...] = ()
```

兼容策略：

- 新 parser 输出 blocks。
- 老 parser 如果没有 blocks，则由 `TextBlockExtractor` 从 text 中提取 blocks。
- 不保留“老 chunker facade”，直接让新 chunker 接受 `CleanedDocument.blocks` 或 `CleanedDocument.metadata["blocks"]`。

### 6.3 Parser 改动

PDF：

- 保留 `[page N]` 的文本标记，同时生成 block 时写入 `page_number=N`。
- 页码传播到 chunk 的 `page_start/page_end`。

Markdown / TXT：

- Markdown 标题 `#` 到 `######` 转为 heading block。
- 列表项识别为 list_item。
- 代码块识别为 code，不和普通段落合并。

DOCX：

- 尝试读取 paragraph style。
- 表格转为 table block，保留行列文本摘要。
- 页码无法可靠获取时允许为空，但要写 `block_ordinal`。

### 6.4 Chunker 策略

新增：

```text
StructureAwareChunker
```

核心规则：

- heading 更新当前 section path，不单独生成 chunk，除非标题下无正文。
- paragraph / list_item 作为基础切分单元。
- table 单独成 chunk 或按行组块。
- code 单独成 chunk。
- 小段落按同一 heading 聚合。
- 超长段落按句子切分，不直接按字符切。
- 只在句子仍超长时才按字符兜底。
- chunk overlap 只按句子/段落 overlap，不切半句话。

建议参数：

```json
{
  "chunk": {
    "strategy": "structure_aware",
    "target_tokens": 500,
    "max_tokens": 900,
    "overlap_tokens": 80,
    "min_chunk_tokens": 80,
    "preserve_tables": true,
    "preserve_code_blocks": true
  }
}
```

### 6.5 Chunk 元数据

写入 `chunks.source_offsets`：

```json
{
  "block_start": 12,
  "block_end": 18,
  "char_start": 2300,
  "char_end": 3900,
  "page_start": 3,
  "page_end": 4,
  "heading_path": ["采购管理", "项目启动", "预算"],
  "block_types": ["paragraph", "list_item"],
  "section_id": "采购管理/项目启动/预算",
  "chunk_strategy": "structure_aware",
  "chunker_version": "structure-aware-v1"
}
```

数据库现有字段已包含：

- `heading_path`
- `page_start`
- `page_end`
- `source_offsets`
- `token_count`

第一阶段可以不新增表字段，先充分利用 `source_offsets`。

### 6.6 索引文本增强

keyword 和 vector 的索引文本建议从纯 chunk text 改为结构化文本：

```text
title: 文档标题
section: 一级标题 > 二级标题 > 三级标题
content: chunk 正文
tags: ...
source_type: ...
```

注意：

- LLM 上下文可以仍只展示自然正文。
- embedding 文本可以带标题和 section，提高召回。
- keyword search_text 也可以带标题和 section。

### 6.7 重建索引

切块策略变更必须触发重建：

- 新上传文档自动使用新策略。
- 旧文档需要管理后台批量重建索引。
- 重建会生成新 document_version 或至少新 index_version。更安全的做法是新 document_version，避免旧 chunk 与新 chunk 混杂。

### 6.8 测试

测试用例：

- Markdown 多级标题生成 heading_path。
- PDF `[page N]` 能传播 page_start/page_end。
- 超长段落按句子切分。
- 表格 block 不被拆散。
- source_offsets 包含 block_start/block_end。
- 重复执行 chunk 阶段不重复插入 chunk。
- 新 chunker 生成的 chunk 可完整走 embedding/index/publish。

## 7. P3 精细化检索策略

### 7.1 目标

让检索更准确，减少“无关片段也被送给 LLM”的情况。

### 7.2 多 query 召回

接入 P1 rewrite 后，检索输入变为：

```text
original_query + rewritten_queries
```

每个 query 独立执行：

- keyword search
- vector search

再统一融合。

建议：

- 原始 query 权重最高。
- rewrite query 按 weight 加权。
- 多 query 结果记录 matched_query，用于诊断。

### 7.3 Weighted RRF

当前 RRF 不区分 query 权重和召回源权重。增强为：

```text
score += query_weight * source_weight / (rrf_k + rank)
```

默认权重：

```json
{
  "keyword_weight": 1.0,
  "vector_weight": 1.2,
  "original_query_weight": 1.2,
  "rewrite_query_weight": 1.0
}
```

### 7.4 召回源字段加权

关键词检索增强：

- title 命中加权。
- heading_path 命中加权。
- tags 命中加权。
- chunk 正文命中为基础分。

可以先在 SQL 中增加 score：

```text
title_match * 0.3
+ heading_match * 0.2
+ tag_match * 0.2
+ body_rank
```

### 7.5 相邻 chunk 扩展

对于 rerank 后的 top candidates：

- 加载同文档同版本的前后 1 个 chunk。
- 只作为上下文扩展，不作为 citation 主来源，除非它本身也通过权限和状态校验。
- 避免回答缺少上下文。

建议新增：

```text
ContextExpansionService
```

位置：

```text
apps/api/app/modules/context/expansion.py
```

### 7.6 文档级聚合与去冗余

问题：

- 多个相邻 chunk 可能来自同一文档同一小节，挤占上下文。

增强：

- 对同文档同 section 的 chunk 做 group。
- 每个文档或 section 限制最多 N 个 chunk。
- 使用 MMR 在相关性和多样性之间平衡。

第一阶段参数：

```json
{
  "retrieval": {
    "max_chunks_per_document": 3,
    "max_chunks_per_section": 2,
    "mmr_enabled": true,
    "mmr_lambda": 0.7
  }
}
```

### 7.7 相关性硬阈值

当前 relevance gate 依赖 rerank 成功。增强：

- rerank 成功：用 rerank score 阈值。
- rerank 不可用：用融合分数、关键词 rank、向量 score 组合阈值。
- 如果所有候选低于阈值，不调用 LLM，直接返回降级答案。

新增：

```text
CandidateQualityGate
```

输出：

```text
accepted_candidates
rejected_count
top_score
quality_reason
```

### 7.8 Context Builder 使用完整 chunk 正文

当前 Context Builder 使用 `text_preview`。增强为：

- 优先通过 `text_object_key` 读取对象存储完整 chunk。
- 对象存储不可用时降级使用 `text_preview`。
- 仍然按 token/字符预算截断。

注意：

- 对象存储读取必须在权限 gate 后。
- 不在 query log / model_call_log 中保存完整 chunk。
- model_call_log 只保留 input hash。

### 7.9 检索诊断增强

管理后台查询诊断中建议显示：

- rewrite queries。
- 每个 query 的 keyword/vector 命中数量。
- fusion 前后候选数量。
- gate 拒绝数量及原因摘要。
- rerank 分数。
- quality gate 是否拦截。
- 最终进入上下文的 chunk 数量。

列表接口仍只展示摘要，详情弹窗再展示细节。

### 7.10 测试

回归数据集扩展：

- 单问题精确命中。
- 多问题拆分命中多个文档。
- 口语化问题命中正式标题。
- 低相关问题不调用 LLM。
- rerank 不可用时仍能用质量 gate 拦截明显无关候选。
- 同文档重复 chunk 不挤占全部上下文。
- 相邻 chunk 扩展不越权。

## 8. 契约与配置变更

### 8.1 API 契约

`POST /internal/v1/queries` 和 `/internal/v1/query-streams`：

- `kb_ids` 从必填改为可选或允许空数组。
- 响应可选增加：

```json
{
  "query_scope": {
    "mode": "auto_all_accessible",
    "resolved_kb_count": 3
  },
  "retrieval_debug": {
    "rewrite_count": 3,
    "candidate_count": 12
  }
}
```

注意：普通用户响应不要暴露内部 trace、完整 rewrite prompt、完整 chunk。debug 字段应受配置控制，默认只给最小摘要。

### 8.2 Config Schema

新增或扩展：

```json
{
  "retrieval": {
    "auto_scope_enabled": true,
    "query_rewrite_enabled": true,
    "query_rewrite_max_queries": 4,
    "query_rewrite_use_conversation": true,
    "query_rewrite_recent_messages": 6,
    "keyword_weight": 1.0,
    "vector_weight": 1.2,
    "original_query_weight": 1.2,
    "rewrite_query_weight": 1.0,
    "max_chunks_per_document": 3,
    "max_chunks_per_section": 2,
    "mmr_enabled": true,
    "mmr_lambda": 0.7,
    "candidate_quality_min_score": 0.05,
    "context_expand_neighbors": 1,
    "context_use_full_chunk_text": true
  },
  "chunk": {
    "strategy": "structure_aware",
    "target_tokens": 500,
    "max_tokens": 900,
    "overlap_tokens": 80,
    "min_chunk_tokens": 80,
    "preserve_tables": true,
    "preserve_code_blocks": true
  },
  "timeout": {
    "query_rewrite_ms": 3000
  }
}
```

需要同步：

- `docs/contracts/config.schema.json`
- `docs/contracts/config-schema.md`
- 初始化示例配置
- 管理后台配置管理表单

## 9. 数据库与迁移

第一阶段尽量复用现有表：

- `chunks.source_offsets` 存结构元数据。
- `chunks.heading_path` 存可读 heading。
- `chunks.page_start/page_end` 存页码。
- `keyword_index_entries.search_text` 增强索引文本。
- `query_logs` 继续存摘要。
- `model_call_logs` 存 rewrite / rerank / llm 调用摘要。

建议新增字段或表：

1. `query_logs.rewrite_count`
2. `query_logs.resolved_kb_count`
3. `query_logs.query_scope_mode`
4. `query_retrieval_diagnostics` 可选，仅管理后台诊断详情使用

如果短期不想增加诊断表，可以先把检索诊断详情保存在 `query_logs` 的 JSON 字段；若当前无 JSON 字段，则新增表更清晰。

## 10. 安全边界

必须保持：

- Rewrite 不参与权限判断。
- Rewrite 不能扩大用户可访问知识库。
- 自动知识库范围只能由后端权限上下文计算。
- 每个 rewritten query 的召回仍必须带 PermissionFilter。
- 相邻 chunk 扩展必须重新检查权限、状态、active index 和 access block。
- Context Builder 读取完整 chunk 前必须确认候选已通过 gate。
- Query log、model_call_log、audit 不记录完整 prompt、完整 chunk、secret、token。
- 如果 rewrite / rerank / vector / LLM 任一环节失败，必须降级而不是越权或返回空白。

## 11. 测试与验收矩阵

### 11.1 单元测试

| 模块 | 用例 |
| --- | --- |
| Query Scope | 空 kb_ids 自动解析可访问知识库、无可访问知识库降级、显式越权拒绝 |
| Query Rewrite | 复合问题拆分、非法 JSON fallback、最多 query 数、最近会话指代补全 |
| Chunker | 标题路径、页码传播、句子切分、表格保留、source_offsets |
| Retrieval | Weighted RRF、字段加权、MMR、相邻 chunk 扩展、质量 gate |
| Context | 完整 chunk 对象读取、对象不可用降级 preview、预算截断 |
| Security | rewrite 不越权、neighbor expansion 不越权、source/citation 仍二次校验 |

### 11.2 集成测试

- Markdown 多标题文档导入后，查询小节问题能命中对应 heading。
- PDF 导入后 citation 带页码。
- 不选择知识库时自动查全部可访问知识库。
- 复合问题能返回多个主题的 citation。
- 低相关问题不调用 LLM。
- rerank provider 失败后仍有可解释降级。

### 11.3 回归评测

扩展 `query-regression.p0.jsonl` 或新增：

```text
docs/examples/query-regression.rag-enhancement.jsonl
```

指标：

- recall@k
- citation_count
- expected_citation_title_terms
- required_keywords
- allow_degraded
- expected_degrade_reason
- no_llm_when_low_relevance

## 12. 分阶段交付计划

### P0 自动搜索全部可访问知识库

交付：

- Query API 支持空 `kb_ids`。
- 后端自动解析 queryable kb ids。
- 前端默认“全部可访问知识库”。
- 查询日志记录 scope 摘要。

验收：

- 不选择知识库可查询。
- 无知识库可用时返回解释性答案。
- 越权知识库不会进入检索。

### P1 Query Rewrite

交付：

- QueryRewriteService。
- 规则 fallback。
- LLM rewrite runtime。
- 多 query 检索。
- rewrite model call log。

验收：

- 一次提多个问题可拆成多个检索 query。
- rewrite 失败仍使用原始问题。
- 不记录完整 prompt。

### P2 结构化切块与元数据增强

交付：

- ParsedBlock / CleanedBlock。
- StructureAwareChunker。
- 页码、heading_path、block offsets、section metadata。
- keyword/vector index text 增强。
- 管理后台重建索引验收。

验收：

- 新导入 Markdown/PDF/DOCX 文档 chunk 元数据明显改善。
- citation 页码不再普遍为空。
- 旧文档重建后使用新 chunker。

### P3 精细化检索

交付：

- Weighted RRF。
- 字段加权关键词召回。
- CandidateQualityGate。
- 相邻 chunk 扩展。
- 文档级去冗余 / MMR。
- 检索诊断详情。

验收：

- 无关问题不再把低相关 chunk 交给 LLM。
- 多文档复合问题命中更稳定。
- 查询诊断可解释候选从召回到上下文的流转。

## 13. 风险与处理

| 风险 | 影响 | 处理 |
| --- | --- | --- |
| Query Rewrite 生成错误 query | 召回偏移 | 保留原始 query，rewrite 只作为额外检索 query |
| 自动搜索全部知识库导致召回量过大 | 延迟和成本上升 | 限制 resolved kb 数、候选总数、按最近活跃 / 权限 scope 做可配置上限 |
| 结构化切块改变 chunk id | citation 和历史索引变化 | 通过新 document_version / index_version 发布，不复用旧 active index |
| 完整 chunk 进入上下文导致 token 超限 | LLM 成本上升 | Context Builder 严格预算，必要时摘要或截断 |
| 相邻 chunk 扩展越权 | 严重安全问题 | expansion 必须复用 PermissionFilter 和 CandidateGate |
| 诊断暴露内部字段 | 信息泄漏 | 普通响应只给摘要，管理详情也不展示完整 prompt/chunk |

## 14. 最小可行改造边界

如果需要最快提升体验，最小闭环是：

1. P0 自动搜索全部可访问知识库。
2. P1 规则版 Query Rewrite，不先接 LLM rewrite。
3. P3 CandidateQualityGate，避免低相关内容进入 LLM。
4. P2 只先增强 Markdown/PDF 页码与 heading metadata。

这四项可以在不大幅扩大模型调用成本的情况下明显改善用户体验。

