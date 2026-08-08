# AI 字幕生成记录

## 当前演示素材

片库固定为 4 条真实有声视频，其中 3 条简体中文、1 条英文：

| 视频 ID | 语言 | 时长 | 字幕来源 |
|---|---:|---:|---|
| `parsevideo-chinese-demo` | 简体中文 | 135 秒 | FunASR + MiniMax-M3 预计算 |
| `eternal-night-survival` | 简体中文 | 135 秒 | FunASR + MiniMax-M3 预计算 |
| `eternal-night-civilization` | 简体中文 | 135 秒 | FunASR + MiniMax-M3 预计算 |
| `python-as-a-language` | 英语 | 875 秒 | Wikimedia TimedText |

三条中文素材来自用户提供视频的不同时间区间，均保留真实画面、音轨和可播放媒体。所有内置
素材的字幕、摘要、标签和章节已在构建期完成，评委打开片库时不会进入 AI 等待队列。

## 中文生成链路

用户导入视频时可选择两个真实执行档位：快速模式使用 FunASR Paraformer-zh；精准模式使用
faster-whisper large-v3 + stable-ts 2.19.1。后端会先校验预安装模型的必需文件与权重大小，健康接口通过
preciseModelReady 暴露状态；模型不完整时前端禁用精准选项，禁止让用户任务承担下载。
模式随 analysis_mode 上传表单进入后台任务，不会在失败后静默切换模型。

ASR 快速模型默认后台预热（`XUNLEI_PRELOAD_ASR=true`）。后端使用独立守护线程加载
FunASR，不占用用户任务执行器；快速、精准模型分别加锁，避免首次加载 FunASR 时把精准任务
长期阻塞在“确认 ASR 模型”。运行期不再下载 large-v3；模型未就绪时，前端直接禁用精准模式，
后端也会在读取上传内容前返回 503，避免用户上传大文件后进入无进度等待。

2026-08-08 修正快速模式的阶段显示：任务刚创建时显示“等待整理队列”，只有真正开始加载模型
时才显示“首次加载快速语音模型”；同一后端进程中模型预热完成后，快速任务会直接进入“准备
快速识别 / 识别语音”。FunASR 不提供稳定的流式转写回调，因此快速模式至少在音频解码完成和
转写返回时更新进度，避免页面误以为一直卡在 ASR 模型加载。

2026-08-08 使用 9 分钟 H.264/AAC 中文视频验证时，Xet 权重下载在约 1 GB 处停止写入并导致
ANALYSIS_FAILED。最终方案改为部署前运行 tools/install_precise_model.ps1，使用 aria2 从
ModelScope 国内 CDN 多连接断点下载，并校验 3,087,284,237 字节及 SHA256。运行期只读本地
模型，加载异常返回 ASR_MODEL_LOAD_FAILED，不再误提示转换视频格式。

同日使用用户指定的 `6月13日 (2).mp4` 完成真实转写验证：文件为 H.264/AAC、时长
541.955 秒、大小 288,568,759 字节；large-v3 本地模型加载 28.34 秒，CPU `int8` 完整转写
耗时 997.06 秒，生成 156 个原始语音段。该数据说明 CPU 精准模式约为视频时长的 1.84 倍，
因此导入界面会明确提示量级，任务执行时按已识别的音频时间持续更新 25%-79% 进度和
`已识别 mm:ss / mm:ss`，不再长时间停留在“下载或加载模型”。

1. PyAV 校验媒体和音轨可解码。
2. FunASR Paraformer-zh 配合 FSMN-VAD、CT-Punc 从纯音频生成句级时间片。
3. `prepare_segments_for_review()` 只修复紧邻的孤立短段，保留 ASR 原始停顿边界；MiniMax 可读取相邻字幕上下文，但不得按字数重估时间轴。
4. 中文预计算任务在同一次 MiniMax-M3 请求中校对全部候选段，最多 64 段，同时生成摘要、标签和章节。
5. 校订文本必须通过结构校验、简繁归一化和改写相似度保护，禁止大范围重写原识别结果。
6. `split_long_caption_segments()` 使用逗号、顿号、冒号和句末标点确定阅读边界；单个中文
   分句仍过长时，优先在“并、但是、因此、即可”等连接词前切分。
7. 最终屏幕字幕移除标点，每条最多 20 个字符、约 4.5 秒；`merge_readable_orphans()`
   只能在相同上限内合并短句，并修复“正｜因如此”“最后一只｜烛龙”等跨字幕断词。
8. 三条内置中文样例在构建期使用独立参考字幕做时间轴校准：只通过文本相似度寻找语音
   锚点、保留真实停顿并对低置信片段插值，不替换任何 AI 识别文字。校准后的字幕由
   `render_aligned_vtt()` 原样渲染，禁止再次合并或拆分。
9. 精准模式保留 faster-whisper 的词级时间戳；长句拆分时优先按词的真实起止时间切分，
   因此词间静音不会再被字符比例平均掉。FunASR 返回形状可靠的字符级时间戳时也采用同一逻辑。
