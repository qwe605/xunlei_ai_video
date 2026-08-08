import { z } from 'zod'

export const indexStatusSchema = z.enum([
  'pending',
  'processing',
  'ready',
  'failed',
  'disabled',
])

export const chapterSchema = z
  .object({
    id: z.string().min(1),
    title: z.string().min(1),
    startSeconds: z.number().nonnegative(),
    endSeconds: z.number().positive(),
    summary: z.string().min(1),
    source: z.enum(['subtitle', 'scene', 'multimodal', 'manual']),
    confidence: z.number().min(0).max(1),
    spoilerLevel: z.enum(['none', 'mild', 'major']),
  })
  .refine((chapter) => chapter.startSeconds < chapter.endSeconds, {
    message: '章节结束时间必须晚于开始时间',
  })

export const evidenceSchema = z
  .object({
    id: z.string().min(1),
    startSeconds: z.number().nonnegative(),
    endSeconds: z.number().positive(),
    text: z.string().min(1),
    sourceType: z.enum(['filename', 'metadata', 'subtitle', 'summary', 'visual']),
    confidence: z.number().min(0).max(1),
  })
  .refine((evidence) => evidence.startSeconds < evidence.endSeconds, {
    message: '证据片段结束时间必须晚于开始时间',
  })

export const videoQaSchema = z
  .object({
    id: z.string().min(1),
    keywords: z.array(z.string().min(1)).min(1),
    question: z.string().min(1),
    answer: z.string().min(1).max(180),
    grounded: z.boolean(),
    confidence: z.number().min(0).max(1),
    citations: z.array(evidenceSchema).max(3),
  })
  .superRefine((item, context) => {
    // “有依据”是问视频功能的可信底线：不能一边声称有证据，一边不给用户可核验的片段。
    if (item.grounded && item.citations.length === 0) {
      context.addIssue({
        code: 'custom',
        message: '有依据的回答至少需要一个引用片段',
      })
    }
    if (!item.grounded && item.citations.length > 0) {
      context.addIssue({
        code: 'custom',
        message: '无依据回答不能携带伪造引用',
      })
    }
  })

export const videoSchema = z
  .object({
    id: z.string().min(1),
    title: z.string().min(1),
    originalFilename: z.string().min(1),
    mediaType: z.enum(['tutorial', 'movie', 'series', 'meeting', 'game', 'cooking', 'other']),
    durationSeconds: z.number().positive(),
    resolution: z.string().min(1),
    codec: z.string().min(1),
    language: z.string().min(1),
    savedAt: z.string().datetime(),
    watchProgressSeconds: z.number().nonnegative(),
    indexStatus: indexStatusSchema,
    indexLevel: z.enum(['L0', 'L1', 'L2', 'L3']),
    confidence: z.number().min(0).max(1),
    shortDescription: z.string().min(1),
    summary: z.string().min(1),
    tags: z.array(z.string().min(1)).min(1).max(8),
    thumbnailCell: z.number().int().min(0).max(11),
    thumbnailUrl: z.string().min(1).optional(),
    posterUrl: z.string().min(1),
    videoUrl: z.string().min(1),
    videoMimeType: z.enum(['video/mp4', 'video/webm']),
    subtitlesUrl: z.string().min(1).optional(),
    subtitleOrigin: z.enum(['provided', 'ai-generated', 'processing']),
    asrModel: z.string().min(1).optional(),
    importSource: z.enum(['demo-public', 'local']),
    sourceAttribution: z
      .object({
        author: z.string().min(1),
        sourceUrl: z.string().url(),
        license: z.string().min(1),
        licenseUrl: z.string().url(),
      })
      .optional(),
    spoilerProtected: z.boolean(),
    duplicateHint: z.string().optional(),
    organizeHint: z.string().optional(),
    chapters: z.array(chapterSchema),
    qa: z.array(videoQaSchema),
  })
  .superRefine((video, context) => {
    if (video.importSource === 'demo-public' && !video.sourceAttribution) {
      context.addIssue({
        code: 'custom',
        path: ['sourceAttribution'],
        message: '公开演示素材必须保留作者、来源和许可证',
      })
    }
    if (video.subtitleOrigin !== 'processing' && !video.subtitlesUrl) {
      context.addIssue({
        code: 'custom',
        path: ['subtitlesUrl'],
        message: '已有字幕或 AI 字幕必须提供可加载的字幕轨',
      })
    }
    if (video.subtitleOrigin === 'ai-generated' && !video.asrModel) {
      context.addIssue({
        code: 'custom',
        path: ['asrModel'],
        message: 'AI 字幕必须记录实际使用的 ASR 模型',
      })
    }
    if (video.watchProgressSeconds > video.durationSeconds) {
      context.addIssue({
        code: 'custom',
        message: '观看进度不能超过视频时长',
      })
    }

    video.chapters.forEach((chapter, index) => {
      if (chapter.endSeconds > video.durationSeconds) {
        context.addIssue({
          code: 'custom',
          path: ['chapters', index],
          message: '章节不能超出视频时长',
        })
      }
      if (index > 0 && chapter.startSeconds < video.chapters[index - 1].startSeconds) {
        context.addIssue({
          code: 'custom',
          path: ['chapters', index],
          message: '章节必须按开始时间升序排列',
        })
      }
    })
  })

export const librarySchema = z.array(videoSchema).min(1)

export type Chapter = z.infer<typeof chapterSchema>
export type EvidenceSegment = z.infer<typeof evidenceSchema>
export type VideoQa = z.infer<typeof videoQaSchema>
export type Video = z.infer<typeof videoSchema>
export type IndexStatus = z.infer<typeof indexStatusSchema>
