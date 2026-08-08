param(
    [string]$OutputPath = ""
)

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $OutputPath = Join-Path $projectRoot "tmp\recording\xunlei-ai-library-voiceover.wav"
}

# 使用 Windows 自带中文语音生成提交视频旁白，避免依赖在线 TTS 服务或 API Key。
Add-Type -AssemblyName System.Speech
$outputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

$narration = @"
大家好，这是迅雷 AI 片库。它面向拥有大量云端视频的用户，解决“我明明存过，却怎么也找不到”的问题。
当云盘进入 TB 级规模，用户往往只记得某个场景、演员或知识点，却记不住由发布组、编码和缩写组成的文件名。即使找到视频，也要逐个试播并反复拖动进度条。
评委可以直接导入自己的 MP4 或 WebM。系统会真实读取时长、分辨率和文件大小，从视频抽取封面，并在当前会话直接播放，不会替换成内置素材。
在首页，我们可以直接提出模糊需求：找讲 Python 名字由来的视频。
系统不只匹配文件名，还会理解摘要、标签和智能章节。第一条结果指出最相关内容位于两分零四秒，并解释视频讲到了 Monty Python。
进入详情页，用户可以在播放前阅读整片摘要，并通过六个智能章节快速理解内容结构。
点击“Python 名字的由来”，播放器会从两分零四秒真实开始，并播放公开授权原片的画面和声音。
接着询问：后面有没有讲保留字？回答只使用当前视频字幕，并引用十一分二十八秒到十一分四十秒的证据。点击证据，时间轴会直接跳到对应片段。

对于没有现成字幕的视频，系统使用 faster-whisper 自动转写。演示中的异常处理教程已经实际生成三十四段可跳转英文字幕。
如果询问视频里不存在的北京餐厅，系统会明确说明没有找到相关内容，而不是调用模型常识编造答案。
生产环境可以复用 FFprobe、faster-whisper、PySceneDetect、BGE-M3 和 pgvector 等成熟组件，在继承原文件权限的前提下预生成索引。
迅雷 AI 片库，让用户从一句模糊记忆出发，最终抵达可验证的视频内容。
"@

$synthesizer = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $synthesizer.SelectVoice("Microsoft Huihui Desktop")
    # 语速 5 与约 80 秒的产品交互录屏匹配，同时仍保留中文解说的可懂度。
    $synthesizer.Rate = 5
    $synthesizer.Volume = 100
    $synthesizer.SetOutputToWaveFile($OutputPath)
    $synthesizer.Speak($narration)
}
finally {
    $synthesizer.Dispose()
}

Get-Item -LiteralPath $OutputPath | Select-Object FullName, Length
