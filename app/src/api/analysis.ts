import { z } from 'zod'

const chapterResultSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  startSeconds: z.number().nonnegative(),
  endSeconds: z.number().positive(),
  summary: z.string().min(1),
  source: z.literal('subtitle'),
  confidence: z.number().min(0).max(1),
  spoilerLevel: z.literal('none'),
})

const analysisResultSchema = z.object({
  language: z.string().min(1),
  confidence: z.number().min(0).max(1),
  shortDescription: z.string().min(1),
  summary: z.string().min(1),
  tags: z.array(z.string().min(1)).min(1).max(8),
  subtitlesVtt: z.string().startsWith('WEBVTT'),
  asrModel: z.string().min(1),
  subtitleCorrectionCount: z.number().int().nonnegative().optional(),
  chapters: z.array(chapterResultSchema).min(1),
})

const analysisJobSchema = z.object({
  id: z.string().min(1),
  videoId: z.string().min(1),
  status: z.enum(['queued', 'processing', 'completed', 'failed']),
  stage: z.string().min(1),
  progress: z.number().int().min(0).max(100),
  detail: z.string().min(1),
  result: analysisResultSchema.nullable().optional(),
  errorCode: z.string().nullable().optional(),
})

export type LocalAnalysisJob = z.infer<typeof analysisJobSchema>
export type AnalysisMode = 'fast' | 'precise'

const analysisCapabilitiesSchema = z.object({
  preciseModel: z.string().min(1),
  preciseModelReady: z.boolean(),
})

export type AnalysisCapabilities = z.infer<typeof analysisCapabilitiesSchema>

const parseResponse = async (response: Response) => {
  // 后端和大模型结果均不可信，进入应用状态前必须通过 Zod 契约。
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `AI 分析服务返回 ${response.status}`)
  }
  return analysisJobSchema.parse(await response.json())
}

export async function createLocalAnalysis(
  videoId: string,
  durationSeconds: number,
  file: File,
  analysisMode: AnalysisMode = 'fast',
  metadata?: {
    title?: string
    resolution?: string
    codec?: string
    width?: number
    height?: number
  },
): Promise<LocalAnalysisJob> {
  const body = new FormData()
  body.set('video_id', videoId)
  body.set('duration_seconds', String(durationSeconds))
  body.set('video', file)
  body.set('analysis_mode', analysisMode)
  if (metadata?.title) body.set('title', metadata.title)
  if (metadata?.resolution) body.set('resolution', metadata.resolution)
  if (metadata?.codec) body.set('codec', metadata.codec)
  if (metadata?.width !== undefined) body.set('width', String(metadata.width))
  if (metadata?.height !== undefined) body.set('height', String(metadata.height))
  return parseResponse(
    await fetch('/api/v1/analyses', {
      method: 'POST',
      body,
    }),
  )
}

export async function readLocalAnalysis(jobId: string): Promise<LocalAnalysisJob> {
  return parseResponse(await fetch(`/api/v1/analyses/${encodeURIComponent(jobId)}`))
}

export async function readAnalysisCapabilities(): Promise<AnalysisCapabilities> {
  const response = await fetch('/api/v1/health')
  if (!response.ok) throw new Error('无法读取语音模型状态')
  return analysisCapabilitiesSchema.parse(await response.json())
}
