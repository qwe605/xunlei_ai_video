import { z } from 'zod'
import type { EvidenceSegment, VideoQa } from '../data/schema'

const citationSchema = z.object({
  id: z.string().min(1),
  videoId: z.string().min(1),
  startSeconds: z.number().nonnegative(),
  endSeconds: z.number().positive(),
  text: z.string().min(1),
  sourceType: z.enum(['filename', 'metadata', 'subtitle', 'summary', 'chapter']),
  confidence: z.number().min(0).max(1),
})

const responseSchema = z.object({
  videoId: z.string().min(1),
  question: z.string().min(1),
  status: z.enum(['answered', 'no_evidence']),
  answer: z.string().nullable().optional(),
  confidence: z.number().min(0).max(1),
  citations: z.array(citationSchema).default([]),
})

function toEvidence(citation: z.infer<typeof citationSchema>): EvidenceSegment {
  return {
    id: citation.id,
    startSeconds: citation.startSeconds,
    endSeconds: citation.endSeconds,
    text: citation.text,
    sourceType: citation.sourceType === 'chapter' ? 'summary' : citation.sourceType,
    confidence: citation.confidence,
  }
}

export async function askPersistedVideo(videoId: string, question: string): Promise<VideoQa | null> {
  const response = await fetch(`/api/v1/videos/${encodeURIComponent(videoId)}/questions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      limit: 5,
    }),
  })
  if (!response.ok) throw new Error('问视频服务暂不可用')

  const payload = responseSchema.parse(await response.json())
  if (payload.status === 'no_evidence' || !payload.answer || payload.citations.length === 0) {
    return null
  }

  return {
    id: `backend-${payload.videoId}-${Date.now()}`,
    keywords: [question],
    question: payload.question,
    answer: payload.answer,
    grounded: true,
    confidence: payload.confidence,
    citations: payload.citations.map(toEvidence),
  }
}
