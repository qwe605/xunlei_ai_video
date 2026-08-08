# 迅雷 AI 片库

迅雷云盘视频的 AI 内容理解 Demo：自动章节、整片摘要、自然语言检索，以及带可跳转
时间证据的视频问答。

## 项目状态

内置样例使用经过 schema 校验的预生成索引，搜索排序、证据约束、拒答和视频时间跳转
均在浏览器中真实执行。中文视频由 FastAPI 服务运行 FunASR Paraformer-zh，并从纯音频
识别时间轴生成摘要、关键词和章节；faster-whisper 作为其他语言和服务异常时的回退。
MiniMax-M3 在同一次内容整理请求中完成内容理解与保守术语纠错，避免额外网络往返。
密钥不进入浏览器或源码，服务端分析完成后删除原始临时视频。

默认中文链路使用 Paraformer-zh、FSMN-VAD、CT-Punc、中文热词和句级时间戳。视频中的
内嵌字幕不参与产品生成，只在开发环境作为标准答案离线计算字符错误率。

当前片库由 3 条中文真实片段和 1 条英文基准教程组成，全部带预计算字幕、摘要和章节。
任何代码、接口、素材或流程修改都必须在同一轮工作中同步更新对应中文文档。

## 快速开始

完整体验（包含 AI 字幕、摘要和章节生成）：

```powershell
.\tools\start-local-demo.ps1
```

## 标准命令

| 命令 | 用途 |
|---|---|
| `.\tools\preflight.ps1` | 检查开发与验收所需环境 |
| `.\tools\verify.ps1` | 执行 Harness 校验、Lint、单测、构建、审计和 E2E |
| `.\tools\build-submission.ps1 -VideoPath <录屏.mp4>` | 验证并生成 PDF、离线包、校验和与提交压缩包 |
| `npm.cmd run capture:qa` | 单独生成评委验收截图，不参与默认门禁 |
| `npm.cmd run test:visual` | 只运行视觉回归测试 |
| `.\tools\preflight.ps1 -IncludeSubmission` | 额外检查 PDF、旁白和录屏依赖 |

统一验证会把机器可读凭证写入 `output/run-receipt.json`，历史运行保存在
`output/harness-runs/`。这些文件是本地证据，不进入版本控制。

首次构建 PDF 和提交包前安装固定的 Python 依赖：

```powershell
python -m pip install -r .\tools\requirements-submission.txt
.\tools\preflight.ps1 -IncludeSubmission
```

也可以通过 `build-submission.ps1 -PythonPath <python.exe>` 使用已安装这些依赖的独立
Python 环境。需要从旁白和原始录屏重新合成视频时，再使用
`preflight.ps1 -IncludeVideoProduction` 检查 SAPI 与 FFmpeg。

## 目录

| 路径 | 职责 |
|---|---|
| `app/` | React 产品 Demo、单元测试与 Playwright 验收 |
| `backend/` | FastAPI、SQLAlchemy ORM、Repository、AI 集成与测试 |
| `deploy/nginx/` | React 静态资源、History 回退与 FastAPI 反向代理配置 |
| `harness/` | AI 编码评测、基线、晋级规则与记录 schema |
| `.agents/skills/` | 项目级 AI 开发 Skills |
| `docs/decisions/` | 已接受的架构决策 |
| `docs/reports/` | 审查和阶段报告 |
| `references/` | 第三方参考仓库及许可证索引 |
| `tools/` | 环境预检、统一验证和提交材料脚本 |

## 文档入口

- 产品范围：[`AI产品创意方案-迅雷AI片库.md`](AI产品创意方案-迅雷AI片库.md)
- 实施计划：[`迅雷AI片库-详细实施计划.md`](迅雷AI片库-详细实施计划.md)
- 技术复用：[`技术选型与开源复用计划.md`](技术选型与开源复用计划.md)
- Demo 说明：[`app/README.md`](app/README.md)
- 后端分层：[`backend/README.md`](backend/README.md)
- 架构决策：[`docs/decisions/ADR-004-FastAPI与React分层架构.md`](docs/decisions/ADR-004-FastAPI与React分层架构.md)
- AI 工作流审查：[`docs/reports/AI编码工作流审查报告-Better-Harness.md`](docs/reports/AI编码工作流审查报告-Better-Harness.md)

## AI 开发规则

代理必须先读 `AGENTS.md`，只加载与任务相关的 Skills。参考实现应先通过
`references/README.md` 定位，禁止无边界递归扫描第三方仓库。完成任务前必须运行统一
验证，并以运行凭证和实际测试结果作为完成证据。