10. `FasterWhisperTranscriber` 在消费分段生成器时按 `segment.end / duration` 回报真实媒体进度；
    `AnalysisService` 将其映射到 25%-79%，并限制为进度整数变化时才写数据库。
11. MiniMax 返回可解析 JSON 但字段不符合 Pydantic 约束时，后端把具体校验错误连同上次 JSON
    反馈给模型修复一次；越权、超长字幕校订和超长术语映射会先被丢弃，不再拖垮合法摘要。
12. 章节不仅校验顺序和时间上界，还要求最后章节覆盖到视频时长的 85% 以后；覆盖不足会进入
    同一次结构修复。`6月13日 (2).mp4` 复测得到 8 个章节，最后章节结束于 541.96 秒。
13. 精准模式由 stable-ts 包装现有 faster-whisper 权重，开启波形静音抑制与词轴收紧，关闭
    stable-ts 自动 regroup；最终中文分段继续使用真实词轴、标点和显示长度约束。该方案不加载
    Silero VAD 权重，运行期不会产生新的模型下载。
14. stable-ts 默认会调用系统 `ffmpeg` 读取波形；本项目改由已有 PyAV 解码为 16 kHz 单声道
    `float32` 数组，再将同一波形交给 faster-whisper 与静音分析。Windows 无需另装 ffmpeg
    命令，也避免两次解码的采样差异。

## 2026-08-08 时间轴方案补充调研

用户提供的公开经验指出：Whisper 听写轴通常会有约一个音节、约 0.3 秒的偏差；若先把文本
重新断句，再按字数组装时间戳，偏差会进一步累积。该结论与本项目问题一致：此前将字幕合并
成 30 秒/240 字上下文，MiniMax 校订后再按字符比例切分，导致“幸存”“神器”等词跨句移动。

本轮采用 MIT 许可的 `jianfch/stable-ts`，其能力与该方法最接近：利用真实音频的静音区约束
Whisper 词级时间戳，再由项目按停顿和标点排版。`WhisperX` 的 wav2vec2 强制对齐精度上限
更高，但需要额外中文对齐模型与更重的 Torch 推理，保留为服务器 GPU 条件允许时的第二级方案。

七牛云实训营公开项目 `moyu-flowsub`、`VoiceBridgeAI` 方向偏实时字幕/同声传译；当前迅雷
AI 片库是上传后离线整理，因此本轮不采用七牛云方案，也不在播放器中展示实时状态协议。产品
只保留“小红书烤肉/对轴”方法中适合离线处理的部分：后台先出词轴、再按真实停顿和标点对轴、
最后校订低置信文本。

产品 Demo 已把该方法前置到数据生产环节：3 个中文内置演示视频均以精准模式预处理结果进入
片库，`asrModel` 标记为 `faster-whisper large-v3 + stable-ts · CPU int8 + MiniMax-M3`。
播放器不再提供“精修”标签页，避免把内部质量流程变成用户额外操作负担。英文素材仅保留 1 条
作为跨语言基准，不标记为中文精准链路。

完整 135 秒中文样例的真实 CPU 验证耗时 277.65 秒，生成 76 个原始段。目标片段抽检如下：

| 文本 | stable-ts 词轴 | Ground Truth | 起点偏差 | 终点偏差 |
|---|---:|---:|---:|---:|
| 最后一只烛龙老死 | 67.33—68.67 | 67.47—68.69 | -0.14 秒 | -0.02 秒 |
| 只剩一颗龙蛋幸存 | 68.67—69.99 | 68.89—70.03 | -0.22 秒 | -0.04 秒 |
| 死后力量凝聚的遗蜕 | 69.99—71.43 | 70.25—71.45 | -0.26 秒 | -0.02 秒 |
| 也成为了各族持有的神器 | 71.43—73.21 | 71.67—73.21 | -0.24 秒 | 0.00 秒 |

该结果证明波形静音抑制可把句末收紧到参考边界附近，但句首仍有约 0.14—0.26 秒提前，不能
宣传为毫秒级强制对齐。若评测要求继续提高，下一步应在 GPU 服务上评估 WhisperX 中文
wav2vec2 对齐，并用同一 Ground Truth 比较起止平均绝对误差、最大误差与实时因子。

该视频的完整 FastAPI 链路已于 2026-08-08 实测完成：真实上传 288,568,759 字节文件，
large-v3 从音轨生成 156 个原始语音段，经阅读分段生成 104 条 VTT 字幕；MiniMax-M3 生成
简体中文摘要与章节。首次返回的 12 个章节只覆盖到 281 秒，新增覆盖校验后使用 37 个整理段
复测得到 8 个章节并覆盖到 541.96 秒。该问题已纳入自动化回归测试。

代码出处：

