import type { FieldSection } from "@/features/setup/setupFieldTypes";

// 基础初始化字段：访问令牌、首个管理员、组织和基础设施。
export const accessSection: FieldSection = {
  title: "访问凭证",
  fields: [
    {
      key: "setupToken",
      label: "初始化令牌",
      input: "password",
      placeholder: "从后端启动日志复制初始化令牌（JWT）",
      hint: "用于调用初始化校验与初始化提交接口；请使用后端启动日志输出的 setup JWT。",
      span: "full",
      required: true,
    },
  ],
};

export const adminSection: FieldSection = {
  title: "首个管理员",
  fields: [
    { key: "adminUsername", label: "登录名", input: "text", hint: "首个系统管理员的唯一登录标识。", required: true },
    { key: "adminDisplayName", label: "显示名", input: "text", hint: "用于管理后台展示、操作记录归属和审计事件摘要。", required: true },
    { key: "adminPassword", label: "初始密码", input: "password", placeholder: "************", hint: "用于创建首个管理员登录凭据；必须满足当前密码策略。", required: true },
    { key: "adminPasswordConfirm", label: "确认密码", input: "password", placeholder: "************", hint: "用于确认初始密码输入无误；两次输入必须完全一致。", required: true },
    { key: "adminEmail", label: "邮箱", input: "email" },
    { key: "adminPhone", label: "手机号", input: "text" },
  ],
};

export const organizationSection: FieldSection = {
  title: "组织初始化",
  fields: [
    { key: "enterpriseName", label: "企业名称", input: "text", hint: "初始化流程将创建该企业作为系统的全局业务主体。", required: true },
    { key: "enterpriseCode", label: "企业编码", input: "text", hint: "企业的稳定内部标识；建议使用字母、数字、下划线或连字符。", required: true },
    { key: "departmentName", label: "默认部门名称", input: "text", hint: "初始化流程将创建该部门，并将首个管理员归属到此部门。", required: true },
    { key: "departmentCode", label: "默认部门编码", input: "text", hint: "部门的稳定内部标识；后续组织结构扩展将基于该编码体系。", required: true },
  ],
};

export const infraSection: FieldSection = {
  title: "基础设施",
  fields: [
    {
      key: "secretProviderEndpoint",
      label: "密钥服务地址",
      input: "text",
      hint: "Secret Store 的 provider 标识或服务地址；使用 PostgreSQL secrets 表时填写 postgres://local-secrets。",
      span: "full",
      required: true,
    },
    {
      key: "redisUrl",
      label: "Redis 地址",
      input: "text",
      hint: "后端服务访问 Redis 的连接地址；同一 Docker 网络可使用 redis://redis:6379/0，跨主机访问请使用实际内网地址。",
      span: "full",
      required: true,
    },
    {
      key: "minioEndpoint",
      label: "MinIO 地址",
      input: "text",
      hint: "后端服务访问对象存储的 S3-compatible endpoint；同一 Docker 网络可使用 http://minio:9000。",
      required: true,
    },
    { key: "minioBucket", label: "存储桶名称", input: "text", hint: "用于保存导入文件、解析产物和索引相关对象；该 bucket 必须已存在且可读写。", required: true },
    { key: "minioRegion", label: "存储区域", input: "text", hint: "对象存储区域标识；本地环境可使用 local，生产环境应与存储服务配置一致。", required: true },
    { key: "objectKeyPrefix", label: "对象路径前缀", input: "text", hint: "用于隔离系统写入的对象路径；建议以斜杠结尾，例如 p0/。", required: true },
    {
      key: "minioAccessKeyRef",
      label: "MinIO 访问密钥引用",
      input: "text",
      hint: "填写 Secret Store 中的 access key 引用；不得填写 access key 明文。",
      span: "full",
      required: true,
    },
    {
      key: "minioSecretKeyRef",
      label: "MinIO 私有密钥引用",
      input: "text",
      hint: "填写 Secret Store 中的 secret key 引用；不得填写 secret key 明文。",
      span: "full",
      required: true,
    },
    {
      key: "qdrantBaseUrl",
      label: "Qdrant 地址",
      input: "text",
      hint: "后端服务访问向量数据库的 HTTP 地址；同一 Docker 网络可使用 http://qdrant:6333。",
      required: true,
    },
    {
      key: "qdrantApiKeyRef",
      label: "Qdrant API Key 引用",
      input: "text",
      hint: "可选。Qdrant 开启 API Key 鉴权时填写 Secret Store 引用，例如 secret://rag/qdrant/api-key；未开启鉴权时留空。",
      span: "full",
    },
    { key: "collectionPrefix", label: "向量集合前缀", input: "text", hint: "用于生成和识别 Qdrant collection；变更前需评估既有索引兼容性。", required: true },
    {
      key: "vectorDistance",
      label: "向量距离",
      input: "select",
      hint: "用于设置 Qdrant collection 的距离计算方式；应与 embedding 模型归一化策略保持一致。",
      required: true,
      options: [
        { label: "cosine", value: "cosine" },
        { label: "dot", value: "dot" },
        { label: "euclidean", value: "euclidean" },
      ],
    },
  ],
};
