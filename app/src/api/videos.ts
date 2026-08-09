import { z } from 'zod'
import fallbackPoster from '../assets/hero.png'
import { videoSchema, type Video } from '../data/schema'

const userProgressSchema = z.object({
  lastPositionSeconds: z.number().nonnegative(),
  completedPercent: z.number().min(0).max(1),
})

const chapterSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  startSeconds: z.number().nonnegative(),
  endSeconds: z.number().positive(),
  summary: z.string().min(1),
  source: z.enum(['subtitle', 'scene', 'multimodal', 'manual']).catch('subtitle'),
  confidence: z.number().min(0).max(1),
  spoilerLevel: z.enum(['none', 'mild', 'major']).catch('none'),
})

const videoDetailSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  originalFilename: z.string().min(1),
  mediaType: z.enum(['tutorial', 'movie', 'series', 'meeting', 'game', 'cooking', 'other']).catch('other'),
  durationSeconds: z.number().positive(),
  resolution: z.string().min(1),
  codec: z.string().min(1),
  language: z.string().min(1),
  savedAt: z.string().min(1),
  indexStatus: z.enum(['pending', 'processing', 'ready', 'failed', 'disabled']),
  indexLevel: z.enum(['L0', 'L1', 'L2', 'L3']),
  confidence: z.number().min(0).max(1),
  shortDescription: z.string().min(1),
  summary: z.string().min(1),
  subtitleOrigin: z.enum(['provided', 'ai-generated', 'processing']),
  asrModel: z.string().nullable().optional(),
  importSource: z.enum(['demo-public', 'local']).catch('local'),
  spoilerProtected: z.boolean(),
  organizeHint: z.string().nullable().optional(),
  hasPoster: z.boolean().default(false),
  tags: z.array(z.string().min(1)).default([]),
  progress: userProgressSchema.nullable().optional(),
  chapters: z.array(chapterSchema).default([]),
})

const videoListSchema = z.array(videoDetailSchema)

type PersistedVideoDetail = z.infer<typeof videoDetailSchema>

const mediaUrl = (videoId: string) => `/api/v1/videos/${encodeURIComponent(videoId)}/media`
const posterUrl = (videoId: string) =>
  `/api/v1/videos/${encodeURIComponent(videoId)}/assets/poster`
const subtitleUrl = (videoId: string) =>
  `/api/v1/videos/${encodeURIComponent(videoId)}/subtitles/active`

export function toClientVideo(video: PersistedVideoDetail): Video {
  const progress = video.progress?.lastPositionSeconds ?? 0
  return videoSchema.parse({
    id: video.id,
    title: video.title,
    originalFilename: video.originalFilename,
    mediaType: video.mediaType,
    durationSeconds: video.durationSeconds,
    resolution: video.resolution,
    codec: video.codec,
    language: video.language,
    savedAt: new Date(video.savedAt).toISOString(),
    watchProgressSeconds: Math.min(progress, video.durationSeconds),
    indexStatus: video.indexStatus,
    indexLevel: video.indexLevel,
    confidence: video.confidence,
    shortDescription: video.shortDescription,
    summary: video.summary,
    tags: video.tags.length > 0 ? video.tags : ['本地导入'],
    thumbnailCell: 0,
    thumbnailUrl: video.hasPoster ? posterUrl(video.id) : fallbackPoster,
    posterUrl: video.hasPoster ? posterUrl(video.id) : fallbackPoster,
    videoUrl: mediaUrl(video.id),
    videoMimeType: video.originalFilename.toLowerCase().endsWith('.webm') ? 'video/webm' : 'video/mp4',
    subtitlesUrl: video.subtitleOrigin === 'processing' ? undefined : subtitleUrl(video.id),
    subtitleOrigin: video.subtitleOrigin,
    asrModel: video.asrModel ?? undefined,
    importSource: video.importSource,
    spoilerProtected: video.spoilerProtected,
    organizeHint: video.organizeHint ?? undefined,
    chapters: video.chapters,
    qa: [],
  })
}

export async function readPersistedVideos(): Promise<Video[]> {
  const response = await fetch('/api/v1/videos')
  if (!response.ok) throw new Error('无法读取服务端片库')
  return videoListSchema.parse(await response.json()).map(toClientVideo)
}

export async function readPersistedVideo(videoId: string): Promise<Video> {
  const response = await fetch(`/api/v1/videos/${encodeURIComponent(videoId)}`)
  if (!response.ok) throw new Error('无法读取视频详情')
  return toClientVideo(videoDetailSchema.parse(await response.json()))
}

export interface VideoInformationUpdate {
  title: string
  shortDescription: string
  summary: string
  tags: string[]
}

export async function updateVideoInformation(
  videoId: string,
  payload: VideoInformationUpdate,
): Promise<Video> {
  const response = await fetch(`/api/v1/videos/${encodeURIComponent(videoId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? '纠正信息保存失败')
  }
  return toClientVideo(videoDetailSchema.parse(await response.json()))
}

export async function saveWatchProgress(video: Video, positionSeconds: number): Promise<void> {
  await fetch(`/api/v1/videos/${encodeURIComponent(video.id)}/progress`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      positionSeconds: Math.min(positionSeconds, video.durationSeconds),
      durationSeconds: video.durationSeconds,
    }),
  })
}

export async function deletePersistedVideo(videoId: string): Promise<void> {
  const response = await fetch(`/api/v1/videos/${encodeURIComponent(videoId)}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? '删除视频失败')
  }
}
