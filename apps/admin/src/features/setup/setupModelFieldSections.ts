import type { FieldSection } from "@/features/setup/setupFieldTypes";

// 模型、检索、切片和缓存字段。
export const modelSection: FieldSection = {
  title: "模型与检索",
  fields: [
    {
      key: "modelGatewayMode",
      label: "模型服务模式",
      input: "select",
      hint: "模型调用采用外部 provider 模式；系统通过下方 provider 地址访问 embedding、rerank 和 LLM 服务。",
      required: true,
      options: [{ label: "external", value: "external" }],
    },
    {
      key: "embeddingProviderBaseUrl",
      label: "向量模型服务地址",
      input: "text",
      hint: "Embedding provider 的基础 URL；同一 Docker 网络可使用 http://tei-embedding:80，生产环境应指向正式模型服务。",
      span: "full",
      required: true,
    },
    {
      key: "embeddingProviderApiKey",
      label: "向量模型访问密钥",
      input: "password",
      hint: "可选。需要鉴权时填写明文 API Key；仅用于本次初始化提交，后端会加密写入 Secret Store，active config 不保存明文。",
      span: "full",
    },
    {
      key: "rerankProviderBaseUrl",
      label: "重排模型服务地址",
      input: "text",
      hint: "Rerank provider 的基础 URL；同一 Docker 网络可使用 http://tei-rerank:80，生产环境应指向正式模型服务。",
      span: "full",
      required: true,
    },
    {
      key: "rerankProviderApiKey",
      label: "重排模型访问密钥",
      input: "password",
      hint: "可选。需要鉴权时填写明文 API Key；仅用于本次初始化提交，后端会加密写入 Secret Store，active config 不保存明文。",
      span: "full",
    },
    {
      key: "llmProviderBaseUrl",
      label: "大模型服务地址",
      input: "text",
      hint: "OpenAI-compatible LLM provider 的基础 URL；当前部署未内置 LLM 服务，必须填写可访问的正式地址。",
      span: "full",
      required: true,
    },
    {
      key: "llmProviderApiKey",
      label: "大模型访问密钥",
      input: "password",
      hint: "可选。需要鉴权时填写明文 API Key；仅用于本次初始化提交，后端会加密写入 Secret Store，active config 不保存明文。",
      span: "full",
    },
    { key: "embeddingDimension", label: "向量维度", input: "number", hint: "必须与 embedding 模型输出维度及 Qdrant collection 维度保持一致。", min: 1, step: 1, required: true },
    { key: "embeddingModel", label: "向量模型", input: "text", hint: "填写 embedding provider 暴露的模型名称；导入与查询应使用兼容模型。", required: true },
    { key: "rerankModel", label: "重排模型", input: "text", hint: "填写 rerank provider 暴露的模型名称，用于对召回候选进行二次排序。", required: true },
    { key: "llmModel", label: "主大模型", input: "text", hint: "填写 LLM provider 暴露的主模型名称，用于答案生成。", required: true },
    { key: "llmFallbackModel", label: "回退大模型", input: "text", hint: "主模型不可用时使用的备用模型；应与业务质量和成本策略一致。", required: true },
    { key: "keywordLanguage", label: "关键词语言", input: "text", hint: "关键词检索语言配置；中文全文检索默认使用 zh。", required: true },
    { key: "keywordAnalyzer", label: "分词器", input: "text", hint: "PostgreSQL 全文检索使用的分词器名称；中文环境默认使用 zhparser。", required: true },
    { key: "vectorTopK", label: "向量召回数量", input: "number", hint: "向量检索阶段返回的候选片段数量。", min: 1, step: 1 },
    { key: "keywordTopK", label: "关键词召回数量", input: "number", hint: "关键词检索阶段返回的候选片段数量。", min: 1, step: 1 },
    { key: "rerankInputTopK", label: "重排输入数量", input: "number", hint: "进入 rerank 阶段的候选片段数量，应结合模型延迟和召回质量设定。", min: 1, step: 1 },
    { key: "rerankMinScore", label: "重排最低分", input: "number", hint: "重排成功后低于该分数的片段不会进入答案上下文。", min: 0, step: 0.01 },
    { key: "finalContextTopK", label: "最终上下文数量", input: "number", hint: "进入答案生成上下文的最终片段数量。", min: 1, step: 1 },
    { key: "maxContextTokens", label: "最大上下文 Token 数", input: "number", min: 1, step: 1 },
  ],
};

export const chunkSection: FieldSection = {
  title: "文档切片策略",
  fields: [
    {
      key: "chunkDefaultSizeTokens",
      label: "切片大小 Token 数",
      input: "number",
      hint: "单个 chunk 的目标 token 数；该配置影响后续导入、重建索引和召回粒度。",
      min: 1,
      step: 1,
      required: true,
    },
    {
      key: "chunkOverlapTokens",
      label: "切片重叠 Token 数",
      input: "number",
      hint: "相邻 chunk 之间保留的重叠 token 数；用于降低语义边界截断带来的召回损失。",
      min: 0,
      step: 1,
      required: true,
    },
    {
      key: "chunkStrategyMode",
      label: "切片策略",
      input: "select",
      hint: "heading_paragraph 优先按标题和段落边界切分；fixed_tokens 按固定 token 窗口切分。",
      required: true,
      options: [
        { label: "heading_paragraph", value: "heading_paragraph" },
        { label: "fixed_tokens", value: "fixed_tokens" },
      ],
    },
    {
      key: "chunkPreserveTables",
      label: "保留表格结构",
      input: "checkbox",
      hint: "启用后切片器应尽量避免拆散同一张表格，提升表格问答的引用完整性。",
      group: "chunk-preserve",
    },
    {
      key: "chunkPreserveCodeBlocks",
      label: "保留代码块结构",
      input: "checkbox",
      hint: "启用后切片器应尽量避免拆散同一个代码块，减少技术文档上下文破碎。",
      group: "chunk-preserve",
    },
    {
      key: "chunkPreserveContractClauses",
      label: "保留合同条款结构",
      input: "checkbox",
      hint: "启用后切片器应尽量保留条款编号和条款正文的完整性。",
      group: "chunk-preserve",
    },
  ],
};

export const cacheSection: FieldSection = {
  title: "缓存开关",
  fields: [
    { key: "queryEmbeddingEnabled", label: "查询向量缓存", input: "checkbox", hint: "启用后可复用相同查询的 embedding 结果，降低重复模型调用成本。", group: "cache-switch" },
    { key: "retrievalResultEnabled", label: "召回结果缓存", input: "checkbox", hint: "启用后缓存检索召回结果；缓存键必须包含权限、配置和索引版本信息。", group: "cache-switch" },
    { key: "finalAnswerEnabled", label: "最终答案缓存", input: "checkbox", hint: "启用后缓存最终答案；涉及权限变更和引用时效时需严格评估风险。", group: "cache-switch" },
    { key: "crossUserFinalAnswerAllowed", label: "允许跨用户最终答案缓存", input: "checkbox", hint: "高风险配置，可能导致不同用户之间复用答案；P0 阶段禁止开启。", group: "cache-switch" },
  ],
};
