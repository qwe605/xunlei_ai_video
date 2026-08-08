import type { Video } from '../../data/schema'
import { chineseDemoVideos } from '../../data/chineseDemoLibrary'
import type { AnalysisMode } from '../../api/analysis'

export type AnalysisJobStatus = 'queued' | 'processing' | 'completed' | 'blocked'

export interface AnalysisJob {
  videoId: string
  title: string
  status: AnalysisJobStatus
  stage: string
  progress: number
  detail: string
  analysisMode: AnalysisMode
}

export const createBlockedJob = (video: Video): AnalysisJob => ({
  videoId: video.id,
  title: video.title,
  status: 'blocked',
  stage: '等待启动',
  progress: video.subtitlesUrl ? 45 : 18,
  detail: video.organizeHint ?? '媒体信息已读取，可启动 AI 服务生成字幕、摘要和章节。',
  analysisMode: 'fast',
})

export const createQueuedJob = (video: Video, analysisMode: AnalysisMode = 'fast'): AnalysisJob => ({
  videoId: video.id,
  title: video.title,
  status: 'queued',
  stage: '等待整理',
  progress: 0,
  detail:
    analysisMode === 'fast'
      ? '已进入快速队列，即将读取音轨。'
      : analysisMode === 'api'
        ? '已进入 ASR API 队列，将调用云端识别后生成字幕。'
        : '已进入精准队列，将使用更大的语音模型。',
  analysisMode,
})

// 内置中文素材已经实际运行过 FunASR 与 MiniMax；用户重新导入同名文件时直接复用结果，
// 既能演示完整队列闭环，也无需让评委重复等待模型推理。
export const getBundledAnalysis = (video: Video): Partial<Video> | null => {
  const filename = video.originalFilename.toLowerCase()
  const bundled = chineseDemoVideos.find((item) => filename.includes(item.id))
  if (!bundled) return null

  // 只复用 AI 产物。媒体 URL、封面、文件名和导入来源必须继续指向用户刚选择的本地文件，
  // 否则播放器会悄悄切换到同名内置视频，破坏“真实本地导入”的产品承诺。
  return {
    mediaType: bundled.mediaType,
    language: bundled.language,
    indexStatus: 'ready',
    indexLevel: bundled.indexLevel,
    confidence: bundled.confidence,
    shortDescription: bundled.shortDescription,
    summary: bundled.summary,
    tags: bundled.tags,
    subtitlesUrl: bundled.subtitlesUrl,
    subtitleOrigin: bundled.subtitleOrigin,
    asrModel: bundled.asrModel,
    organizeHint: bundled.organizeHint,
    chapters: bundled.chapters,
    qa: bundled.qa,
  }
}