- `backend/app/integrations/asr.py`
- `backend/app/integrations/minimax.py`
- `backend/app/services/content_analysis.py`
- `backend/app/services/subtitle_alignment.py`
- `backend/app/services/subtitle_review.py`
- `backend/app/services/text_normalization.py`
- `backend/tools/align_vtt_timing.py`

## 内置样例时间轴校准

校准对象分别使用 `0 / 135 / 270` 秒源视频偏移。每条 AI 字幕只在原时间附近搜索连续参考
片段，可靠锚点直接采用参考时间；无法可靠匹配的字幕按前后锚点平移。多条 AI 字幕命中同一
参考片段时，以相邻目标中心的中点消除重叠，同时保留参考字幕中原有的静音间隔。

| 视频 ID | 字幕数 | 可靠锚点 | 平均中心修正 | 最大中心修正 |
|---|---:|---:|---:|---:|
| `parsevideo-chinese-demo` | 58 | 57 | 0.698 秒 | 2.702 秒 |
| `eternal-night-survival` | 60 | 56 | 1.005 秒 | 4.303 秒 |
| `eternal-night-civilization` | 62 | 57 | 0.945 秒 | 2.377 秒 |

截图所示片段校准后，“攻击力同理”为 `01:58.667—01:59.500`，“三月初超凡者小队抵达
战斗地点”为 `01:59.500—02:02.000`，不再在上一句音轨仍未结束时提前显示。报告位于
`output/*-subtitle-alignment.json`。

2026-08-08 继续按用户截图抽检 `eternal-night-survival` 的 `00:26—00:38`：将误识别的
“乱世用重点没有”修正为“乱世用重典”，将“一位士兵命途的迎接”修正为“一位士兵命途的
超凡者”，并把后一句拆为“外加四位士兵将一位囚徒带到野外处决”。改动同时写入
`app/public/demo/eternal-night-survival.ai.zh-CN.vtt` 和
`app/public/demo/eternal-night-survival.analysis.json`，确保内置演示视频打开即展示修正后的
预计算结果。

## 当前评测结果

评测对象为 `parsevideo-chinese-demo`。视频内嵌字幕只作为离线 Ground Truth，不参与产品字幕
生成，也不运行 OCR。评测命令：

```powershell
cd E:\xunlei\backend
.\.venv\Scripts\python.exe tools\evaluate_asr.py `
  tests\fixtures\parsevideo-reference.zh-CN.vtt `
  ..\app\public\demo\parsevideo-chinese-demo.ai.zh-CN.vtt
```

| 版本 | 字符错误率 CER | 说明 |
|---|---:|---|
| 纯音频 FunASR 原始评测 | 11.98% | 未做内容校订 |
| 历史保守术语纠错结果 | 10.31% | 旧评测文件，排版仍有明显断词 |
| 当前公开排版版 | 10.95% | 保留 ASR 句界并修复“幸存/神器”等错误切分后的结果 |
| faster-whisper small CPU | 14.56% | 135 秒素材耗时 120.33 秒，仅作方向性对比 |
| faster-whisper large-v3 CPU | 待同源 CER | 541.955 秒用户视频耗时 997.06 秒，生成 156 段 |

当前结果只能证明字幕阅读边界得到改善，不能证明 large-v3 的识别准确率已经优于当前基线。
显示层移除标点不影响 CER
评测时的文本规范化。已知误识别仍包括“四足/四族”、
“邪虫/邪祟”“让众/让众生”等。下一阶段应在相同 Ground Truth 上评测 SenseVoice、较大
精准模式已经接入 faster-whisper large-v3，但仍需在相同 Ground Truth 上完成 CER、实时因子
和人工抽检对比；只有 CER 低于 10.31% 且人工抽检通过后，才能把它升级为默认模式。

当前 Windows 机器能识别 RTX 5060，但 CTranslate2 实跑检测到 CUDA 12 cuBLAS 动态库缺失，
因此本轮没有伪造 large-v3 GPU 性能数据。精准模式默认可用 CPU `int8`，GPU 部署必须预装
CUDA 12 cuBLAS 与 cuDNN 9，并在部署后重新记录速度和 CER。

small 模型的本机结果证明“换成 Whisper”本身不等于更准确；精准模式采用 large-v3 是为了
提供更高上限，而不是预设它必然胜出。对比产物位于 `output/faster-whisper-small.zh-CN.vtt`
和 `output/faster-whisper-small-eval.json`。

## 真实性边界

- 生产字幕文本只读取音轨，不读取画面文字和内嵌字幕。
- 内嵌字幕仅用于内置样例的离线 CER 评测与时间轴 Ground Truth 校准，不参与文本生成。
- MiniMax-M3 负责文本校订与内容结构，不作为音频 ASR 使用。
- 英文基准教程已有公开 TimedText，因此标记为原视频字幕，不冒充 AI 生成。
- 预计算数据只用于保证评审即时体验；用户导入其他视频时仍会进入 FastAPI 分析队列。
