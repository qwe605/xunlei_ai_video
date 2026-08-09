import { z } from 'zod'
import type { EvidenceSegment, Video } from '../data/schema'
import type { SearchMode, SearchResult } from '../lib/search'

const citationSchema = z.object({
  id: z.string().min(1),
  videoId: z.string().min(1),
  startSeconds: z.number().nonnegative(),
  endSeconds: z.number().positive(),
  text: z.string().min(1),
  sourceType: z.enum(['filename', 'metadata', 'subtitle', 'summary', 'chapter']),
  confidence: z.number().min(0).max(1),
})

const resultSchema = z.object({
  videoId: z.string().min(1),
  score: z.number().nonnegative(),
  confidenceLabel: z.enum(['高', '中', '低']),
  matchReasons: z.array(z.string().min(1)).default([]),
  citations: z.array(citationSchema).default([]),
})

const responseSchema = z.object({
  query: z.string(),
  mode: z.string(),
  total: z.number().int().nonnegative(),
  results: z.array(resultSchema),
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

export async function searchPersistedVideos(
  query: string,
  mode: SearchMode,
  videos: Video[],
): Promise<SearchResult[]> {
  const response = await fetch('/api/v1/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      mode: mode === 'filename' ? 'filename' : 'hybrid',
      limit: 10,
    }),
  })
  if (!response.ok) throw new Error('服务端搜索暂不可用')

  const videoById = new Map(videos.map((video) => [video.id, video]))
  return responseSchema
    .parse(await response.json())
    .results.map((result) => {
      const video = videoById.get(result.videoId)
      if (!video) return null
      return {
        video,
        score: result.score,
        confidenceLabel: result.confidenceLabel,
        matchReasons: result.matchReasons,
        evidence: result.citations.map(toEvidence),
      }
    })
    .filter((result): result is SearchResult => result !== null)
}
