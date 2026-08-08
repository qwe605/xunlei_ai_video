# 迅雷 AI 片库开发约定

## 产品目标

本项目面向迅雷云盘视频用户，核心体验是：

1. 自动识别视频结构并生成可跳转章节。
2. 为云端视频生成摘要、关键词和关键片段。
3. 支持自然语言提问，返回有依据的答案与可直接跳转的时间片段。

产品范围和用户价值以 `AI产品创意方案-迅雷AI片库.md` 为准，技术复用边界以
`技术选型与开源复用计划.md` 为准。参考仓库只能提供实现思路和兼容许可下的代码，
不能替代产品自身的交互设计。

## 项目 Skills

项目级 Skills 位于 `.agents/skills/`。开发时按任务触发：

- UI、组件、响应式与可访问性：`frontend-ui-engineering`
- React 性能与渲染：`vercel-react-best-practices`
- FastAPI 工程结构：`fastapi-templates`
- REST API 设计：`api-design-principles`
- 自然语言视频检索：`hybrid-search-implementation`、`rag-implementation`
- 摘要提示词与结构化输出：`prompt-engineering-patterns`
- 检索和摘要质量评估：`llm-evaluation`
- 浏览器端验收：`playwright-best-practices`
- 故障定位：`systematic-debugging`
- 安全与 AI 输出边界：`security-and-hardening`
- 架构说明、必要注释与 ADR：`documentation-and-adrs`
- 代码复核：`code-review-and-quality`
- 交付前证据检查：`verification-before-completion`

## 实施约束

- 先复用 `references/` 中已经筛选的组件和模式，再决定是否新增依赖。
- 使用参考代码前先读 `references/README.md`，按索引定向读取候选文件；禁止无边界递归
  搜索整个 `references/` 目录。
- Demo 可以使用明确标识的样例数据，但不得把模拟能力描述成已经接入的线上能力。
- 视频检索结果必须包含视频 ID、起止时间、证据文本和置信度，不能只返回自然语言答案。
- 模型输出一律视为不可信数据；解析后必须经过 schema 校验才能进入检索、数据库或 UI。
- 用户视频、字幕和向量索引按用户隔离，日志不得记录原始隐私内容。
- 注释解释非显而易见的原因、约束和兼容性，不复述代码，不保留注释掉的旧实现。
- UI 必须覆盖加载、空数据、失败和完成状态，并在桌面与移动视口验证。
- 完成一个功能前至少运行对应测试、构建和关键交互检查；不得用“应该能运行”代替证据。

## AI 编码 Harness

- 开始任务前写明目标、非目标、风险和验收标准，并只加载与任务相关的 Skills。
- 产品修改应在 Git 分支或 worktree 中完成；不得直接改写已记录的基线结果。
- 统一使用根目录 `tools/verify.ps1` 验证。运行凭证写入 `output/run-receipt.json`。
- 训练评测用于迭代，留出评测只用于晋级判断；训练集改善但留出集退化时不得晋级。
- 用户数据处理、提示词、依赖、构建与交付脚本的修改必须经过独立复核。
- 失败 trace 在移除用户内容、密钥和绝对个人路径后，才能进入评测候选库。
- “评委截图生成”与视觉回归是两类任务：前者生成交付素材，后者必须使用稳定基线断言。

## 参考代码边界

`.agents/skills/api-design-principles/assets/rest-api-template.py` 仅是结构示例，其中通配
`allowed_hosts` 和 CORS 配置不可直接用于交付环境。所有参考代码在采用前都要按本项目
的鉴权、隐私、许可证和依赖版本重新审查。
