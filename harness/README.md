# AI 编码 Harness

本目录把 `AGENTS.md` 中的文字规范转换为可校验、可比较的评测资产。它衡量 AI 编码流程，
不替代产品单元测试和 E2E。

## 文件

| 文件 | 作用 |
|---|---|
| `config.json` | Harness 版本、必需 Skills 和晋级规则 |
| `baseline.json` | 当前已接受工作流的基线结果 |
| `evals/train.json` | 实现代理可见的迭代任务 |
| `evals/holdout.json` | 仅评测者用于晋级判断的任务 |
| `schemas/run-receipt.schema.json` | 统一验证凭证的数据契约 |
| `scorecard.json` | 候选 Harness 的比较记录 |

## 运行

```powershell
.\tools\check_harness.ps1
.\tools\verify.ps1 -TaskId XL-0001 `
  -SkillsLoaded frontend-ui-engineering,verification-before-completion
.\tools\evaluate-harness-candidate.ps1 -CandidatePath .\candidate-result.json
```

## 晋级规则

1. 先在干净分支或 worktree 运行已接受基线。
2. 一次只改变一个主要 Harness 表面，例如 Skill、提示词或验证器。
3. 候选方案先跑训练集，再由独立评测者运行留出集。
4. 自动检查必须全部通过，人工检查不得出现高风险否决项。
5. 训练集通过数不得下降，留出集通过数必须不低于基线，综合通过数必须提升。
6. 未晋级候选仍记录原因，但不得覆盖 `baseline.json`。

候选结果必须包含训练/留出通过数、唯一主要变更和独立复核结果。当前
`baseline.json` 的任务评测分数仍为 `null`，因此比较器会拒绝晋级；只有实际完成隔离
worktree 评测后才能填入分数，不能用产品单元测试数量代替。

`holdout.json` 存在于当前本地项目是为了让训练营评委能够审查方法完整性。实际团队环境应把
留出用例放在实现代理无读取权限的评测仓库或 CI Secret 管理的制品中。

## Trace 隐私

运行凭证只记录命令名称、退出码、耗时和环境版本，不记录用户视频、字幕、提示词原文、密钥
或个人目录内容。浏览器 trace 进入失败样本库前必须脱敏。
