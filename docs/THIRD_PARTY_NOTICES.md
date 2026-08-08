# Third-Party Notices

本文件列出当前 Demo 实际分发或直接使用的第三方软件。仅用于架构调研、未复制到 Demo
的参考仓库列在 `references/README.md`，不作为本作品的组成部分。

| 组件 | 用途 | 许可证 |
|---|---|---|
| React / React DOM | 前端界面运行时 | MIT |
| Plyr | HTML5 视频播放器 | MIT |
| Lucide React | 界面图标 | ISC |
| Zod | 演示数据运行时校验 | MIT |
| Vite | 构建工具 | MIT |
| Vitest | 单元测试 | MIT |
| Playwright | 端到端与响应式测试 | Apache-2.0 |
| axe-core Playwright | 可访问性测试 | MPL-2.0 |
| faster-whisper 1.2.1 | 快速 Whisper 推理与词级时间戳 | MIT |
| stable-ts 2.19.1 | 基于音频静音区的 Whisper 时间轴精修 | MIT |
| OpenAI Whisper 20250625 | stable-ts 兼容运行依赖 | MIT |

Demo 不包含真实迅雷用户内容。以下媒体来自 Wikimedia Commons，均按 CC BY 3.0
分发，并在产品详情页保留作者、来源页和许可证链接：

| 媒体 | 作者 | 来源 | 许可证 |
|---|---|---|---|
| Lecture 1.3 Python as a Language | Charles Severance（University of Michigan） | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Pythonlectureseverance1.3.webm) | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) |
| Reading Files with Multiple Lines in Python | Adam Gaweda | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Reading_Files_with_Multiple_Lines_in_Python.webm) | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) |
| Catching Multiple Exception Types in Python | Adam Gaweda | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Catching_Multiple_Exception_Types_in_Python.webm) | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) |

海报与章节接触表均从上述公开授权视频生成。主视频的英文字幕来自其 Wikimedia
Commons TimedText 页面，Demo 将字幕解析为章节、摘要与可跳转问答证据。“Catching
Multiple Exception Types in Python”的字幕由 faster-whisper 1.2.1（MIT）和
`Systran/faster-whisper-tiny.en` 在本地 CPU `int8` 模式下生成。
