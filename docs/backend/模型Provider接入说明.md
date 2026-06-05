# 模型 Provider 接入说明

更新时间：2026-06-03

本文说明当前后端如何接入 embedding、rerank 和 LLM provider，以及配置、Secret、超时、错误和验证要求。

## Provider 类型

当前模型链路包含三类 provider：

- embedding：用于 query embedding 和文档 chunk embedding。
- rerank：用于候选重排。
- LLM：用于最终回答生成和流式 token 输出。

本地开发默认使用：

- TEI embedding：`jinaai/jina-embeddings-v2-base-zh`
- TEI rerank：`BAAI/bge-reranker-base`
- OpenAI-compatible LLM provider：由 active config 指定

## 配置来源

模型 provider 配置来自 active config，不从 `.env` 直接读取业务 provider 信息。

主要配置分区：

- `model_gateway.providers.embedding`
- `model_gateway.providers.rerank`
- `model_gateway.providers.llm`
- `model.embedding_model`
- `model.embedding_dimension`
- `model.embedding_normalize`
- `model.rerank_model`
- `model.llm_model`
- `timeout.embedding_ms`
- `timeout.vector_search_ms`
- `timeout.rerank_ms`
- `llm.total_timeout_ms`
- `llm.temperature`
- `llm.max_tokens`

配置版本由配置管理发布为 active 后生效。

## Secret 引用

provider 密钥使用 secret ref，不在配置中保存明文。

默认 secret ref：

```text
secret://rag/model/embedding-api-key
secret://rag/model/rerank-api-key
secret://rag/model/llm-api-key
```

配置中也可以为具体 provider 指定 auth ref。后端通过 Secret Store 解析并注入 provider client。

如果 provider 不需要密钥，可以不配置 auth ref。

## Embedding Provider

当前 embedding client 支持：

- TEI 风格接口。
- OpenAI-compatible embeddings 接口。

默认路径规则：

- provider type 为 `tei` 时默认使用 `/embed`。
- 其他 provider 默认使用 `/v1/embeddings`。
- 如果配置了 `embeddings_path`，优先使用配置值。

TEI payload：

```json
{
  "inputs": ["text"]
}
```

OpenAI-compatible payload：

```json
{
  "model": "embedding-model",
  "input": ["text"]
}
```

返回解析支持 `data[].embedding`、`embedding`、`embeddings` 等常见结构。

关键校验：

- 返回 embedding 数量必须等于输入文本数量。
- 如果配置了 `embedding_dimension`，维度必须匹配。
- 如果配置了 normalize，client 会执行向量归一化。

常见错误码：

- `EMBEDDING_PROVIDER_HTTP_ERROR`
- `EMBEDDING_PROVIDER_UNAVAILABLE`
- `EMBEDDING_PROVIDER_RESPONSE_INVALID`
- `EMBEDDING_COUNT_MISMATCH`
- `EMBEDDING_DIMENSION_MISMATCH`

## Rerank Provider

当前 rerank client 支持：

- TEI rerank。
- OpenAI-compatible / 常见 rerank 风格接口。

TEI payload：

```json
{
  "query": "question",
  "texts": ["candidate text"],
  "raw_scores": true,
  "return_text": false,
  "truncate": true
}
```

OpenAI-compatible payload：

```json
{
  "model": "rerank-model",
  "query": "question",
  "documents": ["candidate text"],
  "top_n": 10
}
```

rerank 不可用时，查询链路会降级使用融合分数，不应直接让整个查询失败。

常见错误码：

- `RERANK_PROVIDER_HTTP_ERROR`
- `RERANK_PROVIDER_UNAVAILABLE`
- `RERANK_PROVIDER_RESPONSE_INVALID`

## LLM Provider

当前 LLM client 使用 OpenAI-compatible Chat Completions 协议。

非流式 payload：

```json
{
  "model": "llm-model",
  "messages": [],
  "temperature": 0.1,
  "max_tokens": 800,
  "stream": false
}
```

流式 payload：

```json
{
  "model": "llm-model",
  "messages": [],
  "temperature": 0.1,
  "max_tokens": 800,
  "stream": true
}
```

支持通过配置追加 `openai_extra_body`。

流式响应按 SSE `data:` 行解析，识别 `[DONE]`，并从 `choices[].delta.content` 或兼容字段中提取 token。

常见错误码：

- `LLM_PROVIDER_HTTP_ERROR`
- `LLM_PROVIDER_UNAVAILABLE`
- `LLM_PROVIDER_RESPONSE_INVALID`

## HTTP 认证

如果解析到 auth token，模型 HTTP client 会添加：

```text
Authorization: Bearer <token>
```

当 provider 返回 401 / 403 时，优先检查：

- Secret ref 是否存在。
- Secret value 是否正确。
- active config 是否指向正确 provider。
- provider 是否要求不同认证头。

如果 provider 不使用 Bearer token，需要扩展 provider client 或配置结构，而不是把密钥硬编码在 URL 或日志里。

## 超时建议

当前默认：

- embedding timeout：`3000ms`
- vector search timeout：`3000ms`
- LLM total timeout：`20000ms`

建议：

- embedding 和 vector search 保持短超时，失败后允许关键词降级。
- rerank 可短超时，失败后使用融合分数。
- LLM 超时不应输出无引用答案，应返回检索结果和降级说明。

## ServiceBootstrap 校验

配置发布时会执行依赖校验和 ServiceBootstrap。provider 相关配置如果缺失、不可达或响应不符合预期，配置发布可能失败。

发布失败时：

- active config 不切换。
- 目标版本可能标记为 failed。
- 返回配置依赖失败错误。
- 写配置发布失败审计。

## 模型调用日志

模型调用日志记录：

- provider route。
- 模型名称。
- 调用方。
- 调用类型。
- 状态。
- latency。
- token 摘要。
- prompt / input / output hash。
- 错误码。
- 是否降级。

模型调用日志不应保存或展示：

- 完整 prompt。
- 完整文档原文。
- secret value。
- token。

## 接入新 Provider 的步骤

1. 确认 provider 协议属于 TEI、OpenAI-compatible，或需要新增 adapter。
2. 在 Secret Store 写入密钥，得到 secret ref。
3. 在配置管理中新建或编辑配置版本。
4. 填写 provider `base_url`、`type`、path、model、timeout 和 secret ref。
5. 校验配置。
6. 激活配置。
7. 执行 provider smoke 或查询回归。
8. 查看模型调用日志确认 route、latency、error_code 正常。

## 禁止事项

- 禁止把 provider 密钥写入 `.env` 后让业务模块直接读取。
- 禁止在日志中输出完整 prompt、文档原文或 secret。
- 禁止为了接入 provider 而跳过 citation 校验。
- 禁止 embedding 维度不匹配时继续写入 Qdrant。
- 禁止 provider 不可用时静默返回空答案。
